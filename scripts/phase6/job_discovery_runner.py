#!/usr/bin/env python3
"""Phase 6 discovery runner scaffold."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "job_search.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_default_search_config() -> dict[str, Any]:
    if not DEFAULT_CONFIG.exists():
        return {}
    try:
        payload = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    config = _load_default_search_config()
    titles = payload.get("titles") or config.get("search_titles") or []
    locations = payload.get("locations") or config.get("search_locations") or []
    sources = payload.get("sources") or ["jobspy", "adzuna", "serpapi", "career_page"]

    queued_queries = len(list(titles)) * len(list(locations)) if titles and locations else 0
    run_id = f"job_discovery_{uuid.uuid4().hex[:12]}"
    return {
        "run_id": run_id,
        "status": "queued",
        "triggered_at": _now_iso(),
        "sources": sources,
        "titles": list(titles),
        "locations": list(locations),
        "queued_queries": queued_queries,
        "message": "Discovery pipeline scaffold queued. Source integrations land in Phase 6B.",
    }
