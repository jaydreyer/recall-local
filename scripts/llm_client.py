"""
Recall.local LLM client.

Switch generation providers with RECALL_LLM_PROVIDER:
- ollama
- anthropic
- openai
- gemini

Embeddings currently use Ollama for local-first privacy.
"""

from __future__ import annotations

import importlib
import os
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "docker" / ".env")
load_dotenv(ROOT / "docker" / ".env.example")

__all__ = ["generate", "embed"]

PROVIDER = os.getenv("RECALL_LLM_PROVIDER", "ollama").strip().lower()
_LANGFUSE_CLIENT: Any | None = None
_LANGFUSE_INIT_ATTEMPTED = False


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def generate(
    prompt: str,
    system: str = "",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    trace_metadata: dict[str, Any] | None = None,
) -> str:
    """Generate text from the configured provider."""
    started = time.perf_counter()
    response_text: str | None = None
    error_text: str | None = None
    try:
        if PROVIDER == "ollama":
            response_text = _ollama_generate(prompt, system, temperature, max_tokens)
        elif PROVIDER == "anthropic":
            response_text = _anthropic_generate(prompt, system, temperature, max_tokens)
        elif PROVIDER == "openai":
            response_text = _openai_generate(prompt, system, temperature, max_tokens)
        elif PROVIDER == "gemini":
            response_text = _gemini_generate(prompt, system, temperature, max_tokens)
        else:
            raise ValueError(f"Unknown RECALL_LLM_PROVIDER '{PROVIDER}'")
        return response_text
    except Exception as exc:
        error_text = str(exc)
        raise
    finally:
        _emit_langfuse_trace(
            operation="generate",
            provider=PROVIDER,
            model=_active_generation_model(PROVIDER),
            input_text=prompt if not system else f"System:\n{system}\n\nPrompt:\n{prompt}",
            output_text=response_text,
            latency_ms=int((time.perf_counter() - started) * 1000),
            metadata=trace_metadata,
            error=error_text,
        )


def embed(text: str, trace_metadata: dict[str, Any] | None = None) -> list[float]:
    """Generate embeddings using Ollama."""
    started = time.perf_counter()
    response_vector: list[float] | None = None
    error_text: str | None = None
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    retries = _int_env("RECALL_EMBED_RETRIES", default=3, minimum=1)
    backoff_seconds = _float_env("RECALL_EMBED_BACKOFF_SECONDS", default=1.5, minimum=0.0)
    max_chars = _int_env("RECALL_EMBED_MAX_CHARS", default=3500, minimum=256)
    min_chars = _int_env("RECALL_EMBED_MIN_CHARS", default=384, minimum=128)

    try:
        prompt = _sanitize_embed_text(text)
        if len(prompt) > max_chars:
            prompt = prompt[:max_chars]

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response_vector = _ollama_embed(host=host, model=model, prompt=prompt)
                return response_vector
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if _is_http_status_error(exc, status_code=500) and len(prompt) > min_chars:
                    # Some extracted PDF chunks can trigger Ollama embedding failures;
                    # progressively shrink the prompt and retry.
                    next_len = max(min_chars, int(len(prompt) * 0.7))
                    prompt = prompt[:next_len]
                if attempt >= retries:
                    break
                time.sleep(backoff_seconds * attempt)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Embedding call failed without an error response")
    except Exception as exc:
        error_text = str(exc)
        raise
    finally:
        _emit_langfuse_trace(
            operation="embed",
            provider="ollama",
            model=model,
            input_text=text,
            output_text=f"embedding_dim={len(response_vector) if response_vector is not None else 0}",
            latency_ms=int((time.perf_counter() - started) * 1000),
            metadata=trace_metadata,
            error=error_text,
        )


