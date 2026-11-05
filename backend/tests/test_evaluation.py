"""The golden-set scorer must be trustworthy, and retrieval must keep finding the expected lines."""

import pytest

from app.services.answering import DEFAULT_TOP_K
from app.services.embedder import FastEmbedEmbedder
from app.services.ingestion import IngestionService
from app.services.retrieval import Retriever, SearchFilters
from evaluation.scoring import (
    TRANSCRIPTS_DIR,
    CaseResult,
    GoldenCase,
    first_relevant_rank,
    load_golden_set,
    missing_facts,
    summarize,
)

# Retrieval quality gate for CI (no LLM needed). Current score: 1.0; leave a little headroom.
MIN_RETRIEVAL_HIT_RATE = 0.9

CASE = GoldenCase(
    id="c", category="fact", question="q", expected_turns=[("planning", 7)], must_include=["17", ["Dana", "Daniela"]]
)


def test_facts_are_checked_without_citation_timestamps():
    # "17" only appears inside the citation's timestamp: must not count.
    assert missing_facts("Dana moved it [planning, 00:01:17, Priya].", CASE.must_include) == ["17"]
    assert missing_facts("Dana moved it to the 17th [planning, 00:01:44, Priya].", CASE.must_include) == []
    assert missing_facts("daniela: november 17", CASE.must_include) == []  # alternatives, case-insensitive


def test_first_relevant_rank_uses_chunk_turn_ranges():
    ranges = [("planning", 0, 3), ("standup", 5, 9), ("planning", 6, 8)]

    assert first_relevant_rank(ranges, [("planning", 7)]) == 3
    assert first_relevant_rank(ranges, [("planning", 4)]) is None


@pytest.mark.parametrize(
    "result, passed",
    [
        (CaseResult(CASE, found=True, cites_expected=True, missing=[]), True),
        (CaseResult(CASE, found=True, cites_expected=False, missing=[]), False),  # right words, wrong source
        (CaseResult(CASE, found=True, cites_expected=True, missing=["17"]), False),  # wrong facts
        (CaseResult(CASE, found=False), False),  # refused an answerable question
        (CaseResult(GoldenCase("u", "unanswerable", "q", answerable=False), found=True), False),
        (CaseResult(GoldenCase("u", "unanswerable", "q", answerable=False), found=False), True),
        (CaseResult(CASE, error="Ollama down"), False),
    ],
)
def test_pass_requires_found_correct_citation_and_facts(result, passed):
    assert result.passed is passed


def test_summary_rates():
    results = [
        CaseResult(CASE, retrieval_rank=1, found=True, cites_expected=True),
        CaseResult(CASE, retrieval_rank=2, found=False),
        CaseResult(GoldenCase("u", "unanswerable", "q", answerable=False), found=False),
    ]

    summary = summarize(results, k=6)

    assert summary["retrieval_hit_at_6"] == 1.0
    assert summary["retrieval_mrr"] == 0.75
    assert summary["answer_pass_rate"] == 0.5
    assert summary["false_not_found"] == 0.5
    assert summary["correct_not_found"] == 1.0


def test_golden_set_references_real_turns():
    from app.parsers import parse_transcript

    turn_counts = {
        path.stem: len(parse_transcript(path.name, path.read_text()).turns) for path in TRANSCRIPTS_DIR.iterdir()
    }
    for case in load_golden_set():
        assert case.answerable == bool(case.expected_turns), case.id
        for title, idx in case.expected_turns:
            assert idx < turn_counts[title], f"{case.id}: {title} has no turn {idx}"
        if case.meeting:
            assert case.meeting in turn_counts, case.id


def test_golden_set_retrieval_quality(session_factory):
    """Retrieval-only slice of the golden set: runs in CI without an LLM."""
    embedder = FastEmbedEmbedder()
    service = IngestionService(session_factory=session_factory, embedder=embedder)  # extraction disabled
    meeting_ids = {}
    for path in sorted(TRANSCRIPTS_DIR.iterdir()):
        meeting_ids[path.stem] = service.ingest(path.name, path.read_bytes())["meeting_id"]
    retriever = Retriever(session_factory, embedder)

    misses = []
    cases = [case for case in load_golden_set() if case.answerable]
    for case in cases:
        filters = SearchFilters(meeting_ids=[meeting_ids[case.meeting]] if case.meeting else None)
        chunks = retriever.retrieve(case.question, filters, k=DEFAULT_TOP_K)
        ranges = [(c.meeting_title, c.first_turn_idx, c.last_turn_idx) for c in chunks]
        if first_relevant_rank(ranges, case.expected_turns) is None:
            misses.append(case.id)

    hit_rate = 1 - len(misses) / len(cases)
    assert hit_rate >= MIN_RETRIEVAL_HIT_RATE, f"hit@{DEFAULT_TOP_K} = {hit_rate:.2f}; missed: {misses}"
