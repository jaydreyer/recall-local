#!/usr/bin/env python3
"""Shared string normalization helpers."""

from __future__ import annotations

import re
from typing import Any


def slugify(value: Any, *, fallback: str = "unknown") -> str:
    """Create a lowercase, dash-separated slug."""
    lowered = str(value or "").strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-") or fallback
