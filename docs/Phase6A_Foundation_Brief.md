# Recall.local — Phase 6A Implementation Brief: Foundation

**Parent Document:** `docs/Recall_local_Phase6_Job_Hunt_PRD.md` (read first for full architecture)
**Phase:** 6A — Foundation
**Est. Effort:** 3-4 days
**Dependencies:** Phase 5 complete (FastAPI bridge, Qdrant, Docker Compose running)

---

## Objective

Stand up the data layer and API skeleton for job hunt intelligence. After this phase: Qdrant has two new collections, the bridge has new endpoints, Jay's resume is ingested, and the Daily Dashboard scaffold is running in Docker.

---

## Task 1: Create Qdrant Collections (1 hour)

Create a setup script at `scripts/phase6/setup_collections.py` that creates two new collections.

### `recall_jobs` Collection

```json
{
  "collection_name": "recall_jobs",
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "payload_schema": {
    "title": "keyword",
    "company": "keyword",
    "company_normalized": "keyword",
    "company_tier": "integer",
    "location": "keyword",
    "location_type": "keyword",
    "url": "keyword",
    "source": "keyword",
    "description": "text",
    "salary_min": "integer",
    "salary_max": "integer",
    "date_posted": "datetime",
    "discovered_at": "datetime",
    "evaluated_at": "datetime",
    "search_query": "keyword",
    "status": "keyword",
    "fit_score": "integer",
    "score_rationale": "text",
    "matching_skills": "json",
    "gaps": "json",
    "application_tips": "text",
    "cover_letter_angle": "text",
    "observation": "json",
    "applied": "bool",
    "applied_at": "datetime",
    "notes": "text",
    "dismissed": "bool"
  }
}
```

**Status values:** `new` → `evaluated` → `applied` | `dismissed` | `expired` | `error`

### `recall_resume` Collection

```json
{
  "collection_name": "recall_resume",
  "vectors": {
    "size": 768,
    "distance": "Cosine"
  },
  "payload_schema": {
    "chunk_text": "text",
    "section": "keyword",
    "version": "integer",
    "ingested_at": "datetime"
  }
}
```

The script should be idempotent — skip creation if collections already exist.

---

## Task 2: FastAPI Endpoints (3-4 hours)

**IMPORTANT:** Follow Jay's existing API design skill in Codex for all naming conventions, documentation standards, error response formats, and versioning. All Phase 6 endpoints must be consistent with Phases 0-5.

### Bridge Implementation Location

Implement Phase 6 bridge routes in `scripts/phase1/ingest_bridge_api.py` (existing FastAPI app) and place new supporting logic in `scripts/phase6/`.

### Endpoints to Implement

| Method | Path | Purpose | Response |
|--------|------|---------|----------|
| `GET` | `/v1/jobs` | List jobs with filtering, sorting, pagination | Array of job objects |
| `GET` | `/v1/jobs/{jobId}` | Single job with full evaluation | Job object |
| `POST` | `/v1/job-evaluation-runs` | Create evaluation run(s) for one or more job IDs | Run metadata (`queued`,`run_id`,`status`,`job_ids`) plus `results` when `wait=true` |
| `GET` | `/v1/job-stats` | Dashboard stats (counts by score range, source, day) | Stats object |
| `GET` | `/v1/job-gaps` | Aggregated gap analysis across all evaluated jobs | Gaps object |
| `POST` | `/v1/job-deduplications` | Deduplication check for candidate job payload | Dedup result |
| `POST` | `/v1/job-discovery-runs` | Trigger discovery pipeline run | Run summary |
| `PATCH` | `/v1/jobs/{jobId}` | Update job status (applied, dismissed, notes) | Updated job |
| `POST` | `/v1/resumes` | Ingest/update resume | `{ "version": N, "chunks": N }` |
| `GET` | `/v1/resumes/current` | Resume metadata | `{ "version": N, "ingested_at": "...", "chunks": N }` |
| `GET` | `/v1/companies` | List company profiles | Array of company objects |
| `GET` | `/v1/companies/{companyId}` | Single company profile with jobs | Company object |
| `POST` | `/v1/company-profile-refresh-runs` | Trigger company profile refresh | Run result |
| `PATCH` | `/v1/llm-settings` | Update LLM configuration | Updated settings |
| `GET` | `/v1/llm-settings` | Current LLM configuration | Settings object |

### `GET /v1/jobs` Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `evaluated` | Filter: new, evaluated, applied, dismissed, expired, error |
| `min_score` | int | 0 | Minimum fit score (`-1` includes unevaluated/unscored jobs) |
| `max_score` | int | 100 | Maximum fit score |
| `company_tier` | int | null | Filter by company tier (1, 2, 3) |
| `source` | string | null | Filter by source (jobspy, adzuna, serpapi, career_page, chrome_extension) |
| `title_query` | string | null | Fuzzy title search |
| `sort` | string | `fit_score` | Sort field: fit_score, discovered_at, company |
| `order` | string | `desc` | Sort order: asc, desc |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Pagination offset |

