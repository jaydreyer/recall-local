#!/usr/bin/env python3
"""Pytest coverage for focused Phase 1 ingestion pipeline helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.phase1.ingestion_pipeline import IngestRequest, chunk_text, resolve_source_identity


def test_resolve_source_identity_prefers_explicit_source_key() -> None:
    """Use the caller-provided stable source key when one is available."""
    request = IngestRequest(
        source_type="text",
        content="hello",
        source_key="candidate-source-key",
        metadata={"source_key": "metadata-source-key"},
        replace_existing=True,
    )

    assert resolve_source_identity(request=request, source_ref="inline:text") == "candidate-source-key"


def test_resolve_source_identity_canonicalizes_url_tracking_params() -> None:
    """Strip tracking parameters so replace-existing works across equivalent URLs."""
    request = IngestRequest(source_type="url", content="https://example.com")

    resolved = resolve_source_identity(
        request=request,
        source_ref="https://Example.com/path/?utm_source=newsletter&b=2&a=1#fragment",
    )

    assert resolved == "https://example.com/path?a=1&b=2"


def test_resolve_source_identity_requires_source_key_for_replace_existing_inline_content() -> None:
    """Reject inline replacement without a stable caller-controlled source key."""
    request = IngestRequest(
        source_type="text",
        content="inline text",
        replace_existing=True,
    )

    with pytest.raises(ValueError, match="requires source_key"):
        resolve_source_identity(request=request, source_ref="inline:text")


def test_resolve_source_identity_uses_resolved_file_path(tmp_path: Path) -> None:
    """Resolve file sources to an absolute path for stable deduplication."""
    file_path = tmp_path / "note.txt"
    file_path.write_text("hello", encoding="utf-8")
    request = IngestRequest(source_type="file", content=str(file_path))

    resolved = resolve_source_identity(request=request, source_ref=str(file_path))

    assert resolved == str(file_path.resolve())


def test_chunk_text_keeps_sections_separate_when_encoder_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve heading boundaries even when tokenization falls back to character windows."""
    monkeypatch.setattr("scripts.phase1.ingestion_pipeline._load_encoder", lambda: None)
    text = "# Intro\nShort intro text.\n\n# Details\nSecond section text."

    chunks = chunk_text(text, max_tokens=50, overlap_tokens=10)

    assert chunks == [
        "# Intro\nShort intro text.",
        "# Details\nSecond section text.",
    ]
