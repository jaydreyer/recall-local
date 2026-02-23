#!/usr/bin/env python3
"""Verify Workflow 03 bridge endpoint and persisted outputs."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Workflow 03 meeting bridge contract.")
    parser.add_argument(
        "--bridge-url",
        default="http://localhost:8090/meeting/action-items",
        help="Workflow 03 bridge endpoint URL.",
    )
    parser.add_argument(
        "--payload-file",
        default=str(ROOT / "n8n" / "workflows" / "payload_examples" / "meeting_action_items_payload_example.json"),
        help="Meeting payload JSON file.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Call endpoint with dry_run=true.")
    parser.add_argument("--timeout-seconds", type=float, default=90.0, help="HTTP timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    payload_path = Path(args.payload_file)
    if not payload_path.exists():
        print(f"Payload file missing: {payload_path}", file=sys.stderr)
        return 2

    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("Payload file must contain a JSON object.", file=sys.stderr)
        return 2

    url = args.bridge_url
    if args.dry_run:
        query = urlencode({"dry_run": "true"})
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"

    try:
        response = httpx.post(url, json=payload, timeout=args.timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        print(f"HTTP request failed: {exc}", file=sys.stderr)
        return 1

    if response.status_code != 200:
        print(f"Workflow 03 endpoint returned HTTP {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        return 1

    try:
        data = response.json()
    except ValueError as exc:
        print(f"Response is not valid JSON: {exc}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        return 1

    if str(data.get("workflow")) != "workflow_03_meeting_action_items":
        print("Unexpected workflow value in response.", file=sys.stderr)
        print(json.dumps(data, indent=2), file=sys.stderr)
        return 1

    result = data.get("result")
    if not isinstance(result, dict):
        print("Response missing object field 'result'.", file=sys.stderr)
        print(json.dumps(data, indent=2), file=sys.stderr)
        return 1

    errors = _validate_result_contract(result)
    if errors:
        print("Workflow 03 result contract validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(json.dumps(result, indent=2), file=sys.stderr)
        return 1

    audit = result["audit"]
    checks: dict[str, Any] = {
        "http_status": response.status_code,
        "workflow": data.get("workflow"),
        "run_id": audit.get("run_id"),
        "dry_run": bool(audit.get("dry_run")),
    }

    if not args.dry_run:
        artifact_path = str(audit.get("artifact_path") or "").strip()
        if not artifact_path:
            print("Missing artifact_path in non-dry-run response.", file=sys.stderr)
            return 1
        artifact_exists = Path(artifact_path).exists()
        if not artifact_exists:
            print(f"Artifact path not found on disk: {artifact_path}", file=sys.stderr)
            return 1
        checks["artifact_path"] = artifact_path
        checks["artifact_exists"] = artifact_exists

        db_path = Path(os.getenv("RECALL_DB_PATH", str(ROOT / "data" / "recall.db")))
        run_id = str(audit.get("run_id") or "").strip()
        if run_id and db_path.exists():
            checks["sqlite_run_present"] = _sqlite_has_run(db_path=db_path, run_id=run_id)
        else:
            checks["sqlite_run_present"] = False

    print(json.dumps({"ok": True, "checks": checks}, indent=2))
    return 0


def _validate_result_contract(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(result.get("meeting_title"), str) or not str(result.get("meeting_title")).strip():
        errors.append("meeting_title must be non-empty string")
    if not isinstance(result.get("summary"), str) or not str(result.get("summary")).strip():
        errors.append("summary must be non-empty string")

    for field in ("decisions", "risks", "follow_ups"):
        value = result.get(field)
        if not isinstance(value, list):
            errors.append(f"{field} must be an array")
            continue
        if any(not isinstance(item, str) for item in value):
            errors.append(f"{field} must contain only strings")

    action_items = result.get("action_items")
    if not isinstance(action_items, list):
        errors.append("action_items must be an array")
    else:
        for index, item in enumerate(action_items):
            if not isinstance(item, dict):
                errors.append(f"action_items[{index}] must be an object")
                continue
            for key in ("owner", "due_date", "description"):
                if not isinstance(item.get(key), str) or not str(item.get(key)).strip():
                    errors.append(f"action_items[{index}].{key} must be non-empty string")

    audit = result.get("audit")
    if not isinstance(audit, dict):
        errors.append("audit must be an object")
    else:
        if not isinstance(audit.get("run_id"), str) or not str(audit.get("run_id")).strip():
            errors.append("audit.run_id must be non-empty string")
        if str(audit.get("workflow")) != "workflow_03_meeting_action_items":
            errors.append("audit.workflow must equal workflow_03_meeting_action_items")

    return errors


def _sqlite_has_run(*, db_path: Path, run_id: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM runs WHERE run_id=? AND workflow='workflow_03_meeting_action_items' LIMIT 1",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    return row is not None


if __name__ == "__main__":
    raise SystemExit(main())
