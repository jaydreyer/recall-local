# Recall.local Daily Dashboard Reliability Runbook

Purpose: keep the Phase 6 daily dashboard responsive and usable even when the bridge is under load.

## Primary failure mode

The page shell can load while the board stays empty when startup requests are too heavy or time out through the dashboard nginx proxy.

Typical symptoms:

- `http://100.116.103.78:3001/` renders chrome but no jobs or companies
- browser console shows `504 Gateway Time-out` on `/v1/companies`, `/v1/job-gaps`, or `/v1/llm-settings`
- browser console shows `ERR_CONTENT_LENGTH_MISMATCH` on very large `/v1/jobs` responses

## Reliability rules

1. First paint must not depend on heavyweight Phase 6 endpoints.
2. The Jobs tab should load only a summary jobs list plus job stats on startup.
3. Company profiles, skill-gap aggregation, and LLM settings must load on demand.
4. The dashboard should keep a last-good local snapshot so reloads are still useful if one live request fails.
5. Company list endpoints should avoid embedded job arrays unless the client explicitly asks for them.
6. Job list endpoints should support a lightweight summary view for board rendering.
7. The bridge should keep dashboard-critical caches warm in the background so first paint does not wait for cold aggregations.
8. Operators should use a single smoke command before demos or interviews rather than ad hoc curls.

## Current implementation

- Jobs board startup path:
  - `GET /v1/job-stats`
  - `GET /v1/jobs?...&view=summary`
- Companies tab:
  - `GET /v1/companies?include_jobs=false&limit=300`
  - `GET /v1/companies/{companyId}` only after a company is selected
- Skill gaps:
  - `GET /v1/job-gaps` only when the `Skill Gaps` tab is opened
- Settings:
  - `GET /v1/llm-settings` only when the settings panel is opened
- Bridge readiness endpoint:
  - `GET /v1/dashboard-checks`
- Operator smoke wrapper:
  - `scripts/phase6/run_dashboard_smoke.sh`
- UI cache keys:
  - `daily-dashboard-jobs-snapshot-v1`
  - `daily-dashboard-gap-snapshot-v1`
  - `daily-dashboard-companies-snapshot-v1`
  - `daily-dashboard-settings-snapshot-v1`
  - `daily-dashboard-active-tab-v1`

## Bridge-side cache warming

The bridge now supports a background dashboard cache warmer for jobs, companies, and skill gaps.

Environment controls:

- `RECALL_DASHBOARD_CACHE_WARMER=true|false`
- `RECALL_DASHBOARD_CACHE_WARM_INTERVAL_SECONDS` (default `300`)
- `RECALL_PHASE6_COMPANY_CACHE_SECONDS` (default `180`)
- `RECALL_PHASE6_JOBS_CACHE_SECONDS` (default `15`)
- `RECALL_PHASE6_GAP_CACHE_SECONDS` (default `300`)

## Proxy settings

The daily-dashboard nginx proxy should keep:

- `proxy_connect_timeout 10s`
- `proxy_send_timeout 180s`
- `proxy_read_timeout 180s`
- `proxy_buffering on`

These are a safety net, not the primary fix. The main protection is lighter startup traffic.

## Live validation

### Stack validation

```bash
ssh ai-lab '
  cd /home/jaydreyer/recall-local/docker &&
  ./validate-stack.sh
'
```

### Direct bridge checks

```bash
ssh ai-lab '
  python3 - <<\"PY\"
import urllib.request
for url in [
    "http://localhost:8090/v1/job-stats",
    "http://localhost:8090/v1/jobs?status=all&limit=60&view=summary",
    "http://localhost:8090/v1/companies?include_jobs=false&limit=300",
]:
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = resp.read()
        print(url, resp.status, len(body))
PY
'
```

### Single-command dashboard smoke

```bash
ssh ai-lab '
  cd /home/jaydreyer/recall-local &&
  ./scripts/phase6/run_dashboard_smoke.sh http://localhost:8090
'
```

### Browser-level checks

Open `http://100.116.103.78:3001/` and confirm:

1. `Jobs` tab shows roles without waiting on `Companies` or `Skill Gaps`
2. reload uses cached content immediately while refresh happens in the background
3. `Companies` tab loads after tab switch rather than during first paint
4. `Skill Gaps` tab loads after tab switch rather than during first paint
5. settings open without blocking the rest of the page

## If the dashboard regresses

1. Check browser console for `504` and `ERR_CONTENT_LENGTH_MISMATCH`.
2. Verify direct bridge endpoints on `:8090` still return data.
3. Run `scripts/phase6/run_dashboard_smoke.sh` against the bridge and inspect the `dashboard-checks` payload.
4. If direct bridge is healthy, inspect `recall-daily-dashboard` nginx logs.
5. Compare the requested dashboard payload sizes and confirm the client is still using:
   - jobs `view=summary`
   - companies `include_jobs=false`
   - lazy loading for gaps/settings
6. Check the `cache_warmer` section in `GET /v1/dashboard-checks` for stale completion times or the last warm-up error.
7. Only after that consider increasing proxy timeouts or investigating bridge performance.
