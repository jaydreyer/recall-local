# Recall.local — Local AI Operations Agent (Focused PRD v2.1)

**One-liner:** Recall.local is a privacy-first, local AI operations agent that ingests messy inputs (documents, logs, notes), builds searchable memory (vector + structured), and executes reliable automations with full auditability.

**Author:** Jay  
**Version:** 2.1 — Focused Scope + Frictionless Ingestion  
**Date:** February 2026

---

## 1. Strategic Context

Recall.local is a capstone portfolio project designed to demonstrate end-to-end AI system design: RAG pipelines, workflow orchestration, prompt engineering, safety guardrails, and observability. It targets Solutions Engineer interview panels at AI-first companies (Anthropic, OpenAI, Cohere, Glean, Writer) where candidates must prove they can design, ship, and explain cohesive systems.

### 1.1 What Makes This Credible

Most AI portfolio projects are chat toys: they answer questions but don't integrate, don't remember, don't act, and aren't auditable. Recall.local differentiates by combining vector memory, structured state, automated workflows, source attribution, and audit trails into a single system that runs entirely on local hardware.

### 1.2 Design Philosophy

> **Core Principle: Polish beats breadth.**  
> Two workflows at 100% are more impressive than five workflows at 70%. Every feature ships with citations, audit trails, and error handling — or it doesn't ship.

- **Depth over width:** Fewer features, fully hardened with eval tests and error recovery
- **Demo-first:** Every capability must be showable in a live 10-minute walkthrough
- **Cloud escape hatch:** Architecture supports swapping local LLMs for API calls via one environment variable, providing demo insurance and a talking point about privacy vs. capability tradeoffs
- **Artifacts are the product:** Markdown outputs (checklists, action items, audit logs) are the deliverable, not a dashboard CRUD table
- **Frictionless ingestion:** If it takes more than 10 seconds to get content into Recall from any device, the ingestion design has failed

---

## 2. Success Metrics

### 2.1 Functional Success

| Metric | Criteria |
|---|---|
| Ingestion | Drop a document into /data/incoming → searchable in Qdrant within 5 minutes |
| Multi-source ingestion | Gmail attachments, web URLs, Google Docs, and mobile shares all reach Recall with ≤2 taps/clicks |
| RAG Quality | Answers include doc_id + chunk_id citations; zero fabricated citations in eval suite |
| Meeting → Actions | Webhook accepts transcript, returns structured action items with owners and dates as Markdown artifact |
| Audit Trail | Every response returns: sources used, run ID, model name, timestamp, artifact path |
| Eval Harness | 10–30 known questions pass nightly: cited answer present, citations map to real chunks, latency < threshold |

### 2.2 Demo Success (10-Minute Script)

1. **Ingest (multi-source):** Show a PDF dropped in a folder, a URL submitted via the share sheet, and a Gmail attachment auto-forwarded — all indexed in Qdrant
2. **RAG Query:** Ask a question, receive a cited answer with doc_id and chunk_id
3. **Meeting Notes:** Paste a transcript, receive structured action items with owners and dates
4. **Audit:** Show run IDs, saved Markdown artifacts, and citation payloads
5. **Eval Report:** Show the green/red test results from the eval harness
6. **Architecture Walkthrough:** Explain the system diagram, tradeoffs, and cloud escape hatch

---

## 3. Non-Goals (Scope Boundaries)

Keeping scope tight is the single most important risk mitigation for this project. The following are explicitly out of scope for v1:

- **Daily digest workflow:** Low demo impact, high risk of underwhelming output from local models. Revisit in v2 only if core workflows are bulletproof.
- **Custom web dashboard:** Time sink with poor ROI. Artifact browsing via MkDocs or a static file server provides 80% of the value.
- **LLM-powered intent router:** Fragile with small local models. Use explicit mode selection (user picks RAG, Meeting Notes, or Log Triage from a menu) in v1. Architecture diagram can still show a router.
- **Log Triage workflow in v1 core scope:** Defer to stretch goal. Meeting → Actions is more universally relatable and better for demos.
- **Multi-user auth/roles:** Design for it, don't implement.
- **Web browsing or autonomous agents:** Out of scope entirely.
- **High-stakes actions without confirmation:** No silent deletes, purchases, or external messages.
- **Full web scraping / rendering engine:** URL ingestion extracts readable content via Readability/Trafilatura, not a headless browser.

