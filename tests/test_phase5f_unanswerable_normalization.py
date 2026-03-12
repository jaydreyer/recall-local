#!/usr/bin/env python3
"""Phase 5F regression tests for unanswerable response normalization guards."""

from __future__ import annotations

import unittest
from unittest.mock import patch

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
        self.assertIn("5-8", instructions)

    def test_infer_answer_style_for_comparison_request(self) -> None:
        instructions = rag_query._infer_answer_style_instructions(  # noqa: SLF001
            query="How is context engineering different than prompt engineering?",
            mode="default",
        )

        self.assertIn("comparison", instructions.lower())
        self.assertIn("differences", instructions.lower())

    def test_infer_answer_style_for_explanatory_request(self) -> None:
        instructions = rag_query._infer_answer_style_instructions(  # noqa: SLF001
            query="What are the benefits of prompt engineering?",
            mode="default",
            query_strategy="explanatory_qa",
        )

        self.assertIn("overview", instructions.lower())
        self.assertIn("benefits", instructions.lower())

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

    def test_named_document_summary_query_is_detected(self) -> None:
        self.assertTrue(
            rag_query._is_named_document_summary_query(  # noqa: SLF001
                'Summarize the article "The New Skill in AI Is Not Prompting, It\'s Context Engineering" for me.'
            )
        )

    def test_query_strategy_prefers_document_summary_for_dominant_doc(self) -> None:
        retrieved = [
            rag_query.RetrievedChunk(
                doc_id="doc-1",
                chunk_id="chunk-1",
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="a",
                score=0.9,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
            rag_query.RetrievedChunk(
                doc_id="doc-1",
                chunk_id="chunk-2",
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="b",
                score=0.8,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
            rag_query.RetrievedChunk(
                doc_id="doc-2",
                chunk_id="chunk-9",
                title="Prompt Engineering Overview",
                source="https://example.com/prompting",
                text="c",
                score=0.4,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
        ]

        strategy = rag_query._query_strategy(  # noqa: SLF001
            question='Summarize the article "The New Skill in AI Is Not Prompting, It\'s Context Engineering" for me.',
            retrieved=retrieved,
        )

        self.assertEqual(strategy, "document_summary")

    def test_query_strategy_detects_compare_queries(self) -> None:
        strategy = rag_query._query_strategy(  # noqa: SLF001
            question="How is prompt engineering different than context engineering? Give examples.",
            retrieved=[],
        )

        self.assertEqual(strategy, "compare_synthesis")

    def test_query_strategy_detects_named_source_lookup_queries(self) -> None:
        strategy = rag_query._query_strategy(  # noqa: SLF001
            question="According to the article \"The New Skill in AI is Not Prompting, It's Context Engineering\", what is the main bottleneck in building useful LLM systems?",
            retrieved=[],
        )

        self.assertEqual(strategy, "named_source_lookup")

    def test_query_strategy_detects_multi_document_synthesis_queries(self) -> None:
        strategy = rag_query._query_strategy(  # noqa: SLF001
            question="What are practical ways to reduce latency in multi-agent systems, and what tradeoffs should I expect in RAG design?",
            retrieved=[],
        )

        self.assertEqual(strategy, "multi_document_synthesis")

    def test_select_generation_chunks_for_compare_keeps_multiple_docs(self) -> None:
        retrieved = [
            rag_query.RetrievedChunk(
                doc_id="doc-a",
                chunk_id="chunk-a1",
                title="Prompt Engineering Overview",
                source="https://example.com/prompt",
                text="prompt details",
                score=0.95,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
            rag_query.RetrievedChunk(
                doc_id="doc-a",
                chunk_id="chunk-a2",
                title="Prompt Engineering Overview",
                source="https://example.com/prompt",
                text="prompt examples",
                score=0.91,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
            rag_query.RetrievedChunk(
                doc_id="doc-b",
                chunk_id="chunk-b1",
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="context details",
                score=0.93,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
            rag_query.RetrievedChunk(
                doc_id="doc-b",
                chunk_id="chunk-b2",
                title="The New Skill in AI Is Not Prompting, It's Context Engineering",
                source="https://philschmid.de/context-engineering",
                text="context examples",
                score=0.88,
                source_type="url",
                ingestion_channel="bookmarklet",
                group="reference",
                tags=["article"],
            ),
        ]

        selected = rag_query._select_generation_chunks(  # noqa: SLF001
            question="How is prompt engineering different than context engineering? Give examples.",
            retrieved=retrieved,
            query_strategy="compare_synthesis",
        )

        self.assertEqual({item.doc_id for item in selected}, {"doc-a", "doc-b"})

    def test_ranked_doc_ids_for_compare_prefers_title_overlap_over_generic_doc(self) -> None:
        grouped = rag_query._group_chunks_by_doc_id(  # noqa: SLF001
            [
                rag_query.RetrievedChunk(
                    doc_id="generic",
                    chunk_id="generic-1",
                    title="GenAI Interview Questions",
                    source="genai-interview-questions.pdf",
                    text="prompt context examples",
                    score=0.95,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["job-search"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="prompt-doc",
                    chunk_id="prompt-1",
                    title="Claude Prompt Engineering Overview",
                    source="https://platform.claude.com/docs/en/build-with-claude/prompt-engineering",
                    text="prompt engineering",
                    score=0.7,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="context-doc",
                    chunk_id="context-1",
                    title="The New Skill in AI is Not Prompting, It's Context Engineering",
                    source="https://www.philschmid.de/context-engineering",
                    text="context engineering",
                    score=0.69,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
            ]
        )

        ranked = rag_query._ranked_doc_ids(  # noqa: SLF001
            question="How is prompt engineering different than context engineering? Give examples.",
            grouped=grouped,
            query_strategy="compare_synthesis",
        )

        self.assertEqual(ranked[:2], ["prompt-doc", "context-doc"])

    def test_synthesis_subqueries_split_multi_clause_question(self) -> None:
        subqueries = rag_query._synthesis_subqueries(  # noqa: SLF001
            "What are practical ways to reduce latency in multi-agent systems, and what tradeoffs should I expect in RAG design?"
        )

        self.assertEqual(
            subqueries,
            [
                "What are practical ways to reduce latency in multi-agent systems",
                "what tradeoffs should I expect in RAG design",
            ],
        )

    def test_retrieve_for_query_strategy_interleaves_synthesis_subqueries(self) -> None:
        latency_chunk = rag_query.RetrievedChunk(
            doc_id="doc-latency",
            chunk_id="chunk-latency",
            title="Handling Latency in Multi-Agentic Systems",
            source="latency.pdf",
            text="latency",
            score=0.9,
            source_type="file",
            ingestion_channel="file",
            group="reference",
            tags=["learning"],
        )
        rag_chunk = rag_query.RetrievedChunk(
            doc_id="doc-rag",
            chunk_id="chunk-rag",
            title="Advanced RAG Decision Flow Chart",
            source="rag.pdf",
            text="rag",
            score=0.1,
            source_type="file",
            ingestion_channel="file",
            group="reference",
            tags=["learning"],
        )

        with patch(
            "scripts.phase1.rag_query.retrieve_chunks",
            side_effect=[
                [latency_chunk],
                [rag_chunk],
                [latency_chunk],
            ],
        ):
            merged = rag_query._retrieve_for_query_strategy(  # noqa: SLF001
                question="What are practical ways to reduce latency in multi-agent systems, and what tradeoffs should I expect in RAG design?",
                query_strategy="multi_document_synthesis",
                top_k=8,
                min_score=0.2,
                filter_tags=["learning", "genai-docs"],
                filter_tag_mode="all",
                filter_group=None,
                retrieval_mode="hybrid",
                hybrid_alpha=None,
                enable_reranker=True,
                reranker_weight=0.65,
            )

        self.assertEqual([item.doc_id for item in merged[:2]], ["doc-latency", "doc-rag"])

    def test_prioritize_chunks_for_subquery_prefers_title_overlap(self) -> None:
        prioritized = rag_query._prioritize_chunks_for_subquery(  # noqa: SLF001
            [
                rag_query.RetrievedChunk(
                    doc_id="doc-generic",
                    chunk_id="chunk-generic",
                    title="AI Patterns",
                    source="patterns.pdf",
                    text="generic",
                    score=0.3,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["learning"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-rag",
                    chunk_id="chunk-rag",
                    title="Advanced RAG Decision Flow Chart",
                    source="rag-flow.pdf",
                    text="rag",
                    score=0.1,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["learning"],
                ),
            ],
            query="what tradeoffs should I expect in RAG design",
        )

        self.assertEqual(prioritized[0].doc_id, "doc-rag")

    def test_select_generation_chunks_for_document_summary_stays_on_primary_doc(self) -> None:
        retrieved = [
            rag_query.RetrievedChunk(
                doc_id="doc-primary",
                chunk_id=f"chunk-{index}",
                title="Vector Embeddings Guide",
                source="vector-embeddings-guide.pdf",
                text=f"chunk {index}",
                score=1.0 - (index * 0.01),
                source_type="file",
                ingestion_channel="file",
                group="reference",
                tags=["learning"],
                chunk_index=index,
            )
            for index in range(10)
        ]
        retrieved.append(
            rag_query.RetrievedChunk(
                doc_id="doc-other",
                chunk_id="other-1",
                title="Other Guide",
                source="other.pdf",
                text="other",
                score=0.5,
                source_type="file",
                ingestion_channel="file",
                group="reference",
                tags=["learning"],
                chunk_index=0,
            )
        )

        selected = rag_query._select_generation_chunks(  # noqa: SLF001
            question='Summarize the document "Vector Embeddings Guide".',
            retrieved=retrieved,
            query_strategy="document_summary",
        )

        self.assertTrue(selected)
        self.assertTrue(all(item.doc_id == "doc-primary" for item in selected))
        self.assertLessEqual(len(selected), rag_query.DOCUMENT_SUMMARY_MAX_SELECTED_CHUNKS)

    def test_build_context_truncates_large_chunk_text(self) -> None:
        chunks = [
            rag_query.RetrievedChunk(
                doc_id="doc-1",
                chunk_id="chunk-1",
                title="Large Doc",
                source="large.pdf",
                text="word " * 2000,
                score=0.9,
                source_type="file",
                ingestion_channel="file",
                group="reference",
                tags=["learning"],
                chunk_index=0,
            )
        ]

        context = rag_query._build_context(  # noqa: SLF001
            chunks,
            query_strategy="general_qa",
        )

        self.assertLess(len(context), 8000)

    def test_validation_requirements_for_compare_require_multi_doc_support(self) -> None:
        requirements = rag_query._validation_requirements(  # noqa: SLF001
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-1",
                    chunk_id="chunk-1",
                    title="Doc 1",
                    source="doc1.pdf",
                    text="a",
                    score=0.9,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=[],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-2",
                    chunk_id="chunk-2",
                    title="Doc 2",
                    source="doc2.pdf",
                    text="b",
                    score=0.8,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=[],
                ),
            ],
            query_strategy="compare_synthesis",
            query="How is prompt engineering different than context engineering?",
            mode="default",
        )

        self.assertEqual(requirements["min_citation_count"], 2)
        self.assertEqual(requirements["min_distinct_doc_count"], 2)
        self.assertEqual(requirements["min_bullet_count"], 4)
        self.assertEqual(requirements["min_answer_chars"], 320)

    def test_validation_requirements_for_general_explanatory_query_require_structure(self) -> None:
        requirements = rag_query._validation_requirements(  # noqa: SLF001
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-1",
                    chunk_id="chunk-1",
                    title="Prompt Engineering Guide",
                    source="guide.pdf",
                    text="a",
                    score=0.9,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=[],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-2",
                    chunk_id="chunk-2",
                    title="Prompt Benefits",
                    source="benefits.pdf",
                    text="b",
                    score=0.8,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=[],
                ),
            ],
            query_strategy="explanatory_qa",
            query="What are the benefits of prompt engineering?",
            mode="default",
        )

        self.assertEqual(requirements["min_bullet_count"], 4)
        self.assertEqual(requirements["min_citation_count"], 2)
        self.assertEqual(requirements["min_answer_chars"], 320)

    def test_query_strategy_detects_explanatory_queries(self) -> None:
        self.assertEqual(
            rag_query._query_strategy(  # noqa: SLF001
                question="What are the benefits of prompt engineering? Give examples if possible.",
                retrieved=[],
            ),
            "explanatory_qa",
        )

    def test_sensitive_secret_query_is_not_routed_to_explanatory_qa(self) -> None:
        self.assertNotEqual(
            rag_query._query_strategy(  # noqa: SLF001
                question="What is the exact private API key currently configured for the production LLM provider?",
                retrieved=[],
            ),
            "explanatory_qa",
        )

    def test_sensitive_secret_query_is_normalized_to_abstention(self) -> None:
        response = {
            "answer": "Here are the concrete takeaways.\n- token details\n- config details\n- secret details\n- more details",
            "citations": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
            "confidence_level": "medium",
            "assumptions": [],
            "sources": [{"doc_id": "doc-1", "chunk_id": "chunk-1"}],
        }

        reason = rag_query._normalize_sensitive_query_response(  # noqa: SLF001
            question="What is the exact private API key currently configured for the production LLM provider?",
            response=response,
        )

        self.assertIsNotNone(reason)
        self.assertEqual(response["answer"], rag_query.UNANSWERABLE_ANSWER)
        self.assertEqual(response["confidence_level"], "low")
        self.assertEqual(
            rag_query._query_strategy(  # noqa: SLF001
                question="How can I enhance my prompt-engineering abilities?",
                retrieved=[],
            ),
            "explanatory_qa",
        )

    def test_prompt_profile_name_prefers_explanatory_strategy(self) -> None:
        self.assertEqual(
            rag_query._prompt_profile_name("default", query_strategy="explanatory_qa"),  # noqa: SLF001
            "workflow_02_explanatory_qa",
        )

    def test_prompt_profile_name_prefers_named_source_lookup_strategy(self) -> None:
        self.assertEqual(
            rag_query._prompt_profile_name("default", query_strategy="named_source_lookup"),  # noqa: SLF001
            "workflow_02_targeted_lookup",
        )

    def test_build_compare_fallback_response_returns_extract_from_two_docs(self) -> None:
        response = rag_query._build_compare_fallback_response(  # noqa: SLF001
            question="How is prompt engineering different than context engineering? Give examples.",
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-context",
                    chunk_id="chunk-context",
                    title="The New Skill in AI is Not Prompting, It's Context Engineering",
                    source="https://philschmid.de/context-engineering",
                    text="Context engineering is about providing the right information and tools at the right time.",
                    score=0.9,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-prompt",
                    chunk_id="chunk-prompt",
                    title="Claude Prompt Engineering Overview",
                    source="https://platform.claude.com/docs/prompt-engineering",
                    text="Prompt engineering focuses on writing clearer instructions and examples inside the prompt.",
                    score=0.8,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
            ],
            reason="validation failed",
        )

        self.assertIsNotNone(response)
        self.assertIn("prompt engineering", response["answer"].lower())
        self.assertIn("context engineering", response["answer"].lower())
        self.assertEqual(len(response["citations"]), 2)

    def test_build_general_qa_fallback_response_returns_structured_bullets(self) -> None:
        response = rag_query._build_general_qa_fallback_response(  # noqa: SLF001
            question="What are the benefits of prompt engineering? Give examples if possible.",
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-1",
                    chunk_id="chunk-1",
                    title="Prompt Engineering for AI Guide",
                    source="https://cloud.google.com/discover/what-is-prompt-engineering",
                    text="Prompt engineering helps guide models toward more accurate, relevant, and safe responses.",
                    score=0.9,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-2",
                    chunk_id="chunk-2",
                    title="Prompt Engineering Overview",
                    source="https://platform.claude.com/docs/prompt-engineering",
                    text="Well-structured prompts make outputs easier to steer and evaluate, especially when examples are included.",
                    score=0.8,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-3",
                    chunk_id="chunk-3",
                    title="Prompting Guide",
                    source="https://example.com/prompting",
                    text="Prompt design can also improve consistency by clarifying the desired format and task boundaries.",
                    score=0.7,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
            ],
            reason="validation failed",
            mode="default",
            parsed_answer="Prompt engineering helps produce more relevant, controlled, and useful model responses.",
        )

        self.assertIsNotNone(response)
        self.assertGreaterEqual(response["answer"].count("\n- "), 3)
        self.assertEqual(len(response["citations"]), 3)
        self.assertIn("Prompt engineering helps produce", response["answer"])
        self.assertIn("More control over outputs", response["answer"])

    def test_build_explanatory_fallback_response_returns_clear_takeaways(self) -> None:
        response = rag_query._build_explanatory_fallback_response(  # noqa: SLF001
            question="How can I enhance my prompt-engineering abilities?",
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-1",
                    chunk_id="chunk-1",
                    title="Prompt Engineering for AI Guide",
                    source="https://cloud.google.com/discover/what-is-prompt-engineering",
                    text="Clear instructions and explicit formats help models respond more consistently.",
                    score=0.9,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-2",
                    chunk_id="chunk-2",
                    title="Claude Prompt Engineering Overview",
                    source="https://platform.claude.com/docs/prompt-engineering",
                    text="Examples and reference outputs make it easier to steer the model toward the style you want.",
                    score=0.85,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-3",
                    chunk_id="chunk-3",
                    title="Prompting Guide",
                    source="https://example.com/prompting",
                    text="Testing prompt variants side by side helps you evaluate quality and iterate deliberately.",
                    score=0.8,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-4",
                    chunk_id="chunk-4",
                    title="Context Engineering Notes",
                    source="https://example.com/context",
                    text="Relevant context and supporting information keep the model grounded on the real task.",
                    score=0.75,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
            ],
            reason="validation failed",
            parsed_answer="You can improve by tightening structure, adding context, and testing iterations.",
        )

        self.assertIsNotNone(response)
        self.assertGreaterEqual(response["answer"].count("\n- "), 4)
        self.assertEqual(len(response["citations"]), 4)
        self.assertIn("Use clearer structure", response["answer"])
        self.assertIn("Test and compare results", response["answer"])

    def test_generation_max_tokens_uses_summary_budget_for_structured_compare(self) -> None:
        settings = rag_query.RagSettings(  # noqa: SLF001
            db_path=rag_query.ROOT / "data" / "recall.db",
            artifacts_dir=rag_query.ROOT / "data" / "artifacts" / "rag",
            prompt_path=rag_query.ROOT / "prompts" / "workflow_02_rag_answer.md",
            compare_prompt_path=rag_query.ROOT / "prompts" / "workflow_02_compare_synthesis.md",
            synthesis_prompt_path=rag_query.ROOT / "prompts" / "workflow_02_multi_document_synthesis.md",
            explanatory_prompt_path=rag_query.ROOT / "prompts" / "workflow_02_explanatory_qa.md",
            summary_prompt_path=rag_query.ROOT / "prompts" / "workflow_02_document_summary.md",
            retry_prompt_path=rag_query.ROOT / "prompts" / "workflow_02_rag_answer_retry.md",
            job_search_prompt_path=rag_query.ROOT / "prompts" / "job_search_coach.md",
            learning_prompt_path=rag_query.ROOT / "prompts" / "learning_coach.md",
            top_k=5,
            summary_top_k=20,
            min_score=0.2,
            max_retries=1,
            temperature=0.2,
            summary_max_tokens=768,
            default_max_tokens=384,
        )

        self.assertEqual(
            rag_query._generation_max_tokens(  # noqa: SLF001
                question="How is prompt engineering different than context engineering?",
                mode="default",
                query_strategy="compare_synthesis",
                settings=settings,
            ),
            768,
        )

    def test_supporting_snippet_skips_boilerplate_when_query_terms_match_later_sentence(self) -> None:
        snippet = rag_query._supporting_snippet(  # noqa: SLF001
            "Thursday AM free if that works for you? Sent an invite, lmk if it works. Context engineering is about providing the right information and tools at the right time.",
            question="How is context engineering different than prompt engineering?",
        )

        self.assertIn("Context engineering", snippet)
        self.assertNotIn("Thursday AM", snippet)

    def test_supporting_snippet_strips_q_and_a_prefixes(self) -> None:
        snippet = rag_query._supporting_snippet(  # noqa: SLF001
            "GenAI Interview Questions: A: Hybrid prompting combines structured and open-ended prompts to improve output quality and relevance.",
            question="What are the benefits of prompt engineering?",
        )

        self.assertIn("Hybrid prompting combines", snippet)
        self.assertNotIn("GenAI Interview Questions", snippet)
        self.assertNotIn("A:", snippet)

    def test_build_document_summary_fallback_response_returns_bullets(self) -> None:
        response = rag_query._build_document_summary_fallback_response(  # noqa: SLF001
            question='Summarize the document "Advanced RAG Decision Flow Chart" and tell me the key decision points as bullets.',
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-rag",
                    chunk_id="chunk-1",
                    title="Advanced RAG Decision Flow Chart",
                    source="rag-flow.pdf",
                    text="RAG systems should choose retrieval depth based on data quality and answer requirements.",
                    score=0.9,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["learning", "rag", "system-design"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-rag",
                    chunk_id="chunk-2",
                    title="Advanced RAG Decision Flow Chart",
                    source="rag-flow.pdf",
                    text="Decision points include whether retrieval is needed, how much context to send, and how to reduce noise.",
                    score=0.8,
                    source_type="file",
                    ingestion_channel="file",
                    group="reference",
                    tags=["learning", "rag", "system-design"],
                ),
            ],
            reason="validation failed",
        )

        self.assertIsNotNone(response)
        self.assertIn("RAG", response["answer"])
        self.assertIn("\n-", response["answer"])
        self.assertGreaterEqual(len(response["citations"]), 2)

    def test_build_named_source_lookup_fallback_response_returns_direct_answer(self) -> None:
        response = rag_query._build_named_source_lookup_fallback_response(  # noqa: SLF001
            question="According to the article \"The New Skill in AI is Not Prompting, It's Context Engineering\", what is the main bottleneck in building useful LLM systems?",
            selected_chunks=[
                rag_query.RetrievedChunk(
                    doc_id="doc-context",
                    chunk_id="chunk-context",
                    title="The New Skill in AI is Not Prompting, It's Context Engineering",
                    source="https://philschmid.de/context-engineering",
                    text="The magic is not in a smarter model. It is about providing the right context, information, and tools at the right time.",
                    score=0.9,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
                rag_query.RetrievedChunk(
                    doc_id="doc-context",
                    chunk_id="chunk-context-2",
                    title="The New Skill in AI is Not Prompting, It's Context Engineering",
                    source="https://philschmid.de/context-engineering",
                    text="You need the right context for the right task.",
                    score=0.8,
                    source_type="url",
                    ingestion_channel="bookmarklet",
                    group="reference",
                    tags=["article"],
                ),
            ],
            reason="validation failed",
        )

        self.assertIsNotNone(response)
        self.assertIn("main bottleneck", response["answer"].lower())
        self.assertIn("right context", response["answer"].lower())
        self.assertGreaterEqual(len(response["citations"]), 1)

    def test_prompt_profile_name_prefers_document_summary_strategy(self) -> None:
        self.assertEqual(
            rag_query._prompt_profile_name("default", query_strategy="document_summary"),  # noqa: SLF001
            "workflow_02_document_summary",
        )

    def test_prompt_profile_name_prefers_compare_strategy(self) -> None:
        self.assertEqual(
            rag_query._prompt_profile_name("default", query_strategy="compare_synthesis"),  # noqa: SLF001
            "workflow_02_compare_synthesis",
        )

    def test_prompt_profile_name_prefers_multi_document_synthesis_strategy(self) -> None:
        self.assertEqual(
            rag_query._prompt_profile_name("default", query_strategy="multi_document_synthesis"),  # noqa: SLF001
            "workflow_02_multi_document_synthesis",
        )


if __name__ == "__main__":
    unittest.main()
