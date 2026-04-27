#!/usr/bin/env python3
"""Run Phase 1D evaluation checks for Workflow 02 cited RAG."""

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

from scripts.shared_time import now_iso

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


@dataclass
class EvalSettings:
    db_path: Path
    artifacts_dir: Path
    cases_file: Path
    default_max_latency_ms: int


@dataclass
class EvalCase:
    case_id: str
    category: str
    question: str
    expected_doc_id: str | None
    expected_answer: str | None
    expected_title_contains: list[str]
    expected_source_contains: list[str]
    max_latency_ms: int | None
    expect_unanswerable: bool
    mode: str | None
    filter_tags: list[str]
    filter_tag_mode: str | None
    required_terms: list[str]
    required_source_tags: list[str]
    required_source_tags_any_of: list[list[str]]
    min_bullet_count: int | None
    min_citation_count: int | None
    min_distinct_doc_count: int | None
    min_answer_chars: int | None
    semantic_similarity_min: float | None
    retrieval_mode: str | None
    hybrid_alpha: float | None
    enable_reranker: bool | None
    reranker_weight: float | None


@dataclass
class CaseResult:
    eval_id: str
    case_id: str
    category: str
    question: str
    expected_doc_id: str | None
    expect_unanswerable: bool
    actual_doc_id: str | None
    actual_title: str | None
    actual_source: str | None
    citation_valid: bool
    unanswerable_ok: bool | None
    required_terms_ok: bool | None
    source_tags_ok: bool | None
    title_match_ok: bool | None
    source_match_ok: bool | None
    bullet_count_ok: bool | None
    citation_count_ok: bool | None
    distinct_doc_count_ok: bool | None
    answer_length_ok: bool | None
    semantic_similarity: float | None
    semantic_similarity_ok: bool | None
    citation_count: int
    distinct_doc_count: int
    bullet_count: int
    answer_chars: int
    latency_ms: int
    passed: bool
    notes: str


