#!/usr/bin/env python3
"""Initialize SQLite database tables for Recall.local."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv


DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    workflow TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'started',
    started_at TEXT NOT NULL,
    ended_at TEXT,
    model TEXT,
    latency_ms INTEGER,
    input_hash TEXT,
    output_path TEXT
);

CREATE TABLE IF NOT EXISTS eval_results (
    eval_id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    expected_doc_id TEXT,
    actual_doc_id TEXT,
    citation_valid BOOLEAN,
    latency_ms INTEGER,
    passed BOOLEAN,
    run_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    severity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    summary TEXT,
    run_id TEXT REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    ingest_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    channel TEXT NOT NULL,
    doc_id TEXT,
    chunks_created INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    timestamp TEXT NOT NULL
);
"""


def main() -> None:
    load_dotenv("docker/.env")
    load_dotenv("docker/.env.example")

    db_path = os.getenv("RECALL_DB_PATH", "data/recall.db")
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_file)
    try:
        conn.executescript(DDL)
        conn.commit()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    finally:
        conn.close()

    names = [row[0] for row in tables]
    print(f"SQLite initialized: {db_file.resolve()}")
    print("Tables:", ", ".join(names))


if __name__ == "__main__":
    main()
