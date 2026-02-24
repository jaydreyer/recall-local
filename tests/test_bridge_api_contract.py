#!/usr/bin/env python3
"""Endpoint contract tests for the FastAPI ingestion bridge."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts.phase1 import ingest_bridge_api
from scripts.phase1.ingestion_pipeline import IngestResult


@contextmanager
def build_client(env_updates: dict[str, str]) -> Iterator[TestClient]:
    with patch.dict(os.environ, env_updates, clear=False):
        app = ingest_bridge_api.create_app()
        with TestClient(app) as client:
            yield client


class BridgeApiContractTests(unittest.TestCase):
    def test_auth_rejects_missing_or_invalid_key_and_allows_valid_key(self) -> None:
        env = {
            "RECALL_API_KEY": "phase5-secret",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "50",
        }
        with build_client(env) as client:
            missing = client.post("/v1/ingestions?dry_run=true", json={"channel": "unsupported"})
            invalid = client.post(
                "/v1/ingestions?dry_run=true",
                json={"channel": "unsupported"},
                headers={"X-API-Key": "wrong-secret"},
            )
            valid = client.post(
                "/v1/ingestions?dry_run=true",
                json={"channel": "unsupported"},
                headers={"X-API-Key": "phase5-secret"},
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(missing.json()["error"]["code"], "unauthorized")
        self.assertEqual(invalid.status_code, 401)
        self.assertEqual(invalid.json()["error"]["code"], "unauthorized")
        self.assertEqual(valid.status_code, 400)
        self.assertEqual(valid.json()["error"]["code"], "unsupported_channel")

    def test_rate_limit_blocks_third_request_in_window(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "2",
        }
        with build_client(env) as client:
            first = client.post("/v1/ingestions?dry_run=true", json={"channel": "unsupported"})
            second = client.post("/v1/ingestions?dry_run=true", json={"channel": "unsupported"})
            third = client.post("/v1/ingestions?dry_run=true", json={"channel": "unsupported"})

        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(third.status_code, 429)
        self.assertEqual(third.json()["error"]["code"], "rate_limited")
        self.assertTrue(third.json()["error"]["details"])
        self.assertEqual(third.json()["error"]["details"][0]["field"], "retry_after_seconds")

    def test_auto_tag_rules_endpoint_supports_canonical_and_alias_paths(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            canonical = client.get("/v1/auto-tag-rules")
            alias = client.get("/config/auto-tags")

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(alias.status_code, 200)
        self.assertIn("groups", canonical.json())
        self.assertEqual(canonical.json(), alias.json())

    def test_ingestion_propagates_group_and_tags_with_reference_fallback(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        fake_result = IngestResult(
            run_id="run-1",
            ingest_id="ingest-1",
            doc_id="doc-1",
            source_type="text",
            source_ref="inline:text",
            title="Example",
            source_identity="inline:text",
            chunks_created=1,
            moved_to=None,
            replace_existing=False,
            replaced_points=0,
            replacement_status="skipped",
            latency_ms=1,
            status="dry_run",
        )
        with patch("scripts.phase1.ingest_bridge_api.ingest_request", return_value=fake_result) as mock_ingest:
            with build_client(env) as client:
                response = client.post(
                    "/v1/ingestions?dry_run=true",
                    json={
                        "channel": "bookmarklet",
                        "type": "text",
                        "content": "hello world",
                        "group": "not-a-group",
                        "tags": ["alpha", "beta"],
                    },
                )

        self.assertEqual(response.status_code, 200)
        request_obj = mock_ingest.call_args.args[0]
        self.assertEqual(request_obj.group, "reference")
        self.assertEqual(request_obj.tags, ["alpha", "beta"])

    def test_rag_query_normalizes_filter_group(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with patch("scripts.phase1.ingest_bridge_api.run_rag_query", return_value={"answer": "ok", "audit": {}}) as mock_rag:
            with build_client(env) as client:
                response = client.post(
                    "/v1/rag-queries?dry_run=true",
                    json={
                        "query": "test query",
                        "filter_group": "INVALID_GROUP",
                        "filter_tags": ["job-search"],
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_rag.call_args.kwargs["filter_group"], "reference")


if __name__ == "__main__":
    unittest.main()
