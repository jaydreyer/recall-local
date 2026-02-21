#!/usr/bin/env python3
"""Phase 0 connectivity smoke test."""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check(name: str, fn):
    try:
        msg = fn()
        print(f"[PASS] {name}: {msg}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {name}: {exc}")
        return False


def main() -> int:
    load_dotenv("docker/.env")
    load_dotenv("docker/.env.example")

    qdrant_host = os.getenv("QDRANT_HOST", "http://localhost:6333")
    n8n_host = os.getenv("N8N_HOST", "http://localhost:5678")
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    db_path = Path(os.getenv("RECALL_DB_PATH", "data/recall.db"))

    checks = []

    checks.append(
        check(
            "Ollama",
            lambda: f"{len(httpx.get(f'{ollama_host}/api/tags', timeout=5).json().get('models', []))} models",
        )
    )

    def _qdrant() -> str:
        result = httpx.get(f"{qdrant_host}/collections", timeout=5).json().get("result", {})
        names = [c["name"] for c in result.get("collections", [])]
        return f"collections={names}"

    checks.append(check("Qdrant", _qdrant))
    checks.append(
        check(
            "n8n",
            lambda: f"status={httpx.get(f'{n8n_host}/healthz', timeout=5).status_code}",
        )
    )

    def _sqlite() -> str:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        finally:
            conn.close()
        return f"tables={[r[0] for r in rows]}"

    checks.append(check("SQLite", _sqlite))

    def _llm_client() -> str:
        import scripts.llm_client as llm_client  # type: ignore

        return f"provider={llm_client.PROVIDER}"

    checks.append(check("LLM client", _llm_client))

    checks.append(check("data/incoming", lambda: str((Path("data/incoming")).resolve(strict=True))))
    checks.append(check("data/processed", lambda: str((Path("data/processed")).resolve(strict=True))))
    checks.append(check("data/artifacts", lambda: str((Path("data/artifacts")).resolve(strict=True))))

    passed = sum(1 for x in checks if x)
    total = len(checks)
    print(f"\nSummary: {passed}/{total} checks passed")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
