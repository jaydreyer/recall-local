#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8090}"
API_KEY="${RECALL_API_KEY:-}"
INCLUDE_GAPS="${RECALL_DASHBOARD_SMOKE_INCLUDE_GAPS:-false}"

python3 - "$BASE_URL" "$API_KEY" "$INCLUDE_GAPS" <<'PY'
import json
import sys
import urllib.request

base_url = sys.argv[1].rstrip("/")
api_key = sys.argv[2].strip()
include_gaps = sys.argv[3].strip().lower() in {"1", "true", "yes", "on"}
url = f"{base_url}/v1/dashboard-checks?include_gaps={'true' if include_gaps else 'false'}"
headers = {"Accept": "application/json"}
if api_key:
    headers["X-API-Key"] = api_key

request = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(request, timeout=60) as response:
    payload = json.load(response)

status = str(payload.get("status") or "").strip().lower()
jobs = payload.get("jobs") or {}
companies = payload.get("companies") or {}
gaps = payload.get("gaps") or {}

if status != "ok":
    raise SystemExit(f"dashboard-checks returned non-ok status: {status}\n{json.dumps(payload, indent=2)}")
if int(jobs.get("count") or 0) <= 0:
    raise SystemExit(f"dashboard-checks reported no jobs\n{json.dumps(payload, indent=2)}")
if int(companies.get("count") or 0) <= 0:
    raise SystemExit(f"dashboard-checks reported no companies\n{json.dumps(payload, indent=2)}")
if include_gaps and gaps and str(gaps.get("status") or "").strip().lower() != "ok":
    raise SystemExit(f"dashboard-checks reported degraded gaps\n{json.dumps(payload, indent=2)}")

print(json.dumps(payload, indent=2))
PY
