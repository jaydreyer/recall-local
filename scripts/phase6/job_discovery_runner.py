#!/usr/bin/env python3
"""Phase 6B discovery runner for job sources and career pages."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from scripts.llm_client import embed
from scripts.phase1.ingestion_pipeline import qdrant_client_from_env
from scripts.phase6 import storage
from scripts.phase6.company_profiler import list_tracked_company_configs
from scripts.phase6.job_dedup import check_job_duplicate
from scripts.phase6.setup_collections import COLLECTION_JOBS

ROOT = Path(__file__).resolve().parents[2]
JOB_SEARCH_CONFIG = ROOT / "config" / "job_search.json"
CAREER_PAGES_CONFIG = ROOT / "config" / "career_pages.json"

DEFAULT_SOURCE_ORDER = ["jobspy", "adzuna", "serpapi"]
DEFAULT_SOURCE_LIMITS = {"jobspy": 2, "adzuna": 2, "serpapi": 1, "career_page": 25}
DEFAULT_QUERY_BATCH_SIZE = 4
DEFAULT_MAX_DAYS_OLD = 7
DEFAULT_DELAY_SECONDS = 2.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _slug(value: Any) -> str:
    cleaned = "".join(char if char.isalnum() else "-" for char in str(value or "").strip().lower())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _norm_lower(value: Any) -> str:
    return _norm(value).lower()


def _clean_html(text: Any) -> str:
    raw = str(text or "")
    if not raw:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    decoded = html.unescape(without_tags)
    normalized_ws = re.sub(r"\s+", " ", decoded)
    return normalized_ws.strip()


def _normalize_company_name(name: str) -> str:
    lowered = _norm_lower(name)
    lowered = re.sub(r"\b(inc\.?|llc|ltd\.?|corp\.?|corporation|co\.?|pbc)\b", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def _coerce_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _coerce_datetime(value: Any) -> datetime | None:
    text = _norm(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    for fmt in (
        None,
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            if fmt is None:
                parsed = datetime.fromisoformat(normalized)
            else:
                parsed = datetime.strptime(normalized, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _to_iso(value: Any) -> str | None:
    parsed = _coerce_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="seconds")


def _location_type(location: str) -> str | None:
    lowered = _norm_lower(location)
    if not lowered:
        return None
    if "remote" in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    if "onsite" in lowered or "on-site" in lowered or "on site" in lowered:
        return "onsite"
    return None


def _load_search_config() -> dict[str, Any]:
    return _read_json(JOB_SEARCH_CONFIG)


def _load_career_config() -> dict[str, Any]:
    return {"companies": list_tracked_company_configs()}


def _get_json_setting(*, key: str, default: dict[str, Any]) -> dict[str, Any]:
    conn = storage.connect_db()
    try:
        row = conn.execute("SELECT setting_value_json FROM settings WHERE setting_key = ?", (key,)).fetchone()
        if row is None:
            return dict(default)
        try:
            payload = json.loads(row["setting_value_json"])
        except (TypeError, json.JSONDecodeError):
            return dict(default)
        if not isinstance(payload, dict):
            return dict(default)
        merged = dict(default)
        merged.update(payload)
        return merged
    finally:
        conn.close()


def _set_json_setting(*, key: str, value: dict[str, Any]) -> None:
    conn = storage.connect_db()
    try:
        conn.execute(
            """
            INSERT INTO settings (setting_key, setting_value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value_json = excluded.setting_value_json, updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, separators=(",", ":")), _now_iso()),
        )
        conn.commit()
    finally:
        conn.close()


def _build_queries(*, titles: list[str], locations: list[str], keywords: list[str]) -> list[dict[str, str]]:
    combos: list[dict[str, str]] = []
    for title in titles:
        title_text = _norm(title)
        if not title_text:
            continue
        for location in locations:
            location_text = _norm(location)
            if not location_text:
                continue
            query = title_text
            if keywords:
                query = f"{title_text} {' '.join(keywords[:3])}".strip()
            combos.append(
                {
                    "title": title_text,
                    "location": location_text,
                    "query": query,
                }
            )
    return combos


