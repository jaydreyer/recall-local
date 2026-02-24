#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

BRIDGE_URL="${RECALL_BRIDGE_URL:-http://localhost:8090}"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"
N8N_BASE_URL="${N8N_HOST%/}"
WEBHOOK_URL="${RECALL_QUERY_WEBHOOK_URL:-$N8N_BASE_URL/webhook/recall-query}"
CHECK_WEBHOOK="true"

usage() {
  cat <<'HELP'
Usage:
  run_service_preflight_now.sh [options]

Options:
  --bridge-url <url>      Override bridge URL (default: http://localhost:8090)
  --n8n-host <url>        Override n8n host (default: http://localhost:5678)
  --webhook-url <url>     Override query webhook URL
  --skip-webhook-check    Skip n8n query webhook dry-run check
  --help                  Show this help

Examples:
  run_service_preflight_now.sh
  run_service_preflight_now.sh --n8n-host http://100.116.103.78:5678
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bridge-url)
      BRIDGE_URL="${2:-}"
      shift 2
      ;;
    --n8n-host)
      N8N_HOST="${2:-}"
      N8N_BASE_URL="${N8N_HOST%/}"
      WEBHOOK_URL="${RECALL_QUERY_WEBHOOK_URL:-$N8N_BASE_URL/webhook/recall-query}"
      shift 2
      ;;
    --webhook-url)
      WEBHOOK_URL="${2:-}"
      shift 2
      ;;
    --skip-webhook-check)
      CHECK_WEBHOOK="false"
      shift
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

echo "[1/3] Core connectivity checks"
python3 "$ROOT_DIR/scripts/phase0/connectivity_check.py"

echo

echo "[2/3] Bridge health"
curl -fsS "$BRIDGE_URL/healthz" >/dev/null
echo "[PASS] bridge health: $BRIDGE_URL/healthz"

if [[ "$CHECK_WEBHOOK" == "true" ]]; then
  webhook_dry_run_url="$WEBHOOK_URL"
  if [[ "$WEBHOOK_URL" == *"?"* ]]; then
    webhook_dry_run_url="${WEBHOOK_URL}&dry_run=true"
  else
    webhook_dry_run_url="${WEBHOOK_URL}?dry_run=true"
  fi

  echo
  echo "[3/3] Workflow 02 webhook dry-run"
  curl -fsS -X POST "$webhook_dry_run_url" \
    -H "content-type: application/json" \
    -d '{"query":"Phase 3C preflight dry-run query","mode":"default","top_k":3,"min_score":0.15}' >/dev/null
  echo "[PASS] webhook query dry-run: $webhook_dry_run_url"
else
  echo
  echo "[3/3] Workflow 02 webhook dry-run (skipped)"
fi

echo

echo "Preflight checks passed."
