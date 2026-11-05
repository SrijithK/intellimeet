from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR

from app.db import Base

EMBEDDING_DIM = 384  # BAAI/bge-small-en-v1.5


class JobRecord(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    file_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="queued")
    meeting = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class MeetingRecord(Base):
    __tablename__ = "meetings"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    source_name = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # "txt", "vtt"; "audio" later
    media_uri = Column(String, nullable=True)  # for future voice ingestion
    meeting_date = Column(DateTime(timezone=True), nullable=True)
    content_hash = Column(String, nullable=False, unique=True)
    extraction_status = Column(String, nullable=False, server_default="pending")  # pending|completed|failed|skipped
    extraction_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TurnRecord(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("meeting_id", "idx"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    idx = Column(Integer, nullable=False)  # position of the turn within the meeting
    speaker = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    start_ts = Column(Float, nullable=False)  # seconds from meeting start
    end_ts = Column(Float, nullable=True)


class ChunkRecord(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    first_turn_idx = Column(Integer, nullable=False)
    last_turn_idx = Column(Integer, nullable=False)
    speakers = Column(ARRAY(String), nullable=False)
    text = Column(Text, nullable=False)
    start_ts = Column(Float, nullable=False)
    end_ts = Column(Float, nullable=True)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    tsv = Column(TSVECTOR, Computed("to_tsvector('english', text)", persisted=True))


def _source_turn_fk() -> ForeignKeyConstraint:
    """Every extracted record points at the turn it came from (for citations)."""
    return ForeignKeyConstraint(["meeting_id", "turn_idx"], ["turns.meeting_id", "turns.idx"], ondelete="CASCADE")


class DecisionRecord(Base):
    __tablename__ = "decisions"
    __table_args__ = (_source_turn_fk(),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, nullable=False, index=True)
    turn_idx = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)


class ActionItemRecord(Base):
    __tablename__ = "action_items"
    __table_args__ = (_source_turn_fk(),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, nullable=False, index=True)
    turn_idx = Column(Integer, nullable=False)
    owner = Column(String, nullable=False)
    task = Column(Text, nullable=False)
    due = Column(String, nullable=True)  # as spoken, e.g. "by Friday"; not resolved to a date


class TopicRecord(Base):
    __tablename__ = "topics"
    __table_args__ = (_source_turn_fk(),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(String, nullable=False, index=True)
    turn_idx = Column(Integer, nullable=False)
    label = Column(String, nullable=False)


class QueryRecord(Base):
    """One row per chat request: what was asked, what was retrieved, what came back, and the cost."""

    __tablename__ = "queries"
    __table_args__ = (Index("ix_queries_created_at", "created_at"),)

    id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    question = Column(Text, nullable=False)
    filters = Column(JSON, nullable=False)
    retrieved_chunk_ids = Column(JSON, nullable=False)
    cited = Column(JSON, nullable=False)  # [{meeting_id, turn_idx, speaker, start}]
    answer = Column(Text, nullable=True)
    found = Column(Boolean, nullable=True)
    model = Column(String, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
