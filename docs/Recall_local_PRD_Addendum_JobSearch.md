# Recall.local PRD — Addendum: Job Search RAG Configuration
**Addendum to:** Recall.local PRD v2.1  
**Author:** Jay  
**Version:** 1.0  
**Date:** February 2026  
**Scope:** Two targeted additions to the base Recall.local design to support a job search use case running on the same infrastructure. No new collections, no new workflows, no new services.

---

## 1. What This Addendum Covers

The base Recall.local PRD (v2.1) provides everything needed for a job search RAG assistant except two things:

1. **Tag-scoped retrieval** — the ability to filter Qdrant queries to job-search-tagged documents only, so a job search query doesn't surface irrelevant content from other use cases
2. **A job-search prompt template** — a system prompt that applies retrieved context through a career coaching lens rather than returning raw retrieval results

These are additive changes. Nothing in the base PRD needs to be removed or restructured.

---

## 2. Document Corpus

The following documents should be ingested into `recall_docs` with `tags: ["job-search"]` at ingestion time. These are the authoritative sources for job search queries.

| Document | Source Type | Notes |
|---|---|---|
| Jay's current resume | `file` (PDF or DOCX) | Re-ingest whenever updated |
| SE Guide (the comprehensive PM-to-SE guide) | `file` | Already exists as a project doc |
| AI Career Acceleration Plan | `file` | Already exists as a project doc |
| Recall.local PRD | `file` | Useful for interview Q&A about the project |
| Target company job descriptions | `url` or `paste` | One per company; re-ingest when JDs change |
| Target company "About" / mission pages | `url` | Anthropic, OpenAI, Cohere, Glean, Writer |
| Target company API / product documentation | `url` | Especially Anthropic docs.anthropic.com |
| Interview prep notes | `paste` | Add as prep sessions accumulate |
| SE Interview Q&A reference doc | `file` | Living document; re-ingest periodically |

**Ingestion tagging requirement:** Every job search document must be tagged `job-search` at ingestion time. Use the existing `tags[]` field in the `recall_docs` Qdrant payload. Additional specificity tags are optional but useful (e.g., `anthropic`, `jd`, `resume`, `prep`).

**Re-ingestion policy:** Job descriptions and prep notes change frequently. When a document is updated, replace old chunks by stable source identity (`source_key`/canonical source) before re-ingesting. Do not allow stale JDs to accumulate — retrieved results from an old JD will silently degrade answer quality.

---

## 3. Required Change: Tag-Scoped Retrieval in Workflow 02

### 3.1 The Problem

Workflow 02 currently searches all of `recall_docs` without filtering by tag. Once Recall.local is in daily use across multiple domains (job search, meeting notes, general research), a job search query like "What should I emphasize for the Anthropic SE role?" will retrieve semantically adjacent but irrelevant chunks — home server notes, personal research, etc. — degrading answer quality.

### 3.2 The Change

Add an optional `filter_tags` parameter to the Workflow 02 webhook payload. When present, the Qdrant query applies a payload filter restricting results to documents matching all specified tags.

**Updated webhook payload (Workflow 02):**
```json
{
  "query": "What should I emphasize for the Anthropic SE role?",
  "mode": "rag",
  "filter_tags": ["job-search"],
  "top_k": 5
}
```

**Qdrant query change:**  
Add a `must` filter on the `tags` payload field when `filter_tags` is present. When `filter_tags` is absent or empty, behavior is unchanged — full collection search.

```python
# Pseudocode for the retrieval call
filter = None
if filter_tags:
    filter = Filter(
        must=[FieldCondition(key="tags", match=MatchAny(any=filter_tags))]
    )

results = qdrant_client.search(
    collection_name="recall_docs",
    query_vector=query_embedding,
    query_filter=filter,
    limit=top_k
)
```

**Impact on existing functionality:** Zero. `filter_tags` is optional. All existing queries without it behave identically to the current design.

### 3.3 Open WebUI Integration

Create a dedicated Open WebUI prompt template for job search queries that pre-populates `filter_tags: ["job-search"]` in the webhook call. Users select "Job Search" mode from the template menu — no manual parameter entry required.

---

## 4. Required Addition: Job Search Prompt Template

### 4.1 File Location

`/prompts/job_search_coach.md`

This is a versioned prompt file consistent with the prompt management approach in Section 9 of the base PRD.

### 4.2 Prompt Template

```
SYSTEM:
You are a career coach helping Jay Dreyer prepare for Solutions Engineer roles at AI companies. Jay has 25 years of enterprise technical product experience — API governance, developer enablement, AI chatbot implementation, and production application development. He is not a PM pivoting to tech; he is a technical operator formalizing SE work he has been doing for years.

Use the provided context (retrieved from Jay's resume, job descriptions, company research, and interview prep materials) to give specific, actionable coaching. Apply the retrieved content to Jay's situation — don't just summarize what's in the documents.

BEHAVIORAL GUIDELINES:
- Frame answers in terms of what Jay should say or do, not just what the documents contain
- When referencing a job description, connect specific JD requirements to specific items in Jay's background
- When Jay asks how to answer an interview question, give him a draft answer using his actual experience — not a generic framework
- Call out self-minimizing language if Jay uses it; redirect to enterprise value framing
- Be direct. Do not hedge or soften assessments of what is or isn't working in his positioning.
- If retrieved context is insufficient to answer the question well, say so explicitly rather than hallucinating an answer

CITATION REQUIREMENT:
Cite the specific document and chunk used for each claim. Format: [Source: {title}, chunk {chunk_id}]

USER QUERY:
{query}

CONTEXT:
{retrieved_chunks}
```

