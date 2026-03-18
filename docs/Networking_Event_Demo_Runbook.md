# Networking Event Demo Runbook

Last updated: 2026-03-17

## Goal

Show Recall.local as an AI Application Ops Copilot, not just a scoring dashboard.

The story:
- it discovers and evaluates roles
- it helps prioritize what matters
- it gives a clear next step
- it helps prepare application materials

## Recommended Demo URL

- Daily dashboard / Ops console:
  - `http://100.116.103.78:3001/`

## Two-Minute Flow

### 1. Start on Overview

Say:
"This is the daily command center. It gives me the current board, the strongest roles, and a fast way into the workflow."

Show:
- the top-level `Overview | Ops` navigation
- the `Jobs` overview board
- the spotlight role and queue lanes

### 2. Open a real role without losing context

Say:
"One problem I fixed was that the old dossier view forced me to scroll through the whole board. Now I can open a role directly in a side dossier."

Show:
- click `Open dossier`
- highlight that the dossier opens as a side drawer
- point out notes, application tip, and cover letter angle

### 3. Move into Ops

Say:
"Overview tells me what needs attention. Ops is where I actually work the opportunity."

Show:
- click `Open in Ops`
- note that the selected role carries over
- point out the wide desktop layout

### 4. Explain the workflow framing

Say:
"This is the demo version of an application ops layer. It derives workflow state, next-best action, blockers, and packet readiness from the role data I already have."

Show:
- selected role in the center workspace
- right rail:
  - workflow state
  - next action
  - blocker
  - timeline

### 5. Show execution support

Say:
"The point is not just analysis. It helps me move forward and prepare materials."

Show one of:
- `Generate Cover Letter Draft`
- `Mark Applied`
- `Save Notes`

If draft generation is fast, use it.
If not, just point at the CTA and explain that the system can draft tailored application support from the role context.

## Three-Minute Version

If there is more time, add:
- `Companies` tab:
  - "I can pivot from roles into company-level signal and tracking."
- `Skill Gaps` tab:
  - "I can see where the market is consistently asking for skills I should strengthen."

Then return to `Ops`.

## What To Emphasize

- "This is human-in-the-loop by design."
- "The system helps me decide what to do next."
- "It turns a job board into an operating workflow."
- "The UX now supports both overview scanning and deep work."

## What To Avoid

- Do not over-explain implementation details first.
- Do not start with model/provider talk.
- Do not spend too long in low-fit or archive roles.
- Do not click into too many tabs before showing Ops.

## Safe Backup Lines

If the board is slow:
- "The live stack is pulling from the same job data and bridge APIs, so I may wait a second for the current role context."

If someone asks what is new:
- "The big shift is from analysis dashboard to application ops workspace."

If someone asks what comes next:
- "The next layer is durable workflow state, approvals, packet generation, and follow-up automation."

## Ideal Demo Role

Choose a role that has:
- a strong fit score
- clear matching skills
- at least one visible gap
- a usable application tip or cover letter angle

That gives the best before-and-after story in Ops.
