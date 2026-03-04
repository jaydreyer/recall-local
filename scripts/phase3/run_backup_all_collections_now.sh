#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

OUTPUT_DIR="${RECALL_BACKUP_ALL_OUTPUT_DIR:-$ROOT_DIR/data/artifacts/backups/phase3c_all}"
BACKUP_NAME=""

usage() {
  cat <<'HELP'
Usage:
  run_backup_all_collections_now.sh [options]

Options:
  --output-dir <path>     Backup output root directory
  --backup-name <name>    Optional fixed backup folder name
  --help                  Show this help

Examples:
  run_backup_all_collections_now.sh
  run_backup_all_collections_now.sh --backup-name daily_all_collections
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --backup-name)
      BACKUP_NAME="${2:-}"
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

cmd=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/phase3/backup_all_collections.py"
  --output-dir "$OUTPUT_DIR"
)

if [[ -n "$BACKUP_NAME" ]]; then
  cmd+=(--backup-name "$BACKUP_NAME")
fi

echo "Running all-collections backup to: $OUTPUT_DIR"
"${cmd[@]}"