### 4.3 Usage Notes

- The "self-minimizing language" instruction is intentional — this is a known coaching need. The model should actively flag when Jay frames his experience as lesser than it is.
- The citation requirement applies to this template the same as all other RAG prompts. No fabricated sources.
- Update the `SYSTEM` block as Jay's situation evolves (new projects completed, new target companies added, etc.). Treat this as a living document. Re-version it when meaningfully changed.

---

## 5. Eval Harness Extension

The base PRD specifies 10–30 eval questions for the RAG pipeline. Add a dedicated job search eval set as a separate test suite that runs independently of the general eval harness.

**Minimum job search eval questions (10):**

| Question | Expected Source | What to Check |
|---|---|---|
| What are the top 3 things I should emphasize for an Anthropic SE role? | Resume + Anthropic JD | Answer references specific resume items AND JD requirements |
| How should I explain the Gap custom GPT project to a non-technical VP? | Resume | Answer uses business value framing, not technical description |
| What's the difference between RAG and fine-tuning, in SE interview terms? | SE Guide or prep notes | Answer includes when-to-use-which, enterprise framing |
| What does Anthropic specifically care about in SE candidates? | Anthropic company/JD docs | Answer is grounded in retrieved content, not generic |
| What should I say when asked why I'm leaving Gap? | Career Acceleration Plan | Answer is direct, brief, pivots to AI excitement |
| What experience do I have that directly maps to SE discovery work? | Resume | Answer cites specific PM/API governance experience |
| How do I explain embeddings to a non-technical audience? | SE Guide or prep notes | Answer includes the "map" analogy or equivalent |
| What are my strongest projects for an SE portfolio? | Resume + Career Plan | Answer names specific projects with enterprise framing |
| What objections might an interviewer raise about my background? | SE Guide | Answer acknowledges the objection AND provides a counter |
| What companies should I prioritize and why? | Career Plan | Answer reflects stated targets and reasoning |

**Eval success criteria:** Same as base PRD — citation present, cited doc_ids exist in Qdrant, latency under threshold. Additionally: answer must reference Jay's specific background, not give generic career advice.

---

## 6. Ingestion Checklist (Day One)

When Workflow 01 is functional, ingest these documents immediately — before Phase 1 is fully complete. The job search assistant is useful the moment retrieval works, even without polish.

- [ ] Resume (PDF) — tag: `job-search`, `resume`
- [ ] SE Guide (DOCX) — tag: `job-search`, `reference`
- [ ] AI Career Acceleration Plan (MD) — tag: `job-search`, `reference`
- [ ] Recall.local PRD (MD) — tag: `job-search`, `project`
- [ ] Anthropic SE job description (URL or paste) — tag: `job-search`, `jd`, `anthropic`
- [ ] Anthropic mission/values page (URL) — tag: `job-search`, `company`, `anthropic`
- [ ] docs.anthropic.com prompt engineering guide (URL) — tag: `job-search`, `reference`, `anthropic`
- [ ] Cohere SE job description (URL or paste) — tag: `job-search`, `jd`, `cohere`
- [ ] Glean SE job description (URL or paste) — tag: `job-search`, `jd`, `glean`
- [ ] Writer SE job description (URL or paste) — tag: `job-search`, `jd`, `writer`

Add OpenAI and others as JDs are identified. Tag every document at ingestion — retroactive tagging requires re-ingestion.

---

## 7. What This Does NOT Change

To be explicit about scope:

- **No new Qdrant collection.** Job search documents live in `recall_docs` alongside all other content. Tags handle scoping.
- **No new n8n workflows.** The `filter_tags` addition to Workflow 02 is a parameter change, not a new workflow.
- **No new services or infrastructure.** Everything runs on the existing stack.
- **No change to Phase delivery order.** This addendum is implemented as part of Phase 1 (tag-scoped retrieval) and Phase 1 (prompt template). It does not create a new phase.
- **No dashboard or UI beyond Open WebUI.** The existing prompt template system handles mode selection.

---

## 8. Demo Value

This is worth noting explicitly because it informs how to present Recall.local in interviews.

When asked about the Job Search RAG project (Project 1 in the Career Acceleration Plan), the answer is: "I built it as a use case on top of Recall.local rather than as a standalone app. The architecture supports multiple retrieval personas through tag-scoped queries and persona-specific system prompts — the job search assistant is one configuration of the same underlying system."

This is a stronger answer than "I built a separate RAG app for job searching." It demonstrates architectural thinking — understanding how to design systems that serve multiple use cases without code duplication — which is exactly what interviewers at AI companies are evaluating.

---

*Addendum to Recall.local PRD v2.1 | February 2026*
