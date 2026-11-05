from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import Callable, Protocol

JobHandler = Callable[[str, str, bytes], Awaitable[None]]  # (job_id, file_name, content)


class JobQueue(Protocol):
    """Where ingestion jobs are sent. In-process locally; SQS on AWS."""

    async def submit(self, job_id: str, file_name: str, content: bytes) -> None: ...


class InProcessJobQueue:
    """Runs jobs as asyncio tasks on the current event loop."""

    def __init__(self, handler: JobHandler) -> None:
        self._handler = handler
        # asyncio only keeps weak references to tasks; hold them until they finish.
        self._tasks: set[asyncio.Task] = set()

    async def submit(self, job_id: str, file_name: str, content: bytes) -> None:
        task = asyncio.create_task(self._handler(job_id, file_name, content))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        """Wait for in-flight jobs (used on shutdown and in tests)."""
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
