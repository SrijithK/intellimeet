from __future__ import annotations

import re

from app.models import Meeting, TranscriptTurn

LINE_RE = re.compile(r"^\[(?P<time>\d{2}:\d{2}:\d{2})\]\s*(?P<speaker>[^:]+):\s*(?P<text>.*)$")


def parse_txt_transcript(file_name: str, content: str) -> Meeting:
    title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    meeting = Meeting(title=title, source_name=file_name)

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = LINE_RE.match(line)
        if not match:
            continue

        timestamp = match.group("time")
        hours, minutes, seconds = map(int, timestamp.split(":"))
        start = hours * 3600 + minutes * 60 + seconds
        speaker = match.group("speaker").strip()
        text = match.group("text").strip()

        meeting.turns.append(
            TranscriptTurn(
                speaker=speaker,
                text=text,
                start=start,
            )
        )

    return meeting
