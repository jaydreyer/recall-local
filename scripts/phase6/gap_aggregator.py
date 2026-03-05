#!/usr/bin/env python3
"""Aggregate and deduplicate Phase 6 job gaps."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from scripts import llm_client

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


def aggregate_gaps(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [
        job
        for job in jobs
        if str(job.get("status", "")).strip().lower() == "evaluated"
        and int(_coerce_int(job.get("fit_score"), default=-1)) > 0
    ]

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
        for skill, count in matching_skill_counter.most_common(10)
    ]

    top_gaps = [
        {"skill": item["gap"], "count": item["frequency"]}
        for item in aggregated[:10]
    ]

    return {
        "total_jobs_analyzed": len(evaluated),
        "aggregated_gaps": aggregated,
        "generated_at": _now_iso(),
        # Backwards-compatible fields used by existing Phase 6A docs/clients.
        "total_jobs": len(jobs),
        "evaluated_jobs": len(evaluated),
        "top_gaps": top_gaps,
        "top_matching_skills": top_matching_skills,
        "recommended_focus": [item["gap"] for item in aggregated[:3]],
    }


def merge_similar_gaps(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not gaps:
        return []

    embed_cache: dict[str, list[float] | None] = {}
    clusters: list[dict[str, Any]] = []

    for item in gaps:
        gap_text = str(item.get("gap") or "").strip()
        if not gap_text:
            continue
        embedding = _get_gap_embedding(gap_text, cache=embed_cache)

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
            "variants": [name for name, _ in variants_counter.most_common(5)],
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
    for serialized, _ in counter.most_common(5):
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


def _get_gap_embedding(text: str, *, cache: dict[str, list[float] | None]) -> list[float] | None:
    normalized = text.strip().lower()
    if not normalized:
        return None
    if normalized in cache:
        return cache[normalized]

    try:
        vector = llm_client.embed(
            normalized,
            trace_metadata={
                "operation": "phase6_gap_embedding",
            },
        )
        cache[normalized] = vector
        return vector
    except Exception:  # noqa: BLE001
        cache[normalized] = None
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
    for a, b in zip(left, right):
        dot += a * b
        left_norm += a * a
        right_norm += b * b

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
