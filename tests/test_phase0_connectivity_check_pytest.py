#!/usr/bin/env python3
"""Regression tests for Phase 0 connectivity checks."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from scripts.phase0 import connectivity_check


def test_check_returns_false_and_prints_failure(capsys: pytest.CaptureFixture[str]) -> None:
    result = connectivity_check.check("demo", lambda: (_ for _ in ()).throw(ValueError("boom")))

    assert result is False
    assert "[FAIL] demo: boom" in capsys.readouterr().out


def test_main_uses_env_hosts_and_reports_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = tmp_path / "recall.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE demo(id INTEGER)")
    conn.commit()
    conn.close()

    paths_seen: list[str] = []

    def fake_get(url: str, timeout: int) -> SimpleNamespace:
        paths_seen.append(url)
        if url.endswith("/api/tags"):
            return SimpleNamespace(json=lambda: {"models": [{"name": "qwen2.5:7b-instruct"}]})
        if url.endswith("/collections"):
            return SimpleNamespace(json=lambda: {"result": {"collections": [{"name": "recall_docs"}]}})
        if url.endswith("/healthz"):
            return SimpleNamespace(status_code=200)
        raise AssertionError(url)

    fake_llm = ModuleType("scripts.llm_client")
    fake_llm.PROVIDER = "ollama"

    monkeypatch.setattr(connectivity_check, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(connectivity_check.httpx, "get", fake_get)
    monkeypatch.setitem(sys.modules, "scripts.llm_client", fake_llm)
    monkeypatch.setenv("QDRANT_HOST", "http://qdrant.example:6333")
    monkeypatch.setenv("N8N_HOST", "http://n8n.example:5678")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.example:11434")
    monkeypatch.setenv("RECALL_DB_PATH", str(db_path))
    monkeypatch.chdir(tmp_path)
    for relative in ("data/incoming", "data/processed", "data/artifacts"):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)

    exit_code = connectivity_check.main()

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Summary: 8/8 checks passed" in out
    assert paths_seen == [
        "http://ollama.example:11434/api/tags",
        "http://qdrant.example:6333/collections",
        "http://n8n.example:5678/healthz",
    ]
