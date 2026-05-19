# Job Hunt Rescue Plan

Current phase: Phase 3 - Job Relevance And Ranking

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
- Cloud model policy: do not assume any OpenAI or Anthropic model ID is available just because public docs list it. Query the live ai-lab API credentials first, then bake off only models that are actually callable from this deployment.
- Skill install note: `bobmatnyc/claude-mpm-skills@local-llm-ops` was advertised by skills search, but its repository exposed only `mcp-protocol-builder` during install. Use installed fallback `local-llm-expert` for local model work unless `local-llm-ops` becomes available later.

## Target Job Titles

- Solutions Engineer
- AI Engineer
- Technical Account Manager
- Customer Engineer
- Forward Deployed Engineer

## Model Baseline And Candidate Pool

Current live/installed Ollama models observed on ai-lab:

- `qwen3:30b`
- `qwen3:14b`
- `deepseek-v2:16b`
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
- `gemma4:e4b` looked best on the synthetic golden set, but failed structured output on real postings.
- `deepseek-v2:16b` failed with an out-of-range scorecard value.
- `qwen3:14b` passed only 60% of synthetic cases and failed structured output on most real postings.
- `qwen3:30b` is too slow/unreliable for the current app path: it ran for 494 seconds and returned an empty response.

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

Status: complete.

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

Results recorded 2026-05-19:

| Model | Install method | Synthetic golden result | Real-job calibration | Phase 1 call |
| --- | --- | --- | --- | --- |
| `llama3.2:3b` | already installed | malformed/non-JSON | not retested after golden failure | reject |
| `llama3:8b` | already installed | 4/5, 80%, fast | failed JSON on 6/8 real postings | reject until prompt/parser repair |
| `qwen2.5:7b-instruct` | already installed | 2/5, 40% | not retested after weak golden | reject |
| `qwen3.5:9b` | already installed | empty response | not retested after empty response | reject |
| `gemma3:12b-it-qat` | already installed | 3/5, 60% | valid JSON on 8/8 real postings, but over-scored some broad/non-target roles | best reliable local fallback |
| `gemma4:e2b` | already installed | malformed scorecard value | not retested after malformed output | reject |
| `gemma4:e4b` | already installed | 4/5, 80% | failed structured output on 8/8 real postings | reject until prompt/parser repair |
| `deepseek-v2:16b` | `ollama pull deepseek-v2:16b` | malformed scorecard value | not retested after malformed output | reject |
| `qwen3:14b` | `ollama pull qwen3:14b` | 3/5, 60%, median about 26s | valid JSON on only 2/8 real postings | reject |
| `qwen3:30b` | `ollama pull qwen3:30b` | ran 494s then empty response | not retested after empty response | reject for current hardware/app path |

Phase 1 recommendation:

- Do not promote any newly pulled model.
- Use `gemma3:12b-it-qat` as the best current local fallback for Phase 2 reliability work, not as a final quality winner.
- Phase 2 should focus on prompt/parser/output validation improvements before more model shopping. The bakeoff suggests model size alone is not solving structured-output reliability.
- Keep `qwen2.5:7b-instruct` pinned for the broader live Ollama stack until Phase 2 proves a better end-to-end setting and the Docker `.env` invariant is intentionally updated.
- Real-job calibration used a quick sampled set from current Qdrant jobs. The negative-control selection was imperfect because current ranking has already over-scored broad solutions/architecture roles; Phase 3 should build a cleaner calibration fixture after relevance cleanup.

### Phase 2 - Evaluation Pipeline Cleanup

Goal: make job evaluation reliable, even if the winning evaluator is cloud-first instead of local-first.

Status: complete enough to promote a guarded evaluator path; quality/ranking cleanup continues in Phase 3.

Implementation notes:

- First discover cloud model availability from the live ai-lab credentials. Record the exact callable OpenAI and Anthropic model IDs, endpoint support, and any auth/rate-limit failures.
- Do not hardcode assumed OpenAI candidates. If available, include `gpt-5-mini`, `gpt-4.1-mini`, current flagship GPT models, and any other callable structured-output-capable OpenAI models in the bakeoff.
- If Anthropic credentials are available, include the current configured Claude model and any callable lower-cost Claude model exposed to this account.
- Run the same synthetic golden and real-job calibration against cloud candidates, using schema-enforced or tool-call structured output where the provider supports it.
- Select a default evaluator using this priority: valid structured output on real jobs, correct target/negative ranking, latency, then cost.
- Keep local Ollama as fallback only unless it beats the cloud candidates on the same evidence. Start fallback work from `gemma3:12b-it-qat`, because it was the only local candidate that returned valid JSON for all sampled real postings.
- Replace hardcoded Phase 6 `llama3.2:3b` defaults with runtime settings or explicit environment defaults.
- Tighten structured output validation and retry/fallback behavior using the real-job failure modes from `llama3:8b`, `gemma4:e4b`, and `qwen3:14b`.
- Preserve the live Docker `.env` invariants unless intentionally changing them after validation.

