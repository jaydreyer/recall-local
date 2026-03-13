#!/usr/bin/env python3
"""Pytest coverage for Phase 6 job dedup helpers."""

from __future__ import annotations

import pytest

from scripts.phase6 import job_dedup


@pytest.mark.parametrize(
    ("raw_company", "expected"),
    [
        ("OpenAI, Inc.", "openai"),
        ("Anthropic LLC", "anthropic"),
        ("Example   Corp.", "example"),
    ],
)
def test_normalize_company_strips_common_suffixes(raw_company: str, expected: str) -> None:
    assert job_dedup._normalize_company(raw_company) == expected


def test_dedup_result_to_dict_keeps_alias_fields() -> None:
    result = job_dedup.DedupResult(
        duplicate=True,
        reason="semantic",
        matched_job_id="job-7",
        similarity_score=0.97,
    )

    payload = result.to_dict()

    assert payload["duplicate"] is True
    assert payload["is_duplicate"] is True
    assert payload["matched_job_id"] == "job-7"
    assert payload["similar_job_id"] == "job-7"
    assert payload["similarity_score"] == 0.97


def test_fallback_check_detects_exact_url_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        job_dedup,
        "all_jobs",
        lambda: [
            {
                "jobId": "job-1",
                "url": "https://example.com/jobs/1",
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "description": "Platform role.",
            }
        ],
    )

    result = job_dedup._fallback_check(
        {"url": "https://example.com/jobs/1", "title": "Other", "company": "Other"},
        similarity_threshold=0.92,
    )

    assert result.duplicate is True
    assert result.reason == "exact_url"
    assert result.matched_job_id == "job-1"


def test_check_job_duplicate_falls_back_when_qdrant_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_dedup, "qdrant_client_from_env", lambda host: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(
        job_dedup,
        "all_jobs",
        lambda: [
            {
                "jobId": "job-2",
                "url": "",
                "title": "AI Engineer",
                "company": "OpenAI",
                "description": "Build customer AI systems and deployment tooling.",
            }
        ],
    )

    result = job_dedup.check_job_duplicate(
        {
            "title": "AI Engineer",
            "company": "OpenAI",
            "description": "Build customer AI systems and deployment tooling.",
        },
        similarity_threshold=2.0,
    )

    assert result.duplicate is True
    assert result.reason in {"company_title_7d", "semantic"}
