#!/usr/bin/env python3
"""Archive obvious Phase 3 off-target job noise without deleting history."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase6.job_repository import apply_relevance_cleanup  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist cleanup. Default is dry-run.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of jobs to update or preview.")
    args = parser.parse_args()

    result = apply_relevance_cleanup(dry_run=not args.apply, limit=args.limit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
