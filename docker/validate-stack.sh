#!/usr/bin/env bash
set -euo pipefail

EXPECTED_PROJECT="recall"
EXPECTED_NETWORK="recall_backend"
EXPECTED_QDRANT_VOLUME="docker_qdrant-storage"
EXPECTED_OLLAMA_VOLUME="docker_ollama-models"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_cmd docker
require_cmd jq

check_container_exists() {
  local name="$1"
  docker inspect "$name" >/dev/null 2>&1 || {
    echo "Missing container: $name" >&2
    exit 1
  }
}

container_project() {
  local name="$1"
  docker inspect "$name" --format '{{ index .Config.Labels "com.docker.compose.project" }}'
}

container_networks_json() {
  local name="$1"
  docker inspect "$name" --format '{{json .NetworkSettings.Networks}}'
}

assert_project() {
  local name="$1"
  local project
  project="$(container_project "$name")"
  if [[ "$project" != "$EXPECTED_PROJECT" ]]; then
    echo "$name has wrong compose project: $project" >&2
    exit 1
  fi
}

assert_network() {
  local name="$1"
  local networks
  networks="$(container_networks_json "$name")"
  echo "$networks" | jq -e --arg net "$EXPECTED_NETWORK" 'has($net)' >/dev/null || {
    echo "$name is not attached to $EXPECTED_NETWORK" >&2
    exit 1
  }
}

assert_mount_name() {
  local name="$1"
  local expected="$2"
  docker inspect "$name" --format '{{json .Mounts}}' \
    | jq -e --arg expected "$expected" '.[] | select(.Name == $expected)' >/dev/null || {
      echo "$name is not using expected volume $expected" >&2
      exit 1
    }
}

echo "Checking container presence..."
for c in n8n ollama qdrant recall-ingest-bridge; do
  check_container_exists "$c"
done

echo "Checking compose project labels..."
for c in n8n ollama qdrant recall-ingest-bridge; do
  assert_project "$c"
done

echo "Checking network attachments..."
for c in n8n ollama qdrant recall-ingest-bridge; do
  assert_network "$c"
done

echo "Checking persistent volume attachments..."
assert_mount_name qdrant "$EXPECTED_QDRANT_VOLUME"
assert_mount_name ollama "$EXPECTED_OLLAMA_VOLUME"

echo "Checking n8n -> ollama DNS..."
docker exec -i n8n node -e "require('dns').lookup('ollama',(e,a)=>{if(e){console.error(e);process.exit(1)};console.log(a)})" >/dev/null

echo "Checking n8n -> ollama HTTP..."
docker exec -i n8n node -e "require('http').get('http://ollama:11434/api/tags',res=>{process.exit(res.statusCode===200?0:1)}).on('error',()=>process.exit(1))"

echo "Checking n8n -> qdrant HTTP..."
docker exec -i n8n node -e "require('http').get('http://qdrant:6333/healthz',res=>{process.exit(res.statusCode===200?0:1)}).on('error',()=>process.exit(1))"

echo "Validation passed."
