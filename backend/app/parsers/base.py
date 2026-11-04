from __future__ import annotations

import re
from typing import Optional

TIME_RE = re.compile(r"^(?P<hours>\d{2}):(?P<minutes>\d{2}):(?P<seconds>\d{2})(?:\.(?P<milliseconds>\d{1,3}))?$")
SPEAKER_RE = re.compile(r"^(?P<speaker>[^:]+):\s*(?P<text>.*)$")


def parse_timestamp(value: str) -> int:
    match = TIME_RE.match(value.strip())
    if not match:
        raise ValueError(f"Unsupported timestamp format: {value!r}")

    groups = match.groupdict()
    hours = int(groups["hours"])
    minutes = int(groups["minutes"])
    seconds = int(groups["seconds"])
    milliseconds = int((groups["milliseconds"] or "0").ljust(3, "0"))
    return hours * 3600 + minutes * 60 + seconds + (milliseconds / 1000)


def parse_speaker_line(raw_line: str) -> tuple[str, str]:
    match = SPEAKER_RE.match(raw_line.strip())
    if not match:
        raise ValueError(f"Could not parse speaker line: {raw_line!r}")
    return match.group("speaker").strip(), match.group("text").strip()
