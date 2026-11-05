from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TranscriptTurn:
    speaker: str
    text: str
    start: float  # seconds from meeting start
    end: Optional[float] = None


@dataclass
class Meeting:
    """Canonical transcript model. Every source format is parsed into this."""

    title: str
    source_name: str
    source_type: str = "txt"
    turns: List[TranscriptTurn] = field(default_factory=list)


@dataclass
class TranscriptChunk:
    """A window of consecutive turns, the unit we embed and retrieve."""

    first_turn_idx: int
    last_turn_idx: int
    speakers: List[str]  # unique, in order of first appearance
    text: str  # one "Speaker: text" line per turn
    start: float
    end: Optional[float] = None
