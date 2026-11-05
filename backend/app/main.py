from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.openapi.utils import get_openapi
from fastapi.responses import StreamingResponse

from app import schemas
from app.config import settings
from app.services import meeting_store
from app.services.answering import Answerer
from app.services.ingestion import ingestion_service
from app.services.job_queue import InProcessJobQueue
from app.services.query_log import record_query
from app.services.retrieval import Retriever, SearchFilters
from app.services.seeding import seed_transcripts
from app.validation import MAX_UPLOAD_SIZE_BYTES, validate_upload

API_VERSION = "0.1.0"

# Our app.* loggers (ingestion, extraction, seeding) are otherwise silent: uvicorn only configures its own.
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

job_queue = InProcessJobQueue(ingestion_service.process_job)
retriever = Retriever(ingestion_service.session_factory)
answerer = Answerer(ingestion_service.session_factory, retriever)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.seed_dir:
        await seed_transcripts(Path(settings.seed_dir), ingestion_service, job_queue)
    yield
    await job_queue.drain()


app = FastAPI(
    title="IntelliMeet API",
    version=API_VERSION,
    description=(
        "Ingest meeting transcripts and ask questions about discussions, decisions and action items. "
        "Answers are grounded in the transcripts and cite `[meeting, hh:mm:ss, speaker]`."
    ),
    lifespan=lifespan,
)


def _error(description: str, example: str) -> dict[str, Any]:
    return {
        "model": schemas.ErrorResponse,
        "description": description,
        "content": {"application/json": {"example": {"detail": example}}},
    }


@app.get("/health", response_model=schemas.Health, tags=["system"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/meetings",
    response_model=schemas.UploadResponse,
    tags=["meetings"],
    summary="Upload a transcript",
    description=(
        "Upload a `.txt` (`[hh:mm:ss] Speaker: text` per line) or WebVTT `.vtt` transcript. "
        "Ingestion (parse, chunk, embed, extract) runs in the background; poll `GET /api/jobs/{job_id}`. "
        "Re-uploading an identical file returns the existing job."
    ),
    responses={
        400: _error("Empty file or unsupported file type", "Unsupported file type: md"),
        409: _error(
            "A different file with the same name exists",
            "A file named 'notes.txt' already exists with different content.",
        ),
        413: _error(
            f"File larger than {MAX_UPLOAD_SIZE_BYTES} bytes",
            f"File is too large. Maximum allowed size is {MAX_UPLOAD_SIZE_BYTES} bytes.",
        ),
    },
)
async def upload_meeting(file: UploadFile = File(..., description="Transcript file")) -> dict[str, object]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A transcript file is required.")

    file_name = file.filename
    content = await file.read()
    try:
        validate_upload(file_name, content)
    except ValueError as exc:
        message = str(exc)
        status_code = 413 if "too large" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    try:
        job = ingestion_service.create_job(file_name, content)
    except ValueError as exc:
        message = str(exc)
        status_code = 409 if "already exists" in message.lower() else 400
        raise HTTPException(status_code=status_code, detail=message) from exc

    if job["status"] == "queued":  # an identical re-upload returns the existing job as-is
        await job_queue.submit(job["job_id"], file_name, content)

    return {"job_id": job["job_id"], "status": job["status"]}


@app.get("/api/meetings", response_model=list[schemas.MeetingSummary], tags=["meetings"], summary="List meetings")
def list_meetings() -> list[dict[str, object]]:
    with ingestion_service.session_factory() as session:
        return meeting_store.list_meetings(session)


@app.get(
    "/api/meetings/{meeting_id}",
    response_model=schemas.MeetingDetail,
    tags=["meetings"],
    summary="Get a meeting",
    description="Transcript turns plus extracted decisions, action items and topics, each linked to its source turn.",
    responses={404: _error("Unknown meeting", "Meeting 123 not found")},
)
def get_meeting(meeting_id: str) -> dict[str, object]:
    with ingestion_service.session_factory() as session:
        meeting = meeting_store.get_meeting(session, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found")
    return meeting


@app.get(
    "/api/jobs/{job_id}",
    response_model=schemas.Job,
    tags=["meetings"],
    summary="Get ingestion job status",
    responses={404: _error("Unknown job", "Job 123 not found")},
)
def get_job(job_id: str) -> dict[str, object]:
    try:
        return ingestion_service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found") from exc


@app.get(
    "/api/search",
    response_model=schemas.SearchResponse,
    tags=["search"],
    summary="Hybrid search over transcript chunks",
    description="Vector and full-text search fused with Reciprocal Rank Fusion. Useful for inspecting retrieval.",
)
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


CHAT_DESCRIPTION = """Answers a question from the meeting transcripts as a stream of
[Server-Sent Events](https://html.spec.whatwg.org/multipage/server-sent-events.html):

1. `event: citations`: `CitationsEvent`, every source the answer may cite
2. `event: token` (repeated): `TokenEvent`, answer text with citations rendered as `[meeting, hh:mm:ss, speaker]`
3. `event: done`: `DoneEvent`, the full answer, cited sources and usage; or `event: error`: `ErrorEvent`

Each event's `data:` line is JSON. When nothing relevant is found, the answer is a fixed
"couldn't find" sentence and `done.found` is `false`."""


@app.post(
    "/api/chat",
    tags=["chat"],
    summary="Ask a question (streamed)",
    description=CHAT_DESCRIPTION,
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Event stream",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "example": (
                        'event: citations\ndata: {"sources": [...]}\n\n'
                        'event: token\ndata: {"text": "The launch moved to November 17th "}\n\n'
                        'event: token\ndata: {"text": "[product-launch-planning, 00:01:44, Priya]."}\n\n'
                        'event: done\ndata: {"answer": "...", "found": true, ...}\n\n'
                    ),
                }
            },
        }
    },
)
def chat(request: schemas.ChatRequest) -> StreamingResponse:
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


def _model_name() -> Optional[str]:
    llm = answerer._llm
    return getattr(llm, "model", None) or getattr(llm, "name", None)


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def custom_openapi() -> dict[str, Any]:
    """Standard spec plus the SSE event payload schemas, which no endpoint references directly."""
    if app.openapi_schema:
        return app.openapi_schema
    spec = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    components = spec.setdefault("components", {}).setdefault("schemas", {})
    for model in schemas.SSE_EVENT_MODELS.values():
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        components.update(schema.pop("$defs", {}))
        components[model.__name__] = schema
    app.openapi_schema = spec
    return spec


app.openapi = custom_openapi
