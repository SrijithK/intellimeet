import json
import os

import httpx
import pytest

from app.llm import LLMError
from app.llm.ollama import OllamaProvider
from app.parsers import parse_transcript
from app.services.extraction import Extractor
from tests.test_retrieval import SEED_DIR

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def _respond(monkeypatch, handler):
    def fake_post(url, json, timeout):  # noqa: A002 - mirrors httpx.post signature
        return handler(httpx.Request("POST", url, json=json))

    monkeypatch.setattr(httpx, "post", fake_post)


def test_sends_schema_context_and_parses_json(monkeypatch):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"ok": true}'}}, request=request)

    _respond(monkeypatch, handler)
    result = OllamaProvider("http://ollama:11434/", "llama3.1", num_ctx=4096).complete_json("sys", "user", SCHEMA)

    assert result == {"ok": True}
    assert seen["format"] == SCHEMA
    assert seen["options"] == {"temperature": 0, "num_ctx": 4096}
    assert [m["role"] for m in seen["messages"]] == ["system", "user"]


@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(404, text="model 'llama3.1' not found"), "404"),
        (httpx.Response(200, json={"message": {"content": "not json"}}), "unexpected response"),
        (httpx.Response(200, json={"message": {"content": "[1, 2]"}}), "not an object"),
    ],
)
def test_errors_are_wrapped(monkeypatch, response, message):
    def handler(request):
        response.request = request
        return response

    _respond(monkeypatch, handler)
    with pytest.raises(LLMError, match=message):
        OllamaProvider("http://ollama:11434", "llama3.1").complete_json("sys", "user", SCHEMA)


def test_unreachable_server_raises_llm_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused")

    _respond(monkeypatch, handler)
    with pytest.raises(LLMError, match="Could not reach Ollama"):
        OllamaProvider("http://ollama:11434", "llama3.1").complete_json("sys", "user", SCHEMA)


@pytest.mark.skipif(os.getenv("RUN_LLM_TESTS") != "1", reason="set RUN_LLM_TESTS=1 to call the local Ollama model")
def test_live_extraction_on_seed_meeting():
    path = SEED_DIR / "product-launch-planning.txt"
    meeting = parse_transcript(path.name, path.read_text())
    llm = OllamaProvider(os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), os.getenv("OLLAMA_MODEL", "llama3.1"))

    result = Extractor(llm).extract(meeting)

    assert any("17" in d.text for d in result.decisions)
    owners = {a.owner for a in result.action_items}
    assert {"Dana", "Marcus", "Leo"} <= owners
