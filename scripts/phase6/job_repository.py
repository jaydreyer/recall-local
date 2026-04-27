#!/usr/bin/env python3
"""Qdrant-backed read/update helpers for Phase 6 job endpoints."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from scripts.phase1.ingestion_pipeline import qdrant_client_from_env
from scripts.shared_strings import slugify

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
DEFAULT_WORKFLOW_PACKET = {
    "tailoredSummary": False,
    "resumeBullets": False,
    "coverLetterDraft": False,
    "outreachNote": False,
    "interviewBrief": False,
    "talkingPoints": False,
}
DEFAULT_WORKFLOW_ARTIFACTS = {
    "coverLetterDraft": {
        "draftId": None,
        "generatedAt": None,
        "provider": None,
        "model": None,
        "wordCount": None,
        "savedToVault": False,
        "vaultPath": None,
    },
    "tailoredSummary": {
        "status": None,
        "updatedAt": None,
        "source": None,
        "vaultPath": None,
        "notes": None,
    },
    "resumeBullets": {
        "status": None,
        "updatedAt": None,
        "source": None,
        "vaultPath": None,
        "notes": None,
    },
    "outreachNote": {
        "status": None,
        "updatedAt": None,
        "source": None,
        "vaultPath": None,
        "notes": None,
    },
    "interviewBrief": {
        "status": None,
        "updatedAt": None,
        "source": None,
        "vaultPath": None,
        "notes": None,
    },
    "talkingPoints": {
        "status": None,
        "updatedAt": None,
        "source": None,
        "vaultPath": None,
        "notes": None,
    },
}
DEFAULT_WORKFLOW_FOLLOW_UP = {
    "status": "not_scheduled",
    "dueAt": None,
    "lastCompletedAt": None,
    "reminder": {
        "created": False,
        "status": "not_created",
        "channel": None,
        "lastRunAt": None,
        "deliveredAt": None,
        "automationId": None,
        "notes": None,
    },
}
DEFAULT_WORKFLOW_NEXT_ACTION = {
    "action": None,
    "rationale": None,
    "confidence": None,
    "dueAt": None,
}
PACKET_REQUIRED_KEYS = ("tailoredSummary", "resumeBullets", "coverLetterDraft")
WORKFLOW_STAGES = {"focus", "review", "follow_up", "monitor", "closed"}
WORKFLOW_FOLLOW_UP_STATUSES = {"not_scheduled", "scheduled", "completed"}
WORKFLOW_FOLLOW_UP_REMINDER_STATUSES = {"not_created", "queued", "sent", "failed"}
WORKFLOW_FOLLOW_UP_REMINDER_CHANNELS = {"manual", "n8n", "email", "calendar"}
WORKFLOW_NEXT_ACTIONS = {
    "none",
    "review_role",
    "tailor_resume",
    "hold",
    "skip",
    "follow_up",
    "monitor_response",
    "schedule_follow_up",
    "send_follow_up",
}
WORKFLOW_NEXT_ACTION_CONFIDENCE = {"low", "medium", "high"}
PACKET_ARTIFACT_KEYS = ("tailoredSummary", "resumeBullets", "outreachNote", "interviewBrief", "talkingPoints")
WORKFLOW_PACKET_ARTIFACT_STATUSES = {"draft", "ready"}
WORKFLOW_PACKET_ARTIFACT_SOURCES = {"manual", "generated", "imported"}
WORKFLOW_EVENT_CATEGORIES = {"application", "workflow", "approval", "packet", "follow_up", "artifact", "system"}
WORKFLOW_EVENT_ORIGINS = {"persisted", "derived"}


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


def _default_workflow_stage(*, status: str | None, fit_score: Any, applied: Any, dismissed: Any) -> str:
    normalized_status = str(status or "").strip().lower()
    if bool(dismissed) or normalized_status in {"dismissed", "expired"}:
        return "closed"
    if bool(applied) or normalized_status == "applied":
        return "follow_up"
    score = _parse_int(fit_score, default=-1)
    if normalized_status == "new" or score < 0:
        return "review"
    if score >= HIGH_FIT_THRESHOLD:
        return "focus"
    return "monitor"


def _normalize_workflow(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    packet = source.get("packet") if isinstance(source.get("packet"), dict) else {}
    artifacts = source.get("artifacts") if isinstance(source.get("artifacts"), dict) else {}
    next_action = source.get("nextAction") if isinstance(source.get("nextAction"), dict) else {}
    follow_up = source.get("followUp") if isinstance(source.get("followUp"), dict) else {}
    stage = str(source.get("stage") or "").strip().lower()
    follow_up_status = str(follow_up.get("status") or "").strip().lower()
    return {
        "stage": stage if stage in WORKFLOW_STAGES else None,
        "nextActionApproval": "approved"
        if str(source.get("nextActionApproval")).strip().lower() == "approved"
        else "pending",
        "packetApproval": "approved" if str(source.get("packetApproval")).strip().lower() == "approved" else "pending",
        "packet": {key: bool(packet.get(key, default)) for key, default in DEFAULT_WORKFLOW_PACKET.items()},
        "nextAction": _normalize_next_action(next_action),
        "artifacts": _normalize_workflow_artifacts(artifacts),
        "followUp": {
            "status": follow_up_status
            if follow_up_status in WORKFLOW_FOLLOW_UP_STATUSES
            else DEFAULT_WORKFLOW_FOLLOW_UP["status"],
            "dueAt": str(follow_up.get("dueAt") or "").strip() or None,
            "lastCompletedAt": str(follow_up.get("lastCompletedAt") or "").strip() or None,
            "reminder": _normalize_follow_up_reminder(follow_up.get("reminder")),
        },
        "updatedAt": str(source.get("updatedAt") or "").strip() or None,
    }


def _normalize_workflow_patch(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized: dict[str, Any] = {}
    if "stage" in source:
        stage = str(source.get("stage") or "").strip().lower()
        if stage in WORKFLOW_STAGES:
            normalized["stage"] = stage
    if "nextActionApproval" in source:
        normalized["nextActionApproval"] = (
            "approved" if str(source.get("nextActionApproval")).strip().lower() == "approved" else "pending"
        )
    if "packetApproval" in source:
        normalized["packetApproval"] = (
            "approved" if str(source.get("packetApproval")).strip().lower() == "approved" else "pending"
        )
    if isinstance(source.get("packet"), dict):
        normalized["packet"] = {
            key: bool(value) for key, value in source["packet"].items() if key in DEFAULT_WORKFLOW_PACKET
        }
    if isinstance(source.get("nextAction"), dict):
        normalized["nextAction"] = _normalize_next_action(source.get("nextAction"))
    if isinstance(source.get("artifacts"), dict):
        artifacts = source["artifacts"]
        next_artifacts: dict[str, Any] = {}
        if "coverLetterDraft" in artifacts:
            next_artifacts["coverLetterDraft"] = _normalize_cover_letter_artifact(artifacts.get("coverLetterDraft"))
        for key in PACKET_ARTIFACT_KEYS:
            if key in artifacts:
                next_artifacts[key] = _normalize_packet_artifact(artifacts.get(key), key=key)
        normalized["artifacts"] = next_artifacts
    if isinstance(source.get("followUp"), dict):
        follow_up = source["followUp"]
        next_follow_up: dict[str, Any] = {}
        if "status" in follow_up:
            status = str(follow_up.get("status") or "").strip().lower()
            if status in WORKFLOW_FOLLOW_UP_STATUSES:
                next_follow_up["status"] = status
        if "dueAt" in follow_up:
            next_follow_up["dueAt"] = str(follow_up.get("dueAt") or "").strip() or None
        if "lastCompletedAt" in follow_up:
            next_follow_up["lastCompletedAt"] = str(follow_up.get("lastCompletedAt") or "").strip() or None
        if isinstance(follow_up.get("reminder"), dict):
            next_follow_up["reminder"] = _normalize_follow_up_reminder_patch(follow_up.get("reminder"))
        normalized["followUp"] = next_follow_up
    return normalized


def _workflow_event_category(event_type: str) -> str:
    normalized = str(event_type or "").strip().lower()
    if normalized in {"applied", "application_recorded", "status_updated"}:
        return "application"
    if normalized in {"next_action_approved", "next_action_pending", "packet_approved", "packet_pending"}:
        return "approval"
    if normalized.startswith("packet_"):
        return "packet"
    if normalized.startswith("follow_up_"):
        return "follow_up"
    if normalized in {"cover_letter_generated", "packet_artifact_updated"}:
        return "artifact"
    if normalized in {"stage_changed"}:
        return "workflow"
    return "system"


def _workflow_event_tone(*, event_type: str, category: str) -> str:
    normalized_type = str(event_type or "").strip().lower()
    normalized_category = str(category or "").strip().lower()
    if normalized_type.endswith("_approved") or normalized_type.endswith("_completed"):
        return "complete"
    if normalized_type.endswith("_sent"):
        return "complete"
    if normalized_type.endswith("_pending") or normalized_type.endswith("_scheduled"):
        return "pending"
    if normalized_type.endswith("_queued"):
        return "pending"
    if normalized_type.endswith("_reopened") or normalized_type.endswith("_cleared"):
        return "warning"
    if normalized_type.endswith("_failed"):
        return "warning"
    if normalized_category in {"artifact", "packet"}:
        return "pending"
    if normalized_category == "application":
        return "default"
    return "default"


def _normalize_workflow_timeline(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    events: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        event_type = str(item.get("type") or "").strip()
        at = str(item.get("at") or "").strip()
        if not label or not event_type or not at:
            continue
        detail = str(item.get("detail") or "").strip()
        events.append(
            {
                "type": event_type,
                "label": label,
                "detail": detail or None,
                "at": at,
                "category": (
                    str(item.get("category") or "").strip().lower()
                    if str(item.get("category") or "").strip().lower() in WORKFLOW_EVENT_CATEGORIES
                    else _workflow_event_category(event_type)
                ),
                "origin": (
                    str(item.get("origin") or "").strip().lower()
                    if str(item.get("origin") or "").strip().lower() in WORKFLOW_EVENT_ORIGINS
                    else "persisted"
                ),
                "tone": (
                    str(item.get("tone") or "").strip().lower()
                    if str(item.get("tone") or "").strip().lower()
                    in {"default", "pending", "warning", "complete", "muted"}
                    else _workflow_event_tone(
                        event_type=event_type,
                        category=(
                            str(item.get("category") or "").strip().lower()
                            if str(item.get("category") or "").strip().lower() in WORKFLOW_EVENT_CATEGORIES
                            else _workflow_event_category(event_type)
                        ),
                    )
                ),
            }
        )
    return events


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
                job.get("evaluation_error"),
                job.get("notes"),
                job.get("observation"),
            ]
        )
    ).lower()
    return normalized_query in haystack


def _to_slug(value: str) -> str:
    return slugify(value, fallback="unknown")


def _normalize_job(record: Any) -> dict[str, Any]:
    payload = dict(getattr(record, "payload", {}) or {})
    qdrant_id = str(getattr(record, "id", ""))
    job_id = str(payload.get("job_id") or payload.get("doc_id") or qdrant_id)
    company = str(payload.get("company") or "")
    workflow = _normalize_workflow(payload.get("workflow"))
    workflow["stage"] = workflow.get("stage") or _default_workflow_stage(
        status=payload.get("status"),
        fit_score=payload.get("fit_score"),
        applied=payload.get("applied"),
        dismissed=payload.get("dismissed"),
    )
    workflow["packetReadiness"] = _workflow_packet_readiness(workflow)
    workflow_timeline = _normalize_workflow_timeline(payload.get("workflow_timeline"))
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
        "evaluation_error": payload.get("evaluation_error") or None,
        "observation": _normalize_observation(payload.get("observation")),
        "applied": bool(payload.get("applied", False)),
        "applied_at": payload.get("applied_at"),
        "notes": payload.get("notes") or "",
        "dismissed": bool(payload.get("dismissed", False)),
        "workflow": workflow,
        "workflowTimeline": workflow_timeline,
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
            "workflow": _normalize_workflow(job.get("workflow")),
            "workflow_timeline": _normalize_workflow_timeline(job.get("workflowTimeline")),
        }
    )
    vector = job.get("_vector")
    point_id = job.get("_qdrant_id")
    return models_module.PointStruct(id=point_id, vector=vector, payload=payload)


def _workflow_event(
    *,
    event_type: str,
    label: str,
    at: str,
    detail: str | None = None,
    category: str | None = None,
    origin: str = "persisted",
    tone: str | None = None,
) -> dict[str, Any]:
    event_category = category if category in WORKFLOW_EVENT_CATEGORIES else _workflow_event_category(event_type)
    return {
        "type": event_type,
        "label": label,
        "detail": detail or None,
        "at": at,
        "category": event_category,
        "origin": origin if origin in WORKFLOW_EVENT_ORIGINS else "persisted",
        "tone": tone or _workflow_event_tone(event_type=event_type, category=event_category),
    }


def _workflow_packet_label(key: str) -> str:
    labels = {
        "tailoredSummary": "Tailored summary",
        "resumeBullets": "Resume bullets",
        "coverLetterDraft": "Cover letter draft",
        "outreachNote": "Outreach note",
        "interviewBrief": "Interview brief",
        "talkingPoints": "Talking points",
    }
    return labels.get(key, key)


def _workflow_stage_label(stage: str) -> str:
    labels = {
        "focus": "Focus",
        "review": "Review",
        "follow_up": "Follow-up",
        "monitor": "Monitor",
        "closed": "Closed",
    }
    return labels.get(stage, stage.replace("_", " ").title())


def _timeline_datetime_label(value: str | None) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return str(value or "").strip()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%b %-d, %Y at %-I:%M %p UTC")


def _default_follow_up_due_at(now: datetime) -> str:
    return (now + timedelta(days=5)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_follow_up_reminder(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    status = str(source.get("status") or "").strip().lower()
    channel = str(source.get("channel") or "").strip().lower()
    normalized = dict(DEFAULT_WORKFLOW_FOLLOW_UP["reminder"])
    normalized.update(
        {
            "created": bool(source.get("created", False)),
            "status": status
            if status in WORKFLOW_FOLLOW_UP_REMINDER_STATUSES
            else DEFAULT_WORKFLOW_FOLLOW_UP["reminder"]["status"],
            "channel": channel if channel in WORKFLOW_FOLLOW_UP_REMINDER_CHANNELS else None,
            "lastRunAt": str(source.get("lastRunAt") or "").strip() or None,
            "deliveredAt": str(source.get("deliveredAt") or "").strip() or None,
            "automationId": str(source.get("automationId") or "").strip() or None,
            "notes": str(source.get("notes") or "").strip() or None,
        }
    )
    if (
        normalized["status"] != "not_created"
        or normalized["channel"]
        or normalized["lastRunAt"]
        or normalized["deliveredAt"]
        or normalized["automationId"]
        or normalized["notes"]
    ):
        normalized["created"] = True
    if not normalized["created"]:
        normalized["status"] = "not_created"
    return normalized


def _normalize_follow_up_reminder_patch(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized: dict[str, Any] = {}
    if "created" in source:
        normalized["created"] = bool(source.get("created"))
    if "status" in source:
        status = str(source.get("status") or "").strip().lower()
        if status in WORKFLOW_FOLLOW_UP_REMINDER_STATUSES:
            normalized["status"] = status
    if "channel" in source:
        channel = str(source.get("channel") or "").strip().lower()
        normalized["channel"] = channel if channel in WORKFLOW_FOLLOW_UP_REMINDER_CHANNELS else None
    if "lastRunAt" in source:
        normalized["lastRunAt"] = str(source.get("lastRunAt") or "").strip() or None
    if "deliveredAt" in source:
        normalized["deliveredAt"] = str(source.get("deliveredAt") or "").strip() or None
    if "automationId" in source:
        normalized["automationId"] = str(source.get("automationId") or "").strip() or None
    if "notes" in source:
        normalized["notes"] = str(source.get("notes") or "").strip() or None
    return normalized


def _normalize_follow_up_state(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized = {
        "status": str(source.get("status") or DEFAULT_WORKFLOW_FOLLOW_UP["status"]).strip().lower(),
        "dueAt": str(source.get("dueAt") or "").strip() or None,
        "lastCompletedAt": str(source.get("lastCompletedAt") or "").strip() or None,
        "reminder": _normalize_follow_up_reminder(source.get("reminder")),
    }
    if normalized["status"] not in WORKFLOW_FOLLOW_UP_STATUSES:
        normalized["status"] = DEFAULT_WORKFLOW_FOLLOW_UP["status"]
    return normalized


def _follow_up_reminder_detail(reminder: dict[str, Any]) -> str | None:
    detail_parts = []
    if reminder.get("channel"):
        detail_parts.append(f"Channel: {reminder['channel']}")
    if reminder.get("automationId"):
        detail_parts.append(f"Automation: {reminder['automationId']}")
    if reminder.get("deliveredAt"):
        detail_parts.append(f"Delivered {_timeline_datetime_label(reminder['deliveredAt'])}")
    elif reminder.get("lastRunAt"):
        detail_parts.append(f"Last run {_timeline_datetime_label(reminder['lastRunAt'])}")
    if reminder.get("notes"):
        detail_parts.append(str(reminder["notes"]))
    return " | ".join(detail_parts) if detail_parts else None


def _normalize_cover_letter_artifact(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized = dict(DEFAULT_WORKFLOW_ARTIFACTS["coverLetterDraft"])
    normalized.update(
        {
            "draftId": str(source.get("draftId") or "").strip() or None,
            "generatedAt": str(source.get("generatedAt") or "").strip() or None,
            "provider": str(source.get("provider") or "").strip() or None,
            "model": str(source.get("model") or "").strip() or None,
            "wordCount": _parse_int(source.get("wordCount"), default=0) or None,
            "savedToVault": bool(source.get("savedToVault", False)),
            "vaultPath": str(source.get("vaultPath") or "").strip() or None,
        }
    )
    return normalized


def _normalize_packet_artifact(value: Any, *, key: str) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized = dict(DEFAULT_WORKFLOW_ARTIFACTS[key])
    status = str(source.get("status") or "").strip().lower()
    source_value = str(source.get("source") or "").strip().lower()
    normalized.update(
        {
            "status": status if status in WORKFLOW_PACKET_ARTIFACT_STATUSES else None,
            "updatedAt": str(source.get("updatedAt") or "").strip() or None,
            "source": source_value if source_value in WORKFLOW_PACKET_ARTIFACT_SOURCES else None,
            "vaultPath": str(source.get("vaultPath") or "").strip() or None,
            "notes": str(source.get("notes") or "").strip() or None,
        }
    )
    return normalized


def _normalize_workflow_artifacts(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized = {
        "coverLetterDraft": _normalize_cover_letter_artifact(source.get("coverLetterDraft")),
    }
    for key in PACKET_ARTIFACT_KEYS:
        normalized[key] = _normalize_packet_artifact(source.get(key), key=key)
    return normalized


def _normalize_next_action(value: Any) -> dict[str, Any]:
    source = dict(value) if isinstance(value, dict) else {}
    normalized = dict(DEFAULT_WORKFLOW_NEXT_ACTION)
    action = str(source.get("action") or "").strip().lower()
    confidence = str(source.get("confidence") or "").strip().lower()
    normalized.update(
        {
            "action": action if action in WORKFLOW_NEXT_ACTIONS else None,
            "rationale": str(source.get("rationale") or "").strip() or None,
            "confidence": confidence if confidence in WORKFLOW_NEXT_ACTION_CONFIDENCE else None,
            "dueAt": str(source.get("dueAt") or "").strip() or None,
        }
    )
    return normalized


def _artifact_available(*, key: str, artifacts: dict[str, Any]) -> bool:
    if key == "coverLetterDraft":
        artifact = _normalize_cover_letter_artifact(artifacts.get("coverLetterDraft"))
        return bool(artifact.get("generatedAt") or artifact.get("draftId") or artifact.get("vaultPath"))
    artifact = _normalize_packet_artifact(artifacts.get(key), key=key)
    return bool(
        artifact.get("updatedAt") or artifact.get("vaultPath") or artifact.get("notes") or artifact.get("status")
    )


def _workflow_packet_readiness(value: Any) -> dict[str, Any]:
    workflow = _normalize_workflow(value)
    packet = workflow.get("packet", {})
    artifacts = workflow.get("artifacts", {})
    checked_items = [key for key in DEFAULT_WORKFLOW_PACKET if bool(packet.get(key))]
    linked_items = [key for key in DEFAULT_WORKFLOW_PACKET if _artifact_available(key=key, artifacts=artifacts)]
    verified_items = [
        key
        for key in DEFAULT_WORKFLOW_PACKET
        if bool(packet.get(key)) and _artifact_available(key=key, artifacts=artifacts)
    ]
    checked_without_artifact = [
        key for key in DEFAULT_WORKFLOW_PACKET if bool(packet.get(key)) and key not in verified_items
    ]
    artifact_without_checklist = [
        key
        for key in DEFAULT_WORKFLOW_PACKET
        if _artifact_available(key=key, artifacts=artifacts) and not bool(packet.get(key))
    ]
    ready_for_approval = all(key in verified_items for key in PACKET_REQUIRED_KEYS)
    return {
        "totalItems": len(DEFAULT_WORKFLOW_PACKET),
        "requiredItems": list(PACKET_REQUIRED_KEYS),
        "checkedItems": checked_items,
        "linkedItems": linked_items,
        "verifiedItems": verified_items,
        "checkedWithoutArtifact": checked_without_artifact,
        "artifactWithoutChecklist": artifact_without_checklist,
        "missingItems": [key for key in DEFAULT_WORKFLOW_PACKET if key not in set(checked_items) | set(linked_items)],
        "counts": {
            "checked": len(checked_items),
            "linked": len(linked_items),
            "verified": len(verified_items),
            "requiredVerified": len([key for key in PACKET_REQUIRED_KEYS if key in verified_items]),
        },
        "readyForApproval": ready_for_approval,
    }


def _append_workflow_event(
    timeline: list[dict[str, Any]],
    *,
    event_type: str,
    label: str,
    at: str,
    detail: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    next_timeline = list(timeline)
    candidate = _workflow_event(event_type=event_type, label=label, at=at, detail=detail, category=category)
    if (
        next_timeline
        and next_timeline[-1].get("type") == candidate["type"]
        and next_timeline[-1].get("label") == candidate["label"]
        and next_timeline[-1].get("detail") == candidate["detail"]
    ):
        return next_timeline
    next_timeline.append(candidate)
    return next_timeline


def update_job(
    *,
    job_id: str,
    status: str | None,
    applied: bool | None,
    dismissed: bool | None,
    notes: str | None,
    workflow: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Persist status or note changes for a single Phase 6 job."""
    current = get_job_raw(job_id)
    if current is None:
        return None

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    current["workflow"] = _normalize_workflow(current.get("workflow"))
    current["workflow"]["stage"] = current["workflow"].get("stage") or _default_workflow_stage(
        status=current.get("status"),
        fit_score=current.get("fit_score"),
        applied=current.get("applied"),
        dismissed=current.get("dismissed"),
    )
    current["workflowTimeline"] = _normalize_workflow_timeline(current.get("workflowTimeline"))
    if status is not None:
        current["status"] = status
        current["workflow"]["updatedAt"] = now
        if status == "applied":
            current["workflow"]["stage"] = "follow_up"
            follow_up = _normalize_follow_up_state(current["workflow"].get("followUp"))
            if follow_up.get("status") == "not_scheduled" and not follow_up.get("dueAt"):
                follow_up["status"] = "scheduled"
                follow_up["dueAt"] = _default_follow_up_due_at(datetime.now(timezone.utc))
                current["workflow"]["followUp"] = follow_up
                current["workflowTimeline"] = _append_workflow_event(
                    current["workflowTimeline"],
                    event_type="follow_up_scheduled",
                    label="Follow-up scheduled",
                    detail=f"Due {_timeline_datetime_label(follow_up['dueAt'])}",
                    at=now,
                    category="follow_up",
                )
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="application_recorded",
                label="Application recorded",
                at=now,
                category="application",
            )
        elif status in {"dismissed", "expired"}:
            current["workflow"]["stage"] = "closed"
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="status_updated",
                label=f"Role marked {status.replace('_', ' ')}",
                at=now,
                category="application",
            )
        elif status != "applied":
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="status_updated",
                label=f"Status changed to {status.replace('_', ' ')}",
                at=now,
                category="application",
            )
    if applied is not None:
        current["applied"] = bool(applied)
        current["workflow"]["updatedAt"] = now
        if applied:
            current["applied_at"] = current.get("applied_at") or now
            current["status"] = "applied"
            current["workflow"]["stage"] = "follow_up"
            follow_up = _normalize_follow_up_state(current["workflow"].get("followUp"))
            if follow_up.get("status") == "not_scheduled" and not follow_up.get("dueAt"):
                follow_up["status"] = "scheduled"
                follow_up["dueAt"] = _default_follow_up_due_at(datetime.now(timezone.utc))
                current["workflow"]["followUp"] = follow_up
                current["workflowTimeline"] = _append_workflow_event(
                    current["workflowTimeline"],
                    event_type="follow_up_scheduled",
                    label="Follow-up scheduled",
                    detail=f"Due {_timeline_datetime_label(follow_up['dueAt'])}",
                    at=now,
                    category="follow_up",
                )
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="application_recorded",
                label="Application recorded",
                at=now,
                category="application",
            )
    if dismissed is not None:
        current["dismissed"] = bool(dismissed)
        current["workflow"]["updatedAt"] = now
        if dismissed:
            current["status"] = "dismissed"
            current["workflow"]["stage"] = "closed"
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="dismissed",
                label="Role dismissed",
                at=now,
                category="application",
            )
    if notes is not None:
        current["notes"] = notes
    if workflow is not None:
        existing_workflow = _normalize_workflow(current.get("workflow"))
        incoming_workflow = _normalize_workflow_patch(workflow)
        merged_packet = {
            **existing_workflow.get("packet", {}),
            **incoming_workflow.get("packet", {}),
        }
        merged_next_action = {
            **_normalize_next_action(existing_workflow.get("nextAction")),
            **incoming_workflow.get("nextAction", {}),
        }
        merged_artifacts = {
            **existing_workflow.get("artifacts", {}),
            **incoming_workflow.get("artifacts", {}),
        }
        merged_artifacts = _normalize_workflow_artifacts(merged_artifacts)
        merged_follow_up = {
            **_normalize_follow_up_state(existing_workflow.get("followUp")),
            **incoming_workflow.get("followUp", {}),
        }
        if "reminder" in incoming_workflow.get("followUp", {}):
            merged_follow_up["reminder"] = {
                **_normalize_follow_up_reminder(
                    _normalize_follow_up_state(existing_workflow.get("followUp")).get("reminder")
                ),
                **incoming_workflow.get("followUp", {}).get("reminder", {}),
            }
            merged_follow_up["reminder"] = _normalize_follow_up_reminder(merged_follow_up.get("reminder"))
        next_workflow = {
            **existing_workflow,
            **incoming_workflow,
            "packet": merged_packet,
            "nextAction": _normalize_next_action(merged_next_action),
            "artifacts": merged_artifacts,
            "followUp": merged_follow_up,
            "updatedAt": now,
        }
        if next_workflow["followUp"].get("status") == "completed" and not next_workflow["followUp"].get(
            "lastCompletedAt"
        ):
            next_workflow["followUp"]["lastCompletedAt"] = now
        if next_workflow["followUp"].get("status") == "completed":
            next_workflow["followUp"]["dueAt"] = None

        if existing_workflow.get("nextActionApproval") != next_workflow.get("nextActionApproval"):
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="next_action_approved"
                if next_workflow.get("nextActionApproval") == "approved"
                else "next_action_pending",
                label="Next action approved"
                if next_workflow.get("nextActionApproval") == "approved"
                else "Next action sent back for review",
                at=now,
                category="approval",
            )
        existing_next_action = _normalize_next_action(existing_workflow.get("nextAction"))
        next_next_action = _normalize_next_action(next_workflow.get("nextAction"))
        if existing_next_action != next_next_action and next_next_action.get("action"):
            detail_parts = []
            if next_next_action.get("confidence"):
                detail_parts.append(f"Confidence: {next_next_action['confidence']}")
            if next_next_action.get("dueAt"):
                detail_parts.append(f"Due {_timeline_datetime_label(next_next_action['dueAt'])}")
            if next_next_action.get("rationale"):
                detail_parts.append(next_next_action["rationale"])
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="next_action_updated",
                label=f"Next action set to {str(next_next_action['action']).replace('_', ' ')}",
                detail=" | ".join(detail_parts) if detail_parts else None,
                at=now,
                category="workflow",
            )
        if existing_workflow.get("packetApproval") != next_workflow.get("packetApproval"):
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="packet_approved" if next_workflow.get("packetApproval") == "approved" else "packet_pending",
                label="Packet approved"
                if next_workflow.get("packetApproval") == "approved"
                else "Packet returned to draft state",
                at=now,
                category="approval",
            )
        if existing_workflow.get("stage") != next_workflow.get("stage") and next_workflow.get("stage"):
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="stage_changed",
                label=f"Moved to {_workflow_stage_label(str(next_workflow['stage']))} lane",
                detail=(
                    f"Previous lane: {_workflow_stage_label(str(existing_workflow.get('stage') or 'review'))}"
                    if existing_workflow.get("stage")
                    else None
                ),
                at=now,
                category="workflow",
            )
        for key, value in merged_packet.items():
            previous_value = bool(existing_workflow.get("packet", {}).get(key))
            if previous_value == bool(value):
                continue
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="packet_item_completed" if value else "packet_item_reopened",
                label=f"{_workflow_packet_label(key)} completed"
                if value
                else f"{_workflow_packet_label(key)} reopened",
                at=now,
                category="packet",
            )
        existing_artifacts = existing_workflow.get("artifacts", {})
        next_artifacts = next_workflow.get("artifacts", {})
        existing_cover_letter = _normalize_cover_letter_artifact(existing_artifacts.get("coverLetterDraft"))
        next_cover_letter = _normalize_cover_letter_artifact(next_artifacts.get("coverLetterDraft"))
        if next_cover_letter.get("generatedAt") and (
            existing_cover_letter.get("generatedAt") != next_cover_letter.get("generatedAt")
            or existing_cover_letter.get("draftId") != next_cover_letter.get("draftId")
        ):
            detail_parts = []
            if next_cover_letter.get("provider") and next_cover_letter.get("model"):
                detail_parts.append(f"{next_cover_letter['provider']} · {next_cover_letter['model']}")
            if next_cover_letter.get("wordCount"):
                detail_parts.append(f"{next_cover_letter['wordCount']} words")
            if next_cover_letter.get("savedToVault") and next_cover_letter.get("vaultPath"):
                detail_parts.append(f"Saved to {next_cover_letter['vaultPath']}")
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="cover_letter_generated",
                label="Cover letter draft generated",
                detail=" | ".join(detail_parts) if detail_parts else None,
                at=next_cover_letter.get("generatedAt") or now,
                category="artifact",
            )
        for key in PACKET_ARTIFACT_KEYS:
            existing_artifact = _normalize_packet_artifact(existing_artifacts.get(key), key=key)
            next_artifact = _normalize_packet_artifact(next_artifacts.get(key), key=key)
            if existing_artifact == next_artifact:
                continue
            if not (next_artifact.get("updatedAt") or next_artifact.get("vaultPath") or next_artifact.get("notes")):
                continue
            detail_parts = []
            if next_artifact.get("status"):
                detail_parts.append(f"Status: {next_artifact['status']}")
            if next_artifact.get("source"):
                detail_parts.append(f"Source: {next_artifact['source']}")
            if next_artifact.get("vaultPath"):
                detail_parts.append(f"Path: {next_artifact['vaultPath']}")
            if next_artifact.get("notes"):
                detail_parts.append(next_artifact["notes"])
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="packet_artifact_updated",
                label=f"{_workflow_packet_label(key)} artifact linked",
                detail=" | ".join(detail_parts) if detail_parts else None,
                at=next_artifact.get("updatedAt") or now,
                category="artifact",
            )
        existing_follow_up = _normalize_follow_up_state(existing_workflow.get("followUp"))
        next_follow_up = _normalize_follow_up_state(next_workflow.get("followUp"))
        if existing_follow_up.get("dueAt") != next_follow_up.get("dueAt") and next_follow_up.get("dueAt"):
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="follow_up_scheduled",
                label="Follow-up scheduled",
                detail=f"Due {_timeline_datetime_label(next_follow_up['dueAt'])}",
                at=now,
                category="follow_up",
            )
        elif (
            existing_follow_up.get("dueAt")
            and not next_follow_up.get("dueAt")
            and next_follow_up.get("status") == "not_scheduled"
        ):
            current["workflowTimeline"] = _append_workflow_event(
                current["workflowTimeline"],
                event_type="follow_up_cleared",
                label="Follow-up cleared",
                at=now,
                category="follow_up",
            )
        if existing_follow_up.get("status") != next_follow_up.get("status"):
            if next_follow_up.get("status") == "completed":
                current["workflowTimeline"] = _append_workflow_event(
                    current["workflowTimeline"],
                    event_type="follow_up_completed",
                    label="Follow-up completed",
                    detail=(f"Completed {_timeline_datetime_label(next_follow_up.get('lastCompletedAt') or now)}"),
                    at=now,
                    category="follow_up",
                )
            elif existing_follow_up.get("status") == "completed":
                current["workflowTimeline"] = _append_workflow_event(
                    current["workflowTimeline"],
                    event_type="follow_up_reopened",
                    label="Follow-up reopened",
                    at=now,
                    category="follow_up",
                )
        existing_reminder = _normalize_follow_up_reminder(existing_follow_up.get("reminder"))
        next_reminder = _normalize_follow_up_reminder(next_follow_up.get("reminder"))
        if existing_reminder != next_reminder:
            reminder_event_type = None
            reminder_label = None
            if existing_reminder.get("status") != next_reminder.get("status"):
                reminder_status_events = {
                    "queued": ("follow_up_reminder_queued", "Follow-up reminder queued"),
                    "sent": ("follow_up_reminder_sent", "Follow-up reminder sent"),
                    "failed": ("follow_up_reminder_failed", "Follow-up reminder failed"),
                    "not_created": ("follow_up_reminder_cleared", "Follow-up reminder cleared"),
                }
                reminder_event_type, reminder_label = reminder_status_events.get(
                    str(next_reminder.get("status") or ""),
                    ("follow_up_reminder_created", "Follow-up reminder created"),
                )
            elif not existing_reminder.get("created") and next_reminder.get("created"):
                reminder_event_type, reminder_label = ("follow_up_reminder_created", "Follow-up reminder created")
            elif existing_reminder.get("lastRunAt") != next_reminder.get("lastRunAt") and next_reminder.get(
                "lastRunAt"
            ):
                reminder_event_type, reminder_label = (
                    "follow_up_reminder_run_recorded",
                    "Follow-up reminder run recorded",
                )
            if reminder_event_type and reminder_label:
                current["workflowTimeline"] = _append_workflow_event(
                    current["workflowTimeline"],
                    event_type=reminder_event_type,
                    label=reminder_label,
                    detail=_follow_up_reminder_detail(next_reminder),
                    at=next_reminder.get("lastRunAt") or next_reminder.get("deliveredAt") or now,
                    category="follow_up",
                )

        current["workflow"] = next_workflow

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
        "score_distribution": [{"range": key, "count": value} for key, value in score_distribution.items()],
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
