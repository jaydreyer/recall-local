# Recall.local — Phase 6C Implementation Brief: AI Evaluation

**Parent Document:** `docs/Recall_local_Phase6_Job_Hunt_PRD.md` (read first for full architecture)
**Phase:** 6C — AI Evaluation
**Est. Effort:** 2-3 days
**Dependencies:** Phase 6A (collections, endpoints, resume ingested), Phase 6B (jobs flowing in)

---

## Objective

Build the AI evaluation engine that scores every discovered job against Jay's resume, identifies skill gaps, recommends improvement actions, and routes manually-discovered jobs from the Chrome extension into the pipeline. After this phase: every job in the system has a fit score and gap analysis.

---

## Task 1: Evaluation Prompt Template (2-3 hours)

### The Prompt

```
You are a career advisor evaluating job fit. You will receive:
1. A job listing (title, company, description, requirements)
2. A candidate resume

Evaluate how well the candidate fits this role. Return ONLY valid JSON with no other text:

{
  "fit_score": <0-100>,
  "score_rationale": "<2-3 sentence summary of why this score>",
  "matching_skills": [
    {"skill": "<skill name>", "evidence": "<where in resume this appears>"}
  ],
  "gaps": [
    {
      "gap": "<missing skill or experience>",
      "severity": "critical|moderate|minor",
      "recommendations": [
        {
          "type": "course|project|video|certification|article",
          "title": "<specific suggestion>",
          "source": "<platform or URL if known>",
          "effort": "<estimated time to complete>"
        }
      ]
    }
  ],
  "application_tips": "<1-2 sentences on how to position the application>",
  "cover_letter_angle": "<the strongest narrative angle for a cover letter>"
}
```

### Testing the Prompt

Before wiring it into the pipeline, test it manually:

1. Load Jay's resume from `recall_resume` collection
2. Pick 3-5 real job descriptions from `recall_jobs` (from Phase 6B)
3. Send to Ollama via: `POST http://localhost:11434/api/generate` with model `llama3.2:3b`
4. Evaluate: Does the JSON parse? Are scores reasonable? Are gaps specific or generic?
5. Iterate on the prompt until results feel right

### Prompt Tuning Tips

- If scores are too high across the board: add "Be critical and honest. A score of 70+ means the candidate is a strong fit."
- If gaps are too vague: add "Be specific about what skills are missing. Don't say 'more experience needed' — say exactly what experience."
- If recommendations are generic: add "Recommend specific, real courses, certifications, or projects. Include platform names and estimated effort."

---

## Task 2: Job Evaluator Service (3-4 hours)

Create `scripts/phase6/job_evaluator.py`:

### Core Function

```python
async def evaluate_job(job_id: str, settings: LLMSettings) -> JobEvaluation:
    # 1. Load resume chunks from recall_resume
    resume_text = load_resume_text()
    
    # 2. Load job from recall_jobs
    job = load_job(job_id)
    
    # 3. Build prompt
    prompt = build_evaluation_prompt(job, resume_text)
    
    # 4. Call LLM
    if settings.evaluation_model == "local":
        response = call_ollama(prompt, model="llama3.2:3b")
    else:
        response = call_cloud(prompt, settings.cloud_provider, settings.cloud_model)
    
    # 5. Parse and validate JSON
    evaluation = parse_evaluation(response)
    
    # 6. Optional: auto-escalate to cloud
    if settings.auto_escalate and should_escalate(evaluation, settings):
        cloud_response = call_cloud(prompt, settings.cloud_provider, settings.cloud_model)
        evaluation = merge_evaluations(evaluation, parse_evaluation(cloud_response))
    
    # 7. Store evaluation in Qdrant (update job record)
    store_evaluation(job_id, evaluation)
    
    return evaluation
```

### JSON Validation & Retry

```python
def parse_evaluation(response_text: str) -> JobEvaluation:
    # Strip any markdown fences
    cleaned = response_text.strip().strip("```json").strip("```").strip()
    
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        raise MalformedResponseError("LLM returned invalid JSON")
    
    # Validate structure
    required_keys = ["fit_score", "score_rationale", "matching_skills", "gaps"]
    for key in required_keys:
        if key not in data:
            raise MalformedResponseError(f"Missing required key: {key}")
    
    # Validate score range
    if not (0 <= data["fit_score"] <= 100):
        raise MalformedResponseError(f"fit_score {data['fit_score']} out of range")
    
    return JobEvaluation(**data)
```

