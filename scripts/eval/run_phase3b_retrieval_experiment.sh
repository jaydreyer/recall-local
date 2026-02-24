#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
N8N_HOST="${N8N_HOST:-http://localhost:5678}"
N8N_BASE_URL="${N8N_HOST%/}"
WEBHOOK_URL="${RECALL_EVAL_WEBHOOK_URL:-$N8N_BASE_URL/webhook/recall-query}"
CASES_FILE="${RECALL_PHASE3B_CASES_FILE:-$ROOT_DIR/scripts/eval/golden_sets/learning_golden_v1.json}"
TOP_K="${RECALL_PHASE3B_TOP_K:-5}"
MIN_SCORE="${RECALL_PHASE3B_MIN_SCORE:-0.15}"
MAX_RETRIES="${RECALL_PHASE3B_MAX_RETRIES:-1}"

CANDIDATE_RETRIEVAL_MODE="${RECALL_PHASE3B_CANDIDATE_RETRIEVAL_MODE:-hybrid}"
CANDIDATE_HYBRID_ALPHA="${RECALL_PHASE3B_CANDIDATE_HYBRID_ALPHA:-0.65}"
CANDIDATE_ENABLE_RERANKER="${RECALL_PHASE3B_CANDIDATE_ENABLE_RERANKER:-true}"
CANDIDATE_RERANKER_WEIGHT="${RECALL_PHASE3B_CANDIDATE_RERANKER_WEIGHT:-0.35}"

SEMANTIC_SCORE="${RECALL_PHASE3B_SEMANTIC_SCORE:-false}"
SEMANTIC_MIN_SCORE="${RECALL_PHASE3B_SEMANTIC_MIN_SCORE:-0.65}"

OUTPUT_DIR="${RECALL_PHASE3B_OUTPUT_DIR:-$ROOT_DIR/data/artifacts/evals/phase3b}"

usage() {
  cat <<'EOF'
Usage:
  run_phase3b_retrieval_experiment.sh

Environment overrides:
  N8N_HOST
  RECALL_EVAL_WEBHOOK_URL
  RECALL_PHASE3B_CASES_FILE
  RECALL_PHASE3B_TOP_K
  RECALL_PHASE3B_MIN_SCORE
  RECALL_PHASE3B_MAX_RETRIES
  RECALL_PHASE3B_CANDIDATE_RETRIEVAL_MODE
  RECALL_PHASE3B_CANDIDATE_HYBRID_ALPHA
  RECALL_PHASE3B_CANDIDATE_ENABLE_RERANKER
  RECALL_PHASE3B_CANDIDATE_RERANKER_WEIGHT
  RECALL_PHASE3B_SEMANTIC_SCORE
  RECALL_PHASE3B_SEMANTIC_MIN_SCORE
  RECALL_PHASE3B_OUTPUT_DIR
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

mkdir -p "$OUTPUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASELINE_JSON="$OUTPUT_DIR/${STAMP}_baseline_vector.json"
CANDIDATE_JSON="$OUTPUT_DIR/${STAMP}_candidate_hybrid.json"
SUMMARY_MD="$OUTPUT_DIR/${STAMP}_comparison.md"

baseline_cmd=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/eval/run_eval.py"
  --cases-file "$CASES_FILE"
  --backend webhook
  --webhook-url "$WEBHOOK_URL"
  --top-k "$TOP_K"
  --min-score "$MIN_SCORE"
  --max-retries "$MAX_RETRIES"
)

candidate_cmd=(
  "$PYTHON_BIN"
  "$ROOT_DIR/scripts/eval/run_eval.py"
  --cases-file "$CASES_FILE"
  --backend webhook
  --webhook-url "$WEBHOOK_URL"
  --top-k "$TOP_K"
  --min-score "$MIN_SCORE"
  --max-retries "$MAX_RETRIES"
  --retrieval-mode "$CANDIDATE_RETRIEVAL_MODE"
  --hybrid-alpha "$CANDIDATE_HYBRID_ALPHA"
  --enable-reranker "$CANDIDATE_ENABLE_RERANKER"
  --reranker-weight "$CANDIDATE_RERANKER_WEIGHT"
)

semantic_flag="$(printf '%s' "$SEMANTIC_SCORE" | tr '[:upper:]' '[:lower:]')"
if [[ "$semantic_flag" == "true" ]]; then
  baseline_cmd+=(--semantic-score --semantic-min-score "$SEMANTIC_MIN_SCORE")
  candidate_cmd+=(--semantic-score --semantic-min-score "$SEMANTIC_MIN_SCORE")
fi

set +e
"${baseline_cmd[@]}" >"$BASELINE_JSON"
BASELINE_EXIT=$?
"${candidate_cmd[@]}" >"$CANDIDATE_JSON"
CANDIDATE_EXIT=$?
set -e

