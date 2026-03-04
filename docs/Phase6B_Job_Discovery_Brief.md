# Recall.local — Phase 6B Implementation Brief: Job Discovery

**Parent Document:** `docs/Recall_local_Phase6_Job_Hunt_PRD.md` (read first for full architecture)
**Phase:** 6B — Job Discovery
**Est. Effort:** 3-4 days
**Dependencies:** Phase 6A complete (Qdrant collections, config files, bridge endpoints)
**Build Style:** Guided — Codex walks Jay through building n8n workflows step by step

---

## Objective

Build three n8n workflows that automatically discover jobs from aggregator APIs and target company career pages, deduplicate them, and store them in Qdrant. After this phase: jobs are flowing into the system on an automated schedule.

---

## Important: Guided Build Approach

Jay wants to understand how these workflows work, not just have them generated. For each workflow:

1. **Explain** the overall structure and what each node does before building
2. **Walk through** creating each node step by step in the n8n UI
3. **Provide** the configuration for each node (HTTP headers, code blocks, expressions)
4. **Help debug** and test as you go
5. **Do NOT** just dump a workflow JSON import

---

## Workflow 1: Job Board Aggregator

**Trigger:** Cron schedule, every 8 hours (6 AM, 2 PM, 10 PM)

### Data Sources

#### Source 1: JobSpy (Primary)

Python library that scrapes Indeed, LinkedIn, Glassdoor, and ZipRecruiter.

- **Execution model:** Run in bridge-side Python (`scripts/phase6/job_discovery_runner.py`) and trigger from n8n via `POST /v1/job-discovery-runs`
- **Runtime constraint:** n8n on ai-lab does not have `python3`, so do not execute JobSpy in n8n nodes
- **Install:** `pip install python-jobspy` in the bridge runtime image/environment
- **Rate limit:** 2-3 second delays between searches
- **Query strategy:** One search per target title × location combo

**Search matrix:** Iterate through titles from `config/job_search.json` × locations. Don't run all combos every cycle — rotate through them to stay under rate limits.

#### Source 2: Adzuna API (Secondary)

Free tier: 250 requests/month.

- **n8n node type:** HTTP Request
- **Endpoint:** `https://api.adzuna.com/v1/api/jobs/us/search/1`
- **Auth:** Query params `app_id` and `app_key` from env vars
- **Key params:** `what` (title), `where` (location), `max_days_old=7`
- **Returns:** `results[]` with title, company, location, description, redirect_url, created, salary_min, salary_max

#### Source 3: SerpAPI Google Jobs (Tertiary)

Free tier: 100 searches/month. Use sparingly.

- **n8n node type:** HTTP Request
- **Endpoint:** `https://serpapi.com/search?engine=google_jobs`
- **Key params:** `q` (search query), `location`, `api_key`
- **Returns:** `jobs_results[]` with title, company_name, location, description, apply_options

### Workflow Steps (n8n node sequence)

```
1. [Schedule Trigger] — Cron: 0 6,14,22 * * *

2. [Load Config] — Code node: Read config/job_search.json
   Output: Array of {title, location} search combos

3. [Trigger Discovery Run] — HTTP Request:
   POST /v1/job-discovery-runs
   Payload includes source selection + search combos from config
   Bridge-side runner performs:
   - Source querying (JobSpy/Adzuna/SerpAPI)
   - Normalization to canonical job schema
   - Deduplication (`/v1/job-deduplications`)
   - Company tier tagging
   - Storage in `recall_jobs`

4. [Collect New Job IDs] — Code node:
   Extract `new_job_ids` from discovery-run response

5. [Trigger Evaluation] — HTTP Request:
   POST /v1/job-evaluation-runs with `{ "job_ids": [...], "wait": false }`
   (This calls Workflow 3 — built in Phase 6C)

6. [Log Summary] — Code node:
    Record n8n execution summary and persist bridge response metrics:
    "Discovered {N} new jobs, {M} duplicates skipped from {source}"
```

### New Bridge Endpoint Needed

`POST /v1/job-deduplications` — accepts a URL and optionally a description, checks Qdrant for duplicates using both exact URL match and semantic similarity. Returns `{ "is_duplicate": bool, "similar_job_id": string|null }`.

Add this to `scripts/phase6/job_dedup.py` and call it from `scripts/phase1/ingest_bridge_api.py`.

---

## Workflow 2: Career Page Monitor

**Trigger:** Cron schedule, every 12 hours (7 AM, 7 PM)

### ATS Platform Handlers

Most target companies use one of three platforms:

**Greenhouse** (Anthropic, OpenAI, Cohere, Writer, Postman, Aisera, others):
```
GET https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs
Response: { "jobs": [{ "id": N, "title": "...", "location": {...}, "absolute_url": "..." }] }
```

**Lever** (some startups):
```
GET https://api.lever.co/v0/postings/{company}
Response: [{ "text": "title", "categories": {...}, "hostedUrl": "..." }]
```

**Workday** (Target, UHG, 3M, Medtronic, Best Buy):
Harder — use keyword search URL + HTML parsing. Lower priority.

### Workflow Steps

