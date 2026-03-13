#!/usr/bin/env python3
"""Pytest coverage for Phase 6 cover letter draft helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.phase6 import cover_letter_drafter


@pytest.mark.parametrize(
    ("raw_text", "expected"),
    [
        ("Line one\n\n\nLine two\n", "Line one\n\nLine two"),
        ("  Dear team  \nRegards  ", "Dear team\nRegards"),
    ],
)
def test_clean_draft_normalizes_spacing(raw_text: str, expected: str) -> None:
    assert cover_letter_drafter._clean_draft(raw_text) == expected


def test_generate_cover_letter_draft_local_mode_returns_cleaned_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cover_letter_drafter,
        "get_job",
        lambda job_id: {
            "jobId": job_id,
            "title": "Solutions Engineer",
            "company": "OpenAI",
            "location": "Remote",
            "description": "Help customers adopt AI platforms.",
            "matching_skills": [{"skill": "API strategy"}],
        },
    )
    monkeypatch.setattr(cover_letter_drafter, "_load_resume_text", lambda: "Resume with API platform work.")
    monkeypatch.setattr(
        cover_letter_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "local", "local_model": "qwen2.5:7b-instruct"},
    )
    monkeypatch.setattr(cover_letter_drafter, "_call_ollama", lambda prompt, settings: "Hello\n\n\nWorld")

    result = cover_letter_drafter.generate_cover_letter_draft(job_id="job-1")

    assert result["job_id"] == "job-1"
    assert result["provider"] == "ollama"
    assert result["model"] == "qwen2.5:7b-instruct"
    assert result["draft"] == "Hello\n\nWorld"
    assert result["word_count"] == 2
    assert result["saved_to_vault"] is False


def test_generate_cover_letter_draft_can_write_to_vault(
    monkeypatch: pytest.MonkeyPatch,
    temp_vault_path: Path,
) -> None:
    monkeypatch.setattr(
        cover_letter_drafter,
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
    monkeypatch.setattr(cover_letter_drafter, "_load_resume_text", lambda: "Resume text.")
    monkeypatch.setattr(
        cover_letter_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "cloud", "cloud_provider": "openai", "cloud_model": "gpt-5"},
    )
    monkeypatch.setattr(cover_letter_drafter, "_call_cloud", lambda prompt, settings: "Dear team,\n\nThanks.")

    result = cover_letter_drafter.generate_cover_letter_draft(job_id="job-99", save_to_vault=True)

    assert result["provider"] == "openai"
    assert result["model"] == "gpt-5"
    assert result["saved_to_vault"] is True
    assert result["vault_path"] is not None

    saved_path = Path(result["vault_path"])
    assert saved_path.exists()
    assert saved_path.is_relative_to(temp_vault_path)
    assert "Forward Deployed Engineer" in saved_path.read_text(encoding="utf-8")
