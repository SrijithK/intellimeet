from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import sessionmaker

from app.db_models import QueryRecord
from app.services.retrieval import SearchFilters

logger = logging.getLogger(__name__)


def record_query(
    session_factory: sessionmaker,
    query_id: str,
    question: str,
    filters: SearchFilters,
    model: Optional[str],
    done: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Persist one chat request. Never raises: losing a log row must not break the answer."""
    done = done or {}
    try:
        with session_factory.begin() as session:
            session.add(
                QueryRecord(
                    id=query_id,
                    question=question,
                    filters={k: _jsonable(v) for k, v in asdict(filters).items() if v} if filters else {},
                    retrieved_chunk_ids=done.get("retrieved_chunk_ids", []),
                    cited=[
                        {key: c[key] for key in ("meeting_id", "turn_idx", "speaker", "start")}
                        for c in done.get("cited", [])
                    ],
                    answer=done.get("answer"),
                    found=done.get("found"),
                    model=model,
                    prompt_tokens=done.get("prompt_tokens"),
                    output_tokens=done.get("output_tokens"),
                    latency_ms=done.get("latency_ms"),
                    error=error,
                )
            )
    except Exception:
        logger.exception("Could not record query %s", query_id)


def _jsonable(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value
