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

import os
from pathlib import Path
from typing import List

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "docker" / ".env")

PROVIDER = os.getenv("RECALL_LLM_PROVIDER", "ollama").strip().lower()


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def generate(prompt: str, system: str = "", temperature: float = 0.3, max_tokens: int = 4096) -> str:
    """Generate text from the configured provider."""
    if PROVIDER == "ollama":
        return _ollama_generate(prompt, system, temperature)
    if PROVIDER == "anthropic":
        return _anthropic_generate(prompt, system, temperature, max_tokens)
    if PROVIDER == "openai":
        return _openai_generate(prompt, system, temperature, max_tokens)
    if PROVIDER == "gemini":
        return _gemini_generate(prompt, system, temperature, max_tokens)
    raise ValueError(f"Unknown RECALL_LLM_PROVIDER '{PROVIDER}'")


def embed(text: str) -> List[float]:
    """Generate embeddings using Ollama."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

    response = httpx.post(
        f"{host}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def _ollama_generate(prompt: str, system: str, temperature: float) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3:8b")

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    if system:
        payload["system"] = system

    response = httpx.post(f"{host}/api/generate", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["response"].strip()


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

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
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

    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _gemini_generate(prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    api_key = _require_env("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    text = prompt if not system else f"System instructions:\n{system}\n\nUser prompt:\n{prompt}"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        },
    }

    response = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": api_key},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini response missing candidates")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise RuntimeError("Gemini response missing parts")
    return "\n".join(part.get("text", "") for part in parts).strip()


if __name__ == "__main__":
    print(f"Provider: {PROVIDER}")
    print("Testing generation...")
    message = generate("Say 'Recall.local is online' and nothing else.")
    print(f"Response: {message}")

    print("\nTesting embedding...")
    vector = embed("test embedding")
    print(f"Embedding dimension: {len(vector)}")
    print("\nAll systems go.")
