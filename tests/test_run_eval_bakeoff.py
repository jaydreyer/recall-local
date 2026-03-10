import json
import tempfile
import unittest
from pathlib import Path

from scripts.eval.run_eval import EvalCase, _count_bullets, _evaluate_payload, load_cases


class RunEvalBakeoffTests(unittest.TestCase):
    def test_load_cases_parses_bakeoff_fields(self) -> None:
        payload = [
            {
                "case_id": "doc-1",
                "category": "specific_document",
                "question": "Summarize this document.",
                "expected_title_contains": ["Vector Embeddings Guide"],
                "expected_source_contains": ["vector-embeddings-guide.pdf"],
                "min_bullet_count": 4,
                "min_citation_count": 2,
                "min_distinct_doc_count": 1,
                "min_answer_chars": 200,
            }
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            cases_path = Path(tmpdir) / "cases.json"
            cases_path.write_text(json.dumps(payload), encoding="utf-8")
            cases = load_cases(cases_path)

        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertEqual(case.case_id, "doc-1")
        self.assertEqual(case.category, "specific_document")
        self.assertEqual(case.expected_title_contains, ["Vector Embeddings Guide"])
        self.assertEqual(case.expected_source_contains, ["vector-embeddings-guide.pdf"])
        self.assertEqual(case.min_bullet_count, 4)
        self.assertEqual(case.min_citation_count, 2)
        self.assertEqual(case.min_distinct_doc_count, 1)
        self.assertEqual(case.min_answer_chars, 200)

    def test_evaluate_payload_checks_document_target_and_format(self) -> None:
        case = EvalCase(
            case_id="doc-1",
            category="specific_document",
            question="Summarize the document.",
            expected_doc_id=None,
            expected_answer=None,
            expected_title_contains=["Vector Embeddings Guide"],
            expected_source_contains=["vector-embeddings-guide.pdf"],
            max_latency_ms=5000,
            expect_unanswerable=False,
            mode=None,
            filter_tags=[],
            filter_tag_mode=None,
            required_terms=["embedding", "retrieval"],
            required_source_tags=[],
            required_source_tags_any_of=[],
            min_bullet_count=3,
            min_citation_count=2,
            min_distinct_doc_count=1,
            min_answer_chars=80,
            semantic_similarity_min=None,
            retrieval_mode=None,
            hybrid_alpha=None,
            enable_reranker=None,
            reranker_weight=None,
        )
        payload = {
            "answer": "- Embeddings map text into vectors.\n- Retrieval compares vectors for semantic search.\n- Better chunking improves retrieval quality.",
            "confidence_level": "medium",
            "citations": [
                {"doc_id": "doc-123", "chunk_id": "chunk-1"},
                {"doc_id": "doc-123", "chunk_id": "chunk-2"},
            ],
            "sources": [
                {
                    "doc_id": "doc-123",
                    "chunk_id": "chunk-1",
                    "title": "Vector Embeddings Guide",
                    "source": "/tmp/vector-embeddings-guide.pdf",
                    "tags": ["learning", "genai-docs"],
                },
                {
                    "doc_id": "doc-123",
                    "chunk_id": "chunk-2",
                    "title": "Vector Embeddings Guide",
                    "source": "/tmp/vector-embeddings-guide.pdf",
                    "tags": ["learning", "genai-docs"],
                },
            ],
        }

        result = _evaluate_payload(
            case=case,
            payload=payload,
            latency_ms=1200,
            default_max_latency_ms=5000,
            semantic_score_enabled=False,
            semantic_min_score=None,
            enforce_semantic_score=False,
        )

        self.assertTrue(result[0], result[-1])
        self.assertEqual(result[8], "Vector Embeddings Guide")
        self.assertTrue(result[10])
        self.assertTrue(result[11])
        self.assertTrue(result[12])
        self.assertTrue(result[13])
        self.assertTrue(result[14])
        self.assertTrue(result[15])
        self.assertEqual(result[16], 2)
        self.assertEqual(result[17], 1)
        self.assertEqual(result[18], 3)

    def test_evaluate_payload_fails_when_summary_uses_wrong_document(self) -> None:
        case = EvalCase(
            case_id="doc-2",
            category="specific_document",
            question="Summarize the document.",
            expected_doc_id=None,
            expected_answer=None,
            expected_title_contains=["The New Skill in AI is Not Prompting, It's Context Engineering"],
            expected_source_contains=["philschmid.de/context-engineering"],
            max_latency_ms=5000,
            expect_unanswerable=False,
            mode=None,
            filter_tags=[],
            filter_tag_mode=None,
            required_terms=[],
            required_source_tags=[],
            required_source_tags_any_of=[],
            min_bullet_count=2,
            min_citation_count=1,
            min_distinct_doc_count=None,
            min_answer_chars=40,
            semantic_similarity_min=None,
            retrieval_mode=None,
            hybrid_alpha=None,
            enable_reranker=None,
            reranker_weight=None,
        )
        payload = {
            "answer": "- Prompting matters.\n- Use examples.",
            "confidence_level": "medium",
            "citations": [{"doc_id": "doc-999", "chunk_id": "chunk-1"}],
            "sources": [
                {
                    "doc_id": "doc-999",
                    "chunk_id": "chunk-1",
                    "title": "Claude Prompt Engineering Overview",
                    "source": "https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview",
                    "tags": ["reference", "anthropic"],
                }
            ],
        }

        result = _evaluate_payload(
            case=case,
            payload=payload,
            latency_ms=1200,
            default_max_latency_ms=5000,
            semantic_score_enabled=False,
            semantic_min_score=None,
            enforce_semantic_score=False,
        )

        self.assertFalse(result[0])
        self.assertFalse(result[10])
        self.assertFalse(result[11])
        self.assertIn("expected text", result[-1])

    def test_count_bullets_handles_markdown_and_numbered_lists(self) -> None:
        answer = "- first\n* second\n1. third\nplain text"
        self.assertEqual(_count_bullets(answer), 3)


if __name__ == "__main__":
    unittest.main()
