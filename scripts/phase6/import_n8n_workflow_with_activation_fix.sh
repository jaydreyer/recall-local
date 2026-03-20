#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOCKER_DIR="$ROOT_DIR/docker"
N8N_DIR="$ROOT_DIR/n8n"
DB_PATH="$N8N_DIR/database.sqlite"
BACKUP_DIR="$ROOT_DIR/data/artifacts/backups/n8n_imports"

usage() {
  cat <<'EOF'
Usage:
  scripts/phase6/import_n8n_workflow_with_activation_fix.sh <workflow-json-path> [--workflow-id <id>] [--no-restart] [--skip-publish]

Purpose:
  Import an n8n workflow artifact from the repo-mounted n8n directory, repair the
  active workflow row in the host SQLite database for n8n builds that leave
  activeVersionId unset, and optionally restart + validate the stack.

Examples:
  scripts/phase6/import_n8n_workflow_with_activation_fix.sh \
    n8n/workflows/phase6_follow_up_reminders_import.workflow.json

  scripts/phase6/import_n8n_workflow_with_activation_fix.sh \
    n8n/workflows/phase6c_evaluate_notify_import.workflow.json \
    --workflow-id 9DEQqfD8JA5PCiVP
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

WORKFLOW_PATH=""
WORKFLOW_ID=""
RESTART_N8N=1
SKIP_PUBLISH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workflow-id)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --workflow-id" >&2
        exit 1
      fi
      WORKFLOW_ID="$2"
      shift 2
      ;;
    --no-restart)
      RESTART_N8N=0
      shift
      ;;
    --skip-publish)
      SKIP_PUBLISH=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -n "$WORKFLOW_PATH" ]]; then
        echo "Unexpected argument: $1" >&2
        usage
        exit 1
      fi
      WORKFLOW_PATH="$1"
      shift
      ;;
  esac
done

if [[ -z "$WORKFLOW_PATH" ]]; then
  echo "Workflow JSON path is required." >&2
  usage
  exit 1
fi

if [[ "$WORKFLOW_PATH" != /* ]]; then
  WORKFLOW_PATH="$ROOT_DIR/$WORKFLOW_PATH"
fi

if [[ ! -f "$WORKFLOW_PATH" ]]; then
  echo "Workflow file not found: $WORKFLOW_PATH" >&2
  exit 1
fi

case "$WORKFLOW_PATH" in
  "$N8N_DIR"/*) ;;
  *)
    echo "Workflow file must live under $N8N_DIR so the n8n container can read it." >&2
    exit 1
    ;;
esac

CONTAINER_INPUT="/home/node/.n8n/${WORKFLOW_PATH#$N8N_DIR/}"

if [[ -z "$WORKFLOW_ID" ]]; then
  WORKFLOW_ID="$(python3 - "$WORKFLOW_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text())
print(str(payload.get("id") or "").strip())
PY
)"
fi

if [[ -z "$WORKFLOW_ID" ]]; then
  echo "Could not determine workflow id from $WORKFLOW_PATH. Pass --workflow-id explicitly." >&2
  exit 1
fi

if [[ ! -d "$DOCKER_DIR" ]]; then
  echo "Docker directory not found: $DOCKER_DIR" >&2
  exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
  echo "n8n database not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
BACKUP_PATH="$BACKUP_DIR/n8n_pre_import_$(date -u +%Y%m%dT%H%M%SZ).tgz"

echo "Creating n8n backup: $BACKUP_PATH"
tar -czf "$BACKUP_PATH" -C "$ROOT_DIR" n8n

if [[ $RESTART_N8N -eq 1 ]]; then
  echo "Running pre-restart stack validation"
  (cd "$DOCKER_DIR" && ./validate-stack.sh)
fi

echo "Importing workflow from $CONTAINER_INPUT"
docker exec n8n n8n import:workflow --input="$CONTAINER_INPUT"

if [[ $SKIP_PUBLISH -eq 0 ]]; then
  echo "Publishing workflow $WORKFLOW_ID"
  docker exec n8n n8n publish:workflow --id="$WORKFLOW_ID"
else
  echo "Skipping n8n publish:workflow step"
fi

echo "Repairing activation state in $DB_PATH"
python3 - "$DB_PATH" "$WORKFLOW_ID" <<'PY'
import sqlite3
import sys

db_path, workflow_id = sys.argv[1], sys.argv[2]
conn = sqlite3.connect(db_path)
try:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE workflow_entity
        SET active = 1,
            activeVersionId = versionId
        WHERE id = ?
        """,
        (workflow_id,),
    )
    if cur.rowcount != 1:
        raise SystemExit(f"Expected to update exactly one workflow row for id={workflow_id}, updated {cur.rowcount}.")
    conn.commit()
    row = cur.execute(
        "SELECT id, active, versionId, activeVersionId, name FROM workflow_entity WHERE id = ?",
        (workflow_id,),
    ).fetchone()
finally:
    conn.close()

if not row:
    raise SystemExit(f"Workflow row not found after repair for id={workflow_id}.")

row_id, active, version_id, active_version_id, name = row
if int(active or 0) != 1 or not version_id or active_version_id != version_id:
    raise SystemExit(
        "Activation repair verification failed "
        f"(id={row_id}, active={active}, versionId={version_id}, activeVersionId={active_version_id})."
    )

print(
    "Activation repair verified:",
    f"id={row_id}",
    f"name={name}",
    f"versionId={version_id}",
    f"activeVersionId={active_version_id}",
)
PY

if [[ $RESTART_N8N -eq 1 ]]; then
  echo "Restarting n8n"
  docker restart n8n >/dev/null
  echo "Running post-restart stack validation"
  (cd "$DOCKER_DIR" && ./validate-stack.sh)
fi

echo "Done. Workflow $WORKFLOW_ID imported and activation state repaired."
