#!/usr/bin/env python3
"""Regression tests for cached Phase 6 gap aggregation."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from scripts.phase6 import gap_aggregator


class GapAggregatorCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        gap_aggregator.invalidate_gap_cache()
        self._original_ttl = os.environ.get("RECALL_PHASE6_GAP_CACHE_SECONDS")
        os.environ["RECALL_PHASE6_GAP_CACHE_SECONDS"] = "300"

    def tearDown(self) -> None:
        gap_aggregator.invalidate_gap_cache()
        if self._original_ttl is None:
            os.environ.pop("RECALL_PHASE6_GAP_CACHE_SECONDS", None)
        else:
            os.environ["RECALL_PHASE6_GAP_CACHE_SECONDS"] = self._original_ttl

    def test_aggregate_gaps_reuses_cached_result_for_same_evaluated_jobs(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "status": "evaluated",
                "fit_score": 88,
                "evaluated_at": "2026-03-10T22:00:00Z",
                "gaps": [{"gap": "Kubernetes", "severity": "moderate"}],
                "matching_skills": ["APIs"],
            }
        ]

        with mock.patch.object(
            gap_aggregator,
            "merge_similar_gaps",
            wraps=gap_aggregator.merge_similar_gaps,
        ) as merge_mock:
            first = gap_aggregator.aggregate_gaps(jobs)
            second = gap_aggregator.aggregate_gaps(jobs)

        self.assertEqual(first["aggregated_gaps"], second["aggregated_gaps"])
        self.assertEqual(merge_mock.call_count, 1)

    def test_aggregate_gaps_cache_key_changes_when_gap_payload_changes(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "status": "evaluated",
                "fit_score": 88,
                "evaluated_at": "2026-03-10T22:00:00Z",
                "gaps": [{"gap": "Kubernetes", "severity": "moderate"}],
                "matching_skills": ["APIs"],
            }
        ]

        changed_jobs = [
            {
                **jobs[0],
                "evaluated_at": "2026-03-10T22:05:00Z",
                "gaps": [{"gap": "Solution Architecture", "severity": "critical"}],
            }
        ]

        with mock.patch.object(
            gap_aggregator,
            "merge_similar_gaps",
            wraps=gap_aggregator.merge_similar_gaps,
        ) as merge_mock:
            gap_aggregator.aggregate_gaps(jobs)
            gap_aggregator.aggregate_gaps(changed_jobs)

        self.assertEqual(merge_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