def _ollama_generate(prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
    retries = _int_env("RECALL_GENERATE_RETRIES", default=3, minimum=1)
    backoff_seconds = _float_env("RECALL_GENERATE_BACKOFF_SECONDS", default=1.5, minimum=0.0)
    timeout_seconds = _float_env("RECALL_OLLAMA_GENERATE_TIMEOUT_SECONDS", default=180.0, minimum=30.0)
    context_window = _int_env("RECALL_OLLAMA_NUM_CTX", default=8192, minimum=2048)
    max_output_tokens = max(1, max_tokens)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": context_window,
            "num_predict": max_output_tokens,
        },
    }
    if system:
        payload["system"] = system

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(
                f"{host}/api/generate",
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return str(response.json()["response"]).strip()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(backoff_seconds * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Generation call failed without an error response")


def _ollama_embed(*, host: str, model: str, prompt: str) -> list[float]:
    """Call Ollama embedding endpoint with forward/backward compatibility."""
    candidates = (
        ("/api/embed", {"model": model, "input": prompt}),
        ("/api/embeddings", {"model": model, "prompt": prompt}),
    )

    last_error: Exception | None = None
    for index, (path, payload) in enumerate(candidates):
        try:
            response = httpx.post(
                f"{host}{path}",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            return _extract_ollama_embedding(response.json())
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            is_not_found = _is_http_status_error(exc, status_code=404)
            has_fallback = index < len(candidates) - 1
            if is_not_found and has_fallback:
                continue
            break

    if last_error is not None:
        raise last_error
    raise RuntimeError("Embedding call failed without an error response")


def _extract_ollama_embedding(payload: Any) -> list[float]:
    if isinstance(payload, dict):
        embedding = payload.get("embedding")
        if isinstance(embedding, list) and embedding:
            return [float(value) for value in embedding]

        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            first = embeddings[0]
            if isinstance(first, list) and first:
                return [float(value) for value in first]

    raise RuntimeError("Ollama embedding response missing embedding vector.")


def _generation_retry_config() -> tuple[int, float]:
    retries = _int_env("RECALL_GENERATE_RETRIES", default=3, minimum=1)
    backoff_seconds = _float_env("RECALL_GENERATE_BACKOFF_SECONDS", default=1.5, minimum=0.0)
    return retries, backoff_seconds


def _is_retryable_generation_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 408 or status_code == 429 or status_code >= 500
    return False


def _post_json_with_retries(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> httpx.Response:
    retries, backoff_seconds = _generation_retry_config()
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries or not _is_retryable_generation_error(exc):
                raise
            time.sleep(backoff_seconds * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Generation call failed without an error response")


def _anthropic_generate(prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    api_key = _require_env("ANTHROPIC_API_KEY")
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system

    response = _post_json_with_retries(
        url="https://api.anthropic.com/v1/messages",
        headers=headers,
        payload=payload,
        timeout_seconds=120,
    )
    content = response.json().get("content", [])
    if not content:
        raise RuntimeError("Anthropic response missing content")
    return content[0].get("text", "").strip()


def _openai_generate(prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    api_key = _require_env("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = _post_json_with_retries(
        url="https://api.openai.com/v1/chat/completions",
        headers=headers,
        payload={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout_seconds=120,
    )
    return response.json()["choices"][0]["message"]["content"].strip()


def _gemini_generate(prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    api_key = _require_env("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    text = prompt if not system else f"System instructions:\n{system}\n\nUser prompt:\n{prompt}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    response = _post_json_with_retries(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        payload=payload,
        timeout_seconds=120,
    )

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini response missing candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini response missing parts")
    return "\n".join(part.get("text", "") for part in parts).strip()


def _active_generation_model(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    if normalized == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if normalized == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")


def _sanitize_embed_text(text: str) -> str:
    cleaned_chars: list[str] = []
    for ch in text:
        codepoint = ord(ch)
        if codepoint == 0 or 0xD800 <= codepoint <= 0xDFFF:
            continue
        if codepoint < 32 and ch not in {"\n", "\t", "\r"}:
            cleaned_chars.append(" ")
            continue
        cleaned_chars.append(ch)
    cleaned = "".join(cleaned_chars).strip()
    return cleaned or "empty"


def _int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(parsed, minimum)


def _float_env(name: str, *, default: float, minimum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return max(parsed, minimum)


def _is_http_status_error(exc: Exception, *, status_code: int) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == status_code


def _emit_langfuse_trace(
    *,
    operation: str,
    provider: str,
    model: str,
    input_text: str,
    output_text: str | None,
    latency_ms: int,
    metadata: dict[str, Any] | None,
    error: str | None,
) -> None:
    if not _langfuse_enabled():
        return

    client = _get_langfuse_client()
    if client is None:
        return

    trace_name = f"recall.{operation}"
    trace_metadata: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "latency_ms": latency_ms,
    }
    if metadata:
        trace_metadata.update(metadata)
    if error:
        trace_metadata["error"] = error

    input_preview = input_text[:4000]
    output_preview = (output_text or "")[:4000]

    try:
        trace = client.trace(name=trace_name, metadata=trace_metadata)
        generation_kwargs = {
            "name": trace_name,
            "model": model,
            "input": input_preview,
            "output": output_preview,
            "metadata": trace_metadata,
        }
        if hasattr(trace, "generation"):
            trace.generation(**generation_kwargs)
        elif hasattr(client, "generation"):
            client.generation(**generation_kwargs)
        if hasattr(client, "flush"):
            client.flush()
    except Exception:
        return


def _langfuse_enabled() -> bool:
    raw_enabled = os.getenv("RECALL_LANGFUSE_ENABLED", "").strip().lower()
    if raw_enabled in {"1", "true", "yes", "on"}:
        return True
    if raw_enabled in {"0", "false", "no", "off"}:
        return False
    # If not explicitly set, allow when standard Langfuse keys are present.
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    )


def _get_langfuse_client():
    global _LANGFUSE_CLIENT
    global _LANGFUSE_INIT_ATTEMPTED

    if _LANGFUSE_INIT_ATTEMPTED:
        return _LANGFUSE_CLIENT
    _LANGFUSE_INIT_ATTEMPTED = True

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    if not public_key or not secret_key:
        return None

    try:
        langfuse_module = importlib.import_module("langfuse")
    except Exception:
        return None

    Langfuse = getattr(langfuse_module, "Langfuse", None)
    if Langfuse is None:
        return None

    host = os.getenv("LANGFUSE_HOST", "").strip() or None
    try:
        _LANGFUSE_CLIENT = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except Exception:
        _LANGFUSE_CLIENT = None
    return _LANGFUSE_CLIENT


def main() -> int:
    print(f"Provider: {PROVIDER}")
    print("Testing generation...")
    message = generate("Say 'Recall.local is online' and nothing else.")
    print(f"Response: {message}")

    print("\nTesting embedding...")
    vector = embed("test embedding")
    print(f"Embedding dimension: {len(vector)}")
    print("\nAll systems go.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