---

## 4. System Architecture

### 4.1 Core Stack

| Component | Technology | Role |
|---|---|---|
| LLM Runtime | Ollama (+ cloud API toggle) | Routing, generation, embeddings |
| Chat UI | Open WebUI | Prompt templates and user interaction |
| Vector Store | Qdrant | Semantic search / RAG memory |
| Orchestration | n8n | Workflow automation |
| Structured State | SQLite (v1) / Postgres (v2) | Run history, alerts, eval results |
| Artifact Viewer | MkDocs / static file server | Browseable output artifacts |
| LLM Observability | Langfuse (self-hosted, Phase 2) | Trace every LLM call, score responses, debug RAG failures |
| Ingestion Gateway | n8n webhooks + email listener | Multi-source content intake |

### 4.2 Dual Memory Model

This is the key architectural differentiator. Recall.local maintains two complementary memory systems:

- **Vector memory (Qdrant):** Document chunks with embeddings for semantic retrieval. Enables "chat over your content" with source attribution.
- **Structured memory (SQLite/Postgres):** Entities, tasks, run history, and eval results. Enables "system with state" — audit trails, reliability metrics, and cross-referencing.

Together, these allow Recall.local to both answer questions about content and maintain operational awareness of what it has done and how well it performed.

### 4.3 Cloud Escape Hatch

> **Architecture Decision: Model Swappability**  
> Every LLM call routes through a thin abstraction layer. A single environment variable (`RECALL_LLM_PROVIDER=ollama|anthropic|openai`) switches between local and cloud inference. This provides demo insurance when local model quality is insufficient, and creates a natural interview talking point about privacy vs. capability tradeoffs.

With the RTX 2060 (6GB VRAM), local models are limited to 7–8B parameters. Structured JSON output and citation accuracy are inconsistent at this scale. The escape hatch ensures the demo never fails due to model quality, while the local-first architecture remains the default. (See **Appendix A** for how the RTX 3060 12GB upgrade changes this calculus.)

---

## 5. Frictionless Ingestion (New in v2.1)

This is about making Recall.local something you actually *use* daily, not just demo. The ingestion surface must meet users where they already are: laptop, phone, email, browser.

### 5.1 Design Principle

> **The 10-Second Rule:** Getting content into Recall from any device or context should take no more than 10 seconds and no more than 2 intentional actions (tap/click/forward).

### 5.2 Ingestion Channels

| Channel | Method | Complexity | Phase |
|---|---|---|---|
| **Local folder drop** | Folder watcher on /data/incoming | Low — already planned | Phase 1 |
| **URL / webpage** | n8n webhook accepts a URL → Trafilatura/Readability extracts clean text → chunked and indexed | Low-Med | Phase 1 |
| **Gmail attachment** | Gmail filter auto-forwards matching emails to a dedicated Recall.local email → n8n email trigger parses attachment → ingestion pipeline | Medium | Phase 1 |
| **Google Doc** | n8n Google Docs node fetches doc by URL/ID → extracts text → ingestion pipeline | Medium | Phase 2 |
| **iOS/Android share** | iOS Shortcut / Android Share target sends selected text or URL to n8n webhook | Low | Phase 1 |
| **Tweet / social post** | Share URL from app → webhook extracts text content | Low | Phase 1 |
| **Browser extension** | Bookmarklet or lightweight extension sends page content/URL to webhook | Low-Med | Phase 2 |
| **Manual paste** | Open WebUI prompt template: "Ingest this" + paste text block | Low — trivial | Phase 1 |

