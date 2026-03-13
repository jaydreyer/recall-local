#!/usr/bin/env python3
"""FastAPI bridge for Recall workflows when n8n Execute Command is unavailable."""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import httpx
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.channel_adapters import normalize_payload  # noqa: E402
from scripts.phase1.group_model import CANONICAL_GROUPS, normalize_group  # noqa: E402
from scripts.phase1.ingest_from_payload import payload_to_requests  # noqa: E402
from scripts.phase1.ingestion_pipeline import IngestRequest, ingest_request, qdrant_client_from_env  # noqa: E402
from scripts.phase1.observability import (  # noqa: E402
    current_request_id as obs_current_request_id,
)
from scripts.phase1.observability import current_trace_id_hex as obs_current_trace_id_hex  # noqa: E402
from scripts.phase1.observability import current_traceparent as obs_current_traceparent  # noqa: E402
from scripts.phase1.observability import init_observability  # noqa: E402
from scripts.phase1.observability import pop_request_id as obs_pop_request_id  # noqa: E402
from scripts.phase1.observability import push_request_id as obs_push_request_id  # noqa: E402
from scripts.phase1.rag_query import run_rag_query  # noqa: E402
from scripts.phase5.vault_sync import list_vault_tree, run_vault_sync_once  # noqa: E402
from scripts.phase2.meeting_action_items import run_meeting_action_items  # noqa: E402
from scripts.phase2.meeting_from_payload import payload_to_meeting_kwargs  # noqa: E402
from scripts.phase6 import storage as phase6_storage  # noqa: E402
from scripts.phase6.company_profiler import (  # noqa: E402
    get_company_profile as phase6_get_company_profile,
)
from scripts.phase6.company_profiler import list_company_profiles as phase6_list_company_profiles  # noqa: E402
from scripts.phase6.company_profiler import refresh_company_profile as phase6_refresh_company_profile  # noqa: E402
from scripts.phase6.company_profiler import upsert_tracked_company_config as phase6_upsert_tracked_company_config  # noqa: E402
from scripts.phase6.cover_letter_drafter import generate_cover_letter_draft as phase6_generate_cover_letter_draft  # noqa: E402
from scripts.phase6.gap_aggregator import aggregate_gaps as phase6_aggregate_gaps  # noqa: E402
from scripts.phase6.ingest_resume import ingest_resume as phase6_ingest_resume  # noqa: E402
from scripts.phase6.job_dedup import check_job_duplicate as phase6_check_job_duplicate  # noqa: E402
from scripts.phase6.job_discovery_runner import run_discovery as phase6_run_discovery  # noqa: E402
from scripts.phase6.job_evaluator import queue_job_evaluations as phase6_queue_job_evaluations  # noqa: E402
from scripts.phase6.job_metadata_extractor import extract_job_metadata as phase6_extract_job_metadata  # noqa: E402
from scripts.phase6.job_metadata_extractor import looks_like_job_url as phase6_looks_like_job_url  # noqa: E402
from scripts.phase6.job_repository import all_jobs as phase6_all_jobs  # noqa: E402
from scripts.phase6.job_repository import get_job as phase6_get_job  # noqa: E402
from scripts.phase6.job_repository import job_stats as phase6_job_stats  # noqa: E402
from scripts.phase6.job_repository import list_jobs as phase6_list_jobs  # noqa: E402
from scripts.phase6.job_repository import update_company_tier as phase6_update_company_tier  # noqa: E402
from scripts.phase6.job_repository import update_job as phase6_update_job  # noqa: E402
from scripts.phase6.setup_collections import ensure_phase6_collections as phase6_ensure_collections  # noqa: E402


ALLOWED_INGEST_CHANNELS = ("webhook", "bookmarklet", "ios-share", "gmail-forward")
API_NAME = "operations-v1"
API_MAJOR_VERSION = "v1"
API_PREFIX = f"/{API_MAJOR_VERSION}"
AUTO_TAG_RULES_PATH = ROOT / "config" / "auto_tag_rules.json"
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 120
RATE_LIMIT_WINDOW_ENV = "RECALL_API_RATE_LIMIT_WINDOW_SECONDS"
RATE_LIMIT_MAX_REQUESTS_ENV = "RECALL_API_RATE_LIMIT_MAX_REQUESTS"
MAX_UPLOAD_MB_ENV = "RECALL_MAX_UPLOAD_MB"
DEFAULT_MAX_UPLOAD_MB = 50
UPLOAD_CHUNK_BYTES = 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".eml"}
DEFAULT_ACTIVITY_LIMIT = 25
DEFAULT_RECENT_EVAL_RUNS = 5
DEFAULT_EVAL_RUN_TIMEOUT_SECONDS = 900
DEFAULT_CORS_ORIGINS = ""
CANONICAL_GROUP_ENUM = list(CANONICAL_GROUPS)
PHASE6_JOB_STATUSES = {"new", "evaluated", "applied", "dismissed", "expired", "error"}
PHASE6_JOB_SOURCES = {"jobspy", "adzuna", "serpapi", "career_page", "chrome_extension"}
DEFAULT_OLLAMA_PULL_TIMEOUT_SECONDS = 900.0
DEFAULT_DASHBOARD_WARM_INTERVAL_SECONDS = 300


class InMemoryRateLimiter:
    """Per-client fixed-window rate limiter."""

    def __init__(self, *, window_seconds: int, max_requests: int):
        self.window_seconds = max(window_seconds, 1)
        self.max_requests = max(max_requests, 1)
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, *, client_id: str) -> tuple[bool, int]:
        now = time.monotonic()
        window_start = now - self.window_seconds
        with self._lock:
            client_events = self._events.setdefault(client_id, deque())
            while client_events and client_events[0] <= window_start:
                client_events.popleft()

            if len(client_events) >= self.max_requests:
                retry_after_seconds = max(1, int(math.ceil((client_events[0] + self.window_seconds) - now)))
                return False, retry_after_seconds

            client_events.append(now)
            return True, 0


class DashboardCacheWarmer:
    """Background cache warmer for dashboard-critical bridge endpoints."""

    def __init__(self, *, interval_seconds: int):
        self.interval_seconds = max(interval_seconds, 30)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.last_started_at: str | None = None
        self.last_completed_at: str | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="dashboard-cache-warmer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "interval_seconds": self.interval_seconds,
                "last_started_at": self.last_started_at,
                "last_completed_at": self.last_completed_at,
                "last_error": self.last_error,
            }

    def warm_once(self) -> None:
        started_at = _now_iso()
        with self._lock:
            self.last_started_at = started_at
            self.last_error = None
        try:
            jobs = phase6_all_jobs()
            phase6_job_stats()
            phase6_list_jobs(status="all", limit=60, include_details=False)
            phase6_list_company_profiles(jobs, include_jobs=False, limit=300)
            phase6_aggregate_gaps(jobs)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self.last_error = str(exc)
            return
        with self._lock:
            self.last_completed_at = _now_iso()

    def _run(self) -> None:
        self.warm_once()
        while not self._stop_event.wait(self.interval_seconds):
            self.warm_once()


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(..., description="Bridge health status.")


class DashboardCheckSection(BaseModel):
    status: Literal["ok", "degraded"] = Field(..., description="Section status for the dashboard readiness check.")
    count: Optional[int] = Field(default=None, description="Count of records or items loaded for this section.")
    detail: Optional[str] = Field(default=None, description="Short human-readable summary for this section.")
    latency_ms: int = Field(..., description="Time spent loading this section in milliseconds.")


class DashboardChecksResponse(BaseModel):
    workflow: Literal["workflow_06a_dashboard_checks"]
    status: Literal["ok", "degraded"]
    checked_at: str
    jobs: DashboardCheckSection
    companies: DashboardCheckSection
    gaps: Optional[DashboardCheckSection] = None
    cache_warmer: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    field: Optional[str] = Field(default=None, description="Field name related to the issue, when applicable.")
    issue: str = Field(..., description="Problem description.")


class ErrorEnvelope(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="Human-readable summary of the failure.")
    details: list[ErrorDetail] = Field(default_factory=list, description="Optional field-level details.")
    requestId: str = Field(..., description="Server-generated request identifier for troubleshooting.")


class ErrorResponse(BaseModel):
    error: ErrorEnvelope


class IngestWorkflowResponse(BaseModel):
    workflow: Literal["workflow_01_ingestion"]
    channel: str
    normalized_payload: dict[str, Any]
    ingested: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    dry_run: bool
    job_pipeline: list[dict[str, Any]] = Field(default_factory=list)


class FileIngestionResponse(BaseModel):
    workflow: Literal["workflow_01_ingestion_file"]
    status: Literal["accepted"]
    filename: str
    stored_path: str
    group: str
    tags: list[str] = Field(default_factory=list)
    save_to_vault: bool
    dry_run: bool
    ingested: list[dict[str, Any]]
    errors: list[dict[str, Any]] = Field(default_factory=list)


class RagWorkflowResponse(BaseModel):
    workflow: Literal["workflow_02_rag_query"]
    dry_run: bool
    result: dict[str, Any]


class MeetingWorkflowResponse(BaseModel):
    workflow: Literal["workflow_03_meeting_action_items"]
    dry_run: bool
    result: dict[str, Any]


class VaultTreeResponse(BaseModel):
    workflow: Literal["workflow_05c_vault_tree"]
    vault_path: str
    generated_at: str
    file_count: int
    tree: dict[str, Any]
    files: list[dict[str, Any]]


class VaultSyncResponse(BaseModel):
    workflow: Literal["workflow_05c_vault_sync"]
    mode: Literal["once"]
    dry_run: bool
    vault_path: str
    state_db_path: str
    scanned_files: int
    changed_files: int
    skipped_unchanged_files: int
    removed_files: int
    ingested_files: int
    errors: list[dict[str, Any]]
    ingested: list[dict[str, Any]]
    synced_at: str
    write_back_report: Optional[str] = None


class ActivityItem(BaseModel):
    ingest_id: str
    source_type: str
    source_ref: Optional[str] = None
    channel: str
    doc_id: Optional[str] = None
    chunks_created: int
    status: str
    timestamp: str
    group: str = Field(..., description="Canonical group for the ingestion event.")
    tags: list[str] = Field(default_factory=list, description="Tag list persisted with the ingestion event.")


class ActivityResponse(BaseModel):
    workflow: Literal["workflow_05d_activity"]
    count: int
    limit: int
    filter_group: Optional[str] = None
    items: list[ActivityItem]


class EvaluationRunStatus(BaseModel):
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    suite: str
    backend: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None


class EvaluationLatestRun(BaseModel):
    run_date: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_latency_ms: Optional[float] = None


class EvaluationLatestResponse(BaseModel):
    workflow: Literal["workflow_05d_eval_latest"]
    latest: Optional[EvaluationLatestRun] = None
    recent: list[EvaluationLatestRun] = Field(default_factory=list)
    active_runs: list[EvaluationRunStatus] = Field(default_factory=list)


class EvaluationRunAcceptedResponse(BaseModel):
    workflow: Literal["workflow_05d_eval_run"]
    accepted: bool
    run: EvaluationRunStatus


class JobsCollectionResponse(BaseModel):
    workflow: Literal["workflow_06a_jobs"]
    total: int
    limit: int
    offset: int
    items: list[dict[str, Any]]


class JobEvaluationRunResponse(BaseModel):
    workflow: Literal["workflow_06a_job_evaluations"]
    queued: int
    run_id: str
    status: str
    job_ids: list[str]
    wait: bool = False
    evaluated: Optional[int] = None
    failed: Optional[int] = None
    results: list[dict[str, Any]] = Field(default_factory=list)


class ResumeIngestionResponse(BaseModel):
    workflow: Literal["workflow_06a_resume_ingestion"]
    version: int
    chunks: int
    ingested_at: str
    source: str
    dry_run: bool


class AutoTagGroup(BaseModel):
    id: str = Field(..., description="Stable group identifier.")
    label: str = Field(..., description="Display name for UI surfaces.")
    icon: str = Field(..., description="Icon token used by UI.")
    color: str = Field(..., description="Hex color used for badges.")


class AutoTagRulesResponse(BaseModel):
    groups: list[AutoTagGroup] = Field(..., description="Configured group options for classification.")
    url_patterns: dict[str, list[str]] = Field(
        default_factory=dict, description="Group-level URL match patterns for auto-detection."
    )
    url_tag_patterns: dict[str, list[str]] = Field(
        default_factory=dict, description="URL host patterns mapped to inferred tags."
    )
    title_patterns: dict[str, list[str]] = Field(
        default_factory=dict, description="Group-level title keyword patterns."
    )
    email_senders: dict[str, list[str]] = Field(
        default_factory=dict, description="Group-level email sender suffix patterns."
    )
    filename_patterns: dict[str, list[str]] = Field(
        default_factory=dict, description="Group-level filename keyword patterns."
    )
    vault_folders: dict[str, str] = Field(
        default_factory=dict, description="Vault folder name to group mapping."
    )
    suggested_tags: dict[str, list[str]] = Field(
        default_factory=dict, description="Group-level suggested tags shown in clients."
    )


ERROR_EXAMPLE_VALIDATION = {
    "error": {
        "code": "validation_failed",
        "message": "Missing required field: query.",
        "details": [{"field": "query", "issue": "value is required"}],
        "requestId": "req_a1b2c3d4e5f6",
    }
}

ERROR_EXAMPLE_UNAUTHORIZED = {
    "error": {
        "code": "unauthorized",
        "message": "API key missing or invalid.",
        "details": [],
        "requestId": "req_a1b2c3d4e5f6",
    }
}

ERROR_EXAMPLE_WORKFLOW = {
    "error": {
        "code": "workflow_failed",
        "message": "Workflow 02 failed: downstream provider timeout.",
        "details": [],
        "requestId": "req_a1b2c3d4e5f6",
    }
}

ERROR_EXAMPLE_RATE_LIMIT = {
    "error": {
        "code": "rate_limited",
        "message": "Rate limit exceeded for client.",
        "details": [{"field": "retry_after_seconds", "issue": "retry after 45 seconds"}],
        "requestId": "req_a1b2c3d4e5f6",
    }
}

ERROR_EXAMPLE_CONFIG_NOT_FOUND = {
    "error": {
        "code": "config_not_found",
        "message": "Auto-tag rules config not found.",
        "details": [{"field": "path", "issue": "missing file: config/auto_tag_rules.json"}],
        "requestId": "req_a1b2c3d4e5f6",
    }
}

ERROR_EXAMPLE_CONFIG_INVALID = {
    "error": {
        "code": "config_invalid",
        "message": "Auto-tag rules config is invalid JSON: Expecting ',' delimiter.",
        "details": [{"field": "path", "issue": "invalid file: config/auto_tag_rules.json"}],
        "requestId": "req_a1b2c3d4e5f6",
    }
}

