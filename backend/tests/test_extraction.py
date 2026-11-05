import pytest

from app.llm import LLMError
from app.models import Meeting, TranscriptTurn
from app.services.extraction import Extractor, batch_turns, format_turn
from app.services.ingestion import IngestionService
from app.services.meeting_store import get_meeting
from tests.fakes import FakeEmbedder, FakeLLM

MEETING = Meeting(
    title="planning",
    source_name="planning.txt",
    turns=[
        TranscriptTurn("Priya", "Launch moves to November 17th.", 104),
        TranscriptTurn("Dana", "I'll update the press release by Wednesday.", 121),
        TranscriptTurn("Marcus", "Next topic: pricing.", 185),
    ],
)

GOOD_RESPONSE = {
    "decisions": [{"turn": 0, "decision": "Launch moves to November 17th"}],
    "action_items": [{"turn": 1, "owner": "dana", "task": "Update the press release", "due": "by Wednesday"}],
    "topics": [{"turn": 0, "label": "Launch date"}, {"turn": 2, "label": "Pricing"}],
}


def test_extract_returns_records_linked_to_turns():
    llm = FakeLLM(GOOD_RESPONSE)

    result = Extractor(llm).extract(MEETING)

    assert [(d.turn_idx, d.text) for d in result.decisions] == [(0, "Launch moves to November 17th")]
    (item,) = result.action_items
    assert (item.turn_idx, item.owner, item.task, item.due) == (1, "Dana", "Update the press release", "by Wednesday")
    assert [t.label for t in result.topics] == ["Launch date", "Pricing"]
    assert "[1] 00:02:01 Dana: I'll update the press release by Wednesday." in llm.calls[0]


def test_invalid_items_are_dropped():
    llm = FakeLLM(
        {
            "decisions": [{"turn": 99, "decision": "Hallucinated turn"}, {"turn": 0, "decision": "  "}, "junk"],
            "action_items": [
                {"turn": 1, "owner": "", "task": "No owner", "due": None},
                {"turn": "1", "owner": "Dana", "task": "Turn is a string", "due": None},
                {"turn": 1, "owner": "Dana", "task": "Valid", "due": ""},
            ],
            "topics": None,
        }
    )

    result = Extractor(llm).extract(MEETING)

    assert result.decisions == []
    assert [(a.task, a.due) for a in result.action_items] == [("Valid", None)]
    assert result.topics == []


def test_owner_not_in_transcript_is_kept_as_given():
    llm = FakeLLM(
        {"decisions": [], "action_items": [{"turn": 1, "owner": "Legal team", "task": "Review"}], "topics": []}
    )

    assert Extractor(llm).extract(MEETING).action_items[0].owner == "Legal team"


def test_long_meetings_are_extracted_in_batches_and_topics_deduplicated():
    turns = [TranscriptTurn("Alice", "x" * 80, i * 10) for i in range(10)]
    meeting = Meeting(title="long", source_name="long.txt", turns=turns)

    def respond(user):
        first_turn = int(user.split("[", 1)[1].split("]", 1)[0])
        return {"decisions": [], "action_items": [], "topics": [{"turn": first_turn, "label": "Budget"}]}

    llm = FakeLLM(respond)
    result = Extractor(llm, batch_chars=300).extract(meeting)

    assert len(llm.calls) > 1
    assert [(t.turn_idx, t.label) for t in result.topics] == [(0, "Budget")]


def test_batches_cover_every_non_empty_turn_once_and_respect_size():
    turns = [TranscriptTurn("A", "word " * 20, i) for i in range(12)] + [TranscriptTurn("A", "  ", 99)]
    meeting = Meeting(title="m", source_name="m.txt", turns=turns)

    batches = batch_turns(meeting, max_chars=400)

    assert [idx for batch in batches for idx in batch] == list(range(12))
    for batch in batches:
        assert sum(len(format_turn(i, turns[i])) + 1 for i in batch) <= 400


# --- pipeline integration -------------------------------------------------

TRANSCRIPT = b"[00:01:44] Priya: Launch moves to November 17th.\n[00:02:01] Dana: I'll update the press release by Wednesday.\n[00:03:05] Marcus: Next topic: pricing.\n"  # noqa: E501


def _service(session_factory, llm):
    return IngestionService(session_factory=session_factory, embedder=FakeEmbedder(), extractor=Extractor(llm))


def test_ingestion_persists_extraction_with_source_turn(session_factory):
    result = _service(session_factory, FakeLLM(GOOD_RESPONSE)).ingest("planning.txt", TRANSCRIPT)

    assert result["extraction_status"] == "completed"
    with session_factory() as session:
        meeting = get_meeting(session, result["meeting_id"])
    assert meeting["extraction_status"] == "completed"
    assert meeting["decisions"] == [
        {"text": "Launch moves to November 17th", "turn_idx": 0, "speaker": "Priya", "start": 104.0}
    ]
    assert meeting["action_items"][0] == {
        "owner": "Dana",
        "task": "Update the press release",
        "due": "by Wednesday",
        "turn_idx": 1,
        "speaker": "Dana",
        "start": 121.0,
    }
    assert [t["label"] for t in meeting["topics"]] == ["Launch date", "Pricing"]


def test_extraction_failure_keeps_meeting_searchable(session_factory):
    llm = FakeLLM(error=LLMError("Could not reach Ollama"))

    result = _service(session_factory, llm).ingest("planning.txt", TRANSCRIPT)

    assert result["extraction_status"] == "failed"
    with session_factory() as session:
        meeting = get_meeting(session, result["meeting_id"])
    assert meeting["chunk_count"] >= 1
    assert meeting["extraction_error"] == "Could not reach Ollama"
    assert meeting["decisions"] == []


def test_extraction_can_be_disabled(session_factory):
    service = IngestionService(session_factory=session_factory, embedder=FakeEmbedder())
    assert service.extractor is None  # EXTRACTION_ENABLED=false in tests

    result = service.ingest("planning.txt", TRANSCRIPT)

    assert result["extraction_status"] == "skipped"


@pytest.mark.parametrize("bad", [{"decisions": "nope"}, {}])
def test_missing_or_malformed_sections_yield_empty_lists(bad):
    result = Extractor(FakeLLM(bad)).extract(MEETING)

    assert (result.decisions, result.action_items, result.topics) == ([], [], [])
