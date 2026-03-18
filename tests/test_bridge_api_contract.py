#!/usr/bin/env python3
"""Endpoint contract tests for the FastAPI ingestion bridge."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts.phase1 import ingest_bridge_api
from scripts.phase1.ingestion_pipeline import IngestResult


@contextmanager
def build_client(env_updates: dict[str, str]) -> Iterator[TestClient]:
    merged_env = {
        "RECALL_PRELOAD_OLLAMA_MODELS": "false",
        "RECALL_DASHBOARD_CACHE_WARMER": "false",
    }
    merged_env.update(env_updates)
    with patch.dict(os.environ, merged_env, clear=False):
        app = ingest_bridge_api.create_app()
        with TestClient(app) as client:
            yield client


class BridgeApiContractTests(unittest.TestCase):
    def test_dashboard_checks_uses_warmed_gap_section_when_available(self) -> None:
        warmer = SimpleNamespace(
            warmed_gap_section=lambda: {"status": "ok", "count": 7, "detail": "7 aggregated gaps across 4 evaluated jobs"},
            snapshot=lambda: {
                "enabled": True,
                "interval_seconds": 300,
                "last_started_at": "2026-03-17T19:00:00+00:00",
                "last_completed_at": "2026-03-17T19:00:10+00:00",
                "last_error": None,
            },
        )

        with patch(
            "scripts.phase1.ingest_bridge_api.phase6_list_jobs",
            return_value={"total": 12, "items": [{"jobId": "job-1"}]},
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_job_stats",
            return_value={"total_jobs": 12, "high_fit_count": 3},
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_all_jobs",
            return_value=[{"jobId": "job-1", "company": "OpenAI", "status": "evaluated", "fit_score": 90}],
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_list_company_profiles",
            return_value=[{"company_id": "openai", "company_name": "OpenAI"}],
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_aggregate_gaps",
        ) as aggregate_mock:
            payload = ingest_bridge_api._dashboard_checks_payload(include_gaps=True, cache_warmer=warmer)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["gaps"]["count"], 7)
        self.assertEqual(payload["gaps"]["status"], "ok")
        aggregate_mock.assert_not_called()

    def test_dashboard_checks_returns_fast_degraded_gap_placeholder_while_warming(self) -> None:
        warmer = SimpleNamespace(
            warmed_gap_section=lambda: None,
            snapshot=lambda: {
                "enabled": True,
                "interval_seconds": 300,
                "last_started_at": "2026-03-17T19:00:00+00:00",
                "last_completed_at": None,
                "last_error": None,
            },
        )

        with patch(
            "scripts.phase1.ingest_bridge_api.phase6_list_jobs",
            return_value={"total": 12, "items": [{"jobId": "job-1"}]},
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_job_stats",
            return_value={"total_jobs": 12, "high_fit_count": 3},
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_all_jobs",
            return_value=[{"jobId": "job-1", "company": "OpenAI", "status": "evaluated", "fit_score": 90}],
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_list_company_profiles",
            return_value=[{"company_id": "openai", "company_name": "OpenAI"}],
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_aggregate_gaps",
        ) as aggregate_mock:
            payload = ingest_bridge_api._dashboard_checks_payload(include_gaps=True, cache_warmer=warmer)

        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["gaps"]["status"], "degraded")
        self.assertIn("warming in the background", payload["gaps"]["detail"].lower())
        self.assertIn("warming in background", payload["notes"][0].lower())
        aggregate_mock.assert_not_called()

    def test_cors_defaults_to_no_cross_origin_access_when_unset(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
            "RECALL_API_CORS_ORIGINS": "",
        }
        with build_client(env) as client:
            response = client.options(
                "/v1/healthz",
                headers={
                    "Origin": "http://localhost:3001",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_cors_allows_configured_origin_only(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
            "RECALL_API_CORS_ORIGINS": "http://localhost:3001,http://localhost:8170",
        }
        with build_client(env) as client:
            allowed = client.options(
                "/v1/healthz",
                headers={
                    "Origin": "http://localhost:3001",
                    "Access-Control-Request-Method": "GET",
                },
            )
            blocked = client.options(
                "/v1/healthz",
                headers={
                    "Origin": "http://evil.example",
                    "Access-Control-Request-Method": "GET",
                },
            )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:3001")
        self.assertEqual(blocked.status_code, 400)
        self.assertNotIn("access-control-allow-origin", blocked.headers)

    def test_healthz_sets_request_id_header_and_echoes_incoming_id(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            generated = client.get("/v1/healthz")
            explicit = client.get("/v1/healthz", headers={"X-Request-Id": "demo-request-123"})

        self.assertEqual(generated.status_code, 200)
        self.assertTrue(generated.headers.get("X-Request-Id", "").startswith("req_"))
        self.assertEqual(explicit.status_code, 200)
        self.assertEqual(explicit.headers.get("X-Request-Id"), "demo-request-123")

    def test_startup_preloads_required_ollama_models(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
            "RECALL_PRELOAD_OLLAMA_MODELS": "true",
            "RECALL_LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "qwen2.5:7b-instruct",
            "OLLAMA_EMBED_MODEL": "nomic-embed-text",
        }
        with patch("scripts.phase1.ingest_bridge_api._ensure_required_ollama_models") as preload_mock:
            with build_client(env):
                pass

        preload_mock.assert_called_once_with()

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

    def test_patch_job_accepts_workflow_state_payload(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        updated_job = {
            "jobId": "job-123",
            "title": "Solutions Engineer",
            "company": "OpenAI",
            "status": "evaluated",
            "fit_score": 88,
            "workflow": {
                "stage": "follow_up",
                "nextActionApproval": "approved",
                "packetApproval": "pending",
                "packet": {
                    "tailoredSummary": True,
                    "resumeBullets": False,
                    "coverLetterDraft": False,
                    "outreachNote": False,
                    "interviewBrief": False,
                    "talkingPoints": False,
                },
                "followUp": {
                    "status": "scheduled",
                    "dueAt": "2026-03-24T16:00:00Z",
                    "lastCompletedAt": None,
                },
                "updatedAt": "2026-03-17T21:05:00Z",
            },
            "workflowTimeline": [
                {
                    "type": "next_action_approved",
                    "label": "Next action approved",
                    "detail": None,
                    "at": "2026-03-17T21:05:00Z",
                }
            ],
        }

        with patch("scripts.phase1.bridge_routes_phase6.phase6_update_job", return_value=updated_job) as update_mock:
            with build_client(env) as client:
                response = client.patch(
                    "/v1/jobs/job-123",
                    json={
                        "workflow": {
                            "stage": "follow_up",
                            "nextActionApproval": "approved",
                            "packet": {
                                "tailoredSummary": True,
                            },
                            "followUp": {
                                "status": "scheduled",
                                "dueAt": "2026-03-24T16:00:00Z",
                            },
                        }
                    },
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"]["nextActionApproval"], "approved")
        self.assertEqual(response.json()["workflow"]["packet"]["tailoredSummary"], True)
        self.assertEqual(response.json()["workflow"]["followUp"]["status"], "scheduled")
        update_mock.assert_called_once_with(
            job_id="job-123",
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "stage": "follow_up",
                "nextActionApproval": "approved",
                "packet": {
                    "tailoredSummary": True,
                },
                "followUp": {
                    "status": "scheduled",
                    "dueAt": "2026-03-24T16:00:00Z",
                },
            },
        )

    def test_patch_job_rejects_invalid_follow_up_payload(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            response = client.patch(
                "/v1/jobs/job-123",
                json={
                    "workflow": {
                        "followUp": {
                            "status": "tomorrow",
                        }
                    },
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_failed")
        self.assertEqual(response.json()["error"]["details"][0]["field"], "workflow.followUp.status")

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

    def test_dashboard_checks_endpoint_returns_summary(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_list_jobs", return_value={"total": 12, "items": [{"jobId": "job-1"}]}), patch(
            "scripts.phase1.ingest_bridge_api.phase6_job_stats",
            return_value={"total_jobs": 12, "high_fit_count": 3},
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_all_jobs",
            return_value=[{"jobId": "job-1", "company": "OpenAI", "status": "evaluated", "fit_score": 90}],
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_list_company_profiles",
            return_value=[{"company_id": "openai", "company_name": "OpenAI"}],
        ), patch(
            "scripts.phase1.ingest_bridge_api.phase6_aggregate_gaps",
            return_value={"aggregated_gaps": [{"gap": "Kubernetes"}], "total_jobs_analyzed": 4},
        ):
            with build_client(env) as client:
                response = client.get("/v1/dashboard-checks")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["workflow"], "workflow_06a_dashboard_checks")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["jobs"]["count"], 12)
        self.assertEqual(payload["companies"]["count"], 1)
        self.assertEqual(payload["gaps"]["count"], 1)

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
            "/v1/jobs",
            "/v1/jobs/{jobId}",
            "/v1/job-evaluation-runs",
            "/v1/job-stats",
            "/v1/job-gaps",
            "/v1/job-deduplications",
            "/v1/job-discovery-runs",
            "/v1/resumes",
            "/v1/resumes/current",
            "/v1/companies",
            "/v1/companies/{companyId}",
            "/v1/company-profile-refresh-runs",
            "/v1/llm-settings",
            "/v1/cover-letter-drafts",
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

    def test_phase6_jobs_and_stats_endpoints_return_canonical_payloads(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        jobs_payload = {
            "total": 1,
            "limit": 50,
            "offset": 0,
            "items": [{"jobId": "job-1", "title": "Solutions Engineer", "status": "evaluated", "fit_score": 80}],
        }
        stats_payload = {
            "total_jobs": 1,
            "score_ranges": {"high": 1, "medium": 0, "low": 0, "unscored": 0},
            "by_source": {"jobspy": 1},
            "by_day": {"2026-03-04": 1},
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_list_jobs", return_value=jobs_payload):
            with patch("scripts.phase1.ingest_bridge_api.phase6_job_stats", return_value=stats_payload):
                with build_client(env) as client:
                    jobs_response = client.get("/v1/jobs")
                    stats_response = client.get("/v1/job-stats")
                    alias_response = client.get("/jobs")

        self.assertEqual(jobs_response.status_code, 200)
        self.assertEqual(jobs_response.json()["workflow"], "workflow_06a_jobs")
        self.assertEqual(jobs_response.json()["items"][0]["jobId"], "job-1")
        self.assertEqual(stats_response.status_code, 200)
        self.assertEqual(stats_response.json()["workflow"], "workflow_06a_job_stats")
        self.assertEqual(alias_response.status_code, 404)
        self.assertEqual(alias_response.json()["error"]["code"], "not_found")

    def test_phase6_jobs_endpoint_accepts_min_score_negative_one_for_unscored(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_list_jobs", return_value={"total": 0, "limit": 50, "offset": 0, "items": []}) as mocked:
            with build_client(env) as client:
                response = client.get("/v1/jobs?status=new&min_score=-1&limit=5")
                invalid = client.get("/v1/jobs?status=new&min_score=-2&limit=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_jobs")
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(mocked.call_args.kwargs["status"], "new")
        self.assertEqual(mocked.call_args.kwargs["min_score"], -1)

    def test_phase6_jobs_endpoint_accepts_status_all(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_list_jobs", return_value={"total": 0, "limit": 50, "offset": 0, "items": []}) as mocked:
            with build_client(env) as client:
                response = client.get("/v1/jobs?status=all&limit=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_jobs")
        self.assertIsNone(mocked.call_args.kwargs["status"])

    def test_phase6_jobs_endpoint_passes_multi_field_search_query(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_list_jobs", return_value={"total": 0, "limit": 50, "offset": 0, "items": []}) as mocked:
            with build_client(env) as client:
                response = client.get("/v1/jobs?search=openai%20remote%20demos&limit=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_jobs")
        self.assertEqual(mocked.call_args.kwargs["search"], "openai remote demos")

    def test_phase6_jobs_endpoint_accepts_summary_view(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_list_jobs", return_value={"total": 0, "limit": 50, "offset": 0, "items": []}) as mocked:
            with build_client(env) as client:
                response = client.get("/v1/jobs?view=summary&limit=5")
                invalid = client.get("/v1/jobs?view=compactest&limit=5")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_jobs")
        self.assertFalse(mocked.call_args.kwargs["include_details"])
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_failed")

    def test_phase6_llm_settings_patch_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "recall.db")
            env = {
                "RECALL_API_KEY": "",
                "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
                "RECALL_DB_PATH": db_path,
            }
            with build_client(env) as client:
                initial = client.get("/v1/llm-settings")
                patched = client.patch(
                    "/v1/llm-settings",
                    json={"evaluation_model": "cloud", "cloud_provider": "openai", "auto_escalate": False},
                )
                after = client.get("/v1/llm-settings")

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json()["settings"]["evaluation_model"], "local")
        self.assertEqual(initial.json()["settings"]["local_model"], "llama3.2:3b")
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["settings"]["evaluation_model"], "cloud")
        self.assertEqual(patched.json()["settings"]["cloud_provider"], "openai")
        self.assertFalse(patched.json()["settings"]["auto_escalate"])
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json()["settings"]["evaluation_model"], "cloud")

    def test_phase6_llm_settings_patch_accepts_local_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "recall.db")
            env = {
                "RECALL_API_KEY": "",
                "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
                "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
                "RECALL_DB_PATH": db_path,
            }
            with build_client(env) as client:
                patched = client.patch(
                    "/v1/llm-settings",
                    json={"evaluation_model": "local", "local_model": "llama3.2:3b"},
                )
                after = client.get("/v1/llm-settings")

        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["settings"]["evaluation_model"], "local")
        self.assertEqual(patched.json()["settings"]["local_model"], "llama3.2:3b")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.json()["settings"]["local_model"], "llama3.2:3b")

    def test_phase6_companies_create_endpoint_returns_created_profile(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        saved = {
            "company_id": "airbnb",
            "company_name": "Airbnb",
            "tier": 1,
            "metadata": {"ats": "greenhouse", "board_id": "airbnb"},
        }
        profile = {
            "company_id": "airbnb",
            "company_name": "Airbnb",
            "tier": 1,
            "ats": "greenhouse",
            "board_id": "airbnb",
            "jobs_summary": {"highest_fit_score": 92},
        }
        with (
            patch("scripts.phase1.ingest_bridge_api.phase6_upsert_tracked_company_config", return_value=saved) as mock_save,
            patch("scripts.phase1.ingest_bridge_api.phase6_update_company_tier", return_value=6) as mock_tier,
            patch("scripts.phase1.ingest_bridge_api.phase6_get_company_profile", return_value=profile),
            patch("scripts.phase1.ingest_bridge_api.phase6_all_jobs", return_value=[]),
        ):
            with build_client(env) as client:
                response = client.post(
                    "/v1/companies",
                    json={
                        "company_name": "Airbnb",
                        "tier": 1,
                        "ats": "greenhouse",
                        "board_id": "airbnb",
                        "url": "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs",
                        "title_filter": ["solutions", "platform"],
                    },
                )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["workflow"], "workflow_06a_company_watchlist")
        self.assertEqual(body["company_id"], "airbnb")
        self.assertEqual(body["jobs_updated"], 6)
        self.assertEqual(mock_save.call_args.kwargs["patch"]["company_name"], "Airbnb")
        self.assertEqual(mock_tier.call_args.kwargs["tier"], 1)

    def test_phase6_companies_patch_endpoint_updates_tier(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        current = {"company_id": "airbnb", "company_name": "Airbnb", "tier": 1}
        saved = {
            "company_id": "airbnb",
            "company_name": "Airbnb",
            "tier": 2,
            "metadata": {"ats": "greenhouse", "board_id": "airbnb"},
        }
        updated = {
            "company_id": "airbnb",
            "company_name": "Airbnb",
            "tier": 2,
            "ats": "greenhouse",
            "board_id": "airbnb",
        }
        with (
            patch("scripts.phase1.ingest_bridge_api.phase6_get_company_profile", side_effect=[current, updated]),
            patch("scripts.phase1.ingest_bridge_api.phase6_upsert_tracked_company_config", return_value=saved) as mock_save,
            patch("scripts.phase1.ingest_bridge_api.phase6_update_company_tier", return_value=88) as mock_tier,
            patch("scripts.phase1.ingest_bridge_api.phase6_all_jobs", return_value=[]),
        ):
            with build_client(env) as client:
                response = client.patch(
                    "/v1/companies/airbnb",
                    json={"tier": 2, "your_connection": "Recruiter screen complete."},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["company_id"], "airbnb")
        self.assertEqual(body["tier"], 2)
        self.assertEqual(body["jobs_updated"], 88)
        self.assertEqual(mock_save.call_args.kwargs["company_id"], "airbnb")
        self.assertEqual(mock_save.call_args.kwargs["patch"]["tier"], 2)
        self.assertEqual(mock_tier.call_args.kwargs["company_id"], "airbnb")

    def test_phase6_companies_endpoint_accepts_limit_and_include_jobs_false(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with (
            patch("scripts.phase1.ingest_bridge_api.phase6_all_jobs", return_value=[]),
            patch("scripts.phase1.ingest_bridge_api.phase6_list_company_profiles", return_value=[{"company_id": "airbnb"}]) as mocked,
        ):
            with build_client(env) as client:
                response = client.get("/v1/companies?limit=25&include_jobs=false")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_companies")
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(mocked.call_args.kwargs["limit"], 25)
        self.assertFalse(mocked.call_args.kwargs["include_jobs"])

    def test_phase6_cover_letter_draft_endpoint_returns_generated_draft(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        fake_result = {
            "draft_id": "cover_letter_job-1",
            "job_id": "job-1",
            "provider": "ollama",
            "model": "llama3.2:3b",
            "generated_at": "2026-03-06T16:00:00+00:00",
            "word_count": 120,
            "draft": "Dear Hiring Team,\\n\\nI would love to help...",
            "saved_to_vault": False,
            "vault_path": None,
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_generate_cover_letter_draft", return_value=fake_result) as mocked, patch(
            "scripts.phase1.ingest_bridge_api.phase6_update_job",
            return_value={"jobId": "job-1"},
        ) as update_mock:
            with build_client(env) as client:
                response = client.post(
                    "/v1/cover-letter-drafts",
                    json={"job_id": "job-1", "save_to_vault": False, "settings": {"evaluation_model": "local"}},
                )
                invalid = client.post("/v1/cover-letter-drafts", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_cover_letter_draft")
        self.assertEqual(response.json()["job_id"], "job-1")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(mocked.call_args.kwargs["job_id"], "job-1")
        self.assertFalse(mocked.call_args.kwargs["save_to_vault"])
        update_mock.assert_called_once_with(
            job_id="job-1",
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"coverLetterDraft": True},
                "artifacts": {
                    "coverLetterDraft": {
                        "draftId": "cover_letter_job-1",
                        "generatedAt": "2026-03-06T16:00:00+00:00",
                        "provider": "ollama",
                        "model": "llama3.2:3b",
                        "wordCount": 120,
                        "savedToVault": False,
                        "vaultPath": None,
                    }
                },
            },
        )

    def test_phase6_resume_endpoint_accepts_markdown_payload(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        fake_resume = {
            "version": 1,
            "chunks": 5,
            "ingested_at": "2026-03-04T12:00:00+00:00",
            "source": "inline:resume-markdown",
            "dry_run": True,
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_ingest_resume", return_value=fake_resume):
            with build_client(env) as client:
                response = client.post("/v1/resumes?dry_run=true", json={"markdown": "# Resume\\nExperience"})
                invalid = client.post("/v1/resumes?dry_run=true", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"], "workflow_06a_resume_ingestion")
        self.assertEqual(response.json()["version"], 1)
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_failed")

    def test_phase6_job_dedup_endpoint_accepts_url_or_description_payload(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }

        class _FakeDedup:
            def to_dict(self) -> dict[str, object]:
                return {
                    "duplicate": True,
                    "is_duplicate": True,
                    "reason": "exact_url",
                    "matched_job_id": "job_123",
                    "similar_job_id": "job_123",
                    "similarity_score": 1.0,
                }

        with patch("scripts.phase1.ingest_bridge_api.phase6_check_job_duplicate", return_value=_FakeDedup()) as mock_dedup:
            with build_client(env) as client:
                response = client.post(
                    "/v1/job-deduplications",
                    json={
                        "url": "https://jobs.example.com/123",
                        "description": "Senior solutions engineer role focused on enterprise APIs.",
                        "similarity_threshold": 0.9,
                    },
                )
                invalid = client.post("/v1/job-deduplications", json={"similarity_threshold": 0.4})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["workflow"], "workflow_06a_job_dedup")
        self.assertTrue(body["is_duplicate"])
        self.assertEqual(body["reason"], "exact_url")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["error"]["code"], "validation_failed")
        called_candidate = mock_dedup.call_args.args[0]
        self.assertEqual(called_candidate["url"], "https://jobs.example.com/123")
        self.assertEqual(mock_dedup.call_args.kwargs["similarity_threshold"], 0.9)

    def test_phase6_job_discovery_endpoint_returns_new_job_ids(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        fake_summary = {
            "run_id": "job_discovery_abc123",
            "status": "completed",
            "triggered_at": "2026-03-04T18:00:00+00:00",
            "sources": ["jobspy"],
            "new_jobs": 2,
            "new_job_ids": ["job_1", "job_2"],
            "duplicates_skipped": 1,
            "message": "Discovered 2 new jobs.",
        }
        fake_collections = [SimpleNamespace(name="recall_jobs", created=False), SimpleNamespace(name="recall_resume", created=False)]
        with patch("scripts.phase1.ingest_bridge_api.phase6_ensure_collections", return_value=fake_collections):
            with patch("scripts.phase1.ingest_bridge_api.phase6_run_discovery", return_value=fake_summary):
                with build_client(env) as client:
                    response = client.post(
                        "/v1/job-discovery-runs",
                        json={"sources": ["jobspy"], "max_queries": 2, "dry_run": True},
                    )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["workflow"], "workflow_06a_job_discovery")
        self.assertEqual(body["new_job_ids"], ["job_1", "job_2"])
        self.assertEqual(body["collections"][0]["name"], "recall_jobs")

    def test_phase6_job_evaluation_endpoint_returns_accepted_for_async_runs(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        queued_response = {
            "run_id": "job_eval_123",
            "queued": 1,
            "job_ids": ["job_1"],
            "status": "queued",
            "wait": False,
            "results": [],
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_queue_job_evaluations", return_value=queued_response) as mock_queue:
            with build_client(env) as client:
                response = client.post(
                    "/v1/job-evaluation-runs",
                    json={"job_ids": ["job_1"], "wait": False},
                )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["workflow"], "workflow_06a_job_evaluations")
        self.assertEqual(body["status"], "queued")
        self.assertEqual(mock_queue.call_args.kwargs["wait"], False)

    def test_phase6_job_evaluation_endpoint_returns_completed_for_sync_runs(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        completed_response = {
            "run_id": "job_eval_456",
            "queued": 1,
            "job_ids": ["job_1"],
            "status": "completed",
            "wait": True,
            "evaluated": 1,
            "failed": 0,
            "results": [{"job_id": "job_1", "status": "completed", "fit_score": 82}],
        }
        with patch("scripts.phase1.ingest_bridge_api.phase6_queue_job_evaluations", return_value=completed_response) as mock_queue:
            with build_client(env) as client:
                response = client.post(
                    "/v1/job-evaluation-runs",
                    json={"job_ids": ["job_1"], "wait": True},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["workflow"], "workflow_06a_job_evaluations")
        self.assertEqual(body["evaluated"], 1)
        self.assertEqual(mock_queue.call_args.kwargs["wait"], True)

    def test_ingestion_routes_job_search_job_urls_into_phase6_pipeline(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        fake_ingest = IngestResult(
            run_id="run-1",
            ingest_id="ingest-1",
            doc_id="doc-1",
            source_type="url",
            source_ref="https://linkedin.com/jobs/view/123",
            title="Job Posting",
            source_identity="job:123",
            chunks_created=2,
            moved_to=None,
            replace_existing=False,
            replaced_points=0,
            replacement_status="skipped",
            latency_ms=10,
            status="completed",
        )
        extracted = {
            "source": "linkedin",
            "title": "Senior Solutions Engineer",
            "company": "ExampleCo",
            "location": "Remote",
            "description": "Role responsibilities and requirements.",
            "salary_min": 150000,
            "salary_max": 180000,
        }
        discovery = {"run_id": "job_discovery_abc", "new_job_ids": ["job_a1b2"]}
        queued_eval = {"run_id": "job_eval_abc", "status": "queued", "job_ids": ["job_a1b2"], "queued": 1, "wait": False}

        with patch("scripts.phase1.ingest_bridge_api.ingest_request", return_value=fake_ingest):
            with patch("scripts.phase1.ingest_bridge_api.phase6_looks_like_job_url", return_value=True):
                with patch("scripts.phase1.ingest_bridge_api._load_ingested_doc_text", return_value="Sample job content"):
                    with patch("scripts.phase1.ingest_bridge_api.phase6_extract_job_metadata", return_value=extracted):
                        with patch("scripts.phase1.ingest_bridge_api.phase6_run_discovery", return_value=discovery) as mock_discovery:
                            with patch("scripts.phase1.ingest_bridge_api.phase6_queue_job_evaluations", return_value=queued_eval) as mock_queue:
                                with build_client(env) as client:
                                    response = client.post(
                                        "/v1/ingestions",
                                        json={
                                            "channel": "bookmarklet",
                                            "type": "url",
                                            "content": "https://linkedin.com/jobs/view/123",
                                            "group": "job-search",
                                        },
                                    )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["job_pipeline"][0]["routed"])
        self.assertEqual(body["job_pipeline"][0]["new_job_ids"], ["job_a1b2"])
        manual_jobs = mock_discovery.call_args.args[0]["jobs"]
        self.assertEqual(manual_jobs[0]["source"], "chrome_extension")
        self.assertEqual(manual_jobs[0]["company"], "ExampleCo")
        self.assertEqual(mock_queue.call_args.kwargs["job_ids"], ["job_a1b2"])

    def test_phase6_company_and_job_aliases_return_not_found(self) -> None:
        env = {
            "RECALL_API_KEY": "",
            "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
            "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
        }
        with build_client(env) as client:
            responses = [
                client.get("/companies"),
                client.post("/company-profile-refresh-runs", json={"company_id": "anthropic"}),
                client.get("/job-stats"),
                client.get("/job-gaps"),
                client.post("/job-evaluation-runs", json={"job_ids": ["job-1"]}),
            ]

        for response in responses:
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["error"]["code"], "not_found")

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
