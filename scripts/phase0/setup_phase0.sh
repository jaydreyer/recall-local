#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f docker/.env ]]; then
  cp docker/.env.example docker/.env
  echo "Created docker/.env from template. Fill API keys before cloud provider tests."
fi

PYTHON_EXEC=""

if python3 -m venv .venv >/dev/null 2>&1; then
  source .venv/bin/activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  PYTHON_EXEC="python"
else
  echo "python3-venv unavailable; using user-site Python packages fallback."
  curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
  python3 /tmp/get-pip.py --user --break-system-packages
  ~/.local/bin/pip install --user --break-system-packages -r requirements.txt
  PYTHON_EXEC="python3"
fi

"$PYTHON_EXEC" scripts/phase0/bootstrap_sqlite.py
"$PYTHON_EXEC" scripts/phase0/bootstrap_qdrant.py
"$PYTHON_EXEC" scripts/phase0/connectivity_check.py || true

echo
echo "Phase 0 setup complete."
echo "Next: edit docker/.env, then run provider checks:"
if [[ "$PYTHON_EXEC" == "python" ]]; then
  RUNNER=".venv/bin/python"
else
  RUNNER="python3"
fi
echo "  RECALL_LLM_PROVIDER=ollama $RUNNER scripts/llm_client.py"
echo "  RECALL_LLM_PROVIDER=anthropic $RUNNER scripts/llm_client.py"
echo "  RECALL_LLM_PROVIDER=openai $RUNNER scripts/llm_client.py"
echo "  RECALL_LLM_PROVIDER=gemini $RUNNER scripts/llm_client.py"
