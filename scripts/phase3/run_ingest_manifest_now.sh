#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

PROFILE="${RECALL_MANIFEST_PROFILE:-job-search}"
MANIFEST_FILE="${RECALL_MANIFEST_FILE:-}"
ENSURE_TAG="${RECALL_MANIFEST_ENSURE_TAG:-}"
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage:
  run_ingest_manifest_now.sh [options]

Options:
  --profile <job-search|learning>  Manifest lane/profile (default: job-search)
  --manifest-file <path>           Explicit manifest path (overrides profile defaults)
  --ensure-tag <tag>               Enforce this tag on every item
  --dry-run                        Skip DB/Qdrant writes
  --help                           Show this help

Examples:
  run_ingest_manifest_now.sh
  run_ingest_manifest_now.sh --profile learning --dry-run
  run_ingest_manifest_now.sh --manifest-file /path/to/manifest.json --ensure-tag job-search
EOF
}

normalize_profile() {
  local value
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$value" in
    job-search|job_search|jobsearch)
      printf '%s' "job-search"
      ;;
    learning|learn)
      printf '%s' "learning"
      ;;
    *)
      echo "Unsupported profile: $1" >&2
      exit 2
      ;;
  esac
}

resolve_manifest_file() {
  local profile="$1"
  local env_override=""
  local candidates=()

  if [[ "$profile" == "job-search" ]]; then
    env_override="${RECALL_JOB_SEARCH_MANIFEST_FILE:-}"
    candidates+=(
      "$ROOT_DIR/scripts/phase2/job_search_manifest.jaydreyer.ai-lab.json"
      "$ROOT_DIR/scripts/phase2/job_search_manifest.example.json"
    )
  else
    env_override="${RECALL_LEARNING_MANIFEST_FILE:-}"
    candidates+=(
      "$ROOT_DIR/scripts/phase2/learning_manifest.genieincodebottle.ai-lab.json"
    )
  fi

  if [[ -n "$env_override" ]]; then
    candidates=("$env_override" "${candidates[@]}")
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done

  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="${2:-}"
      shift 2
      ;;
    --manifest-file)
      MANIFEST_FILE="${2:-}"
      shift 2
      ;;
    --ensure-tag)
      ENSURE_TAG="${2:-}"
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

PROFILE="$(normalize_profile "$PROFILE")"

if [[ -z "$MANIFEST_FILE" ]]; then
  if ! MANIFEST_FILE="$(resolve_manifest_file "$PROFILE")"; then
    echo "Could not resolve a manifest file for profile '$PROFILE'." >&2
    echo "Set --manifest-file or define RECALL_JOB_SEARCH_MANIFEST_FILE / RECALL_LEARNING_MANIFEST_FILE." >&2
    exit 2
  fi
fi

if [[ ! -f "$MANIFEST_FILE" ]]; then
  echo "Manifest file not found: $MANIFEST_FILE" >&2
  exit 2
fi

if [[ -z "$ENSURE_TAG" && "$PROFILE" == "job-search" ]]; then
  ENSURE_TAG="job-search"
fi

cmd=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/phase2/ingest_job_search_manifest.py"
  --manifest-file "$MANIFEST_FILE"
)

if [[ "$DRY_RUN" == "true" ]]; then
  cmd+=(--dry-run)
fi
if [[ -n "$ENSURE_TAG" ]]; then
  cmd+=(--ensure-tag "$ENSURE_TAG")
fi

echo "Running manifest ingest profile=$PROFILE manifest=$MANIFEST_FILE dry_run=$DRY_RUN"
"${cmd[@]}"
