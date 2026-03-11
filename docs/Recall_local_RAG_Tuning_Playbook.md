# Recall.local RAG Tuning Playbook

Purpose: explain what was tuned in the RAG system, why it mattered, and where the implementation lives.

For manual validation through the dashboard UI, use:

- `/Users/jaydreyer/projects/recall-local/docs/Recall_local_RAG_UI_QA_Checklist.md`

## Scope

This project did not fine-tune model weights. It tuned the RAG system through:

1. corpus quality and ingestion behavior
2. retrieval scope and mode routing
3. prompt profiles
4. deterministic post-processing guardrails
5. reliability + eval automation

## 1) Corpus and ingestion tuning

### What changed

- Added source replacement controls for mutable content:
  - `replace_existing`
  - `source_key`
  - canonicalized `source_identity`
- Added DOCX extraction support.
- Added URL extraction fallbacks for difficult sites.
- Added batch manifest ingestion to avoid repetitive manual curl flows.
- Added corpus lane manifests:
  - job-search lane
  - learning lane

### Why

- Prevent stale versions from polluting retrieval.
- Reduce manual ingest errors.
- Keep ingestion reproducible and auditable.

### Files

- `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingestion_pipeline.py`
- `/Users/jaydreyer/projects/recall-local/scripts/phase2/ingest_job_search_manifest.py`
- `/Users/jaydreyer/projects/recall-local/scripts/phase2/job_search_manifest.jaydreyer.ai-lab.json`
- `/Users/jaydreyer/projects/recall-local/scripts/phase2/learning_manifest.genieincodebottle.ai-lab.json`

## 2) Retrieval scope and lane isolation

### What changed

- Added `filter_tags` support end-to-end in Workflow 02.
- Added domain lanes:
  - `job-search` for interview coaching corpus
  - `learning` + `genai-docs` for training material
- Added mode resolution fallback:
  - if `mode` is default/missing and tags imply a lane, route to the correct mode (`job-search` or `learning`).

### Why

- Improve citation relevance.
- Reduce cross-domain contamination.
- Make behavior resilient when upstream webhook payloads drop `mode`.

### Files

- `/Users/jaydreyer/projects/recall-local/scripts/phase1/retrieval.py`
- `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
- `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`

## 3) Prompt profile tuning

### What changed

- Added and refined profile prompts:
  - default: general cited RAG
  - job-search: coaching-oriented output constraints
  - learning: teaching/tradeoff-oriented output constraints

### Why

- Different tasks need different answer style and grounding.
- Keeps output useful without forking the pipeline.

### Files

- `/Users/jaydreyer/projects/recall-local/prompts/workflow_02_rag_answer.md`
- `/Users/jaydreyer/projects/recall-local/prompts/job_search_coach.md`
- `/Users/jaydreyer/projects/recall-local/prompts/learning_coach.md`

## 4) Deterministic guardrails

### What changed

- Low-confidence normalization to explicit abstention behavior.
- Job-search grounding injection when required terms are missing.
- Audit fields expanded to include mode/profile and postprocess notes.

### Why

- Small local models can drift in wording even when retrieval is correct.
- Deterministic guardrails preserve eval reliability.

### Files

- `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`

## 5) Reliability hardening

### What changed

- Embedding retries + backoff + prompt shrinking on Ollama 500s.
- Generation retries + backoff + configurable timeout.
- Scheduled eval retry-on-fail per suite before alerting.

### Why

- Reduce false regression alerts from transient runtime/model failures.
- Keep scheduled gates actionable.

### Files

- `/Users/jaydreyer/projects/recall-local/scripts/llm_client.py`
- `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`

## 6) Evaluation tuning and gates

### What changed

- Added domain eval suites:
  - job-search suite
  - learning suite
- Added scheduled execution for core + domain suites.
- Added required-term and required-tag assertions for domain outputs.

### Why

- Catch prompt/retrieval regressions early.
- Track quality per use case, not just global average behavior.

### Files

- `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
- `/Users/jaydreyer/projects/recall-local/scripts/eval/job_search_eval_cases.json`
- `/Users/jaydreyer/projects/recall-local/scripts/eval/learning_eval_cases.json`
- `/Users/jaydreyer/projects/recall-local/scripts/eval/scheduled_eval.sh`

## 6A) Current local model recommendation

As of the `2026-03-11` ai-lab bakeoff:

