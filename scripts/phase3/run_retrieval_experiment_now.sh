#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

N8N_HOST_OVERRIDE=""
WEBHOOK_URL_OVERRIDE=""
CASES_FILE_OVERRIDE=""

usage() {
  cat <<'EOF'
Usage:
  run_retrieval_experiment_now.sh [options]

Options:
  --n8n-host <url>      Override n8n host (example: http://localhost:5678)
  --webhook-url <url>   Override eval webhook URL directly
  --cases-file <path>   Override eval cases file path
  --help                Show this help

Examples:
  run_retrieval_experiment_now.sh
  run_retrieval_experiment_now.sh --n8n-host http://100.116.103.78:5678
  run_retrieval_experiment_now.sh --cases-file /home/jaydreyer/recall-local/scripts/eval/learning_eval_cases.json
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
    --cases-file)
      CASES_FILE_OVERRIDE="${2:-}"
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
if [[ -n "$CASES_FILE_OVERRIDE" ]]; then
  export RECALL_PHASE3B_CASES_FILE="$CASES_FILE_OVERRIDE"
fi

echo "Running Phase 3B retrieval experiment"
"$ROOT_DIR/scripts/eval/run_phase3b_retrieval_experiment.sh"
