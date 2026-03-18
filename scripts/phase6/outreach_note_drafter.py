#!/usr/bin/env python3
"""Generate Phase 6 outreach note artifacts from resume and evaluated jobs."""

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


def _outreach_prompt(*, job: dict[str, Any], resume_text: str) -> str:
    matching_skills = job.get("matching_skills") or []
    matching_skill_names: list[str] = []
    if isinstance(matching_skills, list):
        for item in matching_skills[:5]:
            if isinstance(item, str) and item.strip():
                matching_skill_names.append(item.strip())
            elif isinstance(item, dict):
                name = str(item.get("skill") or item.get("name") or "").strip()
                if name:
                    matching_skill_names.append(name)

    score_rationale = str(job.get("score_rationale") or "").strip() or "Not provided"
    cover_letter_angle = str(job.get("cover_letter_angle") or "").strip() or "Customer-facing AI platform leadership."
    skills_text = ", ".join(matching_skill_names) if matching_skill_names else "Not provided"

    return (
        "Write a concise outreach note in plain text for a recruiter, hiring manager, or warm contact.\n"
        "Requirements:\n"
        "- Keep it under 120 words.\n"
        "- Use one short greeting, one compact body paragraph, and one short close.\n"
        "- Sound warm, direct, and professional.\n"
        "- Mention why this role is a fit using only resume-grounded evidence.\n"
        "- Do not invent metrics, employers, or relationships.\n"
        "- Avoid sounding generic or overly salesy.\n\n"
        f"Job title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Location: {job.get('location')}\n"
        f"Strongest angle: {cover_letter_angle}\n"
        f"Matching skills: {skills_text}\n"
        f"Score rationale: {score_rationale}\n\n"
        "Job description:\n"
        f"{job.get('description') or 'Not provided'}\n\n"
        "Resume context:\n"
        f"{resume_text}"
    )


def _clean_note(text: str) -> str:
    cleaned = str(text).strip()
    cleaned = re.sub(r"\r\n?", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _save_to_vault(*, job: dict[str, Any], note_text: str) -> str | None:
    write_back_enabled = str(os.getenv("RECALL_VAULT_WRITE_BACK", "false")).strip().lower() == "true"
    if not write_back_enabled:
        return None

    raw_vault_path = str(os.getenv("RECALL_VAULT_PATH", "")).strip()
    if not raw_vault_path:
        return None

    vault_path = Path(raw_vault_path).expanduser()
    folder = vault_path / "career" / "packets" / _slugify(str(job.get("jobId") or "job"))
    folder.mkdir(parents=True, exist_ok=True)

    output_path = folder / "outreach-note.md"
    output_path.write_text(
        "\n".join(
            [
                f"# Outreach Note - {job.get('company')} - {job.get('title')}",
                "",
                f"Generated: {now_iso()}",
                f"Job ID: {job.get('jobId')}",
                f"Posting: {job.get('url') or 'n/a'}",
                "",
                note_text,
                "",
            ]
        ),
        encoding="utf-8",
    )
    return str(output_path)


def generate_outreach_note(
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
    prompt = _outreach_prompt(job=job, resume_text=resume_text)
    mode = str(runtime_settings.get("evaluation_model") or "local").strip().lower()

    if mode == "cloud":
        note = _call_cloud(prompt=prompt, settings=runtime_settings)
        provider = str(runtime_settings.get("cloud_provider") or "anthropic").strip().lower()
        model = str(runtime_settings.get("cloud_model") or "").strip()
    else:
        note = _call_ollama(prompt=prompt, settings=runtime_settings)
        provider = "ollama"
        model = str(runtime_settings.get("local_model") or os.getenv("RECALL_PHASE6_EVAL_LOCAL_MODEL") or "llama3.2:3b").strip()

    cleaned_note = _clean_note(note)
    vault_path = _save_to_vault(job=job, note_text=cleaned_note) if save_to_vault else None

    return {
        "note_id": f"outreach_note_{_slugify(normalized_job_id)}",
        "job_id": normalized_job_id,
        "provider": provider,
        "model": model,
        "generated_at": now_iso(),
        "word_count": len([word for word in cleaned_note.split() if word]),
        "note": cleaned_note,
        "saved_to_vault": vault_path is not None,
        "vault_path": vault_path,
    }
