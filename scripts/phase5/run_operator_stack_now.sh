#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

BRIDGE_URL="${RECALL_BRIDGE_URL:-http://localhost:8090}"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"

FULL_COMPOSE_FILES=(
  "$ROOT_DIR/docker/docker-compose.yml"
)

LITE_COMPOSE_FILES=(
  "$ROOT_DIR/docker/phase1b-ingest-bridge.compose.yml"
  "$ROOT_DIR/docker/docker-compose.lite.yml"
)

usage() {
  cat <<'HELP'
Usage:
  run_operator_stack_now.sh <command> [options]

Commands:
  up [--recreate] [--preflight] [--lite]   Bring up operator stack from compose files.
  down                            Stop and remove operator stack containers.
  restart [--preflight] [--lite]  Recreate operator stack containers.
  status                          Show operator stack service status.
  logs [service] [--lite]         Tail logs for all services or one service.
  preflight                       Run bridge/n8n preflight checks.
  config [--lite]                 Print effective compose services and config checks.
  help                            Show this help.

Options:
  --bridge-url <url>              Override bridge URL used by preflight.
  --n8n-host <url>                Override n8n host used by preflight.
  --lite                          Use Approach-B compose files for existing external services.

Examples:
  run_operator_stack_now.sh up
  run_operator_stack_now.sh up --lite
  run_operator_stack_now.sh up --recreate --preflight
  run_operator_stack_now.sh status
  run_operator_stack_now.sh logs recall-ingest-bridge
  run_operator_stack_now.sh preflight --bridge-url http://100.116.103.78:8090 --n8n-host http://100.116.103.78:5678
HELP
}

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required for operator stack commands." >&2
    exit 1
  fi
}

compose_cmd() {
  local selected_files=()
  if [[ "$COMPOSE_MODE" == "lite" ]]; then
    selected_files=("${LITE_COMPOSE_FILES[@]}")
  else
    selected_files=("${FULL_COMPOSE_FILES[@]}")
  fi

  local args=()
  for compose_file in "${selected_files[@]}"; do
    args+=(-f "$compose_file")
  done
  docker compose "${args[@]}" "$@"
}

run_preflight() {
  "$ROOT_DIR/scripts/phase3/run_service_preflight_now.sh" \
    --bridge-url "$BRIDGE_URL" \
    --n8n-host "$N8N_HOST"
}

COMMAND="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

RUN_PREFLIGHT="false"
FORCE_RECREATE="false"
LOG_SERVICE=""
COMPOSE_MODE="full"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bridge-url)
      BRIDGE_URL="${2:-}"
      shift 2
      ;;
    --n8n-host)
      N8N_HOST="${2:-}"
      shift 2
      ;;
    --preflight)
      RUN_PREFLIGHT="true"
      shift
      ;;
    --recreate)
      FORCE_RECREATE="true"
      shift
      ;;
    --help|-h)
      COMMAND="help"
      shift
      ;;
    --lite)
      COMPOSE_MODE="lite"
      shift
      ;;
    *)
      if [[ "$COMMAND" == "logs" && -z "$LOG_SERVICE" ]]; then
        LOG_SERVICE="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 2
      fi
      ;;
  esac
done

case "$COMMAND" in
  help)
    usage
    ;;
  up)
    require_docker
    cd "$ROOT_DIR"
    if [[ "$FORCE_RECREATE" == "true" ]]; then
      compose_cmd up -d --force-recreate
    else
      compose_cmd up -d
    fi
    if [[ "$RUN_PREFLIGHT" == "true" ]]; then
      run_preflight
    fi
    ;;
  down)
    require_docker
    cd "$ROOT_DIR"
    compose_cmd down
    ;;
  restart)
    require_docker
    cd "$ROOT_DIR"
    compose_cmd up -d --force-recreate
    if [[ "$RUN_PREFLIGHT" == "true" ]]; then
      run_preflight
    fi
    ;;
  status)
    require_docker
    cd "$ROOT_DIR"
    compose_cmd ps
    ;;
  logs)
    require_docker
    cd "$ROOT_DIR"
    if [[ -n "$LOG_SERVICE" ]]; then
      compose_cmd logs -f "$LOG_SERVICE"
    else
      compose_cmd logs -f
    fi
    ;;
  preflight)
    run_preflight
    ;;
  config)
    require_docker
    cd "$ROOT_DIR"
    local_files=("${FULL_COMPOSE_FILES[@]}")
    if [[ "$COMPOSE_MODE" == "lite" ]]; then
      local_files=("${LITE_COMPOSE_FILES[@]}")
    fi
    echo "Compose mode: $COMPOSE_MODE"
    echo "Compose files:"
    for compose_file in "${local_files[@]}"; do
      echo "  - $compose_file"
    done
    echo
    echo "Services:"
    compose_cmd config --services
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    usage >&2
    exit 2
    ;;
esac