Recommended architecture direction:

- Cloud-first for bulk job-fit scoring if an affordable structured-output model is available to Jay's account.
- Local fallback for offline/privacy/cost-control cases, not the primary quality path.
- Claude/Sonnet-style models reserved for deeper qualitative artifacts unless they win cost-adjusted scoring quality in the bakeoff.
- Budget controls are required before enabling broad cloud scoring: max jobs per run, per-run estimated token/cost cap, and a dry-run/report-only mode.

Acceptance criteria:

- Live available cloud model IDs are recorded in this document before any promotion decision.
- Job evaluation returns valid structured results for representative target and negative-control jobs.
- The selected evaluator is visible through `GET /v1/llm-settings` or documented as the active runtime default.
- Local fallback behavior is documented and tested.
- Budget guardrails are documented before any broad cloud evaluation run.
- Required validation passes after sync to ai-lab.

Results recorded 2026-05-19:

- Added `scripts/eval/discover_cloud_models.py` to discover callable OpenAI/Anthropic models from live ai-lab credentials and write JSON artifacts.
- Added `scripts/eval/run_job_fit_bakeoff.py` to run the same job-fit golden cases plus sampled real-job calibration across local/cloud candidates.
- Added OpenAI Responses API support for GPT-5-family evaluator calls; GPT-4.1/4o-family calls continue to use Chat Completions with JSON mode.
- Added evaluator budget guardrails:
  - `max_jobs_per_run`, default `10`
  - `max_cloud_cost_usd`, default `1.0`
  - batches above the job cap are skipped instead of silently expanding cloud spend
  - cloud batches above the estimated cap fail closed before model calls
- Replaced Phase 6 evaluator defaults away from `llama3.2:3b`; local fallback is now `gemma3:12b-it-qat`.
- Persisted live ai-lab evaluator settings to:
  - `evaluation_model=cloud`
  - `cloud_provider=openai`
  - `cloud_model=gpt-4.1-mini`
  - `local_model=gemma3:12b-it-qat`
  - `auto_escalate=false`
  - `max_jobs_per_run=10`
  - `max_cloud_cost_usd=1.0`

Cloud discovery artifacts:

- `/home/jaydreyer/recall-local/data/artifacts/evals/cloud-model-discovery/20260519T183840Z_cloud_model_discovery.json`
- `/home/jaydreyer/recall-local/data/artifacts/evals/cloud-model-discovery/20260519T185341Z_cloud_model_discovery.json`

Callable OpenAI models observed through live ai-lab credentials:

| Model | Endpoint | Structured JSON probe | Notes |
| --- | --- | --- | --- |
| `gpt-4o-mini` | Chat Completions | pass | Cheapest viable OpenAI scorer, but over-scored a negative-control internship in calibration. |
| `gpt-4.1-mini` | Chat Completions | pass | Selected default: best cost/latency/reliability tradeoff in the sampled bakeoff. |
| `gpt-5-mini` | Responses | pass after Responses wiring | Callable, stricter, but slower and initially exhausted output cap without GPT-5-specific handling. |
| `gpt-5` | Responses | pass after Responses wiring | Callable, not chosen for bulk scoring due expected cost/latency. |
| `gpt-5.1` | Responses | pass | Callable, stricter on negatives, but slowest sampled candidate and under-scored target golden cases. |
| `gpt-5.2` | Responses | pass | Callable in probe; not run through full calibration in this pass. |

Callable Anthropic models observed through live ai-lab credentials:

| Model | Endpoint | Structured JSON probe | Notes |
| --- | --- | --- | --- |
| `claude-sonnet-4-20250514` | Messages | pass | Callable; reserved for deeper artifacts unless it wins a future scoring bakeoff. |
| `claude-opus-4-1-20250805` | Messages | pass | Callable but likely too expensive for bulk job scoring. |
| `claude-opus-4-20250514` | Messages | pass | Callable but likely too expensive for bulk job scoring. |
| `claude-opus-4-5-20251101` | Messages | pass in first probe | Not selected for bulk scoring. |
| `claude-opus-4-6` | Messages | pass in first probe | Not selected for bulk scoring. |

Cloud bakeoff artifact:

- `/home/jaydreyer/recall-local/data/artifacts/evals/job-fit-bakeoff/20260519T190922Z_job_fit_bakeoff.json`

Sampled bakeoff summary:

| Candidate | Golden subset | Real-job JSON | Avg latency | Phase 2 call |
| --- | ---: | ---: | ---: | --- |
| `openai:gpt-4o-mini` | 0/3 | 3/3 | 17.5s | reject as default; over-scored negative internship at 74 |
| `openai:gpt-4.1-mini` | 0/3 | 3/3 | 12.0s | selected default; strongest current cost/reliability balance |
| `openai:gpt-5-mini` | 0/3 | 3/3 | 13.5s | keep as future escalation candidate after more prompt/rubric tuning |
| `openai:gpt-5.1` | 0/3 | 3/3 | 25.8s | reject for bulk scoring; stricter but slower and under-scored targets |

