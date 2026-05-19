#!/usr/bin/env python3
"""Deterministic Phase 3 job-title relevance and ranking signals."""

from __future__ import annotations

import re
from typing import Any

TARGET_TITLE_FAMILIES = (
    "solutions_engineer",
    "ai_engineer",
    "technical_account_manager",
    "customer_engineer",
    "forward_deployed_engineer",
)

TARGET_TITLE_LABELS = {
    "solutions_engineer": "Solutions Engineer",
    "ai_engineer": "AI Engineer",
    "technical_account_manager": "Technical Account Manager",
    "customer_engineer": "Customer Engineer",
    "forward_deployed_engineer": "Forward Deployed Engineer",
}

LLM_AI_TERMS = (
    "ai",
    "artificial intelligence",
    "llm",
    "large language model",
    "generative ai",
    "genai",
    "rag",
    "retrieval augmented",
    "agent",
    "agents",
    "prompt",
    "copilot",
)

TARGET_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("forward_deployed_engineer", (r"\bforward deployed engineer\b", r"\bfde\b")),
    ("technical_account_manager", (r"\btechnical account manager\b", r"\btam\b")),
    ("customer_engineer", (r"\bcustomer engineer\b", r"\bcustomer engineering\b")),
    ("solutions_engineer", (r"\bsolutions? engineer\b", r"\bsolutions? consultant\b")),
    ("ai_engineer", (r"\bai engineer\b", r"\bartificial intelligence engineer\b")),
)

ADJACENT_PATTERNS = (
    r"\bsales engineer\b",
    r"\bsolutions? architect\b",
    r"\bai solutions? consultant\b",
    r"\bai consultant\b",
    r"\bimplementation engineer\b",
    r"\bdeveloper relations\b",
    r"\bdeveloper advocate\b",
    r"\benterprise ai strategist\b",
)

NOISE_PATTERNS = (
    r"\bintern(ship)?\b",
    r"\bbackend engineer\b",
    r"\bback end engineer\b",
    r"\bfrontend engineer\b",
    r"\bfront end engineer\b",
    r"\bfull[- ]stack engineer\b",
    r"\bsoftware engineer\b",
    r"\bsite reliability engineer\b",
    r"\bsre\b",
    r"\bdevops\b",
    r"\bdata engineer\b",
    r"\bdata scientist\b",
    r"\bmachine learning engineer\b",
    r"\bml engineer\b",
    r"\bjava\b",
    r"\bspring\b",
    r"\bqa engineer\b",
    r"\bproduct manager\b",
    r"\bprogram manager\b",
)

BROAD_ADJACENT_PATTERNS = (
    r"\barchitect\b",
    r"\bplatform engineer\b",
    r"\bcloud engineer\b",
    r"\btechnical program manager\b",
    r"\bconsultant\b",
)


