# Recall.local — Phase 6: Job Hunt Intelligence

**Product Requirements Document**
**Version:** 1.0
**Date:** March 3, 2026
**Author:** Jay Dreyer + Claude (Anthropic)
**Target Handoff:** Codex (guided build)

---

## Executive Summary

Phase 6 adds an AI-powered job search pipeline to Recall.local, transforming it from a personal knowledge management tool into an active career intelligence system. Job listings are automatically discovered, ingested into Qdrant, evaluated against Jay's resume using local LLMs, and surfaced on a new Daily Dashboard frontend. The system identifies skill gaps and recommends specific actions to close them.

This feature ships as two components: (1) n8n workflows that handle job discovery and ingestion, and (2) a standalone React/Vite Daily Dashboard that presents job intelligence alongside future daily-life widgets (weather, calendar, news, sports).

**Why now:** Employment at Gap Inc. ends May 15, 2026. The job search is the top priority and this system automates the most time-consuming part — finding, filtering, and evaluating relevant openings across dozens of sources.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Daily Dashboard                          │
│                  (React/Vite — separate app)                    │
│                                                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ Job Hunt │ │ Weather  │ │ Calendar │ │ News/    │  (future) │
│  │  Panel   │ │  Widget  │ │  Widget  │ │ Sports   │          │
│  └────┬─────┘ └──────────┘ └──────────┘ └──────────┘          │
│       │                                                         │
└───────┼─────────────────────────────────────────────────────────┘
        │ REST API
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Recall.local Bridge (FastAPI)                 │
│                                                                 │
│  Existing endpoints:                New Phase 6 endpoints:      │
│  POST /v1/ingestions                GET  /v1/jobs               │
│  POST /v1/ingestions/files          GET  /v1/jobs/{jobId}       │
│  POST /v1/rag-queries               POST /v1/job-evaluation-runs│
│  GET  /v1/activities                GET  /v1/job-stats          │
│  GET  /v1/auto-tag-rules            GET  /v1/job-gaps           │
│                                     POST /v1/resumes            │
│                                     GET  /v1/resumes/current    │
│                                     GET/PATCH /v1/llm-settings  │
└────────┬────────────────────────────────┬───────────────────────┘
         │                                │
         ▼                                ▼
┌─────────────────┐            ┌─────────────────────┐
│     Qdrant      │            │       Ollama        │
│                 │            │                     │
│ recall_docs     │            │ llama3.2:3b         │
│ recall_jobs ◄───┤            │ (fit scoring,       │
│ recall_resume   │            │  gap analysis)      │
└─────────────────┘            └─────────────────────┘
         ▲
         │
