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

from scripts.phase1.group_model import normalize_group
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
    metadata = dict(metadata)

    title = metadata.get("title") or payload.get("title")
    group = _normalize_group(payload.get("group"), metadata.get("group"))
    metadata["group"] = group
    tags = _normalize_tags(payload.get("tags"), metadata.get("tags"))
    replace_existing = _coerce_bool(
        payload.get("replace_existing", metadata.get("replace_existing", False))
    )
    source_key = _first_non_empty(
        payload.get("source_key"),
        payload.get("canonical_source_key"),
        metadata.get("source_key"),
        metadata.get("canonical_source_key"),
        metadata.get("source_identity"),
    )

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
                group=group,
                tags=[str(tag) for tag in tags],
                metadata=metadata,
                replace_existing=replace_existing,
                source_key=source_key,
            )
        ]

    if source_type == "email":
        return _email_payload_requests(
            content=content,
            source_channel=source_channel,
            title=title,
            group=group,
            tags=[str(tag) for tag in tags],
            metadata=metadata,
            replace_existing=replace_existing,
            source_key=source_key,
        )

    raise ValueError(f"Unsupported payload type: {source_type}")


def _email_payload_requests(
    *,
    content: Any,
    source_channel: str,
    title: str | None,
    group: str,
    tags: list[str],
    metadata: dict[str, Any],
    replace_existing: bool,
    source_key: str | None,
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
            body_source_key = source_key or message_id or None
            requests.append(
                IngestRequest(
                    source_type="email",
                    content=body,
                    source_channel=source_channel,
                    title=title or subject or "Email body",
                    group=group,
                    tags=tags,
                    metadata=base_metadata,
                    replace_existing=replace_existing,
                    source_key=body_source_key,
                )
            )

        for attachment_path in attachment_paths:
            requests.append(
                IngestRequest(
                    source_type="file",
                    content=str(attachment_path),
                    source_channel=source_channel,
                    title=None,
                    group=group,
                    tags=tags,
                    metadata=base_metadata,
                    replace_existing=replace_existing,
                    source_key=None,
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
                    group=group,
                    tags=tags,
                    metadata=metadata,
                    replace_existing=replace_existing,
                    source_key=source_key,
                )
            )

    if not requests:
        raise ValueError("Email payload had no body or attachment_paths to ingest.")

    return requests


def _normalize_tags(primary: Any, fallback: Any) -> list[str]:
    value = primary if primary is not None else fallback
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            tag = str(item).strip()
            if tag:
                tags.append(tag)
        return tags
    if value in {None, ""}:
        return []
    raise ValueError("Payload tags must be a list or comma-separated string.")


def _coerce_bool(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    raise ValueError("replace_existing must be a boolean-like value.")


def _normalize_group(primary: Any, fallback: Any) -> str:
    value = primary if primary is not None else fallback
    return normalize_group(value)


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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
