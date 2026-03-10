#!/usr/bin/env python3
"""Regression tests for relaxed JSON parsing from local model outputs."""

from __future__ import annotations

import unittest

from scripts import validate_output


class ValidateOutputRelaxedJsonTests(unittest.TestCase):
    def test_parse_json_response_repairs_bare_keys(self) -> None:
        parsed = validate_output.parse_json_response(
            '{answer: "test", citations: [{doc_id: "doc-1", chunk_id: "chunk-1"}], confidence_level: "high", assumptions: []}'
        )

        self.assertEqual(parsed["answer"], "test")
        self.assertEqual(parsed["citations"][0]["doc_id"], "doc-1")

    def test_parse_json_response_repairs_single_quoted_pythonish_object(self) -> None:
        parsed = validate_output.parse_json_response(
            "{'answer': 'test', 'citations': [{'doc_id': 'doc-1', 'chunk_id': 'chunk-1'}], 'confidence_level': 'low', 'assumptions': [], 'fallback_used': false}"
        )

        self.assertEqual(parsed["answer"], "test")
        self.assertFalse(parsed["fallback_used"])

    def test_validate_rag_output_can_require_bullets_and_multiple_docs(self) -> None:
        raw = """
        {
          "answer": "Summary line\\n- First point\\n- Second point\\n- Third point",
          "citations": [
            {"doc_id": "doc-1", "chunk_id": "chunk-1"},
            {"doc_id": "doc-2", "chunk_id": "chunk-2"}
          ],
          "confidence_level": "high",
          "assumptions": []
        }
        """

        result = validate_output.validate_rag_output(
            raw,
            valid_citation_pairs={("doc-1", "chunk-1"), ("doc-2", "chunk-2")},
            min_citation_count=2,
            min_distinct_doc_count=2,
            min_bullet_count=3,
        )

        self.assertTrue(result.valid)

    def test_validate_rag_output_rejects_missing_bullets(self) -> None:
        raw = """
        {
          "answer": "Only a paragraph summary.",
          "citations": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
          "confidence_level": "high",
          "assumptions": []
        }
        """

        result = validate_output.validate_rag_output(
            raw,
            valid_citation_pairs={("doc-1", "chunk-1")},
            min_bullet_count=2,
        )

        self.assertFalse(result.valid)
        self.assertTrue(any("bullet" in error.lower() for error in result.errors))


if __name__ == "__main__":
    unittest.main()
