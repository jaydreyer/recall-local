#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

MODE="${RECALL_QUERY_MODE:-default}"
QUERY="${RECALL_QUERY_TEXT:-}"
TOP_K="${RECALL_QUERY_TOP_K:-}"
MIN_SCORE="${RECALL_QUERY_MIN_SCORE:-}"
MAX_RETRIES="${RECALL_QUERY_MAX_RETRIES:-}"
FILTER_TAGS="${RECALL_QUERY_FILTER_TAGS:-}"
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage:
  run_query_mode_now.sh [options]

Options:
  --mode <default|job-search|learning>  Query mode (default: default)
  --query <text>                         Query text (defaults by mode if omitted)
  --top-k <int>                          Override top-k
  --min-score <float>                    Override min score
  --max-retries <int>                    Override retry count
  --filter-tags <csv>                    Override filter tags
  --dry-run                              Skip artifact/SQLite writes
  --help                                 Show this help

Examples:
  run_query_mode_now.sh --mode default
  run_query_mode_now.sh --mode job-search --query "What should I emphasize for OpenAI?"
  run_query_mode_now.sh --mode learning --dry-run
EOF
}

normalize_mode() {
  local value
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    default|rag)
      printf '%s' "default"
      ;;
    job-search|job_search|jobsearch)
      printf '%s' "job-search"
      ;;
    learning|learn)
      printf '%s' "learning"
      ;;
    *)
      echo "Unsupported mode: $1" >&2
      exit 2
      ;;
  esac
}

default_query_for_mode() {
  local mode="$1"
  case "$mode" in
    default)
      printf '%s' "Summarize what content has been indexed and cite sources."
      ;;
    job-search)
      printf '%s' "What should I emphasize for a solutions engineer interview?"
      ;;
    learning)
      printf '%s' "Summarize key tradeoffs between managed and self-hosted RAG architectures."
      ;;
    *)
      echo "Unsupported mode: $mode" >&2
      exit 2
      ;;
  esac
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --query)
      QUERY="${2:-}"
      shift 2
      ;;
    --top-k)
      TOP_K="${2:-}"
      shift 2
      ;;
    --min-score)
      MIN_SCORE="${2:-}"
      shift 2
      ;;
    --max-retries)
      MAX_RETRIES="${2:-}"
      shift 2
      ;;
    --filter-tags)
      FILTER_TAGS="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
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

MODE="$(normalize_mode "$MODE")"
if [[ -z "$QUERY" ]]; then
  QUERY="$(default_query_for_mode "$MODE")"
fi

if [[ -z "$FILTER_TAGS" ]]; then
  case "$MODE" in
    job-search)
      FILTER_TAGS="job-search"
      ;;
    learning)
      FILTER_TAGS="learning,genai-docs"
      ;;
    default)
      FILTER_TAGS=""
      ;;
  esac
fi

cmd=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/phase1/rag_query.py"
  --query "$QUERY"
  --mode "$MODE"
)

if [[ -n "$TOP_K" ]]; then
  cmd+=(--top-k "$TOP_K")
fi
if [[ -n "$MIN_SCORE" ]]; then
  cmd+=(--min-score "$MIN_SCORE")
fi
if [[ -n "$MAX_RETRIES" ]]; then
  cmd+=(--max-retries "$MAX_RETRIES")
fi
if [[ -n "$FILTER_TAGS" ]]; then
  cmd+=(--filter-tags "$FILTER_TAGS")
fi
if [[ "$DRY_RUN" == "true" ]]; then
  cmd+=(--dry-run)
fi

echo "Running query mode=$MODE dry_run=$DRY_RUN"
"${cmd[@]}"
