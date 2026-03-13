#!/usr/bin/env python3
"""Pytest coverage for Phase 0 SQLite bootstrap."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.phase0 import bootstrap_sqlite


def test_bootstrap_sqlite_main_creates_expected_tables(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    db_path = tmp_path / "phase0" / "recall.db"
    monkeypatch.setenv("RECALL_DB_PATH", str(db_path))

    bootstrap_sqlite.main()

    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

    table_names = [row[0] for row in rows]
    assert table_names == ["alerts", "eval_results", "ingestion_log", "runs"]

    output = capsys.readouterr().out
    assert "SQLite initialized:" in output
    assert "Tables: alerts, eval_results, ingestion_log, runs" in output
