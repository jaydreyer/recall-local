# Recall.local Application Ops Roadmap

## Purpose

This document is the restart point for future Codex sessions working on the Application Ops Console inside the daily dashboard.

It is intended to stay aligned with:

- [recall-local-application-ops-copilot-prd.md](/Users/jaydreyer/Documents/recall-local-application-ops-copilot-prd.md)
- [recall-local-implementation-checklist.md](/Users/jaydreyer/Documents/recall-local-implementation-checklist.md)

If a new session starts cold, use this file as the primary reference for:

- what the original docs asked for
- what is actually implemented now
- what remains to be built next

Last refreshed: 2026-03-17

## Snapshot

The Application Ops upgrade is no longer just a concept or demo shell. It now has a real workflow foundation inside the live dashboard.

Practical status:

- demo-ready UX and product framing: strong
- workflow foundation and execution model: real and usable
- full PRD completion: not finished yet

Estimated completion against the original docs:

- around 65-75% of the intended product
- around 85% of the visible demo and UX shape

## Current Live State

The live app now includes:

- top-level `Overview | Ops` navigation
- overview-to-ops handoff
- fixed dossier access through an attached detail surface instead of forced page scroll
- desktop-first Ops workspace that uses browser real estate much better
- persisted workflow state on jobs
- persisted workflow stages driving Ops lanes
- packet checklist and approval state persisted through the backend
- workflow timeline support
- summary strip for high-attention work
- queue filters
- queue sorting controls

The product has moved beyond "analysis dashboard with nice mock workflow." It now has a real workflow spine, but some areas are still lighter-weight than the original PRD/checklist intended.

## Alignment With The Original Docs

This section is the most important one for future sessions.

### PRD / checklist status by major area

#### 1. Pipeline states

Status: `partial to mostly done`

What is done:

- explicit persisted workflow stage/state now exists
- state is visible in Ops
- state changes can be triggered manually
- stage drives queue/lane membership

What is still off from the original docs:

- current stage taxonomy does not exactly match the PRD's proposed state list
- transition rules are still lighter than a fully formalized workflow engine
- state badges and controls could be more consistently surfaced across every overview/detail surface

#### 2. Next-best action engine

Status: `partial`

What is done:

- next action is visible in the product
- action framing exists in Ops and supports the demo story

What is still missing:

- persisted `next_action`, rationale, confidence, and due date are not yet fully realized as first-class backend-backed workflow fields
- action selection is still simpler than the PRD's intended copilot logic
- recalculation behavior is not yet a fully formalized workflow service

#### 3. Blocker detection

Status: `partial`

What is done:

- blocker concepts are visible in the UI
- blockers are part of the workflow framing in Ops

What is still missing:

- blockers are still lighter-weight and more heuristic than the PRD/checklist intended
- blocker logic is not yet a robust backend engine with richer sources of truth

#### 4. Activity timeline and event logging

Status: `partial`

What is done:

- timeline support exists in Ops
- workflow-oriented events are visible enough for demo and basic operator context

What is still missing:

- richer event taxonomy
- clearer distinction between event types
- more durable event logging model
- better human-readable event labels
- deeper backend/API/test coverage around event creation and retrieval

#### 5. Application packet generation

Status: `partial`

What is done:

- packet concept exists in the product
- packet checklist state exists and persists
- cover letter generation is already part of the broader Recall.local product story

What is still missing:

- packet state is not yet deeply linked to real saved/generated artifacts
- packet readiness still needs stronger artifact truth behind it
- a more explicit packet schema and packet API surface may still be warranted

#### 6. Approval workflow

Status: `mostly done for v1 shape, partial for durable product depth`

What is done:

- approval concepts are visible
- approvals persist through the backend
- approval UX exists in Ops

What is still missing:

- richer approval history in the timeline
- clearer approval semantics tied to actual packet components or outputs
- stronger test coverage around approval mutations

