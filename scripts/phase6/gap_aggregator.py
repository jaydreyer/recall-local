#!/usr/bin/env python3
"""Aggregate skill-gap views from evaluated jobs."""

from __future__ import annotations

from collections import Counter
from typing import Any


def _flatten_gap_items(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        flattened: list[str] = []
        for item in raw:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    flattened.append(text)
            elif isinstance(item, dict):
                for key in ("skill", "gap", "name"):
                    value = str(item.get(key, "")).strip()
                    if value:
                        flattened.append(value)
                        break
        return flattened
    return []


def aggregate_gaps(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [job for job in jobs if str(job.get("status", "")).lower() in {"evaluated", "applied", "dismissed"}]
    gap_counter: Counter[str] = Counter()
    skill_counter: Counter[str] = Counter()

    for job in evaluated:
        gap_counter.update(_flatten_gap_items(job.get("gaps")))
        skill_counter.update(_flatten_gap_items(job.get("matching_skills")))

    top_gaps = [{"skill": skill, "count": count} for skill, count in gap_counter.most_common(10)]
    top_matches = [{"skill": skill, "count": count} for skill, count in skill_counter.most_common(10)]
    focus = [entry["skill"] for entry in top_gaps[:3]]

    return {
        "total_jobs": len(jobs),
        "evaluated_jobs": len(evaluated),
        "top_gaps": top_gaps,
        "top_matching_skills": top_matches,
        "recommended_focus": focus,
    }