def load_settings() -> EvalSettings:
    load_dotenv = _import_load_dotenv()
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    artifacts_root = _safe_dir_from_env(
        env_var="DATA_ARTIFACTS",
        fallback=ROOT / "data" / "artifacts",
    )
    db_path = _safe_file_path_from_env(
        env_var="RECALL_DB_PATH",
        fallback=ROOT / "data" / "recall.db",
    )

    return EvalSettings(
        db_path=db_path,
        artifacts_dir=artifacts_root / "evals",
        cases_file=ROOT / "scripts" / "eval" / "eval_cases.json",
        default_max_latency_ms=int(os.getenv("RECALL_EVAL_MAX_LATENCY_MS", "15000")),
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


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            workflow TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'started',
            started_at TEXT NOT NULL,
            ended_at TEXT,
            model TEXT,
            latency_ms INTEGER,
            input_hash TEXT,
            output_path TEXT
        );

        CREATE TABLE IF NOT EXISTS eval_results (
            eval_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            expected_doc_id TEXT,
            actual_doc_id TEXT,
            citation_valid BOOLEAN,
            latency_ms INTEGER,
            passed BOOLEAN,
            run_date TEXT NOT NULL
        );
        """
    )
    conn.commit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Recall.local Workflow 02 eval checks.")
    parser.add_argument("--cases-file", default=None, help="Path to eval cases JSON file.")
    parser.add_argument("--backend", choices=["direct", "webhook"], default="webhook", help="Execution backend.")
    parser.add_argument(
        "--webhook-url",
        default=None,
        help="Workflow 02 webhook URL for backend=webhook. Default: {N8N_HOST}/webhook/recall-query.",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Retrieval top-k sent to Workflow 02.")
    parser.add_argument("--min-score", type=float, default=0.15, help="Retrieval min score sent to Workflow 02.")
    parser.add_argument("--max-retries", type=int, default=1, help="Validation retries sent to Workflow 02.")
    parser.add_argument(
        "--filter-tag-mode",
        choices=["any", "all"],
        default=None,
        help="Global tag filter mode override: any|all (case-level value wins).",
    )
    parser.add_argument(
        "--retrieval-mode",
        default=None,
        help="Retrieval mode override for all cases: vector|hybrid.",
    )
    parser.add_argument(
        "--hybrid-alpha",
        type=float,
        default=None,
        help="Hybrid fusion weight override for all cases [0..1].",
    )
    parser.add_argument(
        "--enable-reranker",
        default=None,
        choices=["true", "false"],
        help="Enable or disable reranker globally (true|false).",
    )
    parser.add_argument(
        "--reranker-weight",
        type=float,
        default=None,
        help="Reranker lexical blend weight override [0..1].",
    )
    parser.add_argument(
        "--semantic-score",
        action="store_true",
        help="Compute optional semantic similarity score for cases that include expected_answer.",
    )
    parser.add_argument(
        "--semantic-min-score",
        type=float,
        default=None,
        help="Semantic similarity threshold (default from env or 0.65).",
    )
    parser.add_argument(
        "--enforce-semantic-score",
        action="store_true",
        help="Treat semantic score threshold failures as eval failures.",
    )
    parser.add_argument("--max-cases", type=int, default=None, help="Only run first N cases.")
    parser.add_argument("--dry-run", action="store_true", help="Skip DB writes and artifact file write.")
    return parser.parse_args()


def load_cases(path: Path) -> list[EvalCase]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Eval cases file must be a JSON array.")

    cases: list[EvalCase] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Case at index {index} must be a JSON object.")
        case_id_raw = item.get("case_id")
        case_id = str(case_id_raw).strip() if case_id_raw else f"case-{index + 1:02d}"
        category_raw = item.get("category")
        category = str(category_raw).strip() if category_raw else "general"
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"Case at index {index} is missing question.")
        expected_doc_id_raw = item.get("expected_doc_id")
        expected_doc_id = str(expected_doc_id_raw).strip() if expected_doc_id_raw else None
        expected_answer_raw = item.get("expected_answer")
        expected_answer = str(expected_answer_raw).strip() if expected_answer_raw else None
        expected_title_contains = _normalize_string_list(item.get("expected_title_contains"))
        expected_source_contains = _normalize_string_list(item.get("expected_source_contains"))
        max_latency_raw = item.get("max_latency_ms")
        max_latency_ms = int(max_latency_raw) if max_latency_raw is not None else None
        expect_unanswerable = bool(item.get("expect_unanswerable", False))
        mode_raw = item.get("mode")
        mode = str(mode_raw).strip() if isinstance(mode_raw, str) and mode_raw.strip() else None
        filter_tags = _normalize_string_list(item.get("filter_tags"))
        filter_tag_mode = _normalize_filter_tag_mode(item.get("filter_tag_mode"))
        required_terms = _normalize_string_list(item.get("required_terms"))
        required_source_tags = _normalize_string_list(item.get("required_source_tags"))
        required_source_tags_any_of = _normalize_source_tag_groups(item.get("required_source_tags_any_of"))
        min_bullet_count_raw = item.get("min_bullet_count")
        min_bullet_count = int(min_bullet_count_raw) if min_bullet_count_raw is not None else None
        min_citation_count_raw = item.get("min_citation_count")
        min_citation_count = int(min_citation_count_raw) if min_citation_count_raw is not None else None
        min_distinct_doc_count_raw = item.get("min_distinct_doc_count")
        min_distinct_doc_count = int(min_distinct_doc_count_raw) if min_distinct_doc_count_raw is not None else None
        min_answer_chars_raw = item.get("min_answer_chars")
        min_answer_chars = int(min_answer_chars_raw) if min_answer_chars_raw is not None else None
        semantic_similarity_min_raw = item.get("semantic_similarity_min")
        semantic_similarity_min = (
            float(semantic_similarity_min_raw) if semantic_similarity_min_raw is not None else None
        )
        retrieval_mode_raw = item.get("retrieval_mode")
        retrieval_mode = (
            str(retrieval_mode_raw).strip()
            if isinstance(retrieval_mode_raw, str) and retrieval_mode_raw.strip()
            else None
        )
        hybrid_alpha_raw = item.get("hybrid_alpha")
        hybrid_alpha = float(hybrid_alpha_raw) if hybrid_alpha_raw is not None else None
        enable_reranker = _normalize_optional_bool(item.get("enable_reranker"))
        reranker_weight_raw = item.get("reranker_weight")
        reranker_weight = float(reranker_weight_raw) if reranker_weight_raw is not None else None
        cases.append(
            EvalCase(
                case_id=case_id,
                category=category,
                question=question,
                expected_doc_id=expected_doc_id,
                expected_answer=expected_answer,
                expected_title_contains=expected_title_contains,
                expected_source_contains=expected_source_contains,
                max_latency_ms=max_latency_ms,
                expect_unanswerable=expect_unanswerable,
                mode=mode,
                filter_tags=filter_tags,
                filter_tag_mode=filter_tag_mode,
                required_terms=required_terms,
                required_source_tags=required_source_tags,
                required_source_tags_any_of=required_source_tags_any_of,
                min_bullet_count=min_bullet_count,
                min_citation_count=min_citation_count,
                min_distinct_doc_count=min_distinct_doc_count,
                min_answer_chars=min_answer_chars,
                semantic_similarity_min=semantic_similarity_min,
                retrieval_mode=retrieval_mode,
                hybrid_alpha=hybrid_alpha,
                enable_reranker=enable_reranker,
                reranker_weight=reranker_weight,
            )
        )
    return cases


def run_case(
    case: EvalCase,
    *,
    backend: str,
    webhook_url: str,
    top_k: int,
    min_score: float,
    max_retries: int,
    filter_tag_mode: str | None,
    default_max_latency_ms: int,
    retrieval_mode: str | None,
    hybrid_alpha: float | None,
    enable_reranker: bool | None,
    reranker_weight: float | None,
    semantic_score_enabled: bool,
    semantic_min_score: float | None,
    enforce_semantic_score: bool,
) -> CaseResult:
    eval_id = uuid.uuid4().hex

    case_retrieval_mode = case.retrieval_mode or retrieval_mode
    case_filter_tag_mode = case.filter_tag_mode or filter_tag_mode
    case_hybrid_alpha = case.hybrid_alpha if case.hybrid_alpha is not None else hybrid_alpha
    case_enable_reranker = case.enable_reranker if case.enable_reranker is not None else enable_reranker
    case_reranker_weight = case.reranker_weight if case.reranker_weight is not None else reranker_weight

    started = time.perf_counter()
    try:
        payload = _execute_query(
            question=case.question,
            backend=backend,
            webhook_url=webhook_url,
            top_k=top_k,
            min_score=min_score,
            max_retries=max_retries,
            mode=case.mode,
            filter_tags=case.filter_tags,
            filter_tag_mode=case_filter_tag_mode,
            retrieval_mode=case_retrieval_mode,
            hybrid_alpha=case_hybrid_alpha,
            enable_reranker=case_enable_reranker,
            reranker_weight=case_reranker_weight,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        (
            passed,
            citation_valid,
            actual_doc_id,
            unanswerable_ok,
            required_terms_ok,
            source_tags_ok,
            semantic_similarity,
            semantic_similarity_ok,
            actual_title,
            actual_source,
            title_match_ok,
            source_match_ok,
            bullet_count_ok,
            citation_count_ok,
            distinct_doc_count_ok,
            answer_length_ok,
            citation_count,
            distinct_doc_count,
            bullet_count,
            answer_chars,
            notes,
        ) = _evaluate_payload(
            case=case,
            payload=payload,
            latency_ms=latency_ms,
            default_max_latency_ms=default_max_latency_ms,
            semantic_score_enabled=semantic_score_enabled,
            semantic_min_score=semantic_min_score,
            enforce_semantic_score=enforce_semantic_score,
        )
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        passed = False
        citation_valid = False
        actual_doc_id = None
        actual_title = None
        actual_source = None
        unanswerable_ok = None
        required_terms_ok = None
        source_tags_ok = None
        title_match_ok = None
        source_match_ok = None
        bullet_count_ok = None
        citation_count_ok = None
        distinct_doc_count_ok = None
        answer_length_ok = None
        semantic_similarity = None
        semantic_similarity_ok = None
        citation_count = 0
        distinct_doc_count = 0
        bullet_count = 0
        answer_chars = 0
        notes = f"Execution error: {exc}"

    return CaseResult(
        eval_id=eval_id,
        case_id=case.case_id,
        category=case.category,
        question=case.question,
        expected_doc_id=case.expected_doc_id,
        expect_unanswerable=case.expect_unanswerable,
        actual_doc_id=actual_doc_id,
        actual_title=actual_title,
        actual_source=actual_source,
        citation_valid=citation_valid,
        unanswerable_ok=unanswerable_ok,
        required_terms_ok=required_terms_ok,
        source_tags_ok=source_tags_ok,
        title_match_ok=title_match_ok,
        source_match_ok=source_match_ok,
        bullet_count_ok=bullet_count_ok,
        citation_count_ok=citation_count_ok,
        distinct_doc_count_ok=distinct_doc_count_ok,
        answer_length_ok=answer_length_ok,
        semantic_similarity=semantic_similarity,
        semantic_similarity_ok=semantic_similarity_ok,
        citation_count=citation_count,
        distinct_doc_count=distinct_doc_count,
        bullet_count=bullet_count,
        answer_chars=answer_chars,
        latency_ms=latency_ms,
        passed=passed,
        notes=notes,
    )


def _execute_query(
    *,
    question: str,
    backend: str,
    webhook_url: str,
    top_k: int,
    min_score: float,
    max_retries: int,
    mode: str | None,
    filter_tags: list[str],
    filter_tag_mode: str | None,
    retrieval_mode: str | None,
    hybrid_alpha: float | None,
    enable_reranker: bool | None,
    reranker_weight: float | None,
) -> dict[str, Any]:
    if backend == "direct":
        from scripts.phase1.rag_query import run_rag_query  # noqa: PLC0415

        return run_rag_query(
            question,
            top_k=top_k,
            min_score=min_score,
            max_retries=max_retries,
            filter_tags=filter_tags,
            filter_tag_mode=filter_tag_mode,
            mode=mode,
            retrieval_mode=retrieval_mode,
            hybrid_alpha=hybrid_alpha,
            enable_reranker=enable_reranker,
            reranker_weight=reranker_weight,
            dry_run=True,
        )

    request_body = {
        "query": question,
        "top_k": top_k,
        "min_score": min_score,
        "max_retries": max_retries,
    }
    if mode:
        request_body["mode"] = mode
    if filter_tags:
        request_body["filter_tags"] = filter_tags
    if filter_tag_mode:
        request_body["filter_tag_mode"] = filter_tag_mode
    if retrieval_mode:
        request_body["retrieval_mode"] = retrieval_mode
    if hybrid_alpha is not None:
        request_body["hybrid_alpha"] = hybrid_alpha
    if enable_reranker is not None:
        request_body["enable_reranker"] = enable_reranker
    if reranker_weight is not None:
        request_body["reranker_weight"] = reranker_weight
    httpx = _import_httpx()
    response = httpx.post(webhook_url, json=request_body, timeout=90)
    response.raise_for_status()

    body = response.json()
    if isinstance(body, dict) and isinstance(body.get("result"), dict):
        return body["result"]
    if isinstance(body, dict) and isinstance(body.get("rag_result"), dict):
        return body["rag_result"]
    if isinstance(body, dict):
        return body
    raise ValueError("Webhook response was not a JSON object.")


def _import_httpx():
    try:
        import httpx  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency 'httpx'. Install with: pip install -r requirements.txt") from exc
    return httpx


def _import_load_dotenv():
    try:
        from dotenv import load_dotenv  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing dependency 'python-dotenv'. Install with: pip install -r requirements.txt") from exc
    return load_dotenv


def _evaluate_payload(
    *,
    case: EvalCase,
    payload: dict[str, Any],
    latency_ms: int,
    default_max_latency_ms: int,
    semantic_score_enabled: bool,
    semantic_min_score: float | None,
    enforce_semantic_score: bool,
) -> tuple[
    bool,
    bool,
    str | None,
    bool | None,
    bool | None,
    bool | None,
    float | None,
    bool | None,
    str | None,
    str | None,
    bool | None,
    bool | None,
    bool | None,
    bool | None,
    bool | None,
    bool | None,
    int,
    int,
    int,
    int,
    str,
]:
    answer = str(payload.get("answer", "")).strip()
    confidence_level = str(payload.get("confidence_level", "")).strip().lower()
    citations = payload.get("citations")
    sources = payload.get("sources")
    if not isinstance(citations, list):
        return (
            False,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            0,
            0,
            len(answer),
            "Response missing citations array",
        )
    if not isinstance(sources, list):
        return (
            False,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            0,
            0,
            len(answer),
            "Response missing sources array",
        )
    if not answer:
        return (
            False,
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            0,
            0,
            0,
            "Response missing answer text",
        )

    valid_pairs = {
        (str(source.get("doc_id", "")).strip(), str(source.get("chunk_id", "")).strip())
        for source in sources
        if isinstance(source, dict)
    }

    citation_pairs: list[tuple[str, str]] = []
    for citation in citations:
        if not isinstance(citation, dict):
            return (
                False,
                False,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                0,
                0,
                0,
                len(answer),
                "Citation entry is not an object",
            )
        doc_id = str(citation.get("doc_id", "")).strip()
        chunk_id = str(citation.get("chunk_id", "")).strip()
        if not doc_id or not chunk_id:
            return (
                False,
                False,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                0,
                0,
                0,
                len(answer),
                "Citation missing doc_id or chunk_id",
            )
        citation_pairs.append((doc_id, chunk_id))

    invalid_pairs = [pair for pair in citation_pairs if pair not in valid_pairs]
    citation_valid = not invalid_pairs and (bool(citation_pairs) or case.expect_unanswerable)

    actual_doc_id = citation_pairs[0][0] if citation_pairs else None
    cited_sources = _sources_for_tag_validation(sources=sources, citation_pairs=citation_pairs)
    actual_title = _first_source_value(cited_sources, key="title")
    actual_source = _first_source_value(cited_sources, key="source")
    expected_ok = case.expected_doc_id is None or case.expected_doc_id == actual_doc_id
    title_match_ok = _strings_present_in_sources(
        sources=cited_sources, key="title", expected=case.expected_title_contains
    )
    source_match_ok = _strings_present_in_sources(
        sources=cited_sources, key="source", expected=case.expected_source_contains
    )
    citation_count = len(citation_pairs)
    distinct_doc_count = len({doc_id for doc_id, _ in citation_pairs})
    bullet_count = _count_bullets(answer)
    answer_chars = len(answer)

    max_latency = case.max_latency_ms
    if max_latency is None:
        max_latency = default_max_latency_ms
    latency_ok = latency_ms <= max_latency

    notes: list[str] = []
    unanswerable_ok: bool | None = None
    required_terms_ok: bool | None = None
    source_tags_ok: bool | None = None
    semantic_similarity: float | None = None
    semantic_similarity_ok: bool | None = None
    bullet_count_ok: bool | None = None
    citation_count_ok: bool | None = None
    distinct_doc_count_ok: bool | None = None
    answer_length_ok: bool | None = None
    if not citations and not case.expect_unanswerable:
        notes.append("Response returned zero citations")
    if not citation_valid:
        notes.append(f"Invalid citation pairs: {invalid_pairs}")

    if case.expect_unanswerable:
        refusal_phrase_ok = _has_unanswerable_phrase(answer)
        low_confidence_ok = confidence_level == "low"
        unanswerable_ok = refusal_phrase_ok and low_confidence_ok
        if not refusal_phrase_ok:
            notes.append("Expected explicit 'I don't know / insufficient information' style answer.")
        if not low_confidence_ok:
            notes.append(f"Expected confidence_level=low for unanswerable case, got {confidence_level or 'missing'}")
    else:
        if not expected_ok:
            notes.append(f"Expected doc_id {case.expected_doc_id}, got {actual_doc_id}")
        if title_match_ok is False:
            notes.append(f"Cited titles did not include expected text: {case.expected_title_contains}")
        if source_match_ok is False:
            notes.append(f"Cited sources did not include expected text: {case.expected_source_contains}")

    if case.required_terms:
        normalized_answer = answer.lower()
        matched_terms = [term for term in case.required_terms if term.lower() in normalized_answer]
        required_terms_ok = bool(matched_terms)
        if not required_terms_ok:
            notes.append(f"Answer missing required grounding terms: {case.required_terms}")

    if case.required_source_tags:
        tag_sources = _sources_for_tag_validation(sources=sources, citation_pairs=citation_pairs)
        required_source_tags_ok = _sources_match_required_tags(
            sources=tag_sources,
            required_tags=case.required_source_tags,
        )
        source_tags_ok = required_source_tags_ok
        if not required_source_tags_ok:
            notes.append(f"Sources did not satisfy required tags: {case.required_source_tags}")
    if case.required_source_tags_any_of:
        tag_sources = _sources_for_tag_validation(sources=sources, citation_pairs=citation_pairs)
        required_any_of_ok = _sources_match_required_tags_any_of(
            sources=tag_sources,
            required_tag_groups=case.required_source_tags_any_of,
        )
        source_tags_ok = required_any_of_ok if source_tags_ok is None else (source_tags_ok and required_any_of_ok)
        if not required_any_of_ok:
            notes.append(f"Sources did not satisfy any required tag group: {case.required_source_tags_any_of}")

    if case.min_bullet_count is not None:
        bullet_count_ok = bullet_count >= case.min_bullet_count
        if not bullet_count_ok:
            notes.append(f"Answer had {bullet_count} bullets, expected at least {case.min_bullet_count}")

    if case.min_citation_count is not None:
        citation_count_ok = citation_count >= case.min_citation_count
        if not citation_count_ok:
            notes.append(f"Answer cited {citation_count} chunks, expected at least {case.min_citation_count}")

    if case.min_distinct_doc_count is not None:
        distinct_doc_count_ok = distinct_doc_count >= case.min_distinct_doc_count
        if not distinct_doc_count_ok:
            notes.append(
                f"Answer used {distinct_doc_count} distinct docs, expected at least {case.min_distinct_doc_count}"
            )

    if case.min_answer_chars is not None:
        answer_length_ok = answer_chars >= case.min_answer_chars
        if not answer_length_ok:
            notes.append(f"Answer length {answer_chars} chars below minimum {case.min_answer_chars}")

    if semantic_score_enabled and case.expected_answer:
        threshold = (
            case.semantic_similarity_min
            if case.semantic_similarity_min is not None
            else (semantic_min_score if semantic_min_score is not None else _env_semantic_min_score())
        )
        try:
            semantic_similarity = _semantic_similarity(answer, case.expected_answer)
            semantic_similarity_ok = semantic_similarity >= threshold
            if not semantic_similarity_ok:
                notes.append(f"Semantic similarity {semantic_similarity:.3f} below threshold {threshold:.3f}")
        except Exception as exc:  # noqa: BLE001
            semantic_similarity_ok = None
            notes.append(f"Semantic score skipped due error: {exc}")

    if not latency_ok:
        notes.append(f"Latency {latency_ms}ms exceeded threshold {max_latency}ms")

    if case.expect_unanswerable:
        passed = citation_valid and bool(unanswerable_ok) and latency_ok
    else:
        passed = citation_valid and expected_ok and latency_ok
    if title_match_ok is False:
        passed = False
    if source_match_ok is False:
        passed = False
    if required_terms_ok is False:
        passed = False
    if source_tags_ok is False:
        passed = False
    if bullet_count_ok is False:
        passed = False
    if citation_count_ok is False:
        passed = False
    if distinct_doc_count_ok is False:
        passed = False
    if answer_length_ok is False:
        passed = False
    if enforce_semantic_score and semantic_similarity_ok is False:
        passed = False
    return (
        passed,
        citation_valid,
        actual_doc_id,
        unanswerable_ok,
        required_terms_ok,
        source_tags_ok,
        semantic_similarity,
        semantic_similarity_ok,
        actual_title,
        actual_source,
        title_match_ok,
        source_match_ok,
        bullet_count_ok,
        citation_count_ok,
        distinct_doc_count_ok,
        answer_length_ok,
        citation_count,
        distinct_doc_count,
        bullet_count,
        answer_chars,
        "; ".join(notes) if notes else "ok",
    )


def _has_unanswerable_phrase(answer: str) -> bool:
    normalized = " ".join(answer.lower().split())
    return any(pattern in normalized for pattern in UNANSWERABLE_PATTERNS)


def _sources_match_required_tags(*, sources: list[Any], required_tags: list[str]) -> bool:
    required = {tag.strip().lower() for tag in required_tags if tag.strip()}
    if not required:
        return True
    if not sources:
        return False
    for source in sources:
        if not isinstance(source, dict):
            return False
        source_tags_raw = source.get("tags")
        source_tags = {
            str(tag).strip().lower()
            for tag in (source_tags_raw if isinstance(source_tags_raw, list) else [source_tags_raw])
            if str(tag).strip()
        }
        if not required.issubset(source_tags):
            return False
    return True


def _sources_match_required_tags_any_of(*, sources: list[Any], required_tag_groups: list[list[str]]) -> bool:
    groups = [{tag.strip().lower() for tag in group if tag.strip()} for group in required_tag_groups if group]
    groups = [group for group in groups if group]
    if not groups:
        return True
    if not sources:
        return False

    for source in sources:
        if not isinstance(source, dict):
            return False
        source_tags_raw = source.get("tags")
        source_tags = {
            str(tag).strip().lower()
            for tag in (source_tags_raw if isinstance(source_tags_raw, list) else [source_tags_raw])
            if str(tag).strip()
        }
        if not any(group.issubset(source_tags) for group in groups):
            return False
    return True


def _sources_for_tag_validation(*, sources: list[Any], citation_pairs: list[tuple[str, str]]) -> list[Any]:
    normalized_sources = [source for source in sources if isinstance(source, dict)]
    if not normalized_sources:
        return []
    if not citation_pairs:
        return normalized_sources

    citation_set = set(citation_pairs)
    cited_sources = []
    for source in normalized_sources:
        doc_id = str(source.get("doc_id", "")).strip()
        chunk_id = str(source.get("chunk_id", "")).strip()
        if doc_id and chunk_id and (doc_id, chunk_id) in citation_set:
            cited_sources.append(source)
    return cited_sources if cited_sources else normalized_sources


def _first_source_value(sources: list[Any], *, key: str) -> str | None:
    for source in sources:
        if not isinstance(source, dict):
            continue
        value = str(source.get(key, "")).strip()
        if value:
            return value
    return None


def _strings_present_in_sources(*, sources: list[Any], key: str, expected: list[str]) -> bool | None:
    if not expected:
        return None
    haystack = " ".join(str(source.get(key, "")).strip().lower() for source in sources if isinstance(source, dict))
    return all(token.lower() in haystack for token in expected)


def _count_bullets(answer: str) -> int:
    count = 0
    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^(?:[-*•]\s+|\d+\.\s+)", stripped):
            count += 1
    return count


def _semantic_similarity(answer: str, expected_answer: str) -> float:
    from scripts import llm_client  # noqa: PLC0415

    answer_embedding = llm_client.embed(
        answer,
        trace_metadata={
            "workflow": "workflow_04_eval_gate",
            "operation": "semantic_answer_embedding",
        },
    )
    expected_embedding = llm_client.embed(
        expected_answer,
        trace_metadata={
            "workflow": "workflow_04_eval_gate",
            "operation": "semantic_expected_embedding",
        },
    )
    return _cosine_similarity(answer_embedding, expected_embedding)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        raise ValueError("Embedding vectors must be non-empty and equal length.")

    dot = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    left_norm = sum(left_value * left_value for left_value in left) ** 0.5
    right_norm = sum(right_value * right_value for right_value in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("Embedding vectors must have non-zero norm.")
    return dot / (left_norm * right_norm)


def _env_semantic_min_score() -> float:
    raw = os.getenv("RECALL_EVAL_SEMANTIC_MIN_SCORE", "").strip()
    if not raw:
        return 0.65
    try:
        value = float(raw)
    except ValueError:
        return 0.65
    return max(0.0, min(1.0, value))


def _normalize_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    raise ValueError("Boolean-like field must be true/false.")


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized:
                items.append(normalized)
        return items
    raise ValueError("Case fields expecting list values must be array or comma-separated string.")


def _normalize_source_tag_groups(value: Any) -> list[list[str]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("required_source_tags_any_of must be an array of tag arrays.")

    groups: list[list[str]] = []
    for index, group in enumerate(value):
        if isinstance(group, str):
            normalized_group = _normalize_string_list(group)
        elif isinstance(group, list):
            normalized_group = _normalize_string_list(group)
        else:
            raise ValueError(f"required_source_tags_any_of[{index}] must be a string or array of strings.")
        if normalized_group:
            groups.append(normalized_group)
    return groups


def _normalize_filter_tag_mode(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"", "any", "or"}:
        return "any"
    if normalized in {"all", "and", "must"}:
        return "all"
    raise ValueError(f"Unsupported filter_tag_mode: {value}")


def write_results(
    *,
    conn: sqlite3.Connection,
    run_id: str,
    results: list[CaseResult],
    run_date: str,
) -> None:
    for result in results:
        conn.execute(
            """
            INSERT INTO eval_results (
                eval_id, question, expected_doc_id, actual_doc_id,
                citation_valid, latency_ms, passed, run_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.eval_id,
                result.question,
                result.expected_doc_id,
                result.actual_doc_id,
                1 if result.citation_valid else 0,
                result.latency_ms,
                1 if result.passed else 0,
                run_date,
            ),
        )
    conn.commit()


