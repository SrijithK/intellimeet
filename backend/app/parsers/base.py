from __future__ import annotations

from typing import Callable, Dict, FrozenSet, NamedTuple

from app.models import Meeting

ParseFn = Callable[[str, str], Meeting]  # (file_name, text) -> Meeting


class TranscriptSource(NamedTuple):
    """An input format that can be turned into the canonical Meeting model."""

    source_type: str  # stored on meetings.source_type
    extensions: FrozenSet[str]
    parse: ParseFn


_SOURCES: Dict[str, TranscriptSource] = {}


def register_source(source: TranscriptSource) -> None:
    for extension in source.extensions:
        _SOURCES[extension.lower()] = source


def file_extension(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def supported_extensions() -> FrozenSet[str]:
    return frozenset(_SOURCES)


def get_source(file_name: str) -> TranscriptSource:
    extension = file_extension(file_name)
    try:
        return _SOURCES[extension]
    except KeyError:
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}") from None


def parse_transcript(file_name: str, text: str) -> Meeting:
    source = get_source(file_name)
    meeting = source.parse(file_name, text)
    meeting.source_type = source.source_type
    return meeting
