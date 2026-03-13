#!/usr/bin/env python3
"""Pytest coverage for Phase 6 storage helpers."""

from __future__ import annotations

import json

import pytest

from scripts.phase6 import storage


def test_get_llm_settings_returns_defaults_for_empty_db(sqlite_conn) -> None:
    settings = storage.get_llm_settings(sqlite_conn)

    assert settings == storage.DEFAULT_LLM_SETTINGS


@pytest.mark.parametrize(
    ("patch", "expected_key", "expected_value"),
    [
        ({"evaluation_model": "cloud"}, "evaluation_model", "cloud"),
        ({"auto_escalate": False}, "auto_escalate", False),
        ({"local_model": "qwen2.5:7b-instruct"}, "local_model", "qwen2.5:7b-instruct"),
    ],
)
def test_update_llm_settings_persists_known_keys(sqlite_conn, patch, expected_key: str, expected_value: object) -> None:
    updated = storage.update_llm_settings(sqlite_conn, patch)

    assert updated[expected_key] == expected_value
    assert storage.get_llm_settings(sqlite_conn)[expected_key] == expected_value


def test_update_llm_settings_ignores_unknown_keys(sqlite_conn) -> None:
    updated = storage.update_llm_settings(sqlite_conn, {"unknown_flag": 123, "evaluation_model": "cloud"})

    assert "unknown_flag" not in updated
    assert updated["evaluation_model"] == "cloud"


def test_get_llm_settings_recovers_from_invalid_json(sqlite_conn) -> None:
    sqlite_conn.execute(
        "INSERT INTO settings (setting_key, setting_value_json, updated_at) VALUES (?, ?, ?)",
        ("llm_settings", "{not-json", "2026-03-13T00:00:00+00:00"),
    )
    sqlite_conn.commit()

    assert storage.get_llm_settings(sqlite_conn) == storage.DEFAULT_LLM_SETTINGS


def test_record_resume_version_updates_resume_table_and_ingestion_log(sqlite_conn) -> None:
    sqlite_conn.execute(
        """
        CREATE TABLE ingestion_log (
            ingest_id TEXT,
            source_type TEXT,
            source_ref TEXT,
            channel TEXT,
            doc_id TEXT,
            chunks_created INTEGER,
            status TEXT,
            timestamp TEXT,
            group_name TEXT,
            tags_json TEXT
        )
        """
    )
    sqlite_conn.commit()

    storage.record_resume_version(
        sqlite_conn,
        version=2,
        source_type="markdown",
        source_path="/tmp/resume.md",
        chunk_count=4,
        ingested_at="2026-03-13T12:00:00+00:00",
    )

    latest = storage.latest_resume_metadata(sqlite_conn)
    log_row = sqlite_conn.execute(
        "SELECT source_type, source_ref, channel, doc_id, chunks_created, group_name, tags_json FROM ingestion_log"
    ).fetchone()

    assert latest == {
        "version": 2,
        "ingested_at": "2026-03-13T12:00:00+00:00",
        "chunks": 4,
        "source_type": "markdown",
        "source_path": "/tmp/resume.md",
    }
    assert log_row["source_type"] == "resume"
    assert log_row["channel"] == "resume-upload"
    assert log_row["doc_id"] == "resume:v2"
    assert log_row["chunks_created"] == 4
    assert log_row["group_name"] == "job-search"
    assert json.loads(log_row["tags_json"]) == ["resume"]