┌─────────────────────────────────────────────────────────────────┐
│                         n8n Workflows                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ Job Board    │  │ Career Page  │  │ Evaluate &   │         │
│  │ Aggregator   │  │ Monitor      │  │ Notify       │         │
│  │ Scraper      │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  Sources:                                                       │
│  - Adzuna API (free tier)                                       │
│  - JobSpy (Python, scrapes Indeed/LinkedIn/Glassdoor/ZipRecruiter)│
│  - SerpAPI Google Jobs (free tier)                              │
│  - Direct career page RSS/scraping (target companies)           │
└─────────────────────────────────────────────────────────────────┘
```

### How It Fits Into Recall.local

Phase 6 extends the existing Recall.local system — it does not replace anything. Jobs are stored in Qdrant alongside existing documents, using a dedicated `recall_jobs` collection. The FastAPI bridge gets new canonical `/v1/*` endpoints. The existing Recall dashboard (with Ingest, Query, Activity, Eval, Vault tabs) remains untouched. The new Daily Dashboard is a separate React/Vite app running on its own port, reading from the same bridge API.

---

## Target Job Titles

Based on career analysis and role research, the system searches for these titles:

### Primary Targets
- Solutions Engineer
- Solutions Architect
- Sales Engineer
- Technical Account Manager

### Secondary Targets
- AI Solutions Consultant
- AI Enablement Lead / AI Strategist
- Technical Program Manager
- Developer Experience / Developer Relations
- Enterprise AI Strategist
- Artificial Intelligence Consultant

### Search Modifiers
All titles are searched with these qualifiers where supported:
- Remote OR Minneapolis OR Twin Cities OR Minnesota
- AI, SaaS, API, Developer Tools, Enterprise Software

---

## Target Companies

### Tier 1 — Direct Relationship / Strongest Fit
| Company | Why | Monitor Method |
|---------|-----|----------------|
| Postman | API background IS their product | Career page RSS/scrape |
| Aisera | Was their customer, drove 75% resolution rate | Career page RSS/scrape |
| Miro | Direct product experience | Career page RSS/scrape |
| Airtable | Direct product experience | Career page RSS/scrape |
| Smartsheet | Direct product experience | Career page RSS/scrape |

### Tier 2 — Strong Fit / High Interest
| Company | Why | Monitor Method |
|---------|-----|----------------|
| Anthropic | Daily Claude user, built with Claude Code | Career page RSS/scrape |
| OpenAI | ChatGPT Champion, built custom GPTs | Career page RSS/scrape |
| Cohere | Enterprise AI focus | Career page RSS/scrape |
| Glean | Enterprise AI search | Career page RSS/scrape |
| Writer | Enterprise AI platform | Career page RSS/scrape |
| ServiceNow | AI chatbot experience translates | Career page RSS/scrape |
| Atlassian | Dev tools, API ecosystem | Career page RSS/scrape |
| Workato | Enterprise automation/integration | Career page RSS/scrape |
| Datadog | Dev tools, API monitoring | Career page RSS/scrape |

### Tier 3 — Twin Cities Enterprises
| Company | Why | Monitor Method |
|---------|-----|----------------|
| Target | 16 years there, huge network | Career page scrape |
| UnitedHealth / Optum | Massive AI investment | Career page scrape |
| Best Buy | Tech retail, AI adoption | Career page scrape |
| US Bank | Fintech AI | Career page scrape |
| 3M | Enterprise AI | Career page scrape |
| Medtronic | MedTech AI | Career page scrape |

### Visual Flagging
Jobs from Tier 1 and Tier 2 companies receive a visual badge on the dashboard (star icon + company tier color). Scores are NOT inflated — the flag is purely visual so Jay can spot target company listings at a glance. Tier 1 gets a gold badge, Tier 2 gets a blue badge.

---

## Component 1: n8n Job Discovery Workflows

### Overview

Three n8n workflows handle job discovery, career page monitoring, and evaluation orchestration. These are built collaboratively with Codex — the PRD provides the workflow logic, data schemas, and integration details so Codex can guide Jay through the build step by step.

### Workflow 1: Job Board Aggregator

**Trigger:** Cron schedule, every 8 hours (6 AM, 2 PM, 10 PM)

**Data Sources (in priority order):**

1. **JobSpy (Python library)** — Primary source. Scrapes Indeed, LinkedIn, Glassdoor, and ZipRecruiter. Run inside the bridge-side discovery runner (Python), triggered from n8n via HTTP.
   - Runtime note: n8n on ai-lab does not have `python3`, so Python execution must not run inside n8n nodes.
   - Install: `pip install python-jobspy` in the bridge runtime image/environment
   - Returns: title, company, location, description, url, date_posted, salary
   - Rate limit: Add 2-3 second delays between searches
   - Search queries: One per target title × location combo

2. **Adzuna API** — Secondary source. Free tier allows 250 requests/month.
   - Endpoint: `https://api.adzuna.com/v1/api/jobs/{country}/search/{page}`
   - Returns: title, company, location, description, redirect_url, created, salary_min, salary_max
   - Sign up: https://developer.adzuna.com/

3. **SerpAPI Google Jobs** — Tertiary source. Free tier allows 100 searches/month.
   - Endpoint: `https://serpapi.com/search?engine=google_jobs`
   - Returns: title, company_name, location, description, detected_extensions, apply_link
   - Use sparingly — save for broad searches that other sources miss

**Workflow Steps:**

```
[Cron Trigger]
    │
    ▼
[Build Search Queries]
    │  For each title + location combo, generate API params
    │  Rotate through sources to respect rate limits
    │
    ▼
[Execute Discovery Run]
    │  n8n calls `POST /v1/job-discovery-runs`
    │  Bridge runner executes:
    │  ─── JobSpy (Python)
    │  ─── Adzuna API
    │  ─── SerpAPI
    │
    ▼
[Normalize Results]
    │  Map all sources to unified Job schema (see below)
    │  Strip HTML from descriptions
    │  Normalize company names (e.g., "Anthropic, PBC" → "Anthropic")
    │  Normalize locations (e.g., "Minneapolis, MN" → "Minneapolis, MN")
    │
    ▼
[Deduplicate]
    │  Check Qdrant for existing jobs with same URL
    │  Check semantic similarity (threshold: 0.92) to catch reposts
    │  Skip duplicates, log skip count
    │
    ▼
[Enrich & Store]
    │  Add metadata: source, discovered_at, search_query
    │  Tag with company tier (1/2/3/none)
    │  Embed description with same model as Recall docs
    │  Store in recall_jobs Qdrant collection
    │
    ▼
[Trigger Evaluation Workflow]
    │  Pass list of new job IDs to Workflow 3
    │
    ▼
[Log Summary]
    │  Write to SQLite activity log:
    │  "Discovered 12 new jobs, 8 duplicates skipped"
```

### Workflow 2: Career Page Monitor

**Trigger:** Cron schedule, every 12 hours (7 AM, 7 PM)

**Purpose:** Monitors career pages of target companies directly. Many companies post jobs on their own site before they hit aggregators. This workflow catches those early.

**Implementation Approach:**

For each target company, define a career page config:

```json
{
  "company": "Anthropic",
  "url": "https://boards.greenhouse.io/anthropic",
  "type": "greenhouse",
  "tier": 2
}
```

Most target companies use one of three ATS platforms:
- **Greenhouse** (Anthropic, Cohere, Writer, others): Has a JSON API at `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- **Lever** (some startups): JSON API at `https://api.lever.co/v0/postings/{company}`
- **Workday** (Target, UHG, 3M, Medtronic, Best Buy): Harder to scrape — use keyword search URL + HTML parsing

**Workflow Steps:**

```
[Cron Trigger]
    │
    ▼
[Load Company Configs]
    │  Read from config/career_pages.json
    │
    ▼
[For Each Company]
    │
    ├── [Greenhouse API] → JSON response with all open jobs
    ├── [Lever API] → JSON response with all open jobs
    └── [Workday/Other] → HTTP fetch + basic HTML parsing
    │
    ▼
[Filter by Title Match]
    │  Fuzzy match against target title list
    │  Include partial matches (e.g., "Senior Solutions Engineer" matches "Solutions Engineer")
    │
    ▼
[Normalize & Deduplicate]  (same as Workflow 1)
    │
    ▼
[Enrich & Store]  (same as Workflow 1)
    │
    ▼
[Trigger Evaluation Workflow]
```

### Workflow 3: Evaluate & Notify

**Trigger:** Called by Workflows 1 and 2 after new jobs are stored. Also runnable manually from the dashboard.

**Purpose:** Evaluates each new job against Jay's resume using Ollama, generates a fit score, identifies matching skills and gaps, and sends push notifications for high-scoring matches.

**AI Evaluation Approach — Hybrid Model:**

| Task | Model | Rationale |
|------|-------|-----------|
| Fit scoring (0-100) | Ollama (llama3.2:3b) | Structured JSON output, runs locally, fast, free. Good enough for a numeric score + bullet points. |
| Deep gap analysis | Ollama (llama3.2:3b) first, cloud fallback if quality is poor | Gap analysis needs nuance. Start local — if the output is vague or generic, the system can optionally re-run through a cloud API (Anthropic/OpenAI) for that specific job. Default: local only. |
| Improvement recommendations | Ollama (llama3.2:3b) first, cloud fallback | Same logic as gap analysis. Recommending specific courses/projects/videos benefits from a larger model's knowledge base. |

**Cloud fallback is opt-in via environment variable:**
```bash
RECALL_JOBS_CLOUD_FALLBACK=false          # Default: local only
RECALL_JOBS_CLOUD_PROVIDER=anthropic      # anthropic | openai
RECALL_JOBS_CLOUD_MODEL=claude-sonnet-4-5-20250929
```

**Evaluation Prompt Template:**

```
You are a career advisor evaluating job fit. You will receive:
1. A job listing (title, company, description, requirements)
2. A candidate resume

Evaluate how well the candidate fits this role. Return ONLY valid JSON:

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

**Workflow Steps:**

```
[Receive New Job IDs]
    │
    ▼
[Load Resume from Qdrant]
    │  Fetch from recall_resume collection
    │  Concatenate chunks into full resume text
    │
    ▼
[For Each New Job]
    │
    ├── [Fetch Job from Qdrant]
    │
    ├── [Build Evaluation Prompt]
    │   │  Insert job description + resume into template
    │   │
    │   ▼
    │  [Call Ollama API]
    │   │  POST http://localhost:11434/api/generate
    │   │  Model: llama3.2:3b
    │   │  Parse JSON response
    │   │
    │   ▼
    │  [Validate Response]
    │   │  Confirm JSON structure is correct
    │   │  Confirm fit_score is 0-100
    │   │  If malformed: retry once with stricter prompt
    │   │  If still malformed: store with score=-1, flag for manual review
    │   │
    │   ▼
    │  [Optional: Cloud Fallback]
    │   │  If RECALL_JOBS_CLOUD_FALLBACK=true AND
    │   │  (gaps analysis is empty OR recommendations are generic):
    │   │    Re-run gap analysis portion through cloud API
    │   │    Merge cloud results into local evaluation
    │   │
    │   ▼
    │  [Store Evaluation]
    │      Update job record in Qdrant with evaluation payload
    │      Write to SQLite activity log
    │
    ▼
[Check Notification Threshold]
    │  If fit_score >= 75:
    │    Send Telegram notification
    │    Include: job title, company, score, top matching skill
    │
    ▼
[Update Dashboard Stats]
    │  Increment daily counters in SQLite
    │  New jobs found, evaluated, high-scoring
```

---

## Component 2: Qdrant Collections & Data Schema

### New Collection: `recall_jobs`

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
    "applied": "bool",
    "applied_at": "datetime",
    "notes": "text",
    "dismissed": "bool"
  }
}
```

**Status values:** `new` → `evaluated` → `applied` | `dismissed` | `expired`

### New Collection: `recall_resume`

Stores Jay's current resume, chunked and embedded like any other Recall document. Used by the evaluation workflow to compare against job descriptions.

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

**Resume ingestion endpoint:** `POST /v1/resumes` — accepts a markdown or PDF resume, chunks it, embeds it, and stores it in `recall_resume`. Clears previous version first. This allows the resume to be updated as skills are added, and all future evaluations automatically use the latest version.

---

## Component 3: FastAPI Bridge Endpoints

### New Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/jobs` | List jobs with filtering, sorting, pagination |
| `GET` | `/v1/jobs/{jobId}` | Get single job with full evaluation |
| `POST` | `/v1/job-evaluation-runs` | Create job evaluation run(s) for one or more job IDs |
| `GET` | `/v1/job-stats` | Dashboard stats (counts by score range, by source, by day) |
| `GET` | `/v1/job-gaps` | Aggregated gap analysis across all evaluated jobs |
| `POST` | `/v1/job-deduplications` | Check duplicate status for candidate job payloads |
| `POST` | `/v1/job-discovery-runs` | Trigger source discovery + normalization + storage run |
| `POST` | `/v1/resumes` | Ingest/update resume into recall_resume collection |
| `GET` | `/v1/resumes/current` | Return current resume metadata (version, date, chunk count) |
| `GET` | `/v1/companies` | List company profiles |
| `GET` | `/v1/companies/{companyId}` | Get one company profile with associated jobs |
| `POST` | `/v1/company-profile-refresh-runs` | Trigger company-profile refresh for a specific company |
| `GET` | `/v1/llm-settings` | Read current LLM settings |
| `PATCH` | `/v1/llm-settings` | Update LLM settings |
| `PATCH` | `/v1/jobs/{jobId}` | Update job status (applied, dismissed, notes) |

### `GET /v1/jobs` — Query Parameters

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | `evaluated` | Filter: new, evaluated, applied, dismissed, expired |
| `min_score` | int | 0 | Minimum fit score |
| `max_score` | int | 100 | Maximum fit score |
| `company_tier` | int | null | Filter by company tier (1, 2, 3) |
| `source` | string | null | Filter by source (jobspy, adzuna, serpapi, career_page) |
| `title_query` | string | null | Fuzzy title search |
| `sort` | string | `fit_score` | Sort field: fit_score, discovered_at, company |
| `order` | string | `desc` | Sort order: asc, desc |
| `limit` | int | 50 | Page size |
| `offset` | int | 0 | Pagination offset |

### `GET /v1/job-gaps` — Aggregated Gap Analysis

This is a powerful endpoint. It scans all evaluated jobs, aggregates the gaps across them, and returns a ranked list of skills to develop — weighted by how often they appear and the severity rating. This answers the question: "Across all the jobs I'm a fit for, what are the most common things I'm missing?"

**Response:**

```json
{
  "total_jobs_analyzed": 47,
  "aggregated_gaps": [
    {
      "gap": "Kubernetes / container orchestration experience",
      "frequency": 12,
      "avg_severity": "moderate",
      "top_recommendations": [
        {
          "type": "course",
          "title": "Kubernetes for Developers",
          "source": "KodeKloud / Udemy",
          "effort": "20 hours"
        },
        {
          "type": "project",
          "title": "Deploy Recall.local to a K8s cluster",
          "source": "Self-directed",
          "effort": "1 weekend"
        }
      ]
    },
    {
      "gap": "Pre-sales / RFP response experience",
      "frequency": 8,
      "avg_severity": "moderate",
      "top_recommendations": [...]
    }
  ],
  "generated_at": "2026-03-03T12:00:00Z"
}
```

---

## Component 4: Daily Dashboard (React/Vite)

### Overview

A standalone React/Vite application, served as its own Docker container (nginx + static build), running on a separate port from the Recall dashboard. This is the "Daily Mission Control" — the page Jay opens every morning.

Phase 6 delivers the Job Hunt panel. Future phases add weather, calendar, news, and sports widgets.

### Tech Stack
- React 18 + Vite
- Tailwind CSS
- Recharts (for score distribution charts)
- Atelier Ops / Luxury Minimal theme (warm light palette, editorial typography, thin-rule layout)
- Fonts: Playfair Display, Manrope, IBM Plex Mono

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  DAILY DASHBOARD                              March 3, 2026     │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ┌─── Stats Bar ──────────────────────────────────────────────┐ │
│  │ 🆕 12 New Today  │ ⭐ 3 High Fit  │ 📊 Avg: 62  │ 📋 47 │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─── Filters ────────────────────────────────────────────────┐ │
│  │ Score: [All ▾]  Source: [All ▾]  Tier: [All ▾]  Status ▾  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─── Job Cards ──────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ ⭐ Solutions Engineer          Anthropic    🏅 T2    │  │ │
│  │  │ Score: ████████████████░░░░ 82  Remote              │  │ │
│  │  │ Top Match: API governance, AI enablement             │  │ │
│  │  │ Top Gap: Pre-sales demo experience (moderate)        │  │ │
│  │  │ [View Details] [Mark Applied] [Dismiss]              │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  │  ┌──────────────────────────────────────────────────────┐  │ │
│  │  │ Solutions Architect             Glean        🏅 T2    │  │ │
│  │  │ Score: ██████████████░░░░░░ 71  Remote              │  │ │
│  │  │ Top Match: Enterprise SaaS, RAG pipeline             │  │ │
│  │  │ Top Gap: Go language experience (minor)              │  │ │
│  │  │ [View Details] [Mark Applied] [Dismiss]              │  │ │
│  │  └──────────────────────────────────────────────────────┘  │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─── Skill Gap Radar ────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  Your top gaps across all evaluated jobs:                   │ │
│  │                                                             │ │
│  │  Kubernetes (12 jobs)          ████████████░░░░ moderate    │ │
│  │  Pre-sales demos (8 jobs)      ████████░░░░░░░░ moderate    │ │
│  │  Go language (5 jobs)          █████░░░░░░░░░░░ minor       │ │
│  │  Terraform/IaC (4 jobs)        ████░░░░░░░░░░░░ minor       │ │
│  │                                                             │ │
│  │  [View Recommendations →]                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌─── Future Widget Slots ────────────────────────────────────┐ │
│  │  🌤 Weather  │  📅 Calendar  │  📰 News  │  ⚾ Sports     │ │
│  │  (Phase 7)   │  (Phase 7)    │ (Phase 7) │  (Phase 7)     │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Job Detail Expanded View

Clicking "View Details" on a job card expands to show:

- Full job description (scrollable)
- Complete AI evaluation:
  - Fit score with rationale
  - All matching skills with evidence from resume
  - All gaps with severity and recommendations
  - Application tips
  - Cover letter angle
- Action buttons: Mark Applied, Dismiss, Add Notes, Re-evaluate (triggers cloud API if enabled)
- Link to original job posting (opens in new tab)
- "Generate Cover Letter Draft" button (calls Ollama with the cover_letter_angle + resume + job description)

### Skill Gap Recommendations View

Accessible from the "View Recommendations" link on the Skill Gap Radar. Shows a detailed breakdown:

- For each gap: specific courses, projects, videos, and certifications
- Effort estimates for each recommendation
- Progress tracking (manual checkboxes — "I completed this")
- A "Learning Plan" view that sequences recommendations by impact and effort

### Score Distribution Chart

A small Recharts bar chart showing the distribution of fit scores across all evaluated jobs. Helps visualize: are most jobs clustering at 40-60 (need to adjust search terms) or 70-90 (search is well-targeted)?

---

## Component 5: Push Notifications

### Overview

When a job scores 75+ on fit evaluation, send a push notification via Telegram so Jay doesn't have to check the dashboard constantly. Telegram is already set up via the OpenClaw/Arthur bot — reuse the existing bot token and chat ID. Zero new infrastructure.

### Telegram Bot API Integration

The notification service sends messages via the Telegram Bot API using the existing Arthur bot credentials:

```python
import requests

def send_telegram_notification(job):
    bot_token = os.getenv("RECALL_TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("RECALL_TELEGRAM_CHAT_ID")
    
    text = (
        f"🎯 *High-Fit Job: {job['title']}*\n"
        f"📍 {job['company']} ({job['location']})\n"
        f"📊 Score: {job['fit_score']}/100\n"
        f"✅ Top match: {job['matching_skills'][0]['skill']}\n"
        f"⚠️ Top gap: {job['gaps'][0]['gap']} ({job['gaps'][0]['severity']})\n"
        f"\n[View on Dashboard]({dashboard_url}/jobs/{job['id']})"
    )
    
    requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    )
```

### Notification Rules

- Score >= 75: Telegram notification (high priority)
- Score >= 60 AND company_tier in [1, 2]: Telegram notification (normal priority)
- All others: Dashboard only

---

## Component 6: LLM Provider Toggle (UI Setting)

### Overview

Instead of burying the local vs. cloud LLM choice in environment variables, the Daily Dashboard exposes a settings panel where Jay can toggle between providers in real time.

### Settings Panel

Accessible from a gear icon in the dashboard header:

- **Evaluation Model:** Toggle between `Local (Ollama)` and `Cloud`
- **Cloud Provider:** Dropdown — `Anthropic (Claude Sonnet 4.5)` | `Anthropic (Claude Opus 4.5)` | `OpenAI (GPT-4o)`
- **Cloud Fallback:** Toggle — "Auto-escalate to cloud if local quality is poor"
- **Auto-escalate threshold:** Slider — "If local response has fewer than N gaps or score rationale is under N words, re-run with cloud"

### Model Recommendation Hierarchy

| Priority | Model | Cost | Use When |
|----------|-------|------|----------|
| 1 (default) | Ollama llama3.2:3b | Free | Daily bulk scoring, structured JSON |
| 2 (cloud default) | Claude Sonnet 4.5 | ~$0.01-0.03/eval | Gap analysis, recommendations, nuanced reasoning |
| 3 (deep dive) | Claude Opus 4.5 | ~$0.05-0.15/eval | Deep analysis on top candidates, cover letter drafts |
| 4 (alternative) | GPT-4o | ~$0.01-0.03/eval | If using existing OpenAI API key |

### API Endpoint

`GET /v1/llm-settings` and `PATCH /v1/llm-settings` — read and update the current LLM configuration. Stored in SQLite `settings` table so it persists across restarts.

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

---

## Component 7: Manual Job Discovery (Chrome Extension Integration)

### Overview

The existing Recall.local Chrome extension already supports tagging content with the `job-search` group. Phase 6 adds a bridge-level hook: when content is ingested with `group=job-search` and the URL matches known job board patterns, it is also stored in the `recall_jobs` collection and queued for AI evaluation.

This handles the "I found a cool job while browsing" use case — Jay bookmarks it with the Chrome extension exactly as he does today, and it automatically enters the job intelligence pipeline.

### Bridge Hook Logic

In the ingestion pipeline, after standard document ingestion:

```python
JOB_URL_PATTERNS = [
    "linkedin.com/jobs", "indeed.com/viewjob", "lever.co", "greenhouse.io",
    "boards.greenhouse.io", "jobs.ashbyhq.com", "wellfound.com/jobs",
    "careers.", "/careers/", "/jobs/", "workday.com"
]

def post_ingestion_hook(url, group, tags, chunks):
    if group == "job-search" and any(pattern in url for pattern in JOB_URL_PATTERNS):
        # Extract job metadata from the ingested content using Ollama
        job_data = extract_job_metadata(chunks)
        # Store in recall_jobs collection
        store_job(job_data, source="chrome_extension", url=url)
        # Queue for evaluation
        queue_evaluation([job_data["id"]])
```

### Job Metadata Extraction Prompt

When a job is manually discovered (not from a structured API), the raw page content needs to be parsed into the job schema. A lightweight Ollama prompt handles this:

```
Extract the following from this job posting. Return ONLY valid JSON:
{
  "title": "<job title>",
  "company": "<company name>",
  "location": "<location or Remote>",
  "location_type": "<remote|hybrid|onsite>",
  "description": "<full job description>",
  "salary_min": <number or null>,
  "salary_max": <number or null>
}
```

### UX Flow

1. Jay sees interesting job on LinkedIn/Greenhouse/etc.
2. Clicks Chrome extension → group auto-selects "Job Search" (existing behavior)
3. Clicks "Send to Recall" (existing behavior)
4. Bridge ingests content into `recall_docs` (existing behavior)
5. **NEW:** Bridge hook detects job-search group + job URL pattern
6. **NEW:** Extracts job metadata, stores in `recall_jobs`
7. **NEW:** Queues for AI evaluation
8. **NEW:** Job appears on Daily Dashboard within minutes
9. **NEW:** If score >= 75, Telegram notification fires

From Jay's perspective, nothing changes in the workflow — he bookmarks things the same way. The intelligence layer is invisible.

---

## Component 8: Company Intelligence Profiles

### Overview

When a job is ingested from a company for the first time, the system auto-generates a Company Profile page. This becomes a persistent, enrichable page in the Daily Dashboard showing what the company does, their culture, what they look for, and all jobs from that company in one place.

### Company Profile Data

```json
{
  "company_id": "anthropic",
  "name": "Anthropic",
  "tier": 2,
  "description": "<AI safety company, makers of Claude>",
  "size": "<~1000 employees>",
  "hq_location": "San Francisco, CA",
  "remote_policy": "Remote-friendly",
  "funding_stage": "Series D, $7.3B raised",
  "what_they_look_for": "<emphasis on safety-mindedness, technical depth, clear communication>",
  "engineering_culture": "<research-driven, move fast on safety, collaborative>",
  "glassdoor_summary": "<optional, pulled from web if available>",
  "your_connection": "<Jay's existing relationship — e.g., daily Claude user, built with Claude Code>",
  "jobs": [/* all jobs from this company */],
  "first_seen": "2026-03-05T00:00:00Z",
  "last_updated": "2026-03-10T00:00:00Z",
  "profile_source": "ai_generated"
}
```

### Generation Approach

When the first job from a new company is ingested:

1. Check if company profile exists in SQLite `company_profiles` table
2. If not, generate one using Ollama (or cloud model if toggled):
   - Use the job description as primary context
   - If the company is in the target list (`config/career_pages.json`), pull the `your_connection` field from config
   - Prompt: "Based on this job posting, generate a company profile..."
3. Store profile in SQLite
4. For subsequent jobs from the same company, update the profile (merge new info, don't overwrite)

### Dashboard View

- Accessible from a "Companies" tab or from clicking a company name on any job card
- **Visually rich** — this should feel like a one-page executive brief, not a database record

**Company Profile Page Layout:**

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ┌─────────┐  ANTHROPIC                                        │
│  │  LOGO   │  AI Safety Company · San Francisco, CA             │
│  │         │  Series D · ~1,000 employees · Remote-friendly     │
│  └─────────┘  anthropic.com/careers                 🏅 Tier 2   │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  About                                                          │
│  Anthropic is an AI safety company building reliable,           │
│  interpretable AI systems. Founded in 2021 by former OpenAI     │
│  researchers, they created the Claude model family...           │
│                                                                 │
│  ┌───────────────────────┐  ┌───────────────────────┐          │
│  │ What They Look For    │  │ Your Connection        │          │
│  │                       │  │                        │          │
│  │ • Safety-mindedness   │  │ Daily Claude user.     │          │
│  │ • Technical depth     │  │ Built production apps  │          │
│  │ • Clear communication │  │ with Claude Code.      │          │
│  │ • Customer empathy    │  │ Recall.local uses      │          │
│  │ • API design sense    │  │ Anthropic API.         │          │
│  └───────────────────────┘  └───────────────────────┘          │
│                                                                 │
│  ┌──── Jobs from Anthropic ───────────────────────────────────┐ │
│  │ Solutions Engineer        Score: 82   Remote    [View →]   │ │
│  │ Technical Account Mgr     Score: 68   Remote    [View →]   │ │
│  │ ──────────────────────────────────────────────────         │ │
│  │ Avg Fit Score: 75 across 2 roles                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌──── Key Skills They Value ─────────────────────────────────┐ │
│  │                                                             │ │
│  │  ██████████████  API Design          (mentioned in 2/2)     │ │
│  │  ████████████    AI/ML Knowledge     (mentioned in 2/2)     │ │
│  │  ████████        Customer Facing     (mentioned in 1/2)     │ │
│  │  ██████          Python              (mentioned in 1/2)     │ │
│  │                                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Last updated: March 5, 2026                    [↻ Refresh]    │
└─────────────────────────────────────────────────────────────────┘
```

