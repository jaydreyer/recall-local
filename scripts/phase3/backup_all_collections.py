#!/usr/bin/env python3
"""Backup SQLite state and every Qdrant collection into a single snapshot folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_output_dir() -> Path:
    return ROOT / "data" / "artifacts" / "backups" / "phase3c_all"


def _default_sqlite_path() -> Path:
    return Path(os.getenv("RECALL_DB_PATH", str(ROOT / "data" / "recall.db")))


def _default_qdrant_host() -> str:
    return os.getenv("QDRANT_HOST", "http://localhost:6333")


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _extract_vector_config(info: Any) -> tuple[int | None, str | None]:
    vectors = getattr(getattr(getattr(info, "config", None), "params", None), "vectors", None)
    if vectors is None:
        return None, None

    if hasattr(vectors, "size"):
        distance = getattr(vectors, "distance", None)
        distance_name = getattr(distance, "name", None)
        return int(vectors.size), str(distance_name or distance or "")

    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        size = getattr(first, "size", None)
        distance = getattr(first, "distance", None)
        distance_name = getattr(distance, "name", None)
        if size is not None:
            return int(size), str(distance_name or distance or "")

    return None, None


def _collection_names(client: Any) -> list[str]:
    response = client.get_collections()
    collections = getattr(response, "collections", None)
    if collections is None:
        return []
    names: list[str] = []
    for collection in collections:
        name = getattr(collection, "name", None)
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _scroll_points(*, client: Any, collection: str, limit: int) -> list[Any]:
    points: list[Any] = []
    offset: Any = None

    while True:
        response = client.scroll(
            collection_name=collection,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if isinstance(response, tuple) and len(response) == 2:
            records, offset = response
        else:
            records = getattr(response, "points", None)
            offset = getattr(response, "next_page_offset", None)
        if not records:
            break
        points.extend(records)
        if offset is None:
            break
    return points


def run_backup(args: argparse.Namespace) -> int:
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("Missing qdrant-client dependency. Run: pip install -r requirements.txt") from exc

    output_root = Path(args.output_dir).expanduser().resolve()
    backup_name = args.backup_name or _utc_stamp()
    backup_dir = output_root / backup_name
    sqlite_dir = backup_dir / "sqlite"
    qdrant_dir = backup_dir / "qdrant"
    sqlite_dir.mkdir(parents=True, exist_ok=True)
    qdrant_dir.mkdir(parents=True, exist_ok=True)

    sqlite_src = Path(args.sqlite_path).expanduser().resolve()
    if not sqlite_src.exists():
        raise FileNotFoundError(f"SQLite DB file not found: {sqlite_src}")
    sqlite_copy = sqlite_dir / sqlite_src.name
    shutil.copy2(sqlite_src, sqlite_copy)

    client = QdrantClient(url=args.qdrant_host)
    names = _collection_names(client)

    collections_manifest: list[dict[str, Any]] = []
    total_points = 0
    for name in names:
        points_file = qdrant_dir / f"{name}.points.jsonl"
        info = client.get_collection(collection_name=name)
        vector_size, distance = _extract_vector_config(info)

        points = _scroll_points(client=client, collection=name, limit=args.batch_size)
        point_count = 0
        with points_file.open("w", encoding="utf-8") as handle:
            for record in points:
                payload = _normalize_jsonable(getattr(record, "payload", {}) or {})
                point: dict[str, Any] = {
                    "id": _normalize_jsonable(getattr(record, "id", None)),
                    "payload": payload,
                }
                vector = _normalize_jsonable(getattr(record, "vector", None))
                if vector is not None:
                    point["vector"] = vector
                handle.write(json.dumps(point, separators=(",", ":")) + "\n")
                point_count += 1

        total_points += point_count
        collections_manifest.append(
            {
                "name": name,
                "points_path": str(points_file.relative_to(backup_dir)),
                "point_count": point_count,
                "vector_size": vector_size,
                "distance": distance,
                "sha256": _sha256(points_file),
            }
        )

    manifest = {
        "backup_created_at_utc": _utc_stamp(),
        "sqlite": {
            "source_path": str(sqlite_src),
            "backup_path": str(sqlite_copy.relative_to(backup_dir)),
            "sha256": _sha256(sqlite_copy),
        },
        "qdrant": {
            "host": args.qdrant_host,
            "collection_count": len(collections_manifest),
            "total_points": total_points,
            "collections": collections_manifest,
        },
    }
    manifest_path = backup_dir / "manifest.json"
    _json_dump(manifest_path, manifest)

    print(f"[OK] Backup written: {backup_dir}")
    print(f"[OK] SQLite copy: {sqlite_copy}")
    print(f"[OK] Qdrant collections: {len(collections_manifest)}")
    print(f"[OK] Qdrant points total: {total_points}")
    print(f"[OK] Manifest: {manifest_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup all Qdrant collections + SQLite state.")
    parser.add_argument("--output-dir", default=str(_default_output_dir()), help="Backup root output directory.")
    parser.add_argument("--backup-name", default=None, help="Optional fixed backup folder name.")
    parser.add_argument("--sqlite-path", default=str(_default_sqlite_path()), help="Path to SQLite DB file.")
    parser.add_argument("--qdrant-host", default=_default_qdrant_host(), help="Qdrant base URL.")
    parser.add_argument("--batch-size", type=int, default=256, help="Qdrant scroll batch size.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_backup(args)


if __name__ == "__main__":
    raise SystemExit(main())
