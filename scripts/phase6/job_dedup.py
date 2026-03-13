#!/usr/bin/env python3
"""Deduplication helpers for job candidates."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

from scripts.llm_client import embed
from scripts.phase1.ingestion_pipeline import qdrant_client_from_env
from scripts.phase6.job_repository import all_jobs
from scripts.phase6.setup_collections import COLLECTION_JOBS

DEFAULT_SIMILARITY_THRESHOLD = 0.92


@dataclass
class DedupResult:
    duplicate: bool
    reason: str
    matched_job_id: str | None = None
    similarity_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "duplicate": self.duplicate,
            "is_duplicate": self.duplicate,
            "reason": self.reason,
            "matched_job_id": self.matched_job_id,
            "similar_job_id": self.matched_job_id,
            "similarity_score": self.similarity_score,
        }
        return payload


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_company(value: Any) -> str:
    lowered = _norm(value)
    lowered = re.sub(r"\b(inc\.?|llc|ltd\.?|corp\.?|corporation|co\.?|pbc)\b", "", lowered)
    lowered = re.sub(r"[.,]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _coerce_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _extract_first_point(scroll_response: Any) -> Any | None:
    if isinstance(scroll_response, tuple) and len(scroll_response) == 2:
        points = scroll_response[0]
    else:
        points = getattr(scroll_response, "points", None)
    if isinstance(points, list) and points:
        return points[0]
    return None


def _extract_payload(point: Any) -> dict[str, Any]:
    payload = getattr(point, "payload", None)
    if isinstance(payload, dict):
        return payload
    if isinstance(point, dict):
        maybe_payload = point.get("payload")
        if isinstance(maybe_payload, dict):
            return maybe_payload
    return {}


def _extract_job_id(point: Any, payload: dict[str, Any]) -> str | None:
    payload_job_id = payload.get("job_id") or payload.get("doc_id")
    if payload_job_id:
        return str(payload_job_id)
    point_id = getattr(point, "id", None)
    if point_id is not None:
        return str(point_id)
    if isinstance(point, dict) and point.get("id") is not None:
        return str(point["id"])
    return None


def _qdrant_search(*, client: Any, vector: list[float], score_threshold: float) -> Any | None:
    kwargs = {
        "collection_name": COLLECTION_JOBS,
        "limit": 1,
        "with_payload": True,
        "score_threshold": score_threshold,
    }
    if hasattr(client, "search"):
        try:
            points = client.search(query_vector=vector, **kwargs)
        except TypeError:
            points = client.search(query=vector, **kwargs)
        if isinstance(points, list) and points:
            return points[0]
        return None

    if hasattr(client, "query_points"):
        try:
            response = client.query_points(query=vector, **kwargs)
        except TypeError:
            response = client.query_points(query_vector=vector, **kwargs)
        points = getattr(response, "points", None)
        if isinstance(points, list) and points:
            return points[0]
        return None

    return None


def _check_exact_url(*, client: Any, url: str) -> DedupResult | None:
    from qdrant_client import models

    query_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="url",
                match=models.MatchValue(value=url),
            )
        ]
    )
    kwargs = {
        "collection_name": COLLECTION_JOBS,
        "limit": 1,
        "with_payload": True,
        "with_vectors": False,
    }
    try:
        response = client.scroll(scroll_filter=query_filter, **kwargs)
    except TypeError:
        response = client.scroll(filter=query_filter, **kwargs)
    point = _extract_first_point(response)
    if point is None:
        return None
    payload = _extract_payload(point)
    return DedupResult(
        duplicate=True,
        reason="exact_url",
        matched_job_id=_extract_job_id(point, payload),
        similarity_score=1.0,
    )


def _check_company_title_window(*, client: Any, title: str, company: str, discovered_at: datetime) -> DedupResult | None:
    normalized_company = company

    offset: Any = None
    while True:
        kwargs = {
            "collection_name": COLLECTION_JOBS,
            "limit": 128,
            "offset": offset,
            "with_payload": True,
            "with_vectors": False,
        }
        response = client.scroll(**kwargs)
        if isinstance(response, tuple) and len(response) == 2:
            points, offset = response
        else:
            points = getattr(response, "points", None)
            offset = getattr(response, "next_page_offset", None)
        if not points:
            break

        for point in points:
            payload = _extract_payload(point)
            existing_title = _norm(payload.get("title"))
            if existing_title != title:
                continue
            existing_company = _normalize_company(payload.get("company_normalized") or payload.get("company"))
            if existing_company != normalized_company:
                continue
            existing_when = _coerce_datetime(payload.get("date_posted") or payload.get("discovered_at"))
            if existing_when is None:
                continue
            delta = abs((discovered_at - existing_when).total_seconds())
            if delta <= timedelta(days=7).total_seconds():
                return DedupResult(
                    duplicate=True,
                    reason="company_title_7d",
                    matched_job_id=_extract_job_id(point, payload),
                    similarity_score=1.0,
                )

        if offset is None:
            break

    return None


def _check_semantic(*, client: Any, description: str, threshold: float) -> DedupResult | None:
    query_vector = embed(description, trace_metadata={"operation": "phase6_job_dedup_semantic"})
    hit = _qdrant_search(client=client, vector=query_vector, score_threshold=threshold)
    if hit is None:
        return None

    payload = _extract_payload(hit)
    score = getattr(hit, "score", None)
    if score is None and isinstance(hit, dict):
        score = hit.get("score")
    score_value = float(score) if score is not None else None

    return DedupResult(
        duplicate=True,
        reason="semantic",
        matched_job_id=_extract_job_id(hit, payload),
        similarity_score=round(score_value, 4) if score_value is not None else None,
    )


def _fallback_check(candidate: dict[str, Any], *, similarity_threshold: float) -> DedupResult:
    candidate_url = _norm(candidate.get("url"))
    candidate_title = _norm(candidate.get("title"))
    candidate_company = _normalize_company(candidate.get("company") or candidate.get("company_normalized"))
    candidate_description = _norm(candidate.get("description"))

    jobs = all_jobs()
    for job in jobs:
        existing_url = _norm(job.get("url"))
        if candidate_url and existing_url and candidate_url == existing_url:
            return DedupResult(
                duplicate=True,
                reason="exact_url",
                matched_job_id=str(job.get("jobId")),
                similarity_score=1.0,
            )

    for job in jobs:
        existing_title = _norm(job.get("title"))
        existing_company = _normalize_company(job.get("company_normalized") or job.get("company"))
        if candidate_title and candidate_company and existing_title == candidate_title and existing_company == candidate_company:
            return DedupResult(
                duplicate=True,
                reason="company_title_7d",
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
                reason="semantic",
                matched_job_id=best_match_id,
                similarity_score=round(best_score, 4),
            )

    return DedupResult(duplicate=False, reason="unique")


def check_job_duplicate(candidate: dict[str, Any], *, similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> DedupResult:
    candidate_url_raw = str(candidate.get("url") or "").strip()
    candidate_url = _norm(candidate.get("url"))
    candidate_title = _norm(candidate.get("title"))
    candidate_company = _normalize_company(candidate.get("company") or candidate.get("company_normalized"))
    candidate_description = _norm(candidate.get("description"))
    candidate_timestamp = _coerce_datetime(candidate.get("date_posted") or candidate.get("discovered_at"))
    discovered_at = candidate_timestamp or datetime.now(timezone.utc)

    if not candidate_company and candidate.get("company"):
        candidate_company = _normalize_company(candidate.get("company"))

    threshold = float(similarity_threshold)
    if threshold < 0:
        threshold = 0.0
    if threshold > 1:
        threshold = 1.0

    try:
        host = os.getenv("QDRANT_HOST", "http://localhost:6333").strip() or "http://localhost:6333"
        client = qdrant_client_from_env(host)
        if candidate_url_raw:
            exact_url_result = _check_exact_url(client=client, url=candidate_url_raw)
            if exact_url_result is None and candidate_url != candidate_url_raw:
                exact_url_result = _check_exact_url(client=client, url=candidate_url)
            if exact_url_result is not None:
                return exact_url_result

        if candidate_title and candidate_company:
            company_title_result = _check_company_title_window(
                client=client,
                title=candidate_title,
                company=candidate_company,
                discovered_at=discovered_at,
            )
            if company_title_result is not None:
                return company_title_result

        if candidate_description:
            semantic_result = _check_semantic(client=client, description=candidate_description, threshold=threshold)
            if semantic_result is not None:
                return semantic_result

        return DedupResult(duplicate=False, reason="unique")
    except Exception:
        return _fallback_check(candidate, similarity_threshold=threshold)