**Visual Design Elements:**

- **Company logo:** Fetch from Clearbit Logo API (`https://logo.clearbit.com/{domain}`) or Google's favicon service as fallback. Display at 64x64px with a subtle border-radius and warm shadow. If no logo is available, generate a styled monogram (first letter of company name in Playfair Display, set against the accent color).
- **Tier badge:** Gold badge for Tier 1, blue-grey for Tier 2, muted for Tier 3 — same visual language as job cards.
- **Key Skills bar chart:** Horizontal bars showing which skills this company mentions most across all their job postings. Uses the accent palette from the Atelier Ops theme. This tells Jay at a glance "what does this company care about?"
- **"Your Connection" card:** A warm-toned aside card (subtle `#A0916B` left border) that highlights Jay's existing relationship with the company. Pulled from `config/career_pages.json` or auto-generated from Recall's knowledge base.
- **Company description:** AI-generated from job postings + optional web enrichment. Written in natural prose, not bullet points. Aim for 2-3 sentences.
- **Funding / size / location:** Displayed as clean metadata chips, not a dense table. Think tag-pill style with muted backgrounds.
- **Jobs list:** Mini job cards embedded in the profile, sorted by fit score. Clicking goes to the full job detail view.
- **Skill frequency visualization:** When multiple jobs exist from one company, aggregate the required skills into a frequency chart. This reveals what the company consistently values vs. one-off requirements.

