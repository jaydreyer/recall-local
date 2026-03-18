#!/usr/bin/env python3
"""Phase 6 bridge route registration helpers."""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from scripts.phase1.bridge_routes_middleware import *  # noqa: F401,F403
from scripts.phase1.bridge_routes_models import *  # noqa: F401,F403
from scripts.phase1.bridge_routes_phase6_helpers import *  # noqa: F401,F403


def _normalize_optional_iso8601(value: Any, *, field_name: str) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 datetime.") from exc
    return text


def register_phase6_routes(app: FastAPI, *, rate_limiter: InMemoryRateLimiter) -> None:
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
        description="Updates mutable job fields (`status`, `applied`, `dismissed`, `notes`, `workflow`).",
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

        allowed_fields = {"status", "applied", "dismissed", "notes", "workflow"}
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

        workflow_value = payload.get("workflow") if "workflow" in payload else None
        if workflow_value is not None:
            if not isinstance(workflow_value, dict):
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message="workflow must be an object.",
                    request_id=request_id,
                    details=[{"field": "workflow", "issue": "value must be an object"}],
                )

            allowed_workflow_fields = {"stage", "nextActionApproval", "packetApproval", "packet", "nextAction", "artifacts", "followUp"}
            unknown_workflow_fields = [key for key in workflow_value.keys() if key not in allowed_workflow_fields]
            if unknown_workflow_fields:
                return _error_response(
                    status_code=400,
                    code="validation_failed",
                    message="Invalid workflow payload.",
                    request_id=request_id,
                    details=[{"field": f"workflow.{key}", "issue": "field is not supported"} for key in unknown_workflow_fields],
                )

            if "stage" in workflow_value:
                normalized_stage = str(workflow_value.get("stage") or "").strip().lower()
                if normalized_stage not in {"focus", "review", "follow_up", "monitor", "closed"}:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Invalid workflow stage value.",
                        request_id=request_id,
                        details=[{"field": "workflow.stage", "issue": "allowed values: focus, review, follow_up, monitor, closed"}],
                    )
                workflow_value["stage"] = normalized_stage

            for approval_field in ("nextActionApproval", "packetApproval"):
                if approval_field in workflow_value:
                    normalized_approval = str(workflow_value.get(approval_field) or "").strip().lower()
                    if normalized_approval not in {"pending", "approved"}:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message=f"Invalid workflow approval value for {approval_field}.",
                            request_id=request_id,
                            details=[{"field": f"workflow.{approval_field}", "issue": "allowed values: pending, approved"}],
                        )
                    workflow_value[approval_field] = normalized_approval

            if "packet" in workflow_value:
                packet_value = workflow_value.get("packet")
                if not isinstance(packet_value, dict):
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="workflow.packet must be an object.",
                        request_id=request_id,
                        details=[{"field": "workflow.packet", "issue": "value must be an object"}],
                    )
                allowed_packet_fields = {
                    "tailoredSummary",
                    "resumeBullets",
                    "coverLetterDraft",
                    "outreachNote",
                    "interviewBrief",
                    "talkingPoints",
                }
                unknown_packet_fields = [key for key in packet_value.keys() if key not in allowed_packet_fields]
                if unknown_packet_fields:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Invalid workflow packet payload.",
                        request_id=request_id,
                        details=[{"field": f"workflow.packet.{key}", "issue": "field is not supported"} for key in unknown_packet_fields],
                    )
                try:
                    workflow_value["packet"] = {
                        key: _normalize_bool(value, field_name=f"workflow.packet.{key}")
                        for key, value in packet_value.items()
                    }
                except ValueError as exc:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message=str(exc),
                        request_id=request_id,
                    )

            if "nextAction" in workflow_value:
                next_action_value = workflow_value.get("nextAction")
                if not isinstance(next_action_value, dict):
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="workflow.nextAction must be an object.",
                        request_id=request_id,
                        details=[{"field": "workflow.nextAction", "issue": "value must be an object"}],
                    )
                allowed_next_action_fields = {"action", "rationale", "confidence", "dueAt"}
                unknown_next_action_fields = [key for key in next_action_value.keys() if key not in allowed_next_action_fields]
                if unknown_next_action_fields:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Invalid workflow next action payload.",
                        request_id=request_id,
                        details=[{"field": f"workflow.nextAction.{key}", "issue": "field is not supported"} for key in unknown_next_action_fields],
                    )
                if "action" in next_action_value:
                    normalized_action = str(next_action_value.get("action") or "").strip().lower()
                    if normalized_action not in {
                        "none",
                        "review_role",
                        "tailor_resume",
                        "hold",
                        "skip",
                        "follow_up",
                        "monitor_response",
                        "schedule_follow_up",
                        "send_follow_up",
                    }:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message="Invalid workflow next action value.",
                            request_id=request_id,
                            details=[{"field": "workflow.nextAction.action", "issue": "unsupported next action"}],
                        )
                    next_action_value["action"] = normalized_action
                if "confidence" in next_action_value:
                    normalized_confidence = str(next_action_value.get("confidence") or "").strip().lower()
                    if normalized_confidence not in {"low", "medium", "high"}:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message="Invalid workflow next action confidence value.",
                            request_id=request_id,
                            details=[{"field": "workflow.nextAction.confidence", "issue": "allowed values: low, medium, high"}],
                        )
                    next_action_value["confidence"] = normalized_confidence
                if "rationale" in next_action_value:
                    next_action_value["rationale"] = str(next_action_value.get("rationale") or "").strip() or None
                try:
                    if "dueAt" in next_action_value:
                        next_action_value["dueAt"] = _normalize_optional_iso8601(
                            next_action_value.get("dueAt"),
                            field_name="workflow.nextAction.dueAt",
                        )
                except ValueError as exc:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message=str(exc),
                        request_id=request_id,
                    )

            if "followUp" in workflow_value:
                follow_up_value = workflow_value.get("followUp")
                if not isinstance(follow_up_value, dict):
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="workflow.followUp must be an object.",
                        request_id=request_id,
                        details=[{"field": "workflow.followUp", "issue": "value must be an object"}],
                    )
                allowed_follow_up_fields = {"status", "dueAt", "lastCompletedAt"}
                unknown_follow_up_fields = [key for key in follow_up_value.keys() if key not in allowed_follow_up_fields]
                if unknown_follow_up_fields:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Invalid workflow follow-up payload.",
                        request_id=request_id,
                        details=[{"field": f"workflow.followUp.{key}", "issue": "field is not supported"} for key in unknown_follow_up_fields],
                    )
                if "status" in follow_up_value:
                    normalized_status = str(follow_up_value.get("status") or "").strip().lower()
                    if normalized_status not in {"not_scheduled", "scheduled", "completed"}:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message="Invalid workflow follow-up status value.",
                            request_id=request_id,
                            details=[{"field": "workflow.followUp.status", "issue": "allowed values: not_scheduled, scheduled, completed"}],
                        )
                    follow_up_value["status"] = normalized_status
                try:
                    if "dueAt" in follow_up_value:
                        follow_up_value["dueAt"] = _normalize_optional_iso8601(follow_up_value.get("dueAt"), field_name="workflow.followUp.dueAt")
                    if "lastCompletedAt" in follow_up_value:
                        follow_up_value["lastCompletedAt"] = _normalize_optional_iso8601(
                            follow_up_value.get("lastCompletedAt"),
                            field_name="workflow.followUp.lastCompletedAt",
                        )
                except ValueError as exc:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message=str(exc),
                        request_id=request_id,
                    )

            if "artifacts" in workflow_value:
                artifacts_value = workflow_value.get("artifacts")
                if not isinstance(artifacts_value, dict):
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="workflow.artifacts must be an object.",
                        request_id=request_id,
                        details=[{"field": "workflow.artifacts", "issue": "value must be an object"}],
                    )
                allowed_artifact_fields = {
                    "coverLetterDraft",
                    "tailoredSummary",
                    "resumeBullets",
                    "outreachNote",
                    "interviewBrief",
                    "talkingPoints",
                }
                unknown_artifact_fields = [key for key in artifacts_value.keys() if key not in allowed_artifact_fields]
                if unknown_artifact_fields:
                    return _error_response(
                        status_code=400,
                        code="validation_failed",
                        message="Invalid workflow artifacts payload.",
                        request_id=request_id,
                        details=[{"field": f"workflow.artifacts.{key}", "issue": "field is not supported"} for key in unknown_artifact_fields],
                    )
                if "coverLetterDraft" in artifacts_value:
                    cover_letter_value = artifacts_value.get("coverLetterDraft")
                    if not isinstance(cover_letter_value, dict):
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message="workflow.artifacts.coverLetterDraft must be an object.",
                            request_id=request_id,
                            details=[{"field": "workflow.artifacts.coverLetterDraft", "issue": "value must be an object"}],
                        )
                    allowed_cover_letter_fields = {"draftId", "generatedAt", "provider", "model", "wordCount", "savedToVault", "vaultPath"}
                    unknown_cover_letter_fields = [key for key in cover_letter_value.keys() if key not in allowed_cover_letter_fields]
                    if unknown_cover_letter_fields:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message="Invalid cover letter artifact payload.",
                            request_id=request_id,
                            details=[{"field": f"workflow.artifacts.coverLetterDraft.{key}", "issue": "field is not supported"} for key in unknown_cover_letter_fields],
                        )
                    try:
                        if "generatedAt" in cover_letter_value:
                            cover_letter_value["generatedAt"] = _normalize_optional_iso8601(
                                cover_letter_value.get("generatedAt"),
                                field_name="workflow.artifacts.coverLetterDraft.generatedAt",
                            )
                        if "savedToVault" in cover_letter_value:
                            cover_letter_value["savedToVault"] = _normalize_bool(
                                cover_letter_value.get("savedToVault"),
                                field_name="workflow.artifacts.coverLetterDraft.savedToVault",
                            )
                        if "wordCount" in cover_letter_value and cover_letter_value.get("wordCount") is not None:
                            cover_letter_value["wordCount"] = int(cover_letter_value.get("wordCount"))
                    except (ValueError, TypeError) as exc:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message=str(exc),
                            request_id=request_id,
                        )
                for artifact_key in ("tailoredSummary", "resumeBullets", "outreachNote", "interviewBrief", "talkingPoints"):
                    if artifact_key not in artifacts_value:
                        continue
                    packet_artifact_value = artifacts_value.get(artifact_key)
                    if not isinstance(packet_artifact_value, dict):
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message=f"workflow.artifacts.{artifact_key} must be an object.",
                            request_id=request_id,
                            details=[{"field": f"workflow.artifacts.{artifact_key}", "issue": "value must be an object"}],
                        )
                    allowed_packet_artifact_fields = {"status", "updatedAt", "source", "vaultPath", "notes"}
                    unknown_packet_artifact_fields = [
                        key for key in packet_artifact_value.keys() if key not in allowed_packet_artifact_fields
                    ]
                    if unknown_packet_artifact_fields:
                        return _error_response(
                            status_code=400,
                            code="validation_failed",
                            message=f"Invalid workflow artifact payload for {artifact_key}.",
                            request_id=request_id,
                            details=[
                                {"field": f"workflow.artifacts.{artifact_key}.{key}", "issue": "field is not supported"}
                                for key in unknown_packet_artifact_fields
                            ],
                        )
                    if "status" in packet_artifact_value:
                        normalized_status = str(packet_artifact_value.get("status") or "").strip().lower()
                        if normalized_status not in {"draft", "ready"}:
                            return _error_response(
                                status_code=400,
                                code="validation_failed",
                                message=f"Invalid workflow artifact status for {artifact_key}.",
                                request_id=request_id,
                                details=[{"field": f"workflow.artifacts.{artifact_key}.status", "issue": "allowed values: draft, ready"}],
                            )
                        packet_artifact_value["status"] = normalized_status
                    if "source" in packet_artifact_value:
                        normalized_source = str(packet_artifact_value.get("source") or "").strip().lower()
                        if normalized_source not in {"manual", "generated", "imported"}:
                            return _error_response(
                                status_code=400,
                                code="validation_failed",
                                message=f"Invalid workflow artifact source for {artifact_key}.",
                                request_id=request_id,
                                details=[
                                    {
                                        "field": f"workflow.artifacts.{artifact_key}.source",
                                        "issue": "allowed values: manual, generated, imported",
                                    }
                                ],
                            )
                        packet_artifact_value["source"] = normalized_source
                    if "updatedAt" in packet_artifact_value:
                        try:
                            packet_artifact_value["updatedAt"] = _normalize_optional_iso8601(
                                packet_artifact_value.get("updatedAt"),
                                field_name=f"workflow.artifacts.{artifact_key}.updatedAt",
                            )
                        except ValueError as exc:
                            return _error_response(
                                status_code=400,
                                code="validation_failed",
                                message=str(exc),
                                request_id=request_id,
                            )
                    if "vaultPath" in packet_artifact_value:
                        packet_artifact_value["vaultPath"] = str(packet_artifact_value.get("vaultPath") or "").strip() or None
                    if "notes" in packet_artifact_value:
                        packet_artifact_value["notes"] = str(packet_artifact_value.get("notes") or "").strip() or None

        updated = phase6_update_job(
            job_id=jobId,
            status=status_value,
            applied=applied_value,
            dismissed=dismissed_value,
            notes=notes_value,
            workflow=workflow_value,
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
        f"{API_PREFIX}/tailored-summaries",
        tags=["Tailored Summaries"],
        summary="Create tailored summary",
        description="Generates a tailored summary artifact from the current resume and one evaluated job.",
        responses={
            200: {
                "description": "Tailored summary generated.",
                "content": {"application/json": {"example": TAILORED_SUMMARY_SUCCESS_EXAMPLE}},
            },
            400: {"model": ErrorResponse, "description": "Invalid summary payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            500: {"model": ErrorResponse, "description": "Summary generation failed."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": TAILORED_SUMMARY_REQUEST_BODY},
    )
    async def create_tailored_summary(request: Request) -> JSONResponse:
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
            result = phase6_generate_tailored_summary(
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
                message=f"Tailored summary generation failed: {exc}",
                request_id=request_id,
            )
        phase6_update_job(
            job_id=job_id,
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"tailoredSummary": True},
                "artifacts": {
                    "tailoredSummary": {
                        "status": "ready",
                        "updatedAt": result.get("generated_at"),
                        "source": "generated",
                        "vaultPath": result.get("vault_path"),
                        "notes": str(result.get("summary") or "").strip()[:280] or None,
                    }
                },
            },
        )
        return _json_response(200, {"workflow": "workflow_06a_tailored_summary", **result})

    @app.post(
        f"{API_PREFIX}/resume-bullets",
        tags=["Resume Bullets"],
        summary="Create resume bullets",
        description="Generates tailored resume bullets from the current resume and one evaluated job.",
        responses={
            200: {
                "description": "Resume bullets generated.",
                "content": {"application/json": {"example": RESUME_BULLETS_SUCCESS_EXAMPLE}},
            },
            400: {"model": ErrorResponse, "description": "Invalid resume-bullets payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            500: {"model": ErrorResponse, "description": "Resume bullets generation failed."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": RESUME_BULLETS_REQUEST_BODY},
    )
    async def create_resume_bullets(request: Request) -> JSONResponse:
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
            result = phase6_generate_resume_bullets(
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
                message=f"Resume bullets generation failed: {exc}",
                request_id=request_id,
            )
        phase6_update_job(
            job_id=job_id,
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"resumeBullets": True},
                "artifacts": {
                    "resumeBullets": {
                        "status": "ready",
                        "updatedAt": result.get("generated_at"),
                        "source": "generated",
                        "vaultPath": result.get("vault_path"),
                        "notes": str(result.get("bullets") or "").strip() or None,
                    }
                },
            },
        )
        return _json_response(200, {"workflow": "workflow_06a_resume_bullets", **result})

    @app.post(
        f"{API_PREFIX}/interview-briefs",
        tags=["Interview Briefs"],
        summary="Create interview brief",
        description="Generates an interview brief artifact from the current resume and one evaluated job.",
        responses={
            200: {
                "description": "Interview brief generated.",
                "content": {"application/json": {"example": INTERVIEW_BRIEF_SUCCESS_EXAMPLE}},
            },
            400: {"model": ErrorResponse, "description": "Invalid interview-brief payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            500: {"model": ErrorResponse, "description": "Interview brief generation failed."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": INTERVIEW_BRIEF_REQUEST_BODY},
    )
    async def create_interview_brief(request: Request) -> JSONResponse:
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
            result = phase6_generate_interview_brief(
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
                message=f"Interview brief generation failed: {exc}",
                request_id=request_id,
            )
        phase6_update_job(
            job_id=job_id,
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"interviewBrief": True},
                "artifacts": {
                    "interviewBrief": {
                        "status": "ready",
                        "updatedAt": result.get("generated_at"),
                        "source": "generated",
                        "vaultPath": result.get("vault_path"),
                        "notes": str(result.get("brief") or "").strip() or None,
                    }
                },
            },
        )
        return _json_response(200, {"workflow": "workflow_06a_interview_brief", **result})

    @app.post(
        f"{API_PREFIX}/talking-points",
        tags=["Talking Points"],
        summary="Create talking points",
        description="Generates interview talking points from the current resume and one evaluated job.",
        responses={
            200: {
                "description": "Talking points generated.",
                "content": {"application/json": {"example": TALKING_POINTS_SUCCESS_EXAMPLE}},
            },
            400: {"model": ErrorResponse, "description": "Invalid talking-points payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            500: {"model": ErrorResponse, "description": "Talking points generation failed."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": TALKING_POINTS_REQUEST_BODY},
    )
    async def create_talking_points(request: Request) -> JSONResponse:
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
            result = phase6_generate_talking_points(
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
                message=f"Talking points generation failed: {exc}",
                request_id=request_id,
            )
        phase6_update_job(
            job_id=job_id,
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"talkingPoints": True},
                "artifacts": {
                    "talkingPoints": {
                        "status": "ready",
                        "updatedAt": result.get("generated_at"),
                        "source": "generated",
                        "vaultPath": result.get("vault_path"),
                        "notes": str(result.get("talking_points") or "").strip() or None,
                    }
                },
            },
        )
        return _json_response(200, {"workflow": "workflow_06a_talking_points", **result})

    @app.post(
        f"{API_PREFIX}/outreach-notes",
        tags=["Outreach Notes"],
        summary="Create outreach note",
        description="Generates an outreach note artifact from the current resume and one evaluated job.",
        responses={
            200: {
                "description": "Outreach note generated.",
                "content": {"application/json": {"example": OUTREACH_NOTE_SUCCESS_EXAMPLE}},
            },
            400: {"model": ErrorResponse, "description": "Invalid outreach payload.", "content": {"application/json": {"example": ERROR_EXAMPLE_VALIDATION}}},
            401: {"model": ErrorResponse, "description": "Missing or invalid API key.", "content": {"application/json": {"example": ERROR_EXAMPLE_UNAUTHORIZED}}},
            404: {"model": ErrorResponse, "description": "Job not found."},
            500: {"model": ErrorResponse, "description": "Outreach note generation failed."},
            **RATE_LIMIT_ERROR_RESPONSE,
        },
        openapi_extra={"requestBody": OUTREACH_NOTE_REQUEST_BODY},
    )
    async def create_outreach_note(request: Request) -> JSONResponse:
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
            result = phase6_generate_outreach_note(
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
                message=f"Outreach note generation failed: {exc}",
                request_id=request_id,
            )
        phase6_update_job(
            job_id=job_id,
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"outreachNote": True},
                "artifacts": {
                    "outreachNote": {
                        "status": "ready",
                        "updatedAt": result.get("generated_at"),
                        "source": "generated",
                        "vaultPath": result.get("vault_path"),
                        "notes": str(result.get("note") or "").strip() or None,
                    }
                },
            },
        )
        return _json_response(200, {"workflow": "workflow_06a_outreach_note", **result})

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
        phase6_update_job(
            job_id=job_id,
            status=None,
            applied=None,
            dismissed=None,
            notes=None,
            workflow={
                "packet": {"coverLetterDraft": True},
                "artifacts": {
                    "coverLetterDraft": {
                        "draftId": result.get("draft_id"),
                        "generatedAt": result.get("generated_at"),
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "wordCount": result.get("word_count"),
                        "savedToVault": result.get("saved_to_vault"),
                        "vaultPath": result.get("vault_path"),
                    }
                },
            },
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
