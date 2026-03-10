#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DOCKER_DIR="$ROOT_DIR/docker"
ENV_FILE="$DOCKER_DIR/.env"
COMPOSE_FILE="$DOCKER_DIR/docker-compose.yml"
VALIDATE_SCRIPT="$DOCKER_DIR/validate-stack.sh"
CASES_FILE="$ROOT_DIR/scripts/eval/rag_bakeoff_cases.json"
EVAL_SCRIPT="$ROOT_DIR/scripts/eval/run_eval.py"
ARTIFACT_DIR="$ROOT_DIR/data/artifacts/evals/bakeoff"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

DEFAULT_MODELS=(
  "qwen2.5:7b-instruct"
  "qwen3.5:9b"
  "gemma3:12b-it-qat"
)

mkdir -p "$ARTIFACT_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 2
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing compose file: $COMPOSE_FILE" >&2
  exit 2
fi

if [[ ! -f "$CASES_FILE" ]]; then
  echo "Missing bakeoff cases file: $CASES_FILE" >&2
  exit 2
fi

if [[ $# -gt 0 ]]; then
  MODELS=("$@")
else
  MODELS=("${DEFAULT_MODELS[@]}")
fi

ORIGINAL_MODEL="$(
  python3 - "$ENV_FILE" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line.startswith("OLLAMA_MODEL="):
        print(line.split("=", 1)[1].strip())
        break
PY
)"

if [[ -z "$ORIGINAL_MODEL" ]]; then
  echo "Could not determine original OLLAMA_MODEL from $ENV_FILE" >&2
  exit 2
fi

restore_original_model() {
  python3 - "$ENV_FILE" "$ORIGINAL_MODEL" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
model = sys.argv[2]
lines = env_path.read_text(encoding="utf-8").splitlines()
updated = []
replaced = False
for line in lines:
    if line.startswith("OLLAMA_MODEL="):
        updated.append(f"OLLAMA_MODEL={model}")
        replaced = True
    else:
        updated.append(line)
if not replaced:
    updated.append(f"OLLAMA_MODEL={model}")
env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
  (
    cd "$DOCKER_DIR"
    docker compose -p recall --env-file .env -f docker-compose.yml up -d --no-deps --force-recreate recall-ingest-bridge >/dev/null
    ./validate-stack.sh >/dev/null
  )
}

trap restore_original_model EXIT

for model in "${MODELS[@]}"; do
  safe_model="${model//[:\/]/_}"
  result_json="$ARTIFACT_DIR/${TIMESTAMP}_${safe_model}.json"

  echo "==> Pulling model if needed: $model"
  docker exec -i ollama ollama pull "$model" >/dev/null

  echo "==> Switching bridge model to: $model"
  python3 - "$ENV_FILE" "$model" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
model = sys.argv[2]
lines = env_path.read_text(encoding="utf-8").splitlines()
updated = []
replaced = False
for line in lines:
    if line.startswith("OLLAMA_MODEL="):
        updated.append(f"OLLAMA_MODEL={model}")
        replaced = True
    else:
        updated.append(line)
if not replaced:
    updated.append(f"OLLAMA_MODEL={model}")
env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY

  (
    cd "$DOCKER_DIR"
    docker compose -p recall --env-file .env -f docker-compose.yml up -d --no-deps --force-recreate recall-ingest-bridge >/dev/null
    ./validate-stack.sh >/dev/null
  )

  echo "==> Running eval for: $model"
  set +e
  python3 "$EVAL_SCRIPT" \
    --backend webhook \
    --webhook-url "http://localhost:8090/v1/rag-queries" \
    --cases-file "$CASES_FILE" \
    --top-k 8 \
    --max-retries 2 \
    --retrieval-mode hybrid \
    --enable-reranker true \
    --reranker-weight 0.65 \
    > "$result_json"
  eval_exit=$?
  set -e

  python3 - "$result_json" "$model" "$eval_exit" <<'PY'
import json
import sys
from pathlib import Path

result_path = Path(sys.argv[1])
model = sys.argv[2]
eval_exit = int(sys.argv[3])
payload = json.loads(result_path.read_text(encoding="utf-8"))
print(
    f"model={model} status={payload['status']} passed={payload['passed']}/{payload['total']} latency_ms={payload['latency_ms']} eval_exit={eval_exit} artifact={payload.get('artifact_path')}"
)
PY
done

python3 - "$ARTIFACT_DIR" "$TIMESTAMP" "${MODELS[@]}" <<'PY'
import json
import sys
from pathlib import Path

artifact_dir = Path(sys.argv[1])
timestamp = sys.argv[2]
models = sys.argv[3:]
lines = [
    "# RAG Model Bakeoff",
    "",
    f"- Timestamp: `{timestamp}`",
    "",
    "| Model | Status | Passed | Total | Latency (ms) |",
    "|---|---|---:|---:|---:|",
]

for model in models:
    safe_model = model.replace(":", "_").replace("/", "_")
    payload = json.loads((artifact_dir / f"{timestamp}_{safe_model}.json").read_text(encoding="utf-8"))
    lines.append(
        f"| `{model}` | `{payload['status']}` | `{payload['passed']}` | `{payload['total']}` | `{payload['latency_ms']}` |"
    )

summary_path = artifact_dir / f"{timestamp}_summary.md"
summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"summary={summary_path}")
PY
