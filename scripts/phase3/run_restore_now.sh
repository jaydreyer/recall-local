#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

BACKUP_ROOT="${RECALL_BACKUP_OUTPUT_DIR:-$ROOT_DIR/data/artifacts/backups/phase3c}"
BACKUP_DIR=""
REPLACE_COLLECTION="false"
SKIP_SQLITE="false"
SKIP_QDRANT="false"

usage() {
  cat <<'HELP'
Usage:
  run_restore_now.sh [options]

Options:
  --backup-dir <path>      Explicit backup directory (defaults to latest in backup root)
  --backup-root <path>     Root directory containing backup folders
  --replace-collection     Delete/recreate Qdrant collection before restore
  --skip-sqlite            Skip SQLite restore
  --skip-qdrant            Skip Qdrant restore
  --help                   Show this help

Examples:
  run_restore_now.sh
  run_restore_now.sh --backup-dir /home/jaydreyer/recall-local/data/artifacts/backups/phase3c/20260224T030000Z --replace-collection
HELP
}

resolve_latest_backup() {
  local root="$1"
  local latest
  latest="$(ls -1dt "$root"/* 2>/dev/null | head -n 1 || true)"
  if [[ -z "$latest" ]]; then
    return 1
  fi
  printf '%s' "$latest"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backup-dir)
      BACKUP_DIR="${2:-}"
      shift 2
      ;;
    --backup-root)
      BACKUP_ROOT="${2:-}"
      shift 2
      ;;
    --replace-collection)
      REPLACE_COLLECTION="true"
      shift
      ;;
    --skip-sqlite)
      SKIP_SQLITE="true"
      shift
      ;;
    --skip-qdrant)
      SKIP_QDRANT="true"
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

if [[ -z "$BACKUP_DIR" ]]; then
  if ! BACKUP_DIR="$(resolve_latest_backup "$BACKUP_ROOT")"; then
    echo "No backups found under: $BACKUP_ROOT" >&2
    exit 1
  fi
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "Backup directory not found: $BACKUP_DIR" >&2
  exit 1
fi

cmd=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/phase3/backup_restore_state.py"
  restore
  --backup-dir "$BACKUP_DIR"
)

if [[ "$REPLACE_COLLECTION" == "true" ]]; then
  cmd+=(--replace-collection)
fi
if [[ "$SKIP_SQLITE" == "true" ]]; then
  cmd+=(--skip-sqlite)
fi
if [[ "$SKIP_QDRANT" == "true" ]]; then
  cmd+=(--skip-qdrant)
fi

echo "Running Phase 3C restore from: $BACKUP_DIR"
"${cmd[@]}"
