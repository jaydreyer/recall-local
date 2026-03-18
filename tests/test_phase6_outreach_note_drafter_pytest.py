#!/usr/bin/env python3
"""Pytest coverage for Phase 6 outreach note helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.phase6 import outreach_note_drafter


def test_clean_note_collapses_extra_spacing() -> None:
    raw = "Hi team,\n\n\nI would love to connect.\r\n\r\nBest,\nJay\n"
    assert outreach_note_drafter._clean_note(raw) == "Hi team,\n\nI would love to connect.\n\nBest,\nJay"


def test_generate_outreach_note_local_mode_returns_cleaned_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        outreach_note_drafter,
        "get_job",
        lambda job_id: {
            "jobId": job_id,
            "title": "Solutions Engineer",
            "company": "OpenAI",
            "location": "Remote",
            "description": "Help customers adopt AI platforms.",
            "matching_skills": [{"skill": "API strategy"}],
            "score_rationale": "Strong platform and customer-facing fit.",
            "cover_letter_angle": "Lead with customer empathy and AI rollout execution.",
        },
    )
    monkeypatch.setattr(outreach_note_drafter, "_load_resume_text", lambda: "Resume with API platform work.")
    monkeypatch.setattr(
        outreach_note_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "local", "local_model": "qwen2.5:7b-instruct"},
    )
    monkeypatch.setattr(
        outreach_note_drafter,
        "_call_ollama",
        lambda prompt, settings: "Hi team,\n\nI’m reaching out because this role aligns closely with my background leading customer-facing AI workflow rollouts and API adoption work.\n\nBest,\nJay",
    )

    result = outreach_note_drafter.generate_outreach_note(job_id="job-1")

    assert result["job_id"] == "job-1"
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen2.5:7b-instruct"
    assert result["note"].startswith("Hi team,")
    assert result["word_count"] > 0
    assert result["saved_to_vault"] is False


def test_generate_outreach_note_can_write_to_vault(
    monkeypatch: pytest.MonkeyPatch,
    temp_vault_path: Path,
) -> None:
    monkeypatch.setattr(
        outreach_note_drafter,
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
    monkeypatch.setattr(outreach_note_drafter, "_load_resume_text", lambda: "Resume text.")
    monkeypatch.setattr(
        outreach_note_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "cloud", "cloud_provider": "openai", "cloud_model": "gpt-5"},
    )
    monkeypatch.setattr(
        outreach_note_drafter,
        "_call_cloud",
        lambda prompt, settings: "Hi there,\n\nI’d love to be considered for this role and would be glad to share more context on my fit leading complex AI deployments.\n\nBest,\nJay",
    )

    result = outreach_note_drafter.generate_outreach_note(job_id="job-99", save_to_vault=True)

    assert result["provider"] == "openai"
    assert result["model"] == "gpt-5"
    assert result["saved_to_vault"] is True
    assert result["vault_path"] is not None

    saved_path = Path(result["vault_path"])
    assert saved_path.exists()
    assert saved_path.is_relative_to(temp_vault_path)
    assert "Forward Deployed Engineer" in saved_path.read_text(encoding="utf-8")
