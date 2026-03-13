#!/usr/bin/env python3
"""Pytest coverage for Phase 4 trend summarizer helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.phase4 import summarize_eval_trend


@pytest.mark.parametrize(
    ("raw_note", "expected"),
    [
        ("execution error: timeout", "execution_error"),
        ("latency 18000ms exceeded threshold", "latency_threshold_exceeded"),
        ("expected doc_id mismatch", "expected_doc_mismatch"),
        ("unexpected custom note", "unexpected custom note"),
    ],
)
def test_normalize_reason_maps_known_prefixes(raw_note: str, expected: str) -> None:
    assert summarize_eval_trend._normalize_reason(raw_note) == expected


def test_extract_failure_reasons_splits_notes_and_defaults_missing() -> None:
    results = [
        {"passed": False, "notes": "execution error: boom; latency 17000ms"},
        {"passed": False, "notes": ""},
        {"passed": True, "notes": "ignored because passed"},
    ]

    assert summarize_eval_trend._extract_failure_reasons(results) == [
        "execution_error",
        "latency_threshold_exceeded",
        "missing_failure_note",
    ]


def test_load_run_summary_returns_error_when_result_file_missing(tmp_path: Path) -> None:
    meta_path = tmp_path / "core.meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "suite": "core",
                "iteration": 1,
                "command_exit": 0,
                "result_json": str(tmp_path / "missing-result.json"),
                "stderr_log": str(tmp_path / "stderr.log"),
            }
        ),
        encoding="utf-8",
    )

    summary = summarize_eval_trend._load_run_summary(meta_path)

    assert summary.status == "error"
    assert summary.failure_reasons == ["missing_result_json_file"]
    assert summary.error == "result_json_missing"


def test_render_markdown_includes_suite_summary_and_breaches() -> None:
    rendered = summarize_eval_trend._render_markdown(
        label="Phase 4A eval soak",
        generated_at="2026-03-13T12:00:00+00:00",
        min_pass_rate=0.9,
        max_avg_latency_ms=15000,
        overall_status="fail",
        threshold_breaches=["core:avg_latency_above_threshold:16000.0>15000"],
        by_suite={
            "core": {
                "run_count": 2,
                "pass_run_count": 1,
                "fail_run_count": 1,
                "error_run_count": 0,
                "avg_case_pass_rate": 0.95,
                "avg_latency_ms": 16000.0,
                "failure_reason_histogram": {"latency_threshold_exceeded": 1},
                "runs": [
                    {
                        "iteration": 1,
                        "status": "fail",
                        "command_exit": 0,
                        "passed": 9,
                        "total": 10,
                        "case_pass_rate": 0.9,
                        "latency_ms": 16000,
                        "result_json": "/tmp/result.json",
                        "stderr_log": "/tmp/stderr.log",
                    }
                ],
            }
        },
    )

    assert "# Phase 4A eval soak" in rendered
    assert "core:avg_latency_above_threshold:16000.0>15000" in rendered
    assert "| core | 2 | 1 | 1 | 0 | 0.950 | 16000.0 |" in rendered
    assert "- latency_threshold_exceeded: 1" in rendered
