#!/usr/bin/env python3
"""Run Workflow 03 meeting extraction from a JSON payload."""

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

from scripts.phase2.meeting_action_items import run_meeting_action_items  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run meeting extraction from payload file/json/stdin.")
    parser.add_argument("--payload-file", default=None, help="Path to payload JSON file.")
    parser.add_argument("--payload-json", default=None, help="Raw payload JSON string.")
    parser.add_argument("--payload-base64", default=None, help="Base64-encoded payload JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Skip SQLite/Qdrant writes and artifact creation.")
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


def payload_to_meeting_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    transcript = _first_non_empty(payload.get("transcript"), payload.get("content"), payload.get("notes"))
    if not transcript:
        raise ValueError("Payload requires non-empty 'transcript' (or alias: content/notes).")

    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("Payload field 'metadata' must be a JSON object if present.")

    meeting_title = _first_non_empty(
        payload.get("meeting_title"),
        payload.get("title"),
        metadata.get("title"),
    )

    source_channel = str(payload.get("source", metadata.get("source", "webhook"))).strip() or "webhook"
    source_ref = _first_non_empty(payload.get("source_ref"), metadata.get("source_ref"))

    tags_raw = payload.get("tags", metadata.get("tags", []))
    tags = _normalize_tags(tags_raw)

    max_retries_raw = payload.get("max_retries")
    max_retries = None if max_retries_raw is None else int(max_retries_raw)

    return {
        "transcript": transcript,
        "meeting_title": meeting_title,
        "source_channel": source_channel,
        "source_ref": source_ref,
        "tags": tags,
        "max_retries": max_retries,
    }


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_tags(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            tag = str(item).strip()
            if tag:
                tags.append(tag)
        return tags
    return []


def main() -> int:
    args = parse_args()
    try:
        payload = load_payload(args)
        kwargs = payload_to_meeting_kwargs(payload)
        result = run_meeting_action_items(**kwargs, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid payload or meeting execution failure: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
