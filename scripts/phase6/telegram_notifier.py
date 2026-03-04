#!/usr/bin/env python3
"""Telegram notifier scaffold for Phase 6."""

from __future__ import annotations

import os
from typing import Any

import httpx


def notify_job(job: dict[str, Any]) -> dict[str, Any]:
    token = os.getenv("RECALL_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("RECALL_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return {"sent": False, "reason": "telegram_not_configured"}

    text = (
        f"New job candidate: {job.get('title', 'Unknown role')}\n"
        f"Company: {job.get('company', 'Unknown')}\n"
        f"Score: {job.get('fit_score', 'n/a')}\n"
        f"URL: {job.get('url', 'n/a')}"
    )

    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    response.raise_for_status()
    return {"sent": True}
