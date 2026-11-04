from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TranscriptTurn:
    speaker: str
    text: str
    start: int
    end: int | None = None


@dataclass
class Meeting:
    title: str
    source_name: str
    turns: List[TranscriptTurn] = field(default_factory=list)
