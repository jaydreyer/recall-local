#!/usr/bin/env python3
"""Aggregate and deduplicate Phase 6 job gaps."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from scripts import llm_client

LOGGER = logging.getLogger(__name__)
SEVERITY_TO_SCORE = {
    "critical": 3,
    "moderate": 2,
    "minor": 1,
}

SCORE_TO_SEVERITY = {
    3: "critical",
    2: "moderate",
    1: "minor",
}

SIMILARITY_THRESHOLD = 0.85
DEFAULT_GAP_CACHE_SECONDS = 300.0
DEFAULT_GAP_EMBED_LIMIT = 24
MAX_RECOMMENDATIONS = 5
MAX_VARIANTS = 5
TOP_MATCHING_SKILLS_LIMIT = 10
TOP_GAPS_LIMIT = 10
RECOMMENDED_FOCUS_LIMIT = 3
_GAP_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_EMBED_CACHE: dict[str, list[float] | None] = {}


def aggregate_gaps(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate evaluated job gaps into recruiter-friendly clusters and counts."""
    evaluated = [
        job
        for job in jobs
        if str(job.get("status", "")).strip().lower() == "evaluated"
        and int(_coerce_int(job.get("fit_score"), default=-1)) > 0
    ]
    cache_key = _evaluated_jobs_cache_key(evaluated)
    cache_ttl_seconds = _cache_ttl_seconds()
    if cache_ttl_seconds > 0:
        cached = _GAP_CACHE.get(cache_key)
        if cached and cached[0] > time.time():
            return dict(cached[1])

    gap_instances = _collect_gap_instances(evaluated)
    merged = merge_similar_gaps(gap_instances)

    matching_skill_counter = Counter()
    for job in evaluated:
        for skill in _extract_skills(job.get("matching_skills")):
            matching_skill_counter[skill] += 1

    aggregated = []
    for cluster in merged:
        aggregated.append(
            {
                "gap": cluster["gap"],
                "frequency": cluster["frequency"],
                "avg_severity": cluster["avg_severity"],
                "avg_severity_score": cluster["avg_severity_score"],
                "top_recommendations": cluster["top_recommendations"],
                "variants": cluster["variants"],
            }
        )

    top_matching_skills = [
        {"skill": skill, "count": count}
        for skill, count in matching_skill_counter.most_common(TOP_MATCHING_SKILLS_LIMIT)
    ]

    top_gaps = [
        {"skill": item["gap"], "count": item["frequency"]}
        for item in aggregated[:TOP_GAPS_LIMIT]
    ]

    payload = {
        "total_jobs_analyzed": len(evaluated),
        "aggregated_gaps": aggregated,
        "generated_at": _now_iso(),
        # Backwards-compatible fields used by existing Phase 6A docs/clients.
        "total_jobs": len(jobs),
        "evaluated_jobs": len(evaluated),
        "top_gaps": top_gaps,
        "top_matching_skills": top_matching_skills,
        "recommended_focus": [item["gap"] for item in aggregated[:RECOMMENDED_FOCUS_LIMIT]],
    }
    if cache_ttl_seconds > 0:
        _GAP_CACHE[cache_key] = (time.time() + cache_ttl_seconds, dict(payload))
    return payload


def invalidate_gap_cache() -> None:
    """Clear cached aggregate gap results after job data changes."""
    _GAP_CACHE.clear()


