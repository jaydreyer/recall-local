#!/usr/bin/env python3
"""Run Workflow 02 cited RAG from a JSON payload."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.rag_query import run_rag_query  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cited RAG from payload file/json/stdin.")
    parser.add_argument("--payload-file", default=None, help="Path to payload JSON file.")
    parser.add_argument("--payload-json", default=None, help="Raw payload JSON string.")
    parser.add_argument("--payload-base64", default=None, help="Base64-encoded payload JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Skip SQLite writes and artifact file creation.")
    return parser.parse_args()


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_base64:
        decoded = base64.b64decode(args.payload_base64.encode("utf-8")).decode("utf-8")
        return _parse_payload(decoded)

    if args.payload_json:
        return _parse_payload(args.payload_json)

    if args.payload_file:
        payload_text = Path(args.payload_file).read_text(encoding="utf-8")
        return _parse_payload(payload_text)

    stdin_payload = sys.stdin.read().strip()
    if not stdin_payload:
        raise ValueError("No payload provided. Use --payload-file, --payload-json, or stdin.")
    return _parse_payload(stdin_payload)


def _parse_payload(payload_text: str) -> dict[str, Any]:
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object.")
    return payload


def main() -> int:
    args = parse_args()
    try:
        payload = load_payload(args)
        query = str(payload.get("query", "")).strip()
        if not query:
            raise ValueError("Payload requires non-empty 'query'.")

        top_k = payload.get("top_k")
        min_score = payload.get("min_score")
        max_retries = payload.get("max_retries")
        mode = payload.get("mode")
        filter_tags = _normalize_filter_tags(payload.get("filter_tags"))

        if top_k is not None:
            top_k = int(top_k)
        if min_score is not None:
            min_score = float(min_score)
        if max_retries is not None:
            max_retries = int(max_retries)

        result = run_rag_query(
            query,
            top_k=top_k,
            min_score=min_score,
            max_retries=max_retries,
            filter_tags=filter_tags,
            mode=str(mode) if mode is not None else None,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid payload or query execution failure: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


def _normalize_filter_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            tag = str(item).strip()
            if tag:
                tags.append(tag)
        return tags
    raise ValueError("Payload filter_tags must be an array or comma-separated string.")


if __name__ == "__main__":
    raise SystemExit(main())
