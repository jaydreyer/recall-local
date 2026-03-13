#!/usr/bin/env python3
"""Telegram notifier scaffold for Phase 6."""

from __future__ import annotations

import os
from typing import Any

import httpx


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


def _clamp_text(value: Any, max_length: int = 96) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    budget = max(0, max_length - 3)
    truncated = text[:budget].rstrip()
    last_space = truncated.rfind(" ")
    if last_space >= max(12, int(budget * 0.6)):
        truncated = truncated[:last_space].rstrip()
    return truncated + "..."


def _top_match(job: dict[str, Any]) -> str:
    skills = job.get("matching_skills")
    if not isinstance(skills, list) or not skills:
        return "No evidence-backed match captured yet."
    first = skills[0]
    if isinstance(first, str):
        return _clamp_text(first)
    label = _normalize_text(first.get("skill") or first.get("name") or first.get("label"))
    evidence = _first_sentence(first.get("evidence"))
    return _clamp_text(f"{label} from {evidence}" if label and evidence else label or evidence) or "No evidence-backed match captured yet."


def _top_gap(job: dict[str, Any]) -> str:
    gaps = job.get("gaps")
    if not isinstance(gaps, list) or not gaps:
        return "No priority gap captured."
    first = gaps[0]
    if isinstance(first, str):
        return _clamp_text(first)
    label = _normalize_text(first.get("gap") or first.get("skill") or first.get("name") or first.get("label"))
    severity = _normalize_text(first.get("severity"))
    return _clamp_text(f"{label} ({severity})" if label and severity else label or severity) or "No priority gap captured."


def _angle(job: dict[str, Any]) -> str:
    primary = _first_sentence(job.get("cover_letter_angle"))
    fallback = _first_sentence(job.get("application_tips")) or _first_sentence(job.get("score_rationale"))
    return _clamp_text(primary or fallback, max_length=120) or "Open the dossier for the full evaluation context."


def build_notification_text(job: dict[str, Any]) -> str:
    title = job.get("title", "Unknown role")
    company = job.get("company", "Unknown")
    score = job.get("fit_score", "n/a")
    location = _normalize_text(job.get("location")) or _normalize_text(job.get("location_raw")) or "Unknown location"
    url = job.get("url", "n/a")
    return (
        f"Recall job alert\n"
        f"{title} @ {company}\n"
        f"Fit: {score} | {location}\n"
        f"Top match: {_top_match(job)}\n"
        f"Top gap: {_top_gap(job)}\n"
        f"Angle: {_angle(job)}\n"
        f"{url}"
    )


def notify_job(job: dict[str, Any]) -> dict[str, Any]:
    token = os.getenv("RECALL_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("RECALL_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"sent": False, "reason": "telegram_not_configured"}

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": build_notification_text(job)},
        timeout=15,
    )
    response.raise_for_status()
    return {"sent": True}