AUTO_TAG_RULES_SUCCESS_EXAMPLE = {
    "groups": [
        {"id": "job-search", "label": "Job Search", "icon": "target", "color": "#f59e0b"},
        {"id": "learning", "label": "Learning", "icon": "book", "color": "#8b5cf6"},
    ],
    "url_patterns": {"job-search": ["linkedin.com/jobs"], "learning": ["arxiv.org"]},
    "url_tag_patterns": {"anthropic.com": ["anthropic"]},
    "title_patterns": {"meeting": ["meeting", "notes", "action items"]},
    "email_senders": {"job-search": ["@anthropic.com", "@openai.com"]},
    "filename_patterns": {"meeting": ["meeting", "transcript"]},
    "vault_folders": {"career": "job-search", "learning": "learning"},
    "suggested_tags": {"job-search": ["interview-prep", "job-description"]},
}

INGEST_SUCCESS_EXAMPLE = {
    "workflow": "workflow_01_ingestion",
    "channel": "bookmarklet",
    "normalized_payload": {
        "type": "url",
        "content": "https://example.com/job-posting",
        "group": "job-search",
        "source": "bookmarklet",
        "metadata": {"title": "Senior Solutions Engineer", "tags": ["job-search", "exampleco"]},
    },
    "ingested": [
        {
            "run_id": "4d4ee338de194f1d93f20e53f87fb2a0",
            "doc_id": "809d76ac5f8b4f7ca0f65f8a93e10382",
            "source_type": "url",
            "source_ref": "https://example.com/job-posting",
            "status": "ingested",
            "chunks_created": 3,
            "latency_ms": 872,
        }
    ],
    "errors": [],
    "dry_run": False,
    "job_pipeline": [
        {
            "request_index": 0,
            "routed": True,
            "url": "https://example.com/job-posting",
            "source": "career_page",
            "title": "Senior Solutions Engineer",
            "company": "ExampleCo",
            "new_job_ids": ["job_a1b2c3d4"],
            "discovery_run_id": "job_discovery_123abc",
            "evaluation_run_id": "job_eval_123abc",
        }
    ],
}

FILE_INGEST_SUCCESS_EXAMPLE = {
    "workflow": "workflow_01_ingestion_file",
    "status": "accepted",
    "filename": "meeting-notes.md",
    "stored_path": "/home/jaydreyer/recall-local/data/incoming/meeting-notes.md",
    "group": "meeting",
    "tags": ["standup", "action-items"],
    "save_to_vault": True,
    "dry_run": False,
    "ingested": [
        {
            "run_id": "run_file1",
            "doc_id": "doc_file1",
            "source_type": "file",
            "source_ref": "/home/jaydreyer/recall-local/data/incoming/meeting-notes.md",
            "status": "completed",
            "chunks_created": 2,
            "latency_ms": 420,
        }
    ],
    "errors": [],
}

RAG_SUCCESS_EXAMPLE = {
    "workflow": "workflow_02_rag_query",
    "dry_run": False,
    "result": {
        "answer": "Phase 5 starts with FastAPI migration and API hardening.",
        "citations": [{"doc_id": "plan-001", "chunk_id": "chunk-004"}],
        "audit": {
            "workflow": "workflow_02_rag_query",
            "mode": "default",
            "filter_group": "reference",
            "filter_tags": [],
            "latency_ms": 1542,
            "run_id": "5dc39f6f34a4492a9815570bde204f3a",
        },
    },
}

MEETING_SUCCESS_EXAMPLE = {
    "workflow": "workflow_03_meeting_action_items",
    "dry_run": False,
    "result": {
        "meeting_title": "Phase 5 API cleanup",
        "summary": "Reviewed API gaps and assigned documentation cleanup tasks.",
        "decisions": ["Adopt noun-based canonical endpoint paths."],
        "action_items": [
            {
                "owner": "Jay",
                "due_date": "2026-02-26",
                "description": "Finalize strict request/response schemas for canonical endpoints.",
            }
        ],
        "risks": ["Legacy clients may still reference alias paths."],
        "follow_ups": ["Publish migration note for consumers."],
        "audit": {"workflow": "workflow_03_meeting_action_items", "run_id": "53a0f080996742bcbf19ad6eeab11f57"},
    },
}

VAULT_TREE_SUCCESS_EXAMPLE = {
    "workflow": "workflow_05c_vault_tree",
    "vault_path": "/home/jaydreyer/obsidian-vault",
    "generated_at": "2026-02-24T18:35:12+00:00",
    "file_count": 2,
    "tree": {
        "name": ".",
        "type": "directory",
        "children": [
            {
                "name": "career",
                "type": "directory",
                "children": [{"name": "anthropic-prep.md", "type": "file", "path": "career/anthropic-prep.md"}],
            },
            {"name": "daily.md", "type": "file", "path": "daily.md"},
        ],
    },
    "files": [
        {
            "path": "career/anthropic-prep.md",
            "title": "Anthropic Interview Prep",
            "group": "job-search",
            "modified_at": "2026-02-24T18:30:00+00:00",
        },
        {"path": "daily.md", "title": "daily", "group": "reference", "modified_at": "2026-02-24T18:10:00+00:00"},
    ],
}

VAULT_SYNC_SUCCESS_EXAMPLE = {
    "workflow": "workflow_05c_vault_sync",
    "mode": "once",
    "dry_run": False,
    "vault_path": "/home/jaydreyer/obsidian-vault",
    "state_db_path": "/home/jaydreyer/recall-local/data/vault_sync_state.db",
    "scanned_files": 10,
    "changed_files": 2,
    "skipped_unchanged_files": 8,
    "removed_files": 0,
    "ingested_files": 2,
    "errors": [],
    "ingested": [
        {
            "vault_path": "career/anthropic-prep.md",
            "group": "job-search",
            "tags": ["anthropic", "interview"],
            "wiki_links": ["Behavioral Questions"],
            "status": "completed",
            "run_id": "run_abc123",
            "doc_id": "doc_abc123",
        }
    ],
    "synced_at": "2026-02-24T18:36:01+00:00",
}

ACTIVITY_SUCCESS_EXAMPLE = {
    "workflow": "workflow_05d_activity",
    "count": 2,
    "limit": 25,
    "filter_group": "job-search",
    "items": [
        {
            "ingest_id": "d47f3b0f6f45444d9e8a99dd3f71bfcb",
            "source_type": "url",
            "source_ref": "https://anthropic.com/careers/solutions-engineer",
            "channel": "bookmarklet",
            "doc_id": "809d76ac5f8b4f7ca0f65f8a93e10382",
            "chunks_created": 4,
            "status": "completed",
            "timestamp": "2026-02-24T18:40:00+00:00",
            "group": "job-search",
            "tags": ["anthropic", "se-role"],
        },
        {
            "ingest_id": "af6f3f4f9bf1455ebea9099cd3d8a0e0",
            "source_type": "gdoc",
            "source_ref": "https://docs.google.com/document/d/abc123/edit",
            "channel": "webhook",
            "doc_id": "1d4caf80e0f94431ba7ef6e6d58fd6e2",
            "chunks_created": 7,
            "status": "completed",
            "timestamp": "2026-02-24T17:22:10+00:00",
            "group": "job-search",
            "tags": ["interview-prep"],
        },
    ],
}

EVAL_LATEST_SUCCESS_EXAMPLE = {
    "workflow": "workflow_05d_eval_latest",
    "latest": {
        "run_date": "2026-02-24T09:15:00+00:00",
        "total": 15,
        "passed": 14,
        "failed": 1,
        "pass_rate": 0.9333,
        "avg_latency_ms": 1338.6,
    },
    "recent": [
        {
            "run_date": "2026-02-24T09:15:00+00:00",
            "total": 15,
            "passed": 14,
            "failed": 1,
            "pass_rate": 0.9333,
            "avg_latency_ms": 1338.6,
        }
    ],
    "active_runs": [
        {
            "run_id": "eval_a1b2c3d4e5f6",
            "status": "running",
            "suite": "job-search",
            "backend": "webhook",
            "started_at": "2026-02-24T09:20:00+00:00",
            "ended_at": None,
            "error": None,
            "result": None,
        }
    ],
}

EVAL_RUN_ACCEPTED_EXAMPLE = {
    "workflow": "workflow_05d_eval_run",
    "accepted": True,
    "run": {
        "run_id": "eval_a1b2c3d4e5f6",
        "status": "queued",
        "suite": "core",
        "backend": "webhook",
        "started_at": None,
        "ended_at": None,
        "error": None,
        "result": None,
    },
}

EVAL_RUN_COMPLETED_EXAMPLE = {
    "workflow": "workflow_05d_eval_run",
    "accepted": True,
    "run": {
        "run_id": "eval_a1b2c3d4e5f6",
        "status": "completed",
        "suite": "core",
        "backend": "webhook",
        "started_at": "2026-02-24T09:20:00+00:00",
        "ended_at": "2026-02-24T09:20:12+00:00",
        "error": None,
        "result": {
            "status": "pass",
            "passed": 10,
            "total": 10,
        },
    },
}

JOBS_LIST_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_jobs",
    "total": 2,
    "limit": 50,
    "offset": 0,
    "items": [
        {
            "jobId": "job_001",
            "title": "Senior Solutions Engineer",
            "company": "Anthropic",
            "status": "evaluated",
            "fit_score": 84,
            "source": "career_page",
            "observation": {
                "provider_sequence": "local",
                "location": {"preference_bucket": "remote"},
            },
        },
        {
            "jobId": "job_002",
            "title": "Solutions Architect",
            "company": "Postman",
            "status": "evaluated",
            "fit_score": 79,
            "source": "jobspy",
            "observation": {
                "provider_sequence": "local->cloud",
                "location": {"preference_bucket": "twin_cities"},
            },
        },
    ],
}

JOB_STATS_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_job_stats",
    "total_jobs": 12,
    "new_today": 4,
    "high_fit_count": 4,
    "average_fit_score": 68.3,
    "score_ranges": {"high": 4, "medium": 5, "low": 3, "unscored": 0},
    "score_distribution": [
        {"range": "0-24", "count": 1},
        {"range": "25-49", "count": 2},
        {"range": "50-74", "count": 5},
        {"range": "75-100", "count": 4},
    ],
    "by_source": {"jobspy": 7, "career_page": 3, "adzuna": 2},
    "by_day": {"2026-03-04": 6, "2026-03-03": 6},
}

JOB_EVALUATION_RUN_ACCEPTED_EXAMPLE = {
    "workflow": "workflow_06a_job_evaluations",
    "queued": 3,
    "run_id": "job_eval_1a2b3c4d5e6f",
    "status": "queued",
    "job_ids": ["job_001", "job_002", "job_003"],
    "wait": False,
    "message": "Job evaluation run queued.",
}

JOB_EVALUATION_RUN_COMPLETED_EXAMPLE = {
    "workflow": "workflow_06a_job_evaluations",
    "queued": 2,
    "run_id": "job_eval_1a2b3c4d5e6f",
    "status": "completed",
    "job_ids": ["job_001", "job_002"],
    "wait": True,
    "evaluated": 2,
    "failed": 0,
    "results": [
        {"job_id": "job_001", "status": "completed", "fit_score": 84},
        {"job_id": "job_002", "status": "completed", "fit_score": 76},
    ],
}

JOB_GAPS_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_job_gaps",
    "total_jobs": 12,
    "evaluated_jobs": 10,
    "total_jobs_analyzed": 10,
    "aggregated_gaps": [
        {
            "gap": "Kubernetes / container orchestration experience",
            "frequency": 5,
            "avg_severity": "moderate",
            "avg_severity_score": 2.1,
            "top_recommendations": [
                {
                    "type": "course",
                    "title": "Kubernetes for Developers",
                    "source": "KodeKloud",
                    "effort": "20 hours",
                }
            ],
            "variants": ["kubernetes experience", "k8s orchestration"],
        }
    ],
    "generated_at": "2026-03-04T19:10:00Z",
    "top_gaps": [{"skill": "kubernetes", "count": 5}, {"skill": "enterprise-ai", "count": 4}],
    "top_matching_skills": [{"skill": "api-strategy", "count": 7}, {"skill": "solution-design", "count": 6}],
    "recommended_focus": ["kubernetes", "enterprise-ai", "developer-advocacy"],
}

LLM_SETTINGS_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_llm_settings",
    "settings": {
        "evaluation_model": "local",
        "local_model": "llama3.2:3b",
        "cloud_provider": "anthropic",
        "cloud_model": "claude-sonnet-4-5-20250929",
        "auto_escalate": True,
        "escalate_threshold_gaps": 2,
        "escalate_threshold_rationale_words": 20,
    },
}

COVER_LETTER_DRAFT_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_cover_letter_draft",
    "draft_id": "cover_letter_job-001",
    "job_id": "job-001",
    "provider": "ollama",
    "model": "llama3.2:3b",
    "generated_at": "2026-03-06T16:00:00+00:00",
    "word_count": 278,
    "draft": "Dear Hiring Team,\n\nI am excited to apply for the Solutions Engineer role...",
    "saved_to_vault": False,
    "vault_path": None,
}

COMPANY_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_company_watchlist",
    "company_id": "airbnb",
    "company_name": "Airbnb",
    "tier": 1,
    "ats": "greenhouse",
    "board_id": "airbnb",
    "careers_url": "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs",
    "title_filter": ["solutions", "platform", "technical"],
    "your_connection": "Interview loop in progress.",
}

RESUME_SUCCESS_EXAMPLE = {
    "workflow": "workflow_06a_resume_ingestion",
    "version": 2,
    "chunks": 14,
    "ingested_at": "2026-03-04T12:10:00+00:00",
    "source": "/home/jaydreyer/resume.md",
    "dry_run": False,
}

EVAL_RUNS_LOCK = threading.Lock()
EVAL_RUNS: dict[str, dict[str, Any]] = {}

INGEST_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["channel"],
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Ingestion channel selector.",
                        "enum": list(ALLOWED_INGEST_CHANNELS),
                    },
                    "group": {
                        "type": "string",
                        "description": "Optional canonical ingestion group. Invalid values fall back to `reference`.",
                        "enum": CANONICAL_GROUP_ENUM,
                        "default": "reference",
                    },
                    "url": {"type": "string", "description": "Source URL for URL-based ingestion channels."},
                    "title": {"type": "string", "description": "Human-readable title."},
                    "text": {"type": "string", "description": "Optional body text to ingest directly."},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "source": {"type": "string"},
                    "source_key": {"type": "string"},
                    "replace_existing": {"type": "boolean"},
                },
                "additionalProperties": True,
            },
            "examples": {
                "bookmarklet": {
                    "summary": "Bookmarklet ingestion",
                    "value": {
                        "channel": "bookmarklet",
                        "url": "https://example.com/job-posting",
                        "title": "Senior Solutions Engineer",
                        "group": "job-search",
                        "text": "Role responsibilities and qualifications...",
                        "tags": ["job-search", "exampleco"],
                        "source": "bookmarklet",
                        "replace_existing": True,
                        "source_key": "job:exampleco:se",
                    },
                },
                "gmailForward": {
                    "summary": "Gmail forward ingestion",
                    "value": {
                        "channel": "gmail-forward",
                        "subject": "Interview Follow-up",
                        "from": "recruiter@exampleco.com",
                        "group": "job-search",
                        "body": "Thanks for your time...",
                        "tags": ["job-search", "recruiter"],
                        "source": "gmail-forward",
                    },
                },
            },
        }
    },
}

