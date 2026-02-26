#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

BRIDGE_URL="${RECALL_BRIDGE_URL:-http://localhost:8090}"
API_KEY="${RECALL_API_KEY:-}"
DEMO_MODE="dry-run"
RUN_EXTENSION_BROWSER_SMOKE="false"
EVAL_SUITE="${RECALL_PHASE5_EVAL_SUITE:-core}"
EVAL_BACKEND="${RECALL_PHASE5_EVAL_BACKEND:-direct}"
EVAL_WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-}"
REQUIRE_EVAL_PASS="false"
ARTIFACT_ROOT="${RECALL_PHASE5_DEMO_ARTIFACT_DIR:-$ROOT_DIR/data/artifacts/demos/phase5}"

usage() {
  cat <<'HELP'
Usage:
  run_phase5_demo_now.sh [options]

Options:
  --bridge-url <url>                    Bridge base URL (default: RECALL_BRIDGE_URL or http://localhost:8090)
  --api-key <value>                     API key header value (default: RECALL_API_KEY)
  --mode <dry-run|live>                 Run demo in dry-run (default) or live mode
  --eval-suite <core|job-search|learning|both>
                                        Eval suite for gate check (default: core)
  --eval-backend <direct|webhook>       Eval backend (default: direct)
  --eval-webhook-url <url>              Optional webhook URL override for eval backend=webhook
  --require-eval-pass                   Fail run when eval status is not "pass"
  --run-extension-browser-smoke         Run Gmail browser smoke harness (requires Playwright + GUI support)
  --skip-extension-browser-smoke        Skip Gmail browser smoke harness (default)
  --artifact-root <path>                Override artifact root directory
  --help                                Show this help

Examples:
  run_phase5_demo_now.sh
  run_phase5_demo_now.sh --bridge-url http://100.116.103.78:8090 --mode dry-run --eval-suite both
  run_phase5_demo_now.sh --mode live --api-key phase5-secret --require-eval-pass
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bridge-url)
      BRIDGE_URL="${2:-}"
      shift 2
      ;;
    --api-key)
      API_KEY="${2:-}"
      shift 2
      ;;
    --mode)
      DEMO_MODE="${2:-}"
      shift 2
      ;;
    --eval-suite)
      EVAL_SUITE="${2:-}"
      shift 2
      ;;
    --eval-backend)
      EVAL_BACKEND="${2:-}"
      shift 2
      ;;
    --eval-webhook-url)
      EVAL_WEBHOOK_URL="${2:-}"
      shift 2
      ;;
    --require-eval-pass)
      REQUIRE_EVAL_PASS="true"
      shift
      ;;
    --run-extension-browser-smoke)
      RUN_EXTENSION_BROWSER_SMOKE="true"
      shift
      ;;
    --skip-extension-browser-smoke)
      RUN_EXTENSION_BROWSER_SMOKE="false"
      shift
      ;;
    --artifact-root)
      ARTIFACT_ROOT="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$DEMO_MODE" in
  dry-run)
    DEMO_DRY_RUN=true
    ;;
  live)
    DEMO_DRY_RUN=false
    ;;
  *)
    echo "Invalid --mode: $DEMO_MODE (allowed: dry-run, live)" >&2
    exit 2
    ;;
esac

case "$EVAL_SUITE" in
  core|job-search|learning|both)
    ;;
  *)
    echo "Invalid --eval-suite: $EVAL_SUITE (allowed: core, job-search, learning, both)" >&2
    exit 2
    ;;
esac

case "$EVAL_BACKEND" in
  direct|webhook)
    ;;
  *)
    echo "Invalid --eval-backend: $EVAL_BACKEND (allowed: direct, webhook)" >&2
    exit 2
    ;;
esac

if [[ "$EVAL_BACKEND" == "webhook" && -z "$EVAL_WEBHOOK_URL" ]]; then
  N8N_HOST="${N8N_HOST:-http://localhost:5678}"
  EVAL_WEBHOOK_URL="${N8N_HOST%/}/webhook/recall-query"
fi

BRIDGE_BASE_URL="${BRIDGE_URL%/}"
BRIDGE_API_BASE="${BRIDGE_BASE_URL}/v1"

mkdir -p "$ARTIFACT_ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="$ARTIFACT_ROOT/$STAMP"
mkdir -p "$RUN_DIR"

VAULT_FIXTURE_DIR=""
cleanup() {
  if [[ -n "${VAULT_FIXTURE_DIR:-}" && -d "$VAULT_FIXTURE_DIR" ]]; then
    rm -rf "$VAULT_FIXTURE_DIR"
  fi
}
trap cleanup EXIT

