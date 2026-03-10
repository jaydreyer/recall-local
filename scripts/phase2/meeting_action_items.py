#!/usr/bin/env python3
"""Workflow 03 Meeting -> Action Items runner for Recall.local."""

from __future__ import annotations

import argparse
import hashlib
import importlib
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
from scripts.phase1.ingestion_pipeline import qdrant_client_from_env  # noqa: E402
from scripts.validate_output import ValidationResult, validate_meeting_output  # noqa: E402


@dataclass
class MeetingSettings:
    db_path: Path
    artifacts_dir: Path
    prompt_path: Path
    retry_prompt_path: Path
    qdrant_host: str
    qdrant_collection: str
    max_retries: int
    temperature: float


def load_settings() -> MeetingSettings:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    max_retries = int(os.getenv("RECALL_MEETING_MAX_RETRIES", "1"))
    temperature = float(os.getenv("RECALL_MEETING_TEMPERATURE", "0.2"))
    if max_retries < 0:
        raise ValueError("RECALL_MEETING_MAX_RETRIES cannot be negative")

    artifacts_root = _safe_dir_from_env(
        env_var="DATA_ARTIFACTS",
        fallback=ROOT / "data" / "artifacts",
    )
    db_path = _safe_file_path_from_env(
        env_var="RECALL_DB_PATH",
        fallback=ROOT / "data" / "recall.db",
    )
    return MeetingSettings(
        db_path=db_path,
        artifacts_dir=artifacts_root / "meetings",
        prompt_path=ROOT / "prompts" / "workflow_03_meeting_extract.md",
        retry_prompt_path=ROOT / "prompts" / "workflow_03_meeting_extract_retry.md",
        qdrant_host=os.getenv("QDRANT_HOST", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "recall_docs"),
        max_retries=max_retries,
        temperature=temperature,
    )


