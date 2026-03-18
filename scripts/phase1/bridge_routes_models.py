#!/usr/bin/env python3
"""Bridge OpenAPI response contracts shared by route registration modules."""

import sys

_main_module = sys.modules.get("__main__")
if _main_module and str(getattr(_main_module, "__file__", "")).endswith("ingest_bridge_api.py"):
    _bridge_api = _main_module
else:
    from scripts.phase1 import ingest_bridge_api as _bridge_api

HealthResponse = _bridge_api.HealthResponse
DashboardChecksResponse = _bridge_api.DashboardChecksResponse
ErrorResponse = _bridge_api.ErrorResponse
AutoTagRulesResponse = _bridge_api.AutoTagRulesResponse
IngestWorkflowResponse = _bridge_api.IngestWorkflowResponse
FileIngestionResponse = _bridge_api.FileIngestionResponse
RagWorkflowResponse = _bridge_api.RagWorkflowResponse
MeetingWorkflowResponse = _bridge_api.MeetingWorkflowResponse
VaultTreeResponse = _bridge_api.VaultTreeResponse
VaultSyncResponse = _bridge_api.VaultSyncResponse
ActivityResponse = _bridge_api.ActivityResponse
EvaluationLatestResponse = _bridge_api.EvaluationLatestResponse
EvaluationRunAcceptedResponse = _bridge_api.EvaluationRunAcceptedResponse
JobsCollectionResponse = _bridge_api.JobsCollectionResponse
JobEvaluationRunResponse = _bridge_api.JobEvaluationRunResponse
TailoredSummaryResponse = _bridge_api.TailoredSummaryResponse
OutreachNoteResponse = _bridge_api.OutreachNoteResponse
ResumeBulletsResponse = _bridge_api.ResumeBulletsResponse
InterviewBriefResponse = _bridge_api.InterviewBriefResponse
TalkingPointsResponse = _bridge_api.TalkingPointsResponse
ResumeIngestionResponse = _bridge_api.ResumeIngestionResponse

