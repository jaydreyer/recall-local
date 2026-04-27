# Agent Instructions

Placeholder conventions used in this public repo:

- `<repo-root>`: local checkout root
- `<server-repo-root>`: deployment checkout root on the runtime host
- `<vault-root>`: mounted Obsidian vault path
- `<ai-lab-lan-ip>`: private LAN address for the runtime host
- `<ai-lab-tailnet-ip>`: private Tailnet address for the runtime host
- `<ai-lab-public-host>`: reverse-proxied public hostname for n8n and dashboards

## Mandatory Sync Rule (Mac -> ai-lab)

Whenever code is created or updated locally on `<repo-root>`, sync those changes to `ai-lab` (`<server-repo-root>`) before any ai-lab restart, curl verification, or n8n validation.

Do not assume ai-lab has current code until sync is complete and spot-checked.

## Verification After Sync

After syncing, run at least one quick file-content check on `ai-lab` (for example with `rg` on newly added route/function names) before troubleshooting runtime errors.

## SSH Access To ai-lab

Use the `ai-lab` SSH host alias. It is expected to resolve with this identity:

- host: `ai-lab`
- user: `jaydreyer`
- hostname: `<ai-lab-lan-ip>`
- identity file: `~/.ssh/codex_ai_lab`

Quick connectivity check:

```bash
ssh ai-lab 'hostname && pwd'
```

Codex sandbox note: if `ssh ai-lab ...`, `nc`, `ping`, or route checks fail with local sandbox/network errors such as `Operation not permitted` or `No route to host`, do not assume the SSH alias or key is broken. Re-run the same SSH or TCP reachability command with escalated permissions. The `ai-lab` alias and `~/.ssh/codex_ai_lab` key are the expected path.

If the alias is unavailable for any reason, use:

```bash
ssh -i ~/.ssh/codex_ai_lab -o IdentitiesOnly=yes jaydreyer@<ai-lab-lan-ip> 'hostname && pwd'
```

## Docker Safety Rules (Mandatory)

The live ai-lab stack is defined only by:

- `<server-repo-root>/docker/docker-compose.yml`
- `<server-repo-root>/docker/.env`

Do not start or recreate `n8n`, `ollama`, `qdrant`, `recall-ingest-bridge`, `recall-ui`, `recall-daily-dashboard`, or `recall-mkdocs` with `docker run`.

Do not run the Compose stack under any project name other than `recall`.

Do not change or remove these invariants unless the user explicitly approves it:

- Compose project name: `recall`
- External Docker network: `recall_backend`
- Qdrant volume: `docker_qdrant-storage`
- Ollama volume: `docker_ollama-models`

Before any Docker change on ai-lab that could restart, recreate, or move containers, inspect and preserve:

- current Compose project labels
- current attached Docker networks
- current mounted Docker volumes

Use this validation script before and after any Docker change:

- `<server-repo-root>/docker/validate-stack.sh`

If any service moves off `recall_backend`, switches to a different Compose project, or loses the expected volume attachment, stop and repair that before further troubleshooting.

## Required ai-lab Validation

Run this after any Docker-related change on ai-lab:

```bash
cd <server-repo-root>/docker
./validate-stack.sh
```

Do not proceed with n8n, Ollama, or Qdrant troubleshooting unless this validation passes.

## Daily Dashboard Validation

After changes that affect the daily dashboard UI, the Phase 6 jobs/companies/gaps endpoints, or nginx proxy behavior:

- run the dashboard smoke wrapper:
  - `<repo-root>/scripts/phase6/run_dashboard_smoke.sh`
- if the smoke result is not `ok`, inspect:
  - `GET /v1/dashboard-checks`
  - `<repo-root>/docs/Recall_local_Daily_Dashboard_Reliability_Runbook.md`

## Ops Observability Validation

After changes that affect operator readiness, dashboard reliability, bridge availability, or demo safety:

