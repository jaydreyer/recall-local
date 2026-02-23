#!/usr/bin/env python3
"""Ingest unified webhook payloads for Recall.local Workflow 01."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.ingestion_pipeline import IngestRequest, ingest_request  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a Recall.local webhook payload.")
    parser.add_argument("--payload-file", default=None, help="Path to JSON payload file.")
    parser.add_argument("--payload-json", default=None, help="Raw JSON payload string.")
    parser.add_argument("--dry-run", action="store_true", help="Skip DB/Qdrant writes.")
    return parser.parse_args()


def load_payload(args: argparse.Namespace) -> dict[str, Any]:
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


def payload_to_requests(payload: dict[str, Any]) -> list[IngestRequest]:
    source_type = str(payload.get("type", "")).strip().lower()
    if not source_type:
        raise ValueError("Payload requires a non-empty 'type'.")

    source_channel = str(payload.get("source", "webhook")).strip() or "webhook"
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("Payload field 'metadata' must be a JSON object if present.")

    title = metadata.get("title")
    tags = metadata.get("tags") or []
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    if not isinstance(tags, list):
        raise ValueError("Payload metadata.tags must be a list or comma-separated string.")

    content = payload.get("content")
    if source_type in {"url", "text", "file", "gdoc"}:
        if content is None:
            raise ValueError("Payload requires 'content' for this type.")
        return [
            IngestRequest(
                source_type=source_type,
                content=content,
                source_channel=source_channel,
                title=title,
                tags=[str(tag) for tag in tags],
                metadata=metadata,
            )
        ]

    if source_type == "email":
        return _email_payload_requests(
            content=content,
            source_channel=source_channel,
            title=title,
            tags=[str(tag) for tag in tags],
            metadata=metadata,
        )

    raise ValueError(f"Unsupported payload type: {source_type}")


def _email_payload_requests(
    *,
    content: Any,
    source_channel: str,
    title: str | None,
    tags: list[str],
    metadata: dict[str, Any],
) -> list[IngestRequest]:
    requests: list[IngestRequest] = []

    if isinstance(content, dict):
        body = str(content.get("body", "")).strip()
        subject = str(content.get("subject", "")).strip()
        message_id = str(content.get("message_id", "")).strip()
        attachment_paths = content.get("attachment_paths") or []
        if not isinstance(attachment_paths, list):
            raise ValueError("email attachment_paths must be a list.")

        base_metadata = dict(metadata)
        if subject and "email_subject" not in base_metadata:
            base_metadata["email_subject"] = subject
        if message_id and "email_message_id" not in base_metadata:
            base_metadata["email_message_id"] = message_id

        if body:
            requests.append(
                IngestRequest(
                    source_type="email",
                    content=body,
                    source_channel=source_channel,
                    title=title or subject or "Email body",
                    tags=tags,
                    metadata=base_metadata,
                )
            )

        for attachment_path in attachment_paths:
            requests.append(
                IngestRequest(
                    source_type="file",
                    content=str(attachment_path),
                    source_channel=source_channel,
                    title=None,
                    tags=tags,
                    metadata=base_metadata,
                )
            )
    else:
        body = str(content or "").strip()
        if body:
            requests.append(
                IngestRequest(
                    source_type="email",
                    content=body,
                    source_channel=source_channel,
                    title=title or "Email body",
                    tags=tags,
                    metadata=metadata,
                )
            )

    if not requests:
        raise ValueError("Email payload had no body or attachment_paths to ingest.")

    return requests


def main() -> int:
    args = parse_args()
    try:
        payload = load_payload(args)
        requests = payload_to_requests(payload)
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid payload: {exc}", file=sys.stderr)
        return 2

    results = []
    errors = []
    for index, request in enumerate(requests):
        try:
            result = ingest_request(request, dry_run=args.dry_run)
            results.append(asdict(result))
        except Exception as exc:  # noqa: BLE001
            errors.append({"request_index": index, "source_type": request.source_type, "error": str(exc)})

    summary = {"ingested": results, "errors": errors, "dry_run": args.dry_run}
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
