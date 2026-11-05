"""Golden-set evaluation of retrieval and grounded answers, end to end against the local LLM.

Run from backend/ (Postgres and Ollama running):
    .venv/bin/python -m evaluation.run_eval            # fresh DB, ingest transcripts, evaluate
    .venv/bin/python -m evaluation.run_eval --reuse    # skip ingestion, reuse the eval DB
    .venv/bin/python -m evaluation.run_eval --only launch-why,no-ceo

Uses its own database (EVAL_DATABASE_URL, default intellimeet_eval) so dev data is untouched.
Writes evaluation/results/latest.json and latest.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVAL_DATABASE_URL = os.getenv(
    "EVAL_DATABASE_URL", "postgresql+psycopg://intellimeet:intellimeet@localhost:5433/intellimeet_eval"
)
os.environ["DATABASE_URL"] = EVAL_DATABASE_URL  # before app settings are read

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import build_session_factory  # noqa: E402
from app.db_admin import ensure_database, migrate, truncate_all  # noqa: E402
from app.db_models import ChunkRecord, MeetingRecord  # noqa: E402
from app.llm import get_llm  # noqa: E402
from app.services.answering import DEFAULT_TOP_K, Answerer  # noqa: E402
from app.services.embedder import get_embedder  # noqa: E402
from app.services.extraction import Extractor  # noqa: E402
from app.services.ingestion import IngestionService  # noqa: E402
from app.services.retrieval import Retriever, SearchFilters  # noqa: E402
from evaluation.scoring import (  # noqa: E402
    TRANSCRIPTS_DIR,
    CaseResult,
    GoldenCase,
    first_relevant_rank,
    load_golden_set,
    missing_facts,
    summarize,
)

RESULTS_DIR = Path(__file__).with_name("results")


def ingest(session_factory) -> None:
    truncate_all(EVAL_DATABASE_URL)
    service = IngestionService(session_factory=session_factory, embedder=get_embedder(), extractor=Extractor(get_llm()))
    for path in sorted(TRANSCRIPTS_DIR.iterdir()):
        started = time.monotonic()
        result = service.ingest(path.name, path.read_bytes())
        print(f"  ingested {path.name}: extraction {result['extraction_status']} ({time.monotonic() - started:.1f}s)")


def run_case(case: GoldenCase, answerer: Answerer, session_factory, meeting_ids: dict[str, str]) -> CaseResult:
    result = CaseResult(case=case)
    filters = SearchFilters(meeting_ids=[meeting_ids[case.meeting]] if case.meeting else None)
    try:
        done = next(e.data for e in answerer.answer(case.question, filters) if e.type == "done")
    except Exception as exc:  # report and carry on with the next case
        result.error = str(exc)
        return result

    with session_factory() as session:
        rows = session.execute(
            select(ChunkRecord.id, MeetingRecord.title, ChunkRecord.first_turn_idx, ChunkRecord.last_turn_idx)
            .join(MeetingRecord, MeetingRecord.id == ChunkRecord.meeting_id)
            .where(ChunkRecord.id.in_(done["retrieved_chunk_ids"]))
        ).all()
    by_id = {row.id: (row.title, row.first_turn_idx, row.last_turn_idx) for row in rows}
    ranges = [by_id[chunk_id] for chunk_id in done["retrieved_chunk_ids"]]

    result.retrieval_rank = first_relevant_rank(ranges, case.expected_turns)
    result.found = done["found"]
    result.answer = done["answer"]
    result.cited = [(c["meeting_title"], c["turn_idx"]) for c in done["cited"]]
    result.cites_expected = any(turn in case.expected_turns for turn in result.cited)
    result.missing = missing_facts(result.answer, case.must_include) if case.answerable else []
    result.latency_ms = done["latency_ms"]
    result.prompt_tokens = done.get("prompt_tokens")
    result.output_tokens = done.get("output_tokens")
    return result


def write_reports(results: list[CaseResult], summary: dict, meta: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    payload = {
        "meta": meta,
        "summary": summary,
        "cases": [
            {
                "id": r.case.id,
                "category": r.case.category,
                "question": r.case.question,
                "passed": r.passed,
                "failure": r.failure_reason,
                "retrieval_rank": r.retrieval_rank,
                "found": r.found,
                "cited": r.cited,
                "answer": r.answer,
                "latency_ms": r.latency_ms,
                "prompt_tokens": r.prompt_tokens,
                "output_tokens": r.output_tokens,
            }
            for r in results
        ],
    }
    (RESULTS_DIR / "latest.json").write_text(json.dumps(payload, indent=2) + "\n")

    lines = [
        "# Golden-set evaluation",
        "",
        f"Run {meta['run_at']} · model `{meta['model']}` · embedder `{meta['embedder']}` · top_k {meta['top_k']}",
        "",
        "| Metric | Value |",
        "|---|---|",
        *[f"| {name} | {value} |" for name, value in summary.items()],
        "",
        "| Case | Category | Retrieval rank | Result | Notes |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        rank = "n/a" if not r.case.answerable else (r.retrieval_rank or "miss")
        lines.append(
            f"| {r.case.id} | {r.case.category} | {rank} | {'pass' if r.passed else 'FAIL'} | {r.failure_reason} |"
        )
    failures = [r for r in results if not r.passed]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            lines += [f"**{r.case.id}**: {r.case.question}", "", f"> {r.answer or r.error}", ""]
    (RESULTS_DIR / "latest.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reuse", action="store_true", help="skip ingestion and reuse the eval database")
    parser.add_argument("--only", help="comma-separated case ids")
    args = parser.parse_args()

    ensure_database(EVAL_DATABASE_URL)
    migrate(EVAL_DATABASE_URL)
    session_factory = build_session_factory(EVAL_DATABASE_URL)
    if not args.reuse:
        print("Ingesting transcripts (embeddings + LLM extraction)...")
        ingest(session_factory)

    with session_factory() as session:
        meeting_ids = dict(session.execute(select(MeetingRecord.title, MeetingRecord.id)).all())
    cases = load_golden_set()
    if args.only:
        wanted = set(args.only.split(","))
        cases = [case for case in cases if case.id in wanted]

    answerer = Answerer(session_factory, Retriever(session_factory, get_embedder()), get_llm())
    results = []
    for case in cases:
        result = run_case(case, answerer, session_factory, meeting_ids)
        results.append(result)
        print(f"  {'pass' if result.passed else 'FAIL'}  {case.id:28} {result.failure_reason}")

    summary = summarize(results, k=DEFAULT_TOP_K)
    meta = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": f"{settings.llm_provider}:{settings.ollama_model}",
        "embedder": "BAAI/bge-small-en-v1.5",
        "top_k": DEFAULT_TOP_K,
    }
    write_reports(results, summary, meta)
    print(json.dumps(summary, indent=2))
    print(f"Reports: {RESULTS_DIR / 'latest.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