### 5.3 Channel Details

#### URL Ingestion (Web Pages, Articles, Manuals)
The n8n webhook receives a URL, then:
1. Fetches the page via HTTP
2. Extracts clean readable content using **Trafilatura** (Python, excellent at stripping nav/ads/chrome) or **Mozilla Readability** (JS)
3. Preserves title, URL source, and extraction timestamp as metadata
4. Feeds into the standard chunking → embedding → Qdrant pipeline

This handles user manuals, blog posts, documentation pages, tweets (via URL), and most web content without a headless browser.

#### Gmail Integration
Two approaches, in order of simplicity:

**Option A — Forward-to-ingest (simplest, Phase 1):**
- Set up a dedicated email address (e.g., `recall@yourdomain.com` or a Gmail alias with a filter)
- Gmail filter: any email matching a label/keyword auto-forwards to this address
- n8n email trigger (IMAP) watches the inbox, extracts attachments and/or body text
- Attachments route to the file ingestion pipeline; body text routes to the text pipeline
- You forward an email manually or set up rules — either way, it's one action

**Option B — Gmail API via n8n (richer, Phase 2):**
- n8n Gmail node with OAuth watches for specific labels or search queries
- More control: filter by sender, subject pattern, attachment type
- Can auto-ingest all attachments from specific senders (e.g., your accountant, your team)

#### Mobile (iOS Shortcut / Android Share)
This is the highest-leverage low-effort channel:

**iOS Shortcut:**
- Create a Shortcut that accepts text or URLs from the Share Sheet
- Shortcut sends a POST request to the Recall.local n8n webhook with the shared content
- Content type detected automatically (URL → URL pipeline, text → text pipeline)
- From any app: highlight text or tap share → "Send to Recall" → done

**Android equivalent:**
- Tasker or HTTP Shortcuts app sends to the same webhook
- Same Share Sheet integration pattern

The webhook is the same one used for URL ingestion — the mobile shortcut is just a thin client that sends content to it.

#### Google Docs
- n8n has a native Google Docs node
- Webhook receives a Google Doc URL → extracts doc ID → n8n fetches content via API → ingestion pipeline
- Alternatively, the iOS/Android share sheet can share a Google Doc URL, which routes through the URL handler with special-case logic for `docs.google.com` URLs

### 5.4 Unified Webhook Design

All non-folder ingestion channels converge on a single n8n webhook endpoint:

```
POST /webhook/recall-ingest
{
  "type": "url" | "text" | "email" | "gdoc",
  "content": "https://..." | "raw text..." | "doc-id-here",
  "source": "ios-shortcut" | "browser" | "gmail" | "manual",
  "metadata": {
    "title": "optional override",
    "tags": ["optional", "tags"]
  }
}
```

The webhook routes to the appropriate extraction method based on `type`, then feeds into the shared chunking → embedding → Qdrant pipeline. This means adding a new ingestion channel in the future is just building a new thin client that POSTs to this endpoint.

### 5.5 Demo Impact

Frictionless ingestion significantly upgrades the demo script. Instead of just dropping a file in a folder, you can show:

1. Drop a PDF in a folder (local)
2. Share a URL from your phone and watch it appear in Qdrant within seconds
3. Forward an email with an attachment, show it indexed
4. Ask a question that synthesizes information from all three sources

This tells a much more compelling story about practical daily use.

---

## 6. Data Model

### 6.1 Qdrant Collections

#### recall_docs (Primary)
PDFs, notes, manuals, web pages, meeting transcripts — chunked with heading-aware splitting and token limits.

| Field | Type | Purpose |
|---|---|---|
| source | string | File path, URL, or email reference of original |
| source_type | string | `file`, `url`, `email`, `gdoc`, `paste` |
| doc_id | string (UUID) | Unique document identifier |
| chunk_id | string | Unique chunk identifier for citation |
| title | string | Document or section title |
| created_at | datetime | Ingestion timestamp |
| tags[] | string array | Classification tags (auto + manual) |
| ingestion_channel | string | How it arrived: `folder`, `webhook`, `email`, `share` |