def _select_rotated_queries(*, combos: list[dict[str, str]], batch_size: int) -> list[dict[str, str]]:
    if not combos:
        return []

    safe_batch = max(1, min(batch_size, len(combos)))
    state = _get_json_setting(key="job_discovery_cursor", default={"next_index": 0})
    start = int(state.get("next_index", 0) or 0)
    start = start % len(combos)

    selected: list[dict[str, str]] = []
    for offset in range(safe_batch):
        selected.append(combos[(start + offset) % len(combos)])

    next_index = (start + safe_batch) % len(combos)
    _set_json_setting(key="job_discovery_cursor", value={"next_index": next_index, "updated_at": _now_iso()})
    return selected


def _normalize_job_payload(
    *,
    title: str,
    company: str,
    location: str,
    url: str,
    description: str,
    source: str,
    search_query: str,
    company_tier: int,
    salary_min: int | None = None,
    salary_max: int | None = None,
    date_posted: str | None = None,
) -> dict[str, Any]:
    discovered_at = _now_iso()
    company_normalized = _normalize_company_name(company)
    stable_id_seed = "|".join(
        [
            _norm_lower(source),
            _norm_lower(company_normalized or company),
            _norm_lower(title),
            _norm_lower(location),
            _norm_lower(url),
            _norm_lower(date_posted or discovered_at),
        ]
    )
    stable_job_id = f"job_{hashlib.sha1(stable_id_seed.encode('utf-8')).hexdigest()[:16]}"

    return {
        "job_id": stable_job_id,
        "title": _norm(title) or "Untitled role",
        "company": _norm(company) or "Unknown company",
        "company_normalized": company_normalized or _norm(company),
        "company_id": _slug(company_normalized or company),
        "company_tier": int(company_tier),
        "location": _norm(location) or "Unknown",
        "location_type": _location_type(location),
        "url": _norm(url) or None,
        "source": _norm_lower(source) or "unknown",
        "description": _clean_html(description),
        "salary_min": salary_min,
        "salary_max": salary_max,
        "date_posted": date_posted,
        "discovered_at": discovered_at,
        "evaluated_at": None,
        "search_query": _norm(search_query) or None,
        "status": "new",
        "fit_score": -1,
        "score_rationale": "",
        "matching_skills": [],
        "gaps": [],
        "application_tips": "",
        "cover_letter_angle": "",
        "applied": False,
        "applied_at": None,
        "notes": "",
        "dismissed": False,
    }


def _tier_lookup() -> dict[str, int]:
    config = _load_career_config()
    companies = config.get("companies") if isinstance(config, dict) else []
    lookup: dict[str, int] = {}
    if not isinstance(companies, list):
        return lookup
    for item in companies:
        if not isinstance(item, dict):
            continue
        name = _normalize_company_name(item.get("name"))
        if not name:
            continue
        lookup[name] = int(item.get("tier") or 0)
    return lookup