def run_meeting_action_items(
    transcript: str,
    *,
    meeting_title: str | None = None,
    source_channel: str = "webhook",
    source_ref: str | None = None,
    tags: list[str] | None = None,
    max_retries: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = load_settings()
    retries = settings.max_retries if max_retries is None else max_retries
    if retries < 0:
        raise ValueError("max_retries cannot be negative")

    cleaned_transcript = transcript.strip()
    if not cleaned_transcript:
        raise ValueError("Transcript must be non-empty")

    normalized_title = (meeting_title or "").strip() or "Untitled Meeting"
    normalized_source = source_ref or f"meeting:{source_channel}"
    normalized_tags = _dedupe_tags(tags or [])

    started_at = _now_iso()
    started_perf = time.perf_counter()
    run_id = uuid.uuid4().hex

    conn: sqlite3.Connection | None = None
    if not dry_run:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(settings.db_path)
        _insert_run_started(
            conn=conn,
            run_id=run_id,
            transcript=cleaned_transcript,
            title=normalized_title,
            started_at=started_at,
        )

    try:
        response, attempts_used = _generate_validated_meeting_output(
            transcript=cleaned_transcript,
            title=normalized_title,
            max_retries=retries,
            temperature=settings.temperature,
            prompt_path=settings.prompt_path,
            retry_prompt_path=settings.retry_prompt_path,
        )

        artifact_path: str | None = None
        summary_doc_id: str | None = None
        summary_chunk_id: str | None = None

        if not dry_run:
            artifact_path = _write_markdown_artifact(
                settings=settings,
                run_id=run_id,
                payload=response,
                source_channel=source_channel,
                source_ref=normalized_source,
                tags=normalized_tags,
            )
            summary_doc_id, summary_chunk_id = _upsert_meeting_summary(
                settings=settings,
                run_id=run_id,
                title=response["meeting_title"],
                summary=response["summary"],
                decisions=response["decisions"],
                action_items=response["action_items"],
                risks=response["risks"],
                follow_ups=response["follow_ups"],
                source_channel=source_channel,
                source_ref=normalized_source,
                tags=normalized_tags,
            )

        latency_ms = int((time.perf_counter() - started_perf) * 1000)
        provider = os.getenv("RECALL_LLM_PROVIDER", "ollama")
        response["audit"] = {
            "run_id": run_id,
            "timestamp": _now_iso(),
            "workflow": "workflow_03_meeting_action_items",
            "provider": provider,
            "model": _active_model_name(provider),
            "attempts": attempts_used,
            "latency_ms": latency_ms,
            "dry_run": dry_run,
            "source_channel": source_channel,
            "source_ref": normalized_source,
            "tags": normalized_tags,
            "artifact_path": artifact_path,
            "summary_doc_id": summary_doc_id,
            "summary_chunk_id": summary_chunk_id,
        }

        if conn is not None:
            _mark_run_completed(
                conn=conn,
                run_id=run_id,
                ended_at=_now_iso(),
                latency_ms=latency_ms,
                model=response["audit"]["model"],
                output_path=artifact_path,
            )

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


def _generate_validated_meeting_output(
    *,
    transcript: str,
    title: str,
    max_retries: int,
    temperature: float,
    prompt_path: Path,
    retry_prompt_path: Path,
) -> tuple[dict[str, Any], int]:
    primary_template = _load_prompt(
        prompt_path,
        fallback=(
            "Extract decisions, action_items, risks, follow_ups, and summary from the transcript. "
            "Return strict JSON only."
        ),
    )
    retry_template = _load_prompt(
        retry_prompt_path,
        fallback=(
            "Your prior response failed validation. Return strict JSON only and ensure every action item "
            "includes owner, due_date, and description."
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
            meeting_title=title,
            transcript=transcript,
            previous_response=previous_response,
            validation_errors=previous_errors,
        )
        raw_response = llm_client.generate(
            prompt=prompt,
            temperature=0.1 if is_retry else temperature,
        )
        validation = validate_meeting_output(raw_response)
        if validation.valid:
            break
        previous_response = raw_response
        previous_errors = validation.errors

    if validation is None or not validation.valid or not validation.parsed_response:
        fallback_summary = "Meeting extraction fallback used because model output failed validation."
        if validation and validation.errors:
            fallback_summary = f"{fallback_summary} Errors: {'; '.join(validation.errors)}"
        return _fallback_response(title=title, summary=fallback_summary), attempts_used

    parsed = validation.parsed_response
    return (
        {
            "meeting_title": str(parsed.get("meeting_title", "")).strip() or title,
            "summary": str(parsed.get("summary", "")).strip(),
            "decisions": [str(item).strip() for item in parsed.get("decisions", []) if str(item).strip()],
            "action_items": [
                {
                    "owner": str(item.get("owner", "")).strip(),
                    "due_date": str(item.get("due_date", "")).strip(),
                    "description": str(item.get("description", "")).strip(),
                }
                for item in parsed.get("action_items", [])
                if isinstance(item, dict)
            ],
            "risks": [str(item).strip() for item in parsed.get("risks", []) if str(item).strip()],
            "follow_ups": [str(item).strip() for item in parsed.get("follow_ups", []) if str(item).strip()],
        },
        attempts_used,
    )


def _fallback_response(*, title: str, summary: str) -> dict[str, Any]:
    return {
        "meeting_title": title,
        "summary": summary,
        "decisions": [],
        "action_items": [
            {
                "owner": "unspecified",
                "due_date": "unspecified",
                "description": "Manual review required: extraction fallback used.",
            }
        ],
        "risks": ["Extraction quality fallback triggered; verify transcript manually."],
        "follow_ups": ["Rerun Workflow 03 after prompt/model verification."],
    }


def _write_markdown_artifact(
    *,
    settings: MeetingSettings,
    run_id: str,
    payload: dict[str, Any],
    source_channel: str,
    source_ref: str,
    tags: list[str],
) -> str:
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = settings.artifacts_dir / f"{_artifact_stamp()}_{run_id}.md"

    lines: list[str] = []
    lines.append(f"# {payload['meeting_title']}")
    lines.append("")
    lines.append(f"- run_id: `{run_id}`")
    lines.append(f"- generated_at: `{_now_iso()}`")
    lines.append(f"- source_channel: `{source_channel}`")
    lines.append(f"- source_ref: `{source_ref}`")
    lines.append(f"- tags: `{', '.join(tags) if tags else 'none'}`")
    lines.append("")
    lines.append("## Summary")
    lines.append(payload["summary"] or "No summary provided.")
    lines.append("")
    lines.append("## Decisions")
    decisions = payload.get("decisions", [])
    if decisions:
        for decision in decisions:
            lines.append(f"- {decision}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Action Items")
    action_items = payload.get("action_items", [])
    if action_items:
        for item in action_items:
            lines.append(
                f"- owner: {item.get('owner', 'unspecified')} | due_date: {item.get('due_date', 'unspecified')} | "
                f"description: {item.get('description', 'unspecified')}"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Risks")
    risks = payload.get("risks", [])
    if risks:
        for risk in risks:
            lines.append(f"- {risk}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Follow-ups")
    follow_ups = payload.get("follow_ups", [])
    if follow_ups:
        for follow_up in follow_ups:
            lines.append(f"- {follow_up}")
    else:
        lines.append("- none")
    lines.append("")

    artifact_path.write_text("\n".join(lines), encoding="utf-8")
    return str(artifact_path.resolve())


def _upsert_meeting_summary(
    *,
    settings: MeetingSettings,
    run_id: str,
    title: str,
    summary: str,
    decisions: list[str],
    action_items: list[dict[str, str]],
    risks: list[str],
    follow_ups: list[str],
    source_channel: str,
    source_ref: str,
    tags: list[str],
) -> tuple[str, str]:
    models_module = _require_module("qdrant_client.models", "pip install -r requirements.txt")
    PointStruct = models_module.PointStruct

    doc_id = uuid.uuid4().hex
    chunk_id = f"{doc_id}:0000"
    summary_text = _build_meeting_summary_text(
        title=title,
        summary=summary,
        decisions=decisions,
        action_items=action_items,
        risks=risks,
        follow_ups=follow_ups,
    )
    embedding = llm_client.embed(summary_text)
    created_at = _now_iso()
    payload = {
        "source": source_ref,
        "source_type": "meeting",
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "title": title,
        "created_at": created_at,
        "tags": tags,
        "ingestion_channel": source_channel,
        "text": summary_text,
        "metadata": {
            "workflow": "workflow_03_meeting_action_items",
            "run_id": run_id,
        },
    }
    point = PointStruct(id=str(uuid.uuid4()), vector=embedding, payload=payload)
    qdrant = qdrant_client_from_env(settings.qdrant_host)
    qdrant.upsert(collection_name=settings.qdrant_collection, points=[point])
    return doc_id, chunk_id


def _build_meeting_summary_text(
    *,
    title: str,
    summary: str,
    decisions: list[str],
    action_items: list[dict[str, str]],
    risks: list[str],
    follow_ups: list[str],
) -> str:
    lines: list[str] = [f"Meeting: {title}", "", "Summary:", summary or "No summary provided."]
    if decisions:
        lines.append("")
        lines.append("Decisions:")
        for item in decisions:
            lines.append(f"- {item}")
    if action_items:
        lines.append("")
        lines.append("Action Items:")
        for item in action_items:
            lines.append(
                f"- owner={item.get('owner', 'unspecified')}; due_date={item.get('due_date', 'unspecified')}; "
                f"description={item.get('description', 'unspecified')}"
            )
    if risks:
        lines.append("")
        lines.append("Risks:")
        for item in risks:
            lines.append(f"- {item}")
    if follow_ups:
        lines.append("")
        lines.append("Follow-ups:")
        for item in follow_ups:
            lines.append(f"- {item}")
    return "\n".join(lines).strip()


def _insert_run_started(
    *,
    conn: sqlite3.Connection,
    run_id: str,
    transcript: str,
    title: str,
    started_at: str,
) -> None:
    input_hash = hashlib.sha256(f"{title}|{transcript}".encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT INTO runs (run_id, workflow, status, started_at, input_hash)
        VALUES (?, ?, 'started', ?, ?)
        """,
        (run_id, "workflow_03_meeting_action_items", started_at, input_hash),
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


def _load_prompt(path: Path, *, fallback: str) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


def _render_prompt(
    *,
    template: str,
    meeting_title: str,
    transcript: str,
    previous_response: str,
    validation_errors: list[str],
) -> str:
    rendered = template.replace("{{MEETING_TITLE}}", meeting_title)
    rendered = rendered.replace("{{TRANSCRIPT}}", transcript)
    rendered = rendered.replace("{{PREVIOUS_RESPONSE}}", previous_response or "(none)")
    rendered = rendered.replace("{{VALIDATION_ERRORS}}", "\n".join(validation_errors) or "(none)")
    return rendered


def _dedupe_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags:
        tag = str(raw_tag).strip()
        if not tag:
            continue
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _active_model_name(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    if normalized == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if normalized == "gemini":
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")


def _require_module(module_name: str, install_hint: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Missing dependency '{module_name}'. Install with: {install_hint}") from exc


def _artifact_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Workflow 03 Meeting -> Action Items extraction.")
    transcript_group = parser.add_mutually_exclusive_group(required=True)
    transcript_group.add_argument("--transcript", help="Transcript text.")
    transcript_group.add_argument("--transcript-file", help="Path to transcript text file.")
    parser.add_argument("--meeting-title", default=None, help="Optional meeting title override.")
    parser.add_argument("--source", default="webhook", help="Source channel label.")
    parser.add_argument("--source-ref", default=None, help="Stable source reference for metadata.")
    parser.add_argument("--tags", default="", help="Comma-separated tags.")
    parser.add_argument("--max-retries", type=int, default=None, help="Override validation retry count.")
    parser.add_argument("--dry-run", action="store_true", help="Skip SQLite/Qdrant writes and artifact file creation.")
    return parser.parse_args()


def _load_transcript(args: argparse.Namespace) -> str:
    if args.transcript is not None:
        return args.transcript
    assert args.transcript_file is not None
    return Path(args.transcript_file).read_text(encoding="utf-8").strip()


def main() -> int:
    args = parse_args()
    try:
        transcript = _load_transcript(args)
        result = run_meeting_action_items(
            transcript,
            meeting_title=args.meeting_title,
            source_channel=args.source,
            source_ref=args.source_ref,
            tags=[part.strip() for part in args.tags.split(",") if part.strip()],
            max_retries=args.max_retries,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Meeting extraction failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
