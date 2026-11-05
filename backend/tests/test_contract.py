"""The API contract (docs/openapi.json) must match the code, and responses must match the contract."""

import json

import pytest
from fastapi.testclient import TestClient

from app import schemas
from app.main import answerer, app, retriever
from app.services.ingestion import ingestion_service
from scripts.export_openapi import SPEC_PATH, render
from tests.fakes import FakeEmbedder, FakeLLM
from tests.test_api import _sse_events, _upload_and_wait


def test_committed_openapi_spec_is_up_to_date():
    committed = SPEC_PATH.read_text() if SPEC_PATH.exists() else ""

    assert committed == render(), "API changed: run `.venv/bin/python -m scripts.export_openapi` and commit"


def test_spec_documents_sse_events_and_errors():
    spec = app.openapi()

    for name in ("CitationsEvent", "TokenEvent", "DoneEvent", "ErrorEvent", "CitationSource"):
        assert name in spec["components"]["schemas"]
    chat = spec["paths"]["/api/chat"]["post"]
    assert "text/event-stream" in chat["responses"]["200"]["content"]
    upload = spec["paths"]["/api/meetings"]["post"]["responses"]
    assert {"400", "409", "413"} <= upload.keys()
    assert "404" in spec["paths"]["/api/meetings/{meeting_id}"]["get"]["responses"]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fakes():
    originals = ingestion_service._embedder, retriever._embedder, answerer._llm
    ingestion_service.embedder = retriever.embedder = FakeEmbedder()
    answerer.llm = FakeLLM(stream=["Approved ", "[1]."])
    yield
    ingestion_service._embedder, retriever._embedder, answerer._llm = originals


def test_list_and_detail_match_their_models(client):
    job = _upload_and_wait(client, "budget.txt", "[00:00:05] Alice: The marketing budget is approved.\n")
    schemas.Job.model_validate(job)

    meetings = client.get("/api/meetings").json()
    assert [m["title"] for m in meetings] == ["budget"]
    assert meetings[0]["turn_count"] == 1
    schemas.MeetingSummary.model_validate(meetings[0])

    detail = client.get(f"/api/meetings/{meetings[0]['id']}").json()
    schemas.MeetingDetail.model_validate(detail)
    assert detail["extraction_status"] == "skipped"


def test_chat_events_match_documented_event_models(client):
    _upload_and_wait(client, "budget.txt", "[00:00:05] Alice: The marketing budget is approved.\n")

    events = _sse_events(client.post("/api/chat", json={"question": "Was the marketing budget approved?"}).text)

    assert events[0][0] == "citations" and events[-1][0] == "done"
    for name, data in events:
        schemas.SSE_EVENT_MODELS[name].model_validate(data)
    json.dumps(events)  # plain JSON throughout