LOG_FILE="$RUN_DIR/phase5_demo.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Phase 5 demo run start: $STAMP ==="
echo "RUN_DIR=$RUN_DIR"
echo "BRIDGE_API_BASE=$BRIDGE_API_BASE"
echo "DEMO_MODE=$DEMO_MODE"
echo "DEMO_DRY_RUN=$DEMO_DRY_RUN"
echo "API_KEY_CONFIGURED=$([[ -n "$API_KEY" ]] && echo true || echo false)"
echo "EVAL_SUITE=$EVAL_SUITE"
echo "EVAL_BACKEND=$EVAL_BACKEND"
echo "RUN_EXTENSION_BROWSER_SMOKE=$RUN_EXTENSION_BROWSER_SMOKE"
echo

CURL_COMMON=(curl -sS --fail-with-body)

request_json() {
  local method="$1"
  local url="$2"
  local body_file="$3"
  local out_file="$4"
  local -a cmd

  cmd=("${CURL_COMMON[@]}" -X "$method")
  if [[ -n "$API_KEY" ]]; then
    cmd+=(-H "X-API-Key: $API_KEY")
  fi

  if [[ -n "$body_file" ]]; then
    cmd+=(-H "content-type: application/json" --data @"$body_file" "$url")
  else
    cmd+=("$url")
  fi

  "${cmd[@]}" >"$out_file"
}

echo "[1/5] Bridge preflight for demo lanes"
request_json GET "$BRIDGE_API_BASE/healthz" "" "$RUN_DIR/healthz.json"
request_json GET "$BRIDGE_API_BASE/auto-tag-rules" "" "$RUN_DIR/auto_tag_rules.json"
python3 - "$RUN_DIR/healthz.json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
if payload.get("status") != "ok":
    raise SystemExit(f"healthz did not return status=ok: {payload}")
PY
echo "[PASS] bridge health + auto-tag rules"
echo

echo "[2/5] Dashboard ingest/query lane"
cat >"$RUN_DIR/dashboard_ingest_request.json" <<JSON
{
  "channel": "bookmarklet",
  "type": "text",
  "title": "Phase 5 dashboard lane ingest",
  "content": "Phase 5 dashboard ingest demo at $STAMP",
  "group": "job-search",
  "tags": ["phase5", "dashboard-demo"],
  "source": "dashboard"
}
JSON
request_json POST "$BRIDGE_API_BASE/ingestions?dry_run=$DEMO_DRY_RUN" "$RUN_DIR/dashboard_ingest_request.json" "$RUN_DIR/dashboard_ingest_response.json"

cat >"$RUN_DIR/dashboard_query_request.json" <<JSON
{
  "query": "Which URL source is indexed in memory?",
  "mode": "default",
  "top_k": 5,
  "min_score": 0.15
}
JSON
request_json POST "$BRIDGE_API_BASE/rag-queries?dry_run=$DEMO_DRY_RUN" "$RUN_DIR/dashboard_query_request.json" "$RUN_DIR/dashboard_query_response.json"
python3 - "$RUN_DIR/dashboard_ingest_response.json" "$RUN_DIR/dashboard_query_response.json" <<'PY'
import json
import sys

ingest = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
query = json.loads(open(sys.argv[2], "r", encoding="utf-8").read())

if ingest.get("workflow") != "workflow_01_ingestion":
    raise SystemExit(f"unexpected ingest workflow: {ingest.get('workflow')}")
if query.get("workflow") != "workflow_02_rag_query":
    raise SystemExit(f"unexpected query workflow: {query.get('workflow')}")
query_result = query.get("result") or {}
citations = query_result.get("citations")
if not isinstance(citations, list) or len(citations) < 1:
    raise SystemExit(f"dashboard query did not return citations: {query_result}")
PY
echo "[PASS] dashboard ingest/query calls"
echo

echo "[3/5] Extension capture lane"
python3 -m unittest discover -s "$ROOT_DIR/tests" -p "test_phase5e1_gmail_extension.py" >"$RUN_DIR/extension_unittest.log" 2>&1
echo "[PASS] extension contract tests: test_phase5e1_gmail_extension.py"

cat >"$RUN_DIR/extension_ingest_request.json" <<JSON
{
  "channel": "gmail-forward",
  "type": "email",
  "title": "Phase 5 extension lane ingest",
  "content": "Sender: recruiter@openai.com\\nSubject: Solutions Engineer interview follow-up\\nBody: Please review the role packet before next steps.",
  "group": "job-search",
  "tags": ["phase5", "extension-demo", "openai"],
  "source": "chrome-extension"
}
JSON
request_json POST "$BRIDGE_API_BASE/ingestions?dry_run=$DEMO_DRY_RUN" "$RUN_DIR/extension_ingest_request.json" "$RUN_DIR/extension_ingest_response.json"
python3 - "$RUN_DIR/extension_ingest_response.json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
if payload.get("workflow") != "workflow_01_ingestion":
    raise SystemExit(f"unexpected extension ingest workflow: {payload.get('workflow')}")
