# Recall.local — Phase 6D Implementation Brief: Dashboard & Company Profiles

**Parent Document:** `docs/Recall_local_Phase6_Job_Hunt_PRD.md` (read first for full architecture)
**Phase:** 6D — Dashboard, Notifications & Company Profiles
**Est. Effort:** 4-5 days
**Dependencies:** Phase 6A (scaffold running), 6B (jobs in Qdrant), 6C (evaluations complete)

---

## Objective

Build out the Daily Dashboard frontend with the Job Hunt panel, company intelligence profiles, skill gap visualization, settings panel, and score charts. After this phase: Jay opens one page every morning and sees everything he needs.

---

## Design System: Atelier Ops / Luxury Minimal

**CRITICAL:** Study `docs/scaffolds/luxury-minimal.jsx` before writing any frontend code. This dashboard uses a COMPLETELY DIFFERENT aesthetic than the Recall.local ops dashboard.

### Color Tokens

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#FAFAF7` | Page background (warm off-white) |
| Primary text | `#2A2520` | Headings, body text |
| Secondary text | `#8F8578` | Descriptions, subtitles |
| Tertiary text | `#B8AD9E` | Timestamps, metadata, labels |
| Accent | `#E8553A` | Primary actions, active states, CTA buttons |
| Accent hover | `#D04830` | Hover state for accent |
| Status: Active | `#E8553A` | Active items, high scores |
| Status: Pending | `#A0916B` | Queued items, medium scores |
| Status: Complete | `#6B8F71` | Done items, applied status |
| Border | `#E8E2D8` | Thin rules, card borders, dividers |
| Card background | `#FFFFFF` | Input areas, elevated cards |
| Selection | `#E8553A` at 20% opacity | Text selection highlight |

### Typography

| Element | Font | Weight | Size | Spacing |
|---------|------|--------|------|---------|
| Page title | Playfair Display | 400 | 48px | -0.5px |
| Section headers | Manrope | 700 | 10-12px | 2-3px letter-spacing, UPPERCASE |
| Body text | Manrope | 400 | 14px | Normal |
| Card titles | Manrope | 500 | 14px | Normal |
| Timestamps/data | IBM Plex Mono | 400 | 10-11px | 0.5px |
| Buttons | Manrope | 600 | 12px | 1.5px letter-spacing, UPPERCASE |

### UI Patterns

- **Rules, not borders:** Sections separated by 1px `#E8E2D8` lines, not box borders
- **Whitespace is structure:** Generous padding (56px page margins, 40-60px between sections)
- **Animations:** Fade-in with `translateY(16px)`, `cubic-bezier(0.22, 1, 0.36, 1)`, staggered 0.05s delays
- **Inputs:** Transparent background, bottom-border only, accent color on focus
- **Badges:** Small dots (5px circle) + uppercase label, not pill shapes
- **Max width:** 1160px centered
- **Scrollbars:** 4px wide, `#D8D0C4` thumb

### Google Fonts Import

```css
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=IBM+Plex+Mono:wght@300;400;500&display=swap');
```

---

## Task 1: Job Hunt Panel (4-6 hours)

### Stats Bar

Top of the page, single row of key metrics:

- New Today: count of jobs discovered in last 24h
- High Fit: count of jobs scoring 75+
- Average Score: mean fit_score across all evaluated jobs
- Total: total job count

Fetch from `GET /v1/job-stats`. Style as spaced-out data points with IBM Plex Mono numbers, Manrope labels, thin rule below.

### Filters Bar

Below stats. Compact, single row:

- Score range: dropdown (All / 75+ / 50-74 / Under 50)
- Source: dropdown (All / JobSpy / Career Pages / Chrome Extension)
- Company Tier: dropdown (All / Tier 1 / Tier 2 / Tier 3)
- Status: dropdown (All / New / Evaluated / Applied / Dismissed)

Dropdowns styled with transparent background, bottom border, Manrope 13px.

### Job Card List

Scrollable list of job cards. Each card:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Solutions Engineer                    Anthropic   🏅 T2    │
│                                                             │
│  ──────────────────────────────────────────────────         │
│  Score  82                    Remote · 2 days ago           │
│  ──────────────────────────────────────────────────         │
│                                                             │
│  Top match: API governance, AI enablement                   │
│  Top gap: Pre-sales demo experience (moderate)              │
│                                                             │
│  [View Details]          [Mark Applied]         [Dismiss]   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Visual details:**
- Job title in Manrope 500 weight, `#2A2520`
- Company name in `#8F8578`, aligned right
- Tier badge: gold dot for T1, blue-grey dot for T2, muted for T3 (dot + uppercase label pattern from Atelier Ops)
- Score displayed large in IBM Plex Mono, color-coded: `#E8553A` for 75+, `#A0916B` for 50-74, `#8F8578` for under 50
- Top match and top gap in `#4A4540`, 14px
- Action buttons: "View Details" as text link in accent, "Mark Applied" and "Dismiss" as muted outlined buttons
- Cards separated by thin rules, not borders