def write_markdown_artifact(*, artifact_path: Path, results: list[CaseResult], run_id: str, backend: str) -> None:
    passed = sum(1 for row in results if row.passed)
    total = len(results)
    status = "PASS" if passed == total else "FAIL"
    unanswerable_total = sum(1 for row in results if row.expect_unanswerable)
    unanswerable_passed = sum(1 for row in results if row.expect_unanswerable and row.passed)

    lines = [
        "# Recall.local Eval Report",
        "",
        f"- Run ID: `{run_id}`",
        f"- Backend: `{backend}`",
        f"- Status: **{status}**",
        f"- Passed: `{passed}/{total}`",
        f"- Unanswerable Cases: `{unanswerable_passed}/{unanswerable_total}`",
        f"- Generated: `{now_iso()}`",
        "",
        "## Category Summary",
        "",
    ]

    categories = sorted({row.category for row in results})
    for category in categories:
        category_rows = [row for row in results if row.category == category]
        category_passed = sum(1 for row in category_rows if row.passed)
        avg_latency = int(sum(row.latency_ms for row in category_rows) / max(1, len(category_rows)))
        lines.append(f"- `{category}`: `{category_passed}/{len(category_rows)}` passed, avg latency `{avg_latency}ms`")

    lines.extend(
        [
            "",
            "| # | Category | Case ID | Type | Result | Latency (ms) | Citations | Distinct Docs | Bullets | Citation Valid | Title Match | Source Match | Unanswerable OK | Terms OK | Source Tags OK | Semantic Score | Semantic OK | Expected Doc | Actual Doc | Actual Title | Question | Notes |",
            "|---|---|---|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---:|---|---|---|---|---|---|",
        ]
    )

    for index, row in enumerate(results, start=1):
        lines.append(
            "| {index} | {category} | {case_id} | {case_type} | {result} | {latency} | {citation_count} | {distinct_doc_count} | {bullet_count} | {citation_valid} | {title_match_ok} | {source_match_ok} | {unanswerable_ok} | {required_terms_ok} | {source_tags_ok} | {semantic_similarity} | {semantic_ok} | {expected} | {actual} | {actual_title} | {question} | {notes} |".format(
                index=index,
                category=_table_escape(row.category),
                case_id=_table_escape(row.case_id),
                case_type="unanswerable" if row.expect_unanswerable else "answerable",
                result="PASS" if row.passed else "FAIL",
                latency=row.latency_ms,
                citation_count=row.citation_count,
                distinct_doc_count=row.distinct_doc_count,
                bullet_count=row.bullet_count,
                citation_valid="yes" if row.citation_valid else "no",
                title_match_ok=("n/a" if row.title_match_ok is None else ("yes" if row.title_match_ok else "no")),
                source_match_ok=("n/a" if row.source_match_ok is None else ("yes" if row.source_match_ok else "no")),
                unanswerable_ok=("n/a" if row.unanswerable_ok is None else ("yes" if row.unanswerable_ok else "no")),
                required_terms_ok=(
                    "n/a" if row.required_terms_ok is None else ("yes" if row.required_terms_ok else "no")
                ),
                source_tags_ok=("n/a" if row.source_tags_ok is None else ("yes" if row.source_tags_ok else "no")),
                semantic_similarity=("n/a" if row.semantic_similarity is None else f"{row.semantic_similarity:.3f}"),
                semantic_ok=(
                    "n/a" if row.semantic_similarity_ok is None else ("yes" if row.semantic_similarity_ok else "no")
                ),
                expected=(row.expected_doc_id or "-"),
                actual=(row.actual_doc_id or "-"),
                actual_title=_table_escape(row.actual_title or "-"),
                question=_table_escape(row.question),
                notes=_table_escape(row.notes),
            )
        )

    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def insert_run_started(conn: sqlite3.Connection, run_id: str, input_hash: str) -> None:
    conn.execute(
        """
        INSERT INTO runs (run_id, workflow, status, started_at, input_hash)
        VALUES (?, ?, 'started', ?, ?)
        """,
        (run_id, "workflow_04_eval_gate", now_iso(), input_hash),
    )
    conn.commit()


