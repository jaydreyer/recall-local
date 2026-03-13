#!/usr/bin/env python3
"""Pytest coverage for canonical Phase 1 group normalization."""

from __future__ import annotations

import pytest

from scripts.phase1.group_model import DEFAULT_GROUP, normalize_group


@pytest.mark.parametrize(
    ("raw_value", "expected_group"),
    [
        ("job-search", "job-search"),
        ("job_search", "job-search"),
        ("jobsearch", "job-search"),
        ("learning", "learning"),
        (" project ", "project"),
        ("meeting", "meeting"),
        ("REFERENCE", "reference"),
        ("not-a-group", DEFAULT_GROUP),
        ("", DEFAULT_GROUP),
        (None, DEFAULT_GROUP),
    ],
)
def test_normalize_group_returns_canonical_value_or_default(raw_value: object, expected_group: str) -> None:
    """Normalize alias forms while falling back safely for invalid input."""
    assert normalize_group(raw_value) == expected_group
