#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${RECALL_ENV_FILE:-$ROOT_DIR/docker/.env}"
BRIDGE_BASE_URL="${RECALL_UPTIME_BRIDGE_BASE_URL:-http://localhost:8090}"
DASHBOARD_URL="${RECALL_UPTIME_DASHBOARD_URL:-http://localhost:3001}"
CHAT_UI_URL="${RECALL_UPTIME_CHAT_UI_URL:-http://localhost:8170}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

export RECALL_UPTIME_ALERT_TELEGRAM_BOT_TOKEN="${RECALL_UPTIME_ALERT_TELEGRAM_BOT_TOKEN:-${RECALL_TELEGRAM_BOT_TOKEN:-}}"
export RECALL_UPTIME_ALERT_TELEGRAM_CHAT_ID="${RECALL_UPTIME_ALERT_TELEGRAM_CHAT_ID:-${RECALL_TELEGRAM_CHAT_ID:-}}"
export RECALL_UPTIME_NOTIFY_ON_SUCCESS="${RECALL_UPTIME_NOTIFY_ON_SUCCESS:-false}"

exec "$ROOT_DIR/scripts/phase6/run_ops_observability_check.sh" \
  "$BRIDGE_BASE_URL" \
  "$DASHBOARD_URL" \
  "$CHAT_UI_URL"