### `GET /v1/job-gaps` Response Shape

See parent PRD Component 3 for the full aggregated gap analysis response. This is one of the most important endpoints — it answers "what should I study?"

### Job Observation Payload (stored + returned)

Each evaluated job includes `observation` telemetry for non-scoring diagnostics:

```json
{
  "provider_sequence": "local|cloud|local->cloud",
  "escalation": {
    "enabled": true,
    "triggered": false,
    "reasons": ["gaps_below_threshold", "rationale_too_short"]
  },
  "location": {
    "raw": "Minneapolis, MN, US",
    "location_type": "remote|hybrid|onsite",
    "is_remote": false,
    "is_twin_cities": true,
    "preference_bucket": "remote|twin_cities|other"
  },
  "settings_snapshot": {
    "evaluation_model": "local",
    "auto_escalate": true,
    "escalate_threshold_gaps": 2,
    "escalate_threshold_rationale_words": 20
  }
}
```

### `PATCH /v1/llm-settings` Request Body

```json
{
  "evaluation_model": "local",
  "cloud_provider": "anthropic",
  "cloud_model": "claude-sonnet-4-5-20250929",
  "auto_escalate": true,
  "escalate_threshold_gaps": 2,
  "escalate_threshold_rationale_words": 20
}
```

Store in SQLite `settings` table so it persists across restarts.

---

## Task 3: Resume Ingestion (1-2 hours)

### `POST /v1/resumes`

Accepts Jay's resume in markdown or PDF format. Process:

1. Clear existing `recall_resume` collection (previous version)
2. Chunk the document using the same chunking logic as `recall_docs`
3. Embed chunks using the same embedding model (nomic-embed-text)
4. Store in `recall_resume` with `version` incremented, `section` derived from headings
5. Log to SQLite activity

### CLI Script: `scripts/phase6/ingest_resume.py`

A convenience script for command-line ingestion:

```bash
python scripts/phase6/ingest_resume.py --file ~/resume.md
```

**Action item after implementation:** Ingest Jay's current resume (the one from the career project) so it's available for evaluation testing in Phase 6C.

---

## Task 4: Configuration Files (1 hour)

### `config/career_pages.json`

```json
{
  "companies": [
    {
      "name": "Anthropic",
      "tier": 2,
      "ats": "greenhouse",
      "board_id": "anthropic",
      "url": "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs",
      "title_filter": ["solutions", "engineer", "architect", "technical", "account", "sales"],
      "your_connection": "Daily Claude user. Built production apps with Claude Code. Recall.local uses Anthropic API."
    },
    {
      "name": "OpenAI",
      "tier": 2,
      "ats": "greenhouse",
      "board_id": "openai",
      "url": "https://boards-api.greenhouse.io/v1/boards/openai/jobs",
      "title_filter": ["solutions", "engineer", "architect", "sales"],
      "your_connection": "ChatGPT Champion at Gap. Built custom GPTs replacing $50K/year enterprise tools."
    },
    {
      "name": "Postman",
      "tier": 1,
      "ats": "greenhouse",
      "board_id": "postman",
      "url": "https://boards-api.greenhouse.io/v1/boards/postman/jobs",
      "title_filter": ["solutions", "engineer", "architect"],
      "your_connection": "API governance expert from Target (225+ API catalog). Postman power user."
    },
    {
      "name": "Aisera",
      "tier": 1,
      "ats": "greenhouse",
      "board_id": "aisera",
      "url": "https://boards-api.greenhouse.io/v1/boards/aisera/jobs",
      "title_filter": ["solutions", "engineer", "sales", "architect"],
      "your_connection": "Managed Aisera chatbot at Gap, drove 75% resolution rate. Was their customer."
    },
    {
      "name": "Target",
      "tier": 3,
      "ats": "workday",
      "url": "https://jobs.target.com/search-jobs",
      "title_filter": ["solutions", "architect", "ai", "developer experience"],
      "your_connection": "16 years at Target. Built API governance program, 225+ API catalog, developer portal."
    }
  ]
}
```

Add the remaining companies from the target list in the parent PRD. Check each company's actual ATS platform and populate the correct API URL.

### `config/job_search.json`

```json
{
  "search_titles": [
    "Solutions Engineer",
    "Solutions Architect",
    "Sales Engineer",
    "Technical Account Manager",
    "AI Solutions Consultant",
    "AI Enablement Lead",
    "Technical Program Manager",
    "Developer Relations",
    "Enterprise AI Strategist",
    "Artificial Intelligence Consultant"
  ],
  "search_locations": [
    "Remote",
    "Minneapolis, MN",
    "Twin Cities, MN",
    "Minnesota"
  ],
  "search_keywords": [
    "AI", "SaaS", "API", "developer tools", "enterprise software"
  ],
  "score_thresholds": {
    "high_fit": 75,
    "medium_fit": 50,
    "low_fit": 25
  },
  "notification_rules": {
    "push_min_score": 75,
    "push_target_company_min_score": 60,
    "target_company_tiers": [1, 2]
  },
  "schedule": {
    "aggregator_interval_hours": 8,
    "career_page_interval_hours": 12
  },
  "dedup_similarity_threshold": 0.92
}
```

