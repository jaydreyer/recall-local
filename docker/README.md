# Recall Docker Stack

This stack is operationally sensitive. Treat this directory as the source of truth for the live `ai-lab` deployment.

Public-repo note: machine-specific paths and hostnames are intentionally represented with placeholders.

## Canonical Files

- Compose file: `<server-repo-root>/docker/docker-compose.yml`
- Environment file: `<server-repo-root>/docker/.env`
- Validation script: `<server-repo-root>/docker/validate-stack.sh`

## Required Invariants

These must remain true unless the user explicitly approves a change:

- Compose project name: `recall`
- External Docker network: `recall_backend`
- Qdrant volume: `docker_qdrant-storage`
- Ollama volume: `docker_ollama-models`
- n8n base URL: `https://<ai-lab-public-host>/n8n`

## Do Not

- Do not start `n8n`, `ollama`, `qdrant`, `recall-ingest-bridge`, `recall-ui`, `recall-daily-dashboard`, or `recall-mkdocs` with `docker run`.
- Do not run this stack under any Compose project name other than `recall`.
- Do not use `docker compose down -v` unless the user explicitly wants to destroy volumes.
- Do not assume Docker default networks are acceptable for service discovery.

## Why This Matters

The newsletter and Recall workflows depend on Docker DNS from inside `n8n`.

If `ollama` or `qdrant` lands on the wrong Docker network, `n8n` fails with errors such as:

- `getaddrinfo EAI_AGAIN ollama`
- `getaddrinfo EAI_AGAIN qdrant`
- OAuth callback and reverse proxy failures caused by container-to-container DNS mismatch

## Required Validation

Run this before and after any Docker change:

```bash
cd <server-repo-root>/docker
./validate-stack.sh
```

Do not continue troubleshooting application behavior until this validation passes.

## Minimum Recovery Checks

If the newsletter or Recall workflows suddenly fail:

```bash
docker inspect n8n --format 'project={{ index .Config.Labels "com.docker.compose.project" }} networks={{json .NetworkSettings.Networks}}'
docker inspect ollama --format 'project={{ index .Config.Labels "com.docker.compose.project" }} networks={{json .NetworkSettings.Networks}}'
docker inspect qdrant --format 'project={{ index .Config.Labels "com.docker.compose.project" }} networks={{json .NetworkSettings.Networks}}'
docker exec -i n8n node -e "require('dns').lookup('ollama',(e,a)=>{if(e){console.error(e);process.exit(1)};console.log(a)})"
docker exec -i n8n node -e "require('http').get('http://ollama:11434/api/tags',r=>console.log(r.statusCode)).on('error',e=>{console.error(e);process.exit(1)})"
docker exec -i n8n node -e "require('http').get('http://qdrant:6333/healthz',r=>console.log(r.statusCode)).on('error',e=>{console.error(e);process.exit(1)})"
```

## Safe Workflow For Changes

1. Edit the local files in `<repo-root>`.
2. Sync them to `<server-repo-root>` on `ai-lab`.
3. Spot-check the synced files on `ai-lab`.
4. Run `docker compose config`.
5. Run `./validate-stack.sh` before restart if the stack is already up.
6. Apply the change.
7. Run `./validate-stack.sh` again immediately after.

If validation fails, stop and fix the infrastructure state before changing credentials, workflows, or application code.