Fetch from `GET /v1/jobs?status=evaluated&sort=fit_score&order=desc`.

### Job Detail Expanded View

Clicking "View Details" expands the card (or opens a slide-over panel) showing:

- Full job description (scrollable, `#4A4540`, 14px, line-height 1.6)
- Score with rationale (score large in Playfair Display, rationale in body text)
- All matching skills with evidence (two-column: skill name | resume evidence)
- All gaps with severity badges and recommendations
  - Each recommendation: type icon, title, source, effort estimate
  - Styled as a clean list with thin rule separators
- Application tips (accent-bordered aside card)
- Cover letter angle (accent-bordered aside card)
- Action buttons: Mark Applied, Dismiss, Add Notes, Re-evaluate
- "Generate Cover Letter Draft" button (calls Ollama)
- Link to original posting (opens new tab)

---

## Task 2: Score Distribution Chart (1 hour)

Small Recharts bar chart showing fit score distribution across all evaluated jobs.

- X axis: score ranges (0-24, 25-49, 50-74, 75-100)
- Y axis: job count
- Bar colors: match the score color scheme (muted → accent progression)
- Placed near the stats bar or in a sidebar

Helps Jay see: are most jobs clustering at 40-60 (search needs tuning) or 70-90 (well-targeted)?

---

## Task 3: Skill Gap Radar (2-3 hours)

Pulls from `GET /v1/job-gaps`.

### Layout

```
YOUR TOP GAPS ACROSS ALL EVALUATED JOBS

Kubernetes (12 jobs)          ██████████████████░░░ moderate
Pre-sales demos (8 jobs)      ████████████░░░░░░░░░ moderate
Go language (5 jobs)          ████████░░░░░░░░░░░░░ minor
Terraform/IaC (4 jobs)        ██████░░░░░░░░░░░░░░░ minor

[View Recommendations →]
```

- Horizontal bars using the accent color palette
- Frequency count in IBM Plex Mono
- Severity as a badge (dot + label)
- Bar width proportional to frequency (widest gap = full width)

### Recommendations View

Clicking "View Recommendations" shows a detailed breakdown:

- For each gap: expandable section
  - List of specific recommendations (course, project, video, certification)
  - Each recommendation: type pill, title, source, effort estimate
  - Manual checkboxes: "I completed this" (stored in SQLite)
- A "Learning Plan" tab that sequences recommendations by impact × effort

---

## Task 4: Company Intelligence Profiles (3-4 hours)

### Companies List View

A new "Companies" section/tab. Card grid layout:

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  [Logo]      │  │  [Logo]      │  │  [Logo]      │
│  Anthropic   │  │  Glean       │  │  Postman     │
│  🏅 Tier 2   │  │  🏅 Tier 2   │  │  🏅 Tier 1   │
│  2 jobs      │  │  1 job       │  │  3 jobs      │
│  Avg: 75     │  │  Avg: 71     │  │  Avg: 84     │
└──────────────┘  └──────────────┘  └──────────────┘
```

- Sorted by average fit score (highest first)
- Cards: white background, thin border, subtle hover elevation

### Company Logos

**Primary:** Clearbit Logo API — `https://logo.clearbit.com/{domain}`
Example: `https://logo.clearbit.com/anthropic.com`

**Fallback:** Google Favicon Service — `https://www.google.com/s2/favicons?domain={domain}&sz=64`

**Final fallback:** Styled monogram — first letter of company name in Playfair Display, 32px, centered in a 64x64 circle with accent background.

Display at 64x64px, border-radius 8px, subtle warm shadow (`0 2px 8px rgba(42,37,32,0.08)`).

### Company Profile Page

Clicking a company card opens a full profile page. Layout:

**Header:**
- Logo (64x64) + company name (Playfair Display, 28px)
- Metadata chips: HQ location, size, funding stage, remote policy
- Tier badge
- Link to careers page

**About:**
- 2-3 sentence AI-generated description in natural prose
- Source note: "Auto-generated from job postings" or "From career page data"

**Two-Column Cards:**
- "What They Look For" card — key skills/traits this company values
- "Your Connection" card — warm-toned aside (left border `#A0916B`) showing Jay's existing relationship

**Jobs from This Company:**
- Mini job cards sorted by fit score
- Aggregate: "Average fit score: 75 across 2 roles"

**Key Skills They Value:**
- Horizontal bar chart (Recharts) showing skill frequency across all postings from this company
- Same visual language as Skill Gap Radar
- Colors: accent palette, warm tones

### Company Profile Service

Create `scripts/phase6/company_profiler.py`:

