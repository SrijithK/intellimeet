from __future__ import annotations

MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {"txt", "vtt"}


def validate_upload(file_name: str, content: bytes) -> None:
    if not file_name:
        raise ValueError("A transcript file is required.")
    if len(content) == 0:
        raise ValueError("Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(f"File is too large. Maximum allowed size is {MAX_UPLOAD_SIZE_BYTES} bytes.")

    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")
