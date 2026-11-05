from __future__ import annotations

import hashlib
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import build_session_factory
from app.db_models import JobRecord


class JobStore:
    """Persists ingestion job status. Schema is owned by Alembic migrations."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self.session_factory = session_factory or build_session_factory()

    def create_job(self, file_name: str, content: bytes) -> dict[str, object]:
        content_hash = hashlib.sha256(content).hexdigest()

        with self.session_factory() as session:
            existing = session.execute(select(JobRecord).where(JobRecord.file_name == file_name)).scalar_one_or_none()
            if existing is not None:
                if existing.meeting is not None and existing.meeting.get("content_hash") == content_hash:
                    return {
                        "job_id": existing.id,
                        "status": existing.status,
                        "file_name": existing.file_name,
                        "meeting": existing.meeting,
                        "error": existing.error,
                    }
                raise ValueError(f"A file named '{file_name}' already exists with different content.")

            job_id = str(uuid4())
            job = JobRecord(
                id=job_id,
                file_name=file_name,
                status="queued",
                meeting={"content_hash": content_hash},
                error=None,
            )
            session.add(job)
            session.commit()
            return {
                "job_id": job.id,
                "status": job.status,
                "file_name": job.file_name,
                "meeting": job.meeting,
                "error": job.error,
            }

    def get_job(self, job_id: str) -> dict[str, object]:
        with self.session_factory() as session:
            job = session.get(JobRecord, job_id)
            if job is None:
                raise KeyError(job_id)
            return {
                "job_id": job.id,
                "status": job.status,
                "file_name": job.file_name,
                "meeting": job.meeting,
                "error": job.error,
            }

    def update_status(
        self,
        job_id: str,
        status: str,
        meeting: Optional[dict[str, object]] = None,
        error: Optional[str] = None,
    ) -> dict[str, object]:
        with self.session_factory() as session:
            job = session.get(JobRecord, job_id)
            if job is None:
                raise KeyError(job_id)
            job.status = status
            if meeting is not None:
                job.meeting = meeting
            if error is not None:
                job.error = error
            session.commit()
            return self.get_job(job_id)
