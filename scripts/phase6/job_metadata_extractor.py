#!/usr/bin/env python3
"""Extract job metadata hints from ingestion payloads."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

JOB_URL_PATTERNS = [
    re.compile(r"linkedin\.com/jobs", re.IGNORECASE),
    re.compile(r"greenhouse\.io", re.IGNORECASE),
    re.compile(r"lever\.co", re.IGNORECASE),
    re.compile(r"workdayjobs\.com", re.IGNORECASE),
]


def looks_like_job_url(url: str) -> bool:
    text = str(url or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in JOB_URL_PATTERNS)


def infer_source_from_url(url: str) -> str:
    host = urlparse(str(url or "").strip()).netloc.lower()
    if "linkedin.com" in host:
        return "linkedin"
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "workdayjobs.com" in host:
        return "workday"
    return "career_page"


def extract_job_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "").strip()
    source = str(payload.get("source") or "").strip().lower()
    if not source and url:
        source = infer_source_from_url(url)

    return {
        "is_job_url": looks_like_job_url(url),
        "source": source or "unknown",
        "title": str(payload.get("title") or "").strip() or None,
        "company": str(payload.get("company") or "").strip() or None,
        "location": str(payload.get("location") or "").strip() or None,
    }
