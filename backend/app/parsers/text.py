from __future__ import annotations

import re

from app.models import Meeting, TranscriptTurn

LINE_RE = re.compile(r"^\[(?P<time>\d{1,2}:\d{2}:\d{2})\]\s*(?P<speaker>[^:]+):\s*(?P<text>.*)$")


def parse_txt_transcript(file_name: str, content: str) -> Meeting:
    """Parse ``[hh:mm:ss] Speaker: text`` lines.

    Lines without a timestamp are treated as continuations of the previous turn
    (wrapped text); any before the first turn are ignored.
    """
    title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    meeting = Meeting(title=title, source_name=file_name)

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = LINE_RE.match(line)
        if not match:
            if meeting.turns:
                previous = meeting.turns[-1]
                previous.text = f"{previous.text} {line}".strip()
            continue

        hours, minutes, seconds = map(int, match.group("time").split(":"))
        meeting.turns.append(
            TranscriptTurn(
                speaker=match.group("speaker").strip(),
                text=match.group("text").strip(),
                start=hours * 3600 + minutes * 60 + seconds,
            )
        )

    return meeting
