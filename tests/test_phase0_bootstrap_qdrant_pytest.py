#!/usr/bin/env python3
"""Regression tests for Phase 0 Qdrant bootstrap helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.phase0 import bootstrap_qdrant


def test_qdrant_client_from_env_uses_url_keyword(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

    monkeypatch.setenv("QDRANT_HOST", "http://qdrant.internal:6333")
    monkeypatch.setattr(bootstrap_qdrant, "QdrantClient", FakeClient)

    bootstrap_qdrant.qdrant_client_from_env()

    assert calls == [{"url": "http://qdrant.internal:6333"}]


def test_main_creates_collection_when_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    created: list[tuple[str, int]] = []

    class FakeClient:
        def get_collections(self) -> SimpleNamespace:
            return SimpleNamespace(collections=[])

        def create_collection(self, *, collection_name: str, vectors_config: object) -> None:
            created.append((collection_name, vectors_config.size))

    monkeypatch.setattr(bootstrap_qdrant, "qdrant_client_from_env", lambda: FakeClient())
    monkeypatch.setattr(bootstrap_qdrant, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("QDRANT_COLLECTION", "recall_docs")
    monkeypatch.setenv("EMBEDDING_DIMENSION", "1536")

    bootstrap_qdrant.main()

    out = capsys.readouterr().out
    assert created == [("recall_docs", 1536)]
    assert "Created collection: recall_docs (dimension=1536)" in out
