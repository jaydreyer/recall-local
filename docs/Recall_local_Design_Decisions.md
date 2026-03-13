# Recall.local Design Decisions

This document explains the main architectural choices behind Recall.local in reviewer-friendly language.

## 1. Local-First, But Not Local-Only

Recall.local runs primarily against local infrastructure: Ollama for model serving, Qdrant for vector search, SQLite for structured state, and Docker Compose for reproducible operation.

Why:

- It demonstrates practical self-hosted AI system design rather than a wrapper around hosted APIs.
- It makes privacy, latency, offline operation, and operational reliability part of the product story.
- It creates an explicit tradeoff discussion for interviews: local control versus managed-model quality and convenience.

Tradeoff:

- Local models are cheaper and more private, but can be weaker or less consistent.
- The project keeps a cloud escape hatch so quality-sensitive workflows can escalate when needed.

## 2. Dual Memory Model Instead Of "Just RAG"

Recall.local stores information in two ways:

- Qdrant holds chunked embeddings for semantic retrieval.
- SQLite stores operational state such as runs, evaluations, workflow status, and supporting metadata.

Why:

- Semantic retrieval is good for answering questions over messy content.
- Structured state is good for dashboards, observability, and reliable workflow orchestration.
- Together, they make the project feel like a system with memory and accountability, not just a chat demo.

Tradeoff:

- The architecture is more complex than a single vector store.
- In return, it supports both cited answers and operational reporting.

## 3. Thin Bridge API As The System Contract

The FastAPI bridge is deliberately the shared contract for dashboards, scripts, and n8n workflows.

Why:

- A single noun-based API reduces integration drift between clients.
- OpenAPI documentation gives reviewers a concrete, inspectable contract.
- Endpoint contract tests make it easier to evolve the system without breaking the operator paths.

Tradeoff:

- The bridge has a broad endpoint surface.
- That complexity is intentional because it centralizes system behavior instead of scattering it across multiple private scripts.

## 4. Retrieval Uses Layered Ranking Rather Than Embeddings Alone

The retrieval path does not stop at vector similarity.

Why:

- Dense similarity is useful, but it often misses exact lexical intent, quoted titles, or high-precision hints embedded in the query.
- Hybrid ranking and lightweight reranking let the system blend semantic recall with exact-term and title-sensitive precision.
- This mirrors real production retrieval work more closely than "embed and sort by cosine."

Tradeoff:

- The ranking code is more involved than a plain vector query.
- In return, it is easier to explain quality improvements and evaluate retrieval tradeoffs.

## 5. Evaluation Is Local-First With Conditional Escalation

The Phase 6 job evaluator starts with a local model and escalates only when configured heuristics indicate uncertainty or poor output quality.

Why:

- It preserves the local-first story.
- It shows practical judgment about cost, latency, and quality rather than ideological purity.
- It creates a clean interview talking point about fallback design in AI systems.

Tradeoff:

- Evaluation logic becomes more complex because merge and escalation rules must be explicit.
- The benefit is a more resilient pipeline under demo and real usage conditions.

## 6. Artifacts And Runbooks Are Part Of The Product

The repo invests heavily in artifacts, smoke checks, and runbooks.

Why:

- AI systems are hard to evaluate by source alone; artifacts show how the system behaves over time.
- Operational readiness is part of the project’s thesis, not an afterthought.
- This makes the repo useful for reviewers who care about maintainability, not just feature count.

Tradeoff:

- The docs folder is larger and more operational than a typical portfolio repo.
- This is deliberate, because the project aims to show end-to-end ownership: build, validate, explain, and operate.

## Suggested Reading Order

1. [../README.md](../README.md)
2. [Recall_local_Architecture_Diagram.md](Recall_local_Architecture_Diagram.md)
3. [Recall_local_API_Reference.md](Recall_local_API_Reference.md)
4. [../scripts/phase1/retrieval.py](../scripts/phase1/retrieval.py)
5. [../scripts/phase6/job_evaluator.py](../scripts/phase6/job_evaluator.py)
