# Revised Job Search Dashboard Implementation Plan

## Summary

Align the dashboard cleanup work with the current Phase 6 implementation and repo API conventions. The five outcomes remain the same, but the implementation must respect existing contracts: archive means `dismissed`, applied means `applied: true`, new ingestion already uses configured company tiers, and new endpoints use collection-first REST naming.

## Geography Filtering

- Add career-page location filtering in `scripts/phase6/job_discovery_runner.py`.
- Allow definite US/Twin Cities locations: US state names and abbreviations, `United States`, `US`, `USA`, `Remote - US`, `Remote US`, `Minneapolis`, `Twin Cities`, and `Minnesota`.
- Treat empty locations as allowed.
- Treat ambiguous plain `Remote` as allowed, because some ATS APIs omit country details.
- Reject explicit non-US remote/location strings such as `Remote - Europe`, `Remote - India`, `London`, and `Hyderabad`.
- Apply the filter to Greenhouse, Ashby, and Lever career-page discovery.

## Stale Job Archival

- Add `archive_stale_jobs(max_age_days=60) -> int` in `scripts/phase6/job_repository.py`.
- Use current archive semantics: set `status: "dismissed"`, `dismissed: true`, and add `archived_at` plus stale cleanup metadata.
- Invalidate both jobs cache and gap cache after mutation.
- Add collection-style endpoint `POST /v1/job-archivals`.
- Request body: `{ "reason": "stale", "max_age_days": 60 }`.
- Response body: `{ "archived_count": N, "reason": "stale", "max_age_days": 60 }`.

## Gap And Match Hint Cleanup

- Remove hardcoded `REQUIREMENT_GAP_HINTS`, `REQUIREMENT_MATCH_HINTS`, and synthetic hint injection from `scripts/phase6/job_evaluator.py`.
- Keep cleanup and normalization helpers such as `GENERIC_GAP_PATTERNS` and `SKILL_NOISE_TOKENS`.
- Preserve conflict resolution so a skill does not appear as both a match and a gap.

## Company Tier Cleanup

- Reuse configured company tiers rather than rebuilding tier assignment from scratch.
- Add a resolver that exact-matches first, then normalized substring-matches configured companies.
- Add a Qdrant backfill helper so existing jobs from configured companies receive the correct `company_tier`.
- Leave untracked companies as `company_tier: 0` or `null`, not Tier 3.
- Update the dashboard so Tier 3 only means explicitly configured Tier 3 companies.
- Render untracked companies in a collapsed `Untracked` section.
- Remove UI fallbacks like `company_tier || 3` where they misclassify untracked jobs.

## Quick Actions

- Preserve existing job update contract: `PATCH /v1/jobs/{jobId}`.
- Mark applied via `{ "applied": true }`, letting the backend set `status: "applied"` and `applied_at`.
- Dismiss/archive via `{ "dismissed": true }`, letting the backend set `status: "dismissed"`.
- Keep existing Mark Applied and Dismiss actions in job detail/card views.
- Add the missing small dismiss button to focus queue cards, with event handling that does not select/open the card.

## Test Plan

- Add or adjust discovery tests for Greenhouse, Ashby, and Lever location filtering.
- Add repository/API tests for `POST /v1/job-archivals`, stale cutoff behavior, cache invalidation, and history-preserving dismissal.
- Add evaluator tests confirming hardcoded hint constants are gone and conflict resolution still works.
- Add tier resolver/backfill tests for configured companies and an untracked company.
- Build the Daily Dashboard to verify the updated UI compiles.
- After code changes, sync Mac to ai-lab, spot-check changed files, run dashboard smoke, and run ops observability per `AGENTS.md`.

## Assumptions

- Ambiguous plain `Remote` career-page postings remain allowed because some ATS APIs omit country details; explicit non-US remote/location strings are filtered out.
- `Archived` remains a user-facing concept, but persisted job status remains `dismissed` unless a broader status migration is explicitly approved.
- `company_tier: 0` or `null` means untracked; Tier 3 means only explicitly configured Tier 3 companies.
