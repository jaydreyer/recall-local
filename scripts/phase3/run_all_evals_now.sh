#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

N8N_HOST_OVERRIDE=""
WEBHOOK_URL_OVERRIDE=""
ALERT_WEBHOOK_URL_OVERRIDE=""

usage() {
  cat <<'EOF'
Usage:
  run_all_evals_now.sh [options]

Options:
  --n8n-host <url>            Override N8N host (example: http://localhost:5678)
  --webhook-url <url>         Override eval webhook URL directly
  --alert-webhook-url <url>   Optional regression alert webhook URL
  --help                      Show this help

Examples:
  run_all_evals_now.sh
  run_all_evals_now.sh --n8n-host http://100.116.103.78:5678
  run_all_evals_now.sh --webhook-url http://localhost:5678/webhook/recall-query
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --n8n-host)
      N8N_HOST_OVERRIDE="${2:-}"
      shift 2
      ;;
    --webhook-url)
      WEBHOOK_URL_OVERRIDE="${2:-}"
      shift 2
      ;;
    --alert-webhook-url)
      ALERT_WEBHOOK_URL_OVERRIDE="${2:-}"
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

if [[ -n "$N8N_HOST_OVERRIDE" ]]; then
  export N8N_HOST="$N8N_HOST_OVERRIDE"
fi
if [[ -n "$WEBHOOK_URL_OVERRIDE" ]]; then
  export RECALL_EVAL_WEBHOOK_URL="$WEBHOOK_URL_OVERRIDE"
fi
if [[ -n "$ALERT_WEBHOOK_URL_OVERRIDE" ]]; then
  export RECALL_ALERT_WEBHOOK_URL="$ALERT_WEBHOOK_URL_OVERRIDE"
fi

echo "Running eval suites via scripts/eval/scheduled_eval.sh"
"$ROOT_DIR/scripts/eval/scheduled_eval.sh"
