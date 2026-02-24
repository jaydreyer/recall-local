#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

OUTPUT_ROOT="${RECALL_PORTFOLIO_BUNDLE_OUTPUT_ROOT:-$ROOT_DIR/data/artifacts/portfolio/phase3c}"
MAX_TREND_RUNS="${RECALL_PORTFOLIO_MAX_TREND_RUNS:-12}"

usage() {
  cat <<'HELP'
Usage:
  build_portfolio_bundle_now.sh [options]

Options:
  --output-root <path>     Output root for generated bundle directories
  --max-trend-runs <int>   Max eval runs included in trend snapshot table
  --help                   Show this help

Examples:
  build_portfolio_bundle_now.sh
  build_portfolio_bundle_now.sh --max-trend-runs 20
HELP
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-root)
      OUTPUT_ROOT="${2:-}"
      shift 2
      ;;
    --max-trend-runs)
      MAX_TREND_RUNS="${2:-}"
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

echo "Building Phase 3C portfolio bundle"
"$PYTHON_BIN" "$ROOT_DIR/scripts/phase3/build_portfolio_bundle.py" \
  --output-root "$OUTPUT_ROOT" \
  --max-trend-runs "$MAX_TREND_RUNS"
