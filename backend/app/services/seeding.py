from __future__ import annotations

import logging
from pathlib import Path

from app.parsers import file_extension, supported_extensions
from app.services.ingestion import IngestionService
from app.services.job_queue import JobQueue
from app.validation import validate_upload

logger = logging.getLogger(__name__)


async def seed_transcripts(directory: Path, service: IngestionService, queue: JobQueue) -> list[str]:
    """Queue every supported transcript in ``directory`` for ingestion; return the queued job ids.

    Safe on every startup: a file already ingested (same name and content) returns its existing
    job, which is not re-queued once completed or failed. A job still queued/processing at startup
    was interrupted by a restart (nothing is running yet), so it is queued again.
    Bad files are logged and skipped so they never block startup.
    """
    if not directory.is_dir():
        logger.warning("Seed directory %s does not exist; skipping", directory)
        return []

    queued = []
    for path in sorted(directory.iterdir()):
        if not path.is_file() or file_extension(path.name) not in supported_extensions():
            continue
        try:
            content = path.read_bytes()
            validate_upload(path.name, content)
            job = service.create_job(path.name, content)
        except ValueError as exc:
            logger.warning("Skipping seed file %s: %s", path.name, exc)
            continue
        if job["status"] in ("queued", "processing"):
            await queue.submit(job["job_id"], path.name, content)
            queued.append(job["job_id"])
    logger.info("Seeded %d transcript(s) from %s", len(queued), directory)
    return queued
