#!/usr/bin/env python3
"""Phase 6C regression tests for evaluation observation and metadata normalization."""

from __future__ import annotations

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.phase6 import job_evaluator, job_metadata_extractor, job_repository


class Phase6CEvaluatorObservationTests(unittest.TestCase):
    def test_parse_with_retry_uses_strict_prompt_after_malformed_json(self) -> None:
        with (
            patch(
                "scripts.phase6.job_evaluator.parse_evaluation",
                side_effect=[
                    job_evaluator.MalformedResponseError("invalid"),
                    {
                        "fit_score": 77,
                        "score_rationale": "Recovered on retry.",
                        "matching_skills": [],
                        "gaps": [],
                    },
                ],
            ) as parse_mock,
            patch("scripts.phase6.job_evaluator._call_ollama", return_value="{}") as ollama_mock,
        ):
            parsed = job_evaluator._parse_with_retry(
                first_response="not-json",
                prompt="ORIGINAL_PROMPT",
                settings={},
                retry_mode="local",
            )

        self.assertEqual(parsed["fit_score"], 77)
        self.assertEqual(parse_mock.call_count, 2)
        strict_prompt = ollama_mock.call_args.kwargs["prompt"]
        self.assertIn("IMPORTANT: Return ONLY a JSON object.", strict_prompt)
        self.assertIn("ORIGINAL_PROMPT", strict_prompt)

    def test_parse_with_retry_raises_when_retry_still_malformed(self) -> None:
        with (
            patch(
                "scripts.phase6.job_evaluator.parse_evaluation",
                side_effect=[
                    job_evaluator.MalformedResponseError("invalid"),
                    job_evaluator.MalformedResponseError("still-invalid"),
                ],
            ),
            patch("scripts.phase6.job_evaluator._call_ollama", return_value="{}"),
        ):
            with self.assertRaises(RuntimeError) as exc_info:
                job_evaluator._parse_with_retry(
                    first_response="not-json",
                    prompt="PROMPT",
                    settings={},
                    retry_mode="local",
                )

        self.assertIn("malformed evaluation JSON after retry", str(exc_info.exception))

    def test_evaluate_job_records_observation_with_escalation_context(self) -> None:
        local_eval = {
            "fit_score": 62,
            "score_rationale": "Short rationale",
            "matching_skills": [{"skill": "sales", "evidence": "quota achievement"}],
            "gaps": [],
            "application_tips": "",
            "cover_letter_angle": "",
        }
        cloud_eval = {
            "fit_score": 91,
            "score_rationale": "Detailed rationale with enough words to pass minimum threshold checks reliably.",
            "matching_skills": [{"skill": "enterprise SaaS", "evidence": "multi-year account management"}],
            "gaps": [{"gap": "territory planning", "severity": "moderate", "recommendations": []}],
            "application_tips": "Lead with enterprise pipeline ownership.",
            "cover_letter_angle": "Customer outcomes at scale.",
        }
        job_payload = {
            "job_id": "job-1",
            "title": "Account Executive",
            "company": "ExampleCo",
            "company_tier": 1,
            "location": "Remote - US",
            "description": "Remote role working with enterprise customers.",
            "url": "https://jobs.example.com/1",
        }
        settings = {
            "evaluation_model": "local",
            "auto_escalate": True,
            "escalate_threshold_gaps": 2,
            "escalate_threshold_rationale_words": 20,
        }

        with (
            patch("scripts.phase6.job_evaluator._load_job_payload", return_value=job_payload),
            patch("scripts.phase6.job_evaluator._load_resume_text", return_value="Resume body"),
            patch("scripts.phase6.job_evaluator._call_ollama", return_value='{"fit_score": 62}'),
            patch("scripts.phase6.job_evaluator._call_cloud", return_value='{"fit_score": 91}'),
            patch("scripts.phase6.job_evaluator._parse_with_retry", side_effect=[local_eval, cloud_eval]),
            patch("scripts.phase6.job_evaluator._store_evaluation") as store_mock,
        ):
            result = job_evaluator.evaluate_job(job_id="job-1", settings=settings)

        self.assertEqual(result["evaluation_model"], "cloud_escalated")
        observation = result["observation"]
        self.assertEqual(observation["provider_sequence"], "local->cloud")
        self.assertTrue(observation["escalation"]["enabled"])
        self.assertTrue(observation["escalation"]["triggered"])
        self.assertIn("gaps_below_threshold", observation["escalation"]["reasons"])
        self.assertIn("rationale_too_short", observation["escalation"]["reasons"])
        self.assertTrue(observation["location"]["is_remote"])
        self.assertEqual(observation["location"]["preference_bucket"], "remote")
        self.assertEqual(store_mock.call_count, 1)
        persisted = store_mock.call_args.kwargs["evaluation"]
        self.assertIn("observation", persisted)


class Phase6CMetadataNormalizationTests(unittest.TestCase):
    def test_extract_job_metadata_normalizes_invalid_source_and_location_type(self) -> None:
        content = "X" * 150
        with patch(
            "scripts.phase6.job_metadata_extractor._extract_with_llm",
            return_value={
                "title": "Senior Engineer",
                "company": "Acme",
                "location": "Remote - US",
                "location_type": "satellite",
                "description": "Fully remote role across the US.",
            },
        ):
            result = job_metadata_extractor.extract_job_metadata(
                {
                    "url": "https://www.linkedin.com/jobs/view/123",
                    "source": "made-up-source",
                    "content": content,
                }
            )

        self.assertEqual(result["source"], "linkedin")
        self.assertEqual(result["location_type"], "remote")

    def test_extract_job_metadata_preserves_allowed_source(self) -> None:
        result = job_metadata_extractor.extract_job_metadata(
            {
                "url": "https://www.linkedin.com/jobs/view/123",
                "source": "chrome_extension",
                "title": "Role",
                "company": "Acme",
                "location": "Minneapolis, MN",
                "content": "short content",
            }
        )

        self.assertEqual(result["source"], "chrome_extension")


class Phase6CJobRepositoryTests(unittest.TestCase):
    def test_normalize_job_includes_observation_dict_and_sanitizes_invalid_values(self) -> None:
        valid_record = SimpleNamespace(
            id="point-1",
            payload={
                "job_id": "job-1",
                "title": "Solutions Engineer",
                "company": "Acme",
                "status": "evaluated",
                "fit_score": 88,
                "observation": {"provider_sequence": "local"},
            },
            vector=None,
        )
        invalid_record = SimpleNamespace(
            id="point-2",
            payload={
                "job_id": "job-2",
                "title": "Solutions Engineer II",
                "company": "Acme",
                "status": "evaluated",
                "fit_score": 81,
                "observation": "not-a-dict",
            },
            vector=None,
        )

        normalized_valid = job_repository._normalize_job(valid_record)  # noqa: SLF001
        normalized_invalid = job_repository._normalize_job(invalid_record)  # noqa: SLF001

        self.assertEqual(normalized_valid["observation"]["provider_sequence"], "local")
        self.assertEqual(normalized_invalid["observation"], {})


if __name__ == "__main__":
    unittest.main()
