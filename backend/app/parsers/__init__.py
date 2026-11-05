from .base import (
    TranscriptSource,
    file_extension,
    get_source,
    parse_transcript,
    register_source,
    supported_extensions,
)
from .text import parse_txt_transcript
from .vtt import parse_vtt_transcript

# Adding a format = write a parser and register it here. Nothing downstream changes.
register_source(TranscriptSource("txt", frozenset({"txt"}), parse_txt_transcript))
register_source(TranscriptSource("vtt", frozenset({"vtt"}), parse_vtt_transcript))

__all__ = [
    "TranscriptSource",
    "file_extension",
    "get_source",
    "parse_transcript",
    "parse_txt_transcript",
    "parse_vtt_transcript",
    "register_source",
    "supported_extensions",
]
