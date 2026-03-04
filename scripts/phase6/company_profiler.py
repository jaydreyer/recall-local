#!/usr/bin/env python3
"""Company profile helpers for Phase 6 foundation endpoints."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.phase6 import storage

ROOT = Path(__file__).resolve().parents[2]
CAREER_PAGES_PATH = ROOT / "config" / "career_pages.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify_company(name: str) -> str:
    lowered = name.strip().lower()
    cleaned = "".join(char if char.isalnum() else "-" for char in lowered)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "unknown-company"


def _load_career_pages() -> list[dict[str, Any]]:
    if not CAREER_PAGES_PATH.exists():
        return []
    try:
        payload = json.loads(CAREER_PAGES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    companies = payload.get("companies") if isinstance(payload, dict) else None
    return companies if isinstance(companies, list) else []


def _jobs_for_company(company_name: str, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target = company_name.strip().lower()
    return [job for job in jobs if str(job.get("company", "")).strip().lower() == target]


def _skills_summary(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for job in jobs:
        skills = job.get("matching_skills") or []
        if isinstance(skills, list):
            for item in skills:
                if isinstance(item, str) and item.strip():
                    counter[item.strip()] += 1
                elif isinstance(item, dict):
                    name = str(item.get("skill") or item.get("name") or "").strip()
                    if name:
                        counter[name] += 1
    return [{"skill": skill, "count": count} for skill, count in counter.most_common(12)]


def build_company_profiles(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configured = _load_career_pages()
    by_config = {slugify_company(str(item.get("name", ""))): item for item in configured}

    company_names = {str(job.get("company", "")).strip() for job in jobs if str(job.get("company", "")).strip()}
    for name in list(by_config.values()):
        configured_name = str(name.get("name", "")).strip()
        if configured_name:
            company_names.add(configured_name)

    profiles: list[dict[str, Any]] = []
    for company_name in sorted(company_names):
        company_id = slugify_company(company_name)
        config = by_config.get(company_id, {})
        company_jobs = _jobs_for_company(company_name, jobs)
        average_score = 0.0
        if company_jobs:
            scores = [int(job.get("fit_score", 0) or 0) for job in company_jobs]
            average_score = round(sum(scores) / len(scores), 1)

        profile = {
            "company_id": company_id,
            "company_name": company_name,
            "tier": int(config.get("tier", 0) or 0),
            "ats": config.get("ats"),
            "url": config.get("url"),
            "your_connection": config.get("your_connection"),
            "description": config.get("description") or None,
            "job_count": len(company_jobs),
            "average_fit_score": average_score,
            "top_skills": _skills_summary(company_jobs),
            "jobs": company_jobs,
            "updated_at": _now_iso(),
        }
        profiles.append(profile)

    return profiles


def list_company_profiles(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return build_company_profiles(jobs)


def get_company_profile(company_id: str, jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = slugify_company(company_id)
    for profile in build_company_profiles(jobs):
        if profile["company_id"] == target:
            return profile
    return None


def refresh_company_profile(company_id: str, jobs: list[dict[str, Any]]) -> dict[str, Any]:
    profile = get_company_profile(company_id, jobs)
    if profile is None:
        return {
            "run_id": f"company_refresh_{slugify_company(company_id)}",
            "status": "not_found",
            "company_id": slugify_company(company_id),
            "refreshed_at": _now_iso(),
        }

    conn = storage.connect_db()
    try:
        storage.upsert_company_profile(
            conn,
            {
                "company_id": profile["company_id"],
                "company_name": profile["company_name"],
                "tier": profile["tier"],
                "description": profile.get("description"),
                "your_connection": profile.get("your_connection"),
                "metadata": {
                    "ats": profile.get("ats"),
                    "url": profile.get("url"),
                    "job_count": profile.get("job_count"),
                    "average_fit_score": profile.get("average_fit_score"),
                },
                "updated_at": _now_iso(),
            },
        )
    finally:
        conn.close()

    return {
        "run_id": f"company_refresh_{profile['company_id']}",
        "status": "completed",
        "company_id": profile["company_id"],
        "jobs_considered": profile["job_count"],
        "refreshed_at": _now_iso(),
    }
