#!/usr/bin/env python3
"""Reminder selection and payload helpers for Phase 6 follow-up automation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from scripts.phase6.job_repository import all_jobs, update_job

DEFAULT_FOLLOW_UP_REMINDER_AUTOMATION_ID = "phase6-follow-up-reminder"
ELIGIBLE_REMINDER_STATUSES = {"not_created", "failed"}
EXPLICIT_RUN_REMINDER_STATUSES = {"not_created", "queued", "failed"}


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _first_sentence(value: Any) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    for marker in (". ", "! ", "? "):
        if marker in text:
            return text.split(marker, 1)[0].strip() + marker.strip()
    return text


def _format_due_label(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return "an unscheduled time"
    return parsed.strftime("%b %-d at %-I:%M %p UTC")


def build_follow_up_reminder_text(job: dict[str, Any]) -> str:
    title = _normalize_text(job.get("title")) or "Unknown role"
    company = _normalize_text(job.get("company")) or "Unknown company"
    location = _normalize_text(job.get("location")) or "Unknown location"
    due_at = (
        ((job.get("workflow") or {}).get("followUp") or {}).get("dueAt")
        if isinstance(job.get("workflow"), dict)
        else None
    )
    angle = _first_sentence(job.get("cover_letter_angle")) or _first_sentence(job.get("application_tips"))
    url = _normalize_text(job.get("url")) or "No job URL saved."
    lines = [
        "Recall follow-up reminder",
        f"{title} @ {company}",
        f"Due: {_format_due_label(due_at)}",
        f"Location: {location}",
        f"Prompt: {angle or 'Send a concise check-in and keep momentum on the application.'}",
        url,
    ]
    return "\n".join(lines)


def queue_follow_up_reminder_runs(
    *,
    job_ids: list[str] | None = None,
    due_only: bool = True,
    limit: int = 20,
    dry_run: bool = False,
    channel: str = "n8n",
    automation_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_iso = now.isoformat().replace("+00:00", "Z")
    automation_value = str(automation_id or DEFAULT_FOLLOW_UP_REMINDER_AUTOMATION_ID).strip() or DEFAULT_FOLLOW_UP_REMINDER_AUTOMATION_ID
    requested_ids = {str(item).strip() for item in (job_ids or []) if str(item).strip()}

    rows = all_jobs()
    candidates: list[dict[str, Any]] = []
    skipped = 0

    for row in rows:
        job_id = str(row.get("jobId") or "").strip()
        if not job_id:
            skipped += 1
            continue
        if requested_ids and job_id not in requested_ids:
            continue

        workflow = row.get("workflow") if isinstance(row.get("workflow"), dict) else {}
        follow_up = workflow.get("followUp") if isinstance(workflow.get("followUp"), dict) else {}
        reminder = follow_up.get("reminder") if isinstance(follow_up.get("reminder"), dict) else {}
        due_at = _parse_datetime(follow_up.get("dueAt"))
        follow_up_status = str(follow_up.get("status") or "").strip().lower()
        reminder_status = str(reminder.get("status") or "not_created").strip().lower()

        if follow_up_status != "scheduled" or due_at is None:
            skipped += 1
            continue
        if due_only and due_at > now:
            skipped += 1
            continue

        allowed_statuses = EXPLICIT_RUN_REMINDER_STATUSES if requested_ids else ELIGIBLE_REMINDER_STATUSES
        if reminder_status not in allowed_statuses:
            skipped += 1
            continue

        candidates.append(row)

    candidates.sort(key=lambda item: _parse_datetime((((item.get("workflow") or {}).get("followUp") or {}).get("dueAt"))) or now)
    selected = candidates[: max(1, int(limit))]
    items: list[dict[str, Any]] = []

    for row in selected:
        job_id = str(row.get("jobId") or "").strip()
        due_at = (((row.get("workflow") or {}).get("followUp") or {}).get("dueAt"))
        reminder_patch = {
            "created": True,
            "status": "queued",
            "channel": channel,
            "lastRunAt": now_iso,
            "deliveredAt": None,
            "automationId": automation_value,
            "notes": "Queued by follow-up reminder run." if not dry_run else "Selected by follow-up reminder dry run.",
        }
        updated = row
        if not dry_run:
            updated_value = update_job(
                job_id=job_id,
                status=None,
                applied=None,
                dismissed=None,
                notes=None,
                workflow={"followUp": {"reminder": reminder_patch}},
            )
            if updated_value:
                updated = updated_value

        items.append(
            {
                "job_id": job_id,
                "title": row.get("title"),
                "company": row.get("company"),
                "location": row.get("location"),
                "url": row.get("url"),
                "due_at": due_at,
                "channel": channel,
                "automation_id": automation_value,
                "reminder_status": "queued",
                "delivery_target": "telegram",
                "message": build_follow_up_reminder_text(updated if isinstance(updated, dict) else row),
            }
        )

    run_id = f"follow_up_reminder_run_{uuid4().hex[:10]}"
    return {
        "run_id": run_id,
        "status": "completed",
        "queued": len(items),
        "skipped": skipped,
        "dry_run": dry_run,
        "channel": channel,
        "automation_id": automation_value,
        "items": items,
        "message": (
            f"Prepared {len(items)} follow-up reminder item{'s' if len(items) != 1 else ''} "
            f"and skipped {skipped} job{'s' if skipped != 1 else ''}."
        ),
    }
