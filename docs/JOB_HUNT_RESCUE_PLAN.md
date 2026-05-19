# Job Hunt Rescue Plan

Current phase: Phase 1 - Model bakeoff

Last updated: 2026-05-19

## Resume Prompt For Future Chats

Read `AGENTS.md` and `docs/JOB_HUNT_RESCUE_PLAN.md`; continue from the current phase. Follow the ai-lab sync, Docker safety, dashboard smoke, ops observability, and REST API skill rules.

## Current State Snapshot

- Local repo: `/Users/jaydreyer/projects/recall-local`.
- Runtime host: `ai-lab`, server repo `/home/jaydreyer/recall-local`.
- Qdrant is up, healthy, and populated. Recent observed collections/counts: `recall_resume=13`, `recall_docs=1839`, `newsletter_stories=1134`, `recall_jobs=2851`.
- Resume ingestion is current as of 2026-05-19. Current resume version observed through `/v1/resumes/current`: version 4, 13 chunks, source inline markdown from `Jay-Dreyer-Resume.md`.
- Dashboard/job system is live and fresh, but relevance and prioritization are too noisy. Recent observed stats: 2495 total jobs, 669 high-fit jobs, and 828 unscored jobs.
- `GET /v1/job-gaps` has timed out/hung during manual checks and needs caching or precomputation before relying on it in the dashboard.
- `GET /v1/jobs?status=all` currently defaults to `min_score=0`, so API totals can exclude unscored jobs while stats include them.
- Live ai-lab repo has previously shown local/server drift and a dirty worktree. Before runtime validation after code changes, sync Mac to ai-lab and spot-check file contents on ai-lab.

## Decisions Already Made

- Primary goal: make the site genuinely useful for Jay's job hunt, not just a broad job collector.
- Daily workflow target: show the top 3 useful job actions first.
- Data cleanup policy: aggressively archive broad adjacent or off-target jobs while preserving history; do not delete job history.
- Company search policy: keep company discovery broad. Known target companies may receive a soft boost, but company lists must not be hard limits.
- AI Engineer scope: prioritize LLM apps, agents, RAG, and practical AI implementation roles.
- Model tradeoff: quality first, with latency still reasonable enough for daily use.
- Model source policy: include the updated `llmfit` screenshot candidates, but require Ollama compatibility and objective bakeoff results before promotion.
- Coding-tuned models may be tested but should not be favored for job-fit evaluation unless they win on job-fit quality.
- Skill install note: `bobmatnyc/claude-mpm-skills@local-llm-ops` was advertised by skills search, but its repository exposed only `mcp-protocol-builder` during install. Use installed fallback `local-llm-expert` for local model work unless `local-llm-ops` becomes available later.

## Target Job Titles

- Solutions Engineer
- AI Engineer
- Technical Account Manager
- Customer Engineer
- Forward Deployed Engineer

## Model Baseline And Candidate Pool

Current live/installed Ollama models observed on ai-lab:

- `nomic-embed-text:latest`
- `gemma4:e4b`
- `gemma4:e2b`
- `qwen2.5:7b-instruct`
- `gemma3:12b-it-qat`
- `qwen3.5:9b`
- `llama3:8b`
- `llama3.2:3b`

Known dry-run findings:

- `llama3.2:3b` failed the job-fit golden runner with malformed/non-JSON output and should not remain the default evaluator.
- `qwen2.5:7b-instruct` produced valid output but under-scored strong target roles in the golden set.
- `qwen3.5:9b` returned an empty response in the golden run.
- `gemma3:12b-it-qat` is the strongest installed baseline so far, but still missed some target cases.
- `gemma4:e4b` returned invalid JSON in the golden run.

Updated `llmfit` screenshot candidates to investigate first:

