#!/usr/bin/env python3
"""Generate Phase 6 interview-brief artifacts from resume and evaluated jobs."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from scripts.phase6.job_evaluator import (  # noqa: PLC2701
    _call_cloud,
    _call_ollama,
    _load_resume_text,
    _load_runtime_settings,
)
from scripts.phase6.job_repository import get_job
from scripts.shared_strings import slugify
from scripts.shared_time import now_iso


def _slugify(value: str) -> str:
    return slugify(value, fallback="job")


def _extract_skill_names(items: Any, *, limit: int) -> list[str]:
    names: list[str] = []
    if not isinstance(items, list):
        return names
    for item in items[:limit]:
        if isinstance(item, str) and item.strip():
            names.append(item.strip())
        elif isinstance(item, dict):
            name = str(item.get("skill") or item.get("gap") or item.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _interview_brief_prompt(*, job: dict[str, Any], resume_text: str) -> str:
    matching_skills = _extract_skill_names(job.get("matching_skills"), limit=6)
    gaps = _extract_skill_names(job.get("gaps"), limit=4)
    skills_text = ", ".join(matching_skills) if matching_skills else "Not provided"
    gaps_text = ", ".join(gaps) if gaps else "No major gaps provided"
    score_rationale = str(job.get("score_rationale") or "").strip() or "Not provided"
    cover_letter_angle = str(job.get("cover_letter_angle") or "").strip() or "Customer-facing AI platform leadership."
    application_tips = str(job.get("application_tips") or "").strip() or "No application tips provided."

    return (
        "Write a concise interview brief in Markdown.\n"
        "Requirements:\n"
        "- Use exactly these headings in order: ## Role Snapshot, ## Why You Match, ## Stories To Prepare, ## Risks To Address, ## Questions To Ask.\n"
        "- Under each heading, provide 2 bullet points.\n"
        "- Each bullet must start with '- '.\n"
        "- Each bullet should be one sentence.\n"
        "- Use only evidence grounded in the resume and evaluated job context.\n"
        "- Do not invent metrics, employers, dates, tools, or interview process details.\n"
        "- Make the brief useful for live interview preparation, not generic job-search advice.\n\n"
        f"Job title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Location: {job.get('location')}\n"
        f"Strongest angle: {cover_letter_angle}\n"
        f"Matching skills: {skills_text}\n"
        f"Gaps to address carefully: {gaps_text}\n"
        f"Score rationale: {score_rationale}\n"
        f"Application tips: {application_tips}\n\n"
        "Job description:\n"
        f"{job.get('description') or 'Not provided'}\n\n"
        "Resume context:\n"
        f"{resume_text}"
    )


def _clean_interview_brief(text: str) -> str:
    cleaned_lines: list[str] = []
    current_heading: str | None = None
    for raw_line in str(text).strip().splitlines():
        line = raw_line.strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        if line.startswith("## "):
            current_heading = line
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            cleaned_lines.append(line)
            continue
        normalized = re.sub(r"^[-*•\d.\)\s]+", "", line).strip()
        if normalized:
            if current_heading is None:
                current_heading = "## Role Snapshot"
                cleaned_lines.append(current_heading)
            cleaned_lines.append(f"- {normalized}")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines).strip())


def _save_to_vault(*, job: dict[str, Any], brief_text: str) -> str | None:
    write_back_enabled = str(os.getenv("RECALL_VAULT_WRITE_BACK", "false")).strip().lower() == "true"
    if not write_back_enabled:
        return None

    raw_vault_path = str(os.getenv("RECALL_VAULT_PATH", "")).strip()
    if not raw_vault_path:
        return None

    vault_path = Path(raw_vault_path).expanduser()
    folder = vault_path / "career" / "packets" / _slugify(str(job.get("jobId") or "job"))
    folder.mkdir(parents=True, exist_ok=True)

    output_path = folder / "interview-brief.md"
    output_path.write_text(
        "\n".join(
            [
                f"# Interview Brief - {job.get('company')} - {job.get('title')}",
                "",
                f"Generated: {now_iso()}",
                f"Job ID: {job.get('jobId')}",
                f"Posting: {job.get('url') or 'n/a'}",
                "",
                brief_text,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return str(output_path)


def generate_interview_brief(
    *,
    job_id: str,
    settings: dict[str, Any] | None = None,
    save_to_vault: bool = False,
) -> dict[str, Any]:
    normalized_job_id = str(job_id).strip()
    if not normalized_job_id:
        raise ValueError("Missing required field: job_id.")

    job = get_job(normalized_job_id)
    if job is None:
        raise FileNotFoundError(f"Job not found: {normalized_job_id}")

    resume_text = _load_resume_text().strip()
    if not resume_text:
        raise ValueError("No resume content is available in `recall_resume`.")

    runtime_settings = _load_runtime_settings(settings)
    prompt = _interview_brief_prompt(job=job, resume_text=resume_text)
    mode = str(runtime_settings.get("evaluation_model") or "local").strip().lower()

    if mode == "cloud":
        brief = _call_cloud(prompt=prompt, settings=runtime_settings)
        provider = str(runtime_settings.get("cloud_provider") or "anthropic").strip().lower()
        model = str(runtime_settings.get("cloud_model") or "").strip()
    else:
        brief = _call_ollama(prompt=prompt, settings=runtime_settings)
        provider = "ollama"
        model = str(runtime_settings.get("local_model") or os.getenv("RECALL_PHASE6_EVAL_LOCAL_MODEL") or "llama3.2:3b").strip()

    cleaned_brief = _clean_interview_brief(brief)
    vault_path = _save_to_vault(job=job, brief_text=cleaned_brief) if save_to_vault else None

    return {
        "brief_id": f"interview_brief_{_slugify(normalized_job_id)}",
        "job_id": normalized_job_id,
        "provider": provider,
        "model": model,
        "generated_at": now_iso(),
        "word_count": len(cleaned_brief.split()),
        "brief": cleaned_brief,
        "saved_to_vault": vault_path is not None,
        "vault_path": vault_path,
    }
