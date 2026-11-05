from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Optional, Protocol


class LLMError(RuntimeError):
    """The model could not be reached or returned something unusable."""


@dataclass
class StreamChunk:
    """A piece of a streamed reply. The final chunk has done=True and token counts when known."""

    text: str = ""
    done: bool = False
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class LLMProvider(Protocol):
    """Chat model behind an interface: Ollama locally; Anthropic / Bedrock are drop-in alternatives."""

    name: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object that conforms to ``schema``."""
        ...

    def stream_chat(self, system: str, user: str) -> Iterator[StreamChunk]:
        """Stream a free-text reply."""
        ...
