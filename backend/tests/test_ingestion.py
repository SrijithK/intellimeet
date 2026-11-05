import pytest
from sqlalchemy import func, select

from app.db_models import ChunkRecord, MeetingRecord, TurnRecord
from app.services.ingestion import IngestionService
from tests.fakes import FakeEmbedder

TRANSCRIPT = (
    b"[00:00:05] Alice: We decided to move the launch to March.\n"
    b"[00:00:40] Bob: I will update the rollout checklist by Friday.\n"
    b"[00:01:50] Carol: Next topic is hiring.\n"
)


@pytest.fixture
def service(session_factory):
    return IngestionService(session_factory=session_factory, embedder=FakeEmbedder())


def test_ingest_persists_meeting_turns_and_embedded_chunks(service, session_factory):
    result = service.ingest("planning.txt", TRANSCRIPT)

    assert result["deduplicated"] is False
    assert result["turn_count"] == 3
    with session_factory() as session:
        meeting = session.get(MeetingRecord, result["meeting_id"])
        turns = session.execute(select(TurnRecord).order_by(TurnRecord.idx)).scalars().all()
        chunks = session.execute(select(ChunkRecord).order_by(ChunkRecord.id)).scalars().all()

    assert (meeting.title, meeting.source_type) == ("planning", "txt")
    assert [t.speaker for t in turns] == ["Alice", "Bob", "Carol"]
    assert turns[2].start_ts == 110
    # Carol speaks >90s after Alice, so she starts a second (overlapping) chunk.
    assert [(c.first_turn_idx, c.last_turn_idx) for c in chunks] == [(0, 1), (1, 2)]
    assert chunks[1].speakers == ["Bob", "Carol"]
    assert len(chunks[0].embedding) == FakeEmbedder.dim
    assert result["chunk_count"] == len(chunks)


def test_reingesting_same_content_reuses_meeting(service, session_factory):
    first = service.ingest("planning.txt", TRANSCRIPT)
    second = service.ingest("planning-copy.txt", TRANSCRIPT)

    assert second == {"content_hash": first["content_hash"], "meeting_id": first["meeting_id"], "deduplicated": True}
    with session_factory() as session:
        assert session.execute(select(func.count()).select_from(MeetingRecord)).scalar() == 1


def test_file_without_turns_is_rejected_and_nothing_is_saved(service, session_factory):
    with pytest.raises(ValueError, match="No transcript turns"):
        service.ingest("empty.txt", b"just some notes without timestamps\n")

    with session_factory() as session:
        assert session.execute(select(func.count()).select_from(MeetingRecord)).scalar() == 0


def test_vtt_source_type_is_recorded(service, session_factory):
    vtt = b"WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nAlice: Hello there.\n"

    result = service.ingest("standup.vtt", vtt)

    with session_factory() as session:
        assert session.get(MeetingRecord, result["meeting_id"]).source_type == "vtt"
