#!/usr/bin/env python3
"""Core bridge route registration helpers."""

from __future__ import annotations

import threading
from typing import Optional

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from scripts.phase1.bridge_routes_core_helpers import *  # noqa: F401,F403
from scripts.phase1.bridge_routes_middleware import *  # noqa: F401,F403
from scripts.phase1.bridge_routes_models import *  # noqa: F401,F403


def register_core_routes(app: FastAPI, *, rate_limiter: InMemoryRateLimiter, dashboard_cache_warmer: DashboardCacheWarmer | None) -> None:

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
