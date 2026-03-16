#!/usr/bin/env python3
"""Core bridge helper and orchestration exports for route registration."""

from scripts.phase1 import ingest_bridge_api as _bridge_api

from typing import Any

DEFAULT_ACTIVITY_LIMIT = _bridge_api.DEFAULT_ACTIVITY_LIMIT
DEFAULT_RECENT_EVAL_RUNS = _bridge_api.DEFAULT_RECENT_EVAL_RUNS

_dashboard_checks_payload = _bridge_api._dashboard_checks_payload
_read_auto_tag_rules = _bridge_api._read_auto_tag_rules
_process_ingestion = _bridge_api._process_ingestion
_process_file_upload = _bridge_api._process_file_upload
_process_rag_query = _bridge_api._process_rag_query
_process_meeting_action_items = _bridge_api._process_meeting_action_items
_normalize_group_filter = _bridge_api._normalize_group_filter
_read_recent_activity = _bridge_api._read_recent_activity
_read_latest_evaluations = _bridge_api._read_latest_evaluations
_list_eval_runs = _bridge_api._list_eval_runs
_queue_eval_run = _bridge_api._queue_eval_run
_execute_eval_run = _bridge_api._execute_eval_run
_get_eval_run = _bridge_api._get_eval_run

def list_vault_tree() -> dict[str, Any]:
    return _bridge_api.list_vault_tree()


def run_vault_sync_once(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _bridge_api.run_vault_sync_once(*args, **kwargs)

__all__ = [
    "DEFAULT_ACTIVITY_LIMIT",
    "DEFAULT_RECENT_EVAL_RUNS",
    "_dashboard_checks_payload",
    "_read_auto_tag_rules",
    "_process_ingestion",
    "_process_file_upload",
    "_process_rag_query",
    "_process_meeting_action_items",
    "_normalize_group_filter",
    "_read_recent_activity",
    "_read_latest_evaluations",
    "_list_eval_runs",
    "_queue_eval_run",
    "_execute_eval_run",
    "_get_eval_run",
    "list_vault_tree",
    "run_vault_sync_once",
]
