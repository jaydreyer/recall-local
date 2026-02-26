#!/usr/bin/env python3
"""Phase 5F regression tests for unanswerable response normalization guards."""

from __future__ import annotations

import unittest

from scripts.phase1 import rag_query


class Phase5FUnanswerableNormalizationTests(unittest.TestCase):
    def test_filter_tag_mode_normalizes_aliases(self) -> None:
        self.assertEqual(rag_query._normalize_filter_tag_mode("any"), "any")  # noqa: SLF001
        self.assertEqual(rag_query._normalize_filter_tag_mode("AND"), "all")  # noqa: SLF001

    def test_explicit_default_mode_is_not_overridden_by_filters(self) -> None:
        resolved = rag_query._resolve_mode(  # noqa: SLF001
            mode="default",
            filter_tags=["job-search"],
            filter_group="job-search",
        )
        self.assertEqual(resolved, "default")

    def test_implicit_mode_can_still_infer_from_filters(self) -> None:
        resolved = rag_query._resolve_mode(  # noqa: SLF001
            mode=None,
            filter_tags=["job-search"],
            filter_group=None,
        )
        self.assertEqual(resolved, "job-search")

    def test_identifier_like_answer_normalizes_to_abstention(self) -> None:
        response = {
            "answer": "1b7b0fe106ca4c1f9d8a20f227246749",
            "confidence_level": "high",
            "citations": [{"doc_id": "1b7b0fe106ca4c1f9d8a20f227246749", "chunk_id": "chunk-1"}],
            "sources": [{"doc_id": "1b7b0fe106ca4c1f9d8a20f227246749", "chunk_id": "chunk-1"}],
        }

        reason = rag_query._normalize_unanswerable_consistency(response)  # noqa: SLF001

        self.assertIsNotNone(reason)
        self.assertEqual(response["answer"], rag_query.UNANSWERABLE_ANSWER)
        self.assertEqual(response["confidence_level"], "low")

    def test_unanswerable_phrase_forces_low_confidence(self) -> None:
        response = {
            "answer": "I don't have enough information in the retrieved context to answer that.",
            "confidence_level": "high",
            "citations": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
            "sources": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
        }

        reason = rag_query._normalize_unanswerable_consistency(response)  # noqa: SLF001

        self.assertIsNotNone(reason)
        self.assertEqual(response["confidence_level"], "low")
        self.assertEqual(response["answer"], rag_query.UNANSWERABLE_ANSWER)

    def test_grounded_sentence_is_not_normalized(self) -> None:
        response = {
            "answer": "The bridge currently listens on port 8090 according to the environment inventory.",
            "confidence_level": "high",
            "citations": [{"doc_id": "doc-2", "chunk_id": "chunk-2"}],
            "sources": [{"doc_id": "doc-2", "chunk_id": "chunk-2"}],
        }

        reason = rag_query._normalize_unanswerable_consistency(response)  # noqa: SLF001

        self.assertIsNone(reason)
        self.assertEqual(response["confidence_level"], "high")


if __name__ == "__main__":
    unittest.main()
