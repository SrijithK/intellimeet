from __future__ import annotations

from typing import Any, Protocol


class LLMError(RuntimeError):
    """The model could not be reached or returned something unusable."""


class LLMProvider(Protocol):
    """Chat model behind an interface: Ollama locally; Anthropic / Bedrock are drop-in alternatives."""

    name: str

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Return a JSON object that conforms to ``schema``."""
        ...
