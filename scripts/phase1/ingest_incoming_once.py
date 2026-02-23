#!/usr/bin/env python3
"""One-pass folder ingestion for files in DATA_INCOMING."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.ingestion_pipeline import IngestRequest, ingest_request, load_settings  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest files currently present in DATA_INCOMING.")
    parser.add_argument("--limit", type=int, default=0, help="Max number of files to ingest (0 = all).")
    parser.add_argument("--dry-run", action="store_true", help="Skip DB/Qdrant writes.")
    return parser.parse_args()


def list_candidate_files(incoming_dir: Path) -> list[Path]:
    if not incoming_dir.exists():
        return []
    return sorted(
        [
            file_path
            for file_path in incoming_dir.iterdir()
            if file_path.is_file() and not file_path.name.startswith(".")
        ]
    )


def main() -> int:
    args = parse_args()
    settings = load_settings()
    candidates = list_candidate_files(settings.incoming_dir)
    if args.limit > 0:
        candidates = candidates[: args.limit]

    results = []
    errors = []

    for file_path in candidates:
        request = IngestRequest(
            source_type="file",
            content=str(file_path),
            source_channel="folder-watcher",
            metadata={"trigger": "ingest_incoming_once"},
        )
        try:
            result = ingest_request(request, dry_run=args.dry_run)
            results.append(asdict(result))
        except Exception as exc:  # noqa: BLE001
            errors.append({"file": str(file_path), "error": str(exc)})

    summary = {
        "incoming_dir": str(settings.incoming_dir),
        "processed": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
        "dry_run": args.dry_run,
    }
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