AUTO_TAG_RULES_SUCCESS_EXAMPLE = _bridge_api.AUTO_TAG_RULES_SUCCESS_EXAMPLE
ERROR_EXAMPLE_CONFIG_NOT_FOUND = _bridge_api.ERROR_EXAMPLE_CONFIG_NOT_FOUND
ERROR_EXAMPLE_CONFIG_INVALID = _bridge_api.ERROR_EXAMPLE_CONFIG_INVALID
INGEST_SUCCESS_EXAMPLE = _bridge_api.INGEST_SUCCESS_EXAMPLE
INGEST_REQUEST_BODY = _bridge_api.INGEST_REQUEST_BODY
FILE_INGEST_SUCCESS_EXAMPLE = _bridge_api.FILE_INGEST_SUCCESS_EXAMPLE
FILE_INGEST_REQUEST_BODY = _bridge_api.FILE_INGEST_REQUEST_BODY
RAG_SUCCESS_EXAMPLE = _bridge_api.RAG_SUCCESS_EXAMPLE
RAG_REQUEST_BODY = _bridge_api.RAG_REQUEST_BODY
MEETING_SUCCESS_EXAMPLE = _bridge_api.MEETING_SUCCESS_EXAMPLE
MEETING_REQUEST_BODY = _bridge_api.MEETING_REQUEST_BODY
VAULT_TREE_SUCCESS_EXAMPLE = _bridge_api.VAULT_TREE_SUCCESS_EXAMPLE
VAULT_SYNC_SUCCESS_EXAMPLE = _bridge_api.VAULT_SYNC_SUCCESS_EXAMPLE
VAULT_SYNC_REQUEST_BODY = _bridge_api.VAULT_SYNC_REQUEST_BODY
ACTIVITY_SUCCESS_EXAMPLE = _bridge_api.ACTIVITY_SUCCESS_EXAMPLE
EVAL_LATEST_SUCCESS_EXAMPLE = _bridge_api.EVAL_LATEST_SUCCESS_EXAMPLE
EVAL_RUN_COMPLETED_EXAMPLE = _bridge_api.EVAL_RUN_COMPLETED_EXAMPLE
EVAL_RUN_ACCEPTED_EXAMPLE = _bridge_api.EVAL_RUN_ACCEPTED_EXAMPLE
EVAL_RUN_REQUEST_BODY = _bridge_api.EVAL_RUN_REQUEST_BODY
JOBS_LIST_SUCCESS_EXAMPLE = _bridge_api.JOBS_LIST_SUCCESS_EXAMPLE
JOB_EVALUATION_RUN_COMPLETED_EXAMPLE = _bridge_api.JOB_EVALUATION_RUN_COMPLETED_EXAMPLE
JOB_EVALUATION_RUN_ACCEPTED_EXAMPLE = _bridge_api.JOB_EVALUATION_RUN_ACCEPTED_EXAMPLE
JOB_EVALUATION_RUN_REQUEST_BODY = _bridge_api.JOB_EVALUATION_RUN_REQUEST_BODY
JOB_STATS_SUCCESS_EXAMPLE = _bridge_api.JOB_STATS_SUCCESS_EXAMPLE
JOB_GAPS_SUCCESS_EXAMPLE = _bridge_api.JOB_GAPS_SUCCESS_EXAMPLE
JOB_DEDUP_REQUEST_BODY = _bridge_api.JOB_DEDUP_REQUEST_BODY
JOB_DISCOVERY_RUN_REQUEST_BODY = _bridge_api.JOB_DISCOVERY_RUN_REQUEST_BODY
RESUME_SUCCESS_EXAMPLE = _bridge_api.RESUME_SUCCESS_EXAMPLE
RESUME_REQUEST_BODY = _bridge_api.RESUME_REQUEST_BODY
COMPANY_SUCCESS_EXAMPLE = _bridge_api.COMPANY_SUCCESS_EXAMPLE
COMPANY_CREATE_REQUEST_BODY = _bridge_api.COMPANY_CREATE_REQUEST_BODY
COMPANY_PATCH_REQUEST_BODY = _bridge_api.COMPANY_PATCH_REQUEST_BODY
COVER_LETTER_DRAFT_SUCCESS_EXAMPLE = _bridge_api.COVER_LETTER_DRAFT_SUCCESS_EXAMPLE
COVER_LETTER_DRAFT_REQUEST_BODY = _bridge_api.COVER_LETTER_DRAFT_REQUEST_BODY
TAILORED_SUMMARY_SUCCESS_EXAMPLE = _bridge_api.TAILORED_SUMMARY_SUCCESS_EXAMPLE
TAILORED_SUMMARY_REQUEST_BODY = _bridge_api.TAILORED_SUMMARY_REQUEST_BODY
OUTREACH_NOTE_SUCCESS_EXAMPLE = _bridge_api.OUTREACH_NOTE_SUCCESS_EXAMPLE
OUTREACH_NOTE_REQUEST_BODY = _bridge_api.OUTREACH_NOTE_REQUEST_BODY
RESUME_BULLETS_SUCCESS_EXAMPLE = _bridge_api.RESUME_BULLETS_SUCCESS_EXAMPLE
RESUME_BULLETS_REQUEST_BODY = _bridge_api.RESUME_BULLETS_REQUEST_BODY
INTERVIEW_BRIEF_SUCCESS_EXAMPLE = _bridge_api.INTERVIEW_BRIEF_SUCCESS_EXAMPLE
INTERVIEW_BRIEF_REQUEST_BODY = _bridge_api.INTERVIEW_BRIEF_REQUEST_BODY
TALKING_POINTS_SUCCESS_EXAMPLE = _bridge_api.TALKING_POINTS_SUCCESS_EXAMPLE
TALKING_POINTS_REQUEST_BODY = _bridge_api.TALKING_POINTS_REQUEST_BODY
LLM_SETTINGS_SUCCESS_EXAMPLE = _bridge_api.LLM_SETTINGS_SUCCESS_EXAMPLE
LLM_SETTINGS_PATCH_REQUEST_BODY = _bridge_api.LLM_SETTINGS_PATCH_REQUEST_BODY

