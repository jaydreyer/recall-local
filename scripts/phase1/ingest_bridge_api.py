#!/usr/bin/env python3
"""FastAPI bridge for Recall workflows when n8n Execute Command is unavailable."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, Optional

import uvicorn
from fastapi import FastAPI, Path as ApiPath, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.channel_adapters import normalize_payload  # noqa: E402
from scripts.phase1.ingest_from_payload import payload_to_requests  # noqa: E402
from scripts.phase1.ingestion_pipeline import ingest_request  # noqa: E402
from scripts.phase1.rag_query import run_rag_query  # noqa: E402
from scripts.phase2.meeting_action_items import run_meeting_action_items  # noqa: E402
from scripts.phase2.meeting_from_payload import payload_to_meeting_kwargs  # noqa: E402


ALLOWED_INGEST_CHANNELS = ("webhook", "bookmarklet", "ios-share", "gmail-forward")
API_NAME = "operations-v1"
API_MAJOR_VERSION = "v1"
API_PREFIX = f"/{API_MAJOR_VERSION}"


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

INGEST_SUCCESS_EXAMPLE = {
    "workflow": "workflow_01_ingestion",
    "channel": "bookmarklet",
    "normalized_payload": {
        "type": "url",
        "content": "https://example.com/job-posting",
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


def create_app() -> FastAPI:
    server_local = os.getenv("RECALL_API_SERVER_LOCAL", "http://localhost:8090").strip() or "http://localhost:8090"
    server_ai_lab = os.getenv("RECALL_API_SERVER_AI_LAB", "http://100.116.103.78:8090").strip() or "http://100.116.103.78:8090"

    app = FastAPI(
        title=API_NAME,
        version=API_MAJOR_VERSION,
        description=(
            "Recall.local bridge for ingestion, cited RAG querying, and meeting action extraction.\n\n"
            "Authentication: if `RECALL_API_KEY` is configured, send it via `X-API-Key`."
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
        ],
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

    @app.get("/healthz", include_in_schema=False)
    @app.get("/health", include_in_schema=False)
    async def health_alias() -> JSONResponse:
        return _json_response(200, {"status": "ok"})

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
        },
        openapi_extra={"requestBody": INGEST_REQUEST_BODY},
    )
    async def create_ingestion(
        request: Request,
        dry_run: bool = Query(False, description="If true, normalize and validate payload without persistence side effects."),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

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

    @app.post("/ingest/{channel}", include_in_schema=False)
    async def create_ingestion_legacy(
        request: Request,
        channel: str = ApiPath(..., description="Legacy ingestion channel selector."),
        dry_run: bool = Query(False),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        payload_channel = channel.strip()
        payload_body = payload
        if not payload_channel:
            payload_channel = str(payload.get("channel", "")).strip()
            payload_body = dict(payload)
            payload_body.pop("channel", None)

        return _process_ingestion(channel=payload_channel, payload=payload_body, dry_run=dry_run, request_id=request_id)

    @app.post("/ingestions", include_in_schema=False)
    async def create_ingestion_alias_unversioned(
        request: Request,
        dry_run: bool = Query(False),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        payload_channel = str(payload.get("channel", "")).strip()
        payload_body = dict(payload)
        payload_body.pop("channel", None)

        return _process_ingestion(channel=payload_channel, payload=payload_body, dry_run=dry_run, request_id=request_id)

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
        },
        openapi_extra={"requestBody": RAG_REQUEST_BODY},
    )
    async def create_rag_query(
        request: Request,
        dry_run: bool = Query(False, description="If true, skip SQLite writes and artifact persistence."),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        return _process_rag_query(payload=payload, dry_run=dry_run, request_id=request_id)

    @app.post("/rag-queries", include_in_schema=False)
    @app.post("/query/rag", include_in_schema=False)
    @app.post("/rag/query", include_in_schema=False)
    async def create_rag_query_legacy(
        request: Request,
        dry_run: bool = Query(False),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

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
        },
        openapi_extra={"requestBody": MEETING_REQUEST_BODY},
    )
    async def create_meeting_action_items(
        request: Request,
        dry_run: bool = Query(False, description="If true, run extraction without writing durable run artifacts."),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        return _process_meeting_action_items(payload=payload, dry_run=dry_run, request_id=request_id)

    @app.post("/meeting-action-items", include_in_schema=False)
    @app.post("/meeting/action-items", include_in_schema=False)
    @app.post("/meeting/actions", include_in_schema=False)
    @app.post("/query/meeting", include_in_schema=False)
    async def create_meeting_action_items_legacy(
        request: Request,
        dry_run: bool = Query(False),
    ) -> JSONResponse:
        request_id = _request_id()
        auth_error = _enforce_api_key_if_configured(request, request_id=request_id)
        if auth_error is not None:
            return auth_error

        try:
            payload = await _read_json_body(request)
        except ValueError as exc:
            return _error_response(status_code=400, code="invalid_json", message=str(exc), request_id=request_id)

        return _process_meeting_action_items(payload=payload, dry_run=dry_run, request_id=request_id)

    @app.get("/{_path:path}", include_in_schema=False)
    async def not_found_get(_path: str) -> JSONResponse:
        _ = _path
        return _error_response(status_code=404, code="not_found", message="Not found.", request_id=_request_id())

    @app.post("/{_path:path}", include_in_schema=False)
    async def not_found_post(_path: str) -> JSONResponse:
        _ = _path
        return _error_response(status_code=404, code="not_found", message="Unknown path.", request_id=_request_id())

    return app


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
        retrieval_mode_value = str(retrieval_mode) if retrieval_mode is not None else None
        hybrid_alpha_value = float(hybrid_alpha) if hybrid_alpha is not None else None
        reranker_weight_value = float(reranker_weight) if reranker_weight is not None else None
        enable_reranker_value = _normalize_bool(enable_reranker) if enable_reranker is not None else None
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


APP = create_app()


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


def _normalize_bool(value: Any) -> bool:
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
    raise ValueError("enable_reranker must be boolean-like.")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Recall ingestion HTTP bridge.")
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind.")
    parser.add_argument("--port", type=int, default=8090, help="Port to bind.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.getenv("RECALL_API_KEY", "").strip()
    if api_key:
        print("Recall ingestion bridge API key enforcement enabled.")
    else:
        print("[WARN] RECALL_API_KEY is unset; bridge running without API key enforcement.")

    print(f"Recall ingestion bridge listening on http://{args.host}:{args.port}")
    print(f"API docs: http://{args.host}:{args.port}/docs")
    print(f"OpenAPI: http://{args.host}:{args.port}/openapi.json")
    uvicorn.run(APP, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
