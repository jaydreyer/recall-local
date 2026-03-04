#!/usr/bin/env python3
"""Deduplication helpers for job candidates."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from scripts.phase6.job_repository import all_jobs


@dataclass
class DedupResult:
    duplicate: bool
    reason: str
    matched_job_id: str | None = None
    similarity_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "duplicate": self.duplicate,
            "reason": self.reason,
            "matched_job_id": self.matched_job_id,
            "similarity_score": self.similarity_score,
        }


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def check_job_duplicate(candidate: dict[str, Any], *, similarity_threshold: float = 0.92) -> DedupResult:
    candidate_url = _norm(candidate.get("url"))
    candidate_title = _norm(candidate.get("title"))
    candidate_company = _norm(candidate.get("company"))
    candidate_description = _norm(candidate.get("description"))

    jobs = all_jobs()
    for job in jobs:
        existing_url = _norm(job.get("url"))
        if candidate_url and existing_url and candidate_url == existing_url:
            return DedupResult(
                duplicate=True,
                reason="exact_url_match",
                matched_job_id=str(job.get("jobId")),
                similarity_score=1.0,
            )

    candidate_signature = " ".join(part for part in (candidate_title, candidate_company) if part)
    for job in jobs:
        existing_signature = " ".join(
            part for part in (_norm(job.get("title")), _norm(job.get("company"))) if part
        )
        if candidate_signature and existing_signature and candidate_signature == existing_signature:
            return DedupResult(
                duplicate=True,
                reason="title_company_match",
                matched_job_id=str(job.get("jobId")),
                similarity_score=1.0,
            )

    if candidate_description:
        best_score = 0.0
        best_match_id: str | None = None
        for job in jobs:
            existing_description = _norm(job.get("description"))
            if not existing_description:
                continue
            score = SequenceMatcher(a=candidate_description, b=existing_description).ratio()
            if score > best_score:
                best_score = score
                best_match_id = str(job.get("jobId"))
        if best_score >= similarity_threshold and best_match_id:
            return DedupResult(
                duplicate=True,
                reason="description_similarity",
                matched_job_id=best_match_id,
                similarity_score=round(best_score, 4),
            )

    return DedupResult(duplicate=False, reason="unique")