#### recall_preferences (Secondary)
Stable user preferences: formatting rules, device inventory, personal context. Low churn, high value for personalized responses.

### 6.2 Structured DB Tables (SQLite v1)

| Table | Key Fields |
|---|---|
| runs | run_id, workflow, status, started_at, ended_at, model, latency_ms, input_hash, output_path |
| eval_results | eval_id, question, expected_doc_id, actual_doc_id, citation_valid, latency_ms, passed, run_date |
| alerts | alert_id, severity, created_at, status, summary, run_id |
| ingestion_log | ingest_id, source_type, source_ref, channel, doc_id, chunks_created, status, timestamp |

The new `ingestion_log` table tracks every piece of content that enters the system, regardless of channel — useful for debugging, auditing, and the demo.

---

## 7. Core Workflows (n8n)

The focused scope includes three core workflows plus the ingestion gateway. Each must be fully hardened with error handling, structured output validation, and retry logic before moving to the next.

### 7.1 Workflow 01 — Document Ingestion (Multi-Source)

**Trigger:** Folder watcher on /data/incoming OR unified ingestion webhook

#### Pipeline Steps
1. Detect input type: file (from folder watcher) or webhook payload (URL, text, email, gdoc)
2. **Route by type:**
   - File → extract text (PDF parser for PDFs, direct read for text/markdown)
   - URL → fetch page → extract with Trafilatura → clean text
   - Email → parse attachment (→ file pipeline) or body (→ text pipeline)
   - Google Doc → fetch via API → clean text
   - Raw text/paste → use directly
3. Chunk with heading-aware splitting + configurable token limit
4. Generate embeddings via Ollama embedding model
5. Upsert chunks to Qdrant `recall_docs` with full metadata (including `source_type` and `ingestion_channel`)
6. If file: move original to /data/processed
7. Log to SQLite `runs` and `ingestion_log` tables

**Output:** Indexed chunks in Qdrant + run record + ingestion log entry

### 7.2 Workflow 02 — RAG Query (Cited Answers)

**Trigger:** Webhook from Open WebUI prompt template or direct API call

#### Pipeline Steps
1. Receive query with explicit mode selection (no LLM router in v1)
2. Generate query embedding via Ollama
3. Search Qdrant `recall_docs` with configurable top-k and score threshold
4. Assemble context window: query + retrieved chunks + RAG answer prompt
5. Generate answer via Ollama (or cloud API if escape hatch enabled)
6. Validate response structure: citations present, doc_ids map to real chunks, no fabricated sources
7. If validation fails: retry with stricter prompt or return error with explanation
8. Return response JSON with answer, citations[], and audit metadata

> **Output Validation (Critical for Local Models):**  
> Every RAG response passes through a validation layer that checks: (a) citations are present, (b) cited doc_ids exist in Qdrant, (c) response follows structured format. Malformed outputs trigger a retry with a stricter prompt before falling back to error. This is essential given the inconsistency of 7–8B models with structured output.

### 7.3 Workflow 03 — Meeting → Action Items

**Trigger:** Webhook with meeting transcript or notes

#### Pipeline Steps
1. Receive transcript text via webhook
2. Call LLM with meeting extraction prompt requiring structured JSON output
3. Validate extracted structure: action items have owners, dates, descriptions
4. Generate Markdown artifact saved to /data/artifacts/meetings/
5. Upsert meeting summary to `recall_docs` for future RAG retrieval
6. Log run to SQLite `runs` table

**Output:** Markdown artifact with decisions, action items (owner + date), risks, and follow-ups + summary indexed in Qdrant for future search.

---

## 8. Stretch Goal: Cross-Reference Discovery

If core workflows are solid, this single feature creates the "wow moment" in demos.

