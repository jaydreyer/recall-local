# Recall.local Observability Strategy

Last updated: 2026-03-12
Status: foundation implemented, expansion planned

## Purpose

Define a practical observability strategy for Recall.local that is:

- easy for a single operator to use
- strong enough to debug failures across the stack
- clear enough to explain in recruiter and interview conversations
- phased so the foundation can land now and deeper coverage can follow later

## Current State

The observability foundation is no longer hypothetical. The current live baseline already includes:

- bridge request IDs on responses and error envelopes
- the dashboard readiness route:
  - `GET /v1/dashboard-checks`
- an operator dashboard smoke wrapper:
  - `scripts/phase6/run_dashboard_smoke.sh`
- a consolidated operator observability wrapper:
  - `scripts/phase6/run_ops_observability_check.sh`
  - supports optional failure alerts through Telegram or a generic webhook
- optional Langfuse tracing in `scripts/llm_client.py`
- optional OpenTelemetry tracing for the bridge via OTLP / Honeycomb-compatible env vars

What is still planned rather than implemented:

- scheduled synthetic browser checks with screenshots
- deeper alert routing and long-term uptime dashboards
- broader cross-service tracing beyond the bridge itself

## Recommendation

Use a three-layer model:

1. System observability: Honeycomb for service traces, latency, and failures across `n8n`, the FastAPI bridge, and key dependencies.
2. LLM observability: Langfuse for prompt, retrieval, generation, and model-quality debugging.
3. User experience observability: Playwright synthetic checks for the web interfaces plus correlation IDs that tie UI failures back to API traces.

This is intentionally not a full self-hosted observability platform. The goal is strong signal with low operator overhead.

## Why this fits Recall.local

Recall.local is no longer a single script. It spans:

- `n8n` workflows
- the FastAPI bridge in `scripts/phase1/ingest_bridge_api.py`
- LLM calls in `scripts/llm_client.py`
- Qdrant
- SQLite-backed operational state
- multiple React UIs under `ui/`
- scheduled eval and job-discovery flows

That means "what is broken?" now crosses service boundaries. Logs alone are not enough once requests move through multiple components.

## Principles

- Prefer additive instrumentation over architectural rewrites.
- Use one correlation ID everywhere.
- Default to redacted hosted telemetry.
- Keep free-tier limits in mind.
- Start with the smallest useful foundation, then expand.
- Optimize for explainability, not tool sprawl.

## Operating Assumptions

- Hosted telemetry is acceptable.
- Free-tier-only tooling should be assumed initially.
- Telegram is the first alert destination.
- Raw prompt and document content should be redacted by default.
- Existing `/v1/*` bridge APIs remain backward compatible.

## Target Architecture

### Layer 1: System Reliability

Primary tool: Honeycomb

Use Honeycomb for:

- request traces across inbound bridge requests
- latency analysis by endpoint
- dependency error analysis
- workflow and scheduled-job visibility
- alert conditions tied to failure rate and latency

Key path to trace:

`UI or n8n -> bridge API -> retrieval/storage/LLM/dependency -> response`

Current implementation note:

- the bridge now supports opt-in OTLP HTTP tracing
- Honeycomb can be used by setting OTLP exporter env vars directly or by setting `HONEYCOMB_API_KEY`
- tracing is not enabled in the live ai-lab baseline unless `RECALL_OTEL_ENABLED=true`

### Layer 2: LLM Quality and Behavior

Primary tool: Langfuse

Use Langfuse for:

- prompt and retrieval inspection
- generation latency and model behavior
- comparing providers and models
- debugging RAG failures
- tying eval results to concrete model traces

Current repo note:

- Langfuse is already partially wired in `scripts/llm_client.py`
- that integration should be hardened, not replaced

### Layer 3: User Experience

Primary tool: Playwright-based synthetic checks

Use synthetic checks for:

