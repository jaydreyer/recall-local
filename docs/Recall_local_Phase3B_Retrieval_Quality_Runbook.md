# Recall.local - Phase 3B Retrieval Quality Runbook

Purpose: run retrieval quality experiments with optional hybrid retrieval, optional reranker, and optional semantic eval scoring while keeping default Workflow 02 behavior stable.

## What shipped in this slice

1. Retrieval lane controls in Workflow 02:
   - `retrieval_mode`: `vector` (default) or `hybrid`
   - `hybrid_alpha`: dense/sparse fusion weight
   - `enable_reranker`: optional heuristic reranker
   - `reranker_weight`: lexical reranker blend weight
2. Eval harness controls:
   - global retrieval overrides (`--retrieval-mode`, `--hybrid-alpha`, `--enable-reranker`, `--reranker-weight`)
   - optional semantic scoring lane for cases with `expected_answer`
3. Phase 3B experiment scripts:
   - `<repo-root>/scripts/eval/run_phase3b_retrieval_experiment.sh`
   - `<repo-root>/scripts/phase3/run_retrieval_experiment_now.sh`
4. Versioned golden set starter:
   - `<repo-root>/scripts/eval/golden_sets/learning_golden_v1.json`

## Workflow 02 retrieval controls

Payload fields (CLI/webhook):

```json
{
  "query": "Your question",
  "retrieval_mode": "hybrid",
  "hybrid_alpha": 0.65,
  "enable_reranker": true,
  "reranker_weight": 0.35
}
```

Reference payload file:

- `<repo-root>/n8n/workflows/payload_examples/rag_query_hybrid_payload_example.json`

Defaults remain unchanged unless you opt in:

- `retrieval_mode=vector`
- reranker disabled

## Run one candidate query (manual)

```bash
<repo-root>/scripts/phase3/run_query_mode_now.sh \
  --mode learning \
  --retrieval-mode hybrid \
  --hybrid-alpha 0.65 \
  --enable-reranker true \
  --reranker-weight 0.35
```

## Run baseline vs candidate experiment

```bash
<repo-root>/scripts/phase3/run_retrieval_experiment_now.sh
```

Default experiment behavior:

- baseline: `vector`
- candidate: `hybrid + reranker`
- cases file: `scripts/eval/golden_sets/learning_golden_v1.json`
- output dir: `data/artifacts/evals/phase3b/`

## Optional semantic scoring lane

Semantic scoring is optional and only applies to cases that include `expected_answer`.

Enable in experiment:

```bash
RECALL_PHASE3B_SEMANTIC_SCORE=true \
RECALL_PHASE3B_SEMANTIC_MIN_SCORE=0.65 \
<repo-root>/scripts/phase3/run_retrieval_experiment_now.sh
```

To enforce semantic threshold as pass/fail in direct eval runs:

```bash
python3 <repo-root>/scripts/eval/run_eval.py \
  --cases-file <repo-root>/scripts/eval/golden_sets/learning_golden_v1.json \
  --backend webhook \
  --webhook-url http://localhost:5678/webhook/recall-query \
  --semantic-score \
  --semantic-min-score 0.65 \
  --enforce-semantic-score
```

## Evidence artifacts

Each experiment run writes:

1. baseline eval JSON summary
2. candidate eval JSON summary
3. comparison Markdown summary with pass-rate and latency deltas
