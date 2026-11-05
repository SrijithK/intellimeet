from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from app.llm.base import LLMError, StreamChunk


class OllamaProvider:
    """Local models via Ollama's /api/chat: schema-constrained JSON, or streamed text."""

    name = "ollama"

    def __init__(self, base_url: str, model: str, num_ctx: int = 8192, timeout: float = 300.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        # Ollama's default context is small and it truncates silently, so always set it explicitly.
        self.num_ctx = num_ctx
        self.timeout = timeout

    def complete_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            response = httpx.post(f"{self.base_url}/api/chat", json=body, timeout=self.timeout)
            response.raise_for_status()
            content = response.json()["message"]["content"]
            result = json.loads(content)
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"Ollama returned {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise LLMError(f"Ollama returned an unexpected response: {exc}") from exc
        if not isinstance(result, dict):
            raise LLMError("Ollama returned JSON that is not an object.")
        return result

    def stream_chat(self, system: str, user: str) -> Iterator[StreamChunk]:
        body = {
            "model": self.model,
            "stream": True,
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            with httpx.stream("POST", f"{self.base_url}/api/chat", json=body, timeout=self.timeout) as response:
                if response.status_code >= 400:
                    response.read()
                    raise LLMError(f"Ollama returned {response.status_code}: {response.text[:200]}")
                for line in response.iter_lines():  # newline-delimited JSON
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise LLMError(f"Ollama error: {data['error']}")
                    text = data.get("message", {}).get("content", "")
                    if data.get("done"):
                        yield StreamChunk(
                            text=text,
                            done=True,
                            prompt_tokens=data.get("prompt_eval_count"),
                            output_tokens=data.get("eval_count"),
                        )
                        return
                    if text:
                        yield StreamChunk(text=text)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach Ollama at {self.base_url}: {exc}") from exc
        except ValueError as exc:
            raise LLMError(f"Ollama returned an unexpected response: {exc}") from exc
