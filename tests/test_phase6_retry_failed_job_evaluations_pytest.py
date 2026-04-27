#!/usr/bin/env python3
"""Regression coverage for failed Phase 6 evaluation retry helper."""

from __future__ import annotations

import json

from scripts.phase6 import retry_failed_job_evaluations


def test_find_failed_jobs_filters_to_error_status_and_preserves_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(
        retry_failed_job_evaluations.job_repository,
        "list_jobs",
        lambda **kwargs: {
            "items": [
                {
                    "jobId": "job-1",
                    "title": "Solutions Engineer",
                    "company": "OpenAI",
                    "status": "error",
                    "evaluation_error": "bad json",
                },
                {
                    "jobId": "job-2",
                    "title": "Solutions Architect",
                    "company": "Postman",
                    "status": "evaluated",
                    "evaluation_error": "should not appear",
                },
            ]
        },
    )

    failed = retry_failed_job_evaluations.find_failed_jobs(limit=10)

    assert failed == [
        {
            "jobId": "job-1",
            "title": "Solutions Engineer",
            "company": "OpenAI",
            "evaluation_error": "bad json",
        }
    ]


def test_main_dry_run_prints_matching_failed_jobs(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        retry_failed_job_evaluations,
        "find_failed_jobs",
        lambda **kwargs: [
            {
                "jobId": "job-1",
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "evaluation_error": "bad json",
            }
        ],
    )

    exit_code = retry_failed_job_evaluations.main(["--dry-run"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["matched"] == 1
    assert payload["jobs"][0]["evaluation_error"] == "bad json"
    assert payload["message"] == "Dry run only. No evaluations were retried."


def test_main_reruns_matching_failed_jobs(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        retry_failed_job_evaluations,
        "find_failed_jobs",
        lambda **kwargs: [
            {
                "jobId": "job-1",
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "evaluation_error": "bad json",
            },
            {
                "jobId": "job-2",
                "title": "Solutions Architect",
                "company": "Postman",
                "evaluation_error": "missing scorecard",
            },
        ],
    )
    monkeypatch.setattr(
        retry_failed_job_evaluations,
        "run_retry",
        lambda **kwargs: {
            "run_id": "job_eval_retry_123",
            "status": "completed",
            "queued": 2,
            "job_ids": kwargs["job_ids"],
            "wait": kwargs["wait"],
        },
    )

    exit_code = retry_failed_job_evaluations.main([])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["retry"]["job_ids"] == ["job-1", "job-2"]
    assert payload["retry"]["wait"] is True
    assert payload["message"] == "Retried 2 failed job evaluations."
