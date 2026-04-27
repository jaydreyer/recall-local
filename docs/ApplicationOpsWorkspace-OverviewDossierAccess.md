# Application Ops Workspace + Overview Dossier Access

## Summary

Add a new desktop-first `Ops` workspace inside the same app, while keeping the existing daily dashboard as the lighter overview page. The overview page will continue to answer “what needs attention?”, and the new Ops page will answer “what do I do with this role right now?”.

At the same time, fix the current overview page’s dossier usability issue so role details are reachable without scrolling through the entire jobs list. The current pattern in [ui/daily-dashboard/src/components/JobsCommandCenter.jsx](/Users/jaydreyer/projects/recall-local/ui/daily-dashboard/src/components/JobsCommandCenter.jsx) uses `scrollIntoView` to move to a dossier panel placed below the queue; replace that with a true accessible detail surface.

## Key Changes

### Navigation and page structure
- Keep the same app/base URL and add a second route/page inside the dashboard app.
- Add top-level app navigation with two destinations:
  - `Overview`: current daily dashboard, lighter monitoring/triage surface
  - `Ops`: new application operations workspace
- Default landing page remains `Overview`.
- Add deep links from `Overview` into `Ops` using URL state, for example selected role, lane/state, or follow-up queue.

### Overview page changes
- Preserve the current summary/triage role of the page instead of turning it into the full workflow console.
- Replace the current below-the-fold dossier pattern with one of these behaviors:
  - desktop: sticky side panel or slide-over detail panel attached to the selected role
  - mobile: full-screen detail sheet or route-based detail view
- Remove the need to scroll through the queue to reach dossier content.
- Add explicit “Open in Ops” actions from hero card, job cards, and future summary widgets.
- Keep overview filters and queue browsing lightweight; do not add the full workflow timeline/approval/packet surface here.

### New Ops workspace
- Create a wide-screen, desktop-first layout optimized for browser real estate:
  - left rail: queue, filters, pipeline lanes/states
  - center workspace: selected role, next-best action, rationale, and packet work area
  - right rail: blockers, approvals, activity timeline, follow-up state
- On mobile, collapse the Ops workspace into a simpler stacked flow with section tabs or accordions rather than preserving the full three-pane layout.
- Support opening Ops directly from URL params:
  - selected role
  - filtered lane/state
  - “needs review”, “tailoring needed”, or “follow-up due” queue
- Keep Ops focused on actionability, not broad dashboarding.

### Workflow metadata and APIs
- Extend the existing jobs/opportunity model incrementally rather than replacing it.
- Add workflow metadata fields for:
  - pipeline state
  - next-best action
  - next-action rationale/confidence
  - blocker summary
  - workflow timestamps
- Add structured activity/timeline support for role events.
- Add API support for:
  - reading workflow metadata with job detail
  - updating workflow state
  - fetching timeline/activity events
  - optionally recalculating next-best action
- Keep application packets, approvals, and follow-up automation in the design, but phase implementation:
  - v1: state, next-best action, blockers, timeline, overview-to-ops handoff
  - v2: packet generation and approval checkpoints
  - v3: follow-up automation and reminder workflows

### UX and layout standards
- Increase desktop layout flexibility beyond the current centered `1160px` shell in [ui/daily-dashboard/src/styles/theme.css](/Users/jaydreyer/projects/recall-local/ui/daily-dashboard/src/styles/theme.css) for the new Ops route.
- Keep the existing design language, but allow the Ops workspace to use more width and independent pane scrolling.
- Avoid whole-page scrolling as the primary means of switching from queue to detail.
- Ensure keyboard navigation and back/forward navigation work cleanly between Overview and Ops.
- Preserve mobile usability by using route-based or sheet-based detail instead of trying to mirror desktop pane density.

## Public Interfaces / API Additions

- Add app routing/state for `Overview` and `Ops`.
- Add deep-link query params for Ops context:
  - selected job id
  - selected queue/state
- Extend job detail responses with workflow metadata.
- Add workflow mutation/read endpoints for state and timeline.
- Keep current `PATCH /v1/jobs/{jobId}` behavior working for existing status/applied/dismissed flows during migration.

## Test Plan

- Verify the overview page no longer requires scrolling through the full queue to access dossier details.
- Verify “Open dossier” on Overview opens an attached detail surface on desktop and a mobile-friendly detail view on small screens.
- Verify “Open in Ops” preserves selected role context.
- Verify direct Ops URLs open the intended role or queue.
- Verify wide-screen Ops layout uses available browser width without breaking the current aesthetic.
- Verify mobile layout remains usable for both Overview and Ops.
- Verify existing jobs fetch, stats, company profile, and skill-gap flows still work unchanged.
- Add API tests for workflow metadata reads and state/timeline mutations.
- Run the dashboard smoke wrapper after UI/API changes per repo guidance.

## Assumptions and Defaults

- The existing daily dashboard remains the primary landing page.
- The new workspace is added to the same frontend app, not deployed as a separate app.
- `Overview` stays lighter and monitoring-oriented; `Ops` becomes the action-oriented workspace.
- The first implementation phase will not attempt full packet generation, approvals, and automation all at once.
- The current dossier scroll problem is treated as a required fix alongside the new Ops page, not a follow-up nice-to-have.
