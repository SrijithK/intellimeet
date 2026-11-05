from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import update

from app.db_models import MeetingRecord
from app.services.embedder import FastEmbedEmbedder
from app.services.ingestion import IngestionService
from app.services.retrieval import Retriever, SearchFilters, reciprocal_rank_fusion

SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "transcripts"


@pytest.fixture(scope="module")
def embedder():
    return FastEmbedEmbedder()  # real model: these tests check retrieval quality


@pytest.fixture
def meetings(session_factory, embedder):
    service = IngestionService(session_factory=session_factory, embedder=embedder)
    return {
        path.stem: service.ingest(path.name, path.read_bytes())["meeting_id"] for path in sorted(SEED_DIR.iterdir())
    }


@pytest.fixture
def retriever(session_factory, embedder):
    return Retriever(session_factory, embedder)


def test_rrf_rewards_items_ranked_by_both_retrievers():
    scores = reciprocal_rank_fusion([[1, 2, 3], [3, 4]], k=60)

    assert scores[3] == pytest.approx(1 / 63 + 1 / 61)
    assert max(scores, key=scores.get) == 3
    assert scores[1] > scores[2] == scores[4]  # same rank in different lists ties


def test_launch_question_finds_the_launch_decision(retriever, meetings):
    results = retriever.retrieve("When is the launch?", k=3)

    assert results[0].meeting_title == "product-launch-planning"
    assert any("November 17th" in chunk.text for chunk in results[:2])


def test_keyword_question_hits_both_retrievers(retriever, meetings):
    top = retriever.retrieve("What did we decide about CSV export?", k=3)[0]

    assert top.meeting_id == meetings["customer-feedback-review"]
    assert top.vector_rank == 1 and top.text_rank == 1


def test_paraphrase_without_shared_keywords_is_found_by_vector_search(retriever, meetings):
    top = retriever.retrieve("unreliable automated tests", k=3)[0]

    assert top.meeting_title == "engineering-standup"
    assert "flaky" in top.text or "sleep" in top.text


def test_results_carry_citation_metadata(retriever, meetings):
    chunk = retriever.retrieve("pager alert for webhook failures", k=1)[0]

    assert chunk.meeting_title == "engineering-standup"
    assert "Aisha" in chunk.speakers
    assert chunk.start <= 212 <= chunk.end  # Marcus proposes the alert at 00:03:32
    assert chunk.first_turn_idx <= chunk.last_turn_idx
    assert 0 < chunk.similarity <= 1


def test_speaker_filter_is_case_insensitive(retriever, meetings):
    results = retriever.retrieve("what is she working on", SearchFilters(speaker="aisha"), k=10)

    assert results
    assert all("Aisha" in chunk.speakers for chunk in results)


def test_meeting_filter(retriever, meetings):
    only = meetings["engineering-standup"]

    results = retriever.retrieve("launch date", SearchFilters(meeting_ids=[only]), k=10)

    assert results
    assert {chunk.meeting_id for chunk in results} == {only}


def test_date_filter_uses_meeting_date(retriever, meetings, session_factory):
    with session_factory.begin() as session:
        session.execute(update(MeetingRecord).values(meeting_date=datetime(2026, 9, 1, tzinfo=timezone.utc)))
        session.execute(
            update(MeetingRecord)
            .where(MeetingRecord.id == meetings["customer-feedback-review"])
            .values(meeting_date=datetime(2026, 10, 15, tzinfo=timezone.utc))
        )

    results = retriever.retrieve("launch", SearchFilters(date_from=datetime(2026, 10, 1, tzinfo=timezone.utc)), k=10)

    assert results
    assert {chunk.meeting_id for chunk in results} == {meetings["customer-feedback-review"]}


def test_k_limits_results_and_blank_query_returns_nothing(retriever, meetings):
    assert len(retriever.retrieve("payments", k=2)) == 2
    assert retriever.retrieve("   ") == []


def test_query_of_only_stopwords_still_uses_vector_search(retriever, meetings):
    results = retriever.retrieve("what is the", k=3)

    assert len(results) == 3
    assert all(chunk.text_rank is None for chunk in results)
