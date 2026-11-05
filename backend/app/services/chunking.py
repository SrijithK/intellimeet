from __future__ import annotations

from typing import List

from app.models import Meeting, TranscriptChunk, TranscriptTurn

DEFAULT_WINDOW_SECONDS = 90.0
DEFAULT_MAX_CHARS = 1000


def chunk_meeting(
    meeting: Meeting,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> List[TranscriptChunk]:
    """Group whole turns into time windows, overlapping by one turn.

    A chunk closes when adding the next turn would exceed ``window_seconds`` (measured
    from the chunk's first turn) or ``max_chars``. Turns are never split, so a single
    very long turn becomes its own chunk. The last turn of each chunk is repeated as the
    first turn of the next one, so an exchange that straddles a boundary stays together.
    Turn indices refer to positions in ``meeting.turns``.
    """
    indexed = [(i, turn) for i, turn in enumerate(meeting.turns) if turn.text.strip()]
    chunks: List[TranscriptChunk] = []
    window: List[tuple] = []

    for idx, turn in indexed:
        if window and _would_overflow(window, turn, window_seconds, max_chars):
            chunks.append(_build_chunk(window))
            # Carry the last turn over as overlap, unless it alone is what's full.
            window = window[-1:] if len(window) > 1 else []
            if window and _would_overflow(window, turn, window_seconds, max_chars):
                window = []
        window.append((idx, turn))

    if window:
        last = _build_chunk(window)
        # Skip a trailing chunk that only repeats the previous chunk's overlap turn.
        if not chunks or last.last_turn_idx > chunks[-1].last_turn_idx:
            chunks.append(last)

    return chunks


def _line(turn: TranscriptTurn) -> str:
    return f"{turn.speaker}: {turn.text.strip()}"


def _would_overflow(window, turn: TranscriptTurn, window_seconds: float, max_chars: int) -> bool:
    duration = turn.start - window[0][1].start
    length = sum(len(_line(t)) + 1 for _, t in window) + len(_line(turn))
    return duration > window_seconds or length > max_chars


def _build_chunk(window) -> TranscriptChunk:
    turns = [turn for _, turn in window]
    speakers: List[str] = []
    for turn in turns:
        if turn.speaker not in speakers:
            speakers.append(turn.speaker)
    last = turns[-1]
    return TranscriptChunk(
        first_turn_idx=window[0][0],
        last_turn_idx=window[-1][0],
        speakers=speakers,
        text="\n".join(_line(turn) for turn in turns),
        start=turns[0].start,
        end=last.end if last.end is not None else last.start,
    )
