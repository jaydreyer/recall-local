#!/usr/bin/env python3
"""Pytest coverage for Phase 6 resume-bullet helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.phase6 import resume_bullets_drafter


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("Line one\n\n\nLine two\n", "- Line one\n- Line two"),
        ("  * One  \n2. Two", "- One\n- Two"),
    ],
)
def test_clean_bullets_normalizes_bullets(raw_text: str, expected: str) -> None:
    assert resume_bullets_drafter._clean_bullets(raw_text) == expected


def test_generate_resume_bullets_local_mode_returns_cleaned_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        resume_bullets_drafter,
        "get_job",
        lambda job_id: {
            "jobId": job_id,
            "title": "Solutions Engineer",
            "company": "OpenAI",
            "location": "Remote",
            "description": "Help customers adopt AI platforms.",
            "matching_skills": [{"skill": "API strategy"}],
            "gaps": [{"gap": "Kubernetes"}],
            "score_rationale": "Strong platform and customer-facing fit.",
        },
    )
    monkeypatch.setattr(resume_bullets_drafter, "_load_resume_text", lambda: "Resume with API platform work.")
    monkeypatch.setattr(
        resume_bullets_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "local", "local_model": "qwen2.5:7b-instruct"},
    )
    monkeypatch.setattr(
        resume_bullets_drafter,
        "_call_ollama",
        lambda prompt, settings: "* Built AI workflow systems.\n* Led API rollouts.\n* Partnered with customers closely.\n* Translated technical complexity into adoption plans.",
    )

    result = resume_bullets_drafter.generate_resume_bullets(job_id="job-1")

    assert result["job_id"] == "job-1"
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen2.5:7b-instruct"
    assert result["bullets"].startswith("- Built AI workflow systems.")
    assert result["bullet_count"] == 4
    assert result["word_count"] > 0
    assert result["saved_to_vault"] is False


def test_generate_resume_bullets_can_write_to_vault(
    monkeypatch: pytest.MonkeyPatch,
    temp_vault_path: Path,
) -> None:
    monkeypatch.setattr(
        resume_bullets_drafter,
        "get_job",
        lambda job_id: {
            "jobId": job_id,
            "title": "Forward Deployed Engineer",
            "company": "Anthropic",
            "url": "https://example.com/jobs/1",
            "location": "Remote",
            "description": "Own customer deployments.",
        },
    )
    monkeypatch.setattr(resume_bullets_drafter, "_load_resume_text", lambda: "Resume text.")
    monkeypatch.setattr(
        resume_bullets_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "cloud", "cloud_provider": "openai", "cloud_model": "gpt-5"},
    )
    monkeypatch.setattr(
        resume_bullets_drafter,
        "_call_cloud",
        lambda prompt, settings: "- Operated complex AI systems.\n- Worked directly with customers.\n- Delivered production outcomes.\n- Built pragmatic rollout systems.",
    )

    result = resume_bullets_drafter.generate_resume_bullets(job_id="job-99", save_to_vault=True)

    assert result["provider"] == "openai"
    assert result["model"] == "gpt-5"
    assert result["saved_to_vault"] is True
    assert result["vault_path"] is not None

    saved_path = Path(result["vault_path"])
    assert saved_path.exists()
    assert saved_path.is_relative_to(temp_vault_path)
    assert "Forward Deployed Engineer" in saved_path.read_text(encoding="utf-8")
