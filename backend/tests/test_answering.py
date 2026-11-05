import pytest

from app.services.answering import NOT_FOUND, Answerer, CitationRewriter, Source
from app.services.extraction import Extractor
from app.services.ingestion import IngestionService
from app.services.retrieval import Retriever, SearchFilters
from tests.fakes import FakeEmbedder, FakeLLM

SOURCES = {
    1: Source(1, "m1", "planning", 0, "Priya", 104, "Launch moves."),
    2: Source(2, "m1", "planning", 1, "Dana", 121, "Press release."),
}


def _rewrite(pieces):
    rewriter = CitationRewriter(SOURCES)
    return "".join(rewriter.feed(p) for p in pieces) + rewriter.flush(), rewriter.cited


def test_rewriter_handles_references_split_across_tokens():
    text, cited = _rewrite(["Launch moved ", "[", "1", "]", " and PR [2", "]."])

    assert text == "Launch moved [planning, 00:01:44, Priya] and PR [planning, 00:02:01, Dana]."
    assert cited == [1, 2]


def test_rewriter_expands_lists_and_drops_unknown_references():
    text, cited = _rewrite(["Both [2, 1]. Invented [99]. Mixed [1,99]."])

    assert text == (
        "Both [planning, 00:02:01, Dana][planning, 00:01:44, Priya]. Invented . Mixed [planning, 00:01:44, Priya]."
    )
    assert cited == [2, 1]


def test_rewriter_leaves_other_brackets_alone():
    text, cited = _rewrite(["Use [draft] or [a very long bracketed aside without a close", " ... done"])

    assert text == "Use [draft] or [a very long bracketed aside without a close ... done"
    assert cited == []


# --- answer flow -------------------------------------------------------------

PLANNING = b"[00:01:44] Priya: The launch moves to November 17th.\n[00:02:01] Dana: I'll update the press release by Wednesday.\n"  # noqa: E501
STANDUP = b"[00:00:10] Aisha: I upgraded Postgres on staging.\n[00:03:45] Aisha: I'll have the pager alert in place by Thursday.\n"  # noqa: E501


def _extraction(user):
    if "Priya" in user:
        return {
            "decisions": [{"turn": 0, "decision": "Launch moves to November 17th"}],
            "action_items": [{"turn": 1, "owner": "Dana", "task": "update the press release", "due": "by Wednesday"}],
            "topics": [],
        }
    return {
        "decisions": [],
        "action_items": [{"turn": 1, "owner": "Aisha", "task": "set up the pager alert", "due": "by Thursday"}],
        "topics": [],
    }


@pytest.fixture
def meetings(session_factory):
    service = IngestionService(
        session_factory=session_factory, embedder=FakeEmbedder(), extractor=Extractor(FakeLLM(_extraction))
    )
    return {
        "planning": service.ingest("planning.txt", PLANNING)["meeting_id"],
        "standup": service.ingest("standup.txt", STANDUP)["meeting_id"],
    }


def _answerer(session_factory, llm, **kwargs):
    return Answerer(session_factory, Retriever(session_factory, FakeEmbedder()), llm, **kwargs)


def _run(answerer, question, filters=None):
    events = list(answerer.answer(question, filters))
    tokens = "".join(e.data["text"] for e in events if e.type == "token")
    return events, tokens, events[-1].data


def test_answer_streams_grounded_answer_with_citations(session_factory, meetings):
    llm = FakeLLM(stream=["The launch moves to November 17th ", "[", "1", "]."])
    answerer = _answerer(session_factory, llm)

    events, tokens, done = _run(answerer, "When is the launch?", SearchFilters(meeting_ids=[meetings["planning"]]))

    assert [e.type for e in events][0] == "citations" and events[-1].type == "done"
    assert tokens == "The launch moves to November 17th [planning, 00:01:44, Priya]."
    assert done["found"] is True
    assert [(c["speaker"], c["timestamp"], c["meeting_title"]) for c in done["cited"]] == [
        ("Priya", "00:01:44", "planning")
    ]
    assert done["prompt_tokens"] == 100 and done["retrieved_chunk_ids"]
    prompt = llm.calls[0]
    assert 'Meeting "planning":\n[1] 00:01:44 Priya: The launch moves to November 17th.' in prompt
    assert "- Decision: Launch moves to November 17th [1]" in prompt
    assert "- Action item: Dana will update the press release (due: by Wednesday) [2]" in prompt
    assert prompt.endswith("Question: When is the launch?")


def test_irrelevant_question_skips_the_llm(session_factory, meetings):
    llm = FakeLLM()
    answerer = _answerer(session_factory, llm, min_similarity=1.01)  # nothing is similar enough

    events, tokens, done = _run(answerer, "What's the weather in Paris?")

    assert llm.calls == []
    assert tokens == NOT_FOUND
    assert events[0].data == {"sources": []}
    assert done["found"] is False


def test_model_saying_not_found_is_reported_as_not_found(session_factory, meetings):
    answerer = _answerer(session_factory, FakeLLM(stream=[NOT_FOUND]))

    _, tokens, done = _run(answerer, "What did we decide about hiring?")

    assert tokens == NOT_FOUND
    assert done["found"] is False


def test_answer_without_valid_citations_is_not_marked_found(session_factory, meetings):
    answerer = _answerer(session_factory, FakeLLM(stream=["Something made up [42]."]))

    _, tokens, done = _run(answerer, "When is the launch?")

    assert tokens == "Something made up ."
    assert done["found"] is False


def test_named_owner_brings_in_their_action_items_from_any_meeting(session_factory, meetings):
    llm = FakeLLM(stream=["Pager alert [1]."])
    answerer = _answerer(session_factory, llm, min_similarity=1.01)

    _, _, done = _run(answerer, "What does aisha still need to do?")

    assert done["found"] is True
    assert "Action item: Aisha will set up the pager alert (due: by Thursday)" in llm.calls[0]


def test_meeting_filter_excludes_other_meetings_owner_items(session_factory, meetings):
    llm = FakeLLM(stream=["ok"])
    answerer = _answerer(session_factory, llm)

    _run(answerer, "What does Aisha need to do?", SearchFilters(meeting_ids=[meetings["planning"]]))

    assert "Action item: Aisha" not in llm.calls[0]