> **The "Second Brain" Moment:**  
> When a new document is ingested, Recall.local automatically queries Qdrant for semantically similar existing content and surfaces connections the user didn't ask for. "This new meeting transcript references Project Aurora — here are 3 related documents already in your memory." This is what makes the system feel like a genuine second brain rather than a search box.

### Implementation
- After ingestion (Workflow 01), take the top 3 chunks from the new document
- Run similarity search against existing `recall_docs` (excluding the new document itself)
- If matches exceed a confidence threshold, generate a brief cross-reference note
- Save the cross-reference as a linked artifact and optionally notify the user

This is a natural extension of the existing RAG pipeline and requires no new infrastructure — just an additional step in the ingestion workflow.

---

## 9. Prompt Engineering

Prompts are versioned files stored in `/prompts/` and require structured outputs. This is the product quality layer — the difference between a demo that impresses and one that looks like a hack.

### 9.1 RAG Answer Prompt
- Must cite sources using doc_id and chunk_id from retrieved context
- Must list assumptions and uncertainty explicitly
- Fabricated citations are forbidden — prompt includes explicit instruction and output validation enforces it
- Format: structured JSON with answer, citations[], confidence_level, and assumptions[]

### 9.2 Meeting Extraction Prompt
- Must extract: decisions, action_items (each with owner, due_date, description), risks, follow_ups
- Output: structured JSON, validated before artifact generation
- Graceful handling of incomplete transcripts (mark fields as "unspecified" rather than hallucinating)

### 9.3 Log Triage Prompt (Stretch)
- Format: Symptoms → Likely causes → Diagnostic tests → Safe actions → Risky actions (confirm first)
- Requires explicit risk labeling on every recommended action

---

## 10. Evaluation Harness (Build Early)

> **Why This Ships in Phase 1, Not Phase 4:**  
> A green/red eval report is more impressive to interviewers than three extra workflows. It proves you think about reliability, not just features. Build it alongside RAG, not after.

### 10.1 Eval Design
A nightly (or on-demand) smoke test that runs 10–30 predefined questions against the RAG pipeline and checks three things:

1. **Citation presence:** Does the response include at least one citation?
2. **Citation validity:** Do the cited doc_ids and chunk_ids exist in Qdrant?
3. **Latency:** Is end-to-end response time below the configured threshold?

### 10.2 Eval Output
- Results stored in SQLite `eval_results` table for trend tracking
- Summary Markdown artifact saved to /data/artifacts/evals/
- Overall pass/fail status with per-question breakdown
- Latency percentiles (p50, p95) tracked over time

This harness also serves as regression testing: when you change prompts, chunking strategy, or models, the eval catches regressions before they reach the demo.

### 10.3 LLM Observability: Langfuse (Phase 2)

