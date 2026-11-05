from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.db_models import (
    ActionItemRecord,
    ChunkRecord,
    DecisionRecord,
    MeetingRecord,
    TopicRecord,
    TurnRecord,
)
from app.models import Meeting, TranscriptChunk
from app.services.extraction import Extraction


def find_meeting_id_by_hash(session: Session, content_hash: str) -> Optional[str]:
    return session.execute(
        select(MeetingRecord.id).where(MeetingRecord.content_hash == content_hash)
    ).scalar_one_or_none()


def save_meeting(
    session: Session,
    meeting: Meeting,
    content_hash: str,
    chunks: Sequence[TranscriptChunk],
    embeddings: Sequence[Sequence[float]],
) -> str:
    """Add a meeting with its turns and embedded chunks to the session (caller commits)."""
    if len(chunks) != len(embeddings):
        raise ValueError("Each chunk needs exactly one embedding.")

    meeting_id = str(uuid4())
    session.add(
        MeetingRecord(
            id=meeting_id,
            title=meeting.title,
            source_name=meeting.source_name,
            source_type=meeting.source_type,
            content_hash=content_hash,
        )
    )
    session.flush()  # meetings row must exist before the FK-bearing rows
    session.add_all(
        TurnRecord(
            meeting_id=meeting_id,
            idx=idx,
            speaker=turn.speaker,
            text=turn.text,
            start_ts=turn.start,
            end_ts=turn.end,
        )
        for idx, turn in enumerate(meeting.turns)
    )
    session.add_all(
        ChunkRecord(
            meeting_id=meeting_id,
            first_turn_idx=chunk.first_turn_idx,
            last_turn_idx=chunk.last_turn_idx,
            speakers=chunk.speakers,
            text=chunk.text,
            start_ts=chunk.start,
            end_ts=chunk.end,
            embedding=list(embedding),
        )
        for chunk, embedding in zip(chunks, embeddings)
    )
    return meeting_id


def save_extraction(session: Session, meeting_id: str, extraction: Extraction) -> None:
    """Replace the meeting's extracted records and mark extraction completed (caller commits)."""
    for model in (DecisionRecord, ActionItemRecord, TopicRecord):
        session.execute(delete(model).where(model.meeting_id == meeting_id))
    session.add_all(
        DecisionRecord(meeting_id=meeting_id, turn_idx=d.turn_idx, text=d.text) for d in extraction.decisions
    )
    session.add_all(
        ActionItemRecord(meeting_id=meeting_id, turn_idx=a.turn_idx, owner=a.owner, task=a.task, due=a.due)
        for a in extraction.action_items
    )
    session.add_all(TopicRecord(meeting_id=meeting_id, turn_idx=t.turn_idx, label=t.label) for t in extraction.topics)
    set_extraction_status(session, meeting_id, "completed")


def set_extraction_status(session: Session, meeting_id: str, status: str, error: Optional[str] = None) -> None:
    session.execute(
        update(MeetingRecord)
        .where(MeetingRecord.id == meeting_id)
        .values(extraction_status=status, extraction_error=error)
    )


def _with_source_turn(session: Session, model, meeting_id: str, fields: Sequence[str]) -> list[dict[str, Any]]:
    """Extracted records plus the speaker/timestamp of the turn each one cites."""
    rows = session.execute(
        select(model, TurnRecord.speaker, TurnRecord.start_ts)
        .join(TurnRecord, (TurnRecord.meeting_id == model.meeting_id) & (TurnRecord.idx == model.turn_idx))
        .where(model.meeting_id == meeting_id)
        .order_by(model.turn_idx, model.id)
    ).all()
    return [
        {
            **{name: getattr(record, name) for name in fields},
            "turn_idx": record.turn_idx,
            "speaker": speaker,
            "start": start,
        }
        for record, speaker, start in rows
    ]


def _summary(record: MeetingRecord, turn_count: int) -> dict[str, Any]:
    return {
        "id": record.id,
        "title": record.title,
        "source_name": record.source_name,
        "source_type": record.source_type,
        "created_at": record.created_at,
        "extraction_status": record.extraction_status,
        "turn_count": turn_count,
    }


def list_meetings(session: Session) -> list[dict[str, Any]]:
    """All meetings, newest first, with their turn counts."""
    turn_count = (
        select(func.count()).select_from(TurnRecord).where(TurnRecord.meeting_id == MeetingRecord.id).scalar_subquery()
    )
    rows = session.execute(
        select(MeetingRecord, turn_count).order_by(MeetingRecord.created_at.desc(), MeetingRecord.id)
    ).all()
    return [_summary(record, count) for record, count in rows]


def get_meeting(session: Session, meeting_id: str) -> Optional[dict[str, Any]]:
    record = session.get(MeetingRecord, meeting_id)
    if record is None:
        return None
    turns = session.execute(
        select(TurnRecord).where(TurnRecord.meeting_id == meeting_id).order_by(TurnRecord.idx)
    ).scalars()
    chunk_count = session.execute(
        select(func.count()).select_from(ChunkRecord).where(ChunkRecord.meeting_id == meeting_id)
    ).scalar_one()
    turn_list: list[dict[str, Any]] = [
        {"idx": t.idx, "speaker": t.speaker, "text": t.text, "start": t.start_ts, "end": t.end_ts} for t in turns
    ]
    return {
        **_summary(record, len(turn_list)),
        "media_uri": record.media_uri,
        "chunk_count": chunk_count,
        "extraction_error": record.extraction_error,
        "decisions": _with_source_turn(session, DecisionRecord, meeting_id, ["text"]),
        "action_items": _with_source_turn(session, ActionItemRecord, meeting_id, ["owner", "task", "due"]),
        "topics": _with_source_turn(session, TopicRecord, meeting_id, ["label"]),
        "turns": turn_list,
    }