#### 7. Follow-up automation

Status: `not done / early partial`

What is done:

- follow-up exists as a workflow concept and lane direction
- applied roles can be framed as moving into follow-up work

What is still missing:

- follow-up due dates
- persisted follow-up task metadata
- reminder UI
- n8n-backed reminder/automation flow
- follow-up dashboarding that matches the checklist/PRD vision

#### 8. UI / dashboard enhancements

Status: `mostly done for the main intended slice`

What is done:

- app-level navigation
- much better use of desktop real estate
- Overview/Ops separation
- fixed dossier access problem
- filters, counts, and sorting in Ops
- overall live-demo clarity is much stronger

What is still missing:

- more polish in dense areas
- more elegant mobile treatment
- another pass on visual calm and hierarchy

#### 9. Docs, demo, and portfolio packaging

Status: `partial`

What is done:

- the live app now tells a much stronger portfolio story
- demo runbook exists
- roadmap exists

What is still missing:

- README/product framing updates if desired
- architecture diagram
- refreshed screenshots/GIFs
- a tighter final writeup of the "AI Application Ops Copilot" narrative

## What Is Already Done

### Phase 1 / Workflow Intelligence

Implemented:

- app-level `Overview | Ops` navigation
- separate desktop-first Ops workspace inside the same app
- overview dossier access fix
- overview-to-ops handoff
- workflow framing in the UI:
  - next action
  - blockers
  - packet
  - timeline
- persisted workflow state on jobs
- persisted workflow stages on jobs
- lane move controls in Ops

### Phase 2 / Workflow Execution

Implemented:

- packet checklist persisted through the backend
- approval state persisted through the backend
- Ops UI for packet and approval workflows
- queue filters:
  - `All roles`
  - `Needs approval`
  - `Packet in progress`
  - `Ready to apply`
- queue sorting:
  - `Most ready`
  - `Highest fit`
  - `Recently updated`
- clickable Ops summary strip for:
  - `Needs approval`
  - `Packet in progress`
  - `Ready to apply`

### Infrastructure / Deployment / Validation

The live environment at `ai-lab` required recovery work during implementation:

- restored missing shared bridge runtime files
- restored missing `scripts/phase1` route helper modules on the server checkout
- fixed helper import behavior so the modular route layout works with the existing bridge script entrypoint
- ensured dashboard and bridge run under the required Compose project name `recall`

Validation workflow already used successfully:

- `docker/validate-stack.sh`
- `scripts/phase6/run_dashboard_smoke.sh`
- `scripts/phase6/run_ops_observability_check.sh`

## What Is Still Left

### Must-have

These are the highest-value remaining items if the goal is to fulfill the original docs more honestly.

#### 1. Richer timeline and workflow history

- make timeline entries more specific and human-readable
- distinguish clearly between:
  - stage move
  - approval granted
  - approval revoked
  - packet item completed
  - packet item reopened
  - application recorded
  - follow-up scheduled
  - follow-up completed
- improve ordering and presentation of synthetic versus persisted events
- make the right rail feel like real application history

#### 2. Real packet / artifact linkage

- connect packet checklist items to actual generated or saved artifacts where possible
- tie cover letter state to real generated drafts more explicitly
- add durable references to packet components if available
- make packet readiness depend on both checklist state and artifact truth

#### 3. Follow-up workflow and reminders

- add persisted follow-up metadata
- support fields such as:
  - follow-up due date
  - last follow-up date
  - follow-up status
  - reminder created flag or reminder metadata
- expose a queue or summary for follow-up due work
- add timeline events for follow-up changes
- wire follow-up reminder automation into n8n if desired

#### 4. Next-best-action and blocker depth

- formalize persisted next action fields
- add rationale, confidence, and suggested due date as real workflow data
- improve blocker generation from real workflow/artifact state
- make action recalculation more intentional and testable

#### 5. API and test hardening