The eval harness captures pass/fail outcomes. Langfuse captures *why* — the full trace of every LLM call: the assembled prompt, retrieved chunks, raw model response, latency, and token count. When the eval harness flags a bad citation, Langfuse shows whether it was a retrieval problem (wrong chunks from Qdrant), a generation problem (model ignored the chunks), or a prompt problem (instructions weren't clear enough).

**Why Langfuse over LangSmith:** Langfuse is open source and self-hostable, consistent with Recall.local's privacy-first architecture. LangSmith is cloud-only and tied to the LangChain ecosystem, which this stack doesn't use. Langfuse runs as a Docker container alongside the rest of the stack with zero data leaving the network.

**Integration:** Add Langfuse decorators to `llm_client.py` — every `generate()` and `embed()` call is automatically traced. No changes to n8n workflows or prompts required.

**Demo value:** In an interview, pulling up Langfuse and walking through the full trace of a RAG query (retrieval → prompt assembly → generation → validation → scored response) is a strong finishing move that demonstrates production-grade observability thinking.

---

## 11. Safety, Privacy, and Auditability

### 11.1 Safety Rails
- **Allowlisted ingestion:** Only /data/incoming, the unified webhook, and the email listener are monitored
- **Confirmation gates:** Any workflow that sends external messages, deletes files, or creates alerts requires explicit user confirmation
- **Upload limits:** Rate limiting and file size caps on ingestion (webhook and email channels)
- **Output validation:** All LLM outputs are validated before being saved or returned
- **URL allowlist/blocklist:** Optional domain filtering on URL ingestion to prevent accidental ingestion of sensitive sites

### 11.2 Audit Trail (Every Response)

| Field | Description |
|---|---|
| citations[] | doc_id + chunk_id for each source used in the response |
| run_id | Unique identifier for the workflow execution |
| model | Model name and provider (e.g., llama3:8b via ollama) |
| timestamp | ISO 8601 timestamp of response generation |
| latency_ms | End-to-end processing time |
| artifact_path | File path to any saved Markdown artifact |

---

## 12. Phased Delivery Plan

Three phases instead of four. Each phase has hard exit criteria that must be met before advancing. Frictionless ingestion is woven into Phases 1 and 2 rather than treated as a separate phase.

### Phase 0 — Foundation

**Goal:** All services running and communicating.

- Repo skeleton + Docker Compose with shared volumes (/data/incoming, /data/processed, /data/artifacts)
- Qdrant running with health check endpoints
- SQLite initialized with `runs`, `eval_results`, and `ingestion_log` tables
- LLM abstraction layer with `RECALL_LLM_PROVIDER` environment variable
- MkDocs or static file server serving /data/artifacts
- Trafilatura / Readability installed for URL extraction

**Exit Criteria:** All services start, can communicate, and LLM calls work through both Ollama and at least one cloud provider.

### Phase 1 — RAG MVP + Multi-Source Ingestion + Eval Harness (Showable)

**Goal:** Drop content from multiple sources, ask cited questions, prove reliability.

- Workflow 01: Document ingestion via folder watcher AND unified webhook (file, URL, text, email)
- Workflow 02: RAG query with cited answers (doc_id + chunk_id)
- iOS Shortcut that shares URLs/text to the webhook
- Gmail forward-to-ingest pipeline (Option A)
- Output validation layer with retry logic
- Eval harness: 10+ questions with citation and latency checks
- Eval results stored in SQLite and rendered as Markdown artifact

**Exit Criteria:** Drop a PDF, share a URL from your phone, and forward an email attachment — all three are searchable in Qdrant. Ask 3 questions → all answers include valid citations. Eval harness runs green. Results browseable in artifact viewer.

### Phase 2 — Meeting Workflow + Polish (Demo-Ready)

**Goal:** Full demo script works reliably end-to-end.

- Workflow 03: Meeting → Action Items with structured extraction
- Google Docs ingestion via n8n Google Docs node
- Browser bookmarklet (optional)
- Artifact viewer showing all outputs (ingestion reports, cited answers, action items, eval results)
- Audit trail visible on every response
- Cross-reference discovery (stretch goal) if time permits
- Langfuse (self-hosted) for LLM observability — full trace view of every LLM call (prompt in, response out, latency, token count) with the ability to score and tag responses. Instrument via `llm_client.py` decorators. Provides a polished UI for the demo that shows the full RAG pipeline trace: retrieval → prompt assembly → generation → validation.
- Demo script rehearsed and reliable

**Exit Criteria:** The full 10-minute demo script (Section 2.2) runs without failure. All artifacts are browseable. Audit trail is visible on every response. Multi-source ingestion works from at least 3 channels.

---

## 13. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Local model output quality | High | Cloud escape hatch + output validation + retry logic. Test all prompts on both local and cloud models. |
| Scope creep | High | Hard non-goals list. Phase exit criteria enforced. No Phase 2 without Phase 1 fully green. |
| Chunking quality | Medium | Heading-aware chunking + configurable overlap. Eval harness catches retrieval regressions. |
| Demo failure (live) | Medium | Pre-loaded documents in Qdrant. Cloud API as fallback. Rehearsed script with known-good inputs. |
| n8n complexity | Low-Med | Keep workflows simple. Python scripts for heavy logic, n8n for orchestration only. |
| URL extraction quality | Medium | Trafilatura handles most sites well. Fallback to raw HTML parsing. Test against target sites early. |
| Gmail/email reliability | Low-Med | Forward-to-ingest is simple IMAP. Test with common attachment types (PDF, DOCX, images). |
| Mobile shortcut fragility | Low | iOS Shortcuts are stable for HTTP POST. Test on actual device during Phase 1. |

---

## 14. Repository Layout

Streamlined layout reflecting the focused scope:

| Path | Purpose |
|---|---|
| docker/docker-compose.yml | Service definitions (Ollama, Qdrant, n8n, Open WebUI, MkDocs) |
| docker/env.example | Environment config including RECALL_LLM_PROVIDER |
| n8n/workflows/ | Exported n8n workflow JSON files |
| prompts/ | Versioned prompt templates (RAG, meeting, router) |
| scripts/ | Python utilities (chunking, validation, URL extraction) |
| scripts/eval/ | Eval harness + test question bank |
| scripts/extract/ | Trafilatura wrapper, PDF parser, email parser |
| shortcuts/ | iOS Shortcut export, Android HTTP Shortcuts config |
| data/incoming/ | Drop zone for new documents |
| data/processed/ | Archived originals after ingestion |
| data/artifacts/ | Generated outputs (meetings, evals, reports) |
| docs/ | Architecture diagrams, MkDocs content |

---

## 15. Resume Bullets (Copy-Ready)

**Recall.local — Local AI Operations Agent (Ollama, Open WebUI, Qdrant, n8n)**

- Built a privacy-first AI agent platform with dual memory (vector + structured), cited RAG retrieval, and automated meeting-to-action-item extraction, running entirely on local hardware with a cloud API escape hatch.
- Designed frictionless multi-source ingestion (folder watch, URL extraction, Gmail forwarding, mobile share sheet) converging on a unified webhook, enabling daily use as a true "second brain."
- Engineered output validation and retry logic for reliable structured outputs from local LLMs, with a nightly eval harness (10–30 test cases) tracking citation accuracy and latency regression.
- Designed for auditability: every response includes source citations, workflow run IDs, model provenance, and browseable Markdown artifacts — demonstrating production-grade thinking in a portfolio project.

---

## 16. Key Changes from Original PRD

| Area | Original (v1) | Focused (v2) | v2.1 Update |
|---|---|---|---|
| Workflows | 5 workflows | 3 core + 1 stretch | Unchanged |
| Dashboard | Custom web app | MkDocs / static artifact viewer | Unchanged |
| Chat Router | LLM-powered intent classification | Explicit mode selection (menu) | Unchanged |
| Eval Harness | Phase 4 (hardening) | Phase 1 (core deliverable) | Unchanged |
| LLM Provider | Ollama only | Ollama + cloud escape hatch | Unchanged |
| Output Validation | Not specified | Validation + retry on every LLM call | Unchanged |
| Delivery Phases | 4 phases | 3 phases with hard exit criteria | Unchanged |
| "Wow" Feature | Breadth of features | Cross-reference discovery | Unchanged |
| **Ingestion** | **Folder watcher only** | **Folder watcher only** | **Multi-source: folder, URL, email, mobile share, Google Docs** |
| **Ingestion UX** | **Not addressed** | **Not addressed** | **10-Second Rule + unified webhook architecture** |
| **LLM Observability** | **Not addressed** | **Not addressed** | **Langfuse (self-hosted) in Phase 2 for full LLM call tracing** |
| **GPU guidance** | **Not addressed** | **Not addressed** | **Appendix A: RTX 3060 12GB upgrade analysis** |

---

## Appendix A: RTX 3060 12GB Upgrade Impact

### Current State: RTX 2060 6GB VRAM

| Constraint | Impact on Recall.local |
|---|---|
| Model size limit | ~7–8B parameters quantized (Q4). Llama 3 8B, Mistral 7B, Phi-3 Mini are the ceiling. |
| Structured output | Inconsistent JSON compliance. The router prompt and citation formatting frequently require retries. |
| Embedding models | Limited to smaller embedding models; nomic-embed-text (137M params) fits comfortably. |
| Context window | Practically limited to ~4K–8K tokens with 7B models at Q4 before VRAM pressure causes slowdowns. |
| Concurrent requests | Essentially single-request. Running embeddings while generating text causes OOM or severe throttling. |

### Upgraded State: RTX 3060 12GB VRAM

The 3060 12GB doubles available VRAM. Here's what that concretely changes:

#### What Opens Up

| Capability | 2060 (6GB) | 3060 (12GB) | Recall.local Impact |
|---|---|---|---|
| **Max model size** | 7–8B Q4 | 13B Q4 or 7–8B Q6/Q8 | Llama 3 13B and Mixtral 8x7B (with offloading) become viable. Significantly better structured output compliance and reasoning. |
| **Quantization quality** | Q4 only (noticeable quality loss) | Q5/Q6 for 7–8B models | Same model, meaningfully better output quality. Fewer retries needed. |
| **Context window** | ~4–8K practical | ~8–16K practical | Can fit more retrieved chunks in RAG context. Better answers with more evidence. |
| **Embedding + generation** | One at a time | Can overlap with headroom | Ingestion (embedding) doesn't block query answering as hard. |
| **Specialized models** | One model loaded | Can swap faster, or run smaller models alongside | Could keep embedding model warm while swapping generation models. |

#### What This Means for Recall.local Specifically

**Reduces reliance on the cloud escape hatch.** The primary reason for the escape hatch is that 7B Q4 models produce unreliable structured JSON. A 13B model (or a 7B at Q6) is substantially more reliable at following formatting instructions. You may find that local-only works well enough for most demo scenarios, making the escape hatch a genuine architectural feature rather than a crutch.

**Better RAG quality.** With a larger context window, you can include more retrieved chunks (top-5 or top-7 instead of top-3) and still have room for the prompt template. More evidence → better cited answers → fewer hallucinations.

**Faster iteration.** Higher quantization means less time spent debugging malformed outputs and tweaking prompts to compensate for model limitations. This directly translates to shipping faster.

**Embedding throughput.** The 3060 handles batch embedding more comfortably. Ingesting a 50-page PDF (hundreds of chunks) won't bottleneck the system as badly.

#### What Doesn't Change

- **Architecture:** The cloud escape hatch, output validation, and retry logic remain valuable regardless of GPU. Good engineering doesn't become unnecessary with better hardware.
- **Eval harness:** Still essential. Better models still hallucinate — just less often.
- **Prompt engineering:** Still the product quality layer. A 13B model with bad prompts loses to a 7B model with great prompts.
- **n8n workflows:** Entirely GPU-independent.

#### Recommendation

**The upgrade is worth it, but it's not blocking.** Build Recall.local on the 2060 with the cloud escape hatch. The architecture is designed to work at any model quality level. When you upgrade to the 3060, you'll immediately see improvements in output reliability and can gradually reduce cloud fallback usage. The upgrade is most impactful *after* the system is built — it's a quality multiplier, not a prerequisite.

If you're buying the card anyway, do it before Phase 1 so you can develop and test against the better hardware from the start. But if budget timing is a factor, the 2060 + cloud escape hatch is a perfectly viable development platform.

#### Cost-Benefit Summary

| Factor | Assessment |
|---|---|
| Price (used RTX 3060 12GB) | ~$200–250 |
| Primary benefit | 13B models and higher quantization → reliable structured output |
| Secondary benefit | Larger context windows → better RAG quality |
| Impact on project timeline | Reduces debugging time, fewer prompt workarounds |
| Required for Recall.local? | No — cloud escape hatch covers the gap |
| Recommended? | Yes, especially if purchased before Phase 1 |

---

*End of Document*
