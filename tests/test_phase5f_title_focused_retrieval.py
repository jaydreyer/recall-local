#!/usr/bin/env python3
"""Regression tests for title-focused retrieval ranking."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.phase1 import retrieval


class Phase5FTitleFocusedRetrievalTests(unittest.TestCase):
    def test_extract_title_hints_from_quoted_query(self) -> None:
        hints = retrieval._extract_title_hints(  # noqa: SLF001
            'Summarize the article "The New Skill in AI Is Not Prompting, It\'s Context Engineering" for me.'
        )

        self.assertEqual(hints, ["The New Skill in AI Is Not Prompting, It's Context Engineering"])

    def test_focused_retrieval_query_prefers_quoted_title(self) -> None:
        title_hints = ["The New Skill in AI Is Not Prompting, It's Context Engineering"]

        focused = retrieval._focused_retrieval_query(  # noqa: SLF001
            'Summarize the article "The New Skill in AI Is Not Prompting, It\'s Context Engineering" for me.',
            title_hints=title_hints,
        )

        self.assertEqual(focused, title_hints[0])

    def test_focused_retrieval_query_combines_multiple_titles(self) -> None:
        title_hints = [
            "Vector Embeddings Guide",
            "LLM Embeddings Vector DB Comparison Guide",
        ]

        focused = retrieval._focused_retrieval_query(  # noqa: SLF001
            'Compare the "Vector Embeddings Guide" with the "LLM Embeddings Vector DB Comparison Guide".',
            title_hints=title_hints,
        )

        self.assertIn(title_hints[0], focused)
        self.assertIn(title_hints[1], focused)

    def test_title_match_score_prefers_exact_title_match(self) -> None:
        exact = retrieval.RetrievedChunk(
            doc_id="doc-1",
            chunk_id="chunk-1",
            title="The New Skill in AI Is Not Prompting, It's Context Engineering",
            source="https://philschmid.de/context-engineering",
            text="...",
            score=0.42,
            source_type="url",
            ingestion_channel="bookmarklet",
            group="reference",
            tags=[],
        )
        partial = retrieval.RetrievedChunk(
            doc_id="doc-2",
            chunk_id="chunk-2",
            title="Multi Agentic Interview Questions",
            source="multi-agentic-interview-questions.pdf",
            text="...",
            score=0.55,
            source_type="file",
            ingestion_channel="file",
            group="reference",
            tags=[],
        )
        hints = ["The New Skill in AI Is Not Prompting, It's Context Engineering"]

        exact_score = retrieval._title_match_score(item=exact, title_hints=hints)  # noqa: SLF001
        partial_score = retrieval._title_match_score(item=partial, title_hints=hints)  # noqa: SLF001

        self.assertGreater(exact_score, partial_score)
        self.assertEqual(exact_score, 1.0)

    def test_reranker_promotes_exact_title_match_over_generic_overlap(self) -> None:
        hints = ["The New Skill in AI Is Not Prompting, It's Context Engineering"]
        generic = retrieval.RetrievedChunk(
            doc_id="doc-generic",
            chunk_id="chunk-generic",
            title="Prompt Engineering Overview",
            source="https://platform.claude.com/docs/prompt-engineering/overview",
            text="Context engineering and prompting are discussed broadly in AI systems.",
            score=0.82,
            source_type="url",
            ingestion_channel="bookmarklet",
            group="reference",
            tags=[],
        )
        exact = retrieval.RetrievedChunk(
            doc_id="doc-exact",
            chunk_id="chunk-exact",
            title="The New Skill in AI Is Not Prompting, It's Context Engineering",
            source="https://philschmid.de/context-engineering",
            text="The article argues that context engineering is broader than prompting.",
            score=0.63,
            source_type="url",
            ingestion_channel="bookmarklet",
            group="reference",
            tags=[],
        )

        reranked = retrieval._apply_heuristic_reranker(  # noqa: SLF001
            [generic, exact],
            query='Summarize the article "The New Skill in AI Is Not Prompting, It\'s Context Engineering" for me.',
            reranker_weight=0.4,
            title_hints=hints,
        )

        self.assertEqual(reranked[0].doc_id, "doc-exact")

    def test_expand_title_matched_document_loads_same_doc_chunks(self) -> None:
        initial = [
            retrieval.RetrievedChunk(
                doc_id="doc-exact",
                chunk_id="chunk-2",
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="middle",
                score=0.9,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
                title_match_score=1.0,
                chunk_index=2,
            ),
            retrieval.RetrievedChunk(
                doc_id="doc-other",
                chunk_id="chunk-1",
                title="Prompt Engineering Overview",
                source="https://example.com/prompting",
                text="other",
                score=0.7,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
                title_match_score=0.2,
                chunk_index=1,
            ),
        ]
        fake_points = [
            SimpleNamespace(
                payload={
                    "doc_id": "doc-exact",
                    "chunk_id": "chunk-0",
                    "chunk_index": 0,
                    "title": "The New Skill in AI Is Not Prompting, It's Context Engineering",
                    "source": "https://philschmid.de/context-engineering",
                    "text": "first",
                    "source_type": "url",
                    "ingestion_channel": "bookmarklet",
                    "group": "reference",
                    "tags": ["article"],
                }
            ),
            SimpleNamespace(
                payload={
                    "doc_id": "doc-exact",
                    "chunk_id": "chunk-1",
                    "chunk_index": 1,
                    "title": "The New Skill in AI Is Not Prompting, It's Context Engineering",
                    "source": "https://philschmid.de/context-engineering",
                    "text": "second",
                    "source_type": "url",
                    "ingestion_channel": "bookmarklet",
                    "group": "reference",
                    "tags": ["article"],
                }
            ),
        ]
        fake_qdrant = SimpleNamespace(scroll=lambda **_: (fake_points, None))

        with patch("scripts.phase1.retrieval._import_qdrant_models") as models_mock:
            models_mock.return_value = SimpleNamespace(
                FieldCondition=lambda **kwargs: kwargs,
                MatchValue=lambda **kwargs: kwargs,
                MatchAny=lambda **kwargs: kwargs,
                Filter=lambda **kwargs: SimpleNamespace(**kwargs),
            )
            expanded = retrieval._expand_title_matched_document(  # noqa: SLF001
                qdrant=fake_qdrant,
                collection="recall_docs",
                chunks=initial,
                filter_tags=["article"],
                filter_tag_mode="any",
                filter_group=None,
                limit=8,
            )

        self.assertEqual([item.chunk_id for item in expanded[:2]], ["chunk-0", "chunk-1"])
        self.assertTrue(all(item.doc_id == "doc-exact" for item in expanded))

    def test_lookup_document_by_title_hints_falls_back_to_payload_scan(self) -> None:
        page_one = [
            SimpleNamespace(
                payload={
                    "doc_id": "doc-other",
                    "chunk_id": "chunk-x",
                    "chunk_index": 0,
                    "title": "Prompt Engineering Overview",
                    "source": "https://example.com/prompting",
                    "text": "other",
                    "source_type": "url",
                    "ingestion_channel": "bookmarklet",
                    "group": "reference",
                    "tags": ["article"],
                }
            ),
            SimpleNamespace(
                payload={
                    "doc_id": "doc-exact",
                    "chunk_id": "chunk-y",
                    "chunk_index": 0,
                    "title": "The New Skill in AI Is Not Prompting, It's Context Engineering",
                    "source": "https://philschmid.de/context-engineering",
                    "text": "first",
                    "source_type": "url",
                    "ingestion_channel": "bookmarklet",
                    "group": "reference",
                    "tags": ["article"],
                }
            ),
        ]
        fake_qdrant = SimpleNamespace(scroll=lambda **_: (page_one, None))
        loaded_doc_chunks = [
            retrieval.RetrievedChunk(
                doc_id="doc-exact",
                chunk_id="chunk-0",
                chunk_index=0,
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="first",
                score=1.0,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            )
        ]

        with patch("scripts.phase1.retrieval._import_qdrant_models") as models_mock, patch(
            "scripts.phase1.retrieval._load_chunks_for_doc_id",
            return_value=loaded_doc_chunks,
        ) as load_mock:
            models_mock.return_value = SimpleNamespace(
                FieldCondition=lambda **kwargs: kwargs,
                MatchValue=lambda **kwargs: kwargs,
                MatchAny=lambda **kwargs: kwargs,
                Filter=lambda **kwargs: SimpleNamespace(**kwargs),
            )
            resolved = retrieval._lookup_document_by_title_hints(  # noqa: SLF001
                qdrant=fake_qdrant,
                collection="recall_docs",
                title_hints=["The New Skill in AI Is Not Prompting, It's Context Engineering"],
                filter_tags=["article"],
                filter_tag_mode="any",
                filter_group=None,
                limit=8,
            )

        load_mock.assert_called_once()
        self.assertTrue(resolved)
        self.assertTrue(all(item.doc_id == "doc-exact" for item in resolved))

    def test_lookup_documents_by_title_hints_returns_multiple_docs(self) -> None:
        loaded_chunks = {
            "doc-a": [
                retrieval.RetrievedChunk(
                    doc_id="doc-a",
                    chunk_id="chunk-a-0",
                    chunk_index=0,
                    title="Vector Embeddings Guide",
                    source="vector-embeddings-guide.pdf",
                    text="first",
                    score=1.0,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["learning"],
                )
            ],
            "doc-b": [
                retrieval.RetrievedChunk(
                    doc_id="doc-b",
                    chunk_id="chunk-b-0",
                    chunk_index=0,
                    title="LLM Embeddings Vector DB Comparison Guide",
                    source="llm-embeddings-vectordb-guide.pdf",
                    text="second",
                    score=1.0,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["learning"],
                )
            ],
        }

        with patch(
            "scripts.phase1.retrieval._find_best_doc_id_by_title_hints",
            side_effect=["doc-a", "doc-b"],
        ), patch(
            "scripts.phase1.retrieval._load_chunks_for_doc_id",
            side_effect=lambda **kwargs: loaded_chunks[kwargs["doc_id"]],
        ):
            resolved = retrieval._lookup_documents_by_title_hints(  # noqa: SLF001
                qdrant=SimpleNamespace(),
                collection="recall_docs",
                title_hints=["Vector Embeddings Guide", "LLM Embeddings Vector DB Comparison Guide"],
                filter_tags=["learning"],
                filter_tag_mode="all",
                filter_group=None,
                limit=8,
            )

        self.assertEqual({item.doc_id for item in resolved}, {"doc-a", "doc-b"})

    def test_has_strong_title_match_requires_high_score(self) -> None:
        weak = [
            retrieval.RetrievedChunk(
                doc_id="doc-1",
                chunk_id="chunk-1",
                title="Prompt Engineering Overview",
                source="https://example.com",
                text="x",
                score=0.4,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=[],
                title_match_score=0.55,
            )
        ]
        strong = [
            retrieval.RetrievedChunk(
                doc_id="doc-1",
                chunk_id="chunk-1",
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="x",
                score=0.4,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=[],
                title_match_score=0.95,
            )
        ]

        self.assertFalse(retrieval._has_strong_title_match(weak))  # noqa: SLF001
        self.assertTrue(retrieval._has_strong_title_match(strong))  # noqa: SLF001


if __name__ == "__main__":
    unittest.main()
