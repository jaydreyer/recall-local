#!/usr/bin/env python3
"""Regression tests for cached Phase 6 company profile rollups."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from scripts.phase6 import company_profiler


class CompanyProfilerCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        company_profiler.invalidate_company_profile_cache()
        self._original_ttl = os.environ.get("RECALL_PHASE6_COMPANY_CACHE_SECONDS")
        os.environ["RECALL_PHASE6_COMPANY_CACHE_SECONDS"] = "300"

    def tearDown(self) -> None:
        company_profiler.invalidate_company_profile_cache()
        if self._original_ttl is None:
            os.environ.pop("RECALL_PHASE6_COMPANY_CACHE_SECONDS", None)
        else:
            os.environ["RECALL_PHASE6_COMPANY_CACHE_SECONDS"] = self._original_ttl

    def test_list_company_profiles_reuses_cached_result_for_same_inputs(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "company": "OpenAI",
                "status": "evaluated",
                "fit_score": 91,
                "company_tier": 1,
                "title": "Solutions Engineer",
            }
        ]

        with mock.patch.object(company_profiler, "list_tracked_company_configs", return_value=[]), mock.patch.object(
            company_profiler,
            "_load_persisted_profiles",
            return_value={},
        ), mock.patch.object(
            company_profiler,
            "_hydrate_profile",
            wraps=company_profiler._hydrate_profile,
        ) as hydrate_mock:
            first = company_profiler.list_company_profiles(jobs, include_jobs=False, limit=50)
            second = company_profiler.list_company_profiles(jobs, include_jobs=False, limit=50)

        self.assertEqual(first, second)
        self.assertEqual(hydrate_mock.call_count, 1)

    def test_list_company_profiles_cache_key_changes_when_jobs_change(self) -> None:
        base_jobs = [
            {
                "jobId": "job-1",
                "company": "OpenAI",
                "status": "evaluated",
                "fit_score": 91,
                "company_tier": 1,
                "title": "Solutions Engineer",
            }
        ]
        changed_jobs = [{**base_jobs[0], "fit_score": 72}]

        with mock.patch.object(company_profiler, "list_tracked_company_configs", return_value=[]), mock.patch.object(
            company_profiler,
            "_load_persisted_profiles",
            return_value={},
        ), mock.patch.object(
            company_profiler,
            "_hydrate_profile",
            wraps=company_profiler._hydrate_profile,
        ) as hydrate_mock:
            company_profiler.list_company_profiles(base_jobs, include_jobs=False, limit=50)
            company_profiler.list_company_profiles(changed_jobs, include_jobs=False, limit=50)

        self.assertEqual(hydrate_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
