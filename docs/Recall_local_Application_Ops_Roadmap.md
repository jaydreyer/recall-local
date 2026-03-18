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

Last refreshed: 2026-03-18

## Snapshot

The Application Ops upgrade is no longer just a concept or demo shell. It now has a real workflow foundation inside the live dashboard.

Practical status:

- demo-ready UX and product framing: strong
- workflow foundation and execution model: real and usable
- full PRD completion: not finished yet

Estimated completion against the original docs:

- around 72-82% of the intended product
- around 88-92% of the visible demo and UX shape

## Current Live State

The live app now includes:

- top-level `Overview | Ops` navigation
- overview-to-ops handoff
- fixed dossier access through an attached detail surface instead of forced page scroll
- desktop-first Ops workspace that uses browser real estate much better
- persisted workflow state on jobs
- persisted workflow stages driving Ops lanes
- packet checklist and approval state persisted through the backend
- packet artifact metadata now persists for cover letter drafts, tailored summaries, and operator-linked packet deliverables
- packet readiness now reconciles checklist state with artifact truth
- persisted next-action recommendations now include action, rationale, confidence, and due date
- persisted follow-up metadata now supports due dates and completion tracking
- workflow timeline support with richer persisted event semantics
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

Status: `mostly done for v1, partial for deeper copilot logic`

What is done:

- next action is visible in the product
- action framing exists in Ops and supports the demo story
- persisted `nextAction` now stores action, rationale, confidence, and due date
- Ops can sync the recommendation into durable workflow state

What is still missing:

- action selection is still simpler than the PRD's intended copilot logic
- recalculation behavior is not yet a fully formalized workflow service

#### 3. Blocker detection

Status: `partial to mostly done`

What is done:

- blocker concepts are visible in the UI
- blockers are part of the workflow framing in Ops

What is still missing:

- blockers are still lighter-weight and more heuristic than the PRD/checklist intended
- blocker logic is not yet a robust backend engine with richer sources of truth

#### 4. Activity timeline and event logging

Status: `mostly done for v1 UI semantics, partial for deeper backend durability`

What is done:

- timeline support exists in Ops
- workflow-oriented events are visible enough for demo and basic operator context
- persisted timeline events now distinguish approvals, workflow changes, packet milestones, follow-up milestones, artifacts, and application history
- timeline labels are now more human-readable and the right rail better separates persisted versus derived history

What is still missing:

- more durable event logging model
- deeper backend/API/test coverage around event creation and retrieval beyond the current workflow payload model

#### 5. Application packet generation

Status: `partial to mostly done for the current demo/product slice`

What is done:

- packet concept exists in the product
- packet checklist state exists and persists
- cover letter generation is already part of the broader Recall.local product story
- cover letter draft status is now linked to persisted artifact metadata
- tailored summary generation is now a first-class packet artifact flow
- non-cover-letter packet items can now carry persisted linked-artifact metadata from Ops
- packet readiness now depends on both checklist state and artifact truth in Ops queue logic

What is still missing:

- resume bullets, outreach note, interview brief, and talking points do not yet have dedicated generators/services
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

Status: `partial`

What is done:

- follow-up exists as a workflow concept and lane direction
- applied roles can be framed as moving into follow-up work
- persisted follow-up due dates and completion state now exist
- Ops now has a real `Follow-up due` filter/summary and follow-up controls

What is still missing:

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
- next-action recommendation persisted through the backend
- follow-up workflow persisted through the backend
- packet artifact metadata persisted through the backend
- richer workflow timeline metadata persisted through the backend
- tailored summary artifact generation via `POST /v1/tailored-summaries`
- cover letter draft generation via `POST /v1/cover-letter-drafts`
- packet readiness reconciled from checklist state plus artifact truth
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

#### 1. Real packet / artifact linkage

- add dedicated generators/services for:
  - resume bullets
  - outreach note
  - interview brief
  - talking points
- connect remaining packet checklist items to actual generated or saved artifacts where possible
- expand durable references to packet components beyond summary + cover letter
- continue tightening packet readiness so approval depends on actual artifact-backed packet truth

#### 2. Follow-up workflow and reminders

- support richer reminder metadata such as:
  - reminder created flag
  - reminder delivery metadata
  - reminder status / last reminder run
- wire follow-up reminder automation into n8n if desired

#### 3. Next-best-action and blocker depth

- formalize persisted next action fields
- add rationale, confidence, and suggested due date as real workflow data
- improve blocker generation from real workflow/artifact state
- make action recalculation more intentional and testable

#### 4. API and test hardening

- add broader contract coverage for workflow stage changes
- add broader contract coverage for packet and approval updates
- add broader contract coverage for timeline behavior
- add broader contract coverage for follow-up workflow beyond the focused cases already added
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

1. packet / artifact linkage
2. follow-up reminders and automation
3. persisted next-action and blocker depth
4. API and test hardening
5. UX polish pass
6. UX polish pass
7. saved views and recommendation improvements
8. portfolio packaging

## Suggested Next Slice

The best next implementation slice is:

### Packet artifact expansion

Scope:

- add the next real packet artifact flow after tailored summary:
  - outreach note, or
  - resume bullets
- persist generated artifact metadata into workflow packet state
- expose generation directly in the role workspace
- let packet readiness benefit from the new artifact truth automatically

Why this slice next:

- it is now the clearest remaining gap between the current demo and a genuinely artifact-backed application packet
- it deepens the model that is already working instead of introducing a new workflow direction
- it improves both daily usability and the product story immediately

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

"Read [Recall_local_Application_Ops_Roadmap.md](/Users/jaydreyer/projects/recall-local/docs/Recall_local_Application_Ops_Roadmap.md), confirm the current live state against the PRD and implementation checklist, and implement the next slice: add the next real packet artifact flow after tailored summary."
