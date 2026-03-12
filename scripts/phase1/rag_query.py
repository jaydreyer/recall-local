#!/usr/bin/env python3
"""Workflow 02 cited RAG query runner for Recall.local."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import llm_client  # noqa: E402
from scripts.phase1.group_model import normalize_group  # noqa: E402
from scripts.phase1.retrieval import RetrievedChunk, retrieve_chunks  # noqa: E402
from scripts.validate_output import ValidationResult, validate_rag_output  # noqa: E402

UNANSWERABLE_ANSWER = "I don't have enough information in the retrieved context to answer that."
UNANSWERABLE_PATTERNS = (
    "i don't have enough information",
    "i do not have enough information",
    "not enough information",
    "insufficient information",
    "not explicitly stated",
    "cannot determine from the provided context",
    "can't determine from the provided context",
    "unable to answer from the provided context",
    "i don't know based on the provided context",
)
JOB_SEARCH_GROUNDING_TERMS = (
    "jay",
    "experience",
    "role",
    "interview",
    "impact",
    "business value",
    "career",
    "company",
    "fit",
)
JOB_SEARCH_GROUNDING_PREFIX = (
    "For Jay's interview and role preparation, anchor this in his experience, impact, "
    "business value, and company fit. "
)
UUID_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    flags=re.IGNORECASE,
)
HEX_IDENTIFIER_PATTERN = re.compile(r"^[a-f0-9]{16,}$", flags=re.IGNORECASE)
LIST_QUERY_PATTERN = re.compile(r"\b(list|bullet(?:ed)?|bullet-point|key points?|top \d+)\b", flags=re.IGNORECASE)
COMPARE_QUERY_PATTERN = re.compile(r"\b(compare|comparison|different|difference|versus|vs\.?)\b", flags=re.IGNORECASE)
STEPS_QUERY_PATTERN = re.compile(
    r"\b(how to|how can i|how do i|steps?|process|plan|improve|enhance|optimi[sz]e|fix|make this better)\b",
    flags=re.IGNORECASE,
)
EXPLANATION_QUERY_PATTERN = re.compile(
    r"\b(benefits?|advantages?|what are|what is|why|examples?|tradeoffs?|pros and cons|use cases?)\b",
    flags=re.IGNORECASE,
)
SENSITIVE_SECRET_QUERY_PATTERN = re.compile(
    r"\b(api key|apikey|password|secret|token|credential|private key|access key|client secret)\b",
    flags=re.IGNORECASE,
)
EXACT_SECRET_QUERY_PATTERN = re.compile(
    r"\b(exact|currently configured|configured|production|private|current)\b",
    flags=re.IGNORECASE,
)
SUMMARY_QUERY_PATTERN = re.compile(r"\b(summarize|summary|highlights|key takeaways|recap|overview)\b", flags=re.IGNORECASE)
DOCUMENT_REFERENCE_PATTERN = re.compile(r"\b(article|post|blog post|essay|paper|write-?up|document)\b", flags=re.IGNORECASE)
TARGETED_SOURCE_LOOKUP_PATTERN = re.compile(
    r"\b(according to|in the article|in the document|from the article|from the document|what does the article say|what does the document say)\b",
    flags=re.IGNORECASE,
)
QUOTED_TARGET_PATTERN = re.compile(r'["“”](.+?)["“”]')
SYNTHESIS_CONNECTOR_PATTERN = re.compile(r"\b(and|plus|along with)\b", flags=re.IGNORECASE)
RANKING_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "could",
    "different",
    "do",
    "does",
    "examples",
    "for",
    "from",
    "give",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "possible",
    "should",
    "than",
    "that",
    "the",
    "this",
    "to",
    "vs",
    "what",
    "when",
    "with",
}
SNIPPET_BOILERPLATE_PATTERNS = (
    "thursday am",
    "sent an invite",
    "this guide assumes",
    "if not, we highly suggest",
    "here are some specific examples and use cases",
)
DOCUMENT_SUMMARY_MAX_SELECTED_CHUNKS = 8
DOCUMENT_SUMMARY_MAX_CHARS_PER_CHUNK = 1200
DOCUMENT_SUMMARY_MAX_CONTEXT_CHARS = 9000
COMPARE_MAX_SELECTED_DOCS = 2
COMPARE_CHUNKS_PER_DOC = 2
COMPARE_MAX_CHARS_PER_CHUNK = 1000
COMPARE_MAX_CONTEXT_CHARS = 7800
EXPLANATORY_QA_MAX_SELECTED_DOCS = 4
EXPLANATORY_QA_CHUNKS_PER_DOC = 2
EXPLANATORY_QA_MAX_CHARS_PER_CHUNK = 1000
EXPLANATORY_QA_MAX_CONTEXT_CHARS = 8200
GENERAL_QA_MAX_SELECTED_DOCS = 3
GENERAL_QA_CHUNKS_PER_DOC = 2
GENERAL_QA_MAX_CHARS_PER_CHUNK = 850
GENERAL_QA_MAX_CONTEXT_CHARS = 6000


@dataclass
class RagSettings:
    db_path: Path
    artifacts_dir: Path
    prompt_path: Path
    compare_prompt_path: Path
    synthesis_prompt_path: Path
    explanatory_prompt_path: Path
    summary_prompt_path: Path
    retry_prompt_path: Path
    job_search_prompt_path: Path
    learning_prompt_path: Path
    top_k: int
    summary_top_k: int
    min_score: float
    max_retries: int
    temperature: float
    summary_max_tokens: int
    default_max_tokens: int


def load_settings() -> RagSettings:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    top_k = int(os.getenv("RECALL_RAG_TOP_K", "5"))
    summary_top_k = int(os.getenv("RECALL_RAG_SUMMARY_TOP_K", "20"))
    min_score = float(os.getenv("RECALL_RAG_MIN_SCORE", "0.2"))
    max_retries = int(os.getenv("RECALL_RAG_MAX_RETRIES", "1"))
    temperature = float(os.getenv("RECALL_RAG_TEMPERATURE", "0.2"))
    summary_max_tokens = int(os.getenv("RECALL_RAG_SUMMARY_MAX_TOKENS", "768"))
    default_max_tokens = int(os.getenv("RECALL_RAG_MAX_TOKENS", "384"))
    if top_k <= 0:
        raise ValueError("RECALL_RAG_TOP_K must be greater than 0")
    if summary_top_k <= 0:
        raise ValueError("RECALL_RAG_SUMMARY_TOP_K must be greater than 0")
    if max_retries < 0:
        raise ValueError("RECALL_RAG_MAX_RETRIES cannot be negative")
    if summary_max_tokens <= 0:
        raise ValueError("RECALL_RAG_SUMMARY_MAX_TOKENS must be greater than 0")
    if default_max_tokens <= 0:
        raise ValueError("RECALL_RAG_MAX_TOKENS must be greater than 0")

    artifacts_root = _safe_dir_from_env(
        env_var="DATA_ARTIFACTS",
        fallback=ROOT / "data" / "artifacts",
    )
    db_path = _safe_file_path_from_env(
        env_var="RECALL_DB_PATH",
        fallback=ROOT / "data" / "recall.db",
    )
    return RagSettings(
        db_path=db_path,
        artifacts_dir=artifacts_root / "rag",
        prompt_path=ROOT / "prompts" / "workflow_02_rag_answer.md",
        compare_prompt_path=ROOT / "prompts" / "workflow_02_compare_synthesis.md",
        synthesis_prompt_path=ROOT / "prompts" / "workflow_02_multi_document_synthesis.md",
        explanatory_prompt_path=ROOT / "prompts" / "workflow_02_explanatory_qa.md",
        summary_prompt_path=ROOT / "prompts" / "workflow_02_document_summary.md",
        retry_prompt_path=ROOT / "prompts" / "workflow_02_rag_answer_retry.md",
        job_search_prompt_path=ROOT / "prompts" / "job_search_coach.md",
        learning_prompt_path=ROOT / "prompts" / "learning_coach.md",
        top_k=top_k,
        summary_top_k=summary_top_k,
        min_score=min_score,
        max_retries=max_retries,
        temperature=temperature,
        summary_max_tokens=summary_max_tokens,
        default_max_tokens=default_max_tokens,
    )


def _safe_dir_from_env(*, env_var: str, fallback: Path) -> Path:
    raw = os.getenv(env_var, "").strip()
    candidate = Path(raw) if raw else fallback
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _safe_file_path_from_env(*, env_var: str, fallback: Path) -> Path:
    raw = os.getenv(env_var, "").strip()
    candidate = Path(raw) if raw else fallback
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def run_rag_query(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    max_retries: int | None = None,
    filter_tags: list[str] | None = None,
    filter_tag_mode: str | None = None,
    filter_group: str | None = None,
    mode: str | None = None,
    retrieval_mode: str | None = None,
    hybrid_alpha: float | None = None,
    enable_reranker: bool | None = None,
    reranker_weight: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = load_settings()
    limit = settings.top_k if top_k is None else top_k
    threshold = settings.min_score if min_score is None else min_score
    retries = settings.max_retries if max_retries is None else max_retries
    normalized_filter_tags = _normalize_filter_tags(filter_tags)
    normalized_filter_tag_mode = _normalize_filter_tag_mode(filter_tag_mode)
    normalized_filter_group = _normalize_filter_group(filter_group)
    query_strategy_hint = _query_strategy(question=query, retrieved=[])
    summary_hint = query_strategy_hint == "document_summary"
    compare_hint = query_strategy_hint == "compare_synthesis"
    explanatory_hint = query_strategy_hint == "explanatory_qa"
    active_mode = _resolve_mode(
        mode=mode,
        filter_tags=normalized_filter_tags,
        filter_group=normalized_filter_group,
    )
    if limit <= 0:
        raise ValueError("top_k must be greater than 0")
    if retries < 0:
        raise ValueError("max_retries cannot be negative")

    question = query.strip()
    if not question:
        raise ValueError("Query must be non-empty")

    started_at = _now_iso()
    started_perf = time.perf_counter()
    run_id = uuid.uuid4().hex

    conn: sqlite3.Connection | None = None
    if not dry_run:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        _insert_run_started(conn=conn, run_id=run_id, query=question, started_at=started_at)

    try:
        retrieval_limit = limit
        if summary_hint:
            retrieval_limit = max(limit, settings.summary_top_k)
        elif compare_hint or query_strategy_hint == "multi_document_synthesis":
            retrieval_limit = max(limit, min(settings.summary_top_k, 12))
        elif explanatory_hint:
            retrieval_limit = max(limit, min(settings.summary_top_k, 10))
        retrieved = _retrieve_for_query_strategy(
            question=question,
            query_strategy=query_strategy_hint,
            top_k=retrieval_limit,
            min_score=threshold,
            filter_tags=normalized_filter_tags,
            filter_tag_mode=normalized_filter_tag_mode,
            filter_group=normalized_filter_group,
            retrieval_mode=retrieval_mode,
            hybrid_alpha=hybrid_alpha,
            enable_reranker=enable_reranker,
            reranker_weight=reranker_weight,
        )
        fallback_reason: str | None = None
        if not retrieved:
            # Retry once with relaxed threshold to avoid hard failures on sparse / niche queries.
            retrieved = _retrieve_for_query_strategy(
                question=question,
                query_strategy=query_strategy_hint,
                top_k=retrieval_limit,
                min_score=-1.0,
                filter_tags=normalized_filter_tags,
                filter_tag_mode=normalized_filter_tag_mode,
                filter_group=normalized_filter_group,
                retrieval_mode=retrieval_mode,
                hybrid_alpha=hybrid_alpha,
                enable_reranker=enable_reranker,
                reranker_weight=reranker_weight,
            )
            if not retrieved:
                fallback_reason = "No retrieval results available for query."

        if fallback_reason is None:
            try:
                query_strategy = _query_strategy(question=question, retrieved=retrieved)
                response, attempts_used = _generate_validated_answer(
                    question=question,
                    retrieved=retrieved,
                    max_retries=retries,
                    temperature=settings.temperature,
                    max_tokens=_generation_max_tokens(
                        question=question,
                        mode=active_mode,
                        query_strategy=query_strategy,
                        settings=settings,
                    ),
                    prompt_path=settings.prompt_path,
                    compare_prompt_path=settings.compare_prompt_path,
                    synthesis_prompt_path=settings.synthesis_prompt_path,
                    explanatory_prompt_path=settings.explanatory_prompt_path,
                    summary_prompt_path=settings.summary_prompt_path,
                    job_search_prompt_path=settings.job_search_prompt_path,
                    learning_prompt_path=settings.learning_prompt_path,
                    retry_prompt_path=settings.retry_prompt_path,
                    mode=active_mode,
                    query_strategy=query_strategy,
                )
            except Exception as exc:  # noqa: BLE001
                fallback_reason = f"Validation/generation fallback: {exc}"
                response, attempts_used = _build_unanswerable_response(
                    question=question,
                    retrieved=retrieved,
                    reason=fallback_reason,
                )
        else:
            response, attempts_used = _build_unanswerable_response(
                question=question,
                retrieved=retrieved,
                reason=fallback_reason,
            )
        postprocess_reasons: list[str] = []
        consistency_reason = _normalize_unanswerable_consistency(response)
        if consistency_reason is not None:
            postprocess_reasons.append(consistency_reason)

        sensitive_reason = _normalize_sensitive_query_response(question=question, response=response)
        if sensitive_reason is not None:
            postprocess_reasons.append(sensitive_reason)

        normalization_reason = _normalize_low_confidence_response(response)
        if normalization_reason is not None:
            postprocess_reasons.append(normalization_reason)

        if postprocess_reasons:
            combined_reason = "; ".join(postprocess_reasons)
            fallback_reason = (
                combined_reason
                if fallback_reason is None
                else f"{fallback_reason}; {combined_reason}"
            )
        grounding_reason = (
            _ensure_job_search_grounding(response)
            if active_mode == "job-search"
            else None
        )
        if grounding_reason is not None:
            postprocess_notes = response["audit"].get("postprocess_notes")
            if not isinstance(postprocess_notes, list):
                postprocess_notes = []
            postprocess_notes.append(grounding_reason)
            response["audit"]["postprocess_notes"] = postprocess_notes

        latency_ms = int((time.perf_counter() - started_perf) * 1000)
        response["audit"]["run_id"] = run_id
        response["audit"]["timestamp"] = _now_iso()
        response["audit"]["workflow"] = "workflow_02_rag_query"
        response["audit"]["provider"] = os.getenv("RECALL_LLM_PROVIDER", "ollama")
        response["audit"]["model"] = _active_model_name(response["audit"]["provider"])
        response["audit"]["attempts"] = attempts_used
        response["audit"]["latency_ms"] = latency_ms
        response["audit"]["top_k"] = limit
        response["audit"]["min_score"] = threshold
        response["audit"]["filter_tags"] = normalized_filter_tags
        response["audit"]["filter_tag_mode"] = normalized_filter_tag_mode
        response["audit"]["filter_group"] = normalized_filter_group
        response["audit"]["mode"] = active_mode
        query_strategy = _query_strategy(question=question, retrieved=retrieved)
        response["audit"]["query_strategy"] = query_strategy
        response["audit"]["prompt_profile"] = _prompt_profile_name(active_mode, query_strategy=query_strategy)
        response["audit"]["retrieval_mode"] = retrieval_mode or os.getenv("RECALL_RAG_RETRIEVAL_MODE", "vector")
        response["audit"]["hybrid_alpha"] = (
            float(hybrid_alpha)
            if hybrid_alpha is not None
            else _env_float("RECALL_RAG_HYBRID_ALPHA", 0.65)
        )
        response["audit"]["reranker_enabled"] = (
            bool(enable_reranker)
            if enable_reranker is not None
            else _env_bool("RECALL_RAG_ENABLE_RERANK", False)
        )
        response["audit"]["reranker_weight"] = (
            float(reranker_weight)
            if reranker_weight is not None
            else _env_float("RECALL_RAG_RERANK_WEIGHT", 0.35)
        )
        response["audit"]["retrieved_count"] = len(retrieved)
        response["audit"]["dry_run"] = dry_run
        if fallback_reason is not None or bool(response["audit"].get("fallback_used")):
            response["audit"]["fallback_used"] = True
            if fallback_reason is not None:
                response["audit"]["fallback_reason"] = fallback_reason
            elif "fallback_reason" not in response["audit"]:
                response["audit"]["fallback_reason"] = "Unspecified fallback path used."
        else:
            response["audit"]["fallback_used"] = False

        artifact_path: str | None = None
        if not dry_run:
            artifact_path = _write_artifact(settings=settings, run_id=run_id, payload=response)
            _mark_run_completed(
                conn=conn,
                run_id=run_id,
                ended_at=_now_iso(),
                latency_ms=latency_ms,
                model=response["audit"]["model"],
                output_path=artifact_path,
            )
            response["audit"]["artifact_path"] = artifact_path

        return response
    except Exception:
        if conn is not None:
            _mark_run_failed(
                conn=conn,
                run_id=run_id,
                ended_at=_now_iso(),
                latency_ms=int((time.perf_counter() - started_perf) * 1000),
            )
        raise
    finally:
        if conn is not None:
            conn.close()


def _generate_validated_answer(
    *,
    question: str,
    retrieved: list[RetrievedChunk],
    max_retries: int,
    temperature: float,
    max_tokens: int,
    prompt_path: Path,
    compare_prompt_path: Path,
    synthesis_prompt_path: Path,
    explanatory_prompt_path: Path,
    summary_prompt_path: Path,
    job_search_prompt_path: Path,
    learning_prompt_path: Path,
    retry_prompt_path: Path,
    mode: str,
    query_strategy: str,
) -> tuple[dict[str, Any], int]:
    selected_chunks = _select_generation_chunks(
        question=question,
        retrieved=retrieved,
        query_strategy=query_strategy,
    )
    allowed_pairs = {(item.doc_id, item.chunk_id) for item in selected_chunks}
    context = _build_context(selected_chunks, query_strategy=query_strategy)
    validation_requirements = _validation_requirements(
        selected_chunks=selected_chunks,
        query_strategy=query_strategy,
        query=question,
        mode=mode,
    )

    if query_strategy == "document_summary":
        selected_primary_prompt = summary_prompt_path
    elif query_strategy == "compare_synthesis":
        selected_primary_prompt = compare_prompt_path
    elif query_strategy == "multi_document_synthesis":
        selected_primary_prompt = synthesis_prompt_path
    elif query_strategy == "explanatory_qa":
        selected_primary_prompt = explanatory_prompt_path
    elif mode == "job-search":
        selected_primary_prompt = job_search_prompt_path
    elif mode == "learning":
        selected_primary_prompt = learning_prompt_path
    else:
        selected_primary_prompt = prompt_path
    primary_template = _load_prompt(
        selected_primary_prompt,
        fallback=(
            "Answer the question using only the provided context. Return strict JSON with "
            "answer, citations[], confidence_level, assumptions[] and no markdown."
        ),
    )
    retry_template = _load_prompt(
        retry_prompt_path,
        fallback=(
            "Your previous answer failed validation. Return strict JSON only. "
            "Do not cite anything outside the provided context."
        ),
    )

    previous_response = ""
    previous_errors: list[str] = []
    validation: ValidationResult | None = None
    attempts_used = 0
    answer_style_instructions = _infer_answer_style_instructions(
        query=question,
        mode=mode,
        query_strategy=query_strategy,
    )

    for attempt in range(max_retries + 1):
        attempts_used = attempt + 1
        is_retry = attempt > 0
        template = retry_template if is_retry else primary_template
        prompt = _render_prompt(
            template=template,
            query=question,
            context=context,
            previous_response=previous_response,
            validation_errors=previous_errors,
            answer_style_instructions=answer_style_instructions,
        )

        raw_response = llm_client.generate(
            prompt=prompt,
            temperature=0.1 if is_retry else temperature,
            max_tokens=max_tokens,
            trace_metadata={
                "workflow": "workflow_02_rag_query",
                "mode": mode,
                "query_strategy": query_strategy,
                "prompt_profile": _prompt_profile_name(mode, query_strategy=query_strategy),
                "is_retry": is_retry,
            },
        )
        validation = validate_rag_output(
            raw_response,
            valid_citation_pairs=allowed_pairs,
            min_citation_count=validation_requirements["min_citation_count"],
            min_distinct_doc_count=validation_requirements["min_distinct_doc_count"],
            min_bullet_count=validation_requirements["min_bullet_count"],
            min_answer_chars=validation_requirements["min_answer_chars"],
        )
        if validation.valid:
            break

        previous_response = raw_response
        previous_errors = validation.errors

    if validation is None or not validation.valid or not validation.parsed_response:
        if query_strategy == "document_summary":
            summary_fallback = _build_document_summary_fallback_response(
                question=question,
                selected_chunks=selected_chunks,
                reason="; ".join(validation.errors if validation else ["unknown validation failure"]),
            )
            if summary_fallback is not None:
                return summary_fallback, attempts_used
        if query_strategy == "named_source_lookup":
            source_lookup_fallback = _build_named_source_lookup_fallback_response(
                question=question,
                selected_chunks=selected_chunks,
                reason="; ".join(validation.errors if validation else ["unknown validation failure"]),
            )
            if source_lookup_fallback is not None:
                return source_lookup_fallback, attempts_used
        if query_strategy in {"compare_synthesis", "multi_document_synthesis"}:
            compare_fallback = _build_compare_fallback_response(
                question=question,
                selected_chunks=selected_chunks,
                reason="; ".join(validation.errors if validation else ["unknown validation failure"]),
            )
            if compare_fallback is not None:
                return compare_fallback, attempts_used
        if query_strategy == "explanatory_qa":
            explanatory_fallback = _build_explanatory_fallback_response(
                question=question,
                selected_chunks=selected_chunks,
                reason="; ".join(validation.errors if validation else ["unknown validation failure"]),
                parsed_answer=str((validation.parsed_response or {}).get("answer", "")) if validation else "",
            )
            if explanatory_fallback is not None:
                return explanatory_fallback, attempts_used
        general_fallback = _build_general_qa_fallback_response(
            question=question,
            selected_chunks=selected_chunks,
            reason="; ".join(validation.errors if validation else ["unknown validation failure"]),
            mode=mode,
            parsed_answer=str((validation.parsed_response or {}).get("answer", "")) if validation else "",
        )
        if general_fallback is not None:
            return general_fallback, attempts_used
        error_suffix = "; ".join(validation.errors if validation else ["unknown validation failure"])
        response, _ = _build_unanswerable_response(
            question=question,
            retrieved=retrieved,
            reason=f"RAG output validation failed: {error_suffix}",
        )
        return response, attempts_used

    parsed = validation.parsed_response
    return {
        "answer": str(parsed.get("answer", "")).strip(),
        "citations": parsed.get("citations", []),
        "confidence_level": parsed.get("confidence_level", "unspecified"),
        "assumptions": parsed.get("assumptions", []),
        "sources": _source_rows(selected_chunks),
        "audit": {},
    }, attempts_used


def _build_unanswerable_response(
    *,
    question: str,
    retrieved: list[RetrievedChunk],
    reason: str,
) -> tuple[dict[str, Any], int]:
    citations: list[dict[str, str]] = []
    if retrieved:
        primary = retrieved[0]
        citations.append({"doc_id": primary.doc_id, "chunk_id": primary.chunk_id})

    assumptions = [
        "The retrieved context does not provide enough evidence to answer the request reliably.",
        f"Fallback reason: {reason}",
    ]

    return (
        {
            "answer": UNANSWERABLE_ANSWER,
            "citations": citations,
            "confidence_level": "low",
            "assumptions": assumptions,
            "sources": _source_rows(retrieved),
            "audit": {
                "fallback_used": True,
                "fallback_reason": reason,
            },
        },
        1,
    )


def _generation_max_tokens(
    *,
    question: str,
    mode: str,
    query_strategy: str,
    settings: RagSettings,
) -> int:
    if query_strategy in {
        "document_summary",
        "named_source_lookup",
        "compare_synthesis",
        "multi_document_synthesis",
        "explanatory_qa",
    }:
        return settings.summary_max_tokens
    if _requires_structured_general_answer(query=question, mode=mode):
        return settings.summary_max_tokens
    return settings.default_max_tokens


def _build_compare_fallback_response(
    *,
    question: str,
    selected_chunks: list[RetrievedChunk],
    reason: str,
) -> dict[str, Any] | None:
    grouped = _group_chunks_by_doc_id(selected_chunks)
    if len(grouped) < 2:
        return None

    ordered_doc_ids: list[str] = []
    for chunk in selected_chunks:
        if chunk.doc_id not in ordered_doc_ids:
            ordered_doc_ids.append(chunk.doc_id)
        if len(ordered_doc_ids) == 2:
            break
    if len(ordered_doc_ids) < 2:
        return None

    primary_chunks = grouped[ordered_doc_ids[0]]
    secondary_chunks = grouped[ordered_doc_ids[1]]
    primary = primary_chunks[0]
    secondary = secondary_chunks[0]
    additional = primary_chunks[1] if len(primary_chunks) > 1 else (secondary_chunks[1] if len(secondary_chunks) > 1 else None)

    answer_lines = [
        _compare_intro_sentence(question=question, primary=primary, secondary=secondary),
        f"- {_compare_focus_label(chunk=primary, question=question)}: {_supporting_snippet(primary.text, question=question)}",
        f"- {_compare_focus_label(chunk=secondary, question=question)}: {_supporting_snippet(secondary.text, question=question)}",
    ]
    if additional is not None:
        answer_lines.append(
            f"- Additional evidence: {_supporting_snippet(additional.text, question=question)}"
        )
    answer_lines.append(
        f"- Practical tradeoff: rely on {_topic_hint(primary.title)} guidance when the problem is mostly about {_topic_hint(primary.title)}, "
        f"and shift toward {_topic_hint(secondary.title)} guidance when the bottleneck is really about {_topic_hint(secondary.title)}."
    )

    citations = [
        {"doc_id": primary.doc_id, "chunk_id": primary.chunk_id},
        {"doc_id": secondary.doc_id, "chunk_id": secondary.chunk_id},
    ]
    if additional is not None and additional.doc_id not in {primary.doc_id, secondary.doc_id}:
        citations.append({"doc_id": additional.doc_id, "chunk_id": additional.chunk_id})

    return {
        "answer": "\n".join(answer_lines),
        "citations": citations,
        "confidence_level": "low",
        "assumptions": [
            "Returned an extractive comparison fallback because the model could not produce a valid structured compare answer.",
            f"Fallback reason: {reason}",
        ],
        "sources": _source_rows(_dedupe_chunks(primary_chunks + secondary_chunks)),
        "audit": {
            "fallback_used": True,
            "fallback_reason": f"Compare synthesis fallback used after validation failure: {reason}",
        },
    }


def _build_named_source_lookup_fallback_response(
    *,
    question: str,
    selected_chunks: list[RetrievedChunk],
    reason: str,
) -> dict[str, Any] | None:
    if not selected_chunks:
        return None

    primary_doc_id = selected_chunks[0].doc_id
    primary_chunks = [chunk for chunk in selected_chunks if chunk.doc_id == primary_doc_id]
    if not primary_chunks:
        return None

    primary = primary_chunks[0]
    snippet = _supporting_snippet(primary.text, question=question, max_chars=240)
    answer = _named_source_lookup_answer(question=question, title=primary.title, snippet=snippet)
    citations = [{"doc_id": primary.doc_id, "chunk_id": primary.chunk_id}]
    if len(primary_chunks) > 1:
        citations.append({"doc_id": primary_chunks[1].doc_id, "chunk_id": primary_chunks[1].chunk_id})

    return {
        "answer": answer,
        "citations": citations,
        "confidence_level": "low",
        "assumptions": [
            "Returned a direct named-source lookup fallback because the model could not produce a valid structured answer.",
            f"Fallback reason: {reason}",
        ],
        "sources": _source_rows(primary_chunks),
        "audit": {
            "fallback_used": True,
            "fallback_reason": f"Named source lookup fallback used after validation failure: {reason}",
        },
    }


def _build_explanatory_fallback_response(
    *,
    question: str,
    selected_chunks: list[RetrievedChunk],
    reason: str,
    parsed_answer: str = "",
) -> dict[str, Any] | None:
    if not selected_chunks:
        return None

    intro = _general_qa_intro(question=question, parsed_answer=parsed_answer)
    answer_lines = [intro]
    citations: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_labels: set[str] = set()
    seen_bullets: set[str] = set()

    for chunk in selected_chunks:
        pair = (chunk.doc_id, chunk.chunk_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        snippet = _supporting_snippet(chunk.text, question=question, max_chars=220)
        bullet = _explanatory_fallback_bullet(question=question, snippet=snippet, title=chunk.title)
        bullet_key = bullet.lower().strip()
        label = _general_qa_bullet_label(bullet)
        if bullet_key in seen_bullets:
            continue
        if label and label in seen_labels:
            bullet = _explanatory_fallback_bullet(
                question="",
                snippet=snippet,
                title=chunk.title,
            )
            bullet_key = bullet.lower().strip()
            label = _general_qa_bullet_label(bullet)
            if bullet_key in seen_bullets:
                continue
        seen_bullets.add(bullet_key)
        if label:
            seen_labels.add(label)
        answer_lines.append(bullet)
        citations.append({"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id})
        if len(citations) >= 5:
            break

    if len(citations) < 4:
        return None

    return {
        "answer": "\n".join(answer_lines),
        "citations": citations,
        "confidence_level": "low",
        "assumptions": [
            "Returned a synthesized explanatory fallback because the model could not produce a valid structured explanation.",
            f"Fallback reason: {reason}",
        ],
        "sources": _source_rows(selected_chunks),
        "audit": {
            "fallback_used": True,
            "fallback_reason": f"Explanatory QA fallback used after validation failure: {reason}",
        },
    }


def _build_document_summary_fallback_response(
    *,
    question: str,
    selected_chunks: list[RetrievedChunk],
    reason: str,
) -> dict[str, Any] | None:
    if not selected_chunks:
        return None

    primary_doc_id = selected_chunks[0].doc_id
    primary_chunks = [chunk for chunk in selected_chunks if chunk.doc_id == primary_doc_id]
    if not primary_chunks:
        return None

    title = primary_chunks[0].title
    answer_lines = [
        _document_summary_intro(title=title, question=question),
    ]
    citations: list[dict[str, str]] = []
    for chunk in primary_chunks[:4]:
        answer_lines.append(f"- {_supporting_snippet(chunk.text, question=question)}")
        citations.append({"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id})

    return {
        "answer": "\n".join(answer_lines),
        "citations": citations,
        "confidence_level": "low",
        "assumptions": [
            "Returned an extractive summary fallback because the model could not produce a valid structured summary.",
            f"Fallback reason: {reason}",
        ],
        "sources": _source_rows(primary_chunks),
        "audit": {
            "fallback_used": True,
            "fallback_reason": f"Document summary fallback used after validation failure: {reason}",
        },
    }


def _build_general_qa_fallback_response(
    *,
    question: str,
    selected_chunks: list[RetrievedChunk],
    reason: str,
    mode: str,
    parsed_answer: str = "",
) -> dict[str, Any] | None:
    if not selected_chunks:
        return None
    if not _requires_structured_general_answer(query=question, mode=mode):
        return None

    intro = _general_qa_intro(question=question, parsed_answer=parsed_answer)
    answer_lines = [intro]
    citations: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    seen_bullets: set[str] = set()
    seen_labels: set[str] = set()

    for chunk in selected_chunks[:4]:
        pair = (chunk.doc_id, chunk.chunk_id)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        snippet = _supporting_snippet(chunk.text, question=question)
        bullet = _general_qa_bullet(question=question, snippet=snippet)
        bullet_key = bullet.lower().strip()
        if bullet_key in seen_bullets:
            continue
        bullet_label = _general_qa_bullet_label(bullet)
        if bullet_label and bullet_label in seen_labels:
            continue
        seen_bullets.add(bullet_key)
        if bullet_label:
            seen_labels.add(bullet_label)
        answer_lines.append(bullet)
        citations.append({"doc_id": chunk.doc_id, "chunk_id": chunk.chunk_id})

    if len(answer_lines) < 4:
        return None

    return {
        "answer": "\n".join(answer_lines),
        "citations": citations,
        "confidence_level": "low",
        "assumptions": [
            "Returned an extractive general-answer fallback because the model could not produce a valid structured answer.",
            f"Fallback reason: {reason}",
        ],
        "sources": _source_rows(selected_chunks),
        "audit": {
            "fallback_used": True,
            "fallback_reason": f"General QA fallback used after validation failure: {reason}",
        },
    }


def _normalize_low_confidence_response(response: dict[str, Any]) -> str | None:
    confidence_level = str(response.get("confidence_level", "")).strip().lower()
    if confidence_level != "low":
        return None

    answer = str(response.get("answer", "")).strip()
    if _has_unanswerable_phrase(answer):
        return None

    _ensure_citation_from_sources(response)
    citations = response.get("citations")
    has_citations = isinstance(citations, list) and len(citations) > 0

    if has_citations and _is_substantive_answer(answer):
        assumptions = response.get("assumptions")
        if not isinstance(assumptions, list):
            assumptions = []
            response["assumptions"] = assumptions
        retained_assumption = (
            "Answer retained despite low confidence because cited context contains partial supporting evidence."
        )
        if retained_assumption not in assumptions:
            assumptions.append(retained_assumption)
        return None

    response["answer"] = UNANSWERABLE_ANSWER
    assumptions = response.get("assumptions")
    if not isinstance(assumptions, list):
        assumptions = []
        response["assumptions"] = assumptions
    safety_assumption = (
        "Low-confidence response was normalized to an explicit abstention to avoid unsupported claims."
    )
    if safety_assumption not in assumptions:
        assumptions.append(safety_assumption)
    return "Low-confidence response was normalized to an explicit abstention."


def _normalize_unanswerable_consistency(response: dict[str, Any]) -> str | None:
    answer = str(response.get("answer", "")).strip()
    confidence_level = str(response.get("confidence_level", "")).strip().lower()
    reasons: list[str] = []

    if _looks_like_internal_identifier_answer(answer=answer, response=response):
        response["answer"] = UNANSWERABLE_ANSWER
        response["confidence_level"] = "low"
        reasons.append("Identifier-like answer was normalized to explicit abstention.")

    if _has_unanswerable_phrase(str(response.get("answer", ""))) and confidence_level != "low":
        response["confidence_level"] = "low"
        reasons.append("Unanswerable phrasing forced confidence_level=low.")

    return "; ".join(reasons) if reasons else None


def _normalize_sensitive_query_response(*, question: str, response: dict[str, Any]) -> str | None:
    if not _is_sensitive_secret_query(question):
        return None
    answer = str(response.get("answer", "")).strip()
    if _has_unanswerable_phrase(answer):
        if str(response.get("confidence_level", "")).strip().lower() != "low":
            response["confidence_level"] = "low"
            return "Sensitive query forced confidence_level=low."
        return None

    response["answer"] = UNANSWERABLE_ANSWER
    response["confidence_level"] = "low"
    assumptions = response.get("assumptions")
    if not isinstance(assumptions, list):
        assumptions = []
        response["assumptions"] = assumptions
    note = "Sensitive secret-seeking query was normalized to explicit abstention."
    if note not in assumptions:
        assumptions.append(note)
    return note


def _looks_like_internal_identifier_answer(*, answer: str, response: dict[str, Any]) -> bool:
    token = answer.strip()
    if not token:
        return False

    if " " in token:
        return False

    source_ids = set()
    citations = response.get("citations")
    if isinstance(citations, list):
        for citation in citations:
            if isinstance(citation, dict):
                doc_id = str(citation.get("doc_id", "")).strip()
                chunk_id = str(citation.get("chunk_id", "")).strip()
                if doc_id:
                    source_ids.add(doc_id)
                if chunk_id:
                    source_ids.add(chunk_id)

    sources = response.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict):
                doc_id = str(source.get("doc_id", "")).strip()
                chunk_id = str(source.get("chunk_id", "")).strip()
                if doc_id:
                    source_ids.add(doc_id)
                if chunk_id:
                    source_ids.add(chunk_id)

    if token in source_ids:
        return True
    if UUID_PATTERN.fullmatch(token):
        return True
    return bool(HEX_IDENTIFIER_PATTERN.fullmatch(token))


def _ensure_job_search_grounding(response: dict[str, Any]) -> str | None:
    answer = str(response.get("answer", "")).strip()
    if not answer:
        return None

    normalized_answer = answer.lower()
    if any(term in normalized_answer for term in JOB_SEARCH_GROUNDING_TERMS):
        return None

    response["answer"] = f"{JOB_SEARCH_GROUNDING_PREFIX}{answer}".strip()
    return "Injected deterministic grounding language for job-search mode."


def _ensure_citation_from_sources(response: dict[str, Any]) -> None:
    citations = response.get("citations")
    if isinstance(citations, list) and citations:
        return

    sources = response.get("sources")
    if not isinstance(sources, list) or not sources:
        if not isinstance(citations, list):
            response["citations"] = []
        return

    first_source = sources[0] if isinstance(sources[0], dict) else {}
    doc_id = str(first_source.get("doc_id", "")).strip()
    chunk_id = str(first_source.get("chunk_id", "")).strip()
    if doc_id and chunk_id:
        response["citations"] = [{"doc_id": doc_id, "chunk_id": chunk_id}]
    elif not isinstance(citations, list):
        response["citations"] = []


def _has_unanswerable_phrase(answer: str) -> bool:
    normalized = " ".join(answer.lower().split())
    return any(pattern in normalized for pattern in UNANSWERABLE_PATTERNS)


def _is_substantive_answer(answer: str) -> bool:
    normalized = " ".join(str(answer or "").split())
    if len(normalized) < 80:
        return False
    alpha_count = sum(1 for char in normalized if char.isalpha())
    return alpha_count >= 40


def _source_rows(retrieved: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": item.doc_id,
            "chunk_id": item.chunk_id,
            "title": item.title,
            "source": item.source,
            "source_type": item.source_type,
            "ingestion_channel": item.ingestion_channel,
            "group": item.group,
            "tags": item.tags,
            "score": round(item.score, 6),
            "excerpt": _truncate(item.text, 220),
        }
        for item in retrieved
    ]


def _retrieve_for_query_strategy(
    *,
    question: str,
    query_strategy: str,
    top_k: int,
    min_score: float,
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
    retrieval_mode: str | None,
    hybrid_alpha: float | None,
    enable_reranker: bool | None,
    reranker_weight: float | None,
) -> list[RetrievedChunk]:
    if query_strategy != "multi_document_synthesis":
        return retrieve_chunks(
            question,
            top_k=top_k,
            min_score=min_score,
            filter_tags=filter_tags,
            filter_tag_mode=filter_tag_mode,
            filter_group=filter_group,
            retrieval_mode=retrieval_mode,
            hybrid_alpha=hybrid_alpha,
            enable_reranker=enable_reranker,
            reranker_weight=reranker_weight,
        )

    merged: list[RetrievedChunk] = []
    per_query_results: list[list[RetrievedChunk]] = []
    for subquery in _synthesis_subqueries(question):
        subquery_chunks = retrieve_chunks(
                subquery,
                top_k=max(24, top_k * 4),
                min_score=min(min_score, 0.05),
                filter_tags=filter_tags,
                filter_tag_mode=filter_tag_mode,
                filter_group=filter_group,
                retrieval_mode=retrieval_mode,
                hybrid_alpha=hybrid_alpha,
                enable_reranker=enable_reranker,
                reranker_weight=reranker_weight,
            )
        per_query_results.append(
            _prioritize_chunks_for_subquery(subquery_chunks, query=subquery)
        )
    per_query_results.append(
        retrieve_chunks(
            question,
            top_k=top_k,
            min_score=min_score,
            filter_tags=filter_tags,
            filter_tag_mode=filter_tag_mode,
            filter_group=filter_group,
            retrieval_mode=retrieval_mode,
            hybrid_alpha=hybrid_alpha,
            enable_reranker=enable_reranker,
            reranker_weight=reranker_weight,
        )
    )
    merged = _interleave_retrieved_query_results(per_query_results)
    return _dedupe_retrieved_chunks_preserve_order(merged)[:top_k]


def _synthesis_subqueries(question: str) -> list[str]:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return []

    parts = re.split(r",\s*|\band\b", normalized, flags=re.IGNORECASE)
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        candidate = part.strip(" ,.?")
        if len(candidate.split()) < 4:
            continue
        normalized_candidate = candidate.lower()
        if normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        cleaned.append(candidate)
    return cleaned or [normalized]


def _merge_retrieved_chunks(chunks: list[RetrievedChunk], *, limit: int) -> list[RetrievedChunk]:
    best_by_key: dict[tuple[str, str], RetrievedChunk] = {}
    for chunk in chunks:
        key = (chunk.doc_id, chunk.chunk_id)
        existing = best_by_key.get(key)
        if existing is None or chunk.score > existing.score:
            best_by_key[key] = chunk
    merged = sorted(
        best_by_key.values(),
        key=lambda item: (
            item.score,
            item.title_match_score if item.title_match_score is not None else 0.0,
            -(item.chunk_index if item.chunk_index is not None else 999999),
        ),
        reverse=True,
    )
    return merged[:limit]


def _interleave_retrieved_query_results(per_query_results: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
    merged: list[RetrievedChunk] = []
    max_depth = max((len(items) for items in per_query_results), default=0)
    for depth in range(max_depth):
        for items in per_query_results:
            if depth < len(items):
                merged.append(items[depth])
    return merged


def _dedupe_retrieved_chunks_preserve_order(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    deduped: list[RetrievedChunk] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        key = (chunk.doc_id, chunk.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped


def _prioritize_chunks_for_subquery(chunks: list[RetrievedChunk], *, query: str) -> list[RetrievedChunk]:
    query_tokens = _ranking_query_tokens(query)
    return sorted(
        chunks,
        key=lambda item: (
            _chunk_title_source_overlap(item, query_tokens=query_tokens),
            item.score,
            item.title_match_score if item.title_match_score is not None else 0.0,
        ),
        reverse=True,
    )


def _chunk_title_source_overlap(chunk: RetrievedChunk, *, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    title_source_tokens = set(re.findall(r"[a-z0-9]+", chunk.title.lower()))
    title_source_tokens.update(re.findall(r"[a-z0-9]+", chunk.source.lower()))
    for tag in chunk.tags:
        title_source_tokens.update(re.findall(r"[a-z0-9]+", tag.lower()))
    return len(query_tokens.intersection(title_source_tokens)) / len(query_tokens)


def _select_generation_chunks(
    *,
    question: str,
    retrieved: list[RetrievedChunk],
    query_strategy: str,
) -> list[RetrievedChunk]:
    if not retrieved:
        return []

    grouped = _group_chunks_by_doc_id(retrieved)
    ranked_docs = _ranked_doc_ids(
        question=question,
        grouped=grouped,
        query_strategy=query_strategy,
    )

    if query_strategy == "document_summary":
        primary_doc_id = ranked_docs[0]
        return _sample_document_chunks(
            grouped[primary_doc_id],
            max_chunks=DOCUMENT_SUMMARY_MAX_SELECTED_CHUNKS,
        )

    if query_strategy == "named_source_lookup":
        primary_doc_id = ranked_docs[0]
        return _pick_evidence_chunks(
            grouped[primary_doc_id],
            max_chunks=min(4, len(grouped[primary_doc_id])),
        )

    if query_strategy in {"compare_synthesis", "multi_document_synthesis"}:
        target_doc_ids = ranked_docs[:COMPARE_MAX_SELECTED_DOCS]
        if len(target_doc_ids) < 2 and len(grouped) >= 2:
            target_doc_ids = list(grouped.keys())[:2]
        per_doc_selected = [
            _pick_evidence_chunks(
                grouped[doc_id],
                max_chunks=COMPARE_CHUNKS_PER_DOC,
            )
            for doc_id in target_doc_ids
        ]
        selected: list[RetrievedChunk] = []
        max_depth = max((len(items) for items in per_doc_selected), default=0)
        for depth in range(max_depth):
            for items in per_doc_selected:
                if depth < len(items):
                    selected.append(items[depth])
        return _dedupe_chunks(selected)

    if query_strategy == "explanatory_qa":
        selected = []
        for doc_id in ranked_docs[:EXPLANATORY_QA_MAX_SELECTED_DOCS]:
            selected.extend(
                _pick_evidence_chunks(
                    grouped[doc_id],
                    max_chunks=EXPLANATORY_QA_CHUNKS_PER_DOC,
                )
            )
        return _dedupe_chunks(selected)

    selected = []
    for doc_id in ranked_docs[:GENERAL_QA_MAX_SELECTED_DOCS]:
        selected.extend(
            _pick_evidence_chunks(
                grouped[doc_id],
                max_chunks=GENERAL_QA_CHUNKS_PER_DOC,
            )
        )
    return _dedupe_chunks(selected)


def _group_chunks_by_doc_id(retrieved: list[RetrievedChunk]) -> dict[str, list[RetrievedChunk]]:
    grouped: dict[str, list[RetrievedChunk]] = {}
    for chunk in retrieved:
        grouped.setdefault(chunk.doc_id, []).append(chunk)
    for doc_id, chunks in grouped.items():
        grouped[doc_id] = sorted(
            chunks,
            key=lambda item: (
                item.chunk_index if item.chunk_index is not None else 999999,
                -item.score,
            ),
        )
    return grouped


def _ranked_doc_ids(
    *,
    question: str,
    grouped: dict[str, list[RetrievedChunk]],
    query_strategy: str,
) -> list[str]:
    title_hints = [
        " ".join(match.strip().split()).lower()
        for match in QUOTED_TARGET_PATTERN.findall(question)
        if match.strip()
    ]
    query_tokens = _ranking_query_tokens(question)

    def _doc_rank(doc_id: str) -> tuple[float, float, float, float]:
        chunks = grouped[doc_id]
        title_bonus = 0.0
        if title_hints:
            for hint in title_hints:
                for chunk in chunks:
                    title = " ".join(chunk.title.lower().split())
                    source = " ".join(chunk.source.lower().split())
                    if hint and (hint in title or hint in source):
                        title_bonus = max(title_bonus, 2.0)
                        break
        lexical_bonus = (
            _title_source_query_overlap(chunks, query_tokens=query_tokens)
            if query_strategy in {"compare_synthesis", "multi_document_synthesis", "explanatory_qa"}
            else 0.0
        )
        best_title_match = max((chunk.title_match_score or 0.0) for chunk in chunks)
        total_score = sum(chunk.score for chunk in chunks)
        best_score = max(chunk.score for chunk in chunks)
        coverage = float(len(chunks))
        return (title_bonus + best_title_match + lexical_bonus, total_score, best_score, coverage)

    return sorted(grouped, key=_doc_rank, reverse=True)


def _ranking_query_tokens(question: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", question.lower())
        if token not in RANKING_STOPWORDS and len(token) > 2
    }


def _title_source_query_overlap(chunks: list[RetrievedChunk], *, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    title_source_tokens: set[str] = set()
    for chunk in chunks:
        title_source_tokens.update(re.findall(r"[a-z0-9]+", chunk.title.lower()))
        title_source_tokens.update(re.findall(r"[a-z0-9]+", chunk.source.lower()))
    overlap = len(query_tokens.intersection(title_source_tokens))
    return overlap / len(query_tokens)


def _sample_document_chunks(chunks: list[RetrievedChunk], *, max_chunks: int) -> list[RetrievedChunk]:
    ordered = sorted(
        chunks,
        key=lambda item: item.chunk_index if item.chunk_index is not None else 999999,
    )
    if len(ordered) <= max_chunks:
        return ordered
    if max_chunks <= 1:
        return [ordered[0]]

    chosen_indexes = {
        round((len(ordered) - 1) * position / (max_chunks - 1))
        for position in range(max_chunks)
    }
    selected = [ordered[index] for index in sorted(chosen_indexes)]
    if len(selected) == max_chunks:
        return selected

    for chunk in ordered:
        if chunk in selected:
            continue
        selected.append(chunk)
        if len(selected) == max_chunks:
            break
    return sorted(
        selected,
        key=lambda item: item.chunk_index if item.chunk_index is not None else 999999,
    )


def _pick_evidence_chunks(chunks: list[RetrievedChunk], *, max_chunks: int) -> list[RetrievedChunk]:
    ranked = sorted(
        chunks,
        key=lambda item: (
            item.score,
            item.title_match_score if item.title_match_score is not None else 0.0,
            -(item.chunk_index if item.chunk_index is not None else 999999),
        ),
        reverse=True,
    )
    selected = ranked[:max_chunks]
    return sorted(
        selected,
        key=lambda item: item.chunk_index if item.chunk_index is not None else 999999,
    )


def _dedupe_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    deduped: list[RetrievedChunk] = []
    seen: set[tuple[str, str]] = set()
    for chunk in chunks:
        key = (chunk.doc_id, chunk.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped


def _context_budget(query_strategy: str) -> tuple[int, int]:
    if query_strategy in {"document_summary", "named_source_lookup"}:
        return DOCUMENT_SUMMARY_MAX_CHARS_PER_CHUNK, DOCUMENT_SUMMARY_MAX_CONTEXT_CHARS
    if query_strategy == "compare_synthesis":
        return COMPARE_MAX_CHARS_PER_CHUNK, COMPARE_MAX_CONTEXT_CHARS
    if query_strategy == "explanatory_qa":
        return EXPLANATORY_QA_MAX_CHARS_PER_CHUNK, EXPLANATORY_QA_MAX_CONTEXT_CHARS
    return GENERAL_QA_MAX_CHARS_PER_CHUNK, GENERAL_QA_MAX_CONTEXT_CHARS


def _validation_requirements(
    *,
    selected_chunks: list[RetrievedChunk],
    query_strategy: str,
    query: str,
    mode: str,
) -> dict[str, int | None]:
    distinct_docs = {item.doc_id for item in selected_chunks}
    min_citation_count = None
    min_distinct_doc_count = None
    min_bullet_count = None
    min_answer_chars = None

    if query_strategy == "document_summary":
        min_bullet_count = 4
        min_answer_chars = 320
        if len(selected_chunks) >= 2:
            min_citation_count = 2
    elif query_strategy == "named_source_lookup":
        min_answer_chars = 160
        if selected_chunks:
            min_citation_count = 1
    elif query_strategy == "explanatory_qa":
        min_bullet_count = 4
        min_answer_chars = 320
        if len(selected_chunks) >= 2:
            min_citation_count = 2
        if len(distinct_docs) >= 2:
            min_distinct_doc_count = 2
    elif query_strategy in {"compare_synthesis", "multi_document_synthesis"}:
        min_bullet_count = 4
        min_answer_chars = 320
        if len(selected_chunks) >= 2:
            min_citation_count = 2
        if len(distinct_docs) >= 2:
            min_distinct_doc_count = 2
    elif _requires_structured_general_answer(query=query, mode=mode):
        min_bullet_count = 3
        min_answer_chars = 260
        if len(selected_chunks) >= 2:
            min_citation_count = 2

    return {
        "min_citation_count": min_citation_count,
        "min_distinct_doc_count": min_distinct_doc_count,
        "min_bullet_count": min_bullet_count,
        "min_answer_chars": min_answer_chars,
    }


def _build_context(chunks: list[RetrievedChunk], *, query_strategy: str) -> str:
    max_chars_per_chunk, max_context_chars = _context_budget(query_strategy)
    lines: list[str] = []
    total_text_chars = 0
    for index, chunk in enumerate(chunks, start=1):
        remaining = max_context_chars - total_text_chars
        if remaining <= 0:
            break
        chunk_char_limit = min(max_chars_per_chunk, max(remaining, 200))
        chunk_text = _truncate_context_text(chunk.text, chunk_char_limit)
        total_text_chars += len(chunk_text)
        lines.append(f"[chunk {index}]")
        lines.append(f"doc_id: {chunk.doc_id}")
        lines.append(f"chunk_id: {chunk.chunk_id}")
        lines.append(f"title: {chunk.title}")
        lines.append(f"source: {chunk.source}")
        lines.append(f"group: {chunk.group}")
        lines.append(f"tags: {', '.join(chunk.tags) if chunk.tags else '-'}")
        lines.append(f"score: {chunk.score:.6f}")
        lines.append("text:")
        lines.append(chunk_text)
        lines.append("")
    return "\n".join(lines).strip()


def _truncate_context_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _supporting_snippet(text: str, *, question: str = "", max_chars: int = 180) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "No supporting excerpt was available in the retrieved chunk."
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    query_tokens = _ranking_query_tokens(question)
    best_sentence = ""
    best_score = float("-inf")
    for sentence in sentences:
        cleaned = _clean_snippet_sentence(sentence)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        sentence_tokens = set(re.findall(r"[a-z0-9]+", lowered))
        overlap = len(query_tokens.intersection(sentence_tokens))
        length_score = min(len(cleaned), 160) / 160
        boilerplate_penalty = 3.0 if any(pattern in lowered for pattern in SNIPPET_BOILERPLATE_PATTERNS) else 0.0
        score = (overlap * 2.5) + length_score - boilerplate_penalty
        if len(cleaned) < 40:
            score -= 1.5
        if score > best_score:
            best_score = score
            best_sentence = cleaned

    snippet = best_sentence or (_clean_snippet_sentence(sentences[0]) if sentences else normalized)
    if len(snippet) > max_chars:
        return _truncate_context_text(snippet, max_chars)
    return snippet


def _clean_snippet_sentence(sentence: str) -> str:
    cleaned = " ".join(str(sentence).split()).strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"^[A-Z][A-Za-z0-9 &/|,'().-]{0,80}:\s+(?:Q\d+:?\s*)?(?:A:\s*)?", "", cleaned)
    cleaned = re.sub(r"^(?:Q\d+:?\s*)?(?:A:\s*)", "", cleaned)
    return cleaned.strip(" -:\t")


def _compare_intro_sentence(*, question: str, primary: RetrievedChunk, secondary: RetrievedChunk) -> str:
    lower_question = question.lower()
    if "prompt engineering" in lower_question and "context engineering" in lower_question:
        return (
            "Prompt engineering is framed here as improving the instructions inside the prompt, "
            "while context engineering is framed as shaping the broader information and tool setup around the model."
        )
    return (
        f"The retrieved sources emphasize different parts of the question: {primary.title} and {secondary.title} "
        "focus on related but distinct layers of the problem."
    )


def _compare_focus_label(*, chunk: RetrievedChunk, question: str) -> str:
    lower_question = question.lower()
    lower_title = chunk.title.lower()
    if "prompt engineering" in lower_question and "prompt engineering" in lower_title:
        return "Prompt engineering focus"
    if "context engineering" in lower_question and "context engineering" in lower_title:
        return "Context engineering focus"
    if "embedding" in lower_title:
        return "Embedding-model focus"
    if "vector" in lower_title and "db" in lower_title:
        return "Vector database focus"
    topic = _topic_hint(chunk.title).replace("-", " ").strip()
    if not topic:
        return "Source focus"
    return f"{topic.capitalize()} focus"


def _document_summary_intro(*, title: str, question: str) -> str:
    normalized_title = title.lower()
    if "rag" in normalized_title:
        return f"{title} outlines decision points for RAG system design, retrieval choices, and tradeoffs."
    if "embedding" in normalized_title:
        return f"{title} summarizes the main concepts, practical steps, and tradeoffs highlighted in the retrieved document."
    return f"{title} is summarized below using highlights grounded in the retrieved document."


def _named_source_lookup_answer(*, question: str, title: str, snippet: str) -> str:
    lower_question = question.lower()
    cleaned_snippet = snippet.rstrip(".")
    if "bottleneck" in lower_question and "context" in cleaned_snippet.lower():
        return (
            "According to the named source, the main bottleneck is not simply model intelligence. "
            "It is getting the right context, information, and tools in front of the model at the right time."
        )
    if cleaned_snippet:
        normalized_snippet = cleaned_snippet[0].lower() + cleaned_snippet[1:] if len(cleaned_snippet) > 1 else cleaned_snippet.lower()
        return f"According to the named source, {normalized_snippet}."
    return f"According to {title}, the retrieved context supports a direct answer from that source."


def _general_qa_intro(*, question: str, parsed_answer: str = "") -> str:
    cleaned = " ".join(str(parsed_answer).split()).strip()
    if cleaned and cleaned != UNANSWERABLE_ANSWER:
        first_sentence = re.split(r"(?<=[.!?])\s+", cleaned)[0].strip()
        if len(first_sentence) >= 40:
            return _truncate_context_text(first_sentence, 220)
    lower_question = question.lower()
    if "benefit" in lower_question or "advantage" in lower_question:
        return "The retrieved context points to several practical benefits that make prompt engineering more useful and controllable in real work."
    if "improve" in lower_question or "enhance" in lower_question or "how to" in lower_question:
        return "The retrieved context suggests a few concrete ways to improve results, especially around structure, context, and deliberate iteration."
    if "what makes" in lower_question or "effective" in lower_question:
        return "The retrieved context suggests that stronger results come from clearer intent, better context, and more deliberate testing."
    return "The retrieved context supports the following concrete takeaways."


def _general_qa_bullet(*, question: str, snippet: str) -> str:
    lower_question = question.lower()
    lower_snippet = snippet.lower()
    if "benefit" in lower_question or "advantage" in lower_question:
        label = _benefit_label_for_snippet(lower_snippet)
        return f"- {label}: {snippet}"
    if "improve" in lower_question or "enhance" in lower_question or "how to" in lower_question:
        label = _action_label_for_snippet(lower_snippet)
        return f"- {label}: {snippet}"
    return f"- {snippet}"


def _explanatory_fallback_bullet(*, question: str, snippet: str, title: str) -> str:
    lower_question = question.lower()
    lower_snippet = snippet.lower()
    if "benefit" in lower_question or "advantage" in lower_question:
        label = _benefit_label_for_snippet(lower_snippet)
        return f"- {label}: {snippet}"
    if "improve" in lower_question or "enhance" in lower_question or "how to" in lower_question:
        label = _action_label_for_snippet(lower_snippet)
        return f"- {label}: {snippet}"
    if "tradeoff" in lower_question or "risk" in lower_question or "limitation" in lower_question:
        return f"- Tradeoff to watch: {snippet}"
    if "example" in lower_snippet or "such as" in lower_snippet:
        return f"- Example in practice: {snippet}"
    if any(token in lower_snippet for token in ("context", "tool", "retrieval", "information")):
        return f"- Context and setup matter: {snippet}"
    if any(token in lower_snippet for token in ("evaluate", "evaluation", "compare", "test", "iteration")):
        return f"- Evaluation improves reliability: {snippet}"
    topic = _topic_hint(title).replace("-", " ").strip()
    label = f"{topic.capitalize()} takeaway" if topic else "Key takeaway"
    return f"- {label}: {snippet}"


def _general_qa_bullet_label(bullet: str) -> str:
    prefix = bullet.removeprefix("- ").strip()
    if ":" not in prefix:
        return ""
    return prefix.split(":", 1)[0].strip().lower()


def _benefit_label_for_snippet(lower_snippet: str) -> str:
    if any(token in lower_snippet for token in ("evaluate", "evaluation", "quality", "diversity")):
        return "Easier evaluation and iteration"
    if any(token in lower_snippet for token in ("guide model", "guide ai", "steer", "steering", "guide model behaviour", "desired responses")):
        return "More control over outputs"
    if any(token in lower_snippet for token in ("accurate", "accuracy", "relevant", "relevance", "customized", "desired responses")):
        return "Better relevance and accuracy"
    if any(token in lower_snippet for token in ("safe", "safety", "guardrail")):
        return "Safer interactions"
    if any(token in lower_snippet for token in ("example", "examples", "use cases")):
        return "Clearer examples and use cases"
    return "Practical upside"


def _action_label_for_snippet(lower_snippet: str) -> str:
    if any(token in lower_snippet for token in ("clear", "structure", "format", "structured")):
        return "Use clearer structure"
    if any(token in lower_snippet for token in ("context", "relevant")):
        return "Add the right context"
    if any(token in lower_snippet for token in ("example", "examples")):
        return "Include examples"
    if any(token in lower_snippet for token in ("evaluate", "evaluation", "compare", "quality")):
        return "Test and compare results"
    return "Refine the prompt deliberately"


def _topic_hint(title: str) -> str:
    normalized_title = title.lower()
    for phrase in (
        "prompt engineering",
        "context engineering",
        "vector database",
        "vector db",
        "embeddings",
        "embedding",
        "latency",
        "rag",
    ):
        if phrase in normalized_title:
            return phrase
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", normalized_title)
        if token not in RANKING_STOPWORDS and len(token) > 2
    ]
    if not tokens:
        return "that source's focus"
    return " ".join(tokens[:3])


def _load_prompt(path: Path, *, fallback: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def _render_prompt(
    *,
    template: str,
    query: str,
    context: str,
    previous_response: str,
    validation_errors: list[str],
    answer_style_instructions: str,
) -> str:
    rendered = template.replace("{{QUERY}}", query)
    rendered = rendered.replace("{{CONTEXT}}", context)
    rendered = rendered.replace("{{PREVIOUS_RESPONSE}}", previous_response or "(none)")
    rendered = rendered.replace("{{VALIDATION_ERRORS}}", "\n".join(validation_errors) or "(none)")
    rendered = rendered.replace("{{ANSWER_STYLE_INSTRUCTIONS}}", answer_style_instructions)
    return rendered


def _infer_answer_style_instructions(*, query: str, mode: str, query_strategy: str = "general_qa") -> str:
    normalized_query = " ".join(query.strip().split())
    if query_strategy == "document_summary":
        return (
            "This is a named-document summary request. In the JSON `answer` string, give a 1-2 sentence overview "
            "followed by 5-8 newline-separated bullet points covering the document's main arguments, notable claims, "
            "and practical takeaways. Each bullet must start with '- '."
        )
    if query_strategy == "named_source_lookup":
        return (
            "This is a targeted lookup from a named source. In the JSON `answer` string, answer directly in 2-4 "
            "sentences grounded in the named source. Do not answer generically, do not switch into a bullet list, "
            "and make the core claim explicit."
        )
    if query_strategy == "compare_synthesis":
        return (
            "This is a cross-document comparison request. In the JSON `answer` string, lead with one concise "
            "comparison sentence, then provide 4-6 newline-separated bullets covering concrete differences, "
            "overlaps, examples, and practical tradeoffs grounded in at least two cited sources when available. "
            "Each bullet must start with '- '. Use plain language, and do not turn the answer into a source-by-source "
            "dump of titles plus excerpts."
        )
    if query_strategy == "multi_document_synthesis":
        return (
            "This is a multi-document synthesis request. In the JSON `answer` string, lead with one short framing "
            "sentence, then provide 4-6 newline-separated bullets covering recommendations, tradeoffs, or takeaways "
            "grounded in at least two cited sources when available. Each bullet must start with '- '."
        )
    if query_strategy == "explanatory_qa":
        return (
            "This is an explanatory synthesis request. In the JSON `answer` string, give a 1-2 sentence overview "
            "followed by 4-6 newline-separated bullets that cover the main idea, why it matters, concrete benefits or "
            "tradeoffs, and at least one example when the retrieved context supports it. Use evidence from at least two "
            "cited sources when available. Each bullet must start with '- '. Use plain language and make each bullet "
            "read like a takeaway, not a raw excerpt."
        )
    if LIST_QUERY_PATTERN.search(normalized_query):
        return (
            "The user asked for a list. In the JSON `answer` string, lead with one concise framing sentence, then "
            "return a newline-separated bullet list with 5-8 bullets when the context supports it. Each bullet must "
            "start with '- ', add a distinct detail, and include concrete supporting context or an example when available."
        )
    if COMPARE_QUERY_PATTERN.search(normalized_query):
        return (
            "The user asked for a comparison. In the JSON `answer` string, lead with one concise comparison "
            "sentence, then use 3-6 newline-separated bullets covering concrete differences, overlaps, and "
            "practical implications grounded in the retrieved context."
        )
    if STEPS_QUERY_PATTERN.search(normalized_query):
        return (
            "The user is asking for improvement guidance or steps. In the JSON `answer` string, provide a "
            "short recommendation summary followed by 4-6 newline-separated action bullets ordered by impact. "
            "Make each bullet specific and practical, not generic advice."
        )
    if EXPLANATION_QUERY_PATTERN.search(normalized_query):
        return (
            "The user is asking for an explanatory answer. In the JSON `answer` string, give a 1-2 sentence overview "
            "followed by 4-6 newline-separated bullets that cover the main idea, why it matters, concrete benefits or "
            "tradeoffs, and at least one example when the retrieved context supports it. Each bullet must start with '- '. "
            "Use plain language and avoid reading like source notes."
        )
    if mode == "job-search":
        return (
            "Return a practical coaching answer with one short opening sentence followed by 3-5 newline-separated "
            "bullets tying evidence to interview or career actions."
        )
    if mode == "learning":
        return (
            "Return a teaching-oriented answer with one short framing sentence followed by 3-6 newline-separated "
            "bullets that explain the concept, tradeoffs, and practical implications."
        )
    return (
        "Return a detailed answer that directly addresses the request. Use a 1-2 sentence overview followed "
        "by 4-6 newline-separated bullets when the context supports multiple distinct points. Each bullet must "
        "start with '- ' and add a concrete detail, implication, or example instead of rephrasing the same idea."
    )


def _requires_structured_general_answer(*, query: str, mode: str) -> bool:
    normalized_query = " ".join(query.strip().split())
    if not normalized_query:
        return False
    if LIST_QUERY_PATTERN.search(normalized_query):
        return True
    if STEPS_QUERY_PATTERN.search(normalized_query):
        return True
    if EXPLANATION_QUERY_PATTERN.search(normalized_query):
        return True
    return mode in {"job-search", "learning"}


def _write_artifact(*, settings: RagSettings, run_id: str, payload: dict[str, Any]) -> str:
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = settings.artifacts_dir / f"{_artifact_stamp()}_{run_id}.json"
    artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(artifact_path.resolve())


def _insert_run_started(*, conn: sqlite3.Connection, run_id: str, query: str, started_at: str) -> None:
    input_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT INTO runs (run_id, workflow, status, started_at, input_hash)
        VALUES (?, ?, 'started', ?, ?)
        """,
        (run_id, "workflow_02_rag_query", started_at, input_hash),
    )
    conn.commit()