- add contract coverage for workflow stage changes
- add contract coverage for packet and approval updates
- add contract coverage for timeline behavior
- add coverage for follow-up workflow once implemented
- document the workflow patch surface more formally if it continues to expand
- reduce remaining repo/server drift risk

### Should-have

These are high-value improvements that strengthen daily usability and product quality.

#### 6. UX polish pass

- tighten spacing and hierarchy in Ops
- calm the left-rail density
- improve visual distinction between queue, center workspace, and right rail
- refine mobile collapse behavior
- continue reducing prototype-feeling clusters

#### 7. Better Ops intelligence

- improve next-best-action ranking
- improve blocker detection
- improve "most ready" ranking heuristics
- add saved views for common working states, for example:
  - `Ready to apply`
  - `Needs approval`
  - `Packet incomplete`
  - `Follow-up due`

#### 8. Overview / Ops handoff refinement

- make transitions feel even more intentional
- improve context carryover from Overview widgets
- improve URL/deep-link behavior further
- ensure default selected role always feels sensible after filters, sorts, or refresh

#### 9. Portfolio packaging

- update README if you want the repo narrative to match the new product framing
- capture refreshed screenshots or GIFs
- add a small architecture diagram
- tighten the portfolio-facing explanation of the workflow system

### Nice-to-have

#### 10. Multi-operator concepts

- optional owner / assignee
- optional assignment history
- optional collaboration or handoff markers

#### 11. Automation / recommendation layer

- suggest stage moves
- suggest follow-up timing
- suggest packet next steps from actual workflow state
- eventually automate parts of routine progression

#### 12. Analytics / ops reporting

- funnel metrics by stage
- time-in-stage metrics
- approval bottleneck indicators
- packet completion throughput

## Recommended Implementation Order

If continuing from here, use this order:

1. richer timeline events
2. follow-up state and follow-up queue
3. packet / artifact linkage
4. persisted next-action and blocker depth
5. API and test hardening
6. UX polish pass
7. saved views and recommendation improvements
8. portfolio packaging

## Suggested Next Slice

The best next implementation slice is:

### Follow-up workflow + richer timeline

Scope:

- add persisted follow-up metadata to workflow state
- add queue support for follow-up due work
- add timeline events for:
  - stage changes
  - approvals
  - packet milestones
  - follow-up milestones
- improve timeline labels in the right rail

Why this slice next:

- it is the biggest remaining gap versus both original docs
- it deepens the current model instead of changing direction
- it makes the `follow_up` lane genuinely operational
- it improves both daily usability and demo clarity

## How To Use This In A New Session

If starting a new Codex session, point to:

- [Recall_local_Application_Ops_Roadmap.md](/Users/jaydreyer/projects/recall-local/docs/Recall_local_Application_Ops_Roadmap.md)

Helpful companion references:

- [recall-local-application-ops-copilot-prd.md](/Users/jaydreyer/Documents/recall-local-application-ops-copilot-prd.md)
- [recall-local-implementation-checklist.md](/Users/jaydreyer/Documents/recall-local-implementation-checklist.md)
- [Networking_Event_Demo_Runbook.md](/Users/jaydreyer/projects/recall-local/docs/Networking_Event_Demo_Runbook.md)
- [Recall_local_Daily_Dashboard_Reliability_Runbook.md](/Users/jaydreyer/projects/recall-local/docs/Recall_local_Daily_Dashboard_Reliability_Runbook.md)
- [OBSERVABILITY_STRATEGY.md](/Users/jaydreyer/projects/recall-local/docs/OBSERVABILITY_STRATEGY.md)

Suggested kickoff prompt for a future session:

"Read [Recall_local_Application_Ops_Roadmap.md](/Users/jaydreyer/projects/recall-local/docs/Recall_local_Application_Ops_Roadmap.md), confirm the current live state against the PRD and implementation checklist, and implement the next slice: follow-up workflow + richer timeline."