**Companies List View:**

The "Companies" tab shows all companies as a card grid:

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  [Logo]      │  │  [Logo]      │  │  [Logo]      │
│  Anthropic   │  │  Glean       │  │  Postman     │
│  🏅 Tier 2   │  │  🏅 Tier 2   │  │  🏅 Tier 1   │
│  2 jobs      │  │  1 job       │  │  3 jobs      │
│  Avg: 75     │  │  Avg: 71     │  │  Avg: 84     │
└──────────────┘  └──────────────┘  └──────────────┘
```

- Cards are sorted by average fit score (highest first)
- Tier badges are visible at the card level
- Clicking a card opens the full company profile page
- Empty state: "No companies yet — jobs will be discovered on the next scan"

### Future Enhancement

- Enrich profiles with web search data (funding news, recent product launches, leadership changes)
- Cross-reference with Jay's Obsidian vault (if he has notes on the company)
- Track which companies are posting more aggressively (hiring surge detection)

---

## Component 9: Resume Management

### Ingestion

The `POST /v1/resumes` endpoint accepts Jay's resume in markdown or PDF format, processes it through the existing Recall chunking/embedding pipeline, and stores it in the `recall_resume` Qdrant collection.

**Key behavior:**
- Clears previous resume version before ingesting new one
- Increments version counter
- Logs ingestion to SQLite activity
- All subsequent job evaluations automatically use the latest resume

### Resume as Living Document

As Jay completes learning recommendations (courses, projects, certifications), he updates his resume and re-ingests it. The next evaluation cycle automatically produces updated scores. This creates a feedback loop:

```
Find jobs → Identify gaps → Close gaps → Update resume → Re-evaluate → Better scores
```

The dashboard could surface this: "You completed the Kubernetes course. 4 previously-scored jobs would now score higher. [Re-evaluate them →]"

---

## Configuration Files

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
      "title_filter": ["solutions", "engineer", "architect", "technical", "account", "sales"]
    },
    {
      "name": "OpenAI",
      "tier": 2,
      "ats": "greenhouse",
      "board_id": "openai",
      "url": "https://boards-api.greenhouse.io/v1/boards/openai/jobs",
      "title_filter": ["solutions", "engineer", "architect", "sales"]
    },
    {
      "name": "Target",
      "tier": 3,
      "ats": "workday",
      "url": "https://jobs.target.com/search-jobs",
      "title_filter": ["solutions", "architect", "ai", "developer experience"]
    }
  ]
}
```

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

