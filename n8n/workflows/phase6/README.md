# Phase 6B Workflows (Guided Build)

Purpose: build Phase 6B job-discovery workflows in n8n without JSON imports, using bridge canonical APIs.

## Workflows

- `workflow1_aggregator.md`: Job board aggregator (JobSpy/Adzuna/SerpAPI via bridge discovery runner)
- `workflow2_career_pages.md`: Career page monitor (Greenhouse/Lever in n8n, then hand off normalized jobs to bridge)
- `workflow3_evaluate_notify.md`: Full Phase 6C evaluation/notify webhook with Telegram preferred-location gating
- `workflow4_follow_up_reminders.md`: Application Ops follow-up reminder workflow using the bridge reminder-run endpoint plus delivery status write-back
- `../phase6_follow_up_reminders_import.workflow.json`: Import-ready Workflow 4 automation for scheduled follow-up reminder delivery plus sent/failed write-back
- `../phase6b_career_page_monitor_traditional_import.workflow.json`: Import-ready traditional Workflow 2 (multi-node) for easier node-level debugging.
- `../../scripts/phase6/import_n8n_workflow_with_activation_fix.sh`: ai-lab helper for import + activation repair on n8n builds that do not fully activate imported published workflows.

## Bridge endpoints used

- `POST /v1/job-discovery-runs`
- `POST /v1/job-deduplications`
- `POST /v1/job-evaluation-runs`
- `POST /v1/follow-up-reminder-runs`
- `GET /v1/jobs`

## Prerequisites

1. Bridge reachable from n8n:

```text
http://localhost:8090
```

If n8n and bridge share a Docker network, `http://recall-ingest-bridge:8090` can also work.

2. Phase 6 collections already created (`recall_jobs`, `recall_resume`).
3. Optional source keys in bridge runtime env:
- `RECALL_ADZUNA_APP_ID`
- `RECALL_ADZUNA_APP_KEY`
- `RECALL_SERPAPI_API_KEY`
4. JobSpy available in bridge runtime for primary source:

```bash
pip install python-jobspy
```

## Validation order

1. Build Workflow 3 skeleton first (so workflows 1/2 can call it).
2. Build Workflow 1 and run manual trigger.
3. Build Workflow 2 and run manual trigger.
4. Re-run both to verify dedupe (`duplicates_skipped` should rise).
5. Confirm new jobs via `GET /v1/jobs?status=new&min_score=-1`.