def _normalize_manual_jobs(*, jobs: list[dict[str, Any]], tier_lookup: dict[str, int]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        title = _norm(item.get("title"))
        company = _norm(item.get("company"))
        if not title or not company:
            continue
        source = _norm_lower(item.get("source") or "career_page")
        tier = _coerce_int(item.get("company_tier"), default=None)
        if tier is None:
            tier = tier_lookup.get(_normalize_company_name(company), 0)
        normalized.append(
            _normalize_job_payload(
                title=title,
                company=company,
                location=_norm(item.get("location")),
                url=_norm(item.get("url")),
                description=_norm(item.get("description")),
                source=source or "career_page",
                search_query=_norm(item.get("search_query") or item.get("query") or ""),
                company_tier=int(tier or 0),
                salary_min=_coerce_int(item.get("salary_min")),
                salary_max=_coerce_int(item.get("salary_max")),
                date_posted=_to_iso(item.get("date_posted")),
            )
        )
    return normalized


def _pause(seconds: float) -> None:
    if seconds <= 0:
        return
    time.sleep(seconds)


def _extract_jobspy_rows(raw_jobs: Any) -> list[dict[str, Any]]:
    if isinstance(raw_jobs, list):
        return [item for item in raw_jobs if isinstance(item, dict)]
    to_dict = getattr(raw_jobs, "to_dict", None)
    if callable(to_dict):
        try:
            converted = to_dict("records")
            if isinstance(converted, list):
                return [item for item in converted if isinstance(item, dict)]
        except Exception:
            return []
    return []


def _discover_jobspy(
    *,
    queries: list[dict[str, str]],
    max_days_old: int,
    source_limit: int,
    delay_seconds: float,
    tier_lookup: dict[str, int],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    try:
        from jobspy import scrape_jobs  # type: ignore
    except Exception:
        return [], ["jobspy unavailable (install python-jobspy in bridge runtime)."], {"attempted": 0, "returned": 0}

    discovered: list[dict[str, Any]] = []
    errors: list[str] = []
    attempted = 0

    # LinkedIn currently rejects this runtime's location/country combination in jobspy;
    # keep the other primary boards active for stable ingestion.
    sites = ["indeed", "glassdoor", "zip_recruiter"]

    for query in queries[:source_limit]:
        attempted += 1
        for site in sites:
            try:
                raw_jobs = scrape_jobs(
                    site_name=[site],
                    search_term=query["title"],
                    location=query["location"],
                    results_wanted=30,
                    hours_old=max_days_old * 24,
                    # jobspy expects lowercase country tokens like "usa".
                    country_indeed="usa",
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    f"jobspy search failed for {query['title']} @ {query['location']} ({site}): {exc}"
                )
                continue

            for item in _extract_jobspy_rows(raw_jobs):
                company_name = _norm(item.get("company") or item.get("company_name"))
                tier = tier_lookup.get(_normalize_company_name(company_name), 0)
                discovered.append(
                    _normalize_job_payload(
                        title=_norm(item.get("title")),
                        company=company_name,
                        location=_norm(item.get("location")),
                        url=_norm(item.get("job_url") or item.get("url") or item.get("job_url_direct")),
                        description=_norm(item.get("description") or item.get("job_summary")),
                        source="jobspy",
                        search_query=query["query"],
                        company_tier=tier,
                        salary_min=_coerce_int(item.get("min_amount")),
                        salary_max=_coerce_int(item.get("max_amount")),
                        date_posted=_to_iso(item.get("date_posted")),
                    )
                )

        _pause(delay_seconds)

    return discovered, errors, {"attempted": attempted, "returned": len(discovered)}


def _discover_adzuna(
    *,
    client: httpx.Client,
    queries: list[dict[str, str]],
    max_days_old: int,
    source_limit: int,
    delay_seconds: float,
    tier_lookup: dict[str, int],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    app_id = os.getenv("RECALL_ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("RECALL_ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        return [], ["adzuna skipped: missing RECALL_ADZUNA_APP_ID or RECALL_ADZUNA_APP_KEY."], {"attempted": 0, "returned": 0}

    discovered: list[dict[str, Any]] = []
    errors: list[str] = []
    attempted = 0

    for query in queries[:source_limit]:
        attempted += 1
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "what": query["query"],
            "where": query["location"],
            "results_per_page": 25,
            "max_days_old": max_days_old,
            "sort_by": "date",
        }
        try:
            response = client.get("https://api.adzuna.com/v1/api/jobs/us/search/1", params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"adzuna request failed for {query['query']} ({query['location']}): {exc}")
            _pause(delay_seconds)
            continue

        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            _pause(delay_seconds)
            continue

        for item in results:
            if not isinstance(item, dict):
                continue
            company_obj = item.get("company") if isinstance(item.get("company"), dict) else {}
            company_name = _norm(company_obj.get("display_name"))
            location_obj = item.get("location") if isinstance(item.get("location"), dict) else {}
            location = _norm(location_obj.get("display_name") or query["location"])
            tier = tier_lookup.get(_normalize_company_name(company_name), 0)
            discovered.append(
                _normalize_job_payload(
                    title=_norm(item.get("title")),
                    company=company_name,
                    location=location,
                    url=_norm(item.get("redirect_url") or item.get("adref")),
                    description=_norm(item.get("description")),
                    source="adzuna",
                    search_query=query["query"],
                    company_tier=tier,
                    salary_min=_coerce_int(item.get("salary_min")),
                    salary_max=_coerce_int(item.get("salary_max")),
                    date_posted=_to_iso(item.get("created")),
                )
            )

        _pause(delay_seconds)

    return discovered, errors, {"attempted": attempted, "returned": len(discovered)}


def _discover_serpapi(
    *,
    client: httpx.Client,
    queries: list[dict[str, str]],
    source_limit: int,
    delay_seconds: float,
    tier_lookup: dict[str, int],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    api_key = os.getenv("RECALL_SERPAPI_API_KEY", "").strip()
    if not api_key:
        return [], ["serpapi skipped: missing RECALL_SERPAPI_API_KEY."], {"attempted": 0, "returned": 0}

    discovered: list[dict[str, Any]] = []
    errors: list[str] = []
    attempted = 0

    for query in queries[:source_limit]:
        attempted += 1
        params = {
            "engine": "google_jobs",
            "q": query["query"],
            "location": query["location"],
            "hl": "en",
            "api_key": api_key,
        }
        try:
            response = client.get("https://serpapi.com/search.json", params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"serpapi request failed for {query['query']} ({query['location']}): {exc}")
            _pause(delay_seconds)
            continue

        results = payload.get("jobs_results") if isinstance(payload, dict) else None
        if not isinstance(results, list):
            _pause(delay_seconds)
            continue

        for item in results:
            if not isinstance(item, dict):
                continue
            company_name = _norm(item.get("company_name"))
            tier = tier_lookup.get(_normalize_company_name(company_name), 0)
            discovered.append(
                _normalize_job_payload(
                    title=_norm(item.get("title")),
                    company=company_name,
                    location=_norm(item.get("location") or query["location"]),
                    url=_norm(item.get("apply_link") or item.get("share_link") or item.get("job_id")),
                    description=_norm(item.get("description")),
                    source="serpapi",
                    search_query=query["query"],
                    company_tier=tier,
                    salary_min=None,
                    salary_max=None,
                    date_posted=_to_iso(item.get("detected_extensions", {}).get("posted_at") if isinstance(item.get("detected_extensions"), dict) else None),
                )
            )

        _pause(delay_seconds)

    return discovered, errors, {"attempted": attempted, "returned": len(discovered)}


def _title_matches_filters(title: str, filters: list[str]) -> bool:
    normalized_title = _norm_lower(title)
    if not normalized_title:
        return False
    if not filters:
        return True
    for token in filters:
        token_text = _norm_lower(token)
        if token_text and token_text in normalized_title:
            return True
    return False


def _discover_career_pages(
    *,
    client: httpx.Client,
    source_limit: int,
    delay_seconds: float,
    career_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    companies = career_config.get("companies") if isinstance(career_config, dict) else []
    if not isinstance(companies, list):
        return [], ["career_page skipped: config/career_pages.json missing companies[]"], {"attempted": 0, "returned": 0}

    discovered: list[dict[str, Any]] = []
    errors: list[str] = []
    attempted = 0

    for company in companies[: max(1, source_limit)]:
        if not isinstance(company, dict):
            continue
        attempted += 1
        name = _norm(company.get("name"))
        ats = _norm_lower(company.get("ats"))
        tier = int(company.get("tier") or 0)
        title_filter = company.get("title_filter") if isinstance(company.get("title_filter"), list) else []

        try:
            if ats == "greenhouse":
                board_id = _norm(company.get("board_id"))
                if not board_id:
                    raise ValueError(f"missing board_id for {name}")
                response = client.get(f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs")
                response.raise_for_status()
                payload = response.json()
                jobs = payload.get("jobs") if isinstance(payload, dict) else []
                if not isinstance(jobs, list):
                    jobs = []
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    title = _norm(job.get("title"))
                    if not _title_matches_filters(title, title_filter):
                        continue
                    location_obj = job.get("location") if isinstance(job.get("location"), dict) else {}
                    discovered.append(
                        _normalize_job_payload(
                            title=title,
                            company=name,
                            location=_norm(location_obj.get("name")),
                            url=_norm(job.get("absolute_url")),
                            description="",
                            source="career_page",
                            search_query=f"{name} careers",
                            company_tier=tier,
                            date_posted=_to_iso(job.get("updated_at")),
                        )
                    )
            elif ats == "ashby":
                board_id = _norm(company.get("board_id"))
                if not board_id:
                    raise ValueError(f"missing board_id for {name}")
                response = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board_id}")
                response.raise_for_status()
                payload = response.json()
                jobs = payload.get("jobs") if isinstance(payload, dict) else []
                if not isinstance(jobs, list):
                    jobs = []
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    title = _norm(job.get("title"))
                    if not _title_matches_filters(title, title_filter):
                        continue
                    discovered.append(
                        _normalize_job_payload(
                            title=title,
                            company=name,
                            location=_norm(job.get("location")),
                            url=_norm(job.get("jobUrl") or job.get("applyUrl")),
                            description=_norm(job.get("descriptionPlain")) or _clean_html(job.get("descriptionHtml")),
                            source="career_page",
                            search_query=f"{name} careers",
                            company_tier=tier,
                            date_posted=_to_iso(job.get("publishedAt")),
                        )
                    )
            elif ats == "lever":
                board_id = _norm(company.get("board_id") or company.get("lever_company") or name)
                lever_slug = _slug(board_id)
                response = client.get(f"https://api.lever.co/v0/postings/{lever_slug}", params={"mode": "json"})
                response.raise_for_status()
                payload = response.json()
                jobs = payload if isinstance(payload, list) else []
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    title = _norm(job.get("text"))
                    if not _title_matches_filters(title, title_filter):
                        continue
                    categories = job.get("categories") if isinstance(job.get("categories"), dict) else {}
                    discovered.append(
                        _normalize_job_payload(
                            title=title,
                            company=name,
                            location=_norm(categories.get("location")),
                            url=_norm(job.get("hostedUrl")),
                            description=_norm(job.get("descriptionPlain") or job.get("description")),
                            source="career_page",
                            search_query=f"{name} careers",
                            company_tier=tier,
                            date_posted=_to_iso(job.get("createdAt")),
                        )
                    )
            else:
                errors.append(f"career_page skipped unsupported ATS '{ats}' for {name}.")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"career_page fetch failed for {name}: {exc}")

        _pause(delay_seconds)

    return discovered, errors, {"attempted": attempted, "returned": len(discovered)}


def _build_discovery_text(candidate: dict[str, Any]) -> str:
    description = _norm(candidate.get("description"))
    if description:
        return description
    return "\n".join(
        [
            _norm(candidate.get("title")),
            _norm(candidate.get("company")),
            _norm(candidate.get("location")),
            _norm(candidate.get("search_query")),
        ]
    ).strip()


def _store_jobs(candidates: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    if not candidates:
        return [], []

    errors: list[str] = []
    stored_ids: list[str] = []
    host = os.getenv("QDRANT_HOST", "http://localhost:6333").strip() or "http://localhost:6333"

    try:
        client = qdrant_client_from_env(host)
        from qdrant_client import models
    except Exception as exc:  # noqa: BLE001
        return [], [f"qdrant unavailable: {exc}"]

    points: list[Any] = []
    for candidate in candidates:
        try:
            embedding_input = _build_discovery_text(candidate)
            vector = embed(embedding_input, trace_metadata={"operation": "phase6_job_discovery_embed"})
            point_id = str(uuid.uuid4())
            payload = dict(candidate)
            points.append(models.PointStruct(id=point_id, vector=vector, payload=payload))
            stored_ids.append(str(candidate.get("job_id")))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"failed embedding {candidate.get('job_id')}: {exc}")

    if points:
        try:
            client.upsert(collection_name=COLLECTION_JOBS, points=points)
        except Exception as exc:  # noqa: BLE001
            return [], [f"qdrant upsert failed: {exc}"]

    return stored_ids, errors


def _record_activity_log(*, run_id: str, summary: dict[str, Any]) -> None:
    conn = storage.connect_db()
    try:
        has_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingestion_log'"
        ).fetchone()
        if not has_table:
            return
        conn.execute(
            """
            INSERT INTO ingestion_log (
                ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp, group_name, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "job-discovery",
                ",".join(summary.get("sources", [])),
                "job-discovery",
                None,
                int(summary.get("new_jobs", 0) or 0),
                "completed" if summary.get("status") == "completed" else "failed",
                summary.get("triggered_at") or _now_iso(),
                "job-search",
                json.dumps(["phase6", "job-discovery"], separators=(",", ":")),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    search_config = _load_search_config()
    career_config = _load_career_config()
    tier_lookup = _tier_lookup()

    titles = payload.get("titles") or search_config.get("search_titles") or []
    locations = payload.get("locations") or search_config.get("search_locations") or []
    keywords = payload.get("keywords") or search_config.get("search_keywords") or []

    normalized_titles = [_norm(item) for item in titles if _norm(item)]
    normalized_locations = [_norm(item) for item in locations if _norm(item)]
    normalized_keywords = [_norm(item) for item in keywords if _norm(item)]

    configured_sources = payload.get("sources") or DEFAULT_SOURCE_ORDER
    sources = [
        _norm_lower(item)
        for item in configured_sources
        if _norm_lower(item) in {"jobspy", "adzuna", "serpapi", "career_page"}
    ]
    if not sources:
        sources = list(DEFAULT_SOURCE_ORDER)

    batch_size = _coerce_int(payload.get("max_queries"), default=DEFAULT_QUERY_BATCH_SIZE) or DEFAULT_QUERY_BATCH_SIZE
    source_limits_payload = payload.get("source_limits") if isinstance(payload.get("source_limits"), dict) else {}
    source_limits = dict(DEFAULT_SOURCE_LIMITS)
    for key, value in source_limits_payload.items():
        normalized = _norm_lower(key)
        if normalized in source_limits:
            source_limits[normalized] = max(1, _coerce_int(value, default=source_limits[normalized]) or source_limits[normalized])

    max_days_old = _coerce_int(payload.get("max_days_old"), default=DEFAULT_MAX_DAYS_OLD) or DEFAULT_MAX_DAYS_OLD
    delay_seconds = float(payload.get("delay_seconds", DEFAULT_DELAY_SECONDS) or DEFAULT_DELAY_SECONDS)
    if delay_seconds < 0:
        delay_seconds = 0.0

    dry_run = bool(payload.get("dry_run", False))
    similarity_threshold = float(payload.get("similarity_threshold") or search_config.get("dedup_similarity_threshold") or 0.92)

    search_queries = _build_queries(titles=normalized_titles, locations=normalized_locations, keywords=normalized_keywords)
    selected_queries = _select_rotated_queries(combos=search_queries, batch_size=batch_size) if search_queries else []

    manual_jobs_payload = payload.get("jobs") if isinstance(payload.get("jobs"), list) else []
    manual_jobs = _normalize_manual_jobs(
        jobs=[item for item in manual_jobs_payload if isinstance(item, dict)],
        tier_lookup=tier_lookup,
    )

    run_id = f"job_discovery_{uuid.uuid4().hex[:12]}"
    started_at = _now_iso()

    discovered: list[dict[str, Any]] = list(manual_jobs)
    errors: list[str] = []
    source_metrics: dict[str, Any] = {}

    if manual_jobs:
        source_metrics["manual"] = {"attempted": len(manual_jobs), "returned": len(manual_jobs)}
        sources = sorted({str(item.get("source") or "manual") for item in manual_jobs}) or ["manual"]
    else:
        with httpx.Client(timeout=30.0, headers={"User-Agent": "recall-local-phase6-discovery/1.0"}) as client:
            for source in sources:
                if source == "jobspy":
                    rows, source_errors, metrics = _discover_jobspy(
                        queries=selected_queries,
                        max_days_old=max_days_old,
                        source_limit=source_limits.get("jobspy", 2),
                        delay_seconds=delay_seconds,
                        tier_lookup=tier_lookup,
                    )
                elif source == "adzuna":
                    rows, source_errors, metrics = _discover_adzuna(
                        client=client,
                        queries=selected_queries,
                        max_days_old=max_days_old,
                        source_limit=source_limits.get("adzuna", 2),
                        delay_seconds=delay_seconds,
                        tier_lookup=tier_lookup,
                    )
                elif source == "serpapi":
                    rows, source_errors, metrics = _discover_serpapi(
                        client=client,
                        queries=selected_queries,
                        source_limit=source_limits.get("serpapi", 1),
                        delay_seconds=delay_seconds,
                        tier_lookup=tier_lookup,
                    )
                elif source == "career_page":
                    rows, source_errors, metrics = _discover_career_pages(
                        client=client,
                        source_limit=source_limits.get("career_page", 3),
                        delay_seconds=delay_seconds,
                        career_config=career_config,
                    )
                else:
                    rows, source_errors, metrics = [], [f"unsupported source: {source}"], {"attempted": 0, "returned": 0}

                discovered.extend(rows)
                errors.extend(source_errors)
                source_metrics[source] = metrics

    dedupe_reasons: dict[str, int] = {}
    unique_candidates: list[dict[str, Any]] = []
    duplicate_count = 0

    for candidate in discovered:
        dedup = check_job_duplicate(candidate, similarity_threshold=similarity_threshold)
        if dedup.duplicate:
            duplicate_count += 1
            dedupe_reasons[dedup.reason] = dedupe_reasons.get(dedup.reason, 0) + 1
            continue
        unique_candidates.append(candidate)

    new_job_ids: list[str] = []
    persistence_errors: list[str] = []
    if not dry_run:
        new_job_ids, persistence_errors = _store_jobs(unique_candidates)
        errors.extend(persistence_errors)
    else:
        new_job_ids = [str(item.get("job_id")) for item in unique_candidates]

    summary = {
        "run_id": run_id,
        "status": "completed" if not persistence_errors else "partial",
        "triggered_at": started_at,
        "finished_at": _now_iso(),
        "sources": sources,
        "titles": normalized_titles,
        "locations": normalized_locations,
        "search_queries": selected_queries,
        "queued_queries": len(selected_queries),
        "discovered_raw": len(discovered),
        "new_jobs": len(new_job_ids),
        "new_job_ids": new_job_ids,
        "duplicates_skipped": duplicate_count,
        "dedupe_reasons": dedupe_reasons,
        "source_metrics": source_metrics,
        "dry_run": dry_run,
        "errors": errors,
        "message": (
            f"Discovered {len(new_job_ids)} new jobs, skipped {duplicate_count} duplicates "
            f"from {', '.join(sources)}."
        ),
    }
    _record_activity_log(run_id=run_id, summary=summary)
    return summary