```
1. [Schedule Trigger] — Cron: 0 7,19 * * *

2. [Load Company Configs] — Code node:
   Read config/career_pages.json
   Output: Array of company objects

3. [Split Into Batches] — One company at a time

4. [Route by ATS] — Switch node on company.ats:
   4a. [Greenhouse API] — HTTP Request: GET boards-api.greenhouse.io/v1/boards/{board_id}/jobs
   4b. [Lever API] — HTTP Request: GET api.lever.co/v0/postings/{company}
   4c. [Workday/Other] — HTTP Request + HTML Extract node

5. [Filter by Title] — Code node:
   Fuzzy match job titles against company.title_filter array
   Include partial matches: "Senior Solutions Engineer" matches "solutions"
   Include: "Sr.", "Staff", "Principal", "Lead" prefixes

6. [Normalize] — Same normalization as Workflow 1
   Set source: "career_page"
   Set company_tier from config

7. [Deduplicate] — Same dedup as Workflow 1

8. [Store in Qdrant] — Same storage as Workflow 1

9. [Trigger Evaluation] — POST /v1/job-evaluation-runs

10. [Log Summary] — "{company}: {N} new jobs found, {M} existing"
```

### Wait/Rate Limit Between Companies

Add a 2-second wait between company API calls to be respectful. Greenhouse and Lever don't require auth keys for their public boards API, but don't hammer them.

---

## Workflow 3: Evaluate & Notify (Skeleton)

**Note:** The full evaluation logic is built in Phase 6C. In this phase, create the workflow skeleton so Workflows 1 and 2 have something to call.

**Trigger:** Webhook (called by Workflows 1 and 2)

### Skeleton Steps

```
1. [Webhook Trigger] — Receives { "job_ids": [...] }

2. [Placeholder: Load Resume] — (implemented in 6C)

3. [Placeholder: Evaluate Each Job] — (implemented in 6C)
   For now: set fit_score = -1, status = "new"

4. [Placeholder: Notification Check] — (implemented in 6C/6D)

5. [Log] — "Received {N} jobs for evaluation (evaluation engine not yet active)"
```

This ensures end-to-end flow works: Workflow 1/2 discover jobs → store → call Workflow 3 → jobs appear in Qdrant with status "new."

---

## Deduplication Service

Create `scripts/phase6/job_dedup.py`:

### Dedup Logic

1. **Exact URL match:** Query Qdrant `recall_jobs` where `url == incoming_url`. If found → duplicate.
2. **Semantic similarity:** Embed the incoming job description, query Qdrant for nearest neighbors with similarity > 0.92. If found → duplicate (likely a repost with slightly different text).
3. **Company + title match within 7 days:** If same normalized company + same title posted within 7 days → likely duplicate even if URL differs.

### Dedup Endpoint

```python
@app.post("/v1/job-deduplications")
async def check_duplicate(request: DedupRequest):
    # 1. Check exact URL
    url_match = qdrant_client.scroll(
        collection_name="recall_jobs",
        scroll_filter={"must": [{"key": "url", "match": {"value": request.url}}]},
        limit=1
    )
    if url_match[0]:
        return {"is_duplicate": True, "reason": "exact_url", "similar_job_id": url_match[0][0].id}
    
    # 2. Check semantic similarity
    embedding = embed_text(request.description)
    similar = qdrant_client.search(
        collection_name="recall_jobs",
        query_vector=embedding,
        limit=1,
        score_threshold=0.92
    )
    if similar:
        return {"is_duplicate": True, "reason": "semantic", "similar_job_id": similar[0].id}
    
    return {"is_duplicate": False}
```

---

## Testing

After building all workflows:

1. **Manual trigger** Workflow 1 — verify jobs appear in Qdrant
2. **Manual trigger** Workflow 2 — verify career page jobs appear
3. **Check dedup** — trigger again, verify duplicates are skipped
4. **Check logs** — verify SQLite activity entries
5. **Check Qdrant** — verify job payloads have correct schema
6. **Verify** the evaluation webhook fires (even though it's a skeleton)

---

## Definition of Done

- [ ] Workflow 1 (Job Board Aggregator) runs on schedule and stores jobs
- [ ] Workflow 2 (Career Page Monitor) runs on schedule and stores jobs
- [ ] Workflow 3 skeleton exists and is callable
- [ ] Deduplication works (URL + semantic + company/title)
- [ ] At least one source per workflow produces real results
- [ ] Jobs appear in Qdrant with correct schema
- [ ] Activity log records discovery summaries
- [ ] Rate limits are respected (delays between API calls)
- [ ] Jay understands how each workflow works (guided build)

---

## Files Created/Modified

| File | Action |
|------|--------|
| `scripts/phase6/job_dedup.py` | CREATE |
| `scripts/phase6/job_discovery_runner.py` | CREATE |
| `n8n/workflows/phase6/README.md` | CREATE |
| `n8n/workflows/phase6/workflow1_aggregator.md` | CREATE (build notes from guided session) |
| `n8n/workflows/phase6/workflow2_career_pages.md` | CREATE (build notes from guided session) |
| `n8n/workflows/phase6/workflow3_evaluate_notify.md` | CREATE (skeleton notes) |
| `scripts/phase1/ingest_bridge_api.py` | MODIFY (add `/v1/job-deduplications` and `/v1/job-discovery-runs`) |