def _mark_run_completed(
    *,
    conn: sqlite3.Connection,
    run_id: str,
    ended_at: str,
    latency_ms: int,
    model: str,
    output_path: str | None,
) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='completed', ended_at=?, latency_ms=?, model=?, output_path=?
        WHERE run_id=?
        """,
        (ended_at, latency_ms, model, output_path, run_id),
    )
    conn.commit()


def _mark_run_failed(*, conn: sqlite3.Connection, run_id: str, ended_at: str, latency_ms: int) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='failed', ended_at=?, latency_ms=?
        WHERE run_id=?
        """,
        (ended_at, latency_ms, run_id),
    )
    conn.commit()


def _active_model_name(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    if normalized == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if normalized == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")


def _normalize_mode(mode: str | None) -> str:
    raw = (mode or "").strip().lower()
    if raw in {"", "rag", "default"}:
        return "default"
    if raw in {"job-search", "job_search", "jobsearch"}:
        return "job-search"
    if raw in {"learning", "learn"}:
        return "learning"
    raise ValueError(f"Unsupported mode: {mode}")


def _resolve_mode(*, mode: str | None, filter_tags: list[str], filter_group: str | None) -> str:
    if mode is not None and str(mode).strip():
        return _normalize_mode(mode)

    normalized_mode = _normalize_mode(mode)
    if normalized_mode != "default":
        return normalized_mode

    normalized_tags = {tag.strip().lower() for tag in filter_tags if tag.strip()}
    if "job-search" in normalized_tags:
        return "job-search"
    if {"learning", "genai-docs"}.issubset(normalized_tags):
        return "learning"
    if filter_group in {"job-search", "learning"}:
        return filter_group
    return "default"


def _normalize_filter_tags(filter_tags: list[str] | None) -> list[str]:
    if not filter_tags:
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for raw in filter_tags:
        tag = str(raw).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        deduped.append(tag)
    return deduped


def _normalize_filter_group(filter_group: str | None) -> str | None:
    if filter_group is None:
        return None
    raw = str(filter_group).strip()
    if not raw:
        return None
    return normalize_group(raw)


def _normalize_filter_tag_mode(filter_tag_mode: str | None) -> str:
    raw = str(filter_tag_mode or "").strip().lower()
    if raw in {"", "any", "or"}:
        return "any"
    if raw in {"all", "and", "must"}:
        return "all"
    raise ValueError(f"Unsupported filter_tag_mode: {filter_tag_mode}")


def _prompt_profile_name(mode: str, *, query_strategy: str = "general_qa") -> str:
    if query_strategy == "document_summary":
        return "workflow_02_document_summary"
    if query_strategy == "named_source_lookup":
        return "workflow_02_targeted_lookup"
    if query_strategy == "compare_synthesis":
        return "workflow_02_compare_synthesis"
    if query_strategy == "multi_document_synthesis":
        return "workflow_02_multi_document_synthesis"
    if query_strategy == "explanatory_qa":
        return "workflow_02_explanatory_qa"
    if mode == "job-search":
        return "job_search_coach"
    if mode == "learning":
        return "learning_coach"
    return "workflow_02_default"


def _query_strategy(*, question: str, retrieved: list[RetrievedChunk]) -> str:
    if _is_named_document_summary_query(question):
        return "document_summary"
    if _is_named_source_lookup_query(question):
        return "named_source_lookup"
    if _is_compare_query(question):
        return "compare_synthesis"
    if _is_multi_document_synthesis_query(question):
        return "multi_document_synthesis"
    if _is_explanatory_query(question):
        return "explanatory_qa"
    return "general_qa"


def _is_named_document_summary_query(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return False
    has_summary_intent = bool(SUMMARY_QUERY_PATTERN.search(normalized))
    has_document_reference = bool(DOCUMENT_REFERENCE_PATTERN.search(normalized) or QUOTED_TARGET_PATTERN.search(normalized))
    return has_summary_intent and has_document_reference


def _is_named_source_lookup_query(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return False
    if _is_named_document_summary_query(question) or _is_compare_query(question) or _is_multi_document_synthesis_query(question):
        return False
    has_named_source = bool(QUOTED_TARGET_PATTERN.search(normalized) or DOCUMENT_REFERENCE_PATTERN.search(normalized))
    if not has_named_source:
        return False
    return bool(TARGETED_SOURCE_LOOKUP_PATTERN.search(normalized))


def _is_compare_query(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return False
    return bool(COMPARE_QUERY_PATTERN.search(normalized))


def _is_multi_document_synthesis_query(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return False
    if _is_named_document_summary_query(question) or _is_compare_query(question):
        return False
    if not SYNTHESIS_CONNECTOR_PATTERN.search(normalized):
        return False
    lowered = normalized.lower()
    return any(
        marker in lowered
        for marker in ("tradeoff", "tradeoffs", "practical", "ways", "implications", "expect")
    )


def _is_explanatory_query(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return False
    if (
        _is_named_document_summary_query(question)
        or _is_named_source_lookup_query(question)
        or _is_compare_query(question)
        or _is_multi_document_synthesis_query(question)
        or _is_sensitive_secret_query(question)
    ):
        return False
    return bool(EXPLANATION_QUERY_PATTERN.search(normalized) or STEPS_QUERY_PATTERN.search(normalized) or LIST_QUERY_PATTERN.search(normalized))


def _is_sensitive_secret_query(question: str) -> bool:
    normalized = " ".join(question.strip().split())
    if not normalized:
        return False
    lowered = normalized.lower()
    has_secret_target = bool(SENSITIVE_SECRET_QUERY_PATTERN.search(lowered))
    if not has_secret_target:
        return False
    return bool(EXACT_SECRET_QUERY_PATTERN.search(lowered))


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _truncate(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _artifact_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Workflow 02 cited RAG query.")
    query_group = parser.add_mutually_exclusive_group(required=True)
    query_group.add_argument("--query", help="Query text.")
    query_group.add_argument("--query-file", help="Path to a file containing the query text.")
    parser.add_argument("--top-k", type=int, default=None, help="Override retrieval top-k.")
    parser.add_argument("--min-score", type=float, default=None, help="Override retrieval score threshold.")
    parser.add_argument("--max-retries", type=int, default=None, help="Override validation retry count.")
    parser.add_argument(
        "--filter-tags",
        default="",
        help="Comma-separated tags for retrieval filtering (optional).",
    )
    parser.add_argument(
        "--filter-group",
        default="",
        help="Optional group filter (`job-search|learning|project|reference|meeting`).",
    )
    parser.add_argument(
        "--filter-tag-mode",
        default="any",
        help="Tag filter mode: any|all.",
    )
    parser.add_argument(
        "--mode",
        default="default",
        help="Prompt mode: default|job-search|learning (aliases: rag, job_search, learn).",
    )
    parser.add_argument(
        "--retrieval-mode",
        default=None,
        help="Retrieval mode override: vector|hybrid.",
    )
    parser.add_argument(
        "--hybrid-alpha",
        type=float,
        default=None,
        help="Hybrid fusion weight for dense score [0..1].",
    )
    parser.add_argument(
        "--enable-reranker",
        action="store_true",
        help="Enable heuristic reranker after retrieval.",
    )
    parser.add_argument(
        "--reranker-weight",
        type=float,
        default=None,
        help="Reranker lexical blend weight [0..1].",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip SQLite writes and artifact file creation.")
    return parser.parse_args()


def _load_query(args: argparse.Namespace) -> str:
    if args.query is not None:
        return args.query
    assert args.query_file is not None
    return Path(args.query_file).read_text(encoding="utf-8").strip()


def main() -> int:
    args = parse_args()
    try:
        query = _load_query(args)
        result = run_rag_query(
            query,
            top_k=args.top_k,
            min_score=args.min_score,
            max_retries=args.max_retries,
            filter_tags=[part.strip() for part in args.filter_tags.split(",") if part.strip()],
            filter_tag_mode=args.filter_tag_mode,
            filter_group=args.filter_group or None,
            mode=args.mode,
            retrieval_mode=args.retrieval_mode,
            hybrid_alpha=args.hybrid_alpha,
            enable_reranker=args.enable_reranker if args.enable_reranker else None,
            reranker_weight=args.reranker_weight,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"RAG query failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
