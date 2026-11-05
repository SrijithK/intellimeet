from __future__ import annotations

import re
from typing import Optional

from app.models import Meeting, TranscriptTurn

# Hours are optional in WebVTT ("01:02.500" is valid).
TIMESTAMP = r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})"
TIMING_RE = re.compile(rf"^{TIMESTAMP}\s*-->\s*{TIMESTAMP}")
VOICE_RE = re.compile(r"<v(?:\.[^\s>]+)*\s+([^>]+)>")  # <v Alice> or <v.loud Alice>
TAG_RE = re.compile(r"<[^>]+>")
SPEAKER_PREFIX_RE = re.compile(r"^([^:]{1,60}):\s+(.*)$", re.DOTALL)
SKIPPED_BLOCKS = ("WEBVTT", "NOTE", "STYLE", "REGION")


def _seconds(hours: Optional[str], minutes: str, seconds: str, millis: str) -> float:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def _speaker_and_text(payload: str) -> tuple[str, str]:
    voice = VOICE_RE.search(payload)
    if voice:
        return voice.group(1).strip(), TAG_RE.sub("", payload).strip()
    plain = TAG_RE.sub("", payload).strip()
    prefixed = SPEAKER_PREFIX_RE.match(plain)
    if prefixed:
        return prefixed.group(1).strip(), prefixed.group(2).strip()
    return "Unknown", plain


def parse_vtt_transcript(file_name: str, content: str) -> Meeting:
    title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    meeting = Meeting(title=title, source_name=file_name)

    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n\s*\n", normalized):
        lines: list[str] = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines or lines[0].split(" ", 1)[0].upper() in SKIPPED_BLOCKS:
            continue

        # A cue may start with an identifier line (Zoom numbers every cue).
        timing_index = next((i for i, line in enumerate(lines[:2]) if TIMING_RE.match(line)), None)
        if timing_index is None:
            continue
        groups = TIMING_RE.match(lines[timing_index]).groups()
        payload = " ".join(lines[timing_index + 1 :])
        if not payload:
            continue

        speaker, text = _speaker_and_text(payload)
        if not text:
            continue
        meeting.turns.append(
            TranscriptTurn(speaker=speaker, text=text, start=_seconds(*groups[:4]), end=_seconds(*groups[4:]))
        )

    return meeting