if payload.get("channel") != "gmail-forward":
    raise SystemExit(f"unexpected extension ingest channel: {payload.get('channel')}")
PY
echo "[PASS] extension channel ingest call (gmail-forward)"

if [[ "$RUN_EXTENSION_BROWSER_SMOKE" == "true" ]]; then
  GMAIL_SMOKE_SCRIPT="$ROOT_DIR/output/playwright/phase5e1_gmail_smoke.cjs"
  if [[ ! -f "$GMAIL_SMOKE_SCRIPT" ]]; then
    echo "Missing Gmail smoke script: $GMAIL_SMOKE_SCRIPT" >&2
    exit 1
  fi
  node "$GMAIL_SMOKE_SCRIPT" >"$RUN_DIR/extension_browser_smoke.log" 2>&1
  if [[ -f "$ROOT_DIR/output/playwright/phase5e1_gmail_smoke_result.json" ]]; then
    cp "$ROOT_DIR/output/playwright/phase5e1_gmail_smoke_result.json" "$RUN_DIR/extension_browser_smoke_result.json"
  fi
  if [[ -f "$ROOT_DIR/output/playwright/phase5e1_gmail_smoke.png" ]]; then
    cp "$ROOT_DIR/output/playwright/phase5e1_gmail_smoke.png" "$RUN_DIR/extension_browser_smoke.png"
  fi
  python3 - "$RUN_DIR/extension_browser_smoke_result.json" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
if not payload.get("success"):
    raise SystemExit(f"browser smoke reported failure: {payload}")
PY
  echo "[PASS] extension Gmail browser smoke"
else
  echo "[SKIP] extension browser smoke (enable with --run-extension-browser-smoke)"
fi
echo

echo "[4/5] Obsidian sync/query lane"
BRIDGE_HOSTPORT="${BRIDGE_BASE_URL#*://}"
BRIDGE_HOST="${BRIDGE_HOSTPORT%%/*}"
BRIDGE_HOST="${BRIDGE_HOST%%:*}"
USE_LOCAL_VAULT_FIXTURE=false
case "$BRIDGE_HOST" in
  localhost|127.0.0.1|::1)
    USE_LOCAL_VAULT_FIXTURE=true
    ;;
esac

if [[ "$USE_LOCAL_VAULT_FIXTURE" == "true" ]]; then
  VAULT_FIXTURE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/recall-phase5-vault-demo-XXXXXX")"
  mkdir -p "$VAULT_FIXTURE_DIR/career"
  cat >"$VAULT_FIXTURE_DIR/career/phase5-demo-note.md" <<'MD'
---
title: "Phase 5 Demo Vault Note"
tags:
  - obsidian
  - interview-prep
---

# Phase 5 Vault Demo

This note validates the vault sync lane for the Phase 5 run script.
Reference link: [[Interview Checklist]]
#job-search
MD

  python3 - "$RUN_DIR/vault_sync_request.json" "$VAULT_FIXTURE_DIR" "$DEMO_DRY_RUN" <<'PY'
import json
import sys

out_path = sys.argv[1]
vault_path = sys.argv[2]
dry_run = sys.argv[3].strip().lower() == "true"
payload = {"dry_run": dry_run, "max_files": 10, "vault_path": vault_path}
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
  echo "Using local vault fixture: $VAULT_FIXTURE_DIR"
else
  python3 - "$RUN_DIR/vault_sync_request.json" "$DEMO_DRY_RUN" <<'PY'
import json
import sys

out_path = sys.argv[1]
dry_run = sys.argv[2].strip().lower() == "true"
payload = {"dry_run": dry_run, "max_files": 10}
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
  echo "Using bridge-configured vault path for host: $BRIDGE_HOST"
fi

request_json POST "$BRIDGE_API_BASE/vault-syncs" "$RUN_DIR/vault_sync_request.json" "$RUN_DIR/vault_sync_response.json"

cat >"$RUN_DIR/vault_query_request.json" <<JSON
{
  "query": "Summarize vault notes related to interview preparation.",
  "mode": "job-search",
  "filter_group": "job-search",
  "filter_tags": ["obsidian", "interview-prep"],
  "top_k": 5,
  "min_score": 0.15
}
JSON
request_json POST "$BRIDGE_API_BASE/rag-queries?dry_run=$DEMO_DRY_RUN" "$RUN_DIR/vault_query_request.json" "$RUN_DIR/vault_query_response.json"

python3 - "$RUN_DIR/vault_sync_response.json" "$RUN_DIR/vault_query_response.json" <<'PY'
import json
import sys

sync_payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
query_payload = json.loads(open(sys.argv[2], "r", encoding="utf-8").read())

