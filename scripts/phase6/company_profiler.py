#!/usr/bin/env python3
"""Company profile helpers for Phase 6 dashboard endpoints."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def _normalize_title_filters(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            normalized.append(text)
    return normalized


def list_tracked_company_configs() -> list[dict[str, Any]]:
    configured = _load_career_pages()
    persisted = _load_persisted_profiles()

    merged: dict[str, dict[str, Any]] = {}
    for item in configured:
        if not isinstance(item, dict):
            continue
        company_name = str(item.get("name") or "").strip()
        if not company_name:
            continue
        company_id = slugify_company(company_name)
        merged[company_id] = {
            "company_id": company_id,
            "name": company_name,
            "tier": int(item.get("tier") or 0),
            "ats": str(item.get("ats") or "").strip() or None,
            "board_id": str(item.get("board_id") or "").strip() or None,
            "url": str(item.get("url") or "").strip() or None,
            "title_filter": _normalize_title_filters(item.get("title_filter")),
            "your_connection": str(item.get("your_connection") or "").strip() or None,
        }

    for company_id, row in persisted.items():
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if company_id not in merged and not bool(metadata.get("watch_enabled")):
            continue

        current = dict(merged.get(company_id, {}))
        current["company_id"] = company_id
        current["name"] = str(row.get("company_name") or current.get("name") or "").strip()
        current["tier"] = int(row.get("tier") or current.get("tier") or 0)
        current["your_connection"] = str(
            row.get("your_connection") if row.get("your_connection") is not None else current.get("your_connection") or ""
        ).strip() or None

        if "ats" in metadata:
            current["ats"] = str(metadata.get("ats") or "").strip() or None
        if "board_id" in metadata:
            current["board_id"] = str(metadata.get("board_id") or "").strip() or None
        if "careers_url" in metadata or "url" in metadata:
            current["url"] = str(metadata.get("careers_url") or metadata.get("url") or "").strip() or None
        if "title_filter" in metadata:
            current["title_filter"] = _normalize_title_filters(metadata.get("title_filter"))

        merged[company_id] = current

    return sorted(merged.values(), key=lambda item: str(item.get("name") or "").lower())


def upsert_tracked_company_config(*, company_id: str | None = None, patch: dict[str, Any]) -> dict[str, Any]:
    tracked = {item["company_id"]: item for item in list_tracked_company_configs()}
    target_name = str(patch.get("company_name") or "").strip()
    resolved_company_id = slugify_company(company_id or patch.get("company_id") or target_name)
    if not resolved_company_id or resolved_company_id == "unknown-company":
        raise ValueError("company_name is required.")

    existing = tracked.get(resolved_company_id, {})
    persisted = _load_persisted_profiles().get(resolved_company_id, {})
    metadata = dict(persisted.get("metadata") or {})

    company_name = target_name or str(existing.get("name") or persisted.get("company_name") or "").strip()
    if not company_name:
        raise ValueError("company_name is required.")

    tier = int(patch.get("tier") if patch.get("tier") is not None else existing.get("tier") or persisted.get("tier") or 3)
    your_connection = (
        str(patch.get("your_connection") or "").strip()
        if "your_connection" in patch
        else str(existing.get("your_connection") or persisted.get("your_connection") or "").strip()
    ) or None

    if "ats" in patch:
        metadata["ats"] = str(patch.get("ats") or "").strip() or None
    elif "ats" not in metadata and existing.get("ats") is not None:
        metadata["ats"] = existing.get("ats")

    if "board_id" in patch:
        metadata["board_id"] = str(patch.get("board_id") or "").strip() or None
    elif "board_id" not in metadata and existing.get("board_id") is not None:
        metadata["board_id"] = existing.get("board_id")

    if "url" in patch:
        metadata["careers_url"] = str(patch.get("url") or "").strip() or None
    elif "careers_url" not in metadata and existing.get("url") is not None:
        metadata["careers_url"] = existing.get("url")

    if "title_filter" in patch:
        metadata["title_filter"] = _normalize_title_filters(patch.get("title_filter"))
    elif "title_filter" not in metadata and existing.get("title_filter") is not None:
        metadata["title_filter"] = _normalize_title_filters(existing.get("title_filter"))

    metadata["watch_enabled"] = True
    metadata["about_source"] = str(metadata.get("about_source") or "Tracked company watchlist")

    conn = storage.connect_db()
    try:
        storage.upsert_company_profile(
            conn,
            {
                "company_id": resolved_company_id,
                "company_name": company_name,
                "tier": tier,
                "description": persisted.get("description"),
                "your_connection": your_connection,
                "metadata": metadata,
                "updated_at": _now_iso(),
            },
        )
    finally:
        conn.close()

    return {
        "company_id": resolved_company_id,
        "company_name": company_name,
        "tier": tier,
        "your_connection": your_connection,
        "metadata": metadata,
    }


def _group_jobs_by_company(jobs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for job in jobs:
        key = str(job.get("company", "")).strip().lower()
        if not key:
            continue
        grouped.setdefault(key, []).append(job)
    return grouped


def _extract_skill_name(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return str(item.get("skill") or item.get("name") or "").strip()
    return ""


def _skills_summary(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for job in jobs:
        skills = job.get("matching_skills") or []
        if isinstance(skills, list):
            for item in skills:
                name = _extract_skill_name(item)
                if name:
                    counter[name] += 1
    return [{"skill": skill, "count": count} for skill, count in counter.most_common(12)]


def _load_persisted_profiles() -> dict[str, dict[str, Any]]:
    conn = storage.connect_db()
    try:
        rows = storage.list_company_profile_rows(conn)
    finally:
        conn.close()
    return {str(row.get("company_id")): row for row in rows}


def _score_value(job: dict[str, Any]) -> int:
    try:
        return int(job.get("fit_score") or 0)
    except (TypeError, ValueError):
        return 0


def _domain_from_url(url: str | None) -> str | None:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    host = (parsed.netloc or "").strip().lower()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("boards-api."):
        host = host[len("boards-api.") :]
    if host.startswith("boards."):
        host = host[len("boards.") :]
    return host or None


def _remote_policy(jobs: list[dict[str, Any]]) -> str | None:
    if not jobs:
        return None
    counter: Counter[str] = Counter()
    for job in jobs:
        location_type = str(job.get("location_type") or "").strip().lower()
        location_text = str(job.get("location") or "").strip().lower()
        preference_bucket = str(
            ((job.get("observation") or {}).get("location") or {}).get("preference_bucket") or ""
        ).strip().lower()

        if location_type in {"remote", "hybrid", "onsite"}:
            counter[location_type] += 1
        elif preference_bucket == "remote":
            counter["remote"] += 1
        elif "remote" in location_text:
            counter["remote"] += 1
        elif "hybrid" in location_text:
            counter["hybrid"] += 1
        elif location_text:
            counter["onsite"] += 1

    if not counter:
        return None
    winner = counter.most_common(1)[0][0]
    return {
        "remote": "Remote-friendly",
        "hybrid": "Hybrid",
        "onsite": "On-site",
    }.get(winner, None)


def _default_description(
    *,
    company_name: str,
    jobs: list[dict[str, Any]],
    your_connection: str | None,
) -> tuple[str, str]:
    top_titles = [str(job.get("title") or "").strip() for job in jobs if str(job.get("title") or "").strip()]
    top_skills = [item["skill"] for item in _skills_summary(jobs)[:3]]

    title_counter = Counter(top_titles)
    role_text = ", ".join(title for title, _ in title_counter.most_common(2))
    skill_text = ", ".join(top_skills)

    if jobs:
        summary = f"{company_name} is actively hiring for customer-facing roles"
        if role_text:
            summary = f"{company_name} is actively hiring for roles such as {role_text}"
        if skill_text:
            summary += f", with repeated emphasis on {skill_text}"
        summary += "."
    else:
        summary = f"{company_name} is on the tracked company list for Phase 6 job discovery."

    if your_connection:
        summary += f" Existing connection signal: {your_connection}"
    return summary, "Auto-generated from tracked jobs"


def _hydrate_profile(
    *,
    company_name: str,
    company_jobs: list[dict[str, Any]],
    config: dict[str, Any],
    persisted: dict[str, Any] | None,
    include_jobs: bool = True,
) -> dict[str, Any]:
    company_id = slugify_company(company_name)
    persisted = persisted or {}
    persisted_metadata = persisted.get("metadata") if isinstance(persisted.get("metadata"), dict) else {}

    company_jobs = sorted(
        company_jobs,
        key=lambda item: (_score_value(item), str(item.get("discovered_at") or "")),
        reverse=True,
    )
    average_score = round(sum(_score_value(job) for job in company_jobs) / len(company_jobs), 1) if company_jobs else 0.0
    description, about_source = _default_description(
        company_name=company_name,
        jobs=company_jobs,
        your_connection=str(persisted.get("your_connection") or config.get("your_connection") or "").strip() or None,
    )
    if persisted.get("description"):
        description = str(persisted["description"])
        about_source = str(persisted_metadata.get("about_source") or "Stored company profile")

    careers_url = str(persisted_metadata.get("careers_url") or config.get("url") or "").strip() or None
    domain = str(persisted_metadata.get("domain") or _domain_from_url(careers_url) or "").strip() or None

    jobs_by_status = Counter(str(job.get("status") or "unknown").strip().lower() for job in company_jobs)
    top_skills = _skills_summary(company_jobs)

    metadata = {
        "about_source": about_source,
        "ats": persisted_metadata.get("ats") or config.get("ats"),
        "careers_url": careers_url,
        "domain": domain,
        "logo_url": f"https://logo.clearbit.com/{domain}" if domain else None,
        "favicon_url": f"https://www.google.com/s2/favicons?domain={domain}&sz=64" if domain else None,
        "remote_policy": persisted_metadata.get("remote_policy") or _remote_policy(company_jobs),
        "headquarters": persisted_metadata.get("headquarters"),
        "company_size": persisted_metadata.get("company_size"),
        "funding_stage": persisted_metadata.get("funding_stage"),
        "job_count": len(company_jobs),
        "average_fit_score": average_score,
        "highest_fit_score": max((_score_value(job) for job in company_jobs), default=0),
        "jobs_by_status": dict(jobs_by_status),
        "what_they_look_for": [item["skill"] for item in top_skills[:4]],
    }

    return {
        "company_id": company_id,
        "company_name": company_name,
        "tier": int(persisted.get("tier") or config.get("tier") or 0),
        "ats": metadata.get("ats"),
        "board_id": persisted_metadata.get("board_id") or config.get("board_id"),
        "url": careers_url,
        "careers_url": careers_url,
        "title_filter": _normalize_title_filters(
            persisted_metadata.get("title_filter") if "title_filter" in persisted_metadata else config.get("title_filter")
        ),
        "domain": domain,
        "logo_url": metadata.get("logo_url"),
        "favicon_url": metadata.get("favicon_url"),
        "monogram": company_name[:1].upper() if company_name else "?",
        "your_connection": persisted.get("your_connection") or config.get("your_connection"),
        "description": description,
        "about_source": about_source,
        "remote_policy": metadata.get("remote_policy"),
        "headquarters": metadata.get("headquarters"),
        "company_size": metadata.get("company_size"),
        "funding_stage": metadata.get("funding_stage"),
        "job_count": len(company_jobs),
        "average_fit_score": average_score,
        "top_skills": top_skills,
        "skill_chart": top_skills,
        "what_they_look_for": metadata.get("what_they_look_for"),
        "jobs_summary": {
            "job_count": len(company_jobs),
            "average_fit_score": average_score,
            "highest_fit_score": metadata.get("highest_fit_score"),
            "jobs_by_status": dict(jobs_by_status),
        },
        "jobs": company_jobs if include_jobs else [],
        "metadata": metadata,
        "updated_at": str(persisted.get("updated_at") or _now_iso()),
    }


def build_company_profiles(jobs: list[dict[str, Any]], *, include_jobs: bool = True, limit: int | None = None) -> list[dict[str, Any]]:
    configured = list_tracked_company_configs()
    by_config = {slugify_company(str(item.get("name", ""))): item for item in configured}
    persisted = _load_persisted_profiles()
    grouped_jobs = _group_jobs_by_company(jobs)

    company_names = {str(job.get("company", "")).strip() for job in jobs if str(job.get("company", "")).strip()}
    for name in list(by_config.values()):
        configured_name = str(name.get("name", "")).strip()
        if configured_name:
            company_names.add(configured_name)
    for profile in persisted.values():
        configured_name = str(profile.get("company_name", "")).strip()
        if configured_name:
            company_names.add(configured_name)

    profiles: list[dict[str, Any]] = []
    for company_name in company_names:
        if not company_name:
            continue
        company_id = slugify_company(company_name)
        profiles.append(
            _hydrate_profile(
                company_name=company_name,
                company_jobs=grouped_jobs.get(company_name.strip().lower(), []),
                config=by_config.get(company_id, {}),
                persisted=persisted.get(company_id),
                include_jobs=include_jobs,
            )
        )

    profiles.sort(
        key=lambda item: (
            -float(item.get("average_fit_score") or 0.0),
            -int(item.get("job_count") or 0),
            str(item.get("company_name") or "").lower(),
        )
    )

    if limit is not None and limit > 0:
        return profiles[:limit]
    return profiles


def list_company_profiles(jobs: list[dict[str, Any]], *, include_jobs: bool = True, limit: int | None = None) -> list[dict[str, Any]]:
    return build_company_profiles(jobs, include_jobs=include_jobs, limit=limit)


def get_company_profile(company_id: str, jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = slugify_company(company_id)
    for profile in build_company_profiles(jobs, include_jobs=True):
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
                "metadata": profile.get("metadata") or {},
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
        "profile": profile,
        "refreshed_at": _now_iso(),
    }
