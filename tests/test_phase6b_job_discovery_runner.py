#!/usr/bin/env python3
"""Regression tests for Phase 6B career-page discovery sources."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from scripts.phase6 import job_discovery_runner


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    def __init__(self, payload: Any) -> None:
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
                        "location": "Hyderabad, India",
                        "jobUrl": "https://jobs.ashbyhq.com/openai/240d459b-696d-43eb-8497-fab3e56ecd9b",
                        "descriptionPlain": "Filtered by title and geography.",
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

    def test_discover_career_pages_filters_greenhouse_to_us_or_ambiguous_remote_locations(self) -> None:
        client = _FakeClient(
            {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Solutions Engineer",
                        "location": {"name": "Remote - US"},
                        "absolute_url": "https://boards.greenhouse.io/workato/jobs/1",
                        "updated_at": "2026-02-27T18:00:00.000Z",
                    },
                    {
                        "id": 2,
                        "title": "Solutions Architect",
                        "location": {"name": "Remote"},
                        "absolute_url": "https://boards.greenhouse.io/workato/jobs/2",
                        "updated_at": "2026-02-27T18:00:00.000Z",
                    },
                    {
                        "id": 3,
                        "title": "Solutions Engineer",
                        "location": {"name": "London, United Kingdom"},
                        "absolute_url": "https://boards.greenhouse.io/workato/jobs/3",
                        "updated_at": "2026-02-27T18:00:00.000Z",
                    },
                    {
                        "id": 4,
                        "title": "Solutions Engineer",
                        "location": {"name": "Hyderabad, India"},
                        "absolute_url": "https://boards.greenhouse.io/workato/jobs/4",
                        "updated_at": "2026-02-27T18:00:00.000Z",
                    },
                ]
            }
        )
        career_config = {
            "companies": [
                {
                    "name": "Workato",
                    "tier": 2,
                    "ats": "greenhouse",
                    "board_id": "workato",
                    "title_filter": ["solutions"],
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
        self.assertEqual(metrics["returned"], 2)
        self.assertEqual([job["location"] for job in jobs], ["Remote - US", "Remote"])

    def test_discover_career_pages_filters_lever_locations(self) -> None:
        client = _FakeClient(
            [
                {
                    "id": "postman-1",
                    "text": "Customer Engineer",
                    "categories": {"location": "Minneapolis, MN"},
                    "hostedUrl": "https://jobs.lever.co/postman/1",
                    "descriptionPlain": "Support customers.",
                    "createdAt": "2026-02-27T18:00:00.000Z",
                },
                {
                    "id": "postman-2",
                    "text": "Customer Engineer",
                    "categories": {"location": "Remote - Europe"},
                    "hostedUrl": "https://jobs.lever.co/postman/2",
                    "descriptionPlain": "Support customers.",
                    "createdAt": "2026-02-27T18:00:00.000Z",
                },
            ]
        )
        career_config = {
            "companies": [
                {
                    "name": "Postman",
                    "tier": 1,
                    "ats": "lever",
                    "board_id": "postman",
                    "title_filter": ["customer"],
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
        self.assertEqual(metrics["returned"], 1)
        self.assertEqual(jobs[0]["company"], "Postman")
        self.assertEqual(jobs[0]["location"], "Minneapolis, MN")


if __name__ == "__main__":
    unittest.main()