### Environment Variables

```bash
# Job Search Configuration
RECALL_JOBS_ENABLED=true
RECALL_JOBS_CLOUD_FALLBACK=false
RECALL_JOBS_CLOUD_PROVIDER=anthropic
RECALL_JOBS_CLOUD_MODEL=claude-sonnet-4-5-20250929

# Job Source API Keys
ADZUNA_APP_ID=your_app_id
ADZUNA_API_KEY=your_api_key
SERPAPI_KEY=your_key

# Notifications (reuse existing Arthur/OpenClaw Telegram bot)
RECALL_TELEGRAM_BOT_TOKEN=your_existing_bot_token
RECALL_TELEGRAM_CHAT_ID=your_chat_id

# Daily Dashboard
RECALL_DASHBOARD_PORT=3001
```

---

## Implementation Plan

Phase 6 is split into four implementation briefs, each self-contained enough for Codex to work from independently. Read this PRD first for the full architecture, then work through each phase brief in order.

| Phase | Brief Document | Focus | Est. Effort |
|-------|---------------|-------|-------------|
| 6A | `docs/Phase6A_Foundation_Brief.md` | Qdrant collections, FastAPI endpoints, resume ingestion, config files, dashboard scaffold | 3-4 days |
| 6B | `docs/Phase6B_Job_Discovery_Brief.md` | n8n workflows (guided build), deduplication, career page monitoring | 3-4 days |
| 6C | `docs/Phase6C_AI_Evaluation_Brief.md` | Evaluation prompt, Ollama integration, gap aggregation, Chrome extension hook | 2-3 days |
| 6D | `docs/Phase6D_Dashboard_Brief.md` | Job Hunt panel, company profiles, skill gap radar, settings, cover letter drafts | 4-5 days |

