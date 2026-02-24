#!/usr/bin/env python3
"""Batch ingest corpus items from a manifest file."""

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

from scripts.phase1.group_model import normalize_group  # noqa: E402
from scripts.phase1.ingestion_pipeline import IngestRequest, ingest_request  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch ingest corpus items from manifest JSON.")
    parser.add_argument("--manifest-file", required=True, help="Path to manifest JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Skip DB/Qdrant writes.")
    parser.add_argument(
        "--ensure-tag",
        default="",
        help="Optional tag to enforce on every manifest item (defaults to none).",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {}, _coerce_items(data)
    if not isinstance(data, dict):
        raise ValueError("Manifest must be a JSON object or an array of item objects.")

    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("Manifest field 'defaults' must be an object.")

    items_raw = data.get("items")
    if items_raw is None:
        raise ValueError("Manifest object must include 'items' array.")
    return defaults, _coerce_items(items_raw)


def _coerce_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Manifest items must be an array.")
    items: list[dict[str, Any]] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise ValueError(f"Manifest item at index {index} must be an object.")
        items.append(dict(raw))
    return items


def to_ingest_request(
    *,
    defaults: dict[str, Any],
    item: dict[str, Any],
    ensure_tag: str | None = None,
) -> IngestRequest:
    source_type = str(item.get("type", defaults.get("type", ""))).strip().lower()
    if source_type not in {"file", "url", "text", "email", "gdoc"}:
        raise ValueError(f"Unsupported item type: {source_type}")

    content = item.get("content", defaults.get("content"))
    if content is None:
        raise ValueError("Each item must include 'content'.")

    source_channel = str(item.get("source", defaults.get("source", "manual"))).strip() or "manual"
    title = _coalesce_text(item.get("title"), defaults.get("title"))
    group = normalize_group(item.get("group", defaults.get("group")))
    tags = _normalize_tags(item.get("tags", defaults.get("tags")))
    enforced_tag = (ensure_tag or "").strip()
    if enforced_tag and enforced_tag not in tags:
        tags.append(enforced_tag)

    metadata = _coalesce_metadata(defaults.get("metadata"), item.get("metadata"))

    replace_existing = _coerce_bool(item.get("replace_existing", defaults.get("replace_existing", False)))
    source_key = _coalesce_text(item.get("source_key"), defaults.get("source_key"))

    return IngestRequest(
        source_type=source_type,
        content=content,
        source_channel=source_channel,
        title=title,
        group=group,
        tags=tags,
        metadata=metadata,
        replace_existing=replace_existing,
        source_key=source_key,
    )


def _coalesce_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        tags: list[str] = []
        for raw in value:
            tag = str(raw).strip()
            if tag:
                tags.append(tag)
        return tags
    raise ValueError("tags must be array or comma-separated string.")


def _coalesce_metadata(defaults_metadata: Any, item_metadata: Any) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if isinstance(defaults_metadata, dict):
        merged.update(defaults_metadata)
    if isinstance(item_metadata, dict):
        merged.update(item_metadata)
    return merged


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    raise ValueError("replace_existing must be boolean-like.")


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest_file)
    if not manifest_path.exists():
        print(f"Manifest file not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        defaults, items = load_manifest(manifest_path)
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid manifest: {exc}", file=sys.stderr)
        return 2

    results = []
    errors = []
    ensure_tag = args.ensure_tag.strip() or None
    for index, item in enumerate(items):
        try:
            request = to_ingest_request(defaults=defaults, item=item, ensure_tag=ensure_tag)
            result = ingest_request(request, dry_run=args.dry_run)
            results.append(asdict(result))
        except Exception as exc:  # noqa: BLE001
            errors.append({"item_index": index, "item": item, "error": str(exc)})

    summary = {
        "manifest_file": str(manifest_path.resolve()),
        "item_count": len(items),
        "ingested_count": len(results),
        "error_count": len(errors),
        "dry_run": args.dry_run,
        "ingested": results,
        "errors": errors,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
