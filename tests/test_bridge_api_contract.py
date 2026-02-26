#!/usr/bin/env python3
"""Endpoint contract tests for the FastAPI ingestion bridge."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
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

    def test_auto_tag_rules_endpoint_is_canonical_only(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            canonical = client.get("/v1/auto-tag-rules")
            alias = client.get("/config/auto-tags")

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(alias.status_code, 404)
        self.assertEqual(alias.json()["error"]["code"], "not_found")
        self.assertIn("groups", canonical.json())

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

    def test_rag_query_normalizes_filter_group_and_tag_mode(self) -> None:
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
                        "filter_tag_mode": "ALL",
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_rag.call_args.kwargs["filter_group"], "reference")
        self.assertEqual(mock_rag.call_args.kwargs["filter_tag_mode"], "all")

    def test_rag_query_rejects_invalid_filter_tag_mode(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            response = client.post(
                "/v1/rag-queries?dry_run=true",
                json={
                    "query": "test query",
                    "filter_group": "reference",
                    "filter_tags": ["rag"],
                    "filter_tag_mode": "strictly-all",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_failed")
        self.assertIn("filter_tag_mode", response.json()["error"]["message"])

    def test_file_ingestion_endpoint_accepts_supported_upload_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            incoming_dir = os.path.join(temp_dir, "incoming")
            env = {
                "RECALL_API_KEY": "",
                "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
                "DATA_INCOMING": incoming_dir,
            }
            fake_result = IngestResult(
                run_id="run-file-1",
                ingest_id="ingest-file-1",
                doc_id="doc-file-1",
                source_type="file",
                source_ref="incoming/test.md",
                title="test.md",
                source_identity="incoming/test.md",
                chunks_created=1,
                moved_to=None,
                replace_existing=False,
                replaced_points=0,
                replacement_status="skipped",
                latency_ms=5,
                status="dry_run",
            )
            with patch("scripts.phase1.ingest_bridge_api.ingest_request", return_value=fake_result) as mock_ingest:
                with build_client(env) as client:
                    response = client.post(
                        "/v1/ingestions/files?dry_run=true",
                        files={"file": ("test.md", b"# hello", "text/markdown")},
                        data={"group": "invalid-group", "tags": "alpha, beta, alpha", "save_to_vault": "true"},
                    )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"], "workflow_01_ingestion_file")
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(payload["group"], "reference")
        self.assertEqual(payload["tags"], ["alpha", "beta"])
        self.assertTrue(payload["save_to_vault"])
        request_obj = mock_ingest.call_args.args[0]
        self.assertEqual(request_obj.group, "reference")
        self.assertEqual(request_obj.tags, ["alpha", "beta"])
        self.assertTrue(request_obj.metadata["save_to_vault"])

    def test_file_ingestion_endpoint_rejects_unsupported_extension(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            response = client.post(
                "/v1/ingestions/files",
                files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
                data={"group": "reference", "tags": ""},
            )

        self.assertEqual(response.status_code, 415)
        self.assertEqual(response.json()["error"]["code"], "unsupported_media_type")

    def test_file_ingestion_endpoint_rejects_oversized_upload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            incoming_dir = os.path.join(temp_dir, "incoming")
            env = {
                "RECALL_API_KEY": "",
                "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
                "RECALL_MAX_UPLOAD_MB": "1",
                "DATA_INCOMING": incoming_dir,
            }
            with build_client(env) as client:
                response = client.post(
                    "/v1/ingestions/files",
                    files={"file": ("big.md", b"a" * (1024 * 1024 + 1), "text/markdown")},
                    data={"group": "reference", "tags": ""},
                )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"], "payload_too_large")

    def test_vault_tree_endpoint_returns_payload_and_alias_is_removed(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        payload = {
            "workflow": "workflow_05c_vault_tree",
            "vault_path": "/tmp/vault",
            "generated_at": "2026-02-24T18:35:12+00:00",
            "file_count": 1,
            "tree": {"name": ".", "type": "directory", "children": []},
            "files": [{"path": "notes/a.md", "title": "a", "group": "reference", "modified_at": "2026-02-24T18:30:00+00:00"}],
        }
        with patch("scripts.phase1.ingest_bridge_api.list_vault_tree", return_value=payload):
            with build_client(env) as client:
                response = client.get("/v1/vault-files")
                alias = client.get("/v1/vault/tree")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(alias.status_code, 404)
        self.assertEqual(alias.json()["error"]["code"], "not_found")
        self.assertEqual(response.json()["workflow"], "workflow_05c_vault_tree")

    def test_vault_sync_endpoint_accepts_body_and_runs_sync(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        sync_payload = {
            "workflow": "workflow_05c_vault_sync",
            "mode": "once",
            "dry_run": True,
            "vault_path": "/tmp/vault",
            "state_db_path": "/tmp/state.db",
            "scanned_files": 1,
            "changed_files": 1,
            "skipped_unchanged_files": 0,
            "removed_files": 0,
            "ingested_files": 1,
            "errors": [],
            "ingested": [],
            "synced_at": "2026-02-24T18:36:01+00:00",
        }
        with patch("scripts.phase1.ingest_bridge_api.run_vault_sync_once", return_value=sync_payload) as mock_sync:
            with build_client(env) as client:
                response = client.post("/v1/vault-syncs", json={"dry_run": True, "max_files": 5, "vault_path": "/tmp/vault"})
                alias = client.post("/v1/vault/sync", json={"dry_run": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(alias.status_code, 404)
        self.assertEqual(alias.json()["error"]["code"], "not_found")
        self.assertEqual(response.json()["workflow"], "workflow_05c_vault_sync")
        self.assertEqual(mock_sync.call_args_list[0].kwargs["max_files"], 5)
        self.assertEqual(mock_sync.call_args_list[0].kwargs["vault_path"], "/tmp/vault")
        self.assertTrue(mock_sync.call_args_list[0].kwargs["dry_run"])

    def test_activities_endpoint_is_canonical_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "recall.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE ingestion_log (
                    ingest_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_ref TEXT,
                    channel TEXT NOT NULL,
                    doc_id TEXT,
                    chunks_created INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    timestamp TEXT NOT NULL,
                    group_name TEXT,
                    tags_json TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO ingestion_log
                    (ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp, group_name, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ingest-1",
                    "url",
                    "https://example.com/job",
                    "bookmarklet",
                    "doc-1",
                    3,
                    "completed",
                    "2026-02-24T18:40:00+00:00",
                    "job-search",
                    json.dumps(["anthropic", "se-role"]),
                ),
            )
            conn.execute(
                """
                INSERT INTO ingestion_log
                    (ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp, group_name, tags_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ingest-2",
                    "url",
                    "https://example.com/learn",
                    "webhook",
                    "doc-2",
                    2,
                    "completed",
                    "2026-02-24T17:40:00+00:00",
                    "learning",
                    json.dumps(["rag"]),
                ),
            )
            conn.commit()
            conn.close()

            env = {
                "RECALL_API_KEY": "",
                "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
                "RECALL_DB_PATH": db_path,
            }
            with build_client(env) as client:
                canonical = client.get("/v1/activities?group=job-search")
                alias = client.get("/activity?group=job-search")

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(alias.status_code, 404)
        self.assertEqual(alias.json()["error"]["code"], "not_found")
        self.assertEqual(canonical.json()["workflow"], "workflow_05d_activity")
        self.assertEqual(canonical.json()["count"], 1)
        self.assertEqual(canonical.json()["items"][0]["group"], "job-search")

    def test_evaluations_collection_endpoint_supports_latest_query_param(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "recall.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE eval_results (
                    eval_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    expected_doc_id TEXT,
                    actual_doc_id TEXT,
                    citation_valid BOOLEAN,
                    latency_ms INTEGER,
                    passed BOOLEAN,
                    run_date TEXT NOT NULL
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO eval_results
                    (eval_id, question, expected_doc_id, actual_doc_id, citation_valid, latency_ms, passed, run_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("eval-1", "q1", None, None, 1, 1000, 1, "2026-02-24T09:15:00+00:00"),
                    ("eval-2", "q2", None, None, 1, 1100, 0, "2026-02-24T09:15:00+00:00"),
                    ("eval-3", "q3", None, None, 1, 900, 1, "2026-02-24T08:15:00+00:00"),
                ],
            )
            conn.commit()
            conn.close()

            env = {
                "RECALL_API_KEY": "",
                "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
                "RECALL_DB_PATH": db_path,
            }
            with build_client(env) as client:
                canonical = client.get("/v1/evaluations?latest=true")
                alias = client.get("/eval/latest")

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(alias.status_code, 404)
        self.assertEqual(alias.json()["error"]["code"], "not_found")
        self.assertEqual(canonical.json()["workflow"], "workflow_05d_eval_latest")
        self.assertEqual(canonical.json()["latest"]["run_date"], "2026-02-24T09:15:00+00:00")
        self.assertEqual(canonical.json()["latest"]["total"], 2)
        self.assertEqual(canonical.json()["latest"]["passed"], 1)
        self.assertEqual(canonical.json()["latest"]["failed"], 1)

    def test_eval_run_endpoint_supports_wait_mode_and_alias_removed(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        fake_summary = {"suite": "core", "status": "pass", "total": 3, "passed": 3, "failed": 0, "runs": []}
        with patch("scripts.phase1.ingest_bridge_api._run_eval_suite", return_value=fake_summary):
            with build_client(env) as client:
                canonical = client.post("/v1/evaluation-runs", json={"suite": "core", "wait": True})
                alias = client.post("/eval/run", json={"suite": "core", "wait": True})

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(alias.status_code, 404)
        self.assertEqual(alias.json()["error"]["code"], "not_found")
        self.assertEqual(canonical.json()["workflow"], "workflow_05d_eval_run")
        self.assertTrue(canonical.json()["accepted"])
        self.assertEqual(canonical.json()["run"]["status"], "completed")
        self.assertEqual(canonical.json()["run"]["result"]["status"], "pass")

    def test_health_endpoint_is_canonical_only(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            canonical = client.get("/v1/healthz")
            legacy_healthz = client.get("/healthz")
            legacy_health = client.get("/health")

        self.assertEqual(canonical.status_code, 200)
        self.assertEqual(canonical.json(), {"status": "ok"})
        self.assertEqual(legacy_healthz.status_code, 404)
        self.assertEqual(legacy_healthz.json()["error"]["code"], "not_found")
        self.assertEqual(legacy_health.status_code, 404)
        self.assertEqual(legacy_health.json()["error"]["code"], "not_found")

    def test_ingestion_requires_channel_on_canonical_endpoint(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            response = client.post("/v1/ingestions?dry_run=true", json={"type": "url", "content": "https://example.com"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_failed")
        self.assertEqual(response.json()["error"]["details"][0]["field"], "channel")

    def test_openapi_schema_lists_canonical_paths_only(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schema = response.json()
        paths = set(schema.get("paths", {}).keys())
        required_paths = {
            "/v1/healthz",
            "/v1/auto-tag-rules",
            "/v1/ingestions",
            "/v1/ingestions/files",
            "/v1/rag-queries",
            "/v1/meeting-action-items",
            "/v1/activities",
            "/v1/evaluations",
            "/v1/evaluation-runs",
            "/v1/vault-files",
            "/v1/vault-syncs",
        }
        forbidden_paths = {
            "/config/auto-tags",
            "/healthz",
            "/health",
            "/ingest/{channel}",
            "/ingest/file",
            "/ingestions",
            "/query/rag",
            "/rag/query",
            "/rag-queries",
            "/meeting/action-items",
            "/meeting/actions",
            "/query/meeting",
            "/meeting-action-items",
            "/activity",
            "/eval/latest",
            "/eval/run",
            "/v1/evaluations/latest",
            "/v1/vault/tree",
            "/vault/tree",
            "/v1/vault/sync",
            "/vault/sync",
        }
        for path in required_paths:
            self.assertIn(path, paths)
        for path in forbidden_paths:
            self.assertNotIn(path, paths)

    def test_legacy_ingestion_query_and_meeting_aliases_return_not_found(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            responses = [
                client.post("/ingest/bookmarklet", json={"url": "https://example.com"}),
                client.post("/ingestions", json={"channel": "bookmarklet", "url": "https://example.com"}),
                client.post("/query/rag", json={"query": "test"}),
                client.post("/rag/query", json={"query": "test"}),
                client.post("/rag-queries", json={"query": "test"}),
                client.post("/meeting/action-items", json={"meeting_title": "t", "transcript": "x"}),
                client.post("/meeting/actions", json={"meeting_title": "t", "transcript": "x"}),
                client.post("/query/meeting", json={"meeting_title": "t", "transcript": "x"}),
            ]

        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error"]["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
