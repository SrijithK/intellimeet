from __future__ import annotations

from app.models import Meeting, TranscriptTurn


def _parse_timestamp(value: str) -> int:
    hours, minutes, seconds_and_ms = value.split(":")
    seconds, milliseconds = seconds_and_ms.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + (int(milliseconds) / 1000)


def parse_vtt_transcript(file_name: str, content: str) -> Meeting:
    title = file_name.rsplit(".", 1)[0] if "." in file_name else file_name
    meeting = Meeting(title=title, source_name=file_name)

    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].upper() == "WEBVTT":
            lines = lines[1:]
        if not lines:
            continue
        if "-->" not in lines[0]:
            continue

        timeline = lines[0]
        start_value, end_value = [item.strip() for item in timeline.split("-->", 1)]
        start = _parse_timestamp(start_value)
        end = _parse_timestamp(end_value)

        message_lines = lines[1:]
        message = "\n".join(message_lines)
        speaker = "Unknown"
        text = message

        if ":" in message:
            speaker, text = message.split(":", 1)
            speaker = speaker.strip()
            text = text.strip()

        meeting.turns.append(
            TranscriptTurn(
                speaker=speaker,
                text=text,
                start=int(start),
                end=int(end),
            )
        )

    return meeting
