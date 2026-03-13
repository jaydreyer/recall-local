#!/usr/bin/env python3
"""Focused regression coverage for Phase 6 evaluator normalization helpers."""

from __future__ import annotations

import pytest

from scripts.phase6 import job_evaluator


def test_normalize_matching_skills_deduplicates_equivalent_entries() -> None:
    normalized = job_evaluator._normalize_matching_skills(
        [
            "API design",
            {"skill": "API design", "evidence": ""},
            {"name": "Customer partnership", "proof": "Worked directly with enterprise stakeholders."},
        ]
    )

    assert normalized == [
        {"skill": "API design", "evidence": ""},
        {"skill": "Customer partnership", "evidence": "Worked directly with enterprise stakeholders."},
    ]


def test_normalize_gaps_coerces_invalid_recommendation_types_and_deduplicates() -> None:
    normalized = job_evaluator._normalize_gaps(
        [
            "Quota-carrying ownership",
            {
                "gap": "Quota-carrying ownership",
                "severity": "critical",
                "recommendations": [{"type": "bootcamp", "title": "Enterprise sales workshop"}],
            },
            {
                "gap": "Kubernetes / container orchestration",
                "severity": "invalid",
                "recommendations": ["Kubernetes handbook"],
            },
        ]
    )

    assert normalized == [
        {"gap": "Quota-carrying ownership", "severity": "moderate", "recommendations": []},
        {
            "gap": "Kubernetes / container orchestration",
            "severity": "moderate",
            "recommendations": [
                {
                    "type": "article",
                    "title": "Kubernetes handbook",
                    "source": "",
                    "url": "",
                    "effort": "",
                }
            ],
        },
    ]


def test_compute_fit_score_applies_weighting_bonus_and_gap_penalty() -> None:
    score = job_evaluator._compute_fit_score(
        scorecard={
            "role_alignment": 5,
            "technical_alignment": 4,
            "domain_alignment": 4,
            "seniority_alignment": 4,
            "communication_alignment": 5,
        },
        matching_skills=[
            {"skill": "API design", "evidence": "Shipped API programs"},
            {"skill": "Stakeholder management", "evidence": "Partnered with execs"},
            {"skill": "Customer discovery", "evidence": "Ran customer calls"},
        ],
        gaps=[{"gap": "Quota carrying", "severity": "critical", "recommendations": []}],
    )

    assert score == 80


def test_ground_evaluation_to_context_adds_explicit_gap_and_removes_conflicting_gap() -> None:
    grounded = job_evaluator._ground_evaluation_to_context(
        job={
            "description": "Need quota carrying ownership, demos, and technical recommendations for customers.",
        },
        resume_text="Built API adoption programs and technical demos for enterprise customers.",
        evaluation={
            "matching_skills": [
                {"skill": "Technical problem solving", "evidence": "Led API platform enablement."},
                {"skill": "Customer and stakeholder partnership", "evidence": "Worked with product and engineering leaders."},
            ],
            "gaps": [{"gap": "Technical problem solving", "severity": "moderate", "recommendations": []}],
            "scorecard": {
                "role_alignment": 4,
                "technical_alignment": 4,
                "domain_alignment": 3,
                "seniority_alignment": 3,
                "communication_alignment": 4,
            },
        },
    )

    gap_names = [item["gap"] for item in grounded["gaps"]]
    match_names = [item["skill"] for item in grounded["matching_skills"]]

    assert "Quota-carrying ownership" in gap_names
    assert "Technical problem solving" in match_names
    assert "Technical problem solving" not in gap_names
    assert grounded["fit_score"] >= 0


def test_evaluate_jobs_keeps_batch_running_when_one_job_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_evaluate_job(*, job_id: str, settings: dict[str, object]) -> dict[str, object]:
        if job_id == "job-2":
            raise ValueError("broken row")
        return {"fit_score": 81, "observation": {"location": {"preference_bucket": "remote"}}}

    monkeypatch.setattr(job_evaluator, "evaluate_job", fake_evaluate_job)
    monkeypatch.setattr(job_evaluator, "_store_error", lambda **kwargs: None)

    result = job_evaluator._evaluate_jobs(job_ids=["job-1", "job-2"], settings={})

    assert result["evaluated"] == 1
    assert result["failed"] == 1
    assert result["results"][0]["status"] == "completed"
    assert result["results"][1]["status"] == "error"
    assert "broken row" in result["results"][1]["error"]
