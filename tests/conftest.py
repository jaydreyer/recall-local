#!/usr/bin/env python3
"""Shared pytest fixtures for Recall.local tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.phase6 import storage


@pytest.fixture
def temp_db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated SQLite path and wire it into RECALL_DB_PATH."""
    db_path = tmp_path / "recall.db"
    monkeypatch.setenv("RECALL_DB_PATH", str(db_path))
    return db_path


@pytest.fixture
def sqlite_conn(temp_db_path: Path) -> sqlite3.Connection:
    """Open a Phase 6-ready SQLite connection for tests and close it cleanly."""
    conn = storage.connect_db(temp_db_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def temp_vault_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide an isolated vault path and enable write-back for tests that need it."""
    vault_path = tmp_path / "vault"
    monkeypatch.setenv("RECALL_VAULT_PATH", str(vault_path))
    monkeypatch.setenv("RECALL_VAULT_WRITE_BACK", "true")
    return vault_path