---

## Task 5: Daily Dashboard Scaffold (2-3 hours)

### Setup

Create `ui/daily-dashboard/` as a new React/Vite app with its own Dockerfile.

**Tech stack:**
- React 18 + Vite
- Tailwind CSS (or inline styles matching the design system)
- Recharts (for charts)

### Design System: Atelier Ops / Luxury Minimal

**CRITICAL:** This dashboard uses a DIFFERENT theme than the Recall.local ops dashboard. A reference artifact exists at `docs/scaffolds/luxury-minimal.jsx` — study it carefully. Key tokens:

- Background: `#FAFAF7` (warm off-white)
- Primary text: `#2A2520` (deep warm charcoal)
- Secondary text: `#8F8578` (muted stone)
- Tertiary: `#B8AD9E` (light taupe)
- Accent: `#E8553A` (burnt orange-red)
- Status: Active `#E8553A`, Queued `#A0916B`, Complete `#6B8F71`
- Borders: `#E8E2D8` (warm linen), 1px
- Headings: Playfair Display (serif)
- Body: Manrope (sans-serif)
- Mono: IBM Plex Mono (timestamps, scores, data labels)
- Section headers: 10-12px, uppercase, letter-spacing 2-3px

### Scaffold Requirements

- Basic app shell with header (time, date, "Daily Dashboard" title)
- Placeholder tabs/sections for: Jobs, Companies, Skill Gaps, Settings
- Future widget slots for: Weather, Calendar, News, Sports
- API connection to the Recall bridge (configurable base URL + API key)
- Docker container (nginx serving static Vite build)
- Add to `docker/docker-compose.yml` as `daily-dashboard` service on port 3001

The scaffold doesn't need real data yet — mock data is fine. The goal is to have the container running, the theme applied, and the layout established so Phase 6D can fill it in.

---

## Environment Variables

Add to `docker/.env.example`:

```bash
# Job Search Configuration
RECALL_JOBS_ENABLED=true
RECALL_JOBS_CLOUD_FALLBACK=false
RECALL_JOBS_CLOUD_PROVIDER=anthropic
RECALL_JOBS_CLOUD_MODEL=claude-sonnet-4-5-20250929

# Job Source API Keys (populate in Phase 6B)
ADZUNA_APP_ID=
ADZUNA_API_KEY=
SERPAPI_KEY=

# Notifications (reuse existing Arthur/OpenClaw Telegram bot)
RECALL_TELEGRAM_BOT_TOKEN=your_existing_bot_token
RECALL_TELEGRAM_CHAT_ID=your_chat_id

# Daily Dashboard
RECALL_DASHBOARD_PORT=3001
```

---

## Definition of Done

- [ ] `recall_jobs` and `recall_resume` Qdrant collections created successfully
- [ ] All new FastAPI endpoints return proper responses (can use mock data)
- [ ] Jay's resume is ingested into `recall_resume`
- [ ] `config/career_pages.json` populated with all target companies
- [ ] `config/job_search.json` populated with all titles, locations, thresholds
- [ ] Daily Dashboard React app running in Docker on port 3001
- [ ] Dashboard displays the Atelier Ops theme correctly
- [ ] LLM settings stored in SQLite and retrievable via API
- [ ] All endpoints follow existing API design skill conventions

---

## Files Created/Modified

| File | Action |
|------|--------|
| `scripts/phase6/setup_collections.py` | CREATE |
| `scripts/phase6/ingest_resume.py` | CREATE |
| `scripts/phase1/ingest_bridge_api.py` | MODIFY (add Phase 6 `/v1/*` endpoints) |
| `scripts/phase6/job_dedup.py` | CREATE |
| `scripts/phase6/job_discovery_runner.py` | CREATE |
| `scripts/phase6/job_evaluator.py` | CREATE |
| `scripts/phase6/gap_aggregator.py` | CREATE |
| `scripts/phase6/company_profiler.py` | CREATE |
| `scripts/phase6/telegram_notifier.py` | CREATE |
| `scripts/phase6/job_metadata_extractor.py` | CREATE |
| `config/career_pages.json` | CREATE |
| `config/job_search.json` | CREATE |
| `ui/daily-dashboard/` (full scaffold) | CREATE |
| `docker/docker-compose.yml` | MODIFY (add daily-dashboard service) |
| `docker/.env.example` | MODIFY (add new vars) |
