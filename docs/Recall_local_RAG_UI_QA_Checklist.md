# Recall.local RAG UI QA Checklist

Purpose: provide a repeatable manual validation pass for the `Recall Chat` UI after RAG, prompt, model, or dashboard changes, plus a matching scripted smoke suite for the same core behaviors.

Use this checklist after:

- retrieval changes
- prompt/profile changes
- model changes
- output validation changes
- dashboard chat UI changes

## Test goals

The chat UI should do these jobs well:

1. summarize a specific named document
2. answer general compare questions across multiple documents
3. synthesize guidance from multiple documents with tradeoffs
4. answer precise targeted questions from a named source
5. abstain cleanly when the corpus does not support the answer

## Environment notes

- Use the live `Recall Chat` UI against the current `ai-lab` stack.
- Before a manual UI pass, run the scripted smoke suite when retrieval/generation behavior changed:
  - `/Users/jaydreyer/projects/recall-local/scripts/eval/run_chat_quality_smoke.sh`
- For learning/PDF cases, set:
  - `Tag Filter`: `learning,genai-docs`
  - `Tag Match`: `all (AND)`
- Leave `Group Filter` empty unless a test case explicitly needs it.

## Core UI test set

The first 6 prompts below are the canonical manual pass. The scripted smoke suite extends that set with additional explanatory and learning-doc cases.

### 1) Specific article summary

Prompt:

```text
Summarize the article "The New Skill in AI is Not Prompting, It's Context Engineering" for me. Give me highlights as bullet points.
```

Pass criteria:

- answer is clearly bulleted
- cited source cards include the Phil Schmid article
- answer is more than a one-sentence paraphrase
- answer reflects the named article, not adjacent AI documents

### 2) Specific PDF summary

Prompt:

```text
Summarize the document "Vector Embeddings Guide" as a practical bulleted cheat sheet.
```

Pass criteria:

- answer is clearly bulleted
- cited source cards include `Vector Embeddings Guide`
- answer contains practical guidance, not just a generic definition of embeddings

### 3) Cross-document comparison

Prompt:

```text
How is prompt engineering different than context engineering? Give examples, if possible.
```

Pass criteria:

- answer compares the two concepts directly
- citation cards show at least 2 relevant sources
- examples are included or the answer clearly explains the distinction with concrete scenarios

### 4) Cross-document synthesis

Prompt:

```text
What are practical ways to reduce latency in multi-agent systems, and what tradeoffs should I expect in RAG design?
```

Pass criteria:

- answer combines ideas from more than one source
- citation cards show at least 2 relevant sources
- answer mentions tradeoffs, not only tactics

### 5) Targeted factual lookup

Prompt:

```text
According to the article "The New Skill in AI is Not Prompting, It's Context Engineering", what is the main bottleneck in building useful LLM systems?
```

Pass criteria:

- answer is specific and source-grounded
- citations point to the named article
- answer is concise but still clearly tied to the article’s claim

### 6) Abstention / unsupported answer

Prompt:

```text
What is the exact private API key currently configured for the production LLM provider?
```

Pass criteria:

- answer explicitly states that the system does not have enough grounded information
- citations do not pretend to support a secret value
- no fabricated key or guessed secret appears

## UI-specific checks

For each response, verify:

- the answer shape matches the request shape
- source cards match the answer being given
- the diagnostic chips are reasonable:
  - `strategy=...`
  - `model=...`
  - `latency=...`
  - `attempts=...`
  - `profile=...`
- if a fallback path was used, the fallback banner is visible and the answer is still useful and source-grounded

## Scoring rubric

- `Pass`: right source selection, useful answer, correct format, and multi-doc questions cite at least 2 distinct sources
- `Soft fail`: mostly right sources, but answer is too thin, too generic, or weakly formatted
- `Hard fail`: wrong source, fabricated answer, one-doc answer for a multi-doc question, or abstention when the cited corpus clearly contains the answer

## Regression workflow

1. Run the 6 prompts above in the UI.
2. Record any `Soft fail` or `Hard fail`.
3. If the UI looks wrong, compare the answer against a direct API run and inspect audit metadata.
4. If behavior changed after a code change, rerun the scripted bakeoff:
   - `scripts/eval/run_chat_quality_smoke.sh`
   - `scripts/eval/run_eval.py`
   - `scripts/eval/run_rag_model_bakeoff.sh`
5. Keep the current live default pinned unless the bakeoff shows a clear quality gain without unacceptable latency.

## Known benchmark reference

Current recommended reference points:

- latest passing standard rerun on the pinned live default:
  - `data/artifacts/evals/20260311T022400Z_8786f4ea80544b54b94e8c00da2c4b7b.md`
- latest three-model bakeoff summary:
  - `data/artifacts/evals/bakeoff/20260311T020312Z_summary.md`
