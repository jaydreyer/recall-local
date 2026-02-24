# Recall.local — Phase 5: UI, Chrome Extension, Obsidian Integration & Final Sprint

**For:** Codex implementation
**From:** Architecture review session (Claude Opus, 2026-02-23)
**Context:** Codebase is ~70% to production MVP. Core RAG pipeline is solid. This document covers the remaining workstreams to reach demo-ready status.

## Confirmed Project Decisions (2026-02-24)

These decisions supersede any conflicting guidance in this brief:

1. FastAPI migration is approved and is task 1.
2. Dashboard deploys as separate `recall-ui` container.
3. Obsidian write-back is opt-in (`RECALL_VAULT_WRITE_BACK=false` default).
4. Gmail extension support is deferred to `5E.1` after extension base stability.
5. Auth policy is optional local mode:
   - no key set => no auth enforcement + startup warning
   - key set => enforce `X-API-Key`.
6. Obsidian deployment model is Mac-primary vault with Syncthing mirror to ai-lab.
7. This brief and scaffold files are tracked planning assets in-repo.

---

## Table of Contents

1. [Workstream 1: Dashboard UI](#workstream-1-dashboard-ui)
2. [Workstream 2: Chrome Extension](#workstream-2-chrome-extension)
3. [Workstream 3: Obsidian Integration](#workstream-3-obsidian-integration)
4. [Workstream 4: Production Hardening](#workstream-4-production-hardening)
5. [Implementation Order](#implementation-order)
6. [File Reference](#file-reference)

---

## Workstream 1: Dashboard UI

### Why This Matters
The HTTP bridge API (`ingest_bridge_api.py`) already exposes the right endpoints. But without a UI, the system requires curl commands or n8n workflows to operate. For both daily usability and interview demos, we need a lightweight web frontend.

### Architecture Decision
**FastAPI bridge migration first, with dashboard as a separate lightweight container.**

Recommended stack:
- **React** (Vite for build tooling)
- **No component library** — keep it minimal, custom styles
- Communicates with existing bridge API endpoints
- Runs as a dedicated Docker container (`recall-ui`) alongside the bridge

### Design System
- Dark theme (near-black background: `#0a0a0a`)
- Amber/gold accent: `#f59e0b`
- Group colors: Job Search `#f59e0b`, Learning `#8b5cf6`, Project `#22c55e`, Reference `#6366f1`, Meeting `#ec4899`
- Monospace font: IBM Plex Mono for data, labels, code
- Sans font: Instrument Sans (or system sans) for body text
- Minimal chrome — the data is the UI
- Reference scaffold: `docs/scaffolds/recall-dashboard.jsx`

### UI Tabs & Functionality

#### Tab 1: Ingest
- **URL paste box** → `POST /ingest/url` with `{ "url": "...", "group": "...", "tags": [...] }`
- **File drag-and-drop zone** → `POST /ingest/file` (needs new endpoint — multipart upload, saves to `data/incoming/`, triggers pipeline)
- **Group selector + tag picker** — same UX as Chrome extension popup (see Workstream 2). Auto-detect group from URL patterns, show suggested tags contextual to selected group.
- **Quick actions:**
  - "Check Email" → `POST /ingest/email` (triggers IMAP poll)
  - "Sync Vault" → `POST /ingest/obsidian` (triggers vault sync — see Workstream 3)
  - "Google Doc" → `POST /ingest/gdoc` with `{ "url": "..." }`
  - "Paste Text" → `POST /ingest/text` with `{ "content": "...", "title": "..." }`

**New endpoint needed:** `POST /ingest/file` — accept multipart file upload, save to `data/incoming/`, call `ingest_incoming_once.py`

#### Tab 2: Query
- Chat interface hitting `POST /query/rag`
- Mode selector: Default, Job Search, Learning (maps to existing `mode` parameter)
- Display sources/chunks cited in response
- Persist conversation in-memory (no backend chat history needed for MVP)

#### Tab 3: Activity
- Pulls from SQLite `recall.db` — show recent ingestion events
- Columns: type icon, source, group badge, timestamp, chunk count, status
- Group filter bar: `[All] [Job Search (23)] [Learning (12)] [Project (8)] [Reference (4)]`
- Auto-refresh every 30 seconds

**New endpoint needed:** `GET /activity` — query SQLite `run_log` table, return last N ingestion events as JSON. Support `?group=job-search` filter parameter.

#### Tab 4: Eval
- Show last eval run results from SQLite or eval output files
- Pass rate bar, avg latency, suite breakdown
- "Run Eval" button → triggers eval harness

**New endpoint needed:** `GET /eval/latest` — read latest eval results. `POST /eval/run` — trigger eval suite async.

#### Tab 5: Vault
- Show Obsidian vault file tree (read from configured vault path)
- "Sync Now" button
- Show sync status and last sync time

**New endpoint needed:** `GET /vault/tree` — list vault files. `POST /vault/sync` — trigger sync.

---

## Workstream 2: Chrome Extension

### Why This Matters
The dashboard handles ingestion when you're already at the Recall UI. The Chrome extension handles ingestion when you're anywhere else — browsing, reading Gmail, researching companies. This is the "frictionless capture" layer.

### Architecture
```
chrome-extension/
├── manifest.json          # Permissions, context menus, keyboard shortcuts
├── background.js          # Service worker: context menu handler, API calls
├── popup.html + popup.js  # Toolbar popup: group/tag selector, ingest confirmation
├── gmail.js               # Content script injected on mail.google.com
├── config.js              # API URL, API key, auto-tag rules (fetched from bridge)
├── icons/                 # Recall.local logo at 16, 48, 128px
└── styles.css             # Popup styling (matches dashboard design system)
```

### Features
1. **Toolbar button** — click on any page to open the ingest popup
2. **Right-click context menu** → "Send to Recall" on any page, link, or selected text
3. **Gmail integration (deferred to 5E.1)** — content script injects "⊡ Recall" button into Gmail's email toolbar (next to Archive, Delete, etc.)
4. **Keyboard shortcut** → `Ctrl+Shift+R` to open popup instantly
5. **Auto-detection** → pre-selects group and tags based on URL and page content

### Ingest Popup UX

Reference scaffold: `docs/scaffolds/recall-chrome-popup.jsx`

The popup appears when the user clicks the toolbar button or uses the keyboard shortcut. Key UX principles:

**Auto-detection layer** — the popup pre-selects group and tags so 90% of the time the user just glances and hits "Ingest":
- URL pattern matching determines group (see Auto-Tag Rules below)
- URL domain and page title determine initial tags
- User can override everything with one click

**Popup layout:**
```
┌─────────────────────────────────┐
│  ⊡ Recall.local           [●]  │  ← header + health dot
├─────────────────────────────────┤
│  Page Title Being Ingested      │  ← pulled from document.title
│  https://url.being.ingested/... │  ← current tab URL
├─────────────────────────────────┤
│  GROUP                          │
│  [🎯 Job Search] [📚 Learning] │  ← pre-selected via auto-detect
│  [🔧 Project] [📌 Reference]   │
│  [📋 Meeting]                   │
├─────────────────────────────────┤
│  TAGS             auto-detected │
│  [anthropic ×] [se-role ×]      │  ← removable, pre-populated
│  [+ type to add tag         ]   │  ← free-text input
│  + cohere  + glean  + writer    │  ← suggested tags for group
├─────────────────────────────────┤
│  ☑ Extract full page text       │
│  ☐ Save to vault                │  ← also saves to Obsidian
├─────────────────────────────────┤
│           [Cancel] [Ingest → 🎯]│
└─────────────────────────────────┘
```

**After sending:** popup shows confirmation with group badge and tags, auto-closes after 2 seconds.

### Auto-Tag Rules

Store in a JSON config file that both the Chrome extension and dashboard UI read from. Adding a new group is a single JSON edit — no code changes in either UI.

The Chrome extension fetches this config from `GET /config/auto-tags` on the bridge API.

```json
// config/auto_tag_rules.json
{
  "groups": [
    { "id": "job-search", "label": "Job Search", "icon": "🎯", "color": "#f59e0b" },
    { "id": "learning", "label": "Learning", "icon": "📚", "color": "#8b5cf6" },
    { "id": "project", "label": "Project", "icon": "🔧", "color": "#22c55e" },
    { "id": "reference", "label": "Reference", "icon": "📌", "color": "#6366f1" },
    { "id": "meeting", "label": "Meeting", "icon": "📋", "color": "#ec4899" }
  ],
  "url_patterns": {
    "job-search": [
      "linkedin.com/jobs", "lever.co", "greenhouse.io",
      "anthropic.com/careers", "openai.com/careers",
      "boards.greenhouse.io"
    ],
    "learning": [
      "arxiv.org", "huggingface.co", "docs.qdrant.tech",
      "python.langchain.com", "docs.anthropic.com",
      "paperswithcode.com", "readthedocs.io"
    ],
    "project": [
      "github.com"
    ]
  },
  "url_tag_patterns": {
    "anthropic.com": ["anthropic"],
    "openai.com": ["openai"],
    "cohere.com": ["cohere"],
    "cohere.ai": ["cohere"],
    "glean.com": ["glean"],
    "writer.com": ["writer"],
    "arxiv.org": ["research"],
    "github.com": ["code"]
  },
  "title_patterns": {
    "job-search": ["resume", "cv", "cover letter", "job description"],
    "meeting": ["meeting", "notes", "transcript", "action items"]
  },
  "email_senders": {
    "job-search": ["@anthropic.com", "@openai.com", "@lever.co", "@greenhouse.io"]
  },
  "filename_patterns": {
    "job-search": ["resume", "cv", "cover.letter", "jd", "job.description"],
    "meeting": ["meeting", "notes", "transcript", "action.items"]
  },
  "vault_folders": {
    "career": "job-search",
    "learning": "learning",
    "projects": "project",
    "references": "reference",
    "daily": "reference"
  },
  "suggested_tags": {
    "job-search": ["anthropic", "openai", "cohere", "glean", "writer", "job-description", "se-role", "recruiter", "interview-prep"],
    "learning": ["rag", "vector-db", "prompt-engineering", "llm", "python", "api-design", "mcp"],
    "project": ["recall-local", "tone-poet", "myrsdlist", "home-lab"],
    "reference": ["article", "blog-post", "tutorial", "bookmark"],
    "meeting": ["action-items", "transcript", "follow-up"]
  }
}
```

**Adding new groups:** Edit this JSON file — add a new entry to `groups`, add URL patterns, add suggested tags. No code changes needed.

**New endpoint needed:** `GET /config/auto-tags` — serve the contents of `config/auto_tag_rules.json`.

### API Payload
All ingest endpoints accept optional `group` and `tags`:
```json
POST /ingest/url
{
  "url": "https://anthropic.com/careers/solutions-engineer",
  "group": "job-search",
  "tags": ["anthropic", "se-role", "job-description"],
  "save_to_vault": false
}
```

These get stored as Qdrant payload metadata on every chunk:
```python
payload = {
    "source": url_or_filename,
    "source_type": "url",
    "group": group or "reference",   # default if not specified
    "tags": tags or [],
    "ingested_at": timestamp,
    "chunk_index": i,
    "content": chunk_text
}
```

### Gmail Content Script
When the user is on `mail.google.com`, inject a content script that:
1. Watches for the Gmail DOM (email view)
2. Injects a small "⊡ Recall" button in the email action toolbar
3. On click, extracts: subject, sender, body text, attachment names
4. Opens the same ingest popup pre-filled with email content
5. Auto-detects group based on sender (using `email_senders` rules)

---

## Workstream 3: Obsidian Integration

### Concept
Obsidian is a local-first markdown knowledge base. It's a natural fit for Recall.local because:
1. Both are local-first and privacy-focused
2. Obsidian vaults are just folders of `.md` files — trivial to ingest
3. Bidirectional sync creates a powerful loop: notes → RAG knowledge → generated insights → back to notes

### Vault Structure
Configure a vault at a known path (e.g., `~/obsidian-vault/` or configurable via `RECALL_VAULT_PATH` in `.env`).

```
obsidian-vault/
├── daily/                    # Daily notes (Obsidian daily notes plugin)
│   ├── 2026-02-23.md
│   ├── 2026-02-22.md
│   └── ...
├── projects/                 # Active project notes
│   ├── recall-local.md       # This project's running notes
│   ├── tone-poet-tracker.md
│   └── job-search.md
├── career/                   # Job search & career development
│   ├── target-companies.md   # Research on Anthropic, OpenAI, Cohere, etc.
│   ├── interview-prep.md     # Questions, talking points, STAR stories
│   ├── se-role-research.md   # Solutions Engineer role analysis
│   ├── networking-log.md     # People, conversations, follow-ups
│   └── offer-evaluation.md   # Compensation frameworks, decision criteria
├── learning/                 # Technical learning & research
│   ├── rag-patterns.md
│   ├── vector-databases.md
│   ├── prompt-engineering.md
│   └── mcp-servers.md
├── references/               # Imported reference material (from Recall)
│   ├── api-governance-notes.md
│   ├── gap-chatbot-metrics.md
│   └── ...
├── recall-artifacts/         # Auto-generated by Recall.local
│   ├── query-results/        # Saved RAG query outputs
│   ├── meeting-actions/      # Extracted action items
│   └── digests/              # Weekly summaries, trend reports
├── templates/                # Obsidian templates
│   ├── daily-note.md
│   ├── project-note.md
│   ├── interview-debrief.md
│   └── learning-note.md
└── _attachments/             # Images, PDFs referenced by notes
```

### Deployment Model: Mac Obsidian + Syncthing Mirror on ai-lab

Use Mac as primary authoring vault and Syncthing to mirror to ai-lab path used by Recall sync workers.

```
Mac Obsidian vault (primary) <-> Syncthing <-> ai-lab mirrored vault (ingestion path)
```

Implementation implications:

1. `RECALL_VAULT_PATH` should point to the mirrored vault path on ai-lab.
2. Watcher must handle Syncthing move events (`on_moved`) as primary change signal.
3. Exclude Syncthing temporary artifacts (`.syncthing.*`, `.tmp`) from ingestion.
4. Keep debounce enabled to avoid duplicate ingestion from bursty sync events.

### How Obsidian Talks to Recall.local

#### Direction 1: Vault → Recall (Ingestion)
A **file watcher** monitors the vault directory for new or modified `.md` files and ingests them into the RAG pipeline.

Implementation approach:
```python
# scripts/phase5/vault_sync.py
import os, time, hashlib, sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

VAULT_PATH = os.getenv("RECALL_VAULT_PATH", os.path.expanduser("~/obsidian-vault"))
SYNC_DB = "data/vault_sync.db"  # Track file hashes to detect changes
EXCLUDE_DIRS = {"_attachments", ".obsidian", ".trash", "recall-artifacts"}

class VaultHandler(FileSystemEventHandler):
    def on_moved(self, event):
        if event.dest_path.endswith(".md") and not self._is_excluded(event.dest_path):
            self._ingest(event.dest_path)

    def on_modified(self, event):
        if event.src_path.endswith(".md") and not self._is_excluded(event.src_path):
            self._ingest(event.src_path)

    def on_created(self, event):
        if event.src_path.endswith(".md") and not self._is_excluded(event.src_path):
            self._ingest(event.src_path)

    def _is_excluded(self, path):
        if ".syncthing." in path or path.endswith(".tmp"):
            return True
        return any(exc in path for exc in EXCLUDE_DIRS)

    def _ingest(self, filepath):
        # 1. Hash file content
        # 2. Check hash against vault_sync.db
        # 3. If new or changed, call ingestion_pipeline with source_type="obsidian"
        # 4. Determine group from vault folder (using vault_folders mapping in auto_tag_rules.json)
        # 5. Extract Obsidian metadata (wiki-links, tags, frontmatter)
        # 6. Tag chunks with vault path for retrieval filtering
        pass
```

Key decisions:
- **Exclude `recall-artifacts/`** from ingestion to prevent feedback loops
- **Exclude `.obsidian/`** (config files, not content)
- **Group derived from vault folder** — `career/` → `job-search`, `learning/` → `learning` (using `vault_folders` mapping in `auto_tag_rules.json`)
- **Tag ingested chunks** with `source: obsidian` and `vault_path: career/target-companies.md` for filtered retrieval
- **Hash-based change detection** — only re-ingest files that actually changed
- **Debounce** — Obsidian saves frequently; batch changes with a 5-second debounce window
- Vault sync can run as a **daemon** (long-running watcher) or **one-shot** (sync all changed files, exit)

#### Direction 2: Recall → Vault (Output)
When Recall generates useful artifacts, save them as Obsidian-compatible markdown:

```python
def save_to_vault(content, category, title):
    """Save a Recall artifact as an Obsidian note."""
    vault_path = os.getenv("RECALL_VAULT_PATH")
    output_dir = os.path.join(vault_path, "recall-artifacts", category)
    os.makedirs(output_dir, exist_ok=True)

    frontmatter = f"""---
created: {datetime.now().isoformat()}
source: recall-local
type: {category}
tags: [recall-generated, {category}]
---

"""
    filepath = os.path.join(output_dir, f"{title}.md")
    with open(filepath, "w") as f:
        f.write(frontmatter + content)
```

Artifact types to save back:
- **Query results** — triggered by "Save to vault" checkbox in UI or extension
- **Meeting action items** — extracted from meeting notes
- **Weekly digests** — auto-generated summaries of what was ingested/queried
- **Learning summaries** — when learning mode produces study guides

#### Direction 3: Obsidian Links → Enhanced Retrieval
Parse Obsidian's `[[wiki-links]]` and `#tags` during ingestion:

```python
import re

def extract_obsidian_metadata(content):
    wiki_links = re.findall(r'\[\[([^\]]+)\]\]', content)
    tags = re.findall(r'(?:^|\s)#(\w[\w/-]*)', content)
    frontmatter = {}
    if content.startswith('---'):
        end = content.find('---', 3)
        if end != -1:
            # Parse YAML between --- delimiters
            pass
    return {
        "wiki_links": wiki_links,
        "tags": tags,
        "frontmatter": frontmatter
    }
```

- Store `wiki_links` as chunk metadata in Qdrant — enables "find everything linked to X"
- Store `tags` as filterable payload fields — enables `#interview-prep` scoped queries

### New Environment Variables
```bash
RECALL_VAULT_PATH=~/obsidian-vault
RECALL_VAULT_SYNC_MODE=watch    # "watch" for daemon, "once" for one-shot
RECALL_VAULT_DEBOUNCE_SEC=5
RECALL_VAULT_EXCLUDE_DIRS=_attachments,.obsidian,.trash,recall-artifacts
RECALL_VAULT_WRITE_BACK=false   # Opt-in: enable Recall → Vault artifact saving
RECALL_VAULT_IS_SYNCED=true     # Syncthing mirror mode (move-event handling)
```

### Obsidian Plugins to Install (User Setup)
- **Daily Notes** (core plugin) — for the daily/ folder convention
- **Templates** (core plugin) — for consistent note structure
- **Dataview** (community plugin) — query Recall-generated notes with metadata
- **Obsidian Git** (community plugin, optional) — backup vault to a private repo

---

## Workstream 4: Production Hardening

### 4A: API Authentication (Priority: CRITICAL)
```python
API_KEY = os.getenv("RECALL_API_KEY", "")

def check_auth(headers):
    if not API_KEY:
        return True  # No key configured = local-only mode
    return headers.get("X-API-Key") == API_KEY

def startup_warning():
    if not API_KEY:
        print("⚠ No RECALL_API_KEY set — API is unauthenticated (local-only mode)")
```
- Dashboard and Chrome extension send `X-API-Key` header with every request
- Key stored in `.env` as `RECALL_API_KEY`
- If no key is set, auth is bypassed (backward compatible)

### 4B: Rate Limiting (Priority: HIGH)
```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests=60, window_seconds=60):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, client_ip):
        now = time.time()
        self.requests[client_ip] = [
            t for t in self.requests[client_ip] if now - t < self.window
        ]
        if len(self.requests[client_ip]) >= self.max_requests:
            return False
        self.requests[client_ip].append(now)
        return True
```

### 4C: Tests (Priority: HIGH)
```
tests/
├── conftest.py              # Shared fixtures (mock Qdrant, mock Ollama, temp SQLite)
├── test_ingestion.py        # 5-6 tests
├── test_retrieval.py        # 4-5 tests
├── test_rag_query.py        # 3-4 tests
├── test_llm_client.py       # 3-4 tests
├── test_vault_sync.py       # 3-4 tests
├── test_bridge_api.py       # 3-4 tests
└── test_auto_tag.py         # 3-4 tests
```
Target: 25-30 tests. Use mocks for external services — don't require a running stack to pass.

### 4D: Docker Compose Consolidation (Priority: HIGH)
Single `docker-compose.yml` at project root bringing up: Qdrant, Ollama (with GPU), n8n, recall-bridge, recall-ui, mkdocs. Include health checks and restart policies.

### 4E: Cloud Provider Retry Parity (Priority: MEDIUM)
Extract Ollama retry logic into shared decorator, apply to Anthropic/OpenAI/Gemini providers.

---

## Implementation Order

| # | Task | Est. Effort | Dependency |
|---|------|-------------|------------|
| 1 | FastAPI migration (replace `http.server` bridge) | 3-4 hours | None |
| 2 | API key auth + startup warning | 1-2 hours | FastAPI |
| 3 | Rate limiting middleware | 1 hour | FastAPI |
| 4 | Auto-tag rules JSON config (`config/auto_tag_rules.json`) | 1 hour | None |
| 5 | Pytest scaffolding + 25-30 tests | 1-2 days | None |
| 6 | Docker Compose consolidation | 4 hours | FastAPI |
| 7 | New endpoints (file upload, activity, eval, vault, config) | 4-6 hours | FastAPI + Auth |
| 8 | Group + tag support in ingestion pipeline (Qdrant payload) | 2-3 hours | Auto-tag config |
| 9 | Obsidian vault sync script (watcher + one-shot + Syncthing handling) | 4-6 hours | Group/tag support |
| 10 | Obsidian metadata extraction (wiki-links, tags, frontmatter) | 2 hours | Vault sync |
| 11 | Recall → Vault artifact writing (opt-in) | 2 hours | Vault sync |
| 12 | Dashboard UI (React app, 5 tabs) | 2-3 days | New endpoints |
| 13 | Chrome extension: popup + context menu + shortcut | 3-4 hours | Auth, auto-tag config |
| 14 | Cloud provider retry parity | 2 hours | None |
| 15 | Demo recording + README polish | Half day | Everything |
| 5E.1 | Chrome extension: Gmail content script | 3-4 hours | Extension stable |

**Total estimated: ~10-12 working days**

---

## File Reference

| File | Purpose | Location in Repo |
|------|---------|-----------------|
| This document | Implementation brief for Codex | `docs/phase5-implementation-brief.md` |
| Dashboard UI scaffold | Visual reference for React app | `docs/scaffolds/recall-dashboard.jsx` |
| Chrome popup scaffold | Visual reference for extension popup | `docs/scaffolds/recall-chrome-popup.jsx` |
| Auto-tag rules config | Group/tag configuration | `config/auto_tag_rules.json` |

---

## Notes for Codex

- The UI scaffolds are visual references, not production code. Use them for layout and UX direction but implement with proper project structure (Vite + React for dashboard, Manifest V3 for extension).
- FastAPI migration is approved and should happen before endpoint expansion.
- **Both the dashboard and Chrome extension read group/tag config from the same source** (`config/auto_tag_rules.json` served via `GET /config/auto-tags`). Adding a new group is a single JSON edit — no code changes in either UI.
- The Obsidian vault sync should work both as a daemon (`python vault_sync.py --watch`) and as a one-shot triggered by the API (`POST /vault/sync`).
- All new environment variables should be added to `docker/.env.example` with sensible defaults.
- The `recall-artifacts/` directory in the vault must be excluded from ingestion to prevent circular feedback.
- Tests should use mocks for external services — don't require a running stack to pass.
- The Chrome extension stores bridge API URL (default `http://localhost:8090`) and API key in `chrome.storage.local`.
- Gmail extension support is explicitly deferred to `5E.1` after base extension quality is proven.
