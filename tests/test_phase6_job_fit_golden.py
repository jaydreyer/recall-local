#!/usr/bin/env python3
"""Tests for the Phase 6 job-fit golden evaluation runner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.eval import run_job_fit_golden


class JobFitGoldenRunnerTests(unittest.TestCase):
    def test_load_cases_parses_expected_fields(self) -> None:
        payload = [
            {
                "case_id": "solutions-engineer",
                "category": "strong_fit",
                "title": "Solutions Engineer",
                "company": "ExampleCo",
                "location": "Remote - US",
                "url": "https://example.com/roles/1",
                "description": "Customer-facing API role",
                "resume_text": "API governance and enablement background",
                "expected_score_min": 75,
                "expected_score_max": 95,
                "required_matching_skills": ["API"],
                "required_gap_terms": ["demo"],
                "forbidden_gap_terms": ["API governance"],
                "forbidden_matching_skills": ["quota"],
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cases.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            cases = run_job_fit_golden.load_cases(path)

        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case.case_id, "solutions-engineer")
        self.assertEqual(case.expected_score_min, 75)
        self.assertEqual(case.required_matching_skills, ["API"])
        self.assertEqual(case.forbidden_matching_skills, ["quota"])

    def test_evaluate_case_checks_score_ranges_and_expected_terms(self) -> None:
        case = run_job_fit_golden.GoldenCase(
            case_id="solutions-engineer",
            category="strong_fit",
            title="Solutions Engineer",
            company="ExampleCo",
            location="Remote - US",
            url="https://example.com/roles/1",
            description="Customer-facing API role",
            resume_text="API governance and enablement background",
            expected_score_min=75,
            expected_score_max=95,
            required_matching_skills=["API", "stakeholder"],
            required_gap_terms=["demo"],
            forbidden_gap_terms=["API governance"],
            forbidden_matching_skills=["quota"],
        )

        parsed = {
            "fit_score": 86,
            "matching_skills": [
                {"skill": "API governance"},
                {"skill": "Stakeholder communication"},
            ],
            "gaps": [
                {"gap": "Pre-sales demo delivery"},
            ],
        }

        with (
            patch("scripts.eval.run_job_fit_golden.job_evaluator._build_evaluation_prompt", return_value="PROMPT"),
            patch("scripts.eval.run_job_fit_golden.job_evaluator._call_ollama", return_value="{}"),
            patch("scripts.eval.run_job_fit_golden.job_evaluator.parse_evaluation", return_value=parsed),
            patch("scripts.eval.run_job_fit_golden.job_evaluator._ground_evaluation_to_context", return_value=parsed),
        ):
            result = run_job_fit_golden.evaluate_case(case, settings={"evaluation_model": "local"})

        self.assertTrue(result["passed"], result["notes"])
        self.assertEqual(result["score"], 86)
        self.assertEqual(result["matching_skills"], ["API governance", "Stakeholder communication"])

    def test_evaluate_case_fails_when_forbidden_or_missing_terms_appear(self) -> None:
        case = run_job_fit_golden.GoldenCase(
            case_id="enterprise-ae",
            category="mixed_fit",
            title="Enterprise Account Executive",
            company="ExampleCo",
            location="Remote - US",
            url="https://example.com/roles/2",
            description="Quota role",
            resume_text="Technical enablement background",
            expected_score_min=40,
            expected_score_max=70,
            required_matching_skills=["enterprise"],
            required_gap_terms=["quota"],
            forbidden_gap_terms=["executive communication"],
            forbidden_matching_skills=["quota"],
        )

        parsed = {
            "fit_score": 81,
            "matching_skills": [
                {"skill": "Executive communication"},
                {"skill": "Quota carrying"},
            ],
            "gaps": [
                {"gap": "Commercial closing"},
            ],
        }

        with (
            patch("scripts.eval.run_job_fit_golden.job_evaluator._build_evaluation_prompt", return_value="PROMPT"),
            patch("scripts.eval.run_job_fit_golden.job_evaluator._call_ollama", return_value="{}"),
            patch("scripts.eval.run_job_fit_golden.job_evaluator.parse_evaluation", return_value=parsed),
            patch("scripts.eval.run_job_fit_golden.job_evaluator._ground_evaluation_to_context", return_value=parsed),
        ):
            result = run_job_fit_golden.evaluate_case(case, settings={"evaluation_model": "local"})

        self.assertFalse(result["passed"])
        self.assertTrue(any("outside expected range" in note for note in result["notes"]))
        self.assertTrue(any("missing gap terms" in note for note in result["notes"]))
        self.assertTrue(any("forbidden matching skill terms present" in note for note in result["notes"]))

    def test_forbidden_term_matching_uses_signal_overlap_not_substring_noise(self) -> None:
        hits = run_job_fit_golden._contains_any_forbidden(  # noqa: SLF001
            ["API governance", "Stakeholder communication"],
            ["Go"],
        )
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