- keep `qwen2.5:7b-instruct` as the pinned live default
- do not promote `qwen3.5:9b` yet
- do not promote `gemma3:12b-it-qat` yet

Why:

- `qwen2.5:7b-instruct` remains the best quality/latency tradeoff in this stack
- `qwen3.5:9b` and `gemma3:12b-it-qat` were both materially slower and scored worse on the same RAG suite
- one `qwen2.5` bakeoff miss was a transient `Connection reset by peer`, not a stable answer-quality regression

Reference artifacts:

- bakeoff summary: `data/artifacts/evals/bakeoff/20260311T020312Z_summary.md`
- clean rerun on the restored default: `data/artifacts/evals/20260311T022400Z_8786f4ea80544b54b94e8c00da2c4b7b.md`

## 7) How to explain this in interviews

Short version:

- "We did system-level RAG tuning, not model fine-tuning."
- "We improved data hygiene, scoped retrieval with tags/modes, added profile prompts, then enforced output quality with deterministic guards and eval gates."
- "Reliability came from retries/backoff plus scheduled regression checks with alerting."

## 8) Operational quick checks

Job-search lane check:

```bash
python3 /home/jaydreyer/recall-local/scripts/eval/run_eval.py \
  --cases-file /home/jaydreyer/recall-local/scripts/eval/job_search_eval_cases.json \
  --backend webhook \
  --webhook-url http://100.116.103.78:5678/webhook/recall-query
```

Learning lane check:

```bash
python3 /home/jaydreyer/recall-local/scripts/eval/run_eval.py \
  --cases-file /home/jaydreyer/recall-local/scripts/eval/learning_eval_cases.json \
  --backend webhook \
  --webhook-url http://100.116.103.78:5678/webhook/recall-query
```

Scheduled all-suite check:

```bash
/home/jaydreyer/recall-local/scripts/eval/scheduled_eval.sh
```

## 9) Future tuning workflow

Use this order when quality drops:

1. reproduce with a specific query and save the JSON response
2. inspect `sources[]`, `audit.mode`, `audit.filter_tags`, `audit.fallback_used`
3. decide the failure type:
   - retrieval miss (wrong/missing sources)
   - generation style miss (good sources, weak wording)
   - runtime flake (timeouts/500s/fallbacks)
4. change one variable only
5. rerun targeted eval suite
6. keep or revert based on metrics

## 10) Tuning knobs by failure type

### Retrieval miss

- Adjust:
  - `top_k` (start 5 -> 8)
  - `min_score` (start 0.2 -> 0.15)
  - `filter_tags` correctness
  - `mode` correctness (`job-search` vs `learning`)
- Validate with:
  - one query dry-run to inspect `sources[]`
  - matching eval suite run

### Generation style miss

- Adjust:
  - prompt profile (`job_search_coach.md` or `learning_coach.md`)
  - deterministic guards in `/Users/jaydreyer/projects/recall-local/scripts/phase1/rag_query.py`
- Validate with:
  - required-term checks in eval output (`required_terms_ok`)

### Runtime flake

- Adjust:
  - `RECALL_GENERATE_RETRIES`
  - `RECALL_GENERATE_BACKOFF_SECONDS`
  - `RECALL_OLLAMA_GENERATE_TIMEOUT_SECONDS`
  - `RECALL_EMBED_RETRIES`
  - `RECALL_EMBED_BACKOFF_SECONDS`
- Validate with:
  - repeated suite runs (at least 2 back-to-back)
  - scheduled eval pass stability

## 11) Safe experiment protocol

1. Baseline:
   - run target suite and record pass/total + artifact path.
   - run the manual UI checklist if the change affects chat presentation, fallback handling, or user-visible answer quality
2. Apply one change.
3. Run target suite again.
4. Re-run the manual UI checklist for affected flows.
5. Compare:
   - pass rate
   - unanswerable correctness
   - latency
   - fallback frequency
6. Promote only if:
   - pass rate is same or better
   - no major latency regression
   - no increase in false-answer behavior

## 12) Rollback checklist

If a change hurts reliability:

1. revert the changed file(s)
2. sync to ai-lab
3. restart bridge if runtime code changed
4. rerun failing suite to confirm recovery
5. log the failed experiment in:
   - `/Users/jaydreyer/projects/recall-local/docs/IMPLEMENTATION_LOG.md`
