#!/usr/bin/env python3
"""Generate Phase 6 cover letter drafts from resume and evaluated jobs."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.phase6.job_evaluator import (  # noqa: PLC2701
    _call_cloud,
    _call_ollama,
    _load_resume_text,
    _load_runtime_settings,
)
from scripts.phase6.job_repository import get_job


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-") or "job"


def _draft_prompt(*, job: dict[str, Any], resume_text: str) -> str:
    matching_skills = job.get("matching_skills") or []
    matching_skill_names: list[str] = []
    if isinstance(matching_skills, list):
        for item in matching_skills[:6]:
            if isinstance(item, str) and item.strip():
                matching_skill_names.append(item.strip())
            elif isinstance(item, dict):
                name = str(item.get("skill") or item.get("name") or "").strip()
                if name:
                    matching_skill_names.append(name)

    skills_text = ", ".join(matching_skill_names) if matching_skill_names else "Not provided"
    cover_letter_angle = str(job.get("cover_letter_angle") or "").strip() or "Customer-facing AI platform leadership."
    score_rationale = str(job.get("score_rationale") or "").strip()

    return (
        "Write a concise cover letter in plain text.\n"
        "Requirements:\n"
        "- Keep it under 400 words.\n"
        "- Use a confident but grounded tone.\n"
        "- Reference only experience supported by the resume context.\n"
        "- Make the strongest case for this specific role.\n"
        "- Do not invent metrics, dates, or employers.\n"
        "- End with a short, direct closing.\n\n"
        f"Job title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Location: {job.get('location')}\n"
        f"Strongest angle: {cover_letter_angle}\n"
        f"Matching skills: {skills_text}\n"
        f"Score rationale: {score_rationale or 'Not provided'}\n\n"
        "Job description:\n"
        f"{job.get('description') or 'Not provided'}\n\n"
        "Resume context:\n"
        f"{resume_text}"
    )


def _clean_draft(text: str) -> str:
    lines = [line.rstrip() for line in str(text).strip().splitlines()]
    cleaned = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _save_to_vault(*, job: dict[str, Any], draft_text: str) -> str | None:
    write_back_enabled = str(os.getenv("RECALL_VAULT_WRITE_BACK", "false")).strip().lower() == "true"
    if not write_back_enabled:
        return None

    raw_vault_path = str(os.getenv("RECALL_VAULT_PATH", "")).strip()
    if not raw_vault_path:
        return None

    vault_path = Path(raw_vault_path).expanduser()
    folder = vault_path / "career" / "cover-letters"
    folder.mkdir(parents=True, exist_ok=True)

    filename = f"{_slugify(str(job.get('company') or 'company'))}-{_slugify(str(job.get('title') or 'role'))}.md"
    output_path = folder / filename
    output_path.write_text(
        "\n".join(
            [
                f"# Cover Letter Draft - {job.get('company')} - {job.get('title')}",
                "",
                f"Generated: {_now_iso()}",
                f"Job ID: {job.get('jobId')}",
                f"Posting: {job.get('url') or 'n/a'}",
                "",
                draft_text,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return str(output_path)


def generate_cover_letter_draft(
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
    prompt = _draft_prompt(job=job, resume_text=resume_text)
    mode = str(runtime_settings.get("evaluation_model") or "local").strip().lower()

    if mode == "cloud":
        draft = _call_cloud(prompt=prompt, settings=runtime_settings)
        provider = str(runtime_settings.get("cloud_provider") or "anthropic").strip().lower()
        model = str(runtime_settings.get("cloud_model") or "").strip()
    else:
        draft = _call_ollama(prompt=prompt, settings=runtime_settings)
        provider = "ollama"
        model = str(runtime_settings.get("local_model") or os.getenv("RECALL_PHASE6_EVAL_LOCAL_MODEL") or "llama3.2:3b").strip()

    cleaned_draft = _clean_draft(draft)
    vault_path = _save_to_vault(job=job, draft_text=cleaned_draft) if save_to_vault else None

    return {
        "draft_id": f"cover_letter_{_slugify(normalized_job_id)}",
        "job_id": normalized_job_id,
        "provider": provider,
        "model": model,
        "generated_at": _now_iso(),
        "word_count": len([word for word in cleaned_draft.split() if word]),
        "draft": cleaned_draft,
        "saved_to_vault": vault_path is not None,
        "vault_path": vault_path,
    }
