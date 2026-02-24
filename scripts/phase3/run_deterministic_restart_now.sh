#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

QDRANT_HOST="${QDRANT_HOST:-http://localhost:6333}"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"
BRIDGE_URL="${RECALL_BRIDGE_URL:-http://localhost:8090}"

WAIT_TIMEOUT_SECONDS="${RECALL_RESTART_WAIT_TIMEOUT_SECONDS:-120}"
RUN_POST_PREFLIGHT="true"

# Deterministic boot order: vector store -> model runtime -> bridge -> orchestration -> UX surfaces.
DEFAULT_ORDER=(
  qdrant
  ollama
  recall-ingest-bridge
  n8n
  open-webui
  recall-mkdocs
)

usage() {
  cat <<'HELP'
Usage:
  run_deterministic_restart_now.sh [options]

Options:
  --wait-timeout-seconds <int>  Max wait for each health check (default: 120)
  --skip-post-preflight         Skip run_service_preflight_now.sh after restart
  --help                        Show this help

Examples:
  run_deterministic_restart_now.sh
  run_deterministic_restart_now.sh --wait-timeout-seconds 180
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wait-timeout-seconds)
      WAIT_TIMEOUT_SECONDS="${2:-}"
      shift 2
      ;;
    --skip-post-preflight)
      RUN_POST_PREFLIGHT="false"
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

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for deterministic restart." >&2
  exit 1
fi

container_exists() {
  local name="$1"
  docker container inspect "$name" >/dev/null 2>&1
}

wait_for_http() {
  local label="$1"
  local url="$2"
  local timeout="$3"
  local start
  start="$(date +%s)"

  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "[PASS] $label healthy: $url"
      return 0
    fi

    if (( $(date +%s) - start >= timeout )); then
      echo "[FAIL] Timed out waiting for $label health: $url" >&2
      return 1
    fi

    sleep 2
  done
}

for container in "${DEFAULT_ORDER[@]}"; do
  if container_exists "$container"; then
    echo "Restarting container: $container"
    docker restart "$container" >/dev/null
  else
    echo "[WARN] Container not found, skipping: $container"
  fi
done

echo
echo "Waiting for core service health"
wait_for_http "Qdrant" "$QDRANT_HOST/healthz" "$WAIT_TIMEOUT_SECONDS"
wait_for_http "Ollama" "$OLLAMA_HOST/api/tags" "$WAIT_TIMEOUT_SECONDS"
wait_for_http "Ingest bridge" "$BRIDGE_URL/healthz" "$WAIT_TIMEOUT_SECONDS"
wait_for_http "n8n" "${N8N_HOST%/}/healthz" "$WAIT_TIMEOUT_SECONDS"

if [[ "$RUN_POST_PREFLIGHT" == "true" ]]; then
  echo
  "$ROOT_DIR/scripts/phase3/run_service_preflight_now.sh" \
    --bridge-url "$BRIDGE_URL" \
    --n8n-host "$N8N_HOST"
fi

echo
echo "Deterministic restart completed."
