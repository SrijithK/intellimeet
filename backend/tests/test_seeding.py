import asyncio

from app.services.ingestion import IngestionService
from app.services.seeding import seed_transcripts
from tests.fakes import FakeEmbedder


class RecordingQueue:
    def __init__(self):
        self.submitted = []

    async def submit(self, job_id, file_name, content):
        self.submitted.append(file_name)


def test_seeds_supported_files_once_and_skips_bad_ones(tmp_path, session_factory):
    (tmp_path / "a.txt").write_text("[00:00:01] Alice: Hello\n")
    (tmp_path / "b.vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nBob: Hi\n")
    (tmp_path / "notes.md").write_text("# ignored")
    (tmp_path / "empty.txt").write_text("")
    service = IngestionService(session_factory=session_factory, embedder=FakeEmbedder())

    first, second = RecordingQueue(), RecordingQueue()
    job_ids = asyncio.run(seed_transcripts(tmp_path, service, first))
    for job_id in job_ids:
        service.job_store.update_status(job_id, "completed")
    asyncio.run(seed_transcripts(tmp_path, service, second))  # e.g. the next container restart

    assert first.submitted == ["a.txt", "b.vtt"]
    assert second.submitted == []


def test_jobs_interrupted_by_a_restart_are_requeued(tmp_path, session_factory):
    (tmp_path / "a.txt").write_text("[00:00:01] Alice: Hello\n")
    service = IngestionService(session_factory=session_factory, embedder=FakeEmbedder())
    (job_id,) = asyncio.run(seed_transcripts(tmp_path, service, RecordingQueue()))
    service.job_store.update_status(job_id, "processing")  # container stopped mid-ingestion

    again = RecordingQueue()
    asyncio.run(seed_transcripts(tmp_path, service, again))

    assert again.submitted == ["a.txt"]


def test_missing_directory_is_skipped(tmp_path, session_factory):
    service = IngestionService(session_factory=session_factory, embedder=FakeEmbedder())

    assert asyncio.run(seed_transcripts(tmp_path / "nope", service, RecordingQueue())) == []