FILE_INGEST_REQUEST_BODY = {
    "required": True,
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["file"],
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": "Source file to ingest.",
                    },
                    "group": {
                        "type": "string",
                        "description": "Canonical ingestion group.",
                        "enum": CANONICAL_GROUP_ENUM,
                        "default": "reference",
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags.",
                        "example": "anthropic, interview-prep",
                    },
                    "save_to_vault": {
                        "type": "boolean",
                        "description": "If true, annotate ingestion metadata for vault write flows.",
                        "default": False,
                    },
                },
            }
        }
    },
}

RAG_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Question to answer."},
                    "top_k": {"type": "integer", "minimum": 1, "description": "Max chunks to retrieve."},
                    "min_score": {"type": "number", "description": "Retrieval score threshold."},
                    "max_retries": {"type": "integer", "minimum": 0, "description": "Structured output retry attempts."},
                    "mode": {"type": "string", "description": "Prompt mode (`default`, `job-search`, `learning`)."},
                    "filter_tags": {
                        "oneOf": [
                            {"type": "array", "items": {"type": "string"}},
                            {"type": "string"},
                        ],
                        "description": "Tag filter list or comma-separated string.",
                    },
                    "filter_tag_mode": {
                        "type": "string",
                        "enum": ["any", "all"],
                        "default": "any",
                        "description": "Tag matching mode (`any` matches one-or-more tags, `all` requires every tag).",
                    },
                    "filter_group": {
                        "type": "string",
                        "description": "Optional canonical group filter. Invalid values fall back to `reference`.",
                        "enum": CANONICAL_GROUP_ENUM,
                    },
                    "retrieval_mode": {"type": "string", "description": "Retrieval strategy (`vector` or `hybrid`)."},
                    "hybrid_alpha": {"type": "number", "minimum": 0, "maximum": 1},
                    "enable_reranker": {
                        "oneOf": [{"type": "boolean"}, {"type": "string"}, {"type": "integer"}],
                        "description": "Boolean-like value to enable post-retrieval reranking.",
                    },
                    "reranker_weight": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
            "examples": {
                "defaultMode": {
                    "summary": "Default mode query",
                    "value": {
                        "query": "Summarize key decisions from Phase 5 planning docs.",
                        "mode": "default",
                        "top_k": 5,
                        "min_score": 0.15,
                    },
                },
                "jobSearchMode": {
                    "summary": "Job-search query with filters",
                    "value": {
                        "query": "What should I emphasize for an Anthropic Solutions Engineer interview?",
                        "mode": "job-search",
                        "filter_group": "job-search",
                        "filter_tags": ["anthropic", "job-posting"],
                        "filter_tag_mode": "all",
                        "retrieval_mode": "hybrid",
                        "enable_reranker": True,
                        "top_k": 6,
                    },
                },
            },
        }
    },
}

MEETING_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["transcript"],
                "properties": {
                    "meeting_title": {"type": "string"},
                    "transcript": {"type": "string", "description": "Raw meeting transcript text."},
                    "source": {"type": "string"},
                    "source_ref": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
            "examples": {
                "planningMeeting": {
                    "summary": "Action-item extraction request",
                    "value": {
                        "meeting_title": "Phase 5 API cleanup",
                        "transcript": "Jay: Let's clean up API docs. Alex: I will own schema examples by Friday.",
                        "source": "meeting-notes",
                        "source_ref": "obsidian://phase5/api-cleanup",
                        "tags": ["meeting", "phase5"],
                    },
                }
            },
        }
    },
}

VAULT_SYNC_REQUEST_BODY = {
    "required": False,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "dry_run": {
                        "oneOf": [{"type": "boolean"}, {"type": "string"}, {"type": "integer"}],
                        "description": "If true, run sync without durable ingestion/state writes.",
                    },
                    "max_files": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Optional cap on files processed for this sync request.",
                    },
                    "vault_path": {
                        "type": "string",
                        "description": "Optional path override for RECALL_VAULT_PATH.",
                    },
                },
                "additionalProperties": False,
            },
            "examples": {
                "defaultSync": {"summary": "Normal sync run", "value": {}},
                "dryRunLimited": {
                    "summary": "Dry-run sync with cap",
                    "value": {"dry_run": True, "max_files": 25},
                },
            },
        }
    },
}

EVAL_RUN_REQUEST_BODY = {
    "required": False,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "suite": {
                        "type": "string",
                        "description": "Eval suite selector.",
                        "enum": ["core", "job-search", "learning", "both"],
                        "default": "core",
                    },
                    "backend": {
                        "type": "string",
                        "description": "Execution backend passed to run_eval.py.",
                        "enum": ["webhook", "direct"],
                        "default": "webhook",
                    },
                    "webhook_url": {
                        "type": "string",
                        "description": "Optional webhook URL override when backend=webhook.",
                    },
                    "dry_run": {
                        "oneOf": [{"type": "boolean"}, {"type": "string"}, {"type": "integer"}],
                        "description": "If true, skip SQLite and artifact writes in run_eval.py.",
                    },
                    "wait": {
                        "oneOf": [{"type": "boolean"}, {"type": "string"}, {"type": "integer"}],
                        "description": "If true, wait for completion and return final result.",
                    },
                },
                "additionalProperties": False,
            },
            "examples": {
                "asyncCore": {"summary": "Queue async core suite run", "value": {"suite": "core"}},
                "syncJobSearch": {
                    "summary": "Run job-search suite synchronously",
                    "value": {"suite": "job-search", "wait": True, "backend": "webhook"},
                },
            },
        }
    },
}

JOB_EVALUATION_RUN_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["job_ids"],
                "properties": {
                    "job_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "One or more job identifiers to evaluate.",
                    },
                    "wait": {
                        "oneOf": [{"type": "boolean"}, {"type": "string"}, {"type": "integer"}],
                        "description": "If true, run synchronously.",
                        "default": False,
                    },
                    "settings": {
                        "type": "object",
                        "description": "Optional settings override for this run.",
                        "additionalProperties": True,
                    },
                },
                "additionalProperties": False,
            },
            "examples": {
                "singleJob": {"value": {"job_ids": ["job_001"]}},
                "batchSync": {
                    "value": {
                        "job_ids": ["job_001", "job_002"],
                        "wait": True,
                        "settings": {"evaluation_model": "cloud"},
                    }
                },
            },
        }
    },
}

JOB_DEDUP_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "company_normalized": {"type": "string"},
                    "url": {"type": "string"},
                    "description": {"type": "string"},
                    "date_posted": {"type": "string", "format": "date-time"},
                    "discovered_at": {"type": "string", "format": "date-time"},
                    "similarity_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.92},
                },
                "additionalProperties": False,
                "anyOf": [
                    {"required": ["url"]},
                    {"required": ["description"]},
                    {"required": ["title", "company"]},
                ],
            }
        }
    },
}

JOB_DISCOVERY_RUN_REQUEST_BODY = {
    "required": False,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "titles": {"type": "array", "items": {"type": "string"}},
                    "locations": {"type": "array", "items": {"type": "string"}},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "sources": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(PHASE6_JOB_SOURCES - {"chrome_extension"})},
                    },
                    "max_queries": {"type": "integer", "minimum": 1, "maximum": 40, "default": 4},
                    "max_days_old": {"type": "integer", "minimum": 1, "maximum": 30, "default": 7},
                    "delay_seconds": {"type": "number", "minimum": 0, "default": 2.0},
                    "dry_run": {"type": "boolean", "default": False},
                    "similarity_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.92},
                    "source_limits": {
                        "type": "object",
                        "additionalProperties": {"type": "integer", "minimum": 1},
                    },
                    "jobs": {
                        "type": "array",
                        "description": "Optional normalized/partially-normalized jobs supplied by n8n (used by career-page workflow).",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "company": {"type": "string"},
                                "location": {"type": "string"},
                                "url": {"type": "string"},
                                "description": {"type": "string"},
                                "source": {"type": "string"},
                                "search_query": {"type": "string"},
                                "company_tier": {"type": "integer"},
                                "salary_min": {"type": "integer"},
                                "salary_max": {"type": "integer"},
                                "date_posted": {"type": "string", "format": "date-time"},
                            },
                            "required": ["title", "company"],
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            }
        }
    },
}

JOB_PATCH_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": sorted(PHASE6_JOB_STATUSES)},
                    "applied": {"type": "boolean"},
                    "dismissed": {"type": "boolean"},
                    "notes": {"type": "string"},
                },
                "additionalProperties": False,
            }
        }
    },
}

RESUME_REQUEST_BODY = {
    "required": False,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to resume file."},
                    "markdown": {"type": "string", "description": "Inline markdown resume text."},
                },
                "additionalProperties": False,
            }
        },
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "required": ["file"],
                "properties": {
                    "file": {"type": "string", "format": "binary"},
                },
            }
        },
    },
}

LLM_SETTINGS_PATCH_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "evaluation_model": {"type": "string", "enum": ["local", "cloud"]},
                    "local_model": {"type": "string"},
                    "cloud_provider": {"type": "string", "enum": ["anthropic", "openai", "gemini"]},
                    "cloud_model": {"type": "string"},
                    "auto_escalate": {"type": "boolean"},
                    "escalate_threshold_gaps": {"type": "integer", "minimum": 0},
                    "escalate_threshold_rationale_words": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            }
        }
    },
}

COVER_LETTER_DRAFT_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["job_id"],
                "properties": {
                    "job_id": {"type": "string", "description": "Evaluated job identifier."},
                    "save_to_vault": {"type": "boolean", "default": False},
                    "settings": {
                        "type": "object",
                        "description": "Optional runtime override for draft generation model settings.",
                        "properties": {
                            "evaluation_model": {"type": "string", "enum": ["local", "cloud"]},
                            "cloud_provider": {"type": "string", "enum": ["anthropic", "openai", "gemini"]},
                            "cloud_model": {"type": "string"},
                            "auto_escalate": {"type": "boolean"},
                            "local_model": {"type": "string"},
                            "max_tokens": {"type": "integer", "minimum": 256},
                        },
                        "additionalProperties": False,
                    },
                },
                "additionalProperties": False,
            },
            "examples": {
                "default": {
                    "summary": "Generate cover letter draft",
                    "value": {"job_id": "job_001", "save_to_vault": False},
                }
            },
        }
    },
}

COMPANY_CREATE_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["company_name"],
                "properties": {
                    "company_name": {"type": "string", "description": "Tracked company display name."},
                    "tier": {"type": "integer", "minimum": 1, "maximum": 3, "default": 3},
                    "ats": {"type": "string", "description": "Applicant tracking system identifier."},
                    "board_id": {"type": "string", "description": "Board identifier for ATS-backed company pages."},
                    "url": {"type": "string", "description": "Career page or ATS jobs URL."},
                    "title_filter": {"type": "array", "items": {"type": "string"}},
                    "your_connection": {"type": "string", "description": "Personal context shown in the profile."},
                },
                "additionalProperties": False,
            },
            "examples": {
                "greenhouse": {
                    "summary": "Create watched Greenhouse company",
                    "value": {
                        "company_name": "Airbnb",
                        "tier": 1,
                        "ats": "greenhouse",
                        "board_id": "airbnb",
                        "url": "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs",
                        "title_filter": ["solutions", "platform", "technical"],
                        "your_connection": "Interview loop in progress.",
                    },
                }
            },
        }
    },
}

COMPANY_PATCH_REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "tier": {"type": "integer", "minimum": 1, "maximum": 3},
                    "ats": {"type": "string"},
                    "board_id": {"type": "string"},
                    "url": {"type": "string"},
                    "title_filter": {"type": "array", "items": {"type": "string"}},
                    "your_connection": {"type": "string"},
                },
                "additionalProperties": False,
            },
            "examples": {
                "moveTier": {
                    "summary": "Move company to another tier",
                    "value": {"tier": 2, "your_connection": "Still in touch with the recruiter."},
                }
            },
        }
    },
}

RATE_LIMIT_ERROR_RESPONSE = {
    429: {
        "model": ErrorResponse,
        "description": "Too many requests in the active rate-limit window.",
        "content": {"application/json": {"example": ERROR_EXAMPLE_RATE_LIMIT}},
    }
}


