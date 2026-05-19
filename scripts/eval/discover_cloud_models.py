#!/usr/bin/env python3
"""Discover callable cloud evaluator models from the current runtime credentials."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = ROOT / "data" / "artifacts" / "evals" / "cloud-model-discovery"
PROBE_PROMPT = 'Return exactly this JSON object and nothing else: {"ok": true}'


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")


def _csv_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        detail = ""
        try:
            payload = exc.response.json()
            if isinstance(payload, dict):
                message = payload.get("error", {}).get("message") or payload.get("message")
                detail = f": {message}" if message else ""
        except Exception:  # noqa: BLE001
            detail = ""
        return f"HTTP {status}{detail}"
    return str(exc)


def _dedupe(values: list[str]) -> list[str]:
    return [item for item in dict.fromkeys(value.strip() for value in values) if item]


def _openai_list_models(api_key: str) -> tuple[list[str], str | None]:
    try:
        response = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return [], _safe_error(exc)
    payload = response.json()
    ids = sorted(str(item.get("id") or "") for item in payload.get("data", []) if isinstance(item, dict))
    return [item for item in ids if item], None


def _anthropic_list_models(api_key: str) -> tuple[list[str], str | None]:
    try:
        response = httpx.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=30,
        )
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        return [], _safe_error(exc)
    payload = response.json()
    ids = sorted(str(item.get("id") or "") for item in payload.get("data", []) if isinstance(item, dict))
    return [item for item in ids if item], None


def _candidate_openai_models(listed_models: list[str], requested: list[str]) -> list[str]:
    preferred = [
        os.getenv("OPENAI_MODEL", "").strip(),
        *_csv_env("RECALL_PHASE6_EVAL_OPENAI_MODELS"),
        *requested,
    ]
    families = ("gpt-", "o1", "o3", "o4")
    listed = [model for model in listed_models if model.startswith(families)]
    return _dedupe([*preferred, *listed])[:40]


def _candidate_anthropic_models(listed_models: list[str], requested: list[str]) -> list[str]:
    preferred = [
        os.getenv("ANTHROPIC_MODEL", "").strip(),
        *_csv_env("RECALL_PHASE6_EVAL_ANTHROPIC_MODELS"),
        *requested,
    ]
    return _dedupe([*preferred, *listed_models])[:40]


def _probe_openai_model(api_key: str, model: str) -> dict[str, Any]:
    started = time.perf_counter()
    if model.startswith("gpt-5"):
        return _probe_openai_responses_model(api_key=api_key, model=model, started=started)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": 32,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    endpoint = "chat.completions"
    try:
        response = _post_openai_chat(api_key=api_key, payload=payload)
        content = str(response.json().get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        json.loads(content)
        ok = True
        error = None
    except Exception as exc:  # noqa: BLE001
        ok = False
        error = _safe_error(exc)
        content = ""
    return {
        "model": model,
        "provider": "openai",
        "endpoint": endpoint,
        "callable": ok,
        "structured_json": ok,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
        "response_preview": content[:120],
    }


def _probe_openai_responses_model(*, api_key: str, model: str, started: float) -> dict[str, Any]:
    try:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "input": PROBE_PROMPT,
                "text": {"format": {"type": "json_object"}},
                "reasoning": {"effort": "low"},
                "max_output_tokens": 1024,
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "incomplete":
            raise RuntimeError(f"incomplete response: {payload.get('incomplete_details') or {}}")
        content = _extract_openai_responses_text(payload)
        json.loads(content)
        ok = True
        error = None
    except Exception as exc:  # noqa: BLE001
        ok = False
        error = _safe_error(exc)
        content = ""
    return {
        "model": model,
        "provider": "openai",
        "endpoint": "responses",
        "callable": ok,
        "structured_json": ok,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
        "response_preview": content[:120],
    }


def _extract_openai_responses_text(payload: dict[str, Any]) -> str:
    output_text = str(payload.get("output_text") or "").strip()
    if output_text:
        return output_text
    parts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"}:
                parts.append(str(content.get("text") or ""))
    return "".join(parts).strip()


def _post_openai_chat(*, api_key: str, payload: dict[str, Any]) -> httpx.Response:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        message = ""
        try:
            body = exc.response.json()
            if isinstance(body, dict):
                message = str(body.get("error", {}).get("message") or "")
        except Exception:  # noqa: BLE001
            message = ""
        if exc.response.status_code != 400 or "max_tokens" not in message:
            raise
        fallback_payload = dict(payload)
        fallback_payload["max_completion_tokens"] = fallback_payload.pop("max_tokens", 32)
        fallback_payload.pop("temperature", None)
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=fallback_payload,
            timeout=60,
        )
        response.raise_for_status()
        return response


def _probe_anthropic_model(api_key: str, model: str) -> dict[str, Any]:
    started = time.perf_counter()
    payload = {
        "model": model,
        "max_tokens": 32,
        "temperature": 0,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
    }
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        content = str(response.json().get("content", [{}])[0].get("text") or "").strip()
        json.loads(content)
        ok = True
        error = None
    except Exception as exc:  # noqa: BLE001
        ok = False
        error = _safe_error(exc)
        content = ""
    return {
        "model": model,
        "provider": "anthropic",
        "endpoint": "messages",
        "callable": ok,
        "structured_json": ok,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "error": error,
        "response_preview": content[:120],
    }


def discover(*, requested_models: list[str], probe: bool, max_probe_models: int) -> dict[str, Any]:
    _load_dotenv_if_available()
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    providers: dict[str, Any] = {}

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_key:
        listed, list_error = _openai_list_models(openai_key)
        candidates = _candidate_openai_models(listed, requested_models)
        probes = [_probe_openai_model(openai_key, model) for model in candidates[:max_probe_models]] if probe else []
        providers["openai"] = {
            "credentials_present": True,
            "list_error": list_error,
            "listed_model_count": len(listed),
            "candidate_models": candidates,
            "probes": probes,
            "callable_models": [item["model"] for item in probes if item["callable"]],
        }
    else:
        providers["openai"] = {"credentials_present": False, "list_error": "OPENAI_API_KEY is not set"}

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if anthropic_key:
        listed, list_error = _anthropic_list_models(anthropic_key)
        candidates = _candidate_anthropic_models(listed, requested_models)
        probes = (
            [_probe_anthropic_model(anthropic_key, model) for model in candidates[:max_probe_models]] if probe else []
        )
        providers["anthropic"] = {
            "credentials_present": True,
            "list_error": list_error,
            "listed_model_count": len(listed),
            "candidate_models": candidates,
            "probes": probes,
            "callable_models": [item["model"] for item in probes if item["callable"]],
        }
    else:
        providers["anthropic"] = {"credentials_present": False, "list_error": "ANTHROPIC_API_KEY is not set"}

    return {
        "generated_at": generated_at,
        "probe_enabled": probe,
        "max_probe_models": max_probe_models,
        "providers": providers,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover callable OpenAI and Anthropic models for job evaluation.")
    parser.add_argument(
        "--model", action="append", default=[], help="Specific model ID to include in probe candidates."
    )
    parser.add_argument(
        "--no-probe", action="store_true", help="Only list candidate models; do not make generation calls."
    )
    parser.add_argument("--max-probe-models", type=int, default=8, help="Maximum models per provider to probe.")
    parser.add_argument(
        "--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Directory for discovery JSON artifacts."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print discovery only; do not write an artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = discover(
        requested_models=args.model,
        probe=not args.no_probe,
        max_probe_models=max(args.max_probe_models, 1),
    )
    if not args.dry_run:
        artifact_dir = Path(args.artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{_now_stamp()}_cloud_model_discovery.json"
        artifact_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["artifact_path"] = str(artifact_path)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
