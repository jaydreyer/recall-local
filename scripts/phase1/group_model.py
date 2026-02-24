#!/usr/bin/env python3
"""Canonical Recall.local group model helpers."""

from __future__ import annotations

from typing import Any

CANONICAL_GROUPS = ("job-search", "learning", "project", "reference", "meeting")
DEFAULT_GROUP = "reference"

_GROUP_ALIASES = {
    "jobsearch": "job-search",
    "job_search": "job-search",
}


def normalize_group(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw:
            normalized = _GROUP_ALIASES.get(raw, raw.replace("_", "-").replace(" ", "-"))
            if normalized in CANONICAL_GROUPS:
                return normalized
    return DEFAULT_GROUP