__all__ = [
    "HealthResponse",
    "DashboardChecksResponse",
    "ErrorResponse",
    "AutoTagRulesResponse",
    "IngestWorkflowResponse",
    "FileIngestionResponse",
    "RagWorkflowResponse",
    "MeetingWorkflowResponse",
    "VaultTreeResponse",
    "VaultSyncResponse",
    "ActivityResponse",
    "EvaluationLatestResponse",
    "EvaluationRunAcceptedResponse",
    "JobsCollectionResponse",
    "JobEvaluationRunResponse",
    "TailoredSummaryResponse",
    "OutreachNoteResponse",
    "ResumeBulletsResponse",
    "InterviewBriefResponse",
    "TalkingPointsResponse",
    "ResumeIngestionResponse",
    "AUTO_TAG_RULES_SUCCESS_EXAMPLE",
    "ERROR_EXAMPLE_CONFIG_NOT_FOUND",
    "ERROR_EXAMPLE_CONFIG_INVALID",
    "INGEST_SUCCESS_EXAMPLE",
    "INGEST_REQUEST_BODY",
    "FILE_INGEST_SUCCESS_EXAMPLE",
    "FILE_INGEST_REQUEST_BODY",
    "RAG_SUCCESS_EXAMPLE",
    "RAG_REQUEST_BODY",
    "MEETING_SUCCESS_EXAMPLE",
    "MEETING_REQUEST_BODY",
    "VAULT_TREE_SUCCESS_EXAMPLE",
    "VAULT_SYNC_SUCCESS_EXAMPLE",
    "VAULT_SYNC_REQUEST_BODY",
    "ACTIVITY_SUCCESS_EXAMPLE",
    "EVAL_LATEST_SUCCESS_EXAMPLE",
    "EVAL_RUN_COMPLETED_EXAMPLE",
    "EVAL_RUN_ACCEPTED_EXAMPLE",
    "EVAL_RUN_REQUEST_BODY",
    "JOBS_LIST_SUCCESS_EXAMPLE",
    "JOB_EVALUATION_RUN_COMPLETED_EXAMPLE",
    "JOB_EVALUATION_RUN_ACCEPTED_EXAMPLE",
    "JOB_EVALUATION_RUN_REQUEST_BODY",
    "JOB_STATS_SUCCESS_EXAMPLE",
    "JOB_GAPS_SUCCESS_EXAMPLE",
    "JOB_DEDUP_REQUEST_BODY",
    "JOB_DISCOVERY_RUN_REQUEST_BODY",
    "RESUME_SUCCESS_EXAMPLE",
    "RESUME_REQUEST_BODY",
    "COMPANY_SUCCESS_EXAMPLE",
    "COMPANY_CREATE_REQUEST_BODY",
    "COMPANY_PATCH_REQUEST_BODY",
    "COVER_LETTER_DRAFT_SUCCESS_EXAMPLE",
    "COVER_LETTER_DRAFT_REQUEST_BODY",
    "TAILORED_SUMMARY_SUCCESS_EXAMPLE",
    "TAILORED_SUMMARY_REQUEST_BODY",
    "OUTREACH_NOTE_SUCCESS_EXAMPLE",
    "OUTREACH_NOTE_REQUEST_BODY",
    "RESUME_BULLETS_SUCCESS_EXAMPLE",
    "RESUME_BULLETS_REQUEST_BODY",
    "INTERVIEW_BRIEF_SUCCESS_EXAMPLE",
    "INTERVIEW_BRIEF_REQUEST_BODY",
    "TALKING_POINTS_SUCCESS_EXAMPLE",
    "TALKING_POINTS_REQUEST_BODY",
    "LLM_SETTINGS_SUCCESS_EXAMPLE",
    "LLM_SETTINGS_PATCH_REQUEST_BODY",
]
