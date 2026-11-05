from __future__ import annotations

import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import sessionmaker

from app.db_models import ActionItemRecord, DecisionRecord, MeetingRecord, TurnRecord
from app.llm import LLMProvider
from app.services.extraction import format_timestamp
from app.services.retrieval import RetrievedChunk, Retriever, SearchFilters

NOT_FOUND = "I couldn't find anything about that in the meeting transcripts."

# bge-small cosine similarity: on-topic questions score ~0.64+, unrelated ones ~0.55.
DEFAULT_MIN_SIMILARITY = 0.60
DEFAULT_TOP_K = 6
MAX_FACTS = 30

# Reference numbers only, never example facts: small local models copy examples verbatim.
SYSTEM_PROMPT = f"""You answer questions about meetings using ONLY the evidence provided by the user.

The evidence contains transcript lines, each starting with a reference number in square brackets,
and facts extracted from those meetings, each ending with the reference number of its source line.

Rules:
- Use only the evidence. Never use outside knowledge and never guess.
- After every statement, cite the reference number(s) of the lines that support it in square
  brackets, for example [3] or [3][8]. Cite only numbers that appear in the evidence.
- If the evidence does not answer the question, reply with exactly this sentence and nothing else:
  {NOT_FOUND}
- Be concise and direct. Use a short bulleted list when listing several items.
- Refer to people by name and mention which meeting something came from when it helps."""


@dataclass
class Source:
    """A transcript turn the model may cite, by its reference number."""

    ref: int
    meeting_id: str
    meeting_title: str
    turn_idx: int
    speaker: str
    start: float
    text: str

    @property
    def timestamp(self) -> str:
        return format_timestamp(self.start)

    @property
    def citation(self) -> str:
        return f"[{self.meeting_title}, {self.timestamp}, {self.speaker}]"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "timestamp": self.timestamp, "citation": self.citation}


@dataclass
class Evidence:
    sources: list[Source] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    chunks: list[RetrievedChunk] = field(default_factory=list)
    owner_named: bool = False  # the question names someone who owns an action item

    def by_ref(self) -> dict[int, Source]:
        return {source.ref: source for source in self.sources}


@dataclass
class AnswerEvent:
    type: str  # "citations" | "token" | "done"
    data: dict[str, Any]


class CitationRewriter:
    """Rewrites "[3]" / "[3, 8]" into "[meeting, hh:mm:ss, speaker]" in a token stream.

    Tokens can split a bracket ("[", "1", "2]"), so text after an opening bracket is held back
    until it closes. References the model invented (not in the evidence) are removed.
    """

    REF_RE = re.compile(r"\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]")
    MAX_PENDING = 24

    def __init__(self, sources: dict[int, Source]) -> None:
        self.sources = sources
        self.cited: list[int] = []
        self._pending = ""

    def feed(self, text: str) -> str:
        self._pending += text
        out = []
        while self._pending:
            start = self._pending.find("[")
            if start == -1:
                out.append(self._pending)
                self._pending = ""
                break
            out.append(self._pending[:start])
            self._pending = self._pending[start:]
            end = self._pending.find("]")
            if end == -1:
                if len(self._pending) > self.MAX_PENDING:  # not a reference; let it through
                    out.append(self._pending[0])
                    self._pending = self._pending[1:]
                    continue
                break
            out.append(self._replace(self._pending[: end + 1]))
            self._pending = self._pending[end + 1 :]
        return "".join(out)

    def flush(self) -> str:
        rest, self._pending = self._pending, ""
        return rest

    def _replace(self, bracket: str) -> str:
        match = self.REF_RE.fullmatch(bracket)
        if not match:
            return bracket
        parts = []
        for number in (int(n) for n in re.split(r"\s*,\s*", match.group(1))):
            source = self.sources.get(number)
            if source is None:
                continue
            if number not in self.cited:
                self.cited.append(number)
            parts.append(source.citation)
        return "".join(parts)


