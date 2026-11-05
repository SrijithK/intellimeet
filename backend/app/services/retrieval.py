from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import Text, cast, exists, func, select
from sqlalchemy.orm import sessionmaker

from app.db_models import ChunkRecord, MeetingRecord
from app.services.embedder import Embedder, get_embedder

DEFAULT_CANDIDATES = 20  # per retriever, before fusion
RRF_K = 60  # standard Reciprocal Rank Fusion constant


@dataclass
class SearchFilters:
    meeting_ids: Optional[list[str]] = None
    speaker: Optional[str] = None  # case-insensitive; matches chunks in which the speaker talks
    date_from: Optional[datetime] = None  # on meeting date, falling back to upload time
    date_to: Optional[datetime] = None


@dataclass
class RetrievedChunk:
    chunk_id: int
    meeting_id: str
    meeting_title: str
    speakers: list[str]
    text: str
    start: float
    end: Optional[float]
    first_turn_idx: int
    last_turn_idx: int
    score: float  # fused RRF score
    vector_rank: Optional[int] = None  # 1-based; None if outside that retriever's candidates
    text_rank: Optional[int] = None
    similarity: Optional[float] = None  # cosine similarity to the query (for relevance thresholds)


def reciprocal_rank_fusion(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> dict[int, float]:
    """Fuse ranked id lists: score(id) = sum over lists of 1 / (k + rank)."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return scores


def or_tsquery(query: str):
    """Full-text query with OR semantics.

    plainto_tsquery ANDs every word, so a natural-language question rarely matches any
    one chunk. We take its normalised lexemes (stemmed, stopwords removed) and OR them;
    ts_rank_cd then favours chunks matching more of them.
    """
    lexemes = cast(func.plainto_tsquery("english", query), Text)
    return func.to_tsquery("english", func.replace(lexemes, " & ", " | "))


class Retriever:
    """Hybrid retrieval: pgvector cosine search + Postgres full-text, fused with RRF."""

    def __init__(
        self,
        session_factory: sessionmaker,
        embedder: Optional[Embedder] = None,
        candidates: int = DEFAULT_CANDIDATES,
        rrf_k: int = RRF_K,
    ) -> None:
        self.session_factory = session_factory
        self._embedder = embedder
        self.candidates = candidates
        self.rrf_k = rrf_k

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    @embedder.setter
    def embedder(self, value: Embedder) -> None:
        self._embedder = value

    def retrieve(self, query: str, filters: Optional[SearchFilters] = None, k: int = 8) -> list[RetrievedChunk]:
        query = query.strip()
        if not query:
            return []
        filters = filters or SearchFilters()
        query_vector = self.embedder.embed_query(query)
        distance = ChunkRecord.embedding.cosine_distance(query_vector)

        with self.session_factory() as session:
            vector_ids = list(
                session.execute(
                    self._filtered(select(ChunkRecord.id), filters).order_by(distance).limit(self.candidates)
                ).scalars()
            )

            tsquery = or_tsquery(query)
            text_ids = list(
                session.execute(
                    self._filtered(select(ChunkRecord.id), filters)
                    .where(ChunkRecord.tsv.op("@@")(tsquery))
                    .order_by(func.ts_rank_cd(ChunkRecord.tsv, tsquery).desc(), ChunkRecord.id)
                    .limit(self.candidates)
                ).scalars()
            )

            scores = reciprocal_rank_fusion([vector_ids, text_ids], k=self.rrf_k)
            top_ids = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))[:k]
            if not top_ids:
                return []

            rows = session.execute(
                select(ChunkRecord, MeetingRecord.title, (1 - distance).label("similarity"))
                .join(MeetingRecord, MeetingRecord.id == ChunkRecord.meeting_id)
                .where(ChunkRecord.id.in_(top_ids))
            ).all()

        vector_rank = {chunk_id: rank for rank, chunk_id in enumerate(vector_ids, start=1)}
        text_rank = {chunk_id: rank for rank, chunk_id in enumerate(text_ids, start=1)}
        by_id = {
            chunk.id: RetrievedChunk(
                chunk_id=chunk.id,
                meeting_id=chunk.meeting_id,
                meeting_title=title,
                speakers=list(chunk.speakers),
                text=chunk.text,
                start=chunk.start_ts,
                end=chunk.end_ts,
                first_turn_idx=chunk.first_turn_idx,
                last_turn_idx=chunk.last_turn_idx,
                score=scores[chunk.id],
                vector_rank=vector_rank.get(chunk.id),
                text_rank=text_rank.get(chunk.id),
                similarity=float(similarity),
            )
            for chunk, title, similarity in rows
        }
        return [by_id[chunk_id] for chunk_id in top_ids]

    @staticmethod
    def _filtered(statement, filters: SearchFilters):
        if filters.meeting_ids:
            statement = statement.where(ChunkRecord.meeting_id.in_(filters.meeting_ids))
        if filters.speaker:
            speaker = func.unnest(ChunkRecord.speakers).table_valued("value").render_derived(name="speaker")
            statement = statement.where(
                exists(
                    select(1).select_from(speaker).where(func.lower(speaker.c.value) == filters.speaker.strip().lower())
                )
            )
        if filters.date_from or filters.date_to:
            meeting_when = (
                select(func.coalesce(MeetingRecord.meeting_date, MeetingRecord.created_at))
                .where(MeetingRecord.id == ChunkRecord.meeting_id)
                .scalar_subquery()
            )
            if filters.date_from:
                statement = statement.where(meeting_when >= filters.date_from)
            if filters.date_to:
                statement = statement.where(meeting_when <= filters.date_to)
        return statement
