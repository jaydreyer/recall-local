#!/usr/bin/env python3
"""Focused regression coverage for RAG response normalization and fallbacks."""

from __future__ import annotations

from scripts.phase1 import rag_query
from scripts.phase1.retrieval import RetrievedChunk


def _chunk(*, doc_id: str, chunk_id: str, title: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        doc_id=doc_id,
        chunk_id=chunk_id,
        title=title,
        source=f"{title}.md",
        text=text,
        score=0.9,
        source_type="note",
        ingestion_channel="webhook",
        group="reference",
        tags=[],
    )


def test_build_compare_fallback_response_returns_extractable_summary() -> None:
    chunks = [
        _chunk(doc_id="doc-a", chunk_id="doc-a:0001", title="API Design", text="API design focuses on explicit schemas."),
        _chunk(doc_id="doc-b", chunk_id="doc-b:0001", title="Release Ops", text="Release operations focus on safe rollbacks."),
        _chunk(doc_id="doc-a", chunk_id="doc-a:0002", title="API Design", text="Versioning keeps contracts predictable."),
    ]

    response = rag_query._build_compare_fallback_response(
        question="Compare API design and release operations",
        selected_chunks=chunks,
        reason="validation_failed",
    )

    assert response is not None
    assert response["audit"]["fallback_used"] is True
    assert len(response["citations"]) >= 2
    assert "API Design" in response["answer"] or "Release Ops" in response["answer"]


def test_normalize_unanswerable_consistency_abstains_on_identifier_like_answer() -> None:
    response = {
        "answer": "123e4567-e89b-12d3-a456-426614174000",
        "confidence_level": "high",
        "citations": [{"doc_id": "doc-1", "chunk_id": "doc-1:0001"}],
        "sources": [{"doc_id": "doc-1", "chunk_id": "doc-1:0001"}],
    }

    reason = rag_query._normalize_unanswerable_consistency(response)

    assert reason is not None
    assert response["answer"] == rag_query.UNANSWERABLE_ANSWER
    assert response["confidence_level"] == "low"


def test_normalize_low_confidence_response_preserves_cited_substantive_answer() -> None:
    response = {
        "answer": (
            "The runbook recommends a staged rollout with explicit rollback checks, service preflight validation, "
            "and a deterministic restart path before any production-facing verification is attempted."
        ),
        "confidence_level": "low",
        "citations": [{"doc_id": "doc-1", "chunk_id": "doc-1:0001"}],
        "sources": [{"doc_id": "doc-1", "chunk_id": "doc-1:0001"}],
        "assumptions": [],
    }

    reason = rag_query._normalize_low_confidence_response(response)

    assert reason is None
    assert response["answer"].startswith("The runbook recommends")
    assert any("retained despite low confidence" in item for item in response["assumptions"])


def test_normalize_sensitive_query_response_forces_abstention() -> None:
    response = {
        "answer": "The production token is abc123",
        "confidence_level": "high",
        "assumptions": [],
    }

    reason = rag_query._normalize_sensitive_query_response(
        question="What is the production API key currently configured?",
        response=response,
    )

    assert reason is not None
    assert response["answer"] == rag_query.UNANSWERABLE_ANSWER
    assert response["confidence_level"] == "low"
    assert any("Sensitive secret-seeking query" in item for item in response["assumptions"])
