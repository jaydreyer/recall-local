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


if __name__ == "__main__":
    unittest.main()
