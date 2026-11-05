from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import build_session_factory
from app.llm import get_llm
from app.models import Meeting
from app.parsers import parse_transcript
from app.services.chunking import chunk_meeting
from app.services.embedder import Embedder, get_embedder
from app.services.extraction import Extractor
from app.services.job_store import JobStore
from app.services.meeting_store import (
    find_meeting_id_by_hash,
    save_extraction,
    save_meeting,
    set_extraction_status,
)

logger = logging.getLogger(__name__)


class IngestionService:
    """Runs the ingestion pipeline: parse -> chunk -> embed -> persist -> extract."""

    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        session_factory: Optional[sessionmaker] = None,
        embedder: Optional[Embedder] = None,
        extractor: Optional[Extractor] = None,
    ) -> None:
        self.session_factory = session_factory or build_session_factory()
        self.job_store = job_store or JobStore(self.session_factory)
        self._embedder = embedder
        # None + EXTRACTION_ENABLED -> built from the configured LLM on first use.
        self._extractor = extractor
        self.extraction_enabled = extractor is not None or settings.extraction_enabled

    @property
    def extractor(self) -> Optional[Extractor]:
        if self._extractor is None and self.extraction_enabled:
            self._extractor = Extractor(get_llm())
        return self._extractor

    @extractor.setter
    def extractor(self, value: Optional[Extractor]) -> None:
        self._extractor = value
        self.extraction_enabled = value is not None

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    @embedder.setter
    def embedder(self, value: Embedder) -> None:
        self._embedder = value

    def create_job(self, file_name: str, content: bytes) -> dict[str, Any]:
        return self.job_store.create_job(file_name, content)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.job_store.get_job(job_id)

    async def process_job(self, job_id: str, file_name: str, content: bytes) -> None:
        try:
            self.job_store.update_status(job_id, "processing")
            # Parsing and embedding are CPU-bound; keep them off the event loop.
            result = await asyncio.to_thread(self.ingest, file_name, content)
            self.job_store.update_status(job_id, "completed", meeting=result)
        except Exception as exc:
            logger.exception("Ingestion failed for job %s (%s)", job_id, file_name)
            self.job_store.update_status(job_id, "failed", error=str(exc))

    def ingest(self, file_name: str, content: bytes) -> dict[str, Any]:
        content_hash = hashlib.sha256(content).hexdigest()

        with self.session_factory() as session:
            existing_id = find_meeting_id_by_hash(session, content_hash)
        if existing_id is not None:
            return {"content_hash": content_hash, "meeting_id": existing_id, "deduplicated": True}

        meeting = parse_transcript(file_name, content.decode("utf-8-sig"))
        if not meeting.turns:
            raise ValueError("No transcript turns found. Check the file format.")

        chunks = chunk_meeting(meeting)
        embeddings = self.embedder.embed_documents([chunk.text for chunk in chunks])

        try:
            with self.session_factory.begin() as session:
                meeting_id = save_meeting(session, meeting, content_hash, chunks, embeddings)
        except IntegrityError:
            # Same content ingested concurrently under another name: reuse that meeting.
            with self.session_factory() as session:
                existing_id = find_meeting_id_by_hash(session, content_hash)
            if existing_id is None:
                raise
            return {"content_hash": content_hash, "meeting_id": existing_id, "deduplicated": True}

        # The meeting is searchable from here on; extraction failing must not undo that.
        extraction_status = self._extract(meeting_id, meeting)

        return {
            "content_hash": content_hash,
            "meeting_id": meeting_id,
            "title": meeting.title,
            "turn_count": len(meeting.turns),
            "chunk_count": len(chunks),
            "extraction_status": extraction_status,
            "deduplicated": False,
        }

    def _extract(self, meeting_id: str, meeting: Meeting) -> str:
        extractor = self.extractor
        if extractor is None:
            with self.session_factory.begin() as session:
                set_extraction_status(session, meeting_id, "skipped")
            return "skipped"
        try:
            extraction = extractor.extract(meeting)
            with self.session_factory.begin() as session:
                save_extraction(session, meeting_id, extraction)
            return "completed"
        except Exception as exc:
            logger.exception("Extraction failed for meeting %s (%s)", meeting_id, meeting.source_name)
            with self.session_factory.begin() as session:
                set_extraction_status(session, meeting_id, "failed", error=str(exc)[:1000])
            return "failed"


ingestion_service = IngestionService()