class Answerer:
    """Grounded Q&A: retrieve evidence, ask the LLM, stream an answer with citations."""

    def __init__(
        self,
        session_factory: sessionmaker,
        retriever: Retriever,
        llm: Optional[LLMProvider] = None,
        top_k: int = DEFAULT_TOP_K,
        min_similarity: float = DEFAULT_MIN_SIMILARITY,
    ) -> None:
        self.session_factory = session_factory
        self.retriever = retriever
        self._llm = llm
        self.top_k = top_k
        self.min_similarity = min_similarity

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            from app.llm import get_llm

            self._llm = get_llm()
        return self._llm

    @llm.setter
    def llm(self, value: LLMProvider) -> None:
        self._llm = value

    def answer(self, question: str, filters: Optional[SearchFilters] = None) -> Iterator[AnswerEvent]:
        started = time.monotonic()
        filters = filters or SearchFilters()
        evidence = self.gather_evidence(question, filters)
        relevant = self.is_relevant(evidence, filters)
        sources = evidence.by_ref() if relevant else {}
        yield AnswerEvent("citations", {"sources": [s.to_dict() for s in sources.values()]})

        usage: dict[str, Optional[int]] = {"prompt_tokens": None, "output_tokens": None}
        if not relevant:
            yield AnswerEvent("token", {"text": NOT_FOUND})
            answer = NOT_FOUND
            cited: list[int] = []
        else:
            rewriter = CitationRewriter(sources)
            parts = []
            for chunk in self.llm.stream_chat(SYSTEM_PROMPT, build_user_prompt(question, evidence)):
                text = rewriter.feed(chunk.text)
                if chunk.done:
                    text += rewriter.flush()
                    usage = {"prompt_tokens": chunk.prompt_tokens, "output_tokens": chunk.output_tokens}
                if text:
                    parts.append(text)
                    yield AnswerEvent("token", {"text": text})
            tail = rewriter.flush()  # in case the stream ended without a done chunk
            if tail:
                parts.append(tail)
                yield AnswerEvent("token", {"text": tail})
            answer = "".join(parts).strip()
            cited = rewriter.cited

        found = relevant and bool(cited) and NOT_FOUND not in answer
        yield AnswerEvent(
            "done",
            {
                "answer": answer,
                "found": found,
                "cited": [sources[ref].to_dict() for ref in cited],
                "retrieved_chunk_ids": [chunk.chunk_id for chunk in evidence.chunks],
                "latency_ms": int((time.monotonic() - started) * 1000),
                **usage,
            },
        )

    def is_relevant(self, evidence: Evidence, filters: SearchFilters) -> bool:
        if not evidence.sources:
            return False
        if filters.meeting_ids:
            return True  # the user scoped the question to specific meetings; let the model judge
        # Cheap pre-filter only; the model's NOT_FOUND reply is the second line of defence.
        # Similarity alone is too coarse for short questions, so a keyword hit also lets it through.
        best = max((chunk.similarity or 0.0 for chunk in evidence.chunks), default=0.0)
        keyword_hit = any(chunk.text_rank is not None for chunk in evidence.chunks)
        return best >= self.min_similarity or keyword_hit or evidence.owner_named

    def gather_evidence(self, question: str, filters: SearchFilters) -> Evidence:
        chunks = self.retriever.retrieve(question, filters, k=self.top_k)
        meeting_order = list(dict.fromkeys(chunk.meeting_id for chunk in chunks))

        with self.session_factory() as session:
            turn_keys = {
                (chunk.meeting_id, idx)
                for chunk in chunks
                for idx in range(chunk.first_turn_idx, chunk.last_turn_idx + 1)
            }
            decisions = self._decisions(session, meeting_order)
            actions, owner_named = self._action_items(session, meeting_order, question, filters)
            if not chunks and not actions:
                return Evidence()
            # Facts must cite a line the model can see, so include their source turns too.
            turn_keys |= {(r.meeting_id, r.turn_idx) for r in [*decisions, *actions]}
            for record in actions:
                if record.meeting_id not in meeting_order:
                    meeting_order.append(record.meeting_id)
            turns = self._turns(session, turn_keys)

        rank = {meeting_id: i for i, meeting_id in enumerate(meeting_order)}
        turns.sort(key=lambda row: (rank[row.meeting_id], row.idx))
        evidence = Evidence(chunks=chunks, owner_named=owner_named)
        ref_of: dict[tuple[str, int], int] = {}
        for ref, row in enumerate(turns, start=1):
            evidence.sources.append(
                Source(ref, row.meeting_id, row.title, row.idx, row.speaker, row.start_ts, row.text)
            )
            ref_of[(row.meeting_id, row.idx)] = ref

        for record in decisions:
            evidence.facts.append(f"Decision: {record.text} [{ref_of[(record.meeting_id, record.turn_idx)]}]")
        for record in actions:
            due = f" (due: {record.due})" if record.due else ""
            ref = ref_of[(record.meeting_id, record.turn_idx)]
            evidence.facts.append(f"Action item: {record.owner} will {record.task}{due} [{ref}]")
        evidence.facts = evidence.facts[:MAX_FACTS]
        return evidence

    @staticmethod
    def _turns(session, keys: set[tuple[str, int]]):
        if not keys:
            return []
        conditions = [and_(TurnRecord.meeting_id == m, TurnRecord.idx == i) for m, i in keys]
        return list(
            session.execute(
                select(
                    TurnRecord.meeting_id,
                    TurnRecord.idx,
                    TurnRecord.speaker,
                    TurnRecord.start_ts,
                    TurnRecord.text,
                    MeetingRecord.title,
                )
                .join(MeetingRecord, MeetingRecord.id == TurnRecord.meeting_id)
                .where(or_(*conditions))
            ).all()
        )

    @staticmethod
    def _decisions(session, meeting_ids: list[str]):
        if not meeting_ids:
            return []
        return list(
            session.execute(
                select(DecisionRecord)
                .where(DecisionRecord.meeting_id.in_(meeting_ids))
                .order_by(DecisionRecord.meeting_id, DecisionRecord.turn_idx)
            ).scalars()
        )

    @staticmethod
    def _action_items(session, meeting_ids: list[str], question: str, filters: SearchFilters):
        """Action items from the retrieved meetings, plus any whose owner is named in the question.

        The owner lookup spans all meetings so "what does Aisha owe?" works even when retrieval
        surfaces only some of them; it is skipped when the user scoped the question by meeting or date.
        """
        conditions = []
        if meeting_ids:
            conditions.append(ActionItemRecord.meeting_id.in_(meeting_ids))
        words = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'-]+", question)}
        named = None
        if words and not (filters.meeting_ids or filters.date_from or filters.date_to):
            named = func.lower(ActionItemRecord.owner).in_(words)
            conditions.append(named)
        if not conditions:
            return [], False
        records = list(
            session.execute(
                select(ActionItemRecord)
                .where(or_(*conditions))
                .order_by(ActionItemRecord.meeting_id, ActionItemRecord.turn_idx)
            ).scalars()
        )
        owner_named = named is not None and any(r.owner.lower() in words for r in records)
        return records, owner_named


def build_user_prompt(question: str, evidence: Evidence) -> str:
    sections = []
    current_meeting = None
    lines: list[str] = []
    for source in evidence.sources:
        if source.meeting_id != current_meeting:
            if lines:
                sections.append("\n".join(lines))
            lines = [f'Meeting "{source.meeting_title}":']
            current_meeting = source.meeting_id
        lines.append(f"[{source.ref}] {source.timestamp} {source.speaker}: {source.text}")
    if lines:
        sections.append("\n".join(lines))
    evidence_text = "\n\n".join(sections)
    if evidence.facts:
        evidence_text += "\n\nExtracted facts:\n" + "\n".join(f"- {fact}" for fact in evidence.facts)
    return f"Evidence:\n{evidence_text}\n\nQuestion: {question}"
