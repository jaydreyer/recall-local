#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f docker/.env ]]; then
  cp docker/.env.example docker/.env
  echo "Created docker/.env from template. Fill API keys before cloud provider tests."
fi

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

python scripts/phase0/bootstrap_sqlite.py
python scripts/phase0/bootstrap_qdrant.py
python scripts/phase0/connectivity_check.py || true

echo
echo "Phase 0 setup complete."
echo "Next: edit docker/.env, then run provider checks:"
echo "  RECALL_LLM_PROVIDER=ollama .venv/bin/python scripts/llm_client.py"
echo "  RECALL_LLM_PROVIDER=anthropic .venv/bin/python scripts/llm_client.py"
echo "  RECALL_LLM_PROVIDER=openai .venv/bin/python scripts/llm_client.py"
echo "  RECALL_LLM_PROVIDER=gemini .venv/bin/python scripts/llm_client.py"
