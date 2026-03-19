#!/usr/bin/env python3
"""Phase 6 bridge helper exports for route registration."""

import sys
from typing import Any

_main_module = sys.modules.get("__main__")
if _main_module and str(getattr(_main_module, "__file__", "")).endswith("ingest_bridge_api.py"):
    _bridge_api = _main_module
else:
    from scripts.phase1 import ingest_bridge_api as _bridge_api

PHASE6_JOB_STATUSES = _bridge_api.PHASE6_JOB_STATUSES
PHASE6_JOB_SOURCES = _bridge_api.PHASE6_JOB_SOURCES


def phase6_list_jobs(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_list_jobs(*args, **kwargs)


def phase6_get_job(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_get_job(*args, **kwargs)


def phase6_update_job(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_update_job(*args, **kwargs)


def phase6_queue_job_evaluations(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_queue_job_evaluations(*args, **kwargs)


def phase6_queue_follow_up_reminder_runs(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_queue_follow_up_reminder_runs(*args, **kwargs)


def phase6_job_stats(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_job_stats(*args, **kwargs)


def phase6_all_jobs(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_all_jobs(*args, **kwargs)


def phase6_aggregate_gaps(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_aggregate_gaps(*args, **kwargs)


def phase6_check_job_duplicate(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_check_job_duplicate(*args, **kwargs)


def phase6_ensure_collections(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_ensure_collections(*args, **kwargs)


def phase6_run_discovery(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_run_discovery(*args, **kwargs)


def phase6_ingest_resume(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_ingest_resume(*args, **kwargs)


phase6_storage = _bridge_api.phase6_storage


def phase6_list_company_profiles(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_list_company_profiles(*args, **kwargs)


def phase6_get_company_profile(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_get_company_profile(*args, **kwargs)


def phase6_upsert_tracked_company_config(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_upsert_tracked_company_config(*args, **kwargs)


def phase6_update_company_tier(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_update_company_tier(*args, **kwargs)


def phase6_refresh_company_profile(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_refresh_company_profile(*args, **kwargs)


def phase6_generate_cover_letter_draft(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_generate_cover_letter_draft(*args, **kwargs)


def phase6_generate_tailored_summary(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_generate_tailored_summary(*args, **kwargs)


def phase6_generate_outreach_note(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_generate_outreach_note(*args, **kwargs)


def phase6_generate_resume_bullets(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_generate_resume_bullets(*args, **kwargs)


def phase6_generate_interview_brief(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_generate_interview_brief(*args, **kwargs)


def phase6_generate_talking_points(*args: Any, **kwargs: Any) -> Any:
    return _bridge_api.phase6_generate_talking_points(*args, **kwargs)

JOB_PATCH_REQUEST_BODY = _bridge_api.JOB_PATCH_REQUEST_BODY
JOB_EVALUATION_RUN_REQUEST_BODY = _bridge_api.JOB_EVALUATION_RUN_REQUEST_BODY
FOLLOW_UP_REMINDER_RUN_REQUEST_BODY = _bridge_api.FOLLOW_UP_REMINDER_RUN_REQUEST_BODY
JOB_STATS_SUCCESS_EXAMPLE = _bridge_api.JOB_STATS_SUCCESS_EXAMPLE
FOLLOW_UP_REMINDER_RUN_COMPLETED_EXAMPLE = _bridge_api.FOLLOW_UP_REMINDER_RUN_COMPLETED_EXAMPLE
JOB_GAPS_SUCCESS_EXAMPLE = _bridge_api.JOB_GAPS_SUCCESS_EXAMPLE
JOB_DEDUP_REQUEST_BODY = _bridge_api.JOB_DEDUP_REQUEST_BODY
JOB_DISCOVERY_RUN_REQUEST_BODY = _bridge_api.JOB_DISCOVERY_RUN_REQUEST_BODY
RESUME_REQUEST_BODY = _bridge_api.RESUME_REQUEST_BODY
COMPANY_CREATE_REQUEST_BODY = _bridge_api.COMPANY_CREATE_REQUEST_BODY
COMPANY_PATCH_REQUEST_BODY = _bridge_api.COMPANY_PATCH_REQUEST_BODY
COVER_LETTER_DRAFT_REQUEST_BODY = _bridge_api.COVER_LETTER_DRAFT_REQUEST_BODY
TAILORED_SUMMARY_REQUEST_BODY = _bridge_api.TAILORED_SUMMARY_REQUEST_BODY
OUTREACH_NOTE_REQUEST_BODY = _bridge_api.OUTREACH_NOTE_REQUEST_BODY
RESUME_BULLETS_REQUEST_BODY = _bridge_api.RESUME_BULLETS_REQUEST_BODY
INTERVIEW_BRIEF_REQUEST_BODY = _bridge_api.INTERVIEW_BRIEF_REQUEST_BODY
TALKING_POINTS_REQUEST_BODY = _bridge_api.TALKING_POINTS_REQUEST_BODY
LLM_SETTINGS_PATCH_REQUEST_BODY = _bridge_api.LLM_SETTINGS_PATCH_REQUEST_BODY

__all__ = [
    "PHASE6_JOB_STATUSES",
    "PHASE6_JOB_SOURCES",
    "phase6_list_jobs",
    "phase6_get_job",
    "phase6_update_job",
    "JOB_PATCH_REQUEST_BODY",
    "phase6_queue_job_evaluations",
    "JOB_EVALUATION_RUN_REQUEST_BODY",
    "phase6_queue_follow_up_reminder_runs",
    "FOLLOW_UP_REMINDER_RUN_REQUEST_BODY",
    "FOLLOW_UP_REMINDER_RUN_COMPLETED_EXAMPLE",
    "JOB_STATS_SUCCESS_EXAMPLE",
    "phase6_job_stats",
    "JOB_GAPS_SUCCESS_EXAMPLE",
    "phase6_all_jobs",
    "phase6_aggregate_gaps",
    "JOB_DEDUP_REQUEST_BODY",
    "phase6_check_job_duplicate",
    "JOB_DISCOVERY_RUN_REQUEST_BODY",
    "phase6_ensure_collections",
    "phase6_run_discovery",
    "RESUME_REQUEST_BODY",
    "phase6_ingest_resume",
    "phase6_storage",
    "phase6_list_company_profiles",
    "phase6_get_company_profile",
    "COMPANY_CREATE_REQUEST_BODY",
    "phase6_upsert_tracked_company_config",
    "phase6_update_company_tier",
    "COMPANY_PATCH_REQUEST_BODY",
    "phase6_refresh_company_profile",
    "COVER_LETTER_DRAFT_REQUEST_BODY",
    "phase6_generate_cover_letter_draft",
    "TAILORED_SUMMARY_REQUEST_BODY",
    "phase6_generate_tailored_summary",
    "OUTREACH_NOTE_REQUEST_BODY",
    "phase6_generate_outreach_note",
    "RESUME_BULLETS_REQUEST_BODY",
    "phase6_generate_resume_bullets",
    "INTERVIEW_BRIEF_REQUEST_BODY",
    "phase6_generate_interview_brief",
    "TALKING_POINTS_REQUEST_BODY",
    "phase6_generate_talking_points",
    "LLM_SETTINGS_PATCH_REQUEST_BODY",
]
