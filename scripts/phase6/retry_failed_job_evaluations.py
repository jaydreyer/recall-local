#!/usr/bin/env python3
"""List and rerun failed Phase 6 job evaluations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase6 import job_repository  # noqa: E402


def _candidate_jobs(*, job_ids: list[str], limit: int) -> list[dict[str, Any]]:
    if job_ids:
        jobs: list[dict[str, Any]] = []
        for job_id in job_ids:
            job = job_repository.get_job(job_id)
            if job is not None:
                jobs.append(job)
        return jobs
    payload = job_repository.list_jobs(
        status="error",
        min_score=-1,
        max_score=100,
        limit=limit,
        offset=0,
    )
    return list(payload.get("items") or [])


def find_failed_jobs(*, job_ids: list[str] | None = None, limit: int = 25) -> list[dict[str, Any]]:
    """Return jobs currently marked with evaluation errors."""
    seen: set[str] = set()
    failed: list[dict[str, Any]] = []
    for job in _candidate_jobs(job_ids=job_ids or [], limit=limit):
        job_id = str(job.get("jobId") or "").strip()
        if not job_id or job_id in seen:
            continue
        seen.add(job_id)
        if str(job.get("status") or "").strip().lower() != "error":
            continue
        failed.append(
            {
                "jobId": job_id,
                "title": str(job.get("title") or "").strip(),
                "company": str(job.get("company") or "").strip(),
                "evaluation_error": str(job.get("evaluation_error") or "").strip() or None,
            }
        )
    return failed


def run_retry(*, job_ids: list[str], wait: bool) -> dict[str, Any]:
    """Requeue failed jobs through the existing Phase 6 evaluator."""
    from scripts.phase6 import job_evaluator

    return job_evaluator.queue_job_evaluations(job_ids=job_ids, wait=wait)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="List or rerun failed Phase 6 job evaluations.")
    parser.add_argument(
        "--job-id",
        action="append",
        default=[],
        dest="job_ids",
        help="Optional specific failed job identifier to inspect or rerun. Repeat for multiple jobs.",
    )
    parser.add_argument(
        "--limit", type=int, default=25, help="Maximum failed jobs to inspect when no --job-id is provided."
    )
    parser.add_argument("--dry-run", action="store_true", help="List matching failed jobs without rerunning them.")
    parser.add_argument(
        "--async", action="store_true", dest="run_async", help="Queue the retry in the background instead of waiting."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    payload: dict[str, Any] = {
        "workflow": "workflow_06a_retry_failed_job_evaluations",
        "matched": 0,
        "jobs": [],
    }
    try:
        failed_jobs = find_failed_jobs(job_ids=args.job_ids, limit=max(1, args.limit))
    except Exception as exc:  # noqa: BLE001
        payload["message"] = (
            "Failed to inspect Phase 6 jobs. Activate the project environment and verify Qdrant access."
        )
        payload["error"] = str(exc)
        print(json.dumps(payload, indent=2))
        return 1

    payload["matched"] = len(failed_jobs)
    payload["jobs"] = failed_jobs

    if not failed_jobs:
        payload["message"] = "No failed Phase 6 job evaluations matched the requested scope."
        print(json.dumps(payload, indent=2))
        return 0

    if args.dry_run:
        payload["message"] = "Dry run only. No evaluations were retried."
        print(json.dumps(payload, indent=2))
        return 0

    try:
        retry_result = run_retry(job_ids=[job["jobId"] for job in failed_jobs], wait=not args.run_async)
    except Exception as exc:  # noqa: BLE001
        payload["message"] = (
            "Failed to rerun job evaluations. Verify the project environment, model runtime, and bridge dependencies."
        )
        payload["error"] = str(exc)
        print(json.dumps(payload, indent=2))
        return 1

    payload["retry"] = retry_result
    payload["message"] = f"Retried {len(failed_jobs)} failed job evaluation{'' if len(failed_jobs) == 1 else 's'}."
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
