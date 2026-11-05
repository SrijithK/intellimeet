"""API contract: request/response models. These generate the OpenAPI spec (docs/openapi.json)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

JobStatus = Literal["queued", "processing", "completed", "failed"]
ExtractionStatus = Literal["pending", "completed", "failed", "skipped"]


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Meeting 123 not found"])


class Health(BaseModel):
    status: Literal["ok"]


# --- ingestion -----------------------------------------------------------------


class UploadResponse(BaseModel):
    job_id: str
    status: JobStatus


class IngestionResult(BaseModel):
    """Outcome of an ingestion job. While queued/processing only `content_hash` is set."""

    content_hash: str
    meeting_id: Optional[str] = None
    title: Optional[str] = None
    turn_count: Optional[int] = None
    chunk_count: Optional[int] = None
    extraction_status: Optional[ExtractionStatus] = None
    deduplicated: Optional[bool] = Field(None, description="True when identical content was already ingested")


class Job(BaseModel):
    job_id: str
    status: JobStatus
    file_name: str
    result: Optional[IngestionResult] = None
    error: Optional[str] = None


# --- meetings ------------------------------------------------------------------


class MeetingSummary(BaseModel):
    id: str
    title: str
    source_name: str
    source_type: str = Field(..., examples=["txt", "vtt"])
    created_at: datetime
    extraction_status: ExtractionStatus
    turn_count: int


class Turn(BaseModel):
    idx: int = Field(..., description="Position of the turn within the meeting")
    speaker: str
    text: str
    start: float = Field(..., description="Seconds from meeting start")
    end: Optional[float] = None


class SourceTurnRef(BaseModel):
    """Where an extracted record came from."""

    turn_idx: int
    speaker: str
    start: float


class Decision(SourceTurnRef):
    text: str


class ActionItem(SourceTurnRef):
    owner: str
    task: str
    due: Optional[str] = Field(None, description='Deadline as spoken, e.g. "by Friday"')


class Topic(SourceTurnRef):
    label: str


class MeetingDetail(MeetingSummary):
    media_uri: Optional[str] = None
    chunk_count: int
    extraction_error: Optional[str] = None
    decisions: list[Decision]
    action_items: list[ActionItem]
    topics: list[Topic]
    turns: list[Turn]


# --- search --------------------------------------------------------------------


class SearchResult(BaseModel):
    chunk_id: int
    meeting_id: str
    meeting_title: str
    speakers: list[str]
    text: str
    start: float
    end: Optional[float] = None
    first_turn_idx: int
    last_turn_idx: int
    score: float = Field(..., description="Reciprocal Rank Fusion score")
    vector_rank: Optional[int] = Field(None, description="1-based rank in vector search, if retrieved by it")
    text_rank: Optional[int] = Field(None, description="1-based rank in full-text search, if retrieved by it")
    similarity: Optional[float] = Field(None, description="Cosine similarity between query and chunk")


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


# --- chat ----------------------------------------------------------------------


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, examples=["What did we decide about the launch?"])
    meeting_ids: Optional[list[str]] = Field(None, description="Restrict evidence to these meetings")
    speaker: Optional[str] = Field(None, description="Only evidence in which this speaker talks")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class CitationSource(BaseModel):
    """A transcript line the answer may cite."""

    ref: int = Field(..., description="Reference number used in the prompt")
    meeting_id: str
    meeting_title: str
    turn_idx: int
    speaker: str
    start: float
    text: str
    timestamp: str = Field(..., examples=["00:01:44"])
    citation: str = Field(..., examples=["[product-launch-planning, 00:01:44, Priya]"])


class CitationsEvent(BaseModel):
    """SSE `event: citations`, sent first: every source the answer may cite (empty if nothing relevant)."""

    sources: list[CitationSource]


class TokenEvent(BaseModel):
    """SSE `event: token`: the next piece of answer text, citations already rendered."""

    text: str


class DoneEvent(BaseModel):
    """SSE `event: done`, sent last on success."""

    answer: str
    found: bool = Field(..., description="False when the answer is the not-found reply or cites nothing")
    cited: list[CitationSource]
    retrieved_chunk_ids: list[int]
    latency_ms: int
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    query_id: str = Field(..., description="Row id in the query log")


class ErrorEvent(BaseModel):
    """SSE `event: error`, sent last when answering fails after the stream started."""

    message: str
    query_id: str


SSE_EVENT_MODELS = {"citations": CitationsEvent, "token": TokenEvent, "done": DoneEvent, "error": ErrorEvent}