**Total estimated: 14-18 working days**

Each brief includes: specific tasks with effort estimates, code patterns, API details, a definition of done checklist, and a file manifest.

### Codex Handoff Notes

This PRD is designed for a guided build with Codex. Key instructions:

**API Design:** Codex MUST follow Jay's existing API design skill (available in Codex's skill set) for all new endpoints. This covers naming conventions, documentation standards, error response formats, and versioning. All Phase 6 endpoints must be consistent with Phases 0-5.

**n8n Workflows (tasks 6, 7, 11):** Codex should:
1. Explain the workflow structure and what each node does before building it
2. Walk Jay through creating each node step by step in the n8n UI
3. Provide the configuration for each node (HTTP headers, code blocks, expressions)
4. Help debug and test as they go
5. Not just dump a workflow JSON import — the goal is understanding

**Daily Dashboard UI Theme:** The Daily Dashboard uses the **"Atelier Ops" / Luxury Minimal** design system — NOT the Recall.local dark ops theme. A reference artifact exists: `luxury-minimal.jsx`. Codex should study it carefully and extract the design tokens. Key design language:

- **Background:** Warm off-white `#FAFAF7` (not dark mode)
- **Primary text:** Deep warm charcoal `#2A2520`
- **Secondary text:** Muted stone `#8F8578`
- **Tertiary/timestamps:** Light taupe `#B8AD9E`
- **Accent:** Burnt orange-red `#E8553A`
- **Status colors:** Active `#E8553A`, Queued/Pending `#A0916B` (warm gold), Complete `#6B8F71` (sage green)
- **Borders/rules:** Warm linen `#E8E2D8`, razor-thin 1px lines
- **Headings font:** Playfair Display (serif) — elegant, editorial feel
- **Body font:** Manrope (sans-serif) — clean, geometric, modern
- **Mono font:** IBM Plex Mono — for timestamps, data labels, scores
- **Section headers:** 10-12px, uppercase, letter-spacing 2-3px, weight 600-700
- **Layout:** Generous whitespace, architectural grid, 1160px max-width
- **Cards:** No heavy borders or shadows — use thin rules and whitespace to separate sections
- **Animations:** Subtle fade-in with slight translateY, cubic-bezier easing, staggered delays
- **Scrollbars:** Thin (4px), warm tones (`#D8D0C4`)
- **Inputs:** Transparent background, bottom-border only, accent color on focus
- **Buttons:** Solid accent fill for primary, outlined for secondary, uppercase 12px lettering

