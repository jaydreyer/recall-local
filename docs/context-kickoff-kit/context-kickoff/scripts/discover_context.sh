#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(pwd)}"
cd "$ROOT"

echo "[repo] $(pwd)"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[git] branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "[git] status=$(git status --short | wc -l | tr -d ' ') changed paths"
else
  echo "[git] not a git repository"
fi

echo "\n[canonical files]"
for f in \
  docs/ENVIRONMENT_INVENTORY.md \
  docs/IMPLEMENTATION_LOG.md \
  docs/README.md \
  AGENTS.md \
  README.md
do
  if [[ -f "$f" ]]; then
    echo "FOUND $f"
  else
    echo "MISS  $f"
  fi
done

echo "\n[phase/prd candidates]"
rg --files docs 2>/dev/null | rg -n '(PRD|Phase|phase|prd).*\.md$' || true

echo "\n[top headings preview]"
for f in docs/ENVIRONMENT_INVENTORY.md docs/IMPLEMENTATION_LOG.md docs/README.md README.md; do
  if [[ -f "$f" ]]; then
    echo "--- $f"
    rg -n '^# ' "$f" | head -n 5 || true
  fi
done
