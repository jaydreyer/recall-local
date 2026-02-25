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
import threading
import time
import uuid
from collections import deque
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.channel_adapters import normalize_payload  # noqa: E402
from scripts.phase1.group_model import CANONICAL_GROUPS, normalize_group  # noqa: E402
from scripts.phase1.ingest_from_payload import payload_to_requests  # noqa: E402
from scripts.phase1.ingestion_pipeline import ingest_request  # noqa: E402
from scripts.phase1.rag_query import run_rag_query  # noqa: E402
from scripts.phase5.vault_sync import list_vault_tree, run_vault_sync_once  # noqa: E402
from scripts.phase2.meeting_action_items import run_meeting_action_items  # noqa: E402
from scripts.phase2.meeting_from_payload import payload_to_meeting_kwargs  # noqa: E402


ALLOWED_INGEST_CHANNELS = ("webhook", "bookmarklet", "ios-share", "gmail-forward")
API_NAME = "operations-v1"
API_MAJOR_VERSION = "v1"
API_PREFIX = f"/{API_MAJOR_VERSION}"
AUTO_TAG_RULES_PATH = ROOT / "config" / "auto_tag_rules.json"
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 120
RATE_LIMIT_WINDOW_ENV = "RECALL_API_RATE_LIMIT_WINDOW_SECONDS"
RATE_LIMIT_MAX_REQUESTS_ENV = "RECALL_API_RATE_LIMIT_MAX_REQUESTS"
DEFAULT_ACTIVITY_LIMIT = 25
DEFAULT_RECENT_EVAL_RUNS = 5
DEFAULT_EVAL_RUN_TIMEOUT_SECONDS = 900
DEFAULT_CORS_ORIGINS = "*"
CANONICAL_GROUP_ENUM = list(CANONICAL_GROUPS)


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


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(..., description="Bridge health status.")


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
                        "filter_tags": ["job-search", "anthropic"],
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
        openapi_tags=[
            {"name": "Health", "description": "Service liveness endpoints."},
            {"name": "Ingestions", "description": "Create ingestion operations from supported channels."},
            {"name": "RAG Queries", "description": "Run cited retrieval-augmented queries."},
            {"name": "Meeting Action Items", "description": "Extract action items and structured notes from meeting transcripts."},
            {"name": "Auto Tag Rules", "description": "Read shared auto-tag configuration for dashboard and extension clients."},
            {"name": "Vault", "description": "List vault notes and trigger Obsidian vault sync operations."},
            {"name": "Activities", "description": "Read recent ingestion activity for dashboard monitoring."},
            {"name": "Evaluations", "description": "Read latest eval metrics and trigger eval runs."},
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
    for index, item in enumerate(requests):
        try:
            result = ingest_request(item, dry_run=dry_run)
            results.append(asdict(result))
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
    return _json_response(200 if not errors else 207, response)


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
        return [DEFAULT_CORS_ORIGINS]
    if raw == "*":
        return ["*"]
    origins = [value.strip() for value in raw.split(",") if value.strip()]
    return origins or [DEFAULT_CORS_ORIGINS]


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
