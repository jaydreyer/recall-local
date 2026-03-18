#!/usr/bin/env python3
"""Unit tests for Phase 6 job repository helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.phase6 import job_repository


class JobRepositoryTests(unittest.TestCase):
    def test_normalize_workflow_includes_cover_letter_artifact_defaults(self) -> None:
        normalized = job_repository._normalize_workflow(
            {
                "packet": {"coverLetterDraft": True},
                "artifacts": {
                    "coverLetterDraft": {
                        "draftId": "cover_letter_job-1",
                        "generatedAt": "2026-03-18T04:10:00Z",
                        "provider": "ollama",
                        "model": "qwen2.5:7b-instruct",
                        "wordCount": 132,
                        "savedToVault": True,
                        "vaultPath": "/tmp/example.md",
                    }
                },
            }
        )

        self.assertTrue(normalized["packet"]["coverLetterDraft"])
        self.assertEqual(normalized["artifacts"]["coverLetterDraft"]["draftId"], "cover_letter_job-1")
        self.assertEqual(normalized["artifacts"]["coverLetterDraft"]["wordCount"], 132)
        self.assertTrue(normalized["artifacts"]["coverLetterDraft"]["savedToVault"])

    def test_list_jobs_search_matches_company_gap_and_notes_fields(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "company_normalized": "openai",
                "company_tier": 2,
                "location": "Remote",
                "source": "career_page",
                "status": "evaluated",
                "fit_score": 88,
                "matching_skills": [{"skill": "API strategy", "evidence": "Owned API launches"}],
                "gaps": [{"gap": "Pre-sales demos", "severity": "moderate"}],
                "application_tips": "Lead with customer-facing API wins.",
                "cover_letter_angle": "Show operator empathy and AI rollout experience.",
                "notes": "Warm intro possible through former partner contact.",
                "observation": {"escalation_reasons": ["gaps_below_threshold"]},
                "discovered_at": "2026-03-12T10:00:00+00:00",
            },
            {
                "jobId": "job-2",
                "title": "Backend Engineer",
                "company": "OtherCo",
                "company_normalized": "otherco",
                "company_tier": 3,
                "location": "Minneapolis, MN",
                "source": "jobspy",
                "status": "evaluated",
                "fit_score": 41,
                "matching_skills": [],
                "gaps": [],
                "application_tips": "",
                "cover_letter_angle": "",
                "notes": "",
                "observation": {},
                "discovered_at": "2026-03-11T10:00:00+00:00",
            },
        ]

        with patch("scripts.phase6.job_repository._scroll_jobs", return_value=jobs):
            by_company = job_repository.list_jobs(status="evaluated", search="openai")
            by_gap = job_repository.list_jobs(status="evaluated", search="pre-sales demos")
            by_notes = job_repository.list_jobs(status="evaluated", search="warm intro")

        self.assertEqual(by_company["total"], 1)
        self.assertEqual(by_company["items"][0]["jobId"], "job-1")
        self.assertEqual(by_gap["total"], 1)
        self.assertEqual(by_gap["items"][0]["jobId"], "job-1")
        self.assertEqual(by_notes["total"], 1)
        self.assertEqual(by_notes["items"][0]["jobId"], "job-1")

    def test_list_jobs_falls_back_to_title_query_when_search_not_provided(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "title": "Forward Deployed Engineer",
                "company": "OpenAI",
                "company_normalized": "openai",
                "company_tier": 2,
                "location": "Remote",
                "source": "career_page",
                "status": "evaluated",
                "fit_score": 84,
                "matching_skills": [],
                "gaps": [],
                "application_tips": "",
                "cover_letter_angle": "",
                "notes": "",
                "observation": {},
                "discovered_at": "2026-03-12T10:00:00+00:00",
            }
        ]

        with patch("scripts.phase6.job_repository._scroll_jobs", return_value=jobs):
            payload = job_repository.list_jobs(status="evaluated", title_query="forward deployed")

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["jobId"], "job-1")


if __name__ == "__main__":
    unittest.main()
