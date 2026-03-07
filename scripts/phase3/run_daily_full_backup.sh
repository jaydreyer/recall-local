#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUTPUT_ROOT="${RECALL_DAILY_BACKUP_OUTPUT_DIR:-$ROOT_DIR/data/artifacts/backups/daily_full}"
RETENTION_DAYS="${RECALL_DAILY_BACKUP_RETENTION_DAYS:-14}"
QDRANT_VOLUME_NAME="${QDRANT_VOLUME_NAME:-recall_qdrant-storage}"
OLLAMA_CONTAINER_NAME="${OLLAMA_CONTAINER_NAME:-ollama}"
BACKUP_NAME=""

usage() {
  cat <<'HELP'
Usage:
  run_daily_full_backup.sh [options]

Options:
  --output-dir <path>       Backup output root directory
  --backup-name <name>      Optional fixed backup folder name
  --retention-days <days>   Delete backup directories older than this many days
  --help                    Show this help

Examples:
  run_daily_full_backup.sh
  run_daily_full_backup.sh --backup-name manual_verify_20260306
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_ROOT="${2:-}"
      shift 2
      ;;
    --backup-name)
      BACKUP_NAME="${2:-}"
      shift 2
      ;;
    --retention-days)
      RETENTION_DAYS="${2:-}"
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

if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  echo "retention-days must be an integer: $RETENTION_DAYS" >&2
  exit 2
fi

mkdir -p "$OUTPUT_ROOT"
LOCK_DIR="$OUTPUT_ROOT/.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Backup lock already exists at $LOCK_DIR" >&2
  exit 1
fi
trap 'rmdir "$LOCK_DIR"' EXIT

STAMP="${BACKUP_NAME:-$(date -u +%Y%m%dT%H%M%SZ)}"
BACKUP_DIR="$OUTPUT_ROOT/$STAMP"
STATE_DIR="$BACKUP_DIR/state"
RUNTIME_DIR="$BACKUP_DIR/runtime"
CONFIG_DIR="$BACKUP_DIR/config"

mkdir -p "$STATE_DIR" "$RUNTIME_DIR" "$CONFIG_DIR"

echo "Running daily full backup to: $BACKUP_DIR"

echo "[1/7] Backing up SQLite + all Qdrant collections"
"$PYTHON_BIN" "$ROOT_DIR/scripts/phase3/backup_all_collections.py" \
  --output-dir "$BACKUP_DIR" \
  --backup-name state

echo "[2/7] Backing up n8n SQLite database"
"$PYTHON_BIN" - <<PY
from pathlib import Path
import sqlite3

source = Path(r"$ROOT_DIR/n8n/database.sqlite")
target = Path(r"$RUNTIME_DIR/n8n-database.sqlite")
if not source.exists():
    raise FileNotFoundError(f"n8n database not found: {source}")
source_conn = sqlite3.connect(str(source))
target_conn = sqlite3.connect(str(target))
try:
    source_conn.backup(target_conn)
finally:
    target_conn.close()
    source_conn.close()
PY

echo "[3/7] Archiving n8n runtime directory"
tar -czf "$RUNTIME_DIR/n8n-dir.tgz" \
  --exclude='n8n/database.sqlite' \
  --exclude='n8n/database.sqlite-shm' \
  --exclude='n8n/database.sqlite-wal' \
  -C "$ROOT_DIR" n8n

echo "[4/7] Archiving data directory (excluding nested backups)"
tar -czf "$RUNTIME_DIR/data.tgz" \
  --exclude='data/artifacts/backups' \
  --exclude='data/artifacts/backups/*' \
  -C "$ROOT_DIR" data

echo "[5/7] Archiving raw Qdrant volume"
docker run --rm \
  -v "$QDRANT_VOLUME_NAME":/source \
  -v "$RUNTIME_DIR":/backup \
  alpine sh -lc 'tar -czf /backup/qdrant-volume.tgz -C /source .'

echo "[6/7] Capturing deployment config and model inventory"
tar -czf "$CONFIG_DIR/compose-config.tgz" \
  -C "$ROOT_DIR" \
  docker/.env \
  docker/.env.example \
  docker/docker-compose.yml
git -C "$ROOT_DIR" rev-parse HEAD > "$CONFIG_DIR/git-head.txt"
git -C "$ROOT_DIR" status --short > "$CONFIG_DIR/git-status.txt"
if docker ps --format '{{.Names}}' | grep -x "$OLLAMA_CONTAINER_NAME" >/dev/null 2>&1; then
  docker exec "$OLLAMA_CONTAINER_NAME" ollama list > "$RUNTIME_DIR/ollama-models.txt" || true
fi

echo "[7/7] Writing manifest and pruning old backups"
CREATED_AT_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
"$PYTHON_BIN" - <<PY
from __future__ import annotations
import json
from pathlib import Path

backup_dir = Path(r"$BACKUP_DIR")
files = [
    "state/manifest.json",
    "state/sqlite/recall.db",
    "runtime/n8n-database.sqlite",
    "runtime/n8n-dir.tgz",
    "runtime/data.tgz",
    "runtime/qdrant-volume.tgz",
    "config/compose-config.tgz",
    "config/git-head.txt",
    "config/git-status.txt",
]
optional_files = [
    "runtime/ollama-models.txt",
]

manifest = {
    "backup_name": backup_dir.name,
    "created_at_utc": r"$CREATED_AT_UTC",
    "retention_days": int(r"$RETENTION_DAYS"),
    "artifacts": {},
}
for rel_path in files + optional_files:
    path = backup_dir / rel_path
    if path.exists():
        manifest["artifacts"][rel_path] = {"bytes": path.stat().st_size}

(backup_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

ln -sfn "$STAMP" "$OUTPUT_ROOT/latest"
find "$OUTPUT_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '.lock' -mtime +"$RETENTION_DAYS" -exec rm -rf {} +

echo "[OK] Daily full backup written: $BACKUP_DIR"