When first job from a new company is ingested:
1. Check SQLite `company_profiles` table
2. If not found, generate profile using Ollama (or cloud if toggled)
3. Use job description as primary context
4. If company is in `config/career_pages.json`, include `your_connection`
5. Store in SQLite
6. For subsequent jobs: update (merge new info, don't overwrite)

### Company API Endpoints

Implement in `scripts/phase1/ingest_bridge_api.py` with company-profile logic in `scripts/phase6/company_profiler.py`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/companies` | List all company profiles |
| `GET` | `/v1/companies/{companyId}` | Single profile with jobs and skill chart data |
| `POST` | `/v1/company-profile-refresh-runs` | Re-generate profile from latest data |

---

## Task 5: LLM Settings Panel (1-2 hours)

Accessible from a gear icon in the dashboard header. Clean modal or slide-over panel.

### Settings Fields

- **Evaluation Model:** Toggle switch — "Local (Ollama)" / "Cloud"
- **Cloud Provider:** Dropdown — Anthropic / OpenAI
- **Cloud Model:** Dropdown — Claude Sonnet 4.5 / Claude Opus 4.5 / GPT-4o
- **Auto-Escalate:** Toggle — "Automatically use cloud when local quality is poor"
- **Escalation Threshold:** Slider or inputs for minimum gaps count and rationale word count

Reads/writes `GET/PATCH /v1/llm-settings`.

Style: Manrope labels, thin-bordered inputs, accent toggle switches.

---

## Task 6: Cover Letter Draft Generator (1-2 hours)

The "Generate Cover Letter Draft" button on the job detail view.

### Flow

1. User clicks button on a job detail
2. Show loading state ("Arthur is drafting...")
3. Call Ollama (or cloud) with:
   - Jay's resume (from `recall_resume`)
   - The job description
   - The `cover_letter_angle` from the evaluation
   - Prompt: "Write a cover letter for this role. The candidate's strongest angle is: {cover_letter_angle}. Be specific, reference real experience from the resume, and keep it under 400 words."
4. Display the draft in a styled text area
5. "Copy to clipboard" button
6. Optional: "Save to Obsidian" button (writes to vault if write-back is enabled)

---

## Task 7: Docker & Polish (2 hours)

### Docker Compose Updates

The `daily-dashboard` service should already exist from the 6A scaffold. Verify:
- Builds correctly from `ui/daily-dashboard/Dockerfile`
- Nginx serves the Vite build on port 3001
- API requests proxy correctly to the bridge

### End-to-End Testing

Walk through the complete flow:
1. Open Daily Dashboard at `http://server:3001`
2. See stats bar with real data
3. Filter jobs by score/source/tier
4. Expand a job detail — verify evaluation data displays
5. Click a company name — verify company profile loads
6. Check Skill Gap Radar — verify gaps are aggregated
7. Toggle LLM setting — verify it persists
8. Generate a cover letter draft — verify it works
9. Mark a job as "Applied" — verify status updates

---

## Definition of Done

- [ ] Dashboard displays real job data from the API
- [ ] Stats bar shows accurate counts
- [ ] Filters work correctly across all dimensions
- [ ] Job cards render with proper tier badges and color-coded scores
- [ ] Job detail expanded view shows full evaluation
- [ ] Score distribution chart renders
- [ ] Skill Gap Radar displays aggregated gaps with bars
- [ ] Recommendations view shows actionable suggestions
- [ ] Company list page shows logo grid sorted by score
- [ ] Company profile page shows rich, visually interesting profiles with logos, charts, connection cards
- [ ] LLM settings panel reads and writes configuration
- [ ] Cover letter draft generator works
- [ ] All UI follows Atelier Ops / Luxury Minimal design system
- [ ] Dashboard runs in Docker and is accessible at port 3001

---

## Files Created/Modified

| File | Action |
|------|--------|
| `ui/daily-dashboard/src/components/JobHuntPanel.jsx` | CREATE |
| `ui/daily-dashboard/src/components/JobCard.jsx` | CREATE |
| `ui/daily-dashboard/src/components/JobDetail.jsx` | CREATE |
| `ui/daily-dashboard/src/components/SkillGapRadar.jsx` | CREATE |
| `ui/daily-dashboard/src/components/ScoreDistribution.jsx` | CREATE |
| `ui/daily-dashboard/src/components/StatsBar.jsx` | CREATE |
| `ui/daily-dashboard/src/components/Filters.jsx` | CREATE |
| `ui/daily-dashboard/src/components/CompanyProfile.jsx` | CREATE |
| `ui/daily-dashboard/src/components/CompanyList.jsx` | CREATE |
| `ui/daily-dashboard/src/components/SettingsPanel.jsx` | CREATE |
| `ui/daily-dashboard/src/components/CoverLetterDraft.jsx` | CREATE |
| `ui/daily-dashboard/src/components/FutureWidgetSlot.jsx` | CREATE |
| `ui/daily-dashboard/src/hooks/useJobs.js` | CREATE |
| `ui/daily-dashboard/src/hooks/useCompanies.js` | CREATE |
| `ui/daily-dashboard/src/hooks/useSettings.js` | CREATE |
| `ui/daily-dashboard/src/styles/theme.css` | CREATE/MODIFY |
| `scripts/phase6/company_profiler.py` | CREATE |
| `scripts/phase1/ingest_bridge_api.py` | MODIFY (add `/v1/companies*` and `/v1/company-profile-refresh-runs`) |