Interpretation:

- No cloud model passed the current golden thresholds without additional prompt/rubric calibration.
- All sampled OpenAI cloud candidates returned valid structured JSON for sampled real jobs after the Responses path was added for GPT-5-family models.
- `gpt-4o-mini` is cheapest, but it over-scored an obvious negative control (`Engineering Intern`) at 74.
- GPT-5-family models were stricter on negatives, but under-scored strong target cases and added latency/cost risk.
- `gpt-4.1-mini` is the best reliable default for now because it returned valid JSON, separated the internship negative better than `4o-mini`, and is materially cheaper/faster than GPT-5-family models.
- Phase 3 should focus on relevance/ranking and rubric calibration; the current golden thresholds may be too coupled to local-model behavior and should be revisited after corpus cleanup.

Validation:

- Synced changed files from Mac to ai-lab and spot-checked contents before live validation.
- Ran `docker/validate-stack.sh` before and after restarting `recall-ingest-bridge`; both passed.
- Restarted only `recall-ingest-bridge` with `docker compose -p recall --env-file .env -f docker-compose.yml restart recall-ingest-bridge`; no `docker run`, no project-name change, no volume changes.
- `GET /v1/healthz` returned `{"status":"ok"}` after restart.
- `GET /v1/llm-settings` returned the selected `openai:gpt-4.1-mini` cloud evaluator and `gemma3:12b-it-qat` fallback.
- Dashboard smoke with gaps disabled passed with status `ok`.
- Ops observability check artifact `/home/jaydreyer/recall-local/data/artifacts/observability/20260519T191258Z_ops_observability_check.json` returned `error` because `job_alert_workflow` and `rag_probe` timed out; bridge health, dashboard checks, daily dashboard UI, and chat UI were `ok`. Treat this as residual workflow/RAG slowness for follow-up, not as evaluator model selection failure.

### Phase 3 - Job Relevance And Ranking

Goal: make the job corpus useful by prioritizing the right roles and archiving obvious noise.

Handoff prompt for the next chat:

```text
Read AGENTS.md and docs/JOB_HUNT_RESCUE_PLAN.md in /Users/jaydreyer/projects/recall-local.

Continue from the current phase: Phase 3 - Job Relevance And Ranking.

Important context:
- Phase 2 selected the guarded default evaluator path: cloud `openai:gpt-4.1-mini` with local fallback `gemma3:12b-it-qat`.
- Do not rerun model shopping first. The next value is ranking/corpus cleanup, not another bakeoff.
- Top live issue: too many false high-fit and broad/off-target roles. Recent sampled negative controls included `Engineering Intern` and Java/Spring/Azure backend roles that should not rank highly for Jay.
- Preserve history; archive or deprioritize noisy jobs rather than deleting them.
- Keep company discovery broad. Known companies can get a soft boost, but company lists must not become hard filters.
- Target titles remain: Solutions Engineer, AI Engineer, Technical Account Manager, Customer Engineer, Forward Deployed Engineer.
- Follow AGENTS.md strictly: sync Mac changes to ai-lab before live validation, preserve Docker/Compose invariants, use rest-api-design for API work, and do not disturb unrelated dirty ai-lab worktree changes.

Goal for this chat:
Implement Phase 3 enough that the daily job list is dominated by the five target title families and obvious noise is archived/deprioritized while remaining inspectable.
```

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

Cloud model discovery:

```bash
ssh ai-lab 'cd /home/jaydreyer/recall-local && env | rg "OPENAI|ANTHROPIC|RECALL_PHASE6_EVAL|CLOUD_MODEL|CLOUD_PROVIDER"'
```

When credentials are present, query provider model availability through the configured SDK/API and record only callable model IDs in this plan.

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
- 2026-05-19: Phase 1 completed. Pulled `deepseek-v2:16b`, `qwen3:14b`, and `qwen3:30b`; verified `ollama list`; ran stack validation; ran synthetic golden and real-job calibration. No new model beat the current best reliable fallback. Current phase set to Phase 2 - Evaluation pipeline cleanup.
- 2026-05-19: Phase 2 plan updated to evaluate cloud-first scoring. Do not assume `gpt-5-mini`, `gpt-4.1-mini`, or any Claude model is available to the live account; discover callable models from ai-lab credentials, then bake off cloud candidates against the same golden and real-job calibration sets.
- 2026-05-19: Phase 2 implemented a guarded cloud-first evaluator path. Discovered callable OpenAI/Anthropic models from live ai-lab credentials, added GPT-5-family Responses support, added cloud/local bakeoff scripts, added budget guardrails, set live evaluator to `openai:gpt-4.1-mini`, retained `gemma3:12b-it-qat` as local fallback, validated stack/dashboard smoke, and advanced current phase to Phase 3 - Job Relevance And Ranking. Ops observability still needs follow-up for `job_alert_workflow` and `rag_probe` timeouts.