- run the consolidated operator check:
  - `<repo-root>/scripts/phase6/run_ops_observability_check.sh`
- review the latest artifact in:
  - `<repo-root>/data/artifacts/observability`
- if the consolidated check fails, inspect:
  - `GET /v1/healthz`
  - `GET /v1/dashboard-checks`
  - `<repo-root>/docs/OBSERVABILITY_STRATEGY.md`

## RAG Quality Validation

After changes to RAG retrieval, prompts, output validation, model selection, or the dashboard chat UI:

- run the manual UI checklist in `<repo-root>/docs/Recall_local_RAG_UI_QA_Checklist.md`
- if the change affects retrieval/generation quality, run `<repo-root>/scripts/eval/run_rag_model_bakeoff.sh`
- keep the live ai-lab default pinned unless the bakeoff shows a clear quality improvement without unacceptable latency

## Ollama Model Invariant

The live ai-lab stack must explicitly keep these model settings aligned in `<server-repo-root>/docker/.env`:

- `RECALL_LLM_PROVIDER=ollama`
- `OLLAMA_MODEL=qwen2.5:7b-instruct`
- `OLLAMA_EMBED_MODEL=nomic-embed-text`

Do not rely on code defaults for the live stack. Keep the `.env` values explicit.

After any change that touches Ollama, the bridge, or `docker/.env`, verify both models are installed in the live Ollama volume:

```bash
docker exec -i ollama ollama list
```

`<server-repo-root>/docker/validate-stack.sh` is expected to fail if either configured model is missing.

## Newsletter Workflow Safety

The newsletter automation depends on n8n being able to resolve `ollama` and `qdrant` over Docker DNS from inside the `n8n` container.

If the newsletter workflow fails with `getaddrinfo EAI_AGAIN ollama`, treat it as a Docker network regression first, not an Ollama model issue.

Before changing newsletter credentials or workflow nodes, verify:

```bash
docker exec -i n8n node -e "require('dns').lookup('ollama',(e,a)=>{if(e){console.error(e);process.exit(1)};console.log(a)})"
docker exec -i n8n node -e "require('http').get('http://ollama:11434/api/tags',r=>console.log(r.statusCode)).on('error',e=>{console.error(e);process.exit(1)})"
docker exec -i n8n node -e "require('http').get('http://qdrant:6333/healthz',r=>console.log(r.statusCode)).on('error',e=>{console.error(e);process.exit(1)})"
```

## n8n URL and OAuth Safety

The live n8n base URL is expected to be:

- `https://<ai-lab-public-host>/n8n`

These environment values must remain aligned in the running n8n container:

- `N8N_HOST=<ai-lab-public-host>`
- `N8N_PROTOCOL=https`
- `N8N_PATH=/n8n/`
- `N8N_EDITOR_BASE_URL=https://<ai-lab-public-host>/n8n`
- `WEBHOOK_URL=https://<ai-lab-public-host>/n8n/`
- `OLLAMA_BASE_URL=http://ollama:11434`

If Google OAuth callbacks fail or show `502`, inspect proxy routing and Docker DNS before changing credentials.

## Restore/Recovery Discipline

Before any potentially destructive Docker or n8n state change:

- back up `<server-repo-root>/n8n`
- back up the Qdrant volume
- back up the Ollama models volume
- export n8n workflows if the UI/API is available

Never run `docker compose down -v` on this stack unless the user explicitly asks for volume destruction.

## API Skill Routing

For any task involving APIs (design, review, OpenAPI/Swagger specs, endpoint naming, request/response schemas, status codes, or API documentation), always use the `rest-api-design` skill from `$CODEX_HOME/skills/rest-api-design/SKILL.md` and follow its workflow, non-negotiables, and output templates.

Only skip this skill if the user explicitly requests a different approach, or it is impossible to implement due to extenuating circumstances. If the latter is the case, work with the user on a solution.
