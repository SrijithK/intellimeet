from __future__ import annotations

from app.models import Meeting, MeetingChunk


def chunk_meeting(meeting: Meeting, max_turns: int = 2, max_chars: int = 300) -> list[MeetingChunk]:
    chunks: list[MeetingChunk] = []
    buffer: list[MeetingChunk] = []
    current_length = 0
    current_start = None

    for turn in meeting.turns:
        turn_text = turn.text.strip()
        if not turn_text:
            continue

        chunk = MeetingChunk(
            speaker=turn.speaker,
            text=turn_text,
            start=turn.start,
            end=turn.end or turn.start,
        )

        if not buffer:
            buffer.append(chunk)
            current_length = len(turn_text)
            current_start = turn.start
            continue

        if len(" ".join(item.text for item in buffer) + " " + turn_text) > max_chars or len(buffer) >= max_turns:
            chunks.append(_flatten_chunk(buffer, current_start))
            buffer = [chunk]
            current_length = len(turn_text)
            current_start = turn.start
            continue

        buffer.append(chunk)
        current_length = len(" ".join(item.text for item in buffer))

    if buffer:
        chunks.append(_flatten_chunk(buffer, current_start))

    return chunks


def _flatten_chunk(buffer: list[MeetingChunk], start: int | None) -> MeetingChunk:
    speaker = buffer[0].speaker
    text = " ".join(item.text for item in buffer)
    end = max(item.end for item in buffer) if buffer else start
    return MeetingChunk(speaker=speaker, text=text, start=start or 0, end=end)
