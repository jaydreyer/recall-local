#!/usr/bin/env python3
"""Phase 6C regression tests for evaluation observation and metadata normalization."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.phase6 import job_evaluator, job_metadata_extractor, job_repository


class Phase6CEvaluatorObservationTests(unittest.TestCase):
    def test_parse_evaluation_computes_rubric_based_fit_score(self) -> None:
        parsed = job_evaluator.parse_evaluation(
            """
            {
              "fit_score": 92,
              "scorecard": {
                "role_alignment": 5,
                "technical_alignment": 4,
                "domain_alignment": 3,
                "seniority_alignment": 4,
                "communication_alignment": 5
              },
              "score_rationale": "Strong alignment with customer-facing technical work.",
              "matching_skills": [
                {"skill": "solution design", "evidence": "Led technical discovery"},
                {"skill": "api strategy", "evidence": "Led API governance"},
                {"skill": "enablement", "evidence": "Ran cross-functional launch plans"},
                {"skill": "stakeholder management", "evidence": ""}
              ],
              "gaps": [
                {
                  "gap": "Kubernetes",
                  "severity": "moderate",
                  "recommendations": []
                }
              ]
            }
            """
        )

        self.assertEqual(parsed["fit_score"], 82)
        self.assertEqual(parsed["raw_model_fit_score"], 92)
        self.assertEqual(parsed["scoring_version"], "rubric_v1")
        self.assertEqual(parsed["scorecard"]["technical_alignment"], 4)

    def test_parse_evaluation_preserves_recommendation_urls(self) -> None:
        parsed = job_evaluator.parse_evaluation(
            """
            {
              "scorecard": {
                "role_alignment": 4,
                "technical_alignment": 4,
                "domain_alignment": 3,
                "seniority_alignment": 4,
                "communication_alignment": 4
              },
              "score_rationale": "Strong alignment with customer-facing technical work.",
              "matching_skills": [{"skill": "solution design", "evidence": "Led technical discovery"}],
              "gaps": [
                {
                  "gap": "Kubernetes",
                  "severity": "moderate",
                  "recommendations": [
                    {
                      "type": "course",
                      "title": "Kubernetes for Developers",
                      "source": "KodeKloud",
                      "url": "https://kodekloud.com/courses/kubernetes-for-developers/",
                      "effort": "20 hours"
                    }
                  ]
                }
              ]
            }
            """
        )

        recommendation = parsed["gaps"][0]["recommendations"][0]
        self.assertEqual(recommendation["url"], "https://kodekloud.com/courses/kubernetes-for-developers/")

    def test_parse_evaluation_removes_gap_that_duplicates_evidenced_matching_skill(self) -> None:
        parsed = job_evaluator.parse_evaluation(
            """
            {
              "scorecard": {
                "role_alignment": 4,
                "technical_alignment": 4,
                "domain_alignment": 4,
                "seniority_alignment": 4,
                "communication_alignment": 5
              },
              "score_rationale": "Strong alignment with customer-facing AI deployment work.",
              "matching_skills": [
                {
                  "skill": "Generative AI (ChatGPT)",
                  "evidence": "Built a custom GPT replacing a $50K recruiter workflow."
                }
              ],
              "gaps": [
                {
                  "gap": "Generative AI (ChatGPT) experience",
                  "severity": "moderate",
                  "recommendations": []
                },
                {
                  "gap": "Pre-sales demos",
                  "severity": "moderate",
                  "recommendations": []
                }
              ]
            }
            """
        )

        self.assertEqual(len(parsed["matching_skills"]), 1)
        self.assertEqual(len(parsed["gaps"]), 1)
        self.assertEqual(parsed["gaps"][0]["gap"], "Pre-sales demos")

    def test_parse_evaluation_dedupes_matching_skills_and_gaps_by_canonical_label(self) -> None:
        parsed = job_evaluator.parse_evaluation(
            """
            {
              "scorecard": {
                "role_alignment": 4,
                "technical_alignment": 4,
                "domain_alignment": 3,
                "seniority_alignment": 4,
                "communication_alignment": 4
              },
              "score_rationale": "Solid fit with one notable execution gap.",
              "matching_skills": [
                {"skill": "API strategy", "evidence": "Led API governance"},
                {"skill": "API strategy experience", "evidence": "Led API governance"}
              ],
              "gaps": [
                {"gap": "Kubernetes", "severity": "moderate", "recommendations": []},
                {"gap": "Kubernetes experience", "severity": "minor", "recommendations": []}
              ]
            }
            """
        )

        self.assertEqual(len(parsed["matching_skills"]), 1)
        self.assertEqual(parsed["matching_skills"][0]["skill"], "API strategy")
        self.assertEqual(len(parsed["gaps"]), 1)
        self.assertEqual(parsed["gaps"][0]["gap"], "Kubernetes")

    def test_ground_evaluation_replaces_generic_gap_with_explicit_requirement_gap(self) -> None:
        evaluation = {
            "fit_score": 75,
            "raw_model_fit_score": None,
            "scorecard": {
                "role_alignment": 4,
                "technical_alignment": 4,
                "domain_alignment": 5,
                "seniority_alignment": 3,
                "communication_alignment": 5,
            },
            "scoring_version": "rubric_v1",
            "score_rationale": "Strong fit with one notable gap.",
            "matching_skills": [
                {"skill": "API governance", "evidence": "Led API governance"},
                {"skill": "Developer workflows", "evidence": "Managed developer portal"},
            ],
            "gaps": [
                {"gap": "Leadership experience", "severity": "critical", "recommendations": []},
            ],
            "application_tips": "",
            "cover_letter_angle": "",
        }

        grounded = job_evaluator._ground_evaluation_to_context(  # noqa: SLF001
            job={
                "title": "Solutions Engineer",
                "company": "Postman",
                "location": "Remote - US",
                "description": "Lead technical discovery, run product demos, and support proof-of-concept delivery for enterprise customers.",
            },
            resume_text="API governance, developer experience, and stakeholder enablement background.",
            evaluation=evaluation,
        )

        gaps = [item["gap"] for item in grounded["gaps"]]
        self.assertIn("Pre-sales demo delivery", gaps)
        self.assertNotIn("Leadership experience", gaps)
        self.assertGreaterEqual(grounded["fit_score"], 79)

    def test_ground_evaluation_adds_missing_backend_requirement_gaps(self) -> None:
        evaluation = {
            "fit_score": 47,
            "raw_model_fit_score": None,
            "scorecard": {
                "role_alignment": 3,
                "technical_alignment": 2,
                "domain_alignment": 2,
                "seniority_alignment": 2,
                "communication_alignment": 4,
            },
            "scoring_version": "rubric_v1",
            "score_rationale": "Stretch fit with backend gaps.",
            "matching_skills": [
                {"skill": "API governance", "evidence": "Worked with engineering teams"},
            ],
            "gaps": [
                {"gap": "infrastructure specialization", "severity": "moderate", "recommendations": []},
            ],
            "application_tips": "",
            "cover_letter_angle": "",
        }

        grounded = job_evaluator._ground_evaluation_to_context(  # noqa: SLF001
            job={
                "title": "Senior Backend Engineer",
                "company": "Glean",
                "location": "Remote - US",
                "description": "Build distributed services in Go and improve Kubernetes-based infrastructure reliability.",
            },
            resume_text="Strong API governance, stakeholder communication, and developer enablement background.",
            evaluation=evaluation,
        )

        gaps = [item["gap"] for item in grounded["gaps"]]
        self.assertIn("Go backend engineering", gaps)
        self.assertIn("Kubernetes / container orchestration", gaps)

    def test_ground_evaluation_adds_requirement_aligned_matching_skill_hints(self) -> None:
        evaluation = {
            "fit_score": 90,
            "raw_model_fit_score": None,
            "scorecard": {
                "role_alignment": 5,
                "technical_alignment": 5,
                "domain_alignment": 4,
                "seniority_alignment": 4,
                "communication_alignment": 5,
            },
            "scoring_version": "rubric_v1",
            "score_rationale": "Strong fit for customer deployment work.",
            "matching_skills": [
                {"skill": "API integration", "evidence": "Managed API developer experience"},
            ],
            "gaps": [],
            "application_tips": "",
            "cover_letter_angle": "",
        }

        grounded = job_evaluator._ground_evaluation_to_context(  # noqa: SLF001
            job={
                "title": "AI Deployment Engineer",
                "company": "OpenAI",
                "location": "Remote - US",
                "description": "Partner with account teams, guide implementation programs, review architectures, and support customer stakeholders.",
            },
            resume_text="Guided platform adoption, implementation planning, cross-functional stakeholder work, and executive customer communication.",
            evaluation=evaluation,
        )

        skills = [item["skill"] for item in grounded["matching_skills"]]
        self.assertIn("Solutions architecture", skills)
        self.assertIn("Customer and stakeholder partnership", skills)

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
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True),
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
        self.assertEqual(observation["scoring"]["version"], "rubric_v1")
        self.assertEqual(observation["scoring"]["computed_fit_score"], 91)
        self.assertEqual(store_mock.call_count, 1)
        persisted = store_mock.call_args.kwargs["evaluation"]
        self.assertIn("observation", persisted)

    def test_evaluate_job_keeps_local_result_when_cloud_escalation_is_unavailable(self) -> None:
        local_eval = {
            "fit_score": 79,
            "score_rationale": "Short rationale",
            "matching_skills": [{"skill": "api strategy", "evidence": "Led API governance"}],
            "gaps": [],
            "application_tips": "Lead with platform storytelling.",
            "cover_letter_angle": "Bridge technical systems with business adoption.",
        }
        job_payload = {
            "job_id": "job-2",
            "title": "Platform Lead",
            "company": "ExampleCo",
            "company_tier": 1,
            "location": "Remote - US",
            "description": "Remote role working with platform teams.",
            "url": "https://jobs.example.com/2",
        }
        settings = {
            "evaluation_model": "local",
            "cloud_provider": "anthropic",
            "auto_escalate": True,
            "escalate_threshold_gaps": 2,
            "escalate_threshold_rationale_words": 20,
        }

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("scripts.phase6.job_evaluator._load_job_payload", return_value=job_payload),
            patch("scripts.phase6.job_evaluator._load_resume_text", return_value="Resume body"),
            patch("scripts.phase6.job_evaluator._call_ollama", return_value='{"fit_score": 79}'),
            patch("scripts.phase6.job_evaluator._call_cloud") as cloud_mock,
            patch("scripts.phase6.job_evaluator._parse_with_retry", return_value=local_eval),
            patch("scripts.phase6.job_evaluator._store_evaluation"),
        ):
            result = job_evaluator.evaluate_job(job_id="job-2", settings=settings)

        self.assertEqual(result["evaluation_model"], "local")
        self.assertEqual(result["observation"]["provider_sequence"], "local")
        self.assertFalse(result["observation"]["escalation"]["enabled"])
        self.assertFalse(result["observation"]["escalation"]["triggered"])
        self.assertEqual(result["observation"]["escalation"]["reasons"], [])
        cloud_mock.assert_not_called()


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
