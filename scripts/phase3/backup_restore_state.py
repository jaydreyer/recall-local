#!/usr/bin/env python3
"""Phase 3C backup/restore utility for SQLite + Qdrant state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _require_qdrant() -> tuple[Any, Any]:
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
        from qdrant_client.http import models  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Missing qdrant-client dependency. Run: pip install -r requirements.txt") from exc
    return QdrantClient, models


@dataclass
class BackupPaths:
    root: Path
    sqlite_copy: Path
    qdrant_points: Path
    manifest: Path


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _default_sqlite_path() -> Path:
    return Path(os.getenv("RECALL_DB_PATH", str(ROOT / "data" / "recall.db"))).expanduser().resolve()


def _default_qdrant_host() -> str:
    return os.getenv("QDRANT_HOST", "http://localhost:6333")


def _default_qdrant_collection() -> str:
    return os.getenv("QDRANT_COLLECTION", "recall_docs")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_dump(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _distance_to_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if "." in text:
        text = text.split(".")[-1]
    return text.lower()


def _distance_to_enum(models: Any, value: str | None) -> Any:
    normalized = (value or "cosine").strip().lower()
    mapping = {
        "cosine": models.Distance.COSINE,
        "dot": models.Distance.DOT,
        "euclid": models.Distance.EUCLID,
        "manhattan": models.Distance.MANHATTAN,
    }
    if normalized not in mapping:
        raise ValueError(f"Unsupported Qdrant distance metric: {value}")
    return mapping[normalized]


def _normalize_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(f"Unsupported non-JSON value type: {type(value).__name__}")


def _scroll_points(*, client: Any, collection: str, limit: int, with_vectors: bool):
    offset = None
    while True:
        result = client.scroll(
            collection_name=collection,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=with_vectors,
        )

        if isinstance(result, tuple) and len(result) == 2:
            records, offset = result
        elif hasattr(result, "points"):
            records = list(result.points)
            offset = getattr(result, "next_page_offset", None)
        else:
            raise RuntimeError("Unsupported qdrant-client scroll() response shape.")

        yield records
        if offset is None:
            return


def _extract_vector_config(info: Any) -> tuple[int | None, str | None]:
    vectors = getattr(getattr(getattr(info, "config", None), "params", None), "vectors", None)
    if vectors is None:
        return None, None

    if hasattr(vectors, "size"):
        return int(vectors.size), _distance_to_str(getattr(vectors, "distance", None))

    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        if hasattr(first, "size"):
            return int(first.size), _distance_to_str(getattr(first, "distance", None))

    return None, None


def _collection_exists(client: Any, collection: str) -> bool:
    if hasattr(client, "collection_exists"):
        return bool(client.collection_exists(collection_name=collection))
    try:
        client.get_collection(collection_name=collection)
    except Exception:  # noqa: BLE001
        return False
    return True


def _prepare_backup_paths(output_dir: Path, backup_name: str | None) -> BackupPaths:
    name = backup_name or _utc_stamp()
    root = output_dir / name
    sqlite_copy = root / "sqlite" / "recall.db"
    qdrant_points = root / "qdrant" / "points.jsonl"
    manifest = root / "manifest.json"

    sqlite_copy.parent.mkdir(parents=True, exist_ok=True)
    qdrant_points.parent.mkdir(parents=True, exist_ok=True)
    return BackupPaths(root=root, sqlite_copy=sqlite_copy, qdrant_points=qdrant_points, manifest=manifest)


def run_backup(args: argparse.Namespace) -> int:
    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if not sqlite_path.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_path}")

    backup_paths = _prepare_backup_paths(output_dir=output_dir, backup_name=args.backup_name)
    shutil.copy2(sqlite_path, backup_paths.sqlite_copy)

    QdrantClient, _ = _require_qdrant()
    client = QdrantClient(url=args.qdrant_host)

    vector_size: int | None = None
    distance: str | None = None
    try:
        info = client.get_collection(collection_name=args.qdrant_collection)
        vector_size, distance = _extract_vector_config(info)
    except Exception:  # noqa: BLE001
        vector_size, distance = None, None

    point_count = 0
    with backup_paths.qdrant_points.open("w", encoding="utf-8") as handle:
        for batch in _scroll_points(
            client=client,
            collection=args.qdrant_collection,
            limit=args.batch_size,
            with_vectors=(not args.exclude_vectors),
        ):
            for record in batch:
                point = {
                    "id": _normalize_jsonable(getattr(record, "id", None)),
                    "payload": _normalize_jsonable(getattr(record, "payload", None)) or {},
                }
                if not args.exclude_vectors:
                    vector_value = _normalize_jsonable(getattr(record, "vector", None))
                    if vector_value is not None:
                        point["vector"] = vector_value
                handle.write(json.dumps(point, separators=(",", ":")) + "\n")
                point_count += 1

    manifest = {
        "created_at_utc": _utc_stamp(),
        "sqlite": {
            "source_path": str(sqlite_path),
            "backup_path": str(backup_paths.sqlite_copy.relative_to(backup_paths.root)),
            "bytes": backup_paths.sqlite_copy.stat().st_size,
            "sha256": _sha256(backup_paths.sqlite_copy),
        },
        "qdrant": {
            "host": args.qdrant_host,
            "collection": args.qdrant_collection,
            "points_path": str(backup_paths.qdrant_points.relative_to(backup_paths.root)),
            "points_count": point_count,
            "vector_size": vector_size,
            "distance": distance,
            "vectors_included": (not args.exclude_vectors),
            "sha256": _sha256(backup_paths.qdrant_points),
        },
    }
    _json_dump(backup_paths.manifest, manifest)

    print(f"[OK] Backup written: {backup_paths.root}")
    print(f"[OK] SQLite copy: {backup_paths.sqlite_copy}")
    print(f"[OK] Qdrant points: {backup_paths.qdrant_points} (count={point_count})")
    print(f"[OK] Manifest: {backup_paths.manifest}")
    return 0


def _read_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Backup manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _infer_vector_size_from_jsonl(points_file: Path) -> int | None:
    with points_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            vector = record.get("vector")
            if isinstance(vector, list):
                return len(vector)
            if isinstance(vector, dict) and vector:
                first = next(iter(vector.values()))
                if isinstance(first, list):
                    return len(first)
    return None


def _recreate_collection(*, client: Any, models: Any, collection: str, vector_size: int, distance: str | None) -> None:
    if _collection_exists(client, collection):
        client.delete_collection(collection_name=collection)

    client.create_collection(
        collection_name=collection,
        vectors_config=models.VectorParams(
            size=vector_size,
            distance=_distance_to_enum(models, distance),
        ),
    )


def run_restore(args: argparse.Namespace) -> int:
    backup_dir = Path(args.backup_dir).expanduser().resolve()
    if not backup_dir.exists():
        raise FileNotFoundError(f"Backup directory not found: {backup_dir}")

    manifest = _read_manifest(backup_dir)
    sqlite_rel = manifest.get("sqlite", {}).get("backup_path")
    qdrant_rel = manifest.get("qdrant", {}).get("points_path")
    if not sqlite_rel or not qdrant_rel:
        raise RuntimeError("Invalid manifest: missing sqlite/qdrant paths.")

    sqlite_backup = backup_dir / sqlite_rel
    points_file = backup_dir / qdrant_rel
    if not sqlite_backup.exists():
        raise FileNotFoundError(f"SQLite backup file missing: {sqlite_backup}")
    if not points_file.exists():
        raise FileNotFoundError(f"Qdrant points file missing: {points_file}")

    sqlite_target = Path(args.sqlite_path).expanduser().resolve()
    sqlite_target.parent.mkdir(parents=True, exist_ok=True)

    previous_sqlite_backup: str | None = None
    if sqlite_target.exists() and not args.skip_sqlite:
        stamp = _utc_stamp()
        preserved = sqlite_target.with_name(f"{sqlite_target.name}.pre_restore_{stamp}.bak")
        shutil.copy2(sqlite_target, preserved)
        previous_sqlite_backup = str(preserved)

    if not args.skip_sqlite:
        shutil.copy2(sqlite_backup, sqlite_target)

    restored_points = 0
    qdrant_collection = args.qdrant_collection or manifest.get("qdrant", {}).get("collection")
    if not qdrant_collection:
        raise RuntimeError("Qdrant collection is required and missing from manifest/args.")

    if not args.skip_qdrant:
        QdrantClient, models = _require_qdrant()
        client = QdrantClient(url=args.qdrant_host)

        if args.replace_collection:
            vector_size = manifest.get("qdrant", {}).get("vector_size")
            if vector_size is None:
                vector_size = _infer_vector_size_from_jsonl(points_file)
            if vector_size is None:
                raise RuntimeError(
                    "Cannot replace collection without vector size metadata. "
                    "Create backup with vectors included or provide a seeded collection."
                )
            _recreate_collection(
                client=client,
                models=models,
                collection=qdrant_collection,
                vector_size=int(vector_size),
                distance=manifest.get("qdrant", {}).get("distance"),
            )

        batch: list[dict[str, Any]] = []
        with points_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                point: dict[str, Any] = {
                    "id": record["id"],
                    "payload": record.get("payload") or {},
                }
                if "vector" in record and record.get("vector") is not None:
                    point["vector"] = record["vector"]
                batch.append(point)

                if len(batch) >= args.batch_size:
                    client.upsert(collection_name=qdrant_collection, points=batch, wait=True)
                    restored_points += len(batch)
                    batch.clear()

        if batch:
            client.upsert(collection_name=qdrant_collection, points=batch, wait=True)
            restored_points += len(batch)

    report = {
        "restored_at_utc": _utc_stamp(),
        "backup_dir": str(backup_dir),
        "sqlite_target": str(sqlite_target),
        "sqlite_restored": (not args.skip_sqlite),
        "previous_sqlite_backup": previous_sqlite_backup,
        "qdrant_host": args.qdrant_host,
        "qdrant_collection": qdrant_collection,
        "qdrant_restored": (not args.skip_qdrant),
        "qdrant_points_restored": restored_points,
        "replace_collection": bool(args.replace_collection),
    }
    report_path = backup_dir / f"restore_report_{_utc_stamp()}.json"
    _json_dump(report_path, report)

    print(f"[OK] Restore completed from: {backup_dir}")
    if not args.skip_sqlite:
        print(f"[OK] SQLite restored to: {sqlite_target}")
    if previous_sqlite_backup:
        print(f"[OK] Previous SQLite preserved at: {previous_sqlite_backup}")
    if not args.skip_qdrant:
        print(f"[OK] Qdrant upserted points: {restored_points} into collection={qdrant_collection}")
    print(f"[OK] Restore report: {report_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backup/restore Recall.local state for Phase 3C.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup = subparsers.add_parser("backup", help="Create a backup snapshot.")
    backup.add_argument(
        "--output-dir",
        default=str(ROOT / "data" / "artifacts" / "backups" / "phase3c"),
        help="Directory where backup folder should be created.",
    )
    backup.add_argument("--backup-name", default=None, help="Optional fixed backup folder name.")
    backup.add_argument("--sqlite-path", default=str(_default_sqlite_path()), help="Path to SQLite DB file.")
    backup.add_argument("--qdrant-host", default=_default_qdrant_host(), help="Qdrant base URL.")
    backup.add_argument("--qdrant-collection", default=_default_qdrant_collection(), help="Qdrant collection name.")
    backup.add_argument("--batch-size", type=int, default=256, help="Qdrant scroll batch size.")
    backup.add_argument(
        "--exclude-vectors",
        action="store_true",
        help="Do not include vectors in Qdrant backup file (payload-only export).",
    )

    restore = subparsers.add_parser("restore", help="Restore from a backup snapshot.")
    restore.add_argument("--backup-dir", required=True, help="Path to backup directory.")
    restore.add_argument("--sqlite-path", default=str(_default_sqlite_path()), help="Target SQLite DB path.")
    restore.add_argument("--qdrant-host", default=_default_qdrant_host(), help="Qdrant base URL.")
    restore.add_argument(
        "--qdrant-collection",
        default=None,
        help="Override Qdrant collection name (defaults to manifest value).",
    )
    restore.add_argument("--batch-size", type=int, default=128, help="Qdrant upsert batch size.")
    restore.add_argument(
        "--replace-collection",
        action="store_true",
        help="Delete and recreate collection before restore (destructive).",
    )
    restore.add_argument("--skip-sqlite", action="store_true", help="Skip SQLite restore step.")
    restore.add_argument("--skip-qdrant", action="store_true", help="Skip Qdrant restore step.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "backup":
        return run_backup(args)
    if args.command == "restore":
        return run_restore(args)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
