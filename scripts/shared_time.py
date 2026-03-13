#!/usr/bin/env python3
"""Shared UTC timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with second precision."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