def mark_run_completed(conn: sqlite3.Connection, run_id: str, latency_ms: int, output_path: str | None) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='completed', ended_at=?, latency_ms=?, output_path=?
        WHERE run_id=?
        """,
        (now_iso(), latency_ms, output_path, run_id),
    )
    conn.commit()


def mark_run_failed(conn: sqlite3.Connection, run_id: str, latency_ms: int) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='failed', ended_at=?, latency_ms=?
        WHERE run_id=?
        """,
        (now_iso(), latency_ms, run_id),
    )
    conn.commit()


def _table_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    args = parse_args()
    settings = load_settings()

    cases_file = Path(args.cases_file) if args.cases_file else settings.cases_file
    if not cases_file.exists():
        print(f"Cases file not found: {cases_file}", file=sys.stderr)
        return 2

    webhook_url = args.webhook_url or f"{os.getenv('N8N_HOST', 'http://localhost:5678')}/webhook/recall-query"

    try:
        cases = load_cases(cases_file)
    except Exception as exc:  # noqa: BLE001
        print(f"Invalid eval cases file: {exc}", file=sys.stderr)
        return 2

    if args.max_cases is not None:
        cases = cases[: args.max_cases]

    if not cases:
        print("No eval cases to run.", file=sys.stderr)
        return 2

    try:
        global_enable_reranker = _normalize_optional_bool(args.enable_reranker)
    except ValueError as exc:
        print(f"Invalid --enable-reranker value: {exc}", file=sys.stderr)
        return 2

    run_id = uuid.uuid4().hex
    started = time.perf_counter()
    input_hash = hashlib.sha256(
        json.dumps(
            {
                "cases_file": str(cases_file),
                "backend": args.backend,
                "webhook_url": webhook_url,
                "top_k": args.top_k,
                "min_score": args.min_score,
                "max_retries": args.max_retries,
                "filter_tag_mode": args.filter_tag_mode,
                "retrieval_mode": args.retrieval_mode,
                "hybrid_alpha": args.hybrid_alpha,
                "enable_reranker": args.enable_reranker,
                "reranker_weight": args.reranker_weight,
                "semantic_score": args.semantic_score,
                "semantic_min_score": args.semantic_min_score,
                "enforce_semantic_score": args.enforce_semantic_score,
                "case_count": len(cases),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    conn: sqlite3.Connection | None = None
    if not args.dry_run:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        ensure_schema(conn)
        insert_run_started(conn, run_id, input_hash)

    try:
        results = [
            run_case(
                case,
                backend=args.backend,
                webhook_url=webhook_url,
                top_k=args.top_k,
                min_score=args.min_score,
                max_retries=args.max_retries,
                filter_tag_mode=args.filter_tag_mode,
                default_max_latency_ms=settings.default_max_latency_ms,
                retrieval_mode=args.retrieval_mode,
                hybrid_alpha=args.hybrid_alpha,
                enable_reranker=global_enable_reranker,
                reranker_weight=args.reranker_weight,
                semantic_score_enabled=args.semantic_score,
                semantic_min_score=args.semantic_min_score,
                enforce_semantic_score=args.enforce_semantic_score,
            )
            for case in cases
        ]

        pass_count = sum(1 for row in results if row.passed)
        total = len(results)
        artifact_path: Path | None = None

        if not args.dry_run:
            run_date = now_iso()
            write_results(conn=conn, run_id=run_id, results=results, run_date=run_date)
            artifact_path = settings.artifacts_dir / f"{_stamp()}_{run_id}.md"
            write_markdown_artifact(artifact_path=artifact_path, results=results, run_id=run_id, backend=args.backend)

        latency_ms = int((time.perf_counter() - started) * 1000)
        if conn is not None:
            mark_run_completed(conn, run_id, latency_ms, str(artifact_path.resolve()) if artifact_path else None)

        summary = {
            "run_id": run_id,
            "status": "pass" if pass_count == total else "fail",
            "cases_file": str(cases_file),
            "backend": args.backend,
            "webhook_url": webhook_url if args.backend == "webhook" else None,
            "filter_tag_mode": args.filter_tag_mode,
            "retrieval_mode": args.retrieval_mode,
            "hybrid_alpha": args.hybrid_alpha,
            "enable_reranker": global_enable_reranker,
            "reranker_weight": args.reranker_weight,
            "semantic_score": args.semantic_score,
            "semantic_min_score": args.semantic_min_score,
            "enforce_semantic_score": args.enforce_semantic_score,
            "passed": pass_count,
            "total": total,
            "unanswerable_passed": sum(1 for row in results if row.expect_unanswerable and row.passed),
            "unanswerable_total": sum(1 for row in results if row.expect_unanswerable),
            "semantic_scored_cases": sum(1 for row in results if row.semantic_similarity is not None),
            "semantic_passed_cases": sum(1 for row in results if row.semantic_similarity_ok is True),
            "semantic_failed_cases": sum(1 for row in results if row.semantic_similarity_ok is False),
            "latency_ms": latency_ms,
            "artifact_path": str(artifact_path.resolve()) if artifact_path else None,
            "results": [row.__dict__ for row in results],
        }
        print(json.dumps(summary, indent=2))
        return 0 if pass_count == total else 1
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        if conn is not None:
            mark_run_failed(conn, run_id, latency_ms)
        print(f"Eval run failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