def assess_job_relevance(job: dict[str, Any]) -> dict[str, Any]:
    """Return inspectable ranking metadata for one job."""
    title = str(job.get("title") or "")
    description = str(job.get("description") or "")
    search_query = str(job.get("search_query") or "")
    blob = _normalize_blob(f"{title} {description} {search_query}")
    title_blob = _normalize_blob(title)
    fit_score = _coerce_int(job.get("fit_score"), default=0)
    company_tier = _coerce_int(job.get("company_tier"), default=0)

    target_family = _target_family(title_blob=title_blob, full_blob=blob)
    adjacent = _first_pattern_match(title_blob, ADJACENT_PATTERNS)
    practical_ai_engineering = _is_practical_ai_engineering(title_blob=title_blob, full_blob=blob)
    noise = _first_pattern_match(title_blob, NOISE_PATTERNS)
    broad_adjacent = _first_pattern_match(title_blob, BROAD_ADJACENT_PATTERNS)

    signals: list[str] = []
    penalties: list[str] = []
    if target_family:
        category = "target"
        title_score = 32
        signals.append(f"target_title:{target_family}")
    elif adjacent or practical_ai_engineering:
        category = "adjacent"
        title_score = 12 if adjacent else 8
        signals.append(f"adjacent_title:{adjacent or 'practical_ai_engineering'}")
    elif noise:
        category = "noise"
        title_score = -55
        penalties.append(f"off_target_title:{noise}")
    elif broad_adjacent:
        category = "broad_adjacent"
        title_score = -18
        penalties.append(f"broad_adjacent_title:{broad_adjacent}")
    else:
        category = "unclassified"
        title_score = -8
        penalties.append("no_target_title_signal")

    company_boost = {1: 6, 2: 4, 3: 1}.get(company_tier, 0)
    if company_boost:
        signals.append(f"company_tier:{company_tier}")

    location_boost = 0
    location_text = str(job.get("location") or "").lower()
    if "remote" in location_text:
        location_boost = 3
        signals.append("remote_location")

    llm_signal = _contains_any(blob, LLM_AI_TERMS)
    if target_family == "ai_engineer" and llm_signal:
        title_score += 6
        signals.append("practical_ai_signal")
    elif "ai" in title_blob and llm_signal and category in {"adjacent", "broad_adjacent", "unclassified"}:
        title_score += 5
        signals.append("practical_ai_signal")

    if noise and target_family is None:
        penalties.append("archive_candidate")

    ranking_score = max(0, min(120, fit_score + title_score + company_boost + location_boost))
    archive_recommended = _archive_recommended(
        category=category,
        fit_score=fit_score,
        title_blob=title_blob,
        penalties=penalties,
    )

    return {
        "version": "phase3_title_relevance_v1",
        "targetTitleFamilies": list(TARGET_TITLE_FAMILIES),
        "targetFamily": target_family,
        "targetLabel": TARGET_TITLE_LABELS.get(target_family, None),
        "category": category,
        "titleScore": title_score,
        "companyBoost": company_boost,
        "locationBoost": location_boost,
        "rankingScore": ranking_score,
        "signals": signals,
        "penalties": penalties,
        "archiveRecommended": archive_recommended,
        "archiveReason": _archive_reason(category=category, penalties=penalties) if archive_recommended else None,
    }


def _target_family(*, title_blob: str, full_blob: str) -> str | None:
    for family, patterns in TARGET_PATTERNS:
        if any(re.search(pattern, title_blob) for pattern in patterns):
            if family != "ai_engineer" or _contains_any(full_blob, LLM_AI_TERMS):
                return family
    return None


def _archive_recommended(*, category: str, fit_score: int, title_blob: str, penalties: list[str]) -> bool:
    if category == "noise":
        return True
    if category in {"broad_adjacent", "unclassified"} and fit_score >= 75:
        return True
    if "intern" in title_blob:
        return True
    return any(item.startswith("off_target_title:") for item in penalties)


def _is_practical_ai_engineering(*, title_blob: str, full_blob: str) -> bool:
    engineering_title = any(
        phrase in title_blob
        for phrase in (
            " machine learning engineer ",
            " ml engineer ",
            " ai platform engineer ",
            " ai application engineer ",
        )
    )
    if not engineering_title:
        return False
    return _contains_any(full_blob, ("agent", "agents", "llm", "rag", "generative ai", "genai", "ai assistant"))


def _archive_reason(*, category: str, penalties: list[str]) -> str:
    if category == "noise":
        return "Title is clearly outside the five Phase 3 target families."
    if category == "broad_adjacent":
        return "Broad adjacent title is deprioritized despite evaluator score."
    return penalties[0] if penalties else "Phase 3 relevance cleanup."


def _first_pattern_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if re.search(pattern, text):
            return pattern.strip("\\b")
    return None


def _contains_any(blob: str, needles: tuple[str, ...]) -> bool:
    return any(needle in blob for needle in needles)


def _normalize_blob(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9+#.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f" {text} "


def _coerce_int(value: Any, *, default: int) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