def merge_similar_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge near-duplicate gaps using lexical and optional embedding similarity."""
    if not gaps:
        return []

    use_embeddings = _should_use_embeddings(gaps)
    clusters: list[dict[str, Any]] = []

    for item in gaps:
        gap_text = str(item.get("gap") or "").strip()
        if not gap_text:
            continue
        embedding = _get_gap_embedding(gap_text) if use_embeddings else None

        best_index = -1
        best_score = 0.0
        for index, cluster in enumerate(clusters):
            score = _similarity(
                left_text=gap_text,
                right_text=cluster["canonical"],
                left_embedding=embedding,
                right_embedding=cluster.get("embedding"),
            )
            if score > best_score:
                best_score = score
                best_index = index

        if best_index >= 0 and best_score >= SIMILARITY_THRESHOLD:
            _add_to_cluster(clusters[best_index], item)
            continue

        clusters.append(_new_cluster(item, embedding=embedding))

    for cluster in clusters:
        variants_counter = cluster["variants_counter"]
        canonical = variants_counter.most_common(1)[0][0]
        cluster["canonical"] = canonical

        average_score = _average(cluster["severity_scores"])
        rounded = int(round(average_score)) if average_score > 0 else 1
        rounded = max(1, min(3, rounded))
        recommendations = _recommendations_from_counter(cluster["recommendations_counter"])

        cluster["result"] = {
            "gap": canonical,
            "frequency": int(cluster["count"]),
            "avg_severity": SCORE_TO_SEVERITY.get(rounded, "moderate"),
            "avg_severity_score": round(average_score, 2),
            "top_recommendations": recommendations,
            "variants": [name for name, _ in variants_counter.most_common(MAX_VARIANTS)],
        }

    clusters.sort(
        key=lambda cluster: (
            cluster["result"]["frequency"],
            cluster["result"]["avg_severity_score"],
        ),
        reverse=True,
    )
    return [cluster["result"] for cluster in clusters]


def _collect_gap_instances(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for job in jobs:
        raw_gaps = job.get("gaps")
        if not isinstance(raw_gaps, list):
            continue
        for item in raw_gaps:
            parsed = _parse_gap_item(item)
            if parsed is None:
                continue
            rows.append(parsed)
    return rows


def _cache_ttl_seconds() -> float:
    try:
        return max(float(os.getenv("RECALL_PHASE6_GAP_CACHE_SECONDS", str(DEFAULT_GAP_CACHE_SECONDS))), 0.0)
    except (TypeError, ValueError):
        return DEFAULT_GAP_CACHE_SECONDS


def _should_use_embeddings(gaps: list[dict[str, Any]]) -> bool:
    try:
        limit = int(os.getenv("RECALL_PHASE6_GAP_EMBED_LIMIT", str(DEFAULT_GAP_EMBED_LIMIT)))
    except (TypeError, ValueError):
        limit = DEFAULT_GAP_EMBED_LIMIT
    if limit <= 0:
        return False
    unique_gap_count = len(
        {
            str(item.get("gap") or "").strip().lower()
            for item in gaps
            if str(item.get("gap") or "").strip()
        }
    )
    return unique_gap_count <= limit


def _evaluated_jobs_cache_key(jobs: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for job in sorted(jobs, key=lambda item: str(item.get("jobId") or item.get("job_id") or "")):
        digest.update(str(job.get("jobId") or job.get("job_id") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(job.get("status") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(job.get("fit_score") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(job.get("evaluated_at") or "").encode("utf-8"))
        digest.update(b"\0")
        digest.update(json.dumps(job.get("gaps") or [], sort_keys=True, ensure_ascii=True).encode("utf-8"))
        digest.update(b"\0")
        digest.update(json.dumps(job.get("matching_skills") or [], sort_keys=True, ensure_ascii=True).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def _parse_gap_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, str):
        gap = item.strip()
        if not gap:
            return None
        return {
            "gap": gap,
            "severity": "moderate",
            "severity_score": SEVERITY_TO_SCORE["moderate"],
            "recommendations": [],
        }

    if not isinstance(item, dict):
        return None

    gap = str(item.get("gap") or item.get("skill") or item.get("name") or "").strip()
    if not gap:
        return None

    severity = str(item.get("severity") or "moderate").strip().lower()
    if severity not in SEVERITY_TO_SCORE:
        severity = "moderate"

    recommendations = _normalize_recommendations(item.get("recommendations"))
    return {
        "gap": gap,
        "severity": severity,
        "severity_score": SEVERITY_TO_SCORE[severity],
        "recommendations": recommendations,
    }


def _normalize_recommendations(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            normalized.append(
                {
                    "type": "article",
                    "title": text,
                    "source": "",
                    "effort": "",
                }
            )
            continue

        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        if not title:
            continue
        normalized.append(
            {
                "type": str(item.get("type") or "article").strip().lower(),
                "title": title,
                "source": str(item.get("source") or "").strip(),
                "effort": str(item.get("effort") or "").strip(),
            }
        )
    return normalized


def _new_cluster(item: dict[str, Any], *, embedding: list[float] | None) -> dict[str, Any]:
    counter = Counter({item["gap"]: 1})
    rec_counter = Counter()
    for rec in item.get("recommendations", []):
        rec_counter[_recommendation_key(rec)] += 1

    return {
        "canonical": item["gap"],
        "embedding": embedding,
        "count": 1,
        "variants_counter": counter,
        "severity_scores": [int(item.get("severity_score") or 2)],
        "recommendations_counter": rec_counter,
        "result": {},
    }


def _add_to_cluster(cluster: dict[str, Any], item: dict[str, Any]) -> None:
    cluster["count"] += 1
    cluster["variants_counter"][item["gap"]] += 1
    cluster["severity_scores"].append(int(item.get("severity_score") or 2))

    for rec in item.get("recommendations", []):
        cluster["recommendations_counter"][_recommendation_key(rec)] += 1


def _recommendations_from_counter(counter: Counter[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for serialized, _ in counter.most_common(MAX_RECOMMENDATIONS):
        try:
            parsed = json.loads(serialized)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(
                {
                    "type": str(parsed.get("type") or "article"),
                    "title": str(parsed.get("title") or "").strip(),
                    "source": str(parsed.get("source") or "").strip(),
                    "effort": str(parsed.get("effort") or "").strip(),
                }
            )
    return rows


def _recommendation_key(item: dict[str, Any]) -> str:
    normalized = {
        "type": str(item.get("type") or "article").strip().lower(),
        "title": str(item.get("title") or "").strip(),
        "source": str(item.get("source") or "").strip(),
        "effort": str(item.get("effort") or "").strip(),
    }
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _extract_skills(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    rows: list[str] = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text:
                rows.append(text)
            continue
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or item.get("name") or "").strip()
        if skill:
            rows.append(skill)
    return rows


def _get_gap_embedding(text: str) -> list[float] | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    if normalized in _EMBED_CACHE:
        return _EMBED_CACHE[normalized]

    try:
        vector = llm_client.embed(
            normalized,
            trace_metadata={
                "operation": "phase6_gap_embedding",
            },
        )
        _EMBED_CACHE[normalized] = vector
        return vector
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Gap embedding unavailable for %r: %s", normalized, exc)
        _EMBED_CACHE[normalized] = None
        return None


def _similarity(
    *,
    left_text: str,
    right_text: str,
    left_embedding: list[float] | None,
    right_embedding: list[float] | None,
) -> float:
    if left_embedding and right_embedding:
        cosine = _cosine_similarity(left_embedding, right_embedding)
        lexical = _lexical_similarity(left_text, right_text)
        return max(cosine, lexical)
    return _lexical_similarity(left_text, right_text)


def _lexical_similarity(left: str, right: str) -> float:
    left_norm = left.strip().lower()
    right_norm = right.strip().lower()
    if not left_norm or not right_norm:
        return 0.0

    seq = SequenceMatcher(None, left_norm, right_norm).ratio()

    left_tokens = set(_tokenize(left_norm))
    right_tokens = set(_tokenize(right_norm))
    if not left_tokens or not right_tokens:
        return seq
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)

    return (0.6 * seq) + (0.4 * overlap)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0

    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right, strict=True):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value

    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _average(values: list[int]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
