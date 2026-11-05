from __future__ import annotations

from app.parsers import file_extension, supported_extensions

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024


def validate_upload(file_name: str, content: bytes) -> None:
    if not file_name:
        raise ValueError("A transcript file is required.")
    if len(content) == 0:
        raise ValueError("Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(f"File is too large. Maximum allowed size is {MAX_UPLOAD_SIZE_BYTES} bytes.")

    extension = file_extension(file_name)
    if extension not in supported_extensions():
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")
