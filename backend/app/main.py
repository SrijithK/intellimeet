from __future__ import annotations

import asyncio

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.services.ingestion import ingestion_service
from app.validation import MAX_UPLOAD_SIZE_BYTES, validate_upload

app = FastAPI(title="IntelliMeet API")


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

    asyncio.create_task(ingestion_service.process_job(job["job_id"], file_name, content))

    return {"job_id": job["job_id"], "status": job["status"]}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    try:
        return ingestion_service.get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found") from exc