- `deepseek-ai/DeepSeek-V2-Lite`
- `nvidia/Qwen3-30B-A3B-NVFP4`
- `Qwen/Qwen1.5-MoE-A2.7B`
- `moonshotai/Moonlight-16B-A3B`
- `inclusionAI/LLaDA2.1-mini`
- `cyankiwi/Qwen3-Next-80B-A3B-Thinking-AWQ-4bit`
- `solidrust/gemma-2-9b-it-AWQ`
- `dengcao/GLM-4.1V-9B-Thinking-AWQ`
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`
- `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B`
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
- `cyankiwi/Qwen3.5-9B-AWQ-4bit`
- `Qwen/Qwen3-14B-AWQ`

Promotion criteria for a new local evaluator:

- Valid structured JSON on every golden case.
- At least 80% golden pass rate.
- Beats `gemma3:12b-it-qat` on Jay's job-fit golden and real-job calibration cases.
- Correctly identifies strong matches across the five target titles.
- Avoids turning broad/off-target roles into false high-fit recommendations.
- Median latency is acceptable for daily scoring and dashboard use.

## Phased Roadmap

### Phase 0 - Install Skills And Durable Plan

Status: complete.

Acceptance criteria:

- Global skills installed or verified:
  - `sickn33/antigravity-awesome-skills@local-llm-expert` as fallback for unavailable `bobmatnyc/claude-mpm-skills@local-llm-ops`
  - `secondsky/claude-skills@api-testing`
  - `erichowens/some_claude_skills@reactive-dashboard-performance`
- This document exists at `docs/JOB_HUNT_RESCUE_PLAN.md`.
- No app behavior changes are made in Phase 0.

### Phase 1 - Model Bakeoff

Goal: identify the best local model for job-fit scoring before changing ranking or dashboard behavior.

Implementation notes:

- Use the `local-llm-expert` skill when available.
- If `local-llm-ops` becomes installable later, it may be used as an additional model-ops reference.
- Verify Ollama compatibility before assuming screenshot models can be used.
- Prefer Ollama-native models first, then GGUF imports only when needed.
- Keep the live stack stable; do not restart Docker services just to test a model unless required and approved by the repo safety rules.
- Run the existing golden runner against installed candidates and any newly pulled/imported candidates.
- Add or assemble a real-job calibration set covering the five target titles and negative controls.

Acceptance criteria:

- Candidate results are recorded with model name, install/import method, JSON validity, golden pass rate, real-job behavior, and latency.
- A recommended local evaluator is chosen or the plan explicitly records why no local model is good enough yet.
- Current app behavior is not changed until a winner is selected.

### Phase 2 - Evaluation Pipeline Cleanup

Goal: make the chosen evaluator reliable and remove stale `llama3.2:3b` assumptions.

Implementation notes:

- Replace hardcoded Phase 6 `llama3.2:3b` defaults with runtime settings or explicit environment defaults.
- Tighten structured output validation and retry/fallback behavior.
- Keep cloud escalation available for low-quality local outputs.
- Preserve the live Docker `.env` invariants unless intentionally changing them after validation.

Acceptance criteria:

- Job evaluation returns valid structured results for representative target and negative-control jobs.
- The selected local model is visible through `GET /v1/llm-settings` or documented as the active runtime default.
- Required validation passes after sync to ai-lab.

### Phase 3 - Job Relevance And Ranking

Goal: make the job corpus useful by prioritizing the right roles and archiving obvious noise.

Implementation notes:

- Update discovery/ranking around the five target titles.
- Keep company search broad with only a soft boost for known companies.
- Auto-archive broad adjacent/off-target jobs while preserving history.
- Prefer ranking signals that explain why a job is a good action for Jay today.

Acceptance criteria:

- Top recommendations are dominated by the target title families.
- False high-fit roles are reduced.
- Archived jobs remain inspectable and recoverable.

### Phase 4 - Dashboard And API Polish

Goal: make the daily dashboard fast, clear, and action-oriented.

Implementation notes:

- Use the `rest-api-design` skill for any endpoint design or schema changes.
- Use the `api-testing` skill for API behavior validation when available.
- Use the dashboard performance skill if reload loops, slow hooks, or client-side blocking become the main issue.
- Fix the confusing `status=all`/`min_score=0` behavior or make it explicit in the UI/API.
- Cache or precompute expensive gap aggregation so `/v1/job-gaps` does not hang the dashboard.
- Add a top-actions view using existing data first; if an endpoint is needed, use a collection-style design such as `GET /v1/job-actions?limit=3`.

Acceptance criteria:

- Dashboard loads without waiting on slow gap aggregation.
- Top 3 actions are visible and useful.
- Job counts are understandable and consistent.
- Dashboard smoke and ops observability checks pass.

### Phase 5 - End-To-End ai-lab Validation

Goal: prove the full system works on the live ai-lab stack.

Implementation notes:

- Sync Mac changes to ai-lab before any live curl, n8n, or restart validation.
- Spot-check synced file contents on ai-lab before debugging runtime behavior.
- Preserve Compose project, network, and volume invariants.

Acceptance criteria:

- `docker/validate-stack.sh` passes on ai-lab.
- `scripts/phase6/run_dashboard_smoke.sh` passes.
- `scripts/phase6/run_ops_observability_check.sh` passes when applicable.
- A sample job evaluation batch demonstrates improved fit quality.
- The plan document is updated with completion notes and the next phase marker.

## Verification Commands

Local repo status:

```bash
cd /Users/jaydreyer/projects/recall-local
git status --short --branch
```

ai-lab connectivity:

```bash
ssh ai-lab 'hostname && pwd'
```

ai-lab stack validation:

```bash
ssh ai-lab 'cd /home/jaydreyer/recall-local/docker && ./validate-stack.sh'
```

Ollama model inventory:

```bash
ssh ai-lab 'docker exec -i ollama ollama list'
```

Dashboard smoke:

```bash
ssh ai-lab 'cd /home/jaydreyer/recall-local && RECALL_DASHBOARD_SMOKE_INCLUDE_GAPS=false scripts/phase6/run_dashboard_smoke.sh http://localhost:8090'
```

Job stats:

```bash
ssh ai-lab 'curl -fsS http://localhost:8090/v1/job-stats'
```

Golden job-fit runner:

```bash
ssh ai-lab 'cd /home/jaydreyer/recall-local && scripts/eval/run_job_fit_golden.py --model local --local-model <model> --dry-run'
```

## ai-lab Safety Reminders

- After local code changes, sync to ai-lab before live curl, n8n, restart, or Docker validation.
- After syncing, verify at least one changed file's contents on ai-lab before troubleshooting.
- Do not use `docker run` for live stack services.
- Do not use a Compose project name other than `recall`.
- Preserve `recall_backend`, `docker_qdrant-storage`, and `docker_ollama-models`.
- Run `/home/jaydreyer/recall-local/docker/validate-stack.sh` after Docker-related changes.
- After dashboard, endpoint, or nginx changes, run `scripts/phase6/run_dashboard_smoke.sh`.
- After operator readiness, dashboard reliability, bridge availability, or demo-safety changes, run `scripts/phase6/run_ops_observability_check.sh`.
- After RAG retrieval, prompt, output validation, model selection, or dashboard chat changes, follow the RAG QA checklist and run the bakeoff when quality is affected.
- For API design, schema, status code, or documentation work, use the `rest-api-design` skill.

## Phase Completion Log

- 2026-05-19: Phase 0 created this durable plan and set the current phase to Phase 1 - Model bakeoff.
- 2026-05-19: Installed `api-testing`, `reactive-dashboard-performance`, and `local-llm-expert`. Attempted `local-llm-ops`; skills search listed it, but the source installed only `mcp-protocol-builder`, so `local-llm-expert` is the active local-LLM helper skill.
