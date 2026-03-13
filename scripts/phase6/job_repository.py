#!/usr/bin/env python3
"""Qdrant-backed read/update helpers for Phase 6 job endpoints."""

from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from scripts.phase1.ingestion_pipeline import qdrant_client_from_env

LOGGER = logging.getLogger(__name__)
COLLECTION_JOBS = "recall_jobs"
DEFAULT_STATUS_FILTER = "evaluated"
DEFAULT_QDRANT_HOST = "http://localhost:6333"
DEFAULT_SCROLL_CACHE_SECONDS = 15.0
SCROLL_PAGE_SIZE = 256
UPSERT_BATCH_SIZE = 128
HIGH_FIT_THRESHOLD = 75
MEDIUM_FIT_THRESHOLD = 50
LOW_FIT_THRESHOLD = 25
_JOBS_SCROLL_CACHE: dict[tuple[bool, str], tuple[float, list[dict[str, Any]]]] = {}


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _normalize_observation(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _flatten_search_value(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, dict):
        parts: list[str] = []
        for item in value.values():
            parts.extend(_flatten_search_value(item))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(_flatten_search_value(item))
        return parts
    return [str(value)]


def _matches_search(job: dict[str, Any], query: str) -> bool:
    normalized_query = str(query or "").strip().lower()
    if not normalized_query:
        return True

    haystack = " ".join(
        _flatten_search_value(
            [
                job.get("title"),
                job.get("company"),
                job.get("company_normalized"),
                job.get("location"),
                job.get("source"),
                job.get("search_query"),
                job.get("score_rationale"),
                job.get("matching_skills"),
                job.get("gaps"),
                job.get("application_tips"),
                job.get("cover_letter_angle"),
                job.get("notes"),
                job.get("observation"),
            ]
        )
    ).lower()
    return normalized_query in haystack


def _to_slug(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = "".join(char if char.isalnum() else "-" for char in lowered)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "unknown"


def _normalize_job(record: Any) -> dict[str, Any]:
    payload = dict(getattr(record, "payload", {}) or {})
    qdrant_id = str(getattr(record, "id", ""))
    job_id = str(payload.get("job_id") or payload.get("doc_id") or qdrant_id)
    company = str(payload.get("company") or "")
    normalized = {
        "jobId": job_id,
        "title": payload.get("title") or "Untitled role",
        "company": company,
        "company_normalized": payload.get("company_normalized") or company,
        "company_id": payload.get("company_id") or _to_slug(company),
        "company_tier": _parse_int(payload.get("company_tier"), default=0),
        "location": payload.get("location") or "Unknown",
        "location_type": payload.get("location_type") or None,
        "url": payload.get("url") or None,
        "source": payload.get("source") or "unknown",
        "description": payload.get("description") or "",
        "salary_min": payload.get("salary_min"),
        "salary_max": payload.get("salary_max"),
        "date_posted": payload.get("date_posted"),
        "discovered_at": payload.get("discovered_at"),
        "evaluated_at": payload.get("evaluated_at"),
        "search_query": payload.get("search_query"),
        "status": payload.get("status") or "new",
        "fit_score": _parse_int(payload.get("fit_score"), default=0),
        "score_rationale": payload.get("score_rationale") or "",
        "matching_skills": payload.get("matching_skills") or [],
        "gaps": payload.get("gaps") or [],
        "application_tips": payload.get("application_tips") or "",
        "cover_letter_angle": payload.get("cover_letter_angle") or "",
        "observation": _normalize_observation(payload.get("observation")),
        "applied": bool(payload.get("applied", False)),
        "applied_at": payload.get("applied_at"),
        "notes": payload.get("notes") or "",
        "dismissed": bool(payload.get("dismissed", False)),
        "_qdrant_id": qdrant_id,
        "_vector": getattr(record, "vector", None),
        "_payload": payload,
    }
    return normalized


def _scroll_jobs(*, with_vectors: bool = False, collection_name: str = COLLECTION_JOBS) -> list[dict[str, Any]]:
    cache_ttl_seconds = _parse_float(
        os.getenv("RECALL_PHASE6_JOBS_CACHE_SECONDS"),
        default=DEFAULT_SCROLL_CACHE_SECONDS,
    )
    cache_key = (with_vectors, collection_name)
    if cache_ttl_seconds > 0:
        cached = _JOBS_SCROLL_CACHE.get(cache_key)
        if cached and cached[0] > time.time():
            return [dict(item) for item in cached[1]]

    client = qdrant_client_from_env(os.getenv("QDRANT_HOST", DEFAULT_QDRANT_HOST))
    points: list[Any] = []
    offset: Any = None
    while True:
        try:
            response = client.scroll(
                collection_name=collection_name,
                limit=SCROLL_PAGE_SIZE,
                offset=offset,
                with_payload=True,
                with_vectors=with_vectors,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to scroll jobs from Qdrant collection %s: %s", collection_name, exc)
            return []
        if isinstance(response, tuple) and len(response) == 2:
            records, offset = response
        else:
            records = getattr(response, "points", None)
            offset = getattr(response, "next_page_offset", None)
        if not records:
            break
        points.extend(records)
        if offset is None:
            break

    deduped: dict[str, dict[str, Any]] = {}
    for record in points:
        job = _normalize_job(record)
        key = str(job["jobId"])
        if key in deduped and deduped[key].get("fit_score", 0) >= job.get("fit_score", 0):
            continue
        deduped[key] = job
    rows = list(deduped.values())
    if cache_ttl_seconds > 0:
        _JOBS_SCROLL_CACHE[cache_key] = (time.time() + cache_ttl_seconds, [dict(item) for item in rows])
    return rows


def invalidate_jobs_cache() -> None:
    """Clear the in-memory jobs cache after mutations or config changes."""
    _JOBS_SCROLL_CACHE.clear()


def list_jobs(
    *,
    status: str | None = DEFAULT_STATUS_FILTER,
    min_score: int = 0,
    max_score: int = 100,
    company_tier: int | None = None,
    source: str | None = None,
    search: str | None = None,
    title_query: str | None = None,
    sort: str = "fit_score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    include_details: bool = True,
) -> dict[str, Any]:
    """List Phase 6 jobs with filtering, sorting, and pagination applied."""
    records = _scroll_jobs(with_vectors=False)

    normalized_status = str(status or "").strip().lower()
    if normalized_status == "all":
        normalized_status = ""
    normalized_source = str(source or "").strip().lower()
    normalized_search = str(search or "").strip().lower()
    normalized_title_query = str(title_query or "").strip().lower()
    effective_search = normalized_search or normalized_title_query

    filtered: list[dict[str, Any]] = []
    for item in records:
        if normalized_status and str(item.get("status", "")).strip().lower() != normalized_status:
            continue
        score = _parse_int(item.get("fit_score"), default=0)
        if score < min_score or score > max_score:
            continue
        if company_tier is not None and _parse_int(item.get("company_tier"), default=0) != company_tier:
            continue
        if normalized_source and str(item.get("source", "")).strip().lower() != normalized_source:
            continue
        if effective_search and not _matches_search(item, effective_search):
            continue
        filtered.append(item)

    reverse = str(order or "desc").strip().lower() != "asc"
    sort_key = str(sort or "fit_score").strip().lower()

    if sort_key == "discovered_at":
        filtered.sort(key=lambda item: _parse_datetime(item.get("discovered_at")) or datetime.min, reverse=reverse)
    elif sort_key == "company":
        filtered.sort(key=lambda item: str(item.get("company", "")).lower(), reverse=reverse)
    else:
        filtered.sort(key=lambda item: _parse_float(item.get("fit_score"), 0.0), reverse=reverse)

    total = len(filtered)
    page = filtered[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_sanitize_job(item, include_details=include_details) for item in page],
    }


def get_job(job_id: str) -> dict[str, Any] | None:
    """Return one sanitized job record by its stable job identifier."""
    target = str(job_id).strip()
    if not target:
        return None
    for item in _scroll_jobs(with_vectors=False):
        if str(item.get("jobId")) == target:
            return _sanitize_job(item)
    return None


def get_job_raw(job_id: str) -> dict[str, Any] | None:
    """Return one internal job record, including Qdrant update fields."""
    target = str(job_id).strip()
    if not target:
        return None
    for item in _scroll_jobs(with_vectors=True):
        if str(item.get("jobId")) == target:
            return item
    return None


def _point_for_update(*, models_module: Any, job: dict[str, Any]) -> Any:
    payload = dict(job.get("_payload") or {})
    payload.update(
        {
            "status": job.get("status"),
            "applied": bool(job.get("applied", False)),
            "dismissed": bool(job.get("dismissed", False)),
            "applied_at": job.get("applied_at"),
            "notes": job.get("notes"),
        }
    )
    vector = job.get("_vector")
    point_id = job.get("_qdrant_id")
    return models_module.PointStruct(id=point_id, vector=vector, payload=payload)


def update_job(
    *,
    job_id: str,
    status: str | None,
    applied: bool | None,
    dismissed: bool | None,
    notes: str | None,
) -> dict[str, Any] | None:
    """Persist status or note changes for a single Phase 6 job."""
    current = get_job_raw(job_id)
    if current is None:
        return None

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if status is not None:
        current["status"] = status
    if applied is not None:
        current["applied"] = bool(applied)
        if applied:
            current["applied_at"] = current.get("applied_at") or now
            current["status"] = "applied"
    if dismissed is not None:
        current["dismissed"] = bool(dismissed)
        if dismissed:
            current["status"] = "dismissed"
    if notes is not None:
        current["notes"] = notes

    from qdrant_client import models

    client = qdrant_client_from_env(os.getenv("QDRANT_HOST", DEFAULT_QDRANT_HOST))
    client.upsert(
        collection_name=COLLECTION_JOBS,
        points=[_point_for_update(models_module=models, job=current)],
    )
    invalidate_jobs_cache()
    refreshed = get_job(job_id)
    return refreshed


def update_company_tier(*, company_id: str, tier: int) -> int:
    """Update the stored tier value for every job associated with a company."""
    target = _to_slug(company_id)
    if not target:
        return 0

    rows = _scroll_jobs(with_vectors=True)
    if not rows:
        return 0

    from qdrant_client import models

    client = qdrant_client_from_env(os.getenv("QDRANT_HOST", DEFAULT_QDRANT_HOST))
    points: list[Any] = []
    updated = 0

    for item in rows:
        item_company_id = _to_slug(str(item.get("company_id") or item.get("company") or ""))
        if item_company_id != target:
            continue

        payload = dict(item.get("_payload") or {})
        payload["company_tier"] = int(tier)
        points.append(
            models.PointStruct(
                id=item.get("_qdrant_id"),
                vector=item.get("_vector"),
                payload=payload,
            )
        )
        updated += 1

    if not points:
        return 0

    for start in range(0, len(points), UPSERT_BATCH_SIZE):
        client.upsert(
            collection_name=COLLECTION_JOBS,
            points=points[start : start + UPSERT_BATCH_SIZE],
        )

    invalidate_jobs_cache()
    return updated


def job_stats() -> dict[str, Any]:
    """Summarize job volume, source mix, and fit-score distribution."""
    rows = _scroll_jobs(with_vectors=False)
    by_source: dict[str, int] = {}
    by_day: dict[str, int] = {}
    score_buckets = {"high": 0, "medium": 0, "low": 0, "unscored": 0}
    score_distribution = {"0-24": 0, "25-49": 0, "50-74": 0, "75-100": 0}
    total_scored = 0
    score_sum = 0
    new_today = 0
    now = datetime.now(timezone.utc)
    lookback = now - timedelta(hours=24)

    for item in rows:
        source = str(item.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1

        discovered = str(item.get("discovered_at") or "")
        discovered_day = discovered[:10] if len(discovered) >= 10 else "unknown"
        by_day[discovered_day] = by_day.get(discovered_day, 0) + 1

        discovered_at = _parse_datetime(item.get("discovered_at"))
        if discovered_at is not None:
            if discovered_at.tzinfo is None:
                discovered_at = discovered_at.replace(tzinfo=timezone.utc)
            if discovered_at >= lookback:
                new_today += 1

        score = _parse_int(item.get("fit_score"), default=-1)
        if score >= HIGH_FIT_THRESHOLD:
            score_buckets["high"] += 1
            score_distribution["75-100"] += 1
        elif score >= MEDIUM_FIT_THRESHOLD:
            score_buckets["medium"] += 1
            score_distribution["50-74"] += 1
        elif score >= 0:
            score_buckets["low"] += 1
            if score >= LOW_FIT_THRESHOLD:
                score_distribution["25-49"] += 1
            else:
                score_distribution["0-24"] += 1
        else:
            score_buckets["unscored"] += 1

        if score >= 0:
            total_scored += 1
            score_sum += score

    return {
        "total_jobs": len(rows),
        "new_today": new_today,
        "high_fit_count": score_buckets["high"],
        "average_fit_score": round(score_sum / total_scored, 1) if total_scored else 0.0,
        "score_ranges": score_buckets,
        "score_distribution": [
            {"range": key, "count": value}
            for key, value in score_distribution.items()
        ],
        "by_source": by_source,
        "by_day": by_day,
    }


def _sanitize_job(item: dict[str, Any], *, include_details: bool = True) -> dict[str, Any]:
    sanitized = dict(item)
    sanitized.pop("_qdrant_id", None)
    sanitized.pop("_vector", None)
    sanitized.pop("_payload", None)
    if not include_details:
        sanitized.pop("description", None)
        sanitized.pop("observation", None)
    return sanitized


def all_jobs() -> list[dict[str, Any]]:
    """Return every stored job in its sanitized API-friendly form."""
    return [_sanitize_job(item) for item in _scroll_jobs(with_vectors=False)]