### Retry Logic

If the first attempt produces malformed JSON:
1. Retry once with a stricter prompt: prepend "IMPORTANT: Return ONLY a JSON object. No explanation, no markdown, no code fences."
2. If still malformed: store with `fit_score = -1`, `status = "error"`, flag for manual review

### Auto-Escalation Logic

```python
def should_escalate(evaluation: JobEvaluation, settings: LLMSettings) -> bool:
    if not settings.auto_escalate:
        return False
    if len(evaluation.gaps) < settings.escalate_threshold_gaps:
        return True  # Suspiciously few gaps — local model probably didn't try hard enough
    if len(evaluation.score_rationale.split()) < settings.escalate_threshold_rationale_words:
        return True  # Rationale too brief
    return False
```

### Observation Telemetry (non-scoring)

Persist an `observation` payload with each evaluated job and include it in evaluation-run responses. This is used for tuning and alert quality review without changing scoring thresholds:

- provider sequence (`local`, `cloud`, `local->cloud`)
- escalation trace (`enabled`, `triggered`, `reasons`)
- location diagnostics (`raw`, normalized `location_type`, `is_remote`, `is_twin_cities`, `preference_bucket`)
- evaluation settings snapshot (`evaluation_model`, escalation thresholds)

### LLM Provider Calls

**Ollama:**
```python
async def call_ollama(prompt: str, model: str = "llama3.2:3b") -> str:
    response = requests.post("http://localhost:11434/api/generate", json={
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 2000}
    })
    return response.json()["response"]
```

**Cloud (Anthropic):**
```python
async def call_cloud(prompt: str, provider: str, model: str) -> str:
    if provider == "anthropic":
        # Use existing Recall cloud provider logic with retry parity
        ...
    elif provider == "openai":
        ...
```

Use the same cloud provider retry logic that was built in Phase 5 (cloud provider retry parity).

### Model Recommendation Hierarchy

| Priority | Model | Cost | Use When |
|----------|-------|------|----------|
| 1 (default) | Ollama llama3.2:3b | Free | Daily bulk scoring |
| 2 (cloud default) | Claude Sonnet 4.5 | ~$0.01-0.03/eval | Gap analysis, recommendations |
| 3 (deep dive) | Claude Opus 4.5 | ~$0.05-0.15/eval | Top candidates, cover letters |
| 4 (alternative) | GPT-4o | ~$0.01-0.03/eval | If using existing OpenAI key |

---

## Task 3: Complete n8n Workflow 3 — Evaluate & Notify (3-4 hours)

Fill in the skeleton from Phase 6B. This is another guided build with Codex.

### Full Workflow Steps

```
1. [Webhook Trigger] — Receives { "job_ids": [...] }

2. [Load LLM Settings] — HTTP Request:
   GET /v1/llm-settings → get current model config

3. [Split Job IDs] — SplitInBatches: one job at a time

4. [Call Evaluation API] — HTTP Request:
   POST /v1/job-evaluation-runs with `{ "job_ids": ["..."], "wait": true, "settings": {...} }`
   (Use the same run endpoint for both single-job and batch execution)

5. [Wait] — 2 seconds between evaluations (give Ollama breathing room)

6. [Check Score Threshold] — IF node:
   If fit_score >= 75 → Notification path
   If fit_score >= 60 AND company_tier in [1,2] → Notification path
   Else → Skip notification

7. [Send Telegram] — HTTP Request (notification path only):
   POST https://api.telegram.org/bot{token}/sendMessage
   Body: formatted job alert message (see parent PRD Component 5)

8. [Log Evaluation] — Code node:
   Summary: "Evaluated {N} jobs. Scores: {min}-{max}. {H} high-fit notifications sent."
```

### New Bridge Endpoint

`POST /v1/job-evaluation-runs` — run resource endpoint used for both single-job and batch evaluation.

- Single job: `job_ids` length = 1 and `wait=true`
- Batch: `job_ids` length > 1 and `wait=false`

---

## Task 4: Gap Aggregation Service (2 hours)

Create `scripts/phase6/gap_aggregator.py`:

### Logic

1. Query all jobs in `recall_jobs` with `status = "evaluated"` and `fit_score > 0`
2. Extract all `gaps` arrays
3. Group by gap name (fuzzy — "Kubernetes experience" and "K8s / container orchestration" should merge)
4. Count frequency of each gap
5. Average the severity ratings
6. Collect the top recommendations across all instances
7. Return sorted by frequency (most common gaps first)