- `recall-ui` availability
- `daily-dashboard` availability
- key happy paths such as query, ingest, and dashboard hydration
- screenshot and console capture on failure

## Minimum Now vs Later

### Minimum Now

This is the current foundation to preserve now, even if full observability waits:

1. Request ID propagation
   - accept optional `X-Request-Id`
   - generate one when absent
   - return it on every response
   - pass it into logs and Langfuse metadata

2. Structured bridge telemetry
   - route
   - status code
   - latency
   - request ID
   - error code
   - workflow or channel context where available

3. Langfuse hardening
   - ensure consistent metadata on all `generate()` and `embed()` calls
   - redact content by default

4. Basic operator checks
   - `scripts/phase6/run_dashboard_smoke.sh` for dashboard data readiness
   - `scripts/phase6/run_ops_observability_check.sh` for bridge health, dashboard checks, UI reachability, one grounded RAG probe, and optional failure alerting

These pieces are worth doing before the project is "finished" because retrofitting correlation later is harder and less clean.

### Later Expansion

Add after more features stabilize:

1. Honeycomb OTEL tracing for the bridge and core jobs
2. n8n execution telemetry and error workflows
3. alert thresholds and richer Telegram/webhook routing
4. broader synthetic coverage for new UI flows
5. recruiter-facing dashboards and screenshots

## Proposed Rollout

### Phase A: Foundation

- add request ID propagation across bridge and UI calls
- add structured logs and metadata fields
- keep telemetry behind environment flags

### Phase B: Backend Tracing

- instrument FastAPI routes with OpenTelemetry
- export to Honeycomb
- trace retrieval, generation, eval, and job-discovery paths

Current status:

- partially implemented for the FastAPI bridge
- request spans can now be exported through OTLP when enabled
- request IDs and trace IDs are returned on bridge responses

### Phase C: Workflow Coverage

- emit `n8n` execution metadata
- forward request IDs from workflows into bridge calls
- alert on workflow failures to Telegram

### Phase D: UX Monitoring

- schedule Playwright synthetic checks
- store screenshots and failure artifacts
- forward check failures to Telegram

### Phase E: Dashboards and Interview Story

- create Honeycomb boards for latency and failures
- create Langfuse views for LLM behavior
- document a short walkthrough for interview use

## API and Interface Additions

These are additive and should not require a new API version.

### Request and Response Headers

- `X-Request-Id`
  - request: optional from caller
  - response: always returned by bridge

- `traceparent`
  - optional passthrough for distributed tracing

### Environment Variables

Planned additions:

