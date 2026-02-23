#!/usr/bin/env python3
"""Normalize channel payloads and ingest via the Phase 1 ingestion backend."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.channel_adapters import normalize_payload  # noqa: E402
from scripts.phase1.ingest_from_payload import payload_to_requests  # noqa: E402
from scripts.phase1.ingestion_pipeline import ingest_request  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest a channel payload (webhook, bookmarklet, iOS share, Gmail forward)."
    )
    parser.add_argument(
        "--channel",
        required=True,
        choices=["webhook", "bookmarklet", "ios-share", "gmail-forward"],
        help="Input channel format to normalize.",
    )
    parser.add_argument("--payload-file", default=None, help="Path to JSON payload file.")
    parser.add_argument("--payload-json", default=None, help="Raw JSON payload string.")
    parser.add_argument("--payload-base64", default=None, help="Base64-encoded JSON payload.")
    parser.add_argument(
        "--normalize-only",
        action="store_true",
        help="Validate and print normalized payload without ingestion.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip DB/Qdrant writes.")
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
        raise ValueError("No payload provided. Use --payload-file, --payload-json, --payload-base64, or stdin.")
    return _parse_payload(stdin_payload)


def _parse_payload(payload_text: str) -> dict[str, Any]:
    payload = json.loads(payload_text)
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object.")
    return payload


def main() -> int:
    args = parse_args()
    try:
        raw_payload = load_payload(args)
        unified_payload = normalize_payload(raw_payload, channel=args.channel)
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid payload: {exc}", file=sys.stderr)
        return 2

    if args.normalize_only:
        print(
            json.dumps(
                {"channel": args.channel, "normalized_payload": unified_payload, "normalize_only": True},
                indent=2,
            )
        )
        return 0

    try:
        requests = payload_to_requests(unified_payload)
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

    summary = {
        "channel": args.channel,
        "normalized_payload": unified_payload,
        "ingested": results,
        "errors": errors,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
