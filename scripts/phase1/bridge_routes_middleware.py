#!/usr/bin/env python3
"""Route middleware and protocol primitives for bridge endpoints."""

import sys

_main_module = sys.modules.get("__main__")
if _main_module and str(getattr(_main_module, "__file__", "")).endswith("ingest_bridge_api.py"):
    _bridge_api = _main_module
else:
    from scripts.phase1 import ingest_bridge_api as _bridge_api

API_PREFIX = _bridge_api.API_PREFIX
ERROR_EXAMPLE_UNAUTHORIZED = _bridge_api.ERROR_EXAMPLE_UNAUTHORIZED
ERROR_EXAMPLE_VALIDATION = _bridge_api.ERROR_EXAMPLE_VALIDATION
ERROR_EXAMPLE_WORKFLOW = _bridge_api.ERROR_EXAMPLE_WORKFLOW
RATE_LIMIT_ERROR_RESPONSE = _bridge_api.RATE_LIMIT_ERROR_RESPONSE

InMemoryRateLimiter = _bridge_api.InMemoryRateLimiter
DashboardCacheWarmer = _bridge_api.DashboardCacheWarmer

_request_id = _bridge_api._request_id
_enforce_api_and_rate_limit = _bridge_api._enforce_api_and_rate_limit
_json_response = _bridge_api._json_response
_error_response = _bridge_api._error_response
_read_json_body = _bridge_api._read_json_body
_normalize_bool = _bridge_api._normalize_bool
_normalize_optional_positive_int = _bridge_api._normalize_optional_positive_int
_normalize_optional_string = _bridge_api._normalize_optional_string
_normalize_company_watch_payload = _bridge_api._normalize_company_watch_payload

__all__ = [
    "API_PREFIX",
    "ERROR_EXAMPLE_UNAUTHORIZED",
    "ERROR_EXAMPLE_VALIDATION",
    "ERROR_EXAMPLE_WORKFLOW",
    "RATE_LIMIT_ERROR_RESPONSE",
    "InMemoryRateLimiter",
    "DashboardCacheWarmer",
    "_request_id",
    "_enforce_api_and_rate_limit",
    "_json_response",
    "_error_response",
    "_read_json_body",
    "_normalize_bool",
    "_normalize_optional_positive_int",
    "_normalize_optional_string",
    "_normalize_company_watch_payload",
]
