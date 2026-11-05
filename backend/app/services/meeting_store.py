from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db_models import ChunkRecord, MeetingRecord, TurnRecord
from app.models import Meeting, TranscriptChunk


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
        "id": record.id,
        "title": record.title,
        "source_name": record.source_name,
        "source_type": record.source_type,
        "media_uri": record.media_uri,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "chunk_count": chunk_count,
        "turns": turn_list,
    }