This is a reading surface for starting the day — calm, warm, focused. Think "Bloomberg Terminal meets Monocle magazine." The job cards, skill gap radar, and company profiles should all follow this same language.

For the React dashboard and FastAPI endpoints, Codex can generate code more directly since Jay is comfortable with that workflow from Phases 0-5.

---

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Jobs discovered per day | 10-30 new unique | SQLite activity log |
| Evaluation accuracy | Fit scores feel "right" to Jay | Manual spot-check of 10 jobs |
| False positive rate (high score, bad fit) | < 20% | Manual review |
| Time from posting to dashboard | < 6 hours | discovered_at vs date_posted |
| Dashboard load time | < 2 seconds | Browser dev tools |
| Notification latency | < 5 min after evaluation | Spot check |

---

## Future Enhancements (Phase 7+)

### Daily Dashboard Expansion

**Weather Widget**
- Pull weather for Minneapolis from a free API (OpenWeatherMap or Open-Meteo)
- Show current conditions, high/low, precipitation probability
- "Do I need a jacket?" AI summary using Ollama

**Calendar Widget**
- Integrate with Google Calendar API (or CalDAV for local-first)
- Show today's schedule, upcoming interviews, application deadlines
- Auto-create calendar events when Jay marks "Applied" (interview prep reminder 2 days out)

**AI News Feed**
- Curated RSS feeds from AI-focused sources (The Batch, Hacker News AI, Anthropic blog, OpenAI blog, arXiv highlights)
- Ollama summarizes overnight articles into 3-5 bullet points
- Relevant for interview prep ("Did you see Anthropic's announcement about X?")
- Tag articles as relevant to specific target companies

**Sports Scores & News**
- ESPN API or similar for teams Jay follows
- Minimal widget — just scores and upcoming games
- Optional: Ollama generates a brief "what happened" summary

### Job Hunt Advanced Features

**Application Tracker**
- Full Kanban board: Discovered → Applied → Phone Screen → Technical → Onsite → Offer → Accepted/Rejected
- Track dates, contacts, notes for each stage
- Auto-populate from job card "Mark Applied" action

**Interview Prep Generator**
- When a job moves to "Phone Screen" stage, auto-generate:
  - Company research summary (pulled from Recall knowledge base + web)
  - STAR stories from resume that map to job requirements
  - Likely interview questions based on job description
  - Questions to ask the interviewer
- Store prep docs in Obsidian vault for mobile access

**Network Intelligence**
- Cross-reference job listings with LinkedIn connections (manual input or CSV export)
- Surface: "You know 3 people at Anthropic — Sarah (from Target), Mike (from Gap), Lisa (met at API World)"
- Prompt to reach out for referrals on high-fit jobs

**Salary Intelligence**
- Aggregate salary data from job listings that include ranges
- Show market rate ranges by title and location
- Compare against Jay's target compensation
- Factor into fit scoring (optional weight)

**Auto-Apply Draft Generation**
- For high-fit jobs (score 80+), auto-generate:
  - Tailored cover letter draft
  - Resume bullet point suggestions (reorder/emphasize based on job requirements)
  - Application question answers (many job apps have 2-3 freeform questions)
- Store drafts in Obsidian for review before submission

**Job Market Trend Analysis**
- Weekly digest: which titles are posting more/less, which companies are hiring aggressively
- Skills trending up/down across listings (e.g., "Kubernetes mentioned 40% more this month")
- Geographic trends (remote vs hybrid shifting?)
- Alert: "Anthropic just posted 5 new SE roles — they may be expanding the team"

**Competitive Intelligence**
- Track what other companies in the same space are hiring for
- Compare job descriptions across companies for the same title
- Identify which companies value which skills most
- "Anthropic's SE role emphasizes API design; OpenAI's emphasizes demos and storytelling"

