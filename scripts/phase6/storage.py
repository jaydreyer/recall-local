#!/usr/bin/env python3
"""SQLite storage helpers for Phase 6 foundation state."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LLM_SETTINGS: dict[str, Any] = {
    "evaluation_model": "local",
    "cloud_provider": "anthropic",
    "cloud_model": "claude-sonnet-4-5-20250929",
    "auto_escalate": True,
    "escalate_threshold_gaps": 2,
    "escalate_threshold_rationale_words": 20,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db_path_from_env() -> Path:
    raw = os.getenv("RECALL_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "recall.db"


def connect_db(db_path: Path | None = None) -> sqlite3.Connection:
    resolved = (db_path or db_path_from_env()).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(resolved)
    conn.row_factory = sqlite3.Row
    ensure_phase6_tables(conn)
    return conn


def ensure_phase6_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            setting_key TEXT PRIMARY KEY,
            setting_value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS resume_versions (
            version INTEGER PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_path TEXT,
            ingested_at TEXT NOT NULL,
            chunk_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS company_profiles (
            company_id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            tier INTEGER,
            description TEXT,
            your_connection TEXT,
            metadata_json TEXT,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def get_llm_settings(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        "SELECT setting_value_json FROM settings WHERE setting_key = ?",
        ("llm_settings",),
    ).fetchone()
    if row is None:
        return dict(DEFAULT_LLM_SETTINGS)
    try:
        parsed = json.loads(row["setting_value_json"])
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    merged = dict(DEFAULT_LLM_SETTINGS)
    merged.update(parsed)
    return merged


def update_llm_settings(conn: sqlite3.Connection, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_llm_settings(conn)
    for key, value in patch.items():
        if key in DEFAULT_LLM_SETTINGS and value is not None:
            current[key] = value

    conn.execute(
        """
        INSERT INTO settings (setting_key, setting_value_json, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(setting_key)
        DO UPDATE SET setting_value_json = excluded.setting_value_json, updated_at = excluded.updated_at
        """,
        ("llm_settings", json.dumps(current, separators=(",", ":")), now_iso()),
    )
    conn.commit()
    return current


def next_resume_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(version), 0) AS max_version FROM resume_versions").fetchone()
    return int(row["max_version"] or 0) + 1


def record_resume_version(
    conn: sqlite3.Connection,
    *,
    version: int,
    source_type: str,
    source_path: str | None,
    chunk_count: int,
    ingested_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO resume_versions (version, source_type, source_path, ingested_at, chunk_count)
        VALUES (?, ?, ?, ?, ?)
        """,
        (version, source_type, source_path, ingested_at, chunk_count),
    )

    has_ingestion_log = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingestion_log'"
    ).fetchone()
    if has_ingestion_log:
        conn.execute(
            """
            INSERT INTO ingestion_log (
                ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp, group_name, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"resume-{version}-{ingested_at}",
                "resume",
                source_path,
                "resume-upload",
                f"resume:v{version}",
                chunk_count,
                "completed",
                ingested_at,
                "job-search",
                json.dumps(["resume"]),
            ),
        )

    conn.commit()


def latest_resume_metadata(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT version, ingested_at, chunk_count, source_type, source_path
        FROM resume_versions
        ORDER BY version DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return None
    return {
        "version": int(row["version"]),
        "ingested_at": row["ingested_at"],
        "chunks": int(row["chunk_count"]),
        "source_type": row["source_type"],
        "source_path": row["source_path"],
    }


def list_company_profile_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT company_id, company_name, tier, description, your_connection, metadata_json, updated_at
        FROM company_profiles
        ORDER BY company_name ASC
        """
    ).fetchall()
    profiles: list[dict[str, Any]] = []
    for row in rows:
        metadata: dict[str, Any] = {}
        raw_metadata = row["metadata_json"]
        if raw_metadata:
            try:
                loaded = json.loads(raw_metadata)
                if isinstance(loaded, dict):
                    metadata = loaded
            except json.JSONDecodeError:
                metadata = {}
        profiles.append(
            {
                "company_id": row["company_id"],
                "company_name": row["company_name"],
                "tier": row["tier"],
                "description": row["description"],
                "your_connection": row["your_connection"],
                "metadata": metadata,
                "updated_at": row["updated_at"],
            }
        )
    return profiles


def upsert_company_profile(conn: sqlite3.Connection, profile: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO company_profiles (
            company_id, company_name, tier, description, your_connection, metadata_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_id)
        DO UPDATE SET
            company_name = excluded.company_name,
            tier = excluded.tier,
            description = excluded.description,
            your_connection = excluded.your_connection,
            metadata_json = excluded.metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            profile.get("company_id"),
            profile.get("company_name"),
            profile.get("tier"),
            profile.get("description"),
            profile.get("your_connection"),
            json.dumps(profile.get("metadata", {}), separators=(",", ":")),
            profile.get("updated_at") or now_iso(),
        ),
    )
    conn.commit()
