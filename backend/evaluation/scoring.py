"""Golden-set loading and scoring, shared by the full evaluation and the CI retrieval test."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

GOLDEN_SET_PATH = Path(__file__).with_name("golden_set.json")
TRANSCRIPTS_DIR = Path(__file__).resolve().parents[2] / "data" / "transcripts"

TurnKey = tuple[str, int]  # (meeting title, turn index)
Requirement = Union[str, list[str]]  # a list means "any of these"


@dataclass
class GoldenCase:
    id: str
    category: str
    question: str
    answerable: bool = True
    meeting: Optional[str] = None  # scope the question to this meeting title
    expected_turns: list[TurnKey] = field(default_factory=list)
    must_include: list[Requirement] = field(default_factory=list)


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[GoldenCase]:
    raw = json.loads(path.read_text())
    return [
        GoldenCase(
            id=case["id"],
            category=case["category"],
            question=case["question"],
            answerable=case.get("answerable", True),
            meeting=case.get("meeting"),
            expected_turns=[(title, idx) for title, idx in case.get("expected_turns", [])],
            must_include=case.get("must_include", []),
        )
        for case in raw["cases"]
    ]


def first_relevant_rank(chunk_ranges: list[tuple[str, int, int]], expected: list[TurnKey]) -> Optional[int]:
    """1-based rank of the first retrieved chunk containing any expected turn, or None."""
    for rank, (title, first, last) in enumerate(chunk_ranges, start=1):
        if any(title == t and first <= idx <= last for t, idx in expected):
            return rank
    return None


# Rendered citations, e.g. "[product-launch-planning, 00:01:44, Priya]".
CITATION_RE = re.compile(r"\[[^\[\]]+?, \d{2}:\d{2}:\d{2}, [^\[\]]+?\]")


def missing_facts(answer: str, requirements: list[Requirement]) -> list[str]:
    """Requirements not satisfied by the answer (case-insensitive substring match).

    Citations are removed first: a required "17" must not be satisfied by a timestamp like 00:01:17.
    """
    text = CITATION_RE.sub(" ", answer).lower()
    missing = []
    for requirement in requirements:
        options = [requirement] if isinstance(requirement, str) else requirement
        if not any(option.lower() in text for option in options):
            missing.append(" | ".join(options))
    return missing


@dataclass
class CaseResult:
    case: GoldenCase
    retrieval_rank: Optional[int] = None
    found: Optional[bool] = None
    answer: str = ""
    cited: list[TurnKey] = field(default_factory=list)
    cites_expected: Optional[bool] = None
    missing: list[str] = field(default_factory=list)
    latency_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None

    @property
    def retrieval_hit(self) -> bool:
        return self.retrieval_rank is not None

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        if not self.case.answerable:
            return self.found is False
        return bool(self.found and self.cites_expected and not self.missing)

    @property
    def failure_reason(self) -> str:
        if self.error:
            return f"error: {self.error}"
        if not self.case.answerable:
            return "" if self.found is False else "answered an unanswerable question"
        reasons = []
        if not self.found:
            reasons.append("said not found")
        elif not self.cites_expected:
            reasons.append("did not cite an expected line")
        if self.missing:
            reasons.append(f"missing: {', '.join(self.missing)}")
        return "; ".join(reasons)


def summarize(results: list[CaseResult], k: int) -> dict[str, Any]:
    answerable = [r for r in results if r.case.answerable]
    unanswerable = [r for r in results if not r.case.answerable]
    ranks = [r.retrieval_rank for r in answerable]
    latencies = [r.latency_ms for r in results if r.latency_ms is not None]

    def rate(items: list[bool]) -> Optional[float]:
        return round(sum(items) / len(items), 3) if items else None

    return {
        "cases": len(results),
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        f"retrieval_hit_at_{k}": rate([rank is not None for rank in ranks]),
        "retrieval_mrr": round(sum(1 / rank for rank in ranks if rank) / len(ranks), 3) if ranks else None,
        "answer_pass_rate": rate([r.passed for r in answerable]),
        "cited_expected_line": rate([bool(r.cites_expected) for r in answerable]),
        "facts_present": rate([not r.missing for r in answerable]),
        "false_not_found": rate([r.found is False for r in answerable]),
        "correct_not_found": rate([r.passed for r in unanswerable]),
        "overall_pass_rate": rate([r.passed for r in results]),
        "median_latency_ms": sorted(latencies)[len(latencies) // 2] if latencies else None,
    }