### Technical Enhancements

**Semantic Job Matching**
- Instead of just keyword title matching, use embeddings to find jobs that are semantically similar to the target role profiles
- Catch jobs with unusual titles that are actually good fits (e.g., "Customer Success Architect" might be an SE role in disguise)

**Resume A/B Testing**
- Store multiple resume versions
- Score the same job against different versions
- See which framing produces higher scores
- "Your resume v3 (emphasizing AI projects) scores 8 points higher on average than v2 (emphasizing PM experience)"

**Job Expiration Detection**
- Periodically re-check job URLs
- Mark expired/filled positions
- Track time-to-fill by company (useful for knowing when to expect responses)

**Recall.local Integration Deepening**
- When ingesting an interesting article via Chrome extension, cross-reference against job gaps
- "This article about Kubernetes service meshes is relevant to a gap in 12 of your target jobs. [Save to Learning →]"
- Obsidian daily note auto-includes a "Job Search Summary" section

**Voice Briefing (Arthur Integration)**
- Morning briefing via Arthur: "Good morning Jay. You have 4 new high-fit jobs overnight. The top one is a Solutions Engineer at Anthropic, scoring 82. You have an interview prep session on your calendar at 2 PM. It's 28 degrees outside."
- Conversational interface: "Arthur, what should I study this week based on my gaps?"

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Job boards block scraping | No new jobs from that source | Use multiple sources; prefer APIs over scraping; JobSpy handles rotation |
| Ollama produces malformed JSON | Evaluation fails | JSON validation + retry with stricter prompt + fallback to cloud |
| Ollama fit scores are unreliable | Bad signal, wrong priorities | Calibrate with manual review of first 20 jobs; adjust prompt until scores feel right |
| Too many low-quality results | Dashboard noise | Aggressive dedup + minimum score threshold in config |
| API rate limits (Adzuna, SerpAPI) | Reduced coverage | Stagger calls; use free tiers wisely; prioritize JobSpy which has no API limit |
| Resume changes break scoring consistency | Scores not comparable over time | Version the resume; allow re-evaluation of all jobs against new version |
| Notification fatigue | Ignore real opportunities | Tight threshold (75+); daily digest option as alternative to per-job alerts |

---

## File Structure

```text
recall-local/
├── config/
│   ├── auto_tag_rules.json          # Existing
│   ├── career_pages.json            # NEW: Target company career page configs
│   └── job_search.json              # NEW: Search titles, locations, thresholds
├── docs/
│   ├── Recall_local_PRD.md          # Existing
│   ├── Recall_local_Phase0_Guide.md # Existing
│   ├── Recall_local_Phase6_Job_Hunt_PRD.md  # THIS DOCUMENT
│   └── scaffolds/
│       └── luxury-minimal.jsx       # Design reference for Daily Dashboard theme
├── scripts/
│   ├── phase1/
│   │   └── ingest_bridge_api.py     # Existing bridge API entrypoint; add Phase 6 `/v1/*` routes here
│   └── phase6/
│       ├── setup_collections.py      # NEW: Create Qdrant collections
│       ├── ingest_resume.py          # NEW: CLI resume ingestion
│       ├── job_evaluator.py          # NEW: Ollama/cloud evaluation logic
│       ├── job_dedup.py              # NEW: Deduplication logic
│       ├── gap_aggregator.py         # NEW: Cross-job gap analysis
│       ├── company_profiler.py       # NEW: Company profile generation
│       ├── telegram_notifier.py      # NEW: Telegram push notifications
│       ├── job_metadata_extractor.py # NEW: Extract job data from raw page content
│       └── job_discovery_runner.py   # NEW: JobSpy/Adzuna/Serp orchestration runner
├── ui/
│   └── daily-dashboard/              # NEW: Separate React/Vite app
│       ├── src/
│       │   ├── App.jsx
│       │   ├── components/
│       │   │   ├── JobHuntPanel.jsx
│       │   │   ├── JobCard.jsx
│       │   │   ├── JobDetail.jsx
│       │   │   ├── SkillGapRadar.jsx
│       │   │   ├── ScoreDistribution.jsx
│       │   │   ├── StatsBar.jsx
│       │   │   ├── Filters.jsx
│       │   │   ├── CompanyProfile.jsx
│       │   │   ├── CompanyList.jsx
│       │   │   ├── SettingsPanel.jsx
│       │   │   └── FutureWidgetSlot.jsx
│       │   ├── hooks/
│       │   │   ├── useJobs.js
│       │   │   ├── useCompanies.js
│       │   │   └── useSettings.js
│       │   └── styles/
│       │       └── theme.css
│       ├── Dockerfile
│       ├── nginx.conf
│       ├── package.json
│       └── vite.config.js
├── n8n/
│   └── workflows/
│       └── phase6/
│           ├── README.md
│           ├── workflow1_aggregator.md
│           ├── workflow2_career_pages.md
│           └── workflow3_evaluate_notify.md
└── docker/
    └── docker-compose.yml            # Updated with daily-dashboard service
```

---

## Appendix: Interview Talking Points

This project is designed to be demonstrable in an SE interview. Key talking points:

1. **"I built an AI-powered job search pipeline that runs entirely on my own hardware."** — Demonstrates: systems thinking, practical AI application, self-hosting philosophy.

2. **"It uses RAG to compare job descriptions against my resume and produces structured evaluations."** — Demonstrates: RAG pipeline expertise, prompt engineering, structured output handling.

3. **"Jobs are deduplicated using both exact URL matching and semantic similarity via vector search."** — Demonstrates: vector database knowledge, practical Qdrant usage.

4. **"The system aggregates skill gaps across all evaluated jobs to tell me what to study."** — Demonstrates: data analysis, product thinking, feedback loop design.

5. **"I built the n8n workflows collaboratively with an AI coding agent, which is how modern SE teams will work."** — Demonstrates: AI-augmented development, workflow automation, exactly what an SE would help customers do.

---

*Document Version: 1.0*
*Location: `docs/Recall_local_Phase6_Job_Hunt_PRD.md`*
*Status: Ready for Codex handoff*
