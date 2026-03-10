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

    def test_low_confidence_substantive_answer_with_citations_is_retained(self) -> None:
        response = {
            "answer": (
                "The top items called out are Perplexity's new Cowork scheduled tasks feature, "
                "a guide on building long-running agents with shell tools and skills, and a post "
                "on prompt caching to avoid recomputing repeated prefixes."
            ),
            "confidence_level": "low",
            "citations": [{"doc_id": "doc-3", "chunk_id": "chunk-3"}],
            "sources": [{"doc_id": "doc-3", "chunk_id": "chunk-3"}],
            "assumptions": [],
        }

        reason = rag_query._normalize_low_confidence_response(response)  # noqa: SLF001

        self.assertIsNone(reason)
        self.assertNotEqual(response["answer"], rag_query.UNANSWERABLE_ANSWER)
        self.assertIn(
            "Answer retained despite low confidence because cited context contains partial supporting evidence.",
            response["assumptions"],
        )

    def test_low_confidence_non_substantive_answer_normalizes_to_abstention(self) -> None:
        response = {
            "answer": "Not sure.",
            "confidence_level": "low",
            "citations": [],
            "sources": [],
            "assumptions": [],
        }

        reason = rag_query._normalize_low_confidence_response(response)  # noqa: SLF001

        self.assertIsNotNone(reason)
        self.assertEqual(response["answer"], rag_query.UNANSWERABLE_ANSWER)
        self.assertEqual(response["confidence_level"], "low")

    def test_infer_answer_style_for_bulleted_request(self) -> None:
        instructions = rag_query._infer_answer_style_instructions(  # noqa: SLF001
            query="Give me a bulleted list of what context engineering is all about.",
            mode="default",
        )

        self.assertIn("bullet", instructions.lower())
        self.assertIn("4-8", instructions)

    def test_infer_answer_style_for_comparison_request(self) -> None:
        instructions = rag_query._infer_answer_style_instructions(  # noqa: SLF001
            query="How is context engineering different than prompt engineering?",
            mode="default",
        )

        self.assertIn("comparison", instructions.lower())
        self.assertIn("differences", instructions.lower())

    def test_render_prompt_includes_answer_style_instructions(self) -> None:
        rendered = rag_query._render_prompt(  # noqa: SLF001
            template="Query={{QUERY}}\nStyle={{ANSWER_STYLE_INSTRUCTIONS}}",
            query="test",
            context="ctx",
            previous_response="",
            validation_errors=[],
            answer_style_instructions="Use bullets.",
        )

        self.assertIn("Style=Use bullets.", rendered)


if __name__ == "__main__":
    unittest.main()
