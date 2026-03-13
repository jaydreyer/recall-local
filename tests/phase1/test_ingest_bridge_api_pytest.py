#!/usr/bin/env python3
"""Pytest coverage for focused Phase 1 bridge upload behaviors."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scripts.phase1 import ingest_bridge_api
from scripts.phase1.ingestion_pipeline import IngestResult


@contextmanager
def build_client(env_updates: dict[str, str]) -> Iterator[TestClient]:
    """Create a bridge test client with stable test-only environment defaults."""
    merged_env = {
        "RECALL_API_KEY": "",
        "RECALL_PRELOAD_OLLAMA_MODELS": "false",
        "RECALL_DASHBOARD_CACHE_WARMER": "false",
        "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
        "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
    }
    merged_env.update(env_updates)
    with patch.dict(os.environ, merged_env, clear=False):
        app = ingest_bridge_api.create_app()
        with TestClient(app) as client:
            yield client


def test_file_ingestion_rejects_unsupported_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return a typed 415 error before writing unsupported uploads to disk."""
    monkeypatch.setattr(ingest_bridge_api, "_incoming_dir_from_env", lambda: tmp_path)

    with build_client({}) as client:
        response = client.post(
            "/v1/ingestions/files?dry_run=true",
            files={"file": ("payload.exe", b"binary", "application/octet-stream")},
        )

    body = response.json()
    assert response.status_code == 415
    assert body["error"]["code"] == "unsupported_media_type"
    assert not list(tmp_path.iterdir())


def test_file_ingestion_enforces_upload_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject oversize uploads and remove any partially written temp file."""
    monkeypatch.setattr(ingest_bridge_api, "_incoming_dir_from_env", lambda: tmp_path)
    monkeypatch.setattr(ingest_bridge_api, "_max_upload_bytes", lambda: 4)
    monkeypatch.setattr(ingest_bridge_api, "_max_upload_mb", lambda: 1)

    with build_client({}) as client:
        response = client.post(
            "/v1/ingestions/files?dry_run=true",
            files={"file": ("payload.txt", b"12345", "text/plain")},
        )

    body = response.json()
    assert response.status_code == 413
    assert body["error"]["code"] == "payload_too_large"
    assert not list(tmp_path.iterdir())


def test_file_ingestion_normalizes_group_and_tags_before_calling_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass normalized request metadata to the ingestion pipeline for uploads."""
    captured_request = None

    def fake_ingest_request(request, *, dry_run):  # type: ignore[no-untyped-def]
        nonlocal captured_request
        captured_request = request
        return IngestResult(
            run_id="run-1",
            ingest_id="ingest-1",
            doc_id="doc-1",
            source_type="file",
            source_ref=str(tmp_path / "resume.md"),
            title="resume.md",
            source_identity=str(tmp_path / "resume.md"),
            chunks_created=1,
            moved_to=None,
            replace_existing=False,
            replaced_points=0,
            replacement_status="skipped",
            latency_ms=1,
            status="dry_run",
        )

    monkeypatch.setattr(ingest_bridge_api, "_incoming_dir_from_env", lambda: tmp_path)
    monkeypatch.setattr(ingest_bridge_api, "ingest_request", fake_ingest_request)

    with build_client({}) as client:
        response = client.post(
            "/v1/ingestions/files?dry_run=true",
            data={"group": "job_search", "tags": "alpha, beta , ,gamma", "save_to_vault": "true"},
            files={"file": ("resume.md", b"# Resume", "text/markdown")},
        )

    assert response.status_code == 200
    assert captured_request is not None
    assert captured_request.group == "job-search"
    assert captured_request.tags == ["alpha", "beta", "gamma"]
    assert captured_request.metadata["save_to_vault"] is True
    assert captured_request.metadata["uploaded_filename"] == "resume.md"
