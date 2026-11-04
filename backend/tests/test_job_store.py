from app.services.job_store import JobStore


def test_job_store_persists_jobs_and_retrieves_by_id():
    store = JobStore(database_url="sqlite:///:memory:")

    job = store.create_job("demo.txt", b"hello world")
    persisted = store.get_job(job["job_id"])

    assert persisted["file_name"] == "demo.txt"
    assert persisted["status"] == "queued"

    store.update_status(job["job_id"], "completed")
    assert store.get_job(job["job_id"])["status"] == "completed"
