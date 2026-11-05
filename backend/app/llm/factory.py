from __future__ import annotations

from typing import Optional

from app.config import settings
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider

_llm: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    """The configured provider (LLM_PROVIDER). Only "ollama" exists so far."""
    global _llm
    if _llm is None:
        if settings.llm_provider != "ollama":
            raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r} (supported: 'ollama')")
        _llm = OllamaProvider(settings.ollama_base_url, settings.ollama_model, num_ctx=settings.ollama_num_ctx)
    return _llm