- `RECALL_OTEL_ENABLED`
- `OTEL_SERVICE_NAME`
- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_HEADERS`
- `HONEYCOMB_API_KEY`
- `HONEYCOMB_DATASET`
- `HONEYCOMB_API_ENDPOINT`
- `RECALL_OBS_REDACT_MODE`
- `RECALL_TRACE_SAMPLE_SUCCESS_RATE`
- `RECALL_TRACE_SAMPLE_ERROR_RATE`
- `VITE_RECALL_OBS_ENABLED`

## Initial Alert Targets

Send to Telegram first.

First useful alerts:

- bridge health check failing repeatedly
- `/v1/rag-queries` elevated error rate
- `/v1/rag-queries` high latency
- scheduled eval regression versus recent baseline
- repeated synthetic UI failures

## Uptime and Alerting Now

The practical uptime path is now:

1. Run `scripts/phase6/run_ops_observability_check.sh`
2. Write a JSON artifact under `data/artifacts/observability`
3. Exit non-zero on failure
4. Optionally send alerts when these env vars are present:
   - `RECALL_UPTIME_ALERT_WEBHOOK_URL`
   - `RECALL_UPTIME_ALERT_TELEGRAM_BOT_TOKEN`
   - `RECALL_UPTIME_ALERT_TELEGRAM_CHAT_ID`
   - `RECALL_UPTIME_NOTIFY_ON_SUCCESS`

Cron-friendly wrapper:

- `scripts/phase6/run_ops_observability_cron.sh`
- sources `docker/.env`
- falls back to `RECALL_TELEGRAM_BOT_TOKEN` and `RECALL_TELEGRAM_CHAT_ID` when dedicated uptime alert vars are unset

Recommended ai-lab cron baseline:

```cron
*/10 * * * * cd /home/jaydreyer/recall-local && /home/jaydreyer/recall-local/scripts/phase6/run_ops_observability_cron.sh >> /home/jaydreyer/recall-local/data/artifacts/observability/cron.log 2>&1
```

That is intentionally lightweight. It does not replace richer synthetic monitoring later, but it gives a real operator-facing uptime and alerting loop now.

## Honeycomb Status

We have not given up on Honeycomb. We intentionally deferred it.

Reason:

- the current highest-risk gap was not trace visualizations
- it was "will I know quickly when the live stack is broken before a demo or interview?"

The cron-driven uptime check plus alerting closes that gap with very low overhead. Honeycomb is still the recommended next layer once the operator loop is stable, because it answers a different question:

- uptime checks tell us that something is broken
- Honeycomb would tell us why a request path is slow or failing across service boundaries

Current status:

- bridge-side OTLP tracing support is now implemented
- live export still requires real Honeycomb or OTLP credentials plus `RECALL_OTEL_ENABLED=true`
- broader service coverage for `n8n`, Qdrant, and browser flows is still future work

## Definitions of Done

### Foundation complete

- every bridge response includes a request ID
- bridge responses can include `X-Trace-Id` and `traceparent` when tracing is enabled
- logs and Langfuse traces can be correlated by request ID
- raw text is redacted by default in hosted telemetry

### Backend tracing complete

- Honeycomb shows route latency, errors, and dependency timing
- one RAG request can be followed from HTTP request to generation

### UX monitoring complete

- a failed UI synthetic run produces a screenshot, error context, and a request ID or trace link

## Testing Expectations

- request ID passthrough when supplied by callers
- request ID generation when omitted
- backward compatibility for existing `/v1/*` responses
- trace metadata presence for `generate()` and `embed()`
- synthetic checks fail loudly and produce artifacts
- error traces are retained even when success sampling is low

## Risks and Constraints

- hosted telemetry can become noisy if redaction and sampling are not enforced
- free-tier limits require selective tracing rather than full capture everywhere
- `n8n` visibility is weaker unless execution IDs and workflow metadata are forwarded deliberately

## Interview Value

This strategy creates a clear story:

- Langfuse explains model behavior
- Honeycomb explains system behavior
- synthetic checks explain user-facing reliability

That is stronger than saying "we had logs." It shows intentional operational design as the project grew from a prototype into a multi-service application.

## Implementation Order Recommendation

If this work starts before the rest of the product is complete, use this order:

1. request ID propagation
2. structured bridge telemetry
3. Langfuse metadata and redaction cleanup
4. one synthetic check per UI
5. Honeycomb tracing
6. workflow alerts and dashboards

## Related Files

- `/Users/jaydreyer/projects/recall-local/scripts/phase1/ingest_bridge_api.py`
- `/Users/jaydreyer/projects/recall-local/scripts/llm_client.py`
- `/Users/jaydreyer/projects/recall-local/scripts/eval/run_eval.py`
- `/Users/jaydreyer/projects/recall-local/scripts/phase6/job_discovery_runner.py`
- `/Users/jaydreyer/projects/recall-local/scripts/phase6/run_ops_observability_check.sh`
- `/Users/jaydreyer/projects/recall-local/ui/dashboard/src/api.js`
- `/Users/jaydreyer/projects/recall-local/ui/daily-dashboard/src/api.js`
- `/Users/jaydreyer/projects/recall-local/docs/Recall_local_PRD.md`
- `/Users/jaydreyer/projects/recall-local/docs/IMPLEMENTATION_LOG.md`
