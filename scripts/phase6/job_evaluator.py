#!/usr/bin/env python3
"""Phase 6 job-evaluation queue scaffold."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def queue_job_evaluations(
    *,
    job_ids: list[str],
    wait: bool = False,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unique_ids = [item for item in dict.fromkeys(str(job_id).strip() for job_id in job_ids) if item]
    run_id = f"job_eval_{uuid.uuid4().hex[:12]}"
    return {
        "run_id": run_id,
        "queued": len(unique_ids),
        "job_ids": unique_ids,
        "status": "completed" if wait else "queued",
        "wait": wait,
        "triggered_at": _now_iso(),
        "settings": settings or {},
        "message": "Evaluation orchestration scaffold ready. Full scoring pipeline lands in Phase 6C.",
    }
