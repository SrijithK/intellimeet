import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ingestion import ingestion_service
from app.validation import MAX_UPLOAD_SIZE_BYTES
from tests.fakes import FakeEmbedder



@pytest.fixture(scope="module")
def client():
    # Context manager keeps one event loop alive so background jobs can finish.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def fake_embedder():
    original = ingestion_service._embedder
    ingestion_service.embedder = FakeEmbedder()
    yield
    ingestion_service._embedder = original


def test_upload_txt_meeting_creates_and_completes_job(client):
    response = client.post(
        "/api/meetings",
        files={
            "file": (
                "demo.txt",
                "[00:01:05] Alice: We decided to move the launch.\n[00:02:10] Bob: I will own the rollout checklist.\n",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert "job_id" in payload

    job_id = payload["job_id"]
    last_status = payload["status"]

    for _ in range(50):
        status_response = client.get(f"/api/jobs/{job_id}")
        last_status = status_response.json()["status"]
        if last_status == "completed":
            break
        time.sleep(0.05)

    assert last_status == "completed"
    result = client.get(f"/api/jobs/{job_id}").json()["meeting"]
    meeting_response = client.get(f"/api/meetings/{result['meeting_id']}")
    assert meeting_response.status_code == 200
    meeting = meeting_response.json()
    assert meeting["title"] == "demo"
    assert meeting["source_type"] == "txt"
    assert meeting["chunk_count"] == 1
    assert len(meeting["turns"]) == 2
    assert meeting["turns"][0]["speaker"] == "Alice"
    assert meeting["turns"][1]["speaker"] == "Bob"


def test_rejects_unsupported_file_type(client):
    response = client.post(
        "/api/meetings",
        files={"file": ("notes.md", "# heading\nplain text\n", "text/markdown")},
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_rejects_files_above_size_limit(client):
    oversized_content = b"x" * (MAX_UPLOAD_SIZE_BYTES + 1)
    response = client.post(
        "/api/meetings",
        files={"file": ("oversized.txt", oversized_content, "text/plain")},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"].lower()


def test_rejects_duplicate_file_name_with_different_content(client):
    first_response = client.post(
        "/api/meetings",
        files={"file": ("duplicate.txt", "[00:00:01] Alice: first upload\n", "text/plain")},
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/meetings",
        files={"file": ("duplicate.txt", "[00:00:02] Bob: second upload\n", "text/plain")},
    )

    assert second_response.status_code == 409
    assert "already exists" in second_response.json()["detail"].lower()


def test_unknown_meeting_returns_404(client):
    assert client.get("/api/meetings/does-not-exist").status_code == 404