### Fuzzy Gap Merging

Use embedding similarity to group gaps that mean the same thing:

```python
def merge_similar_gaps(gaps: list[dict]) -> list[dict]:
    # Embed each gap description
    # Cluster by similarity > 0.85
    # Use the most common phrasing as the canonical name
    # Sum frequencies, average severities, collect unique recommendations
    ...
```

This powers the `GET /v1/job-gaps` endpoint (already defined in 6A).

---

## Task 5: Chrome Extension → Job Pipeline Hook (2 hours)

### Bridge Hook Logic

In the existing ingestion pipeline (`scripts/phase1/ingest_bridge_api.py`), add a post-ingestion hook:

```python
JOB_URL_PATTERNS = [
    "linkedin.com/jobs", "indeed.com/viewjob", "lever.co", "greenhouse.io",
    "boards.greenhouse.io", "jobs.ashbyhq.com", "wellfound.com/jobs",
    "careers.", "/careers/", "/jobs/", "workday.com"
]

async def post_ingestion_hook(url: str, group: str, tags: list, chunks: list):
    """Called after standard document ingestion completes."""
    if group == "job-search" and any(pattern in url for pattern in JOB_URL_PATTERNS):
        # This looks like a job posting — route to job pipeline
        job_data = await extract_job_metadata(chunks)
        job_id = await store_job(job_data, source="chrome_extension", url=url)
        await queue_evaluation([job_id])
```

### Job Metadata Extraction

Create `scripts/phase6/job_metadata_extractor.py`:

When a job is ingested via Chrome extension (raw page content, not structured API), extract metadata using Ollama:

```
Extract the following from this job posting. Return ONLY valid JSON:
{
  "title": "<job title>",
  "company": "<company name>",
  "location": "<location or Remote>",
  "location_type": "<remote|hybrid|onsite>",
  "description": "<full job description text>",
  "salary_min": <number or null>,
  "salary_max": <number or null>
}
```

### UX Flow (from Jay's perspective)

1. See interesting job on LinkedIn/Greenhouse/etc.
2. Click Chrome extension → group auto-selects "Job Search" (existing behavior)
3. Click "Send to Recall" (existing behavior)
4. **Invisible:** Bridge hook detects job URL pattern, extracts metadata, stores in `recall_jobs`, queues evaluation
5. Job appears on Daily Dashboard within minutes
6. If score >= 75, Telegram notification fires

Nothing changes in Jay's workflow — the intelligence layer is invisible.

---

## Testing

1. **Evaluate 5 real jobs** manually via the API — verify JSON parses, scores feel right
2. **Test retry logic** — send a prompt that might produce bad JSON, verify retry works
3. **Test auto-escalation** — set threshold low, verify cloud is called when local output is thin
4. **Test gap aggregation** — with 10+ evaluated jobs, verify `/v1/job-gaps` returns meaningful data
5. **Test Chrome extension hook** — ingest a LinkedIn job URL via Chrome extension, verify it appears in `recall_jobs`
6. **Test Telegram notification** — trigger evaluation on a high-scoring job, verify notification arrives

---

## Definition of Done

- [ ] Evaluation prompt produces consistent, parseable JSON from Ollama
- [ ] Fit scores feel reasonable on a manual review of 10+ jobs
- [ ] Retry logic handles malformed JSON gracefully
- [ ] Cloud fallback works when toggled on
- [ ] Auto-escalation correctly detects thin local responses
- [ ] n8n Workflow 3 is fully wired: evaluate → notify
- [ ] Telegram notifications fire for high-scoring jobs in preferred-location buckets
- [ ] Gap aggregation returns ranked, deduplicated gaps
- [ ] Chrome extension ingestion routes job-tagged URLs to the job pipeline
- [ ] Job metadata extraction works for LinkedIn, Greenhouse, and Indeed pages

---

## Files Created/Modified

| File | Action |
|------|--------|
| `scripts/phase6/job_evaluator.py` | CREATE |
| `scripts/phase6/gap_aggregator.py` | CREATE |
| `scripts/phase6/job_metadata_extractor.py` | CREATE |
| `scripts/phase6/telegram_notifier.py` | CREATE |
| `scripts/phase1/ingest_bridge_api.py` | MODIFY (evaluation + post-ingestion hooks) |
| `n8n/workflows/phase6/workflow3_evaluate_notify.md` | MODIFY (full implementation notes) |