def create_app() -> FastAPI:
    server_local = os.getenv("RECALL_API_SERVER_LOCAL", "http://localhost:8090").strip() or "http://localhost:8090"
    server_ai_lab = os.getenv("RECALL_API_SERVER_AI_LAB", "http://100.116.103.78:8090").strip() or "http://100.116.103.78:8090"
    rate_limit_window_seconds = _read_positive_int_env(RATE_LIMIT_WINDOW_ENV, DEFAULT_RATE_LIMIT_WINDOW_SECONDS)
    rate_limit_max_requests = _read_positive_int_env(RATE_LIMIT_MAX_REQUESTS_ENV, DEFAULT_RATE_LIMIT_MAX_REQUESTS)
    rate_limiter = InMemoryRateLimiter(
        window_seconds=rate_limit_window_seconds,
        max_requests=rate_limit_max_requests,
    )
    dashboard_cache_warmer = (
        DashboardCacheWarmer(
            interval_seconds=_read_positive_int_env(
                "RECALL_DASHBOARD_CACHE_WARM_INTERVAL_SECONDS",
                DEFAULT_DASHBOARD_WARM_INTERVAL_SECONDS,
            )
        )
        if _env_flag("RECALL_DASHBOARD_CACHE_WARMER", default=True)
        else None
    )
    observability = init_observability()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if _env_flag("RECALL_PRELOAD_OLLAMA_MODELS", default=True):
            _ensure_required_ollama_models()
        if dashboard_cache_warmer is not None:
            dashboard_cache_warmer.start()
        yield
        if dashboard_cache_warmer is not None:
            dashboard_cache_warmer.stop()

    app = FastAPI(
        title=API_NAME,
        version=API_MAJOR_VERSION,
        description=(
            "Recall.local bridge for ingestion, cited RAG querying, and meeting action extraction.\n\n"
            "Authentication: if `RECALL_API_KEY` is configured, send it via `X-API-Key`.\n"
            f"Rate limits: `{RATE_LIMIT_MAX_REQUESTS_ENV}` requests per `{RATE_LIMIT_WINDOW_ENV}` seconds."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        servers=[
            {"url": server_local, "description": f"{API_NAME} local"},
            {"url": server_ai_lab, "description": f"{API_NAME} ai-lab"},
        ],
        lifespan=lifespan,
        openapi_tags=[
            {"name": "Health", "description": "Service liveness endpoints."},
            {"name": "Dashboard", "description": "Readiness and smoke-check endpoints for the daily dashboard."},
            {"name": "Ingestions", "description": "Create ingestion operations from supported channels."},
            {"name": "RAG Queries", "description": "Run cited retrieval-augmented queries."},
            {"name": "Meeting Action Items", "description": "Extract action items and structured notes from meeting transcripts."},
            {"name": "Auto Tag Rules", "description": "Read shared auto-tag configuration for dashboard and extension clients."},
            {"name": "Vault", "description": "List vault notes and trigger Obsidian vault sync operations."},
            {"name": "Activities", "description": "Read recent ingestion activity for dashboard monitoring."},
            {"name": "Evaluations", "description": "Read latest eval metrics and trigger eval runs."},
            {"name": "Jobs", "description": "List, inspect, update, and aggregate discovered jobs."},
            {"name": "Resumes", "description": "Ingest and inspect resume versions used for job evaluation."},
            {"name": "Companies", "description": "List and refresh company profile summaries for job intelligence."},
            {"name": "LLM Settings", "description": "Read and update Phase 6 evaluation model settings."},
            {"name": "Cover Letter Drafts", "description": "Generate cover letter drafts from the current resume and job context."},
        ],
    )
    cors_origins = _cors_origins_from_env()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.observability = observability

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-Id", "").strip() or _generated_request_id()
        request.state.request_id = request_id
        request.state.request_started_at = time.monotonic()
        token = obs_push_request_id(request_id)
        span_name = f"{request.method} {request.url.path}"
        with observability.request_span(
            name=span_name,
            request_headers=request.headers,
            attributes={
                "http.method": request.method,
                "http.route": request.url.path,
                "http.target": str(request.url),
                "recall.request_id": request_id,
            },
        ) as span:
            try:
                response = await call_next(request)
            except Exception as exc:
                if span is not None:
                    span.record_exception(exc)
                    span.set_attribute("http.response.status_code", 500)
                raise
            finally:
                obs_pop_request_id(token)
            duration_ms = int((time.monotonic() - request.state.request_started_at) * 1000)
            if span is not None:
                span.set_attribute("http.response.status_code", response.status_code)
                span.set_attribute("recall.latency_ms", duration_ms)
            response.headers["X-Request-Id"] = request_id
            trace_id = obs_current_trace_id_hex()
            if trace_id:
                response.headers["X-Trace-Id"] = trace_id
            traceparent = obs_current_traceparent()
            if traceparent:
                response.headers["traceparent"] = traceparent
            return response

    @app.get(
        f"{API_PREFIX}/healthz",
        tags=["Health"],
        summary="Health check",
        description="Lightweight liveness probe for bridge service monitoring.",
        response_model=HealthResponse,
    )
    async def healthz_v1() -> JSONResponse:
        return _json_response(200, {"status": "ok"})

    @app.get(
        f"{API_PREFIX}/dashboard-checks",
        tags=["Dashboard"],
        summary="Get dashboard readiness checks",
        description=(
            "Runs lightweight dashboard-facing checks against jobs, companies, and optionally skill gaps. "
            "This endpoint is intended for operator smoke validation and demo-readiness checks."
        ),
        response_model=DashboardChecksResponse,
        responses={
            200: {"description": "Dashboard readiness checks completed."},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_dashboard_checks(
        request: Request,
        include_gaps: bool = Query(True, description="Include the skill-gap readiness check."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        payload = _dashboard_checks_payload(
            include_gaps=include_gaps,
            cache_warmer=dashboard_cache_warmer,
        )
        return _json_response(200, payload)

    @app.get(
        f"{API_PREFIX}/auto-tag-rules",
        tags=["Auto Tag Rules"],
        summary="Read auto-tag rules",
        description=(
            "Returns shared auto-tag configuration used by dashboard, browser extension, and vault sync "
            "flows for group and tag inference."
        ),
        response_model=AutoTagRulesResponse,
        responses={
            200: {"description": "Auto-tag rules loaded.", "content": {"application/json": {"example": AUTO_TAG_RULES_SUCCESS_EXAMPLE}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Auto-tag config file is missing.", "content": {"application/json": {"example": ERROR_EXAMPLE_CONFIG_NOT_FOUND}}},
            500: {"model": ErrorResponse, "description": "Auto-tag config could not be parsed.", "content": {"application/json": {"example": ERROR_EXAMPLE_CONFIG_INVALID}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_auto_tag_rules(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        return _read_auto_tag_rules(request_id=request_id)

    @app.post(
        f"{API_PREFIX}/ingestions",
        tags=["Ingestions"],
        summary="Create ingestion operation",
        description=(
            "Creates an ingestion operation for a supported channel. The `channel` field selects the adapter "
            "used to normalize the payload before ingestion."
        ),
        response_model=IngestWorkflowResponse,
        responses={
            200: {"description": "Ingestion operation completed.", "content": {"application/json": {"example": INGEST_SUCCESS_EXAMPLE}}},
            207: {"description": "Partial success; one or more ingestion requests failed.", "content": {"application/json": {"example": INGEST_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Validation or payload normalization failure.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": INGEST_REQUEST_BODY},
    )
    async def create_ingestion(
        request: Request,
        dry_run: bool = Query(False, description="If true, normalize and validate payload without persistence side effects."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        channel = str(payload.get("channel", "")).strip().lower()
        if not channel:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Missing required field: channel.",
                request_id=request_id,
                details=[{"field": "channel", "issue": "value is required"}],
            )

        payload_without_channel = dict(payload)
        payload_without_channel.pop("channel", None)
        return _process_ingestion(channel=channel, payload=payload_without_channel, dry_run=dry_run, request_id=request_id)

    @app.post(
        f"{API_PREFIX}/ingestions/files",
        tags=["Ingestions"],
        summary="Create file ingestion operation",
        description=(
            "Accepts a multipart file upload, stores it under incoming data, and ingests it "
            "as a canonical file source."
        ),
        response_model=FileIngestionResponse,
        responses={
            200: {"description": "File ingestion accepted.", "content": {"application/json": {"example": FILE_INGEST_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid form values.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            413: {"model": ErrorResponse, "description": "Uploaded file exceeds max allowed size.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            415: {"model": ErrorResponse, "description": "Unsupported media/file type.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            500: {"model": ErrorResponse, "description": "Ingestion workflow failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": FILE_INGEST_REQUEST_BODY},
    )
    async def create_file_ingestion(
        request: Request,
        file: UploadFile = File(..., description="File to ingest."),
        group: str = Form("reference"),
        tags: str = Form(""),
        save_to_vault: bool = Form(False),
        dry_run: bool = Query(False, description="If true, process upload without durable DB/vector writes."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        return await _process_file_upload(
            uploaded_file=file,
            group=group,
            tags=tags,
            save_to_vault=save_to_vault,
            dry_run=dry_run,
            request_id=request_id,
        )

    @app.post(
        f"{API_PREFIX}/rag-queries",
        tags=["RAG Queries"],
        summary="Create RAG query operation",
        description="Runs Workflow 02 against indexed memory and returns answer text, citations, and audit metadata.",
        response_model=RagWorkflowResponse,
        responses={
            200: {"description": "Query operation completed.", "content": {"application/json": {"example": RAG_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Missing query or invalid query options.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Workflow execution failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": RAG_REQUEST_BODY},
    )
    async def create_rag_query(
        request: Request,
        dry_run: bool = Query(False, description="If true, skip SQLite writes and artifact persistence."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        return _process_rag_query(payload=payload, dry_run=dry_run, request_id=request_id)

    @app.post(
        f"{API_PREFIX}/meeting-action-items",
        tags=["Meeting Action Items"],
        summary="Create meeting action-item extraction",
        description=(
            "Runs Workflow 03 to summarize a transcript into action items, decisions, risks, follow-ups, "
            "and audit metadata."
        ),
        response_model=MeetingWorkflowResponse,
        responses={
            200: {"description": "Meeting extraction completed.", "content": {"application/json": {"example": MEETING_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid or missing meeting payload fields.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Workflow execution failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": MEETING_REQUEST_BODY},
    )
    async def create_meeting_action_items(
        request: Request,
        dry_run: bool = Query(False, description="If true, run extraction without writing durable run artifacts."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        return _process_meeting_action_items(payload=payload, dry_run=dry_run, request_id=request_id)

    @app.get(
        f"{API_PREFIX}/vault-files",
        tags=["Vault"],
        summary="List vault files",
        description=(
            "Returns vault markdown notes as both a flat list and a directory tree representation. "
            "Excluded folders and Syncthing temp files are omitted."
        ),
        response_model=VaultTreeResponse,
        responses={
            200: {"description": "Vault tree generated.", "content": {"application/json": {"example": VAULT_TREE_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Vault path is missing or invalid.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Vault listing failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_vault_files(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = list_vault_tree()
        except (FileNotFoundError, NotADirectoryError) as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid vault configuration: {exc}",
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Vault listing failed: {exc}",
                request_id=request_id,
            )
        return _json_response(200, payload)

    @app.post(
        f"{API_PREFIX}/vault-syncs",
        tags=["Vault"],
        summary="Create vault sync operation",
        description=(
            "Runs one-shot vault sync with hash-based change detection and metadata extraction "
            "for wiki-links, hashtags, and frontmatter."
        ),
        response_model=VaultSyncResponse,
        responses={
            200: {"description": "Vault sync completed.", "content": {"application/json": {"example": VAULT_SYNC_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Sync options are invalid.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Vault sync execution failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": VAULT_SYNC_REQUEST_BODY},
    )
    async def create_vault_sync(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        try:
            dry_run_value = _normalize_bool(payload.get("dry_run", False), field_name="dry_run")
            max_files_value = _normalize_optional_positive_int(payload.get("max_files"))
            vault_path_value = _normalize_optional_string(payload.get("vault_path"))
        except ValueError as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid vault sync options: {exc}",
                request_id=request_id,
            )

        try:
            result = run_vault_sync_once(
                vault_path=vault_path_value,
                dry_run=dry_run_value,
                max_files=max_files_value,
            )
        except (FileNotFoundError, NotADirectoryError) as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid vault configuration: {exc}",
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Vault sync failed: {exc}",
                request_id=request_id,
            )
        return _json_response(200, result)

    @app.get(
        f"{API_PREFIX}/activities",
        tags=["Activities"],
        summary="List recent ingestion activity",
        description=(
            "Returns recent ingestion events from SQLite `ingestion_log`, including group/tag metadata "
            "when available."
        ),
        response_model=ActivityResponse,
        responses={
            200: {"description": "Recent activity loaded.", "content": {"application/json": {"example": ACTIVITY_SUCCESS_EXAMPLE}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Activity query failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_activities(
        request: Request,
        limit: int = Query(DEFAULT_ACTIVITY_LIMIT, ge=1, le=200, description="Max activity items to return."),
        group_filter: Optional[str] = Query(
            default=None,
            alias="group",
            description="Optional group filter (`job-search|learning|project|reference|meeting`).",
        ),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        normalized_group = _normalize_group_filter(group_filter)
        try:
            items = _read_recent_activity(limit=limit, filter_group=normalized_group)
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Activity query failed: {exc}",
                request_id=request_id,
            )
        return _json_response(
            200,
            {
                "workflow": "workflow_05d_activity",
                "count": len(items),
                "limit": limit,
                "filter_group": normalized_group,
                "items": items,
            },
        )

    @app.get(
        f"{API_PREFIX}/evaluations",
        tags=["Evaluations"],
        summary="List evaluation summaries",
        description=(
            "Returns evaluation aggregate metrics from SQLite `eval_results` plus currently active "
            "evaluation runs started through this bridge process. Pass `latest=true` to request only "
            "the newest summary."
        ),
        response_model=EvaluationLatestResponse,
        responses={
            200: {"description": "Evaluation summaries loaded.", "content": {"application/json": {"example": EVAL_LATEST_SUCCESS_EXAMPLE}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Eval summary query failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_evaluations(
        request: Request,
        limit: int = Query(DEFAULT_RECENT_EVAL_RUNS, ge=1, le=50, description="Number of recent summaries to return."),
        latest: bool = Query(False, description="If true, return only the latest evaluation summary."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            recent_limit = 1 if latest else limit
            latest_summary, recent = _read_latest_evaluations(recent_limit=recent_limit)
            if latest and latest_summary is not None:
                recent = [latest_summary]
            active_runs = _list_eval_runs(include_terminal=False)
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Eval summary query failed: {exc}",
                request_id=request_id,
            )
        return _json_response(
            200,
            {
                "workflow": "workflow_05d_eval_latest",
                "latest": latest_summary,
                "recent": recent,
                "active_runs": active_runs,
            },
        )

    @app.post(
        f"{API_PREFIX}/evaluation-runs",
        tags=["Evaluations"],
        summary="Create evaluation run",
        description=(
            "Queues or executes an eval run via `scripts/eval/run_eval.py`. "
            "Use `wait=true` to run synchronously and return the final summary."
        ),
        response_model=EvaluationRunAcceptedResponse,
        responses={
            200: {"description": "Synchronous eval run completed.", "content": {"application/json": {"example": EVAL_RUN_COMPLETED_EXAMPLE}}},
            202: {"description": "Async eval run accepted.", "content": {"application/json": {"example": EVAL_RUN_ACCEPTED_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid eval run options.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Eval run execution failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": EVAL_RUN_REQUEST_BODY},
    )
    async def create_evaluation_run(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        suite = str(payload.get("suite", "core")).strip().lower()
        if suite not in {"core", "job-search", "learning", "both"}:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid suite: {suite}",
                request_id=request_id,
                details=[{"field": "suite", "issue": "allowed values: core, job-search, learning, both"}],
            )

        backend = str(payload.get("backend", "webhook")).strip().lower()
        if backend not in {"webhook", "direct"}:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid backend: {backend}",
                request_id=request_id,
                details=[{"field": "backend", "issue": "allowed values: webhook, direct"}],
            )

        try:
            dry_run = _normalize_bool(payload.get("dry_run", False), field_name="dry_run")
            wait = _normalize_bool(payload.get("wait", False), field_name="wait")
            webhook_url = _normalize_optional_string(payload.get("webhook_url"))
        except ValueError as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid eval run options: {exc}",
                request_id=request_id,
            )

        eval_run_id = _queue_eval_run(suite=suite, backend=backend)
        if wait:
            _execute_eval_run(
                eval_run_id=eval_run_id,
                suite=suite,
                backend=backend,
                webhook_url=webhook_url,
                dry_run=dry_run,
            )
            run_state = _get_eval_run(eval_run_id)
            return _json_response(200, {"workflow": "workflow_05d_eval_run", "accepted": True, "run": run_state})

        thread = threading.Thread(
            target=_execute_eval_run,
            kwargs={
                "eval_run_id": eval_run_id,
                "suite": suite,
                "backend": backend,
                "webhook_url": webhook_url,
                "dry_run": dry_run,
            },
            daemon=True,
        )
        thread.start()
        run_state = _get_eval_run(eval_run_id)
        return _json_response(202, {"workflow": "workflow_05d_eval_run", "accepted": True, "run": run_state})

    @app.get(
        f"{API_PREFIX}/jobs",
        tags=["Jobs"],
        summary="List jobs",
        description=(
            "Lists jobs from `recall_jobs` with filtering, sorting, and pagination controls "
            "for the Daily Dashboard."
        ),
        response_model=JobsCollectionResponse,
        responses={
            200: {"description": "Jobs loaded.", "content": {"application/json": {"example": JOBS_LIST_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid list query options.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_jobs(
        request: Request,
        status: str = Query("evaluated", description="Filter by status."),
        min_score: int = Query(
            0,
            ge=-1,
            le=100,
            description="Minimum fit score. Use -1 to include unscored jobs in `status=new` views.",
        ),
        max_score: int = Query(100, ge=0, le=100, description="Maximum fit score."),
        company_tier: Optional[int] = Query(None, ge=1, le=3, description="Optional company tier filter."),
        source: Optional[str] = Query(None, description="Optional source filter."),
        search: Optional[str] = Query(
            None,
            description=(
                "Optional fuzzy search across title, company, location, evaluation notes, match/gap text, "
                "and other dashboard-facing job fields."
            ),
        ),
        title_query: Optional[str] = Query(None, description="Optional fuzzy title search."),
        sort: str = Query("fit_score", description="Sort field: fit_score, discovered_at, company."),
        order: str = Query("desc", description="Sort order: asc, desc."),
        limit: int = Query(50, ge=1, le=200, description="Page size."),
        offset: int = Query(0, ge=0, description="Pagination offset."),
        view: str = Query("full", description="Response payload shape: full, summary."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        normalized_status = str(status).strip().lower()
        if normalized_status not in PHASE6_JOB_STATUSES and normalized_status != "all":
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid status: {status}",
                request_id=request_id,
                details=[{"field": "status", "issue": f"allowed values: {', '.join(sorted(PHASE6_JOB_STATUSES | {'all'}))}"}],
            )

        normalized_source = str(source or "").strip().lower() or None
        if normalized_source and normalized_source not in PHASE6_JOB_SOURCES:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid source: {source}",
                request_id=request_id,
                details=[{"field": "source", "issue": f"allowed values: {', '.join(sorted(PHASE6_JOB_SOURCES))}"}],
            )

        normalized_sort = str(sort).strip().lower()
        if normalized_sort not in {"fit_score", "discovered_at", "company"}:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid sort: {sort}",
                request_id=request_id,
                details=[{"field": "sort", "issue": "allowed values: fit_score, discovered_at, company"}],
            )

        normalized_order = str(order).strip().lower()
        if normalized_order not in {"asc", "desc"}:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid order: {order}",
                request_id=request_id,
                details=[{"field": "order", "issue": "allowed values: asc, desc"}],
            )

        normalized_view = str(view).strip().lower()
        if normalized_view not in {"full", "summary"}:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=f"Invalid view: {view}",
                request_id=request_id,
                details=[{"field": "view", "issue": "allowed values: full, summary"}],
            )

        try:
            payload = phase6_list_jobs(
                status=None if normalized_status == "all" else normalized_status,
                min_score=min_score,
                max_score=max_score,
                company_tier=company_tier,
                source=normalized_source,
                search=search,
                title_query=title_query,
                sort=normalized_sort,
                order=normalized_order,
                limit=limit,
                offset=offset,
                include_details=normalized_view != "summary",
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Job query failed: {exc}",
                request_id=request_id,
            )
        payload["workflow"] = "workflow_06a_jobs"
        return _json_response(200, payload)

    @app.get(
        f"{API_PREFIX}/jobs/{{jobId}}",
        tags=["Jobs"],
        summary="Get job",
        description="Returns one job with full evaluation metadata.",
        responses={
            200: {"description": "Job loaded."},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_job_by_id(request: Request, jobId: str) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        job = phase6_get_job(jobId)
        if job is None:
            return _error_response(
                status_code=404,
                code="not_found",
                message=f"Job not found: {jobId}",
                request_id=request_id,
            )
        return _json_response(200, job)

    @app.patch(
        f"{API_PREFIX}/jobs/{{jobId}}",
        tags=["Jobs"],
        summary="Update job",
        description="Updates mutable job fields (`status`, `applied`, `dismissed`, `notes`).",
        responses={
            200: {"description": "Job updated."},
            400: {"model": ErrorResponse, "description": "Invalid update payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": JOB_PATCH_REQUEST_BODY},
    )
    async def patch_job(request: Request, jobId: str) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        allowed_fields = {"status", "applied", "dismissed", "notes"}
        unknown_fields = [key for key in payload.keys() if key not in allowed_fields]
        if unknown_fields:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Invalid job update payload.",
                request_id=request_id,
                details=[{"field": key, "issue": "field is not supported"} for key in unknown_fields],
            )

        status_value = payload.get("status")
        if status_value is not None:
            status_value = str(status_value).strip().lower()
            if status_value not in PHASE6_JOB_STATUSES:
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message=f"Invalid status: {status_value}",
                    request_id=request_id,
                    details=[{"field": "status", "issue": f"allowed values: {', '.join(sorted(PHASE6_JOB_STATUSES))}"}],
                )

        try:
            applied_value = (
                _normalize_bool(payload.get("applied"), field_name="applied")
                if "applied" in payload
                else None
            )
            dismissed_value = (
                _normalize_bool(payload.get("dismissed"), field_name="dismissed")
                if "dismissed" in payload
                else None
            )
        except ValueError as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=str(exc),
                request_id=request_id,
            )

        notes_value = payload.get("notes") if "notes" in payload else None
        if notes_value is not None:
            notes_value = str(notes_value)

        updated = phase6_update_job(
            job_id=jobId,
            status=status_value,
            applied=applied_value,
            dismissed=dismissed_value,
            notes=notes_value,
        )
        if updated is None:
            return _error_response(
                status_code=404,
                code="not_found",
                message=f"Job not found: {jobId}",
                request_id=request_id,
            )
        return _json_response(200, updated)

    @app.post(
        f"{API_PREFIX}/job-evaluation-runs",
        tags=["Jobs"],
        summary="Create job evaluation run",
        description="Queues or executes evaluation run(s) for one or more job identifiers.",
        response_model=JobEvaluationRunResponse,
        responses={
            200: {"description": "Synchronous evaluation run completed.", "content": {"application/json": {"example": JOB_EVALUATION_RUN_COMPLETED_EXAMPLE}}},
            202: {"description": "Async evaluation run accepted.", "content": {"application/json": {"example": JOB_EVALUATION_RUN_ACCEPTED_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid run payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            500: {"model": ErrorResponse, "description": "Evaluation run failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": JOB_EVALUATION_RUN_REQUEST_BODY},
    )
    async def create_job_evaluation_run(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        raw_job_ids = payload.get("job_ids")
        if not isinstance(raw_job_ids, list) or not raw_job_ids:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Missing required field: job_ids.",
                request_id=request_id,
                details=[{"field": "job_ids", "issue": "value must be a non-empty array of job ids"}],
            )

        try:
            wait = _normalize_bool(payload.get("wait", False), field_name="wait")
        except ValueError as exc:
            return _error_response(status_code=400, code="validation_failed", message=str(exc), request_id=request_id)
        settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}

        try:
            result = phase6_queue_job_evaluations(job_ids=[str(item) for item in raw_job_ids], wait=wait, settings=settings)
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Job evaluation run failed: {exc}",
                request_id=request_id,
            )

        result["workflow"] = "workflow_06a_job_evaluations"
        status_code = 200 if wait else 202
        return _json_response(status_code, result)

    @app.get(
        f"{API_PREFIX}/job-stats",
        tags=["Jobs"],
        summary="Get job stats",
        description="Returns dashboard-friendly aggregate job stats grouped by source, score range, and day.",
        responses={
            200: {"description": "Job stats loaded.", "content": {"application/json": {"example": JOB_STATS_SUCCESS_EXAMPLE}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_job_stats(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        payload = phase6_job_stats()
        payload["workflow"] = "workflow_06a_job_stats"
        return _json_response(200, payload)

    @app.get(
        f"{API_PREFIX}/job-gaps",
        tags=["Jobs"],
        summary="Get job gap analysis",
        description="Aggregates gaps and matching skills across evaluated jobs.",
        responses={
            200: {"description": "Gap analysis loaded.", "content": {"application/json": {"example": JOB_GAPS_SUCCESS_EXAMPLE}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_job_gaps(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        jobs = phase6_all_jobs()
        payload = phase6_aggregate_gaps(jobs)
        payload["workflow"] = "workflow_06a_job_gaps"
        return _json_response(200, payload)

    @app.post(
        f"{API_PREFIX}/job-deduplications",
        tags=["Jobs"],
        summary="Check job deduplication",
        description="Checks whether a candidate job payload already exists in `recall_jobs`.",
        responses={
            200: {"description": "Deduplication check complete."},
            400: {"model": ErrorResponse, "description": "Invalid candidate payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": JOB_DEDUP_REQUEST_BODY},
    )
    async def create_job_deduplication(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        title = str(payload.get("title", "")).strip()
        company = str(payload.get("company", "")).strip()
        url = str(payload.get("url", "")).strip()
        description = str(payload.get("description", "")).strip()
        if not url and not description and (not title or not company):
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Provide one of: url, description, or title+company.",
                request_id=request_id,
                details=[
                    {"field": "url", "issue": "provide url, or provide description, or provide title+company"},
                ],
            )

        threshold = payload.get("similarity_threshold", 0.92)
        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="similarity_threshold must be numeric.",
                request_id=request_id,
                details=[{"field": "similarity_threshold", "issue": "value must be between 0 and 1"}],
            )
        if threshold_value < 0 or threshold_value > 1:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="similarity_threshold must be between 0 and 1.",
                request_id=request_id,
                details=[{"field": "similarity_threshold", "issue": "value must be between 0 and 1"}],
            )

        dedup = phase6_check_job_duplicate(
            {
                "title": title,
                "company": company,
                "company_normalized": payload.get("company_normalized"),
                "url": url,
                "description": description,
                "date_posted": payload.get("date_posted"),
                "discovered_at": payload.get("discovered_at"),
            },
            similarity_threshold=threshold_value,
        )
        return _json_response(200, {"workflow": "workflow_06a_job_dedup", **dedup.to_dict()})

    @app.post(
        f"{API_PREFIX}/job-discovery-runs",
        tags=["Jobs"],
        summary="Create job discovery run",
        description="Triggers the discovery runner scaffold and returns queued run metadata.",
        responses={
            200: {"description": "Discovery run accepted."},
            400: {"model": ErrorResponse, "description": "Invalid discovery payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": JOB_DISCOVERY_RUN_REQUEST_BODY},
    )
    async def create_job_discovery_run(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        try:
            collections = phase6_ensure_collections()
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Collection setup failed: {exc}",
                request_id=request_id,
            )

        try:
            summary = phase6_run_discovery(payload)
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Discovery run failed: {exc}",
                request_id=request_id,
            )
        summary["workflow"] = "workflow_06a_job_discovery"
        summary["collections"] = [
            {"name": item.name, "created": item.created} for item in collections
        ]
        return _json_response(200, summary)

    @app.post(
        f"{API_PREFIX}/resumes",
        tags=["Resumes"],
        summary="Create resume ingestion",
        description="Ingests markdown or file-based resume content into `recall_resume`.",
        response_model=ResumeIngestionResponse,
        responses={
            200: {"description": "Resume ingested.", "content": {"application/json": {"example": RESUME_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid resume payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            415: {"model": ErrorResponse, "description": "Unsupported media/file type.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            500: {"model": ErrorResponse, "description": "Resume ingestion failed.", "content": {"application/json": {"example": ERROR_EXAMPLE_WORKFLOW}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": RESUME_REQUEST_BODY},
    )
    async def create_resume_ingestion(
        request: Request,
        dry_run: bool = Query(False, description="If true, validate/chunk resume without persistence side effects."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        content_type = request.headers.get("content-type", "")
        try:
            if "multipart/form-data" in content_type:
                form = await request.form()
                uploaded = form.get("file")
                if uploaded is None:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Missing required field: file.",
                        request_id=request_id,
                        details=[{"field": "file", "issue": "value is required"}],
                    )

                filename = Path(str(getattr(uploaded, "filename", "") or "resume.md")).name
                suffix = Path(filename).suffix.lower()
                if suffix not in {".md", ".txt", ".pdf", ".docx"}:
                    return _error_response(
                        status_code=415,
                        code="unsupported_media_type",
                        message=f"Unsupported resume file type: {suffix or 'unknown'}",
                        request_id=request_id,
                        details=[{"field": "file", "issue": "allowed extensions: .md, .txt, .pdf, .docx"}],
                    )

                with tempfile.NamedTemporaryFile(prefix="recall-resume-", suffix=suffix or ".md", delete=False) as handle:
                    temp_path = Path(handle.name)
                    data = await uploaded.read()
                    handle.write(data)
                try:
                    result = phase6_ingest_resume(file_path=temp_path, dry_run=dry_run)
                finally:
                    temp_path.unlink(missing_ok=True)
            else:
                payload = await _read_json_body(request)
                markdown = payload.get("markdown")
                file_path = payload.get("file_path")
                if markdown is not None:
                    result = phase6_ingest_resume(markdown_text=str(markdown), dry_run=dry_run)
                elif file_path:
                    result = phase6_ingest_resume(file_path=Path(str(file_path)).expanduser(), dry_run=dry_run)
                else:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Provide either `markdown` or `file_path`.",
                        request_id=request_id,
                        details=[
                            {"field": "markdown", "issue": "inline markdown resume text"},
                            {"field": "file_path", "issue": "absolute path to resume file"},
                        ],
                    )
        except (FileNotFoundError, ValueError) as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=str(exc),
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Resume ingestion failed: {exc}",
                request_id=request_id,
            )

        return _json_response(200, {"workflow": "workflow_06a_resume_ingestion", **result})

    @app.get(
        f"{API_PREFIX}/resumes/current",
        tags=["Resumes"],
        summary="Get current resume metadata",
        description="Returns latest ingested resume version metadata.",
        responses={
            200: {"description": "Resume metadata loaded."},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Resume not found."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_current_resume(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        conn = phase6_storage.connect_db()
        try:
            metadata = phase6_storage.latest_resume_metadata(conn)
        finally:
            conn.close()
        if metadata is None:
            return _error_response(
                status_code=404,
                code="not_found",
                message="No resume has been ingested yet.",
                request_id=request_id,
            )
        return _json_response(200, metadata)

    @app.get(
        f"{API_PREFIX}/companies",
        tags=["Companies"],
        summary="List company profiles",
        description="Lists company profile rollups with attached jobs.",
        responses={
            200: {"description": "Company profiles loaded."},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_companies(
        request: Request,
        limit: Optional[int] = Query(None, ge=1, le=500, description="Optional maximum number of company summaries."),
        include_jobs: bool = Query(True, description="Include embedded job arrays in each company list item."),
    ) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        profiles = phase6_list_company_profiles(phase6_all_jobs(), include_jobs=include_jobs, limit=limit)
        return _json_response(200, {"workflow": "workflow_06a_companies", "count": len(profiles), "items": profiles})

    @app.get(
        f"{API_PREFIX}/companies/{{companyId}}",
        tags=["Companies"],
        summary="Get company profile",
        description="Returns one company profile with associated jobs.",
        responses={
            200: {"description": "Company profile loaded."},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Company profile not found."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_company(request: Request, companyId: str) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        profile = phase6_get_company_profile(companyId, phase6_all_jobs())
        if profile is None:
            return _error_response(
                status_code=404,
                code="not_found",
                message=f"Company not found: {companyId}",
                request_id=request_id,
            )
        return _json_response(200, profile)

    @app.post(
        f"{API_PREFIX}/companies",
        tags=["Companies"],
        summary="Create watched company",
        description="Creates or persists a watched company entry used by the companies dashboard and future discovery runs.",
        responses={
            201: {"description": "Watched company created.", "content": {"application/json": {"example": COMPANY_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid company payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": COMPANY_CREATE_REQUEST_BODY},
    )
    async def create_company(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
            normalized = _normalize_company_watch_payload(payload, require_company_name=True)
            saved = phase6_upsert_tracked_company_config(patch=normalized)
            jobs_updated = 0
            if "tier" in normalized:
                jobs_updated = phase6_update_company_tier(company_id=saved["company_id"], tier=int(saved["tier"]))
            profile = phase6_get_company_profile(saved["company_id"], phase6_all_jobs())
        except ValueError as exc:
            return _error_response(status_code=400, code="validation_failed", message=str(exc), request_id=request_id)
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Company create failed: {exc}",
                request_id=request_id,
            )

        return _json_response(
            201,
            {"workflow": "workflow_06a_company_watchlist", "jobs_updated": jobs_updated, **(profile or saved)},
        )

    @app.patch(
        f"{API_PREFIX}/companies/{{companyId}}",
        tags=["Companies"],
        summary="Update watched company",
        description="Updates tracked company settings such as tier, ATS source, title filters, and connection notes.",
        responses={
            200: {"description": "Watched company updated.", "content": {"application/json": {"example": COMPANY_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid company payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Company not found."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": COMPANY_PATCH_REQUEST_BODY},
    )
    async def patch_company(request: Request, companyId: str) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        current = phase6_get_company_profile(companyId, phase6_all_jobs())
        if current is None:
            return _error_response(
                status_code=404,
                code="not_found",
                message=f"Company not found: {companyId}",
                request_id=request_id,
            )

        try:
            payload = await _read_json_body(request)
            normalized = _normalize_company_watch_payload(payload, require_company_name=False)
            saved = phase6_upsert_tracked_company_config(company_id=companyId, patch=normalized)
            jobs_updated = 0
            if "tier" in normalized:
                jobs_updated = phase6_update_company_tier(company_id=saved["company_id"], tier=int(saved["tier"]))
            profile = phase6_get_company_profile(saved["company_id"], phase6_all_jobs())
        except ValueError as exc:
            return _error_response(status_code=400, code="validation_failed", message=str(exc), request_id=request_id)
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Company update failed: {exc}",
                request_id=request_id,
            )

        return _json_response(
            200,
            {"workflow": "workflow_06a_company_watchlist", "jobs_updated": jobs_updated, **(profile or saved)},
        )

    @app.post(
        f"{API_PREFIX}/company-profile-refresh-runs",
        tags=["Companies"],
        summary="Create company profile refresh run",
        description="Refreshes a single company profile summary.",
        responses={
            200: {"description": "Refresh run completed."},
            400: {"model": ErrorResponse, "description": "Invalid refresh payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def create_company_profile_refresh_run(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        company_id = str(payload.get("company_id") or payload.get("companyId") or "").strip()
        if not company_id:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Missing required field: company_id.",
                request_id=request_id,
                details=[{"field": "company_id", "issue": "value is required"}],
            )

        result = phase6_refresh_company_profile(company_id, phase6_all_jobs())
        return _json_response(200, {"workflow": "workflow_06a_company_profile_refresh", **result})

    @app.post(
        f"{API_PREFIX}/cover-letter-drafts",
        tags=["Cover Letter Drafts"],
        summary="Create cover letter draft",
        description="Generates a tailored cover letter draft from the current resume and one evaluated job.",
        responses={
            200: {
                "description": "Cover letter draft generated.",
                "content": {"application/json": {"example": COVER_LETTER_DRAFT_SUCCESS_EXAMPLE}},
            },
            400: {"model": ErrorResponse, "description": "Invalid draft payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            500: {"model": ErrorResponse, "description": "Draft generation failed."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": COVER_LETTER_DRAFT_REQUEST_BODY},
    )
    async def create_cover_letter_draft(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Missing required field: job_id.",
                request_id=request_id,
                details=[{"field": "job_id", "issue": "value is required"}],
            )

        try:
            save_to_vault = _normalize_bool(payload.get("save_to_vault", False), field_name="save_to_vault")
        except ValueError as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=str(exc),
                request_id=request_id,
            )

        settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else None
        try:
            result = phase6_generate_cover_letter_draft(
                job_id=job_id,
                settings=settings,
                save_to_vault=save_to_vault,
            )
        except FileNotFoundError:
            return _error_response(
                status_code=404,
                code="not_found",
                message=f"Job not found: {job_id}",
                request_id=request_id,
            )
        except ValueError as exc:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message=str(exc),
                request_id=request_id,
            )
        except Exception as exc:  # noqa: BLE001
            return _error_response(
                status_code=500,
                code="workflow_failed",
                message=f"Cover letter draft generation failed: {exc}",
                request_id=request_id,
            )
        return _json_response(200, {"workflow": "workflow_06a_cover_letter_draft", **result})

    @app.get(
        f"{API_PREFIX}/llm-settings",
        tags=["LLM Settings"],
        summary="Get LLM settings",
        description="Returns current persisted LLM settings for job evaluation.",
        responses={
            200: {"description": "LLM settings loaded.", "content": {"application/json": {"example": LLM_SETTINGS_SUCCESS_EXAMPLE}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
    )
    async def get_llm_settings(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        conn = phase6_storage.connect_db()
        try:
            settings = phase6_storage.get_llm_settings(conn)
        finally:
            conn.close()
        return _json_response(200, {"workflow": "workflow_06a_llm_settings", "settings": settings})

    @app.patch(
        f"{API_PREFIX}/llm-settings",
        tags=["LLM Settings"],
        summary="Update LLM settings",
        description="Updates and persists evaluation LLM settings in SQLite.",
        responses={
            200: {"description": "LLM settings updated.", "content": {"application/json": {"example": LLM_SETTINGS_SUCCESS_EXAMPLE}}},
            400: {"model": ErrorResponse, "description": "Invalid settings payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": LLM_SETTINGS_PATCH_REQUEST_BODY},
    )
    async def patch_llm_settings(request: Request) -> JSONResponse:
        request_id = _request_id()
        control_error = _enforce_api_and_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)
        if control_error is not None:
            return control_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        allowed_fields = set(phase6_storage.DEFAULT_LLM_SETTINGS.keys())
        unknown = [field for field in payload.keys() if field not in allowed_fields]
        if unknown:
            return _error_response(
                status_code=400,
                code="validation_failed",
                message="Invalid llm settings payload.",
                request_id=request_id,
                details=[{"field": field, "issue": "field is not supported"} for field in unknown],
            )

        normalized: dict[str, Any] = {}
        if "evaluation_model" in payload:
            value = str(payload["evaluation_model"]).strip().lower()
            if value not in {"local", "cloud"}:
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message="evaluation_model must be `local` or `cloud`.",
                    request_id=request_id,
                    details=[{"field": "evaluation_model", "issue": "allowed values: local, cloud"}],
                )
            normalized["evaluation_model"] = value
        if "cloud_provider" in payload:
            value = str(payload["cloud_provider"]).strip().lower()
            if value not in {"anthropic", "openai", "gemini"}:
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message="cloud_provider must be one of anthropic, openai, gemini.",
                    request_id=request_id,
                    details=[{"field": "cloud_provider", "issue": "allowed values: anthropic, openai, gemini"}],
                )
            normalized["cloud_provider"] = value
        if "cloud_model" in payload:
            model_value = str(payload["cloud_model"]).strip()
            if not model_value:
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message="cloud_model cannot be empty.",
                    request_id=request_id,
                    details=[{"field": "cloud_model", "issue": "value is required"}],
                )
            normalized["cloud_model"] = model_value
        if "local_model" in payload:
            model_value = str(payload["local_model"]).strip()
            if not model_value:
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message="local_model cannot be empty.",
                    request_id=request_id,
                    details=[{"field": "local_model", "issue": "value is required"}],
                )
            normalized["local_model"] = model_value
        if "auto_escalate" in payload:
            try:
                normalized["auto_escalate"] = _normalize_bool(payload["auto_escalate"], field_name="auto_escalate")
            except ValueError as exc:
                return _error_response(status_code=400, code="validation_failed", message=str(exc), request_id=request_id)
        for integer_field in ("escalate_threshold_gaps", "escalate_threshold_rationale_words"):
            if integer_field in payload:
                try:
                    parsed = int(payload[integer_field])
                except (TypeError, ValueError):
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message=f"{integer_field} must be an integer.",
                        request_id=request_id,
                        details=[{"field": integer_field, "issue": "value must be an integer >= 0"}],
                    )
                if parsed < 0:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message=f"{integer_field} must be >= 0.",
                        request_id=request_id,
                        details=[{"field": integer_field, "issue": "value must be an integer >= 0"}],
                    )
                normalized[integer_field] = parsed

        conn = phase6_storage.connect_db()
        try:
            settings = phase6_storage.update_llm_settings(conn, normalized)
        finally:
            conn.close()
        return _json_response(200, {"workflow": "workflow_06a_llm_settings", "settings": settings})

    @app.get("/{_path:path}", include_in_schema=False)
    async def not_found_get(_path: str) -> JSONResponse:
        _ = _path
        return _error_response(status_code=404, code="not_found", message="Not found.", request_id=_request_id())

    @app.post("/{_path:path}", include_in_schema=False)
    async def not_found_post(_path: str) -> JSONResponse:
        _ = _path
        return _error_response(status_code=404, code="not_found", message="Unknown path.", request_id=_request_id())

    app.state.rate_limit_window_seconds = rate_limit_window_seconds
    app.state.rate_limit_max_requests = rate_limit_max_requests
    return app


def _required_ollama_models() -> list[str]:
    required: list[str] = []

    embed_model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip() or "nomic-embed-text"
    required.append(embed_model)

    provider = os.getenv("RECALL_LLM_PROVIDER", "ollama").strip().lower()
    if provider == "ollama":
        generation_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct").strip() or "qwen2.5:7b-instruct"
        required.append(generation_model)

    deduped: list[str] = []
    seen: set[str] = set()
    for model in required:
        if not model or model in seen:
            continue
        seen.add(model)
        deduped.append(model)
    return deduped


def _ensure_required_ollama_models() -> None:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip() or "http://localhost:11434"
    timeout_seconds = _read_positive_float_env("RECALL_OLLAMA_PULL_TIMEOUT_SECONDS", DEFAULT_OLLAMA_PULL_TIMEOUT_SECONDS)
    required_models = _required_ollama_models()

    if not required_models:
        return

    installed_models = _ollama_installed_models(host=host, timeout_seconds=30.0)
    missing_models = [model for model in required_models if model not in installed_models]
    if not missing_models:
        print(f"Ollama model preflight: all required models present ({', '.join(required_models)}).")
        return

    print(f"Ollama model preflight: pulling missing models: {', '.join(missing_models)}")
    for model in missing_models:
        _ollama_pull_model(host=host, model=model, timeout_seconds=timeout_seconds)
    print("Ollama model preflight: required models ready.")


def _ollama_installed_models(*, host: str, timeout_seconds: float) -> set[str]:
    response = httpx.get(f"{host.rstrip('/')}/api/tags", timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models", [])
    installed: set[str] = set()
    if isinstance(models, list):
        for item in models:
            if not isinstance(item, dict):
                continue
            for key in ("name", "model"):
                value = str(item.get(key, "")).strip()
                if value:
                    installed.add(value)
    return installed


def _ollama_pull_model(*, host: str, model: str, timeout_seconds: float) -> None:
    response = httpx.post(
        f"{host.rstrip('/')}/api/pull",
        json={"name": model, "stream": False},
        timeout=timeout_seconds,
    )
    response.raise_for_status()


def _read_positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _dashboard_checks_payload(
    *,
    include_gaps: bool,
    cache_warmer: DashboardCacheWarmer | None,
) -> dict[str, Any]:
    notes: list[str] = []
    sections: dict[str, dict[str, Any] | None] = {
        "jobs": _run_dashboard_check(
            label="jobs",
            runner=lambda: _dashboard_jobs_section(),
            notes=notes,
        ),
        "companies": _run_dashboard_check(
            label="companies",
            runner=lambda: _dashboard_companies_section(),
            notes=notes,
        ),
        "gaps": (
            _run_dashboard_check(
                label="gaps",
                runner=lambda: _dashboard_gaps_section(),
                notes=notes,
            )
            if include_gaps
            else None
        ),
    }
    statuses = [section["status"] for section in sections.values() if isinstance(section, dict)]
    overall_status = "ok" if statuses and all(status == "ok" for status in statuses) else "degraded"
    warmer_snapshot = cache_warmer.snapshot() if cache_warmer is not None else {
        "enabled": False,
        "interval_seconds": 0,
        "last_started_at": None,
        "last_completed_at": None,
        "last_error": None,
    }
    if warmer_snapshot.get("last_error"):
        notes.append(f"Cache warmer last error: {warmer_snapshot['last_error']}")
        overall_status = "degraded"
    return {
        "workflow": "workflow_06a_dashboard_checks",
        "status": overall_status,
        "checked_at": _now_iso(),
        "jobs": sections["jobs"],
        "companies": sections["companies"],
        "gaps": sections["gaps"],
        "cache_warmer": warmer_snapshot,
        "notes": notes,
    }


def _run_dashboard_check(
    *,
    label: str,
    runner: Any,
    notes: list[str],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        section = runner()
    except Exception as exc:  # noqa: BLE001
        notes.append(f"{label} check failed: {exc}")
        return {
            "status": "degraded",
            "count": 0,
            "detail": f"{label} check failed",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    section["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return section


def _dashboard_jobs_section() -> dict[str, Any]:
    jobs_payload = phase6_list_jobs(status="all", limit=60, include_details=False)
    stats_payload = phase6_job_stats()
    item_count = len(jobs_payload.get("items") or [])
    total_jobs = int(jobs_payload.get("total") or stats_payload.get("total_jobs") or 0)
    high_fit = int(stats_payload.get("high_fit_count") or 0)
    status = "ok" if total_jobs > 0 and item_count > 0 else "degraded"
    detail = f"{item_count} jobs loaded for the board, {total_jobs} total tracked, {high_fit} high-fit"
    return {"status": status, "count": total_jobs, "detail": detail}


def _dashboard_companies_section() -> dict[str, Any]:
    jobs = phase6_all_jobs()
    profiles = phase6_list_company_profiles(jobs, include_jobs=False, limit=300)
    count = len(profiles)
    top_company = str((profiles[0] or {}).get("company_name") or "").strip() if profiles else ""
    status = "ok" if count > 0 else "degraded"
    detail = f"{count} tracked companies loaded"
    if top_company:
        detail += f"; top company {top_company}"
    return {"status": status, "count": count, "detail": detail}


def _dashboard_gaps_section() -> dict[str, Any]:
    jobs = phase6_all_jobs()
    payload = phase6_aggregate_gaps(jobs)
    gap_count = len(payload.get("aggregated_gaps") or [])
    analyzed = int(payload.get("total_jobs_analyzed") or 0)
    status = "ok" if analyzed > 0 else "degraded"
    detail = f"{gap_count} aggregated gaps across {analyzed} evaluated jobs"
    return {"status": status, "count": gap_count, "detail": detail}


def _db_path() -> Path:
    raw = os.getenv("RECALL_DB_PATH", "").strip()
    if raw:
        return Path(raw)
    return ROOT / "data" / "recall.db"


def _read_recent_activity(*, limit: int, filter_group: str | None) -> list[dict[str, Any]]:
    db_path = _db_path()
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ingestion_log'"
        ).fetchone()
        if table_exists is None:
            return []

        columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(ingestion_log)").fetchall()}
        has_group = "group_name" in columns
        has_tags = "tags_json" in columns

        if has_group and has_tags:
            sql = (
                "SELECT ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp, "
                "group_name, tags_json "
                "FROM ingestion_log "
            )
            params: list[Any] = []
            if filter_group:
                sql += "WHERE COALESCE(group_name, 'reference') = ? "
                params.append(filter_group)
            sql += "ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
        else:
            sql = (
                "SELECT ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp "
                "FROM ingestion_log "
            )
            params = []
            sql += "ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()

        items: list[dict[str, Any]] = []
        for row in rows:
            group_value = normalize_group(row["group_name"]) if has_group and row["group_name"] else "reference"
            if filter_group and group_value != filter_group:
                continue

            tags_value = _safe_parse_tags(row["tags_json"]) if has_tags else []
            items.append(
                {
                    "ingest_id": row["ingest_id"],
                    "source_type": row["source_type"],
                    "source_ref": row["source_ref"],
                    "channel": row["channel"],
                    "doc_id": row["doc_id"],
                    "chunks_created": int(row["chunks_created"] or 0),
                    "status": row["status"],
                    "timestamp": row["timestamp"],
                    "group": group_value,
                    "tags": tags_value,
                }
            )
        return items
    finally:
        conn.close()


def _safe_parse_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []
    text = str(raw_tags).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return []


def _read_latest_evaluations(*, recent_limit: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    db_path = _db_path()
    if not db_path.exists():
        return None, []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='eval_results'"
        ).fetchone()
        if table_exists is None:
            return None, []

        rows = conn.execute(
            """
            SELECT run_date,
                   COUNT(*) AS total,
                   SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed,
                   AVG(latency_ms) AS avg_latency_ms
            FROM eval_results
            GROUP BY run_date
            ORDER BY run_date DESC
            LIMIT ?
            """,
            (recent_limit,),
        ).fetchall()

        summaries: list[dict[str, Any]] = []
        for row in rows:
            total = int(row["total"] or 0)
            passed = int(row["passed"] or 0)
            failed = max(total - passed, 0)
            pass_rate = (passed / total) if total else 0.0
            avg_latency = float(row["avg_latency_ms"]) if row["avg_latency_ms"] is not None else None
            summaries.append(
                {
                    "run_date": row["run_date"],
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": round(pass_rate, 4),
                    "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
                }
            )

        latest = summaries[0] if summaries else None
        return latest, summaries
    finally:
        conn.close()


def _queue_eval_run(*, suite: str, backend: str) -> str:
    eval_run_id = f"eval_{uuid.uuid4().hex[:12]}"
    queued_at = _now_iso()
    with EVAL_RUNS_LOCK:
        EVAL_RUNS[eval_run_id] = {
            "run_id": eval_run_id,
            "status": "queued",
            "suite": suite,
            "backend": backend,
            "queued_at": queued_at,
            "started_at": None,
            "ended_at": None,
            "error": None,
            "result": None,
        }
    return eval_run_id


def _get_eval_run(eval_run_id: str) -> dict[str, Any]:
    with EVAL_RUNS_LOCK:
        payload = EVAL_RUNS.get(eval_run_id)
        if payload is None:
            return {
                "run_id": eval_run_id,
                "status": "failed",
                "suite": "unknown",
                "backend": "unknown",
                "started_at": None,
                "ended_at": _now_iso(),
                "error": "run_not_found",
                "result": None,
            }
        return dict(payload)


def _list_eval_runs(*, include_terminal: bool) -> list[dict[str, Any]]:
    with EVAL_RUNS_LOCK:
        runs = [dict(item) for item in EVAL_RUNS.values()]
    if not include_terminal:
        runs = [item for item in runs if item.get("status") in {"queued", "running"}]
    runs.sort(key=lambda item: item.get("queued_at") or "", reverse=True)
    return runs


def _execute_eval_run(
    *,
    eval_run_id: str,
    suite: str,
    backend: str,
    webhook_url: str | None,
    dry_run: bool,
) -> None:
    _update_eval_run(
        eval_run_id,
        status="running",
        started_at=_now_iso(),
        error=None,
    )
    try:
        result = _run_eval_suite(
            suite=suite,
            backend=backend,
            webhook_url=webhook_url,
            dry_run=dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        _update_eval_run(
            eval_run_id,
            status="failed",
            ended_at=_now_iso(),
            error=str(exc),
            result=None,
        )
        return

    _update_eval_run(
        eval_run_id,
        status="completed",
        ended_at=_now_iso(),
        error=None,
        result=result,
    )


def _update_eval_run(eval_run_id: str, **fields: Any) -> None:
    with EVAL_RUNS_LOCK:
        current = EVAL_RUNS.get(eval_run_id)
        if current is None:
            return
        current.update(fields)


def _run_eval_suite(
    *,
    suite: str,
    backend: str,
    webhook_url: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    suites = [suite]
    if suite == "both":
        suites = ["core", "job-search", "learning"]

    run_results: list[dict[str, Any]] = []
    for selected_suite in suites:
        summary = _run_eval_once(
            selected_suite=selected_suite,
            backend=backend,
            webhook_url=webhook_url,
            dry_run=dry_run,
        )
        run_results.append(summary)

    total = sum(int(item.get("total", 0) or 0) for item in run_results)
    passed = sum(int(item.get("passed", 0) or 0) for item in run_results)
    failed = max(total - passed, 0)
    all_passed = all(str(item.get("status", "")).lower() == "pass" for item in run_results if item)
    return {
        "suite": suite,
        "status": "pass" if all_passed else "fail",
        "total": total,
        "passed": passed,
        "failed": failed,
        "runs": run_results,
    }


def _run_eval_once(
    *,
    selected_suite: str,
    backend: str,
    webhook_url: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    cases_file = _eval_cases_file_for_suite(selected_suite)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "eval" / "run_eval.py"),
        "--cases-file",
        str(cases_file),
        "--backend",
        backend,
    ]
    if backend == "webhook":
        resolved_webhook_url = webhook_url or _default_eval_webhook_url()
        command.extend(["--webhook-url", resolved_webhook_url])
    if dry_run:
        command.append("--dry-run")

    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=DEFAULT_EVAL_RUN_TIMEOUT_SECONDS,
        check=False,
    )
    if completed.returncode not in {0, 1}:
        stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown run_eval failure"
        raise RuntimeError(f"Eval runner failed for suite={selected_suite}: {stderr}")

    summary = _parse_eval_summary_output(completed.stdout)
    summary["suite"] = selected_suite
    summary["command_exit_code"] = completed.returncode
    if completed.returncode == 1 and not summary.get("status"):
        summary["status"] = "fail"
    return summary


def _eval_cases_file_for_suite(selected_suite: str) -> Path:
    if selected_suite == "core":
        return ROOT / "scripts" / "eval" / "eval_cases.json"
    if selected_suite == "job-search":
        return ROOT / "scripts" / "eval" / "job_search_eval_cases.json"
    if selected_suite == "learning":
        return ROOT / "scripts" / "eval" / "learning_eval_cases.json"
    raise ValueError(f"Unsupported eval suite: {selected_suite}")


def _default_eval_webhook_url() -> str:
    explicit = os.getenv("RECALL_EVAL_WEBHOOK_URL", "").strip()
    if explicit:
        return explicit
    n8n_host = os.getenv("N8N_HOST", "http://localhost:5678").strip() or "http://localhost:5678"
    return f"{n8n_host.rstrip('/')}/webhook/recall-query"


def _parse_eval_summary_output(raw_stdout: str) -> dict[str, Any]:
    text = raw_stdout.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"raw_output": text}

    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"raw_output": text}
    if isinstance(parsed, dict):
        return parsed
    return {"raw_output": text}


async def _process_file_upload(
    *,
    uploaded_file: UploadFile,
    group: str,
    tags: str,
    save_to_vault: bool,
    dry_run: bool,
    request_id: str,
) -> JSONResponse:
    original_name = Path(str(uploaded_file.filename or "")).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        return _error_response(
            status_code=415,
            code="unsupported_media_type",
            message=f"Unsupported file type: {suffix or 'unknown'}",
            request_id=request_id,
            details=[
                {
                    "field": "file",
                    "issue": f"allowed extensions: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
                }
            ],
        )

    incoming_dir = _incoming_dir_from_env()
    incoming_dir.mkdir(parents=True, exist_ok=True)
    target_path = _next_available_upload_path(incoming_dir=incoming_dir, original_name=original_name)
    max_upload_bytes = _max_upload_bytes()

    bytes_written = 0
    try:
        with target_path.open("wb") as destination:
            while True:
                chunk = await uploaded_file.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    destination.close()
                    target_path.unlink(missing_ok=True)
                    return _error_response(
                        status_code=413,
                        code="payload_too_large",
                        message=f"Uploaded file exceeds max size of {_max_upload_mb()} MB.",
                        request_id=request_id,
                        details=[{"field": "file", "issue": f"size limit is {_max_upload_mb()} MB"}],
                    )
                destination.write(chunk)
    finally:
        await uploaded_file.close()

    normalized_group = normalize_group(group)
    normalized_tags = _parse_comma_tags(tags)
    metadata = {
        "save_to_vault": save_to_vault,
        "uploaded_filename": original_name,
    }
    ingest_payload = IngestRequest(
        source_type="file",
        content=str(target_path),
        source_channel="webhook",
        title=original_name,
        group=normalized_group,
        tags=normalized_tags,
        metadata=metadata,
    )
    try:
        ingest_result = ingest_request(ingest_payload, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            status_code=500,
            code="workflow_failed",
            message=f"File ingestion failed: {exc}",
            request_id=request_id,
        )

    return _json_response(
        200,
        {
            "workflow": "workflow_01_ingestion_file",
            "status": "accepted",
            "filename": target_path.name,
            "stored_path": str(target_path),
            "group": normalized_group,
            "tags": normalized_tags,
            "save_to_vault": save_to_vault,
            "dry_run": dry_run,
            "ingested": [asdict(ingest_result)],
            "errors": [],
        },
    )


def _process_ingestion(*, channel: str, payload: dict[str, Any], dry_run: bool, request_id: str) -> JSONResponse:
    normalized_channel = channel.strip().lower()
    if normalized_channel not in ALLOWED_INGEST_CHANNELS:
        return _error_response(
            status_code=400,
            code="unsupported_channel",
            message=f"Unsupported ingest channel: {normalized_channel}",
            request_id=request_id,
            details=[
                {
                    "field": "channel",
                    "issue": f"allowed values: {', '.join(ALLOWED_INGEST_CHANNELS)}",
                }
            ],
        )

    try:
        unified = normalize_payload(payload, channel=normalized_channel)
        requests = payload_to_requests(unified)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            status_code=400,
            code="invalid_payload",
            message=f"Invalid payload: {exc}",
            request_id=request_id,
        )

    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    job_pipeline: list[dict[str, Any]] = []
    for index, item in enumerate(requests):
        try:
            result = ingest_request(item, dry_run=dry_run)
            results.append(asdict(result))
            route_result = _maybe_route_job_pipeline(
                request_index=index,
                item=item,
                ingest_result=result,
                dry_run=dry_run,
            )
            if route_result is not None:
                job_pipeline.append(route_result)
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "request_index": index,
                    "source_type": item.source_type,
                    "error": str(exc),
                }
            )

    response = {
        "workflow": "workflow_01_ingestion",
        "channel": normalized_channel,
        "normalized_payload": unified,
        "ingested": results,
        "errors": errors,
        "dry_run": dry_run,
    }
    if job_pipeline:
        response["job_pipeline"] = job_pipeline
    return _json_response(200 if not errors else 207, response)


def _maybe_route_job_pipeline(
    *,
    request_index: int,
    item: IngestRequest,
    ingest_result: Any,
    dry_run: bool,
) -> dict[str, Any] | None:
    normalized_group = normalize_group(item.group)
    if normalized_group != "job-search":
        return None

    source_url = _resolve_ingest_source_url(item=item, ingest_result=ingest_result)
    if not source_url:
        return {
            "request_index": request_index,
            "routed": False,
            "reason": "missing_source_url",
        }

    if not phase6_looks_like_job_url(source_url):
        return {
            "request_index": request_index,
            "routed": False,
            "reason": "url_not_job_posting",
            "url": source_url,
        }

    if dry_run:
        return {
            "request_index": request_index,
            "routed": False,
            "reason": "dry_run",
            "url": source_url,
        }

    metadata = dict(item.metadata) if isinstance(item.metadata, dict) else {}
    doc_text = _load_ingested_doc_text(str(getattr(ingest_result, "doc_id", "") or ""))

    try:
        extracted = phase6_extract_job_metadata(
            {
                "url": source_url,
                "title": item.title or metadata.get("title"),
                "company": metadata.get("company"),
                "location": metadata.get("location"),
                "source": "chrome_extension",
                "content": doc_text,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "request_index": request_index,
            "routed": False,
            "reason": "metadata_extraction_failed",
            "url": source_url,
            "error": str(exc),
        }

    title = str(extracted.get("title") or "").strip()
    company = str(extracted.get("company") or "").strip()
    if not title or not company:
        return {
            "request_index": request_index,
            "routed": False,
            "reason": "metadata_incomplete",
            "url": source_url,
            "title": title,
            "company": company,
        }

    manual_job = {
        "title": title,
        "company": company,
        "location": str(extracted.get("location") or "Unknown"),
        "url": source_url,
        "description": str(extracted.get("description") or doc_text or ""),
        "source": "chrome_extension",
        "salary_min": extracted.get("salary_min"),
        "salary_max": extracted.get("salary_max"),
    }

    try:
        discovery_summary = phase6_run_discovery({"jobs": [manual_job], "dry_run": False})
    except Exception as exc:  # noqa: BLE001
        return {
            "request_index": request_index,
            "routed": False,
            "reason": "job_pipeline_store_failed",
            "url": source_url,
            "error": str(exc),
        }

    new_job_ids = discovery_summary.get("new_job_ids") if isinstance(discovery_summary.get("new_job_ids"), list) else []
    eval_run_id: str | None = None
    if new_job_ids:
        try:
            eval_result = phase6_queue_job_evaluations(job_ids=[str(job_id) for job_id in new_job_ids], wait=False)
            eval_run_id = str(eval_result.get("run_id") or "")
        except Exception as exc:  # noqa: BLE001
            return {
                "request_index": request_index,
                "routed": True,
                "url": source_url,
                "new_job_ids": new_job_ids,
                "reason": "evaluation_queue_failed",
                "error": str(exc),
            }

    return {
        "request_index": request_index,
        "routed": True,
        "url": source_url,
        "source": extracted.get("source"),
        "title": title,
        "company": company,
        "new_job_ids": new_job_ids,
        "discovery_run_id": discovery_summary.get("run_id"),
        "evaluation_run_id": eval_run_id,
    }


def _resolve_ingest_source_url(*, item: IngestRequest, ingest_result: Any) -> str:
    if item.source_type == "url":
        return str(item.content or "").strip()

    if item.source_type == "gdoc" and isinstance(item.content, dict):
        value = str(item.content.get("url") or "").strip()
        if value:
            return value

    metadata = item.metadata if isinstance(item.metadata, dict) else {}
    for key in ("url", "page_url", "source_url"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value

    source_ref = str(getattr(ingest_result, "source_ref", "") or "").strip()
    if source_ref.startswith("http://") or source_ref.startswith("https://"):
        return source_ref
    return ""


def _load_ingested_doc_text(doc_id: str) -> str:
    target = str(doc_id or "").strip()
    if not target:
        return ""

    try:
        client = qdrant_client_from_env(os.getenv("QDRANT_HOST", "http://localhost:6333"))
        collection_name = os.getenv("QDRANT_COLLECTION", "recall_docs")
        from qdrant_client import models

        query_filter = models.Filter(
            must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=target))]
        )
        response = None
        try:
            response = client.scroll(
                collection_name=collection_name,
                limit=200,
                with_payload=True,
                with_vectors=False,
                query_filter=query_filter,
            )
        except Exception as exc:
            if "query_filter" not in str(exc):
                raise
            response = client.scroll(
                collection_name=collection_name,
                limit=200,
                with_payload=True,
                with_vectors=False,
                scroll_filter=query_filter,
            )

        if isinstance(response, tuple) and len(response) == 2:
            points = response[0]
        else:
            points = getattr(response, "points", None)

        if not isinstance(points, list):
            return ""

        chunks: list[tuple[int, str]] = []
        for point in points:
            payload = dict(getattr(point, "payload", {}) or {})
            text = str(payload.get("text") or "").strip()
            if not text:
                continue
            try:
                index = int(payload.get("chunk_index", 999999))
            except (TypeError, ValueError):
                index = 999999
            chunks.append((index, text))
        chunks.sort(key=lambda entry: entry[0])
        return "\n\n".join(text for _, text in chunks)
    except Exception:  # noqa: BLE001
        return ""


def _process_rag_query(*, payload: dict[str, Any], dry_run: bool, request_id: str) -> JSONResponse:
    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response(
            status_code=400,
            code="validation_failed",
            message="Missing required field: query.",
            request_id=request_id,
            details=[{"field": "query", "issue": "value is required"}],
        )

    top_k = payload.get("top_k")
    min_score = payload.get("min_score")
    max_retries = payload.get("max_retries")
    mode = payload.get("mode")
    filter_tags = payload.get("filter_tags")
    filter_tag_mode = payload.get("filter_tag_mode")
    filter_group = payload.get("filter_group")
    retrieval_mode = payload.get("retrieval_mode")
    hybrid_alpha = payload.get("hybrid_alpha")
    enable_reranker = payload.get("enable_reranker")
    reranker_weight = payload.get("reranker_weight")
    try:
        top_k_value = int(top_k) if top_k is not None else None
        min_score_value = float(min_score) if min_score is not None else None
        max_retries_value = int(max_retries) if max_retries is not None else None
        mode_value = str(mode) if mode is not None else None
        filter_tags_value = _normalize_tag_filter(filter_tags)
        filter_tag_mode_value = _normalize_filter_tag_mode(filter_tag_mode)
        filter_group_value = _normalize_group_filter(filter_group)
        retrieval_mode_value = str(retrieval_mode) if retrieval_mode is not None else None
        hybrid_alpha_value = float(hybrid_alpha) if hybrid_alpha is not None else None
        reranker_weight_value = float(reranker_weight) if reranker_weight is not None else None
        enable_reranker_value = (
            _normalize_bool(enable_reranker, field_name="enable_reranker")
            if enable_reranker is not None
            else None
        )
    except (TypeError, ValueError) as exc:
        return _error_response(
            status_code=400,
            code="validation_failed",
            message=f"Invalid RAG options: {exc}",
            request_id=request_id,
        )

    try:
        result = run_rag_query(
            query,
            top_k=top_k_value,
            min_score=min_score_value,
            max_retries=max_retries_value,
            filter_tags=filter_tags_value,
            filter_tag_mode=filter_tag_mode_value,
            filter_group=filter_group_value,
            mode=mode_value,
            retrieval_mode=retrieval_mode_value,
            hybrid_alpha=hybrid_alpha_value,
            enable_reranker=enable_reranker_value,
            reranker_weight=reranker_weight_value,
            dry_run=dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            status_code=500,
            code="workflow_failed",
            message=f"Workflow 02 failed: {exc}",
            request_id=request_id,
        )

    return _json_response(
        200,
        {
            "workflow": "workflow_02_rag_query",
            "dry_run": dry_run,
            "result": result,
        },
    )


def _process_meeting_action_items(*, payload: dict[str, Any], dry_run: bool, request_id: str) -> JSONResponse:
    try:
        kwargs = payload_to_meeting_kwargs(payload)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            status_code=400,
            code="validation_failed",
            message=f"Invalid meeting payload: {exc}",
            request_id=request_id,
        )

    try:
        result = run_meeting_action_items(**kwargs, dry_run=dry_run)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            status_code=500,
            code="workflow_failed",
            message=f"Workflow 03 failed: {exc}",
            request_id=request_id,
        )

    return _json_response(
        200,
        {
            "workflow": "workflow_03_meeting_action_items",
            "dry_run": dry_run,
            "result": result,
        },
    )


def _normalize_tag_filter(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            tag = str(item).strip()
            if tag:
                tags.append(tag)
        return tags
    raise ValueError("filter_tags must be an array or comma-separated string.")


def _normalize_group_filter(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return normalize_group(raw)


def _normalize_filter_tag_mode(value: Any) -> str:
    if value is None:
        return "any"
    normalized = str(value).strip().lower()
    if normalized in {"", "any", "or"}:
        return "any"
    if normalized in {"all", "and", "must"}:
        return "all"
    raise ValueError("filter_tag_mode must be one of: any, all.")


def _normalize_bool(value: Any, *, field_name: str = "value") -> bool:
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
    raise ValueError(f"{field_name} must be boolean-like.")


def _normalize_company_watch_payload(payload: dict[str, Any], *, require_company_name: bool) -> dict[str, Any]:
    allowed_fields = {"company_name", "tier", "ats", "board_id", "url", "title_filter", "your_connection"}
    unknown = [field for field in payload.keys() if field not in allowed_fields]
    if unknown:
        raise ValueError(f"Unsupported company fields: {', '.join(sorted(unknown))}.")

    normalized: dict[str, Any] = {}
    if "company_name" in payload:
        company_name = str(payload.get("company_name") or "").strip()
        if not company_name:
            raise ValueError("company_name is required.")
        normalized["company_name"] = company_name
    elif require_company_name:
        raise ValueError("company_name is required.")

    if "tier" in payload:
        try:
            tier = int(payload["tier"])
        except (TypeError, ValueError) as exc:
            raise ValueError("tier must be an integer between 1 and 3.") from exc
        if tier not in {1, 2, 3}:
            raise ValueError("tier must be an integer between 1 and 3.")
        normalized["tier"] = tier

    for field_name in ("ats", "board_id", "url", "your_connection"):
        if field_name in payload:
            normalized[field_name] = str(payload.get(field_name) or "").strip()

    if "ats" in normalized and normalized["ats"]:
        normalized["ats"] = normalized["ats"].lower()

    if "title_filter" in payload:
        raw_filters = payload.get("title_filter")
        if not isinstance(raw_filters, list):
            raise ValueError("title_filter must be an array of strings.")
        normalized["title_filter"] = [str(item or "").strip() for item in raw_filters if str(item or "").strip()]

    return normalized


def _normalize_optional_positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("max_files must be a positive integer.")
    return parsed


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_comma_tags(raw_tags: str) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for part in str(raw_tags or "").split(","):
        normalized = part.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tags.append(normalized)
    return tags


def _max_upload_mb() -> int:
    return _read_positive_int_env(MAX_UPLOAD_MB_ENV, DEFAULT_MAX_UPLOAD_MB)


def _max_upload_bytes() -> int:
    return _max_upload_mb() * 1024 * 1024


def _incoming_dir_from_env() -> Path:
    incoming_raw = os.getenv("DATA_INCOMING", str(ROOT / "data" / "incoming")).strip()
    incoming = Path(incoming_raw).expanduser()
    if incoming.is_absolute():
        return incoming
    return (ROOT / incoming).resolve()


def _next_available_upload_path(*, incoming_dir: Path, original_name: str) -> Path:
    safe_name = Path(original_name).name or f"upload-{uuid.uuid4().hex[:8]}.txt"
    stem = Path(safe_name).stem or f"upload-{uuid.uuid4().hex[:8]}"
    suffix = Path(safe_name).suffix
    candidate = incoming_dir / safe_name
    counter = 1
    while candidate.exists():
        candidate = incoming_dir / f"{stem}-{counter}{suffix}"
        counter += 1
    return candidate


async def _read_json_body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Request body is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object.")
    return parsed


def _read_auto_tag_rules(*, request_id: str) -> JSONResponse:
    if not AUTO_TAG_RULES_PATH.exists():
        return _error_response(
            status_code=404,
            code="config_not_found",
            message="Auto-tag rules config not found.",
            request_id=request_id,
            details=[{"field": "path", "issue": f"missing file: {AUTO_TAG_RULES_PATH.relative_to(ROOT)}"}],
        )

    try:
        payload = json.loads(AUTO_TAG_RULES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _error_response(
            status_code=500,
            code="config_invalid",
            message=f"Auto-tag rules config is invalid JSON: {exc}",
            request_id=request_id,
            details=[{"field": "path", "issue": f"invalid file: {AUTO_TAG_RULES_PATH.relative_to(ROOT)}"}],
        )

    if not isinstance(payload, dict):
        return _error_response(
            status_code=500,
            code="config_invalid",
            message="Auto-tag rules config must be a JSON object.",
            request_id=request_id,
            details=[{"field": "path", "issue": f"invalid file: {AUTO_TAG_RULES_PATH.relative_to(ROOT)}"}],
        )

    return _json_response(200, payload)


def _enforce_api_and_rate_limit(
    request: Request,
    *,
    request_id: str,
    rate_limiter: InMemoryRateLimiter,
) -> Optional[JSONResponse]:
    auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
    if auth_error is not None:
        return auth_error
    return _enforce_rate_limit(request, request_id=request_id, rate_limiter=rate_limiter)


def _enforce_rate_limit(
    request: Request,
    *,
    request_id: str,
    rate_limiter: InMemoryRateLimiter,
) -> Optional[JSONResponse]:
    client_id = _rate_limit_client_id(request)
    allowed, retry_after_seconds = rate_limiter.allow(client_id=client_id)
    if allowed:
        return None
    return _error_response(
        status_code=429,
        code="rate_limited",
        message="Rate limit exceeded for client.",
        request_id=request_id,
        details=[{"field": "retry_after_seconds", "issue": f"retry after {retry_after_seconds} seconds"}],
    )


def _rate_limit_client_id(request: Request) -> str:
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        return f"api-key:{api_key}"
    client_host = request.client.host if request.client is not None else "unknown"
    return f"client:{client_host}"


def _enforce_api_key_if_configured(request: Request, *, request_id: str) -> Optional[JSONResponse]:
    expected = os.getenv("RECALL_API_KEY", "").strip()
    if not expected:
        return None

    provided = request.headers.get("X-API-Key", "").strip()
    if provided == expected:
        return None
    return _error_response(
        status_code=401,
        code="unauthorized",
        message="API key missing or invalid.",
        request_id=request_id,
    )


def _request_id() -> str:
    return obs_current_request_id() or _generated_request_id()


def _generated_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_positive_int_env(name: str, default_value: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default_value
    try:
        parsed = int(raw)
    except ValueError:
        return default_value
    if parsed <= 0:
        return default_value
    return parsed


def _cors_origins_from_env() -> list[str]:
    raw = os.getenv("RECALL_API_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).strip()
    if not raw:
        return []
    if raw == "*":
        return ["*"]
    origins = [value.strip() for value in raw.split(",") if value.strip()]
    return origins


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: Optional[list[dict[str, Optional[str]]]] = None,
) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "requestId": request_id,
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


def _json_response(status_code: int, payload: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)


APP = create_app()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Recall ingestion HTTP bridge.")
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind.")
    parser.add_argument("--port", type=int, default=8090, help="Port to bind.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.getenv("RECALL_API_KEY", "").strip()
    rate_limit_window_seconds = getattr(APP.state, "rate_limit_window_seconds", DEFAULT_RATE_LIMIT_WINDOW_SECONDS)
    rate_limit_max_requests = getattr(APP.state, "rate_limit_max_requests", DEFAULT_RATE_LIMIT_MAX_REQUESTS)
    if api_key:
        print("Recall ingestion bridge API key enforcement enabled.")
    else:
        print("[WARN] RECALL_API_KEY is unset; bridge running without API key enforcement.")
    print(
        "Rate limiting enabled: "
        f"{rate_limit_max_requests} requests/{rate_limit_window_seconds}s "
        f"({RATE_LIMIT_MAX_REQUESTS_ENV}/{RATE_LIMIT_WINDOW_ENV})."
    )

    print(f"Recall ingestion bridge listening on http://{args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    print(f"OpenAPI: http://{args.host}:{args.port}/openapi.json")
    uvicorn.run(APP, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