"$PYTHON_BIN" - <<'PY' "$BASELINE_JSON" "$CANDIDATE_JSON" "$SUMMARY_MD" "$CASES_FILE" "$WEBHOOK_URL" "$BASELINE_EXIT" "$CANDIDATE_EXIT" "$CANDIDATE_RETRIEVAL_MODE" "$CANDIDATE_HYBRID_ALPHA" "$CANDIDATE_ENABLE_RERANKER" "$CANDIDATE_RERANKER_WEIGHT"
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

baseline_path = Path(sys.argv[1])
candidate_path = Path(sys.argv[2])
summary_path = Path(sys.argv[3])
cases_file = sys.argv[4]
webhook_url = sys.argv[5]
baseline_exit = int(sys.argv[6])
candidate_exit = int(sys.argv[7])
candidate_mode = sys.argv[8]
candidate_alpha = sys.argv[9]
candidate_reranker = sys.argv[10]
candidate_weight = sys.argv[11]

baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))

def avg_latency(payload: dict) -> float:
    values = [int(row.get("latency_ms", 0)) for row in payload.get("results", [])]
    return statistics.mean(values) if values else 0.0

def semantic_avg(payload: dict):
    values = []
    for row in payload.get("results", []):
        value = row.get("semantic_similarity")
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return statistics.mean(values)

baseline_pass = int(baseline.get("passed", 0))
baseline_total = int(baseline.get("total", 0))
candidate_pass = int(candidate.get("passed", 0))
candidate_total = int(candidate.get("total", 0))

baseline_latency = avg_latency(baseline)
candidate_latency = avg_latency(candidate)

baseline_semantic = semantic_avg(baseline)
candidate_semantic = semantic_avg(candidate)

lines = [
    "# Phase 3B Retrieval Experiment Summary",
    "",
    f"- Generated: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`",
    f"- Cases file: `{cases_file}`",
    f"- Webhook URL: `{webhook_url}`",
    "",
    "## Config",
    "",
    "- Baseline: `retrieval_mode=vector`",
    (
        "- Candidate: "
        f"`retrieval_mode={candidate_mode}`, "
        f"`hybrid_alpha={candidate_alpha}`, "
        f"`enable_reranker={candidate_reranker}`, "
        f"`reranker_weight={candidate_weight}`"
    ),
    "",
    "## Results",
    "",
    f"- Baseline exit/status: `{baseline_exit}` / `{baseline.get('status')}`",
    f"- Candidate exit/status: `{candidate_exit}` / `{candidate.get('status')}`",
    f"- Baseline pass rate: `{baseline_pass}/{baseline_total}`",
    f"- Candidate pass rate: `{candidate_pass}/{candidate_total}`",
    f"- Pass-rate delta: `{candidate_pass - baseline_pass}`",
    f"- Baseline avg per-case latency: `{baseline_latency:.1f} ms`",
    f"- Candidate avg per-case latency: `{candidate_latency:.1f} ms`",
    f"- Latency delta: `{candidate_latency - baseline_latency:+.1f} ms`",
    "",
]

if baseline_semantic is not None or candidate_semantic is not None:
    lines.extend(
        [
            "## Semantic Lane (optional)",
            "",
            f"- Baseline avg semantic similarity: `{baseline_semantic:.3f}`" if baseline_semantic is not None else "- Baseline avg semantic similarity: `n/a`",
            f"- Candidate avg semantic similarity: `{candidate_semantic:.3f}`" if candidate_semantic is not None else "- Candidate avg semantic similarity: `n/a`",
            (
                f"- Semantic delta: `{candidate_semantic - baseline_semantic:+.3f}`"
                if baseline_semantic is not None and candidate_semantic is not None
                else "- Semantic delta: `n/a`"
            ),
            "",
        ]
    )

lines.extend(
    [
        "## Artifacts",
        "",
        f"- Baseline JSON: `{baseline_path}`",
        f"- Candidate JSON: `{candidate_path}`",
        f"- Baseline markdown artifact: `{baseline.get('artifact_path')}`",
        f"- Candidate markdown artifact: `{candidate.get('artifact_path')}`",
        "",
    ]
)

summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

echo "Phase 3B retrieval experiment complete:"
echo "  baseline_json: $BASELINE_JSON"
echo "  candidate_json: $CANDIDATE_JSON"
echo "  summary_md: $SUMMARY_MD"

if [[ "$BASELINE_EXIT" -ne 0 || "$CANDIDATE_EXIT" -ne 0 ]]; then
  if [[ "$BASELINE_EXIT" -ne 0 ]]; then
    exit "$BASELINE_EXIT"
  fi
  exit "$CANDIDATE_EXIT"
fi
