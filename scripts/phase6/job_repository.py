#!/usr/bin/env python3
"""Qdrant-backed read/update helpers for Phase 6 job endpoints."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from scripts.phase1.ingestion_pipeline import qdrant_client_from_env

COLLECTION_JOBS = "recall_jobs"
DEFAULT_STATUS_FILTER = "evaluated"


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
    client = qdrant_client_from_env(os.getenv("QDRANT_HOST", "http://localhost:6333"))
    points: list[Any] = []
    offset: Any = None
    while True:
        try:
            response = client.scroll(
                collection_name=collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=with_vectors,
            )
        except Exception:
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
    return list(deduped.values())


def list_jobs(
    *,
    status: str | None = DEFAULT_STATUS_FILTER,
    min_score: int = 0,
    max_score: int = 100,
    company_tier: int | None = None,
    source: str | None = None,
    title_query: str | None = None,
    sort: str = "fit_score",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    records = _scroll_jobs(with_vectors=False)

    normalized_status = str(status or "").strip().lower()
    normalized_source = str(source or "").strip().lower()
    normalized_title_query = str(title_query or "").strip().lower()

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
        if normalized_title_query and normalized_title_query not in str(item.get("title", "")).lower():
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
        "items": [_sanitize_job(item) for item in page],
    }


def get_job(job_id: str) -> dict[str, Any] | None:
    target = str(job_id).strip()
    if not target:
        return None
    for item in _scroll_jobs(with_vectors=False):
        if str(item.get("jobId")) == target:
            return _sanitize_job(item)
    return None


def get_job_raw(job_id: str) -> dict[str, Any] | None:
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


def update_job(*, job_id: str, status: str | None, applied: bool | None, dismissed: bool | None, notes: str | None) -> dict[str, Any] | None:
    current = get_job_raw(job_id)
    if current is None:
        return None

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
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

    client = qdrant_client_from_env(os.getenv("QDRANT_HOST", "http://localhost:6333"))
    client.upsert(
        collection_name=COLLECTION_JOBS,
        points=[_point_for_update(models_module=models, job=current)],
    )
    refreshed = get_job(job_id)
    return refreshed


def job_stats() -> dict[str, Any]:
    rows = _scroll_jobs(with_vectors=False)
    by_source: dict[str, int] = {}
    by_day: dict[str, int] = {}
    score_buckets = {"high": 0, "medium": 0, "low": 0, "unscored": 0}

    for item in rows:
        source = str(item.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1

        discovered = str(item.get("discovered_at") or "")
        discovered_day = discovered[:10] if len(discovered) >= 10 else "unknown"
        by_day[discovered_day] = by_day.get(discovered_day, 0) + 1

        score = _parse_int(item.get("fit_score"), default=-1)
        if score >= 75:
            score_buckets["high"] += 1
        elif score >= 50:
            score_buckets["medium"] += 1
        elif score >= 0:
            score_buckets["low"] += 1
        else:
            score_buckets["unscored"] += 1

    return {
        "total_jobs": len(rows),
        "score_ranges": score_buckets,
        "by_source": by_source,
        "by_day": by_day,
    }


def _sanitize_job(item: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(item)
    sanitized.pop("_qdrant_id", None)
    sanitized.pop("_vector", None)
    sanitized.pop("_payload", None)
    return sanitized


def all_jobs() -> list[dict[str, Any]]:
    return [_sanitize_job(item) for item in _scroll_jobs(with_vectors=False)]
