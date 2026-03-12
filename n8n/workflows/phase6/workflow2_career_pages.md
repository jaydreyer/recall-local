# Workflow 2: Career Page Monitor (Guided)

Goal: monitor target company boards every 12 hours, normalize results in n8n, then hand normalized jobs to bridge for dedupe + storage.

## Reliability notes for the import-ready workflows

- The import-ready Workflow 2 JSON files now use `this.helpers.httpRequest()` inside Code nodes instead of raw `fetch()`.
- Keep that helper-based approach if you edit the workflow in n8n. It is more reliable inside the n8n execution runtime and gives cleaner timeout / status handling.
- The "Summary (No Matches)" step now emits:
  - `status: fetch-error` when the ATS request fails
  - `status: no-matches` when the ATS request succeeds but nothing matches the title filters
- Preserve that distinction so operators can tell the difference between a quiet board and a broken fetch.

## Node 1: Schedule Trigger

- Node type: `Schedule Trigger`
- Mode: `Cron`
- Cron expression: `0 7,19 * * *`

## Node 2: Load Company Configs

- Node type: `Code`
- Name: `Load Company Configs`
- Code (start with a small set, then expand):

```javascript
return [
  {
    json: {
      companies: [
        { name: "Anthropic", ats: "greenhouse", board_id: "anthropic", tier: 2, title_filter: ["solutions", "engineer", "architect", "technical"] },
        { name: "OpenAI", ats: "ashby", board_id: "openai", tier: 2, title_filter: ["deployment", "solutions engineer", "solution engineer", "forward deployed", "architect", "pre-sales"] },
        { name: "Postman", ats: "greenhouse", board_id: "postman", tier: 1, title_filter: ["solutions", "engineer", "architect", "technical"] }
      ]
    }
  }
];
```

## Node 3: Split In Batches

- Node type: `Split In Batches`
- Batch size: `1`
- Source list expression: `={{ $json.companies }}`

## Node 4: Route by ATS

- Node type: `Switch`
- Expression: `={{ $json.ats }}`
- Cases:
- `greenhouse`
- `ashby`
- `lever`
- default (`workday` / unsupported)

## Node 5A: Greenhouse API (case: greenhouse)

- Node type: `HTTP Request`
- Method: `GET`
- URL expression:

```javascript
={{ `https://boards-api.greenhouse.io/v1/boards/${$json.board_id}/jobs` }}
```

- Response format: `JSON`

## Node 5B: Lever API (case: lever)

- Node type: `HTTP Request`
- Method: `GET`
- URL expression:

```javascript
={{ `https://api.lever.co/v0/postings/${$json.board_id}?mode=json` }}
```

## Node 5C: Ashby API (case: ashby)

- Node type: `HTTP Request`
- Method: `GET`
- URL expression:

```javascript
={{ `https://api.ashbyhq.com/posting-api/job-board/${$json.board_id}` }}
```

## Node 5D: Workday/Other Placeholder (default case)

- Node type: `Code`
- Code:

```javascript
return [{
  json: {
    company: $json,
    jobs: [],
    note: `Skipped ATS=${$json.ats}; add HTML extraction flow for this company.`
  }
}];
```

## Node 6A: Normalize Greenhouse Jobs

- Node type: `Code`
- Input: from Greenhouse API node + company item
- Code:

```javascript
const company = $items("Split In Batches", 0, 0).json;
const filters = (company.title_filter || []).map(v => String(v).toLowerCase());
const jobs = ($json.jobs || [])
  .filter(j => {
    const title = String(j.title || "").toLowerCase();
    return filters.length === 0 || filters.some(token => title.includes(token));
  })
  .map(j => ({
    title: j.title,
    company: company.name,
    location: j.location?.name || "Unknown",
    url: j.absolute_url,
    description: "",
    source: "career_page",
    search_query: `${company.name} careers`,
    company_tier: company.tier,
    date_posted: j.updated_at
  }));
return [{ json: { company: company.name, jobs } }];
```

## Node 6B: Normalize Lever Jobs

- Node type: `Code`
- Code:

```javascript
const company = $items("Split In Batches", 0, 0).json;
const filters = (company.title_filter || []).map(v => String(v).toLowerCase());
const sourceJobs = Array.isArray($json) ? $json : [];
const jobs = sourceJobs
  .filter(j => {
    const title = String(j.text || "").toLowerCase();
    return filters.length === 0 || filters.some(token => title.includes(token));
  })
  .map(j => ({
    title: j.text,
    company: company.name,
    location: j.categories?.location || "Unknown",
    url: j.hostedUrl,
    description: j.descriptionPlain || j.description || "",
    source: "career_page",
    search_query: `${company.name} careers`,
    company_tier: company.tier,
    date_posted: j.createdAt || null
  }));
return [{ json: { company: company.name, jobs } }];
```

## Node 6C: Normalize Ashby Jobs

- Node type: `Code`
- Code:

```javascript
const company = $items("Split In Batches", 0, 0).json;
const filters = (company.title_filter || []).map(v => String(v).toLowerCase());
const sourceJobs = Array.isArray($json.jobs) ? $json.jobs : [];
const jobs = sourceJobs
  .filter(j => {
    const title = String(j.title || "").toLowerCase();
    return filters.length === 0 || filters.some(token => title.includes(token));
  })
  .map(j => ({
    title: j.title,
    company: company.name,
    location: j.location || "Unknown",
    url: j.jobUrl || j.applyUrl,
    description: j.descriptionPlain || j.descriptionHtml || "",
    source: "career_page",
    search_query: `${company.name} careers`,
    company_tier: company.tier,
    date_posted: j.publishedAt || null
  }));
return [{ json: { company: company.name, jobs } }];
```

## Node 7: Wait (Rate Limit)

- Node type: `Wait`
- Wait amount: `2 seconds`

## Node 8: Store + Dedupe via Bridge

- Node type: `HTTP Request`
- Method: `POST`
- URL: `http://100.116.103.78:8090/v1/job-discovery-runs`
- Send body: `JSON`
- JSON body:

```javascript
={{ {
  sources: ["career_page"],
  jobs: $json.jobs,
  dry_run: false,
  similarity_threshold: 0.92
} }}
```

## Node 9: If New Jobs

- Node type: `IF`
- Expression: `={{ ($json.new_job_ids || []).length > 0 }}`

## Node 10: Trigger Evaluate + Notify

- Node type: `HTTP Request`
- Method: `POST`
- URL: `http://100.116.103.78:5678/webhook/recall-job-evaluate`
- JSON body:

```javascript
={{ { job_ids: $json.new_job_ids, wait: true } }}
```

## Node 11: Summary

- Node type: `Code`
- Code:

```javascript
return [{
  json: {
    company: $json.company || "batch",
    run_id: $json.run_id,
    result_count: Number($json.result_count || 0),
    high_fit_count: Number($json.high_fit_count || 0),
    notifications_sent: Number($json.notifications_sent || 0),
    notification_errors: $json.notification_errors || []
  }
}];
```

## Quick test

1. Run manually with 2-3 companies, including the OpenAI Ashby board.
2. Confirm Node 8 returns `new_job_ids`.
3. Confirm high-fit matches produce `notifications_sent > 0` and arrive in Telegram.
