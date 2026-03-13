#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

REMOTE_HOST="${AI_LAB_HOST:-ai-lab}"
REMOTE_USER="${AI_LAB_USER:-jaydreyer}"
REMOTE_REPO_PATH="${AI_LAB_REPO_PATH:-/home/jaydreyer/recall-local}"
REMOTE_SSH_KEY="${AI_LAB_SSH_KEY:-}"
SKIP_REMOTE="false"
FAIL_ON_FINDINGS="true"
OUTPUT_JSON=""

usage() {
  cat <<'EOF'
Usage:
  run_repo_hygiene_check.sh [options]

Options:
  --remote-host <host>       ai-lab host/address (default: ai-lab)
  --remote-user <user>       ai-lab SSH user (default: jaydreyer)
  --remote-repo-path <path>  ai-lab runtime repo path (default: /home/jaydreyer/recall-local)
  --ssh-key <path>           Optional SSH private key path for ai-lab checks
  --skip-remote              Skip ai-lab checks and run local metadata checks only
  --no-fail                  Always exit 0 (report findings without failing)
  --output-json <path>       Write machine-readable report JSON
  --help                     Show this help

Examples:
  run_repo_hygiene_check.sh
  run_repo_hygiene_check.sh --skip-remote
  run_repo_hygiene_check.sh --ssh-key ~/.ssh/codex_ai_lab
  run_repo_hygiene_check.sh --remote-host ai-lab --remote-user jaydreyer
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remote-host)
      REMOTE_HOST="${2:-}"
      shift 2
      ;;
    --remote-user)
      REMOTE_USER="${2:-}"
      shift 2
      ;;
    --remote-repo-path)
      REMOTE_REPO_PATH="${2:-}"
      shift 2
      ;;
    --ssh-key)
      REMOTE_SSH_KEY="${2:-}"
      shift 2
      ;;
    --skip-remote)
      SKIP_REMOTE="true"
      shift 1
      ;;
    --no-fail)
      FAIL_ON_FINDINGS="false"
      shift 1
      ;;
    --output-json)
      OUTPUT_JSON="${2:-}"
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

if [[ -z "$OUTPUT_JSON" ]]; then
  STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
  OUTPUT_JSON="$ROOT_DIR/data/artifacts/phase4/hygiene/${STAMP}_repo_hygiene.json"
fi

mkdir -p "$(dirname "$OUTPUT_JSON")"

local_dot_count="$(find "$ROOT_DIR" -type f -name '._*' -not -path "$ROOT_DIR/.git/*" | wc -l | tr -d ' ')"

remote_checked="false"
remote_error=""
remote_dirty_count="0"
remote_stash_count="0"
remote_dot_count="0"

if [[ "$SKIP_REMOTE" != "true" ]]; then
  remote_checked="true"
  SSH_CMD=(ssh -o BatchMode=yes -o ConnectTimeout=10)
  if [[ -n "$REMOTE_SSH_KEY" ]]; then
    SSH_CMD+=(-i "$REMOTE_SSH_KEY")
  fi
  remote_result="$(
    "${SSH_CMD[@]}" "$REMOTE_USER@$REMOTE_HOST" "bash -s -- '$REMOTE_REPO_PATH'" <<'EOF'
set -euo pipefail
repo_path="$1"
if [[ ! -d "$repo_path/.git" ]]; then
  echo "REMOTE_ERROR=repo_not_found:$repo_path"
  exit 0
fi

dirty_count="$(git -C "$repo_path" status --porcelain | wc -l | tr -d ' ')"
stash_count="$(git -C "$repo_path" stash list | wc -l | tr -d ' ')"
dot_count="$(find "$repo_path" -type f -name '._*' -not -path "$repo_path/.git/*" | wc -l | tr -d ' ')"
echo "REMOTE_ERROR="
echo "REMOTE_DIRTY_COUNT=$dirty_count"
echo "REMOTE_STASH_COUNT=$stash_count"
echo "REMOTE_DOT_COUNT=$dot_count"
EOF
  )" || remote_error="ssh_failed"

  if [[ -z "$remote_error" ]]; then
    while IFS='=' read -r key value; do
      case "$key" in
        REMOTE_ERROR)
          remote_error="$value"
          ;;
        REMOTE_DIRTY_COUNT)
          remote_dirty_count="$value"
          ;;
        REMOTE_STASH_COUNT)
          remote_stash_count="$value"
          ;;
        REMOTE_DOT_COUNT)
          remote_dot_count="$value"
          ;;
      esac
    done <<<"$remote_result"
  fi
fi

issue_count=0
finding_lines=()

if [[ "$local_dot_count" != "0" ]]; then
  issue_count=$((issue_count + 1))
  finding_lines+=("local_dot_underscore_files=$local_dot_count")
fi

if [[ "$remote_checked" == "true" ]]; then
  if [[ -n "$remote_error" ]]; then
    issue_count=$((issue_count + 1))
    finding_lines+=("remote_check_error=$remote_error")
  else
    if [[ "$remote_dirty_count" != "0" ]]; then
      issue_count=$((issue_count + 1))
      finding_lines+=("remote_dirty_repo_files=$remote_dirty_count")
    fi
    if [[ "$remote_stash_count" != "0" ]]; then
      issue_count=$((issue_count + 1))
      finding_lines+=("remote_stashes_present=$remote_stash_count")
    fi
    if [[ "$remote_dot_count" != "0" ]]; then
      issue_count=$((issue_count + 1))
      finding_lines+=("remote_dot_underscore_files=$remote_dot_count")
    fi
  fi
fi

status="pass"
if [[ "$issue_count" -gt 0 ]]; then
  status="fail"
fi

{
  echo "{"
  echo "  \"generated_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"status\": \"$status\","
  echo "  \"root_dir\": \"$ROOT_DIR\","
  echo "  \"local\": {"
  echo "    \"dot_underscore_count\": $local_dot_count"
  echo "  },"
  echo "  \"remote\": {"
  echo "    \"checked\": $([[ "$remote_checked" == "true" ]] && echo "true" || echo "false"),"
  echo "    \"host\": \"$REMOTE_HOST\","
  echo "    \"user\": \"$REMOTE_USER\","
  echo "    \"repo_path\": \"$REMOTE_REPO_PATH\","
  echo "    \"error\": \"${remote_error}\","
  echo "    \"dirty_count\": $remote_dirty_count,"
  echo "    \"stash_count\": $remote_stash_count,"
  echo "    \"dot_underscore_count\": $remote_dot_count"
  echo "  },"
  echo "  \"findings\": ["
  for i in "${!finding_lines[@]}"; do
    comma=","
    if [[ "$i" -eq "$((${#finding_lines[@]} - 1))" ]]; then
      comma=""
    fi
    echo "    \"${finding_lines[$i]}\"$comma"
  done
  echo "  ]"
  echo "}"
} >"$OUTPUT_JSON"

echo "Repo hygiene report: $OUTPUT_JSON"
if [[ "$issue_count" -eq 0 ]]; then
  echo "Repo hygiene check passed."
  exit 0
fi

echo "Repo hygiene findings:"
for line in "${finding_lines[@]}"; do
  echo "  - $line"
done

if [[ "$FAIL_ON_FINDINGS" == "true" ]]; then
  exit 1
fi

exit 0
