#!/usr/bin/env python3
"""Workflow 02 cited RAG query runner for Recall.local."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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


@dataclass
class RagSettings:
    db_path: Path
    artifacts_dir: Path
    prompt_path: Path
    retry_prompt_path: Path
    top_k: int
    min_score: float
    max_retries: int
    temperature: float


def load_settings() -> RagSettings:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    top_k = int(os.getenv("RECALL_RAG_TOP_K", "5"))
    min_score = float(os.getenv("RECALL_RAG_MIN_SCORE", "0.2"))
    max_retries = int(os.getenv("RECALL_RAG_MAX_RETRIES", "1"))
    temperature = float(os.getenv("RECALL_RAG_TEMPERATURE", "0.2"))
    if top_k <= 0:
        raise ValueError("RECALL_RAG_TOP_K must be greater than 0")
    if max_retries < 0:
        raise ValueError("RECALL_RAG_MAX_RETRIES cannot be negative")

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
        retry_prompt_path=ROOT / "prompts" / "workflow_02_rag_answer_retry.md",
        top_k=top_k,
        min_score=min_score,
        max_retries=max_retries,
        temperature=temperature,
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
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = load_settings()
    limit = settings.top_k if top_k is None else top_k
    threshold = settings.min_score if min_score is None else min_score
    retries = settings.max_retries if max_retries is None else max_retries
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
        retrieved = retrieve_chunks(question, top_k=limit, min_score=threshold)
        fallback_reason: str | None = None
        if not retrieved:
            # Retry once with relaxed threshold to avoid hard failures on sparse / niche queries.
            retrieved = retrieve_chunks(question, top_k=limit, min_score=-1.0)
            if not retrieved:
                fallback_reason = "No retrieval results available for query."

        if fallback_reason is None:
            try:
                response, attempts_used = _generate_validated_answer(
                    question=question,
                    retrieved=retrieved,
                    max_retries=retries,
                    temperature=settings.temperature,
                    prompt_path=settings.prompt_path,
                    retry_prompt_path=settings.retry_prompt_path,
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
        normalization_reason = _normalize_low_confidence_response(response)
        if normalization_reason is not None:
            fallback_reason = (
                normalization_reason
                if fallback_reason is None
                else f"{fallback_reason}; {normalization_reason}"
            )

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
    prompt_path: Path,
    retry_prompt_path: Path,
) -> tuple[dict[str, Any], int]:
    allowed_pairs = {(item.doc_id, item.chunk_id) for item in retrieved}
    context = _build_context(retrieved)

    primary_template = _load_prompt(
        prompt_path,
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
        )

        raw_response = llm_client.generate(
            prompt=prompt,
            temperature=0.1 if is_retry else temperature,
        )
        validation = validate_rag_output(raw_response, valid_citation_pairs=allowed_pairs)
        if validation.valid:
            break

        previous_response = raw_response
        previous_errors = validation.errors

    if validation is None or not validation.valid or not validation.parsed_response:
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
        "sources": _source_rows(retrieved),
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


def _normalize_low_confidence_response(response: dict[str, Any]) -> str | None:
    confidence_level = str(response.get("confidence_level", "")).strip().lower()
    if confidence_level != "low":
        return None

    _ensure_citation_from_sources(response)

    answer = str(response.get("answer", "")).strip()
    if _has_unanswerable_phrase(answer):
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


def _source_rows(retrieved: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [
        {
            "doc_id": item.doc_id,
            "chunk_id": item.chunk_id,
            "title": item.title,
            "source": item.source,
            "source_type": item.source_type,
            "ingestion_channel": item.ingestion_channel,
            "score": round(item.score, 6),
            "excerpt": _truncate(item.text, 220),
        }
        for item in retrieved
    ]


def _build_context(chunks: list[RetrievedChunk]) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        lines.append(f"[chunk {index}]")
        lines.append(f"doc_id: {chunk.doc_id}")
        lines.append(f"chunk_id: {chunk.chunk_id}")
        lines.append(f"title: {chunk.title}")
        lines.append(f"source: {chunk.source}")
        lines.append(f"score: {chunk.score:.6f}")
        lines.append("text:")
        lines.append(chunk.text)
        lines.append("")
    return "\n".join(lines).strip()


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
) -> str:
    rendered = template.replace("{{QUERY}}", query)
    rendered = rendered.replace("{{CONTEXT}}", context)
    rendered = rendered.replace("{{PREVIOUS_RESPONSE}}", previous_response or "(none)")
    rendered = rendered.replace("{{VALIDATION_ERRORS}}", "\n".join(validation_errors) or "(none)")
    return rendered


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
    return os.getenv("OLLAMA_MODEL", "llama3.2:3b")


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
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"RAG query failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
