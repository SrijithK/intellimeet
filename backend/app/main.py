from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services import meeting_store
from app.services.answering import Answerer
from app.services.ingestion import ingestion_service
from app.services.job_queue import InProcessJobQueue
from app.services.query_log import record_query
from app.services.retrieval import Retriever, SearchFilters
from app.validation import validate_upload

job_queue = InProcessJobQueue(ingestion_service.process_job)
retriever = Retriever(ingestion_service.session_factory)
answerer = Answerer(ingestion_service.session_factory, retriever)
logger = logging.getLogger(__name__)


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


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    meeting_ids: Optional[list[str]] = None
    speaker: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


def _model_name() -> Optional[str]:
    llm = answerer._llm
    return getattr(llm, "model", None) or getattr(llm, "name", None)


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@app.post("/api/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    """Grounded answer as Server-Sent Events: `citations`, then `token`s, then `done` (or `error`)."""
    filters = SearchFilters(
        meeting_ids=request.meeting_ids,
        speaker=request.speaker,
        date_from=request.date_from,
        date_to=request.date_to,
    )

    question = request.question.strip()
    query_id = str(uuid4())

    def events() -> Iterator[str]:
        try:
            for event in answerer.answer(question, filters):
                if event.type == "done":
                    event.data["query_id"] = query_id
                    record_query(answerer.session_factory, query_id, question, filters, _model_name(), done=event.data)
                yield _sse(event.type, event.data)
        except Exception as exc:  # the stream has started, so report errors in-band
            logger.exception("Chat failed for query %s", query_id)
            record_query(answerer.session_factory, query_id, question, filters, _model_name(), error=str(exc))
            yield _sse("error", {"message": str(exc), "query_id": query_id})

    # A sync generator: Starlette iterates it in a threadpool, so blocking LLM/DB calls are fine.
    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    try:
        return ingestion_service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found") from exc
