#!/usr/bin/env python3
"""Regression tests for Phase 6B career-page discovery sources."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.phase6 import job_discovery_runner


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requested_urls: list[str] = []

    def get(self, url: str, params: dict[str, object] | None = None) -> _FakeResponse:
        self.requested_urls.append(url if not params else f"{url}?{params}")
        return _FakeResponse(self.payload)


class Phase6BJobDiscoveryRunnerTests(unittest.TestCase):
    def test_discover_career_pages_supports_ashby_boards(self) -> None:
        client = _FakeClient(
            {
                "jobs": [
                    {
                        "id": "openai-1",
                        "title": "AI Deployment Engineer",
                        "location": "Remote - US",
                        "jobUrl": "https://jobs.ashbyhq.com/openai/a0f063e7-8d60-43d8-a042-7612c7adc8fb",
                        "applyUrl": "https://jobs.ashbyhq.com/openai/a0f063e7-8d60-43d8-a042-7612c7adc8fb/application",
                        "descriptionPlain": "Guide enterprise customers from prototype to production on the OpenAI platform.",
                        "publishedAt": "2026-02-27T18:00:00.000+00:00",
                    },
                    {
                        "id": "openai-2",
                        "title": "Research Engineer",
                        "location": "San Francisco",
                        "jobUrl": "https://jobs.ashbyhq.com/openai/240d459b-696d-43eb-8497-fab3e56ecd9b",
                        "descriptionPlain": "Not relevant to customer-facing role filters.",
                        "publishedAt": "2026-02-26T18:00:00.000+00:00",
                    },
                ],
                "apiVersion": "0.1",
            }
        )
        career_config = {
            "companies": [
                {
                    "name": "OpenAI",
                    "tier": 2,
                    "ats": "ashby",
                    "board_id": "openai",
                    "title_filter": ["deployment"],
                }
            ]
        }

        with patch("scripts.phase6.job_discovery_runner._pause"):
            jobs, errors, metrics = job_discovery_runner._discover_career_pages(
                client=client,
                source_limit=3,
                delay_seconds=0.0,
                career_config=career_config,
            )

        self.assertEqual(errors, [])
        self.assertEqual(metrics["attempted"], 1)
        self.assertEqual(metrics["returned"], 1)
        self.assertEqual(client.requested_urls, ["https://api.ashbyhq.com/posting-api/job-board/openai"])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["company"], "OpenAI")
        self.assertEqual(jobs[0]["location"], "Remote - US")
        self.assertEqual(jobs[0]["location_type"], "remote")
        self.assertEqual(jobs[0]["url"], "https://jobs.ashbyhq.com/openai/a0f063e7-8d60-43d8-a042-7612c7adc8fb")
        self.assertEqual(
            jobs[0]["description"],
            "Guide enterprise customers from prototype to production on the OpenAI platform.",
        )
        self.assertEqual(jobs[0]["date_posted"], "2026-02-27T18:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
