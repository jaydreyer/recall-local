#!/usr/bin/env python3
"""Pytest coverage for top-level LLM client dispatch and retry behavior."""

from __future__ import annotations

import httpx
import pytest

from scripts import llm_client


def _http_status_error(status_code: int, url: str) -> httpx.HTTPStatusError:
    """Build an HTTP status error with a real request/response pair."""
    request = httpx.Request("POST", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"status={status_code}", request=request, response=response)


def test_generate_dispatches_to_configured_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the module-level provider switch to route generation calls."""
    trace_calls: list[dict[str, object]] = []
    monkeypatch.setattr(llm_client, "PROVIDER", "openai")
    monkeypatch.setattr(llm_client, "_openai_generate", lambda prompt, system, temperature, max_tokens: "generated")
    monkeypatch.setattr(llm_client, "_emit_langfuse_trace", lambda **kwargs: trace_calls.append(kwargs))

    result = llm_client.generate("hello", system="system prompt", trace_metadata={"test": True})

    assert result == "generated"
    assert trace_calls and trace_calls[0]["provider"] == "openai"
    assert trace_calls[0]["output_text"] == "generated"


def test_generate_emits_error_trace_when_provider_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trace failures too so debugging keeps the same observability shape."""
    trace_calls: list[dict[str, object]] = []
    monkeypatch.setattr(llm_client, "PROVIDER", "unknown-provider")
    monkeypatch.setattr(llm_client, "_emit_langfuse_trace", lambda **kwargs: trace_calls.append(kwargs))

    with pytest.raises(ValueError, match="Unknown RECALL_LLM_PROVIDER"):
        llm_client.generate("hello")

    assert trace_calls and "Unknown RECALL_LLM_PROVIDER" in str(trace_calls[0]["error"])


def test_embed_retries_with_shorter_prompt_after_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shrink long prompt text when Ollama returns a retryable server error."""
    prompts_seen: list[str] = []

    def fake_embed(*, host: str, model: str, prompt: str) -> list[float]:
        prompts_seen.append(prompt)
        if len(prompts_seen) == 1:
            raise _http_status_error(500, f"{host}/api/embed")
        return [0.1, 0.2]

    monkeypatch.setenv("RECALL_EMBED_RETRIES", "2")
    monkeypatch.setenv("RECALL_EMBED_BACKOFF_SECONDS", "0")
    monkeypatch.setenv("RECALL_EMBED_MAX_CHARS", "1000")
    monkeypatch.setenv("RECALL_EMBED_MIN_CHARS", "200")
    monkeypatch.setattr(llm_client, "_ollama_embed", fake_embed)
    monkeypatch.setattr(llm_client, "_emit_langfuse_trace", lambda **kwargs: None)
    monkeypatch.setattr(llm_client.time, "sleep", lambda seconds: None)

    embedding = llm_client.embed("word " * 250)

    assert embedding == [0.1, 0.2]
    assert len(prompts_seen) == 2
    assert len(prompts_seen[1]) < len(prompts_seen[0])
