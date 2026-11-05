from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.llm import LLMProvider
from app.models import Meeting, TranscriptTurn

logger = logging.getLogger(__name__)

# ~3k tokens of transcript per call: comfortably inside an 8k context with prompt and output.
DEFAULT_BATCH_CHARS = 12_000

# No concrete example facts in this prompt: small local models copy them verbatim into the output.
SYSTEM_PROMPT = """You extract structured records from a meeting transcript.
Each line is "[turn] hh:mm:ss Speaker: text".

Rules:
- Only record what is explicitly said. Never invent owners, dates or decisions.
- decisions: conclusions the group agreed on. Restate each as a complete sentence that names what
  was decided, using the transcript's own facts, so it makes sense without the transcript.
  Never use a bare reply such as "Agreed" or "Sounds good". "turn" = the turn where it was agreed.
- action_items: a specific person committing to, or being asked to do, a task.
  owner = that person's name exactly as it appears in the transcript.
  due = the deadline as spoken (e.g. "by Friday"), or null if none was given.
  "turn" = the turn where the commitment is made.
- topics: the main agenda subjects, 2-5 words each. "turn" = the turn where the topic starts.
- Return empty lists when there is nothing to record."""

_TURN = {"type": "integer"}
_TEXT = {"type": "string"}
EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["decisions", "action_items", "topics"],
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["turn", "decision"],
                "properties": {"turn": _TURN, "decision": _TEXT},
            },
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["turn", "owner", "task", "due"],
                "properties": {"turn": _TURN, "owner": _TEXT, "task": _TEXT, "due": {"type": ["string", "null"]}},
            },
        },
        "topics": {
            "type": "array",
            "items": {"type": "object", "required": ["turn", "label"], "properties": {"turn": _TURN, "label": _TEXT}},
        },
    },
}


@dataclass
class Decision:
    turn_idx: int
    text: str


@dataclass
class ActionItem:
    turn_idx: int
    owner: str
    task: str
    due: Optional[str] = None


@dataclass
class Topic:
    turn_idx: int
    label: str


@dataclass
class Extraction:
    decisions: list[Decision] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    topics: list[Topic] = field(default_factory=list)


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def format_turn(idx: int, turn: TranscriptTurn) -> str:
    return f"[{idx}] {format_timestamp(turn.start)} {turn.speaker}: {turn.text}"


def batch_turns(meeting: Meeting, max_chars: int = DEFAULT_BATCH_CHARS) -> list[list[int]]:
    """Split turn indices into consecutive batches whose formatted text fits ``max_chars``."""
    batches: list[list[int]] = []
    current: list[int] = []
    size = 0
    for idx, turn in enumerate(meeting.turns):
        if not turn.text.strip():
            continue
        length = len(format_turn(idx, turn)) + 1
        if current and size + length > max_chars:
            batches.append(current)
            current, size = [], 0
        current.append(idx)
        size += length
    if current:
        batches.append(current)
    return batches


class Extractor:
    """Extracts decisions, action items and topics, each linked to its source turn."""

    def __init__(self, llm: LLMProvider, batch_chars: int = DEFAULT_BATCH_CHARS) -> None:
        self.llm = llm
        self.batch_chars = batch_chars

    def extract(self, meeting: Meeting) -> Extraction:
        result = Extraction()
        for batch in batch_turns(meeting, self.batch_chars):
            transcript = "\n".join(format_turn(idx, meeting.turns[idx]) for idx in batch)
            raw = self.llm.complete_json(SYSTEM_PROMPT, f"Transcript:\n{transcript}", EXTRACTION_SCHEMA)
            _merge(result, _validate(raw, meeting, set(batch)))
        return result


def _clean(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _valid_turn(item: dict[str, Any], allowed: set[int]) -> Optional[int]:
    turn = item.get("turn")
    return turn if isinstance(turn, int) and turn in allowed else None


def _validate(raw: dict[str, Any], meeting: Meeting, allowed: set[int]) -> Extraction:
    """Keep only well-formed items that cite a turn from this batch. The model is not trusted."""
    out = Extraction()
    dropped = 0
    speakers = {turn.speaker.lower(): turn.speaker for turn in meeting.turns}

    for item in _items(raw, "decisions"):
        turn, text = _valid_turn(item, allowed), _clean(item.get("decision"))
        if turn is None or not text:
            dropped += 1
            continue
        out.decisions.append(Decision(turn, text))

    for item in _items(raw, "action_items"):
        turn, owner, task = _valid_turn(item, allowed), _clean(item.get("owner")), _clean(item.get("task"))
        if turn is None or not owner or not task:
            dropped += 1
            continue
        # Normalise owner spelling to the transcript's speaker label when it is one.
        owner = speakers.get(owner.lower(), owner)
        out.action_items.append(ActionItem(turn, owner, task, _clean(item.get("due")) or None))

    for item in _items(raw, "topics"):
        turn, label = _valid_turn(item, allowed), _clean(item.get("label"))
        if turn is None or not label:
            dropped += 1
            continue
        out.topics.append(Topic(turn, label))

    if dropped:
        logger.warning("Dropped %d malformed extraction items for %s", dropped, meeting.source_name)
    return out


def _items(raw: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = raw.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _merge(into: Extraction, part: Extraction) -> None:
    into.decisions.extend(part.decisions)
    into.action_items.extend(part.action_items)
    seen = {topic.label.lower() for topic in into.topics}
    for topic in part.topics:
        if topic.label.lower() not in seen:  # a topic can recur across batches
            into.topics.append(topic)
            seen.add(topic.label.lower())
