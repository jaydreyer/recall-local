#!/usr/bin/env python3
"""Run Phase 1D evaluation checks for Workflow 02 cited RAG."""

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

import httpx
from dotenv import load_dotenv

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
    question: str
    expected_doc_id: str | None
    max_latency_ms: int | None
    expect_unanswerable: bool


@dataclass
class CaseResult:
    eval_id: str
    question: str
    expected_doc_id: str | None
    expect_unanswerable: bool
    actual_doc_id: str | None
    citation_valid: bool
    unanswerable_ok: bool | None
    latency_ms: int
    passed: bool
    notes: str


def load_settings() -> EvalSettings:
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
        question = str(item.get("question", "")).strip()
        if not question:
            raise ValueError(f"Case at index {index} is missing question.")
        expected_doc_id_raw = item.get("expected_doc_id")
        expected_doc_id = str(expected_doc_id_raw).strip() if expected_doc_id_raw else None
        max_latency_raw = item.get("max_latency_ms")
        max_latency_ms = int(max_latency_raw) if max_latency_raw is not None else None
        expect_unanswerable = bool(item.get("expect_unanswerable", False))
        cases.append(
            EvalCase(
                question=question,
                expected_doc_id=expected_doc_id,
                max_latency_ms=max_latency_ms,
                expect_unanswerable=expect_unanswerable,
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
    default_max_latency_ms: int,
) -> CaseResult:
    eval_id = uuid.uuid4().hex

    started = time.perf_counter()
    try:
        payload = _execute_query(
            question=case.question,
            backend=backend,
            webhook_url=webhook_url,
            top_k=top_k,
            min_score=min_score,
            max_retries=max_retries,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        passed, citation_valid, actual_doc_id, unanswerable_ok, notes = _evaluate_payload(
            case=case,
            payload=payload,
            latency_ms=latency_ms,
            default_max_latency_ms=default_max_latency_ms,
        )
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        passed = False
        citation_valid = False
        actual_doc_id = None
        unanswerable_ok = None
        notes = f"Execution error: {exc}"

    return CaseResult(
        eval_id=eval_id,
        question=case.question,
        expected_doc_id=case.expected_doc_id,
        expect_unanswerable=case.expect_unanswerable,
        actual_doc_id=actual_doc_id,
        citation_valid=citation_valid,
        unanswerable_ok=unanswerable_ok,
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
) -> dict[str, Any]:
    if backend == "direct":
        from scripts.phase1.rag_query import run_rag_query  # noqa: PLC0415

        return run_rag_query(question, top_k=top_k, min_score=min_score, max_retries=max_retries, dry_run=True)

    request_body = {
        "query": question,
        "top_k": top_k,
        "min_score": min_score,
        "max_retries": max_retries,
    }
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


def _evaluate_payload(
    *,
    case: EvalCase,
    payload: dict[str, Any],
    latency_ms: int,
    default_max_latency_ms: int,
) -> tuple[bool, bool, str | None, bool | None, str]:
    answer = str(payload.get("answer", "")).strip()
    confidence_level = str(payload.get("confidence_level", "")).strip().lower()
    citations = payload.get("citations")
    sources = payload.get("sources")
    if not isinstance(citations, list):
        return False, False, None, None, "Response missing citations array"
    if not isinstance(sources, list):
        return False, False, None, None, "Response missing sources array"
    if not answer:
        return False, False, None, None, "Response missing answer text"

    valid_pairs = {
        (str(source.get("doc_id", "")).strip(), str(source.get("chunk_id", "")).strip())
        for source in sources
        if isinstance(source, dict)
    }

    citation_pairs: list[tuple[str, str]] = []
    for citation in citations:
        if not isinstance(citation, dict):
            return False, False, None, None, "Citation entry is not an object"
        doc_id = str(citation.get("doc_id", "")).strip()
        chunk_id = str(citation.get("chunk_id", "")).strip()
        if not doc_id or not chunk_id:
            return False, False, None, None, "Citation missing doc_id or chunk_id"
        citation_pairs.append((doc_id, chunk_id))

    invalid_pairs = [pair for pair in citation_pairs if pair not in valid_pairs]
    citation_valid = not invalid_pairs and (bool(citation_pairs) or case.expect_unanswerable)

    actual_doc_id = citation_pairs[0][0] if citation_pairs else None
    expected_ok = case.expected_doc_id is None or case.expected_doc_id == actual_doc_id

    max_latency = case.max_latency_ms
    if max_latency is None:
        max_latency = default_max_latency_ms
    latency_ok = latency_ms <= max_latency

    notes: list[str] = []
    unanswerable_ok: bool | None = None
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

    if not latency_ok:
        notes.append(f"Latency {latency_ms}ms exceeded threshold {max_latency}ms")

    if case.expect_unanswerable:
        passed = citation_valid and bool(unanswerable_ok) and latency_ok
    else:
        passed = citation_valid and expected_ok and latency_ok
    return passed, citation_valid, actual_doc_id, unanswerable_ok, "; ".join(notes) if notes else "ok"


def _has_unanswerable_phrase(answer: str) -> bool:
    normalized = " ".join(answer.lower().split())
    return any(pattern in normalized for pattern in UNANSWERABLE_PATTERNS)


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
        f"- Generated: `{_now_iso()}`",
        "",
        "| # | Type | Result | Latency (ms) | Citation Valid | Unanswerable OK | Expected Doc | Actual Doc | Question | Notes |",
        "|---|---|---|---:|---|---|---|---|---|---|",
    ]

    for index, row in enumerate(results, start=1):
        lines.append(
            "| {index} | {case_type} | {result} | {latency} | {citation_valid} | {unanswerable_ok} | {expected} | {actual} | {question} | {notes} |".format(
                index=index,
                case_type="unanswerable" if row.expect_unanswerable else "answerable",
                result="PASS" if row.passed else "FAIL",
                latency=row.latency_ms,
                citation_valid="yes" if row.citation_valid else "no",
                unanswerable_ok=(
                    "n/a"
                    if row.unanswerable_ok is None
                    else ("yes" if row.unanswerable_ok else "no")
                ),
                expected=(row.expected_doc_id or "-"),
                actual=(row.actual_doc_id or "-"),
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
        (run_id, "workflow_04_eval_gate", _now_iso(), input_hash),
    )
    conn.commit()


def mark_run_completed(conn: sqlite3.Connection, run_id: str, latency_ms: int, output_path: str | None) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='completed', ended_at=?, latency_ms=?, output_path=?
        WHERE run_id=?
        """,
        (_now_iso(), latency_ms, output_path, run_id),
    )
    conn.commit()


def mark_run_failed(conn: sqlite3.Connection, run_id: str, latency_ms: int) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='failed', ended_at=?, latency_ms=?
        WHERE run_id=?
        """,
        (_now_iso(), latency_ms, run_id),
    )
    conn.commit()


def _table_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
                default_max_latency_ms=settings.default_max_latency_ms,
            )
            for case in cases
        ]

        pass_count = sum(1 for row in results if row.passed)
        total = len(results)
        artifact_path: Path | None = None

        if not args.dry_run:
            run_date = _now_iso()
            write_results(conn=conn, run_id=run_id, results=results, run_date=run_date)
            artifact_path = settings.artifacts_dir / f"{_stamp()}_{run_id}.md"
            write_markdown_artifact(artifact_path=artifact_path, results=results, run_id=run_id, backend=args.backend)

        latency_ms = int((time.perf_counter() - started) * 1000)
        if conn is not None:
            mark_run_completed(conn, run_id, latency_ms, str(artifact_path.resolve()) if artifact_path else None)

        summary = {
            "run_id": run_id,
            "status": "pass" if pass_count == total else "fail",
            "backend": args.backend,
            "webhook_url": webhook_url if args.backend == "webhook" else None,
            "passed": pass_count,
            "total": total,
            "unanswerable_passed": sum(1 for row in results if row.expect_unanswerable and row.passed),
            "unanswerable_total": sum(1 for row in results if row.expect_unanswerable),
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
