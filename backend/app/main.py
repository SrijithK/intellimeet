from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.services import meeting_store
from app.services.ingestion import ingestion_service
from app.services.job_queue import InProcessJobQueue
from app.services.retrieval import Retriever, SearchFilters
from app.validation import validate_upload

job_queue = InProcessJobQueue(ingestion_service.process_job)
retriever = Retriever(ingestion_service.session_factory)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await job_queue.drain()


app = FastAPI(title="IntelliMeet API", lifespan=lifespan)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/meetings")
async def upload_meeting(file: UploadFile = File(...)) -> dict[str, object]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A transcript file is required.")

    file_name = file.filename
    content = await file.read()
    try:
        validate_upload(file_name, content)
    except ValueError as exc:
        message = str(exc)
        status_code = 413 if "too large" in message.lower() else 400
        if "unsupported file type" in message.lower():
            status_code = 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    try:
        job = ingestion_service.create_job(file_name, content)
    except ValueError as exc:
        message = str(exc)
        if "already exists" in message.lower():
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc

    if job["status"] == "queued":  # an identical re-upload returns the existing job as-is
        await job_queue.submit(job["job_id"], file_name, content)

    return {"job_id": job["job_id"], "status": job["status"]}


@app.get("/api/meetings/{meeting_id}")
async def get_meeting(meeting_id: str) -> dict[str, object]:
    with ingestion_service.session_factory() as session:
        meeting = meeting_store.get_meeting(session, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    return meeting


@app.get("/api/search")
def search(
    q: str = Query(..., min_length=1, description="Natural-language query"),
    meeting_id: Optional[list[str]] = Query(None, description="Restrict to these meetings (repeatable)"),
    speaker: Optional[str] = Query(None, description="Only chunks in which this speaker talks"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    k: int = Query(8, ge=1, le=50),
) -> dict[str, object]:
    # Sync endpoint: embedding and DB calls block, so FastAPI runs this in its threadpool.
    filters = SearchFilters(meeting_ids=meeting_id, speaker=speaker, date_from=date_from, date_to=date_to)
    results = retriever.retrieve(q, filters, k=k)
    return {"query": q, "results": [asdict(chunk) for chunk in results]}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    try:
        return ingestion_service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found") from exc