if sync_payload.get("workflow") != "workflow_05c_vault_sync":
    raise SystemExit(f"unexpected vault sync workflow: {sync_payload.get('workflow')}")
if query_payload.get("workflow") != "workflow_02_rag_query":
    raise SystemExit(f"unexpected vault query workflow: {query_payload.get('workflow')}")
PY
echo "[PASS] vault sync/query calls"
echo

echo "[5/5] Eval gate lane"
python3 - "$RUN_DIR/eval_run_request.json" "$EVAL_SUITE" "$EVAL_BACKEND" "$DEMO_DRY_RUN" "$EVAL_WEBHOOK_URL" <<'PY'
import json
import sys

out_path = sys.argv[1]
suite = sys.argv[2]
backend = sys.argv[3]
dry_run = sys.argv[4].strip().lower() == "true"
webhook_url = sys.argv[5].strip()

payload = {
    "suite": suite,
    "backend": backend,
    "dry_run": dry_run,
    "wait": True,
}
if backend == "webhook" and webhook_url:
    payload["webhook_url"] = webhook_url

with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY

request_json POST "$BRIDGE_API_BASE/evaluation-runs" "$RUN_DIR/eval_run_request.json" "$RUN_DIR/eval_run_response.json"
request_json GET "$BRIDGE_API_BASE/evaluations?latest=true" "" "$RUN_DIR/evaluations_latest_response.json"

python3 - "$RUN_DIR/eval_run_response.json" "$RUN_DIR/evaluations_latest_response.json" "$REQUIRE_EVAL_PASS" <<'PY'
import json
import sys

run_payload = json.loads(open(sys.argv[1], "r", encoding="utf-8").read())
latest_payload = json.loads(open(sys.argv[2], "r", encoding="utf-8").read())
require_eval_pass = sys.argv[3].strip().lower() == "true"

if run_payload.get("workflow") != "workflow_05d_eval_run":
    raise SystemExit(f"unexpected eval run workflow: {run_payload.get('workflow')}")
if not run_payload.get("accepted"):
    raise SystemExit(f"eval run not accepted: {run_payload}")

run = run_payload.get("run") or {}
if str(run.get("status", "")).lower() != "completed":
    raise SystemExit(f"eval run did not complete synchronously: {run_payload}")

result = run.get("result") or {}
result_status = str(result.get("status", "")).lower()
if require_eval_pass and result_status != "pass":
    raise SystemExit(f"eval run completed but did not pass: status={result_status}")

if latest_payload.get("workflow") != "workflow_05d_eval_latest":
    raise SystemExit(f"unexpected eval latest workflow: {latest_payload.get('workflow')}")
PY
echo "[PASS] eval run + latest summary calls"
echo

python3 - "$RUN_DIR" "$STAMP" "$DEMO_MODE" "$DEMO_DRY_RUN" "$RUN_EXTENSION_BROWSER_SMOKE" "$EVAL_SUITE" "$EVAL_BACKEND" <<'PY'
import json
import pathlib
import sys

run_dir = pathlib.Path(sys.argv[1])
stamp = sys.argv[2]
demo_mode = sys.argv[3]
demo_dry_run = sys.argv[4].strip().lower() == "true"
extension_browser_smoke = sys.argv[5].strip().lower() == "true"
eval_suite = sys.argv[6]
eval_backend = sys.argv[7]

ingest_payload = json.loads((run_dir / "dashboard_ingest_response.json").read_text(encoding="utf-8"))
query_payload = json.loads((run_dir / "dashboard_query_response.json").read_text(encoding="utf-8"))
vault_payload = json.loads((run_dir / "vault_sync_response.json").read_text(encoding="utf-8"))
eval_payload = json.loads((run_dir / "eval_run_response.json").read_text(encoding="utf-8"))

summary = {
    "workflow": "workflow_05f_demo_run",
    "run_id": stamp,
    "mode": demo_mode,
    "dry_run": demo_dry_run,
    "extension_browser_smoke_enabled": extension_browser_smoke,
    "eval_suite": eval_suite,
    "eval_backend": eval_backend,
    "dashboard_ingest_status": ingest_payload.get("workflow"),
    "dashboard_query_status": query_payload.get("workflow"),
    "vault_sync_status": vault_payload.get("workflow"),
    "eval_run_status": (eval_payload.get("run") or {}).get("status"),
    "eval_result_status": ((eval_payload.get("run") or {}).get("result") or {}).get("status"),
}

summary_path = run_dir / "phase5_demo_summary.json"
summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(f"SUMMARY_FILE={summary_path}")
PY

echo
echo "=== Phase 5 demo run end: $(date -u +%Y%m%dT%H%M%SZ) ==="
echo "LOG_FILE=$LOG_FILE"
