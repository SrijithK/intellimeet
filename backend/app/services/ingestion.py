from __future__ import annotations

from typing import Any, Optional

from app.models import Meeting
from app.parsers import parse_txt_transcript, parse_vtt_transcript
from app.services.job_store import JobStore

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


class IngestionService:
    def __init__(self, job_store: Optional[JobStore] = None) -> None:
        self.job_store = job_store or JobStore()

    def create_job(self, file_name: str, content: bytes) -> dict[str, Any]:
        if len(content) == 0:
            raise ValueError("Uploaded file is empty.")
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise ValueError(f"File is too large. Maximum allowed size is {MAX_UPLOAD_SIZE_BYTES} bytes.")
        return self.job_store.create_job(file_name, content)

    async def process_job(self, job_id: str, file_name: str, content: bytes) -> None:
        try:
            self.job_store.update_status(job_id, "processing")
            meeting = self._parse_meeting(file_name, content)
            serialized = self._serialize_meeting(meeting)
            self.job_store.update_status(job_id, "completed", meeting=serialized)
        except Exception as exc:  # pragma: no cover - guarded by API validation path
            self.job_store.update_status(job_id, "failed", error=str(exc))

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self.job_store.get_job(job_id)

    @staticmethod
    def _parse_meeting(file_name: str, content: bytes) -> Meeting:
        text = content.decode("utf-8")
        extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        if extension == "txt":
            return parse_txt_transcript(file_name, text)
        if extension == "vtt":
            return parse_vtt_transcript(file_name, text)
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")

    @staticmethod
    def _serialize_meeting(meeting: Meeting) -> dict[str, Any]:
        return {
            "title": meeting.title,
            "source_name": meeting.source_name,
            "turns": [
                {
                    "speaker": turn.speaker,
                    "text": turn.text,
                    "start": turn.start,
                    "end": turn.end,
                }
                for turn in meeting.turns
            ],
        }


ingestion_service = IngestionService()
