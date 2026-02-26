# Recall.local — Phase 5 Punch List (Post-Audit)

**For:** Codex implementation
**From:** Architecture review of Phase 5 audit (Claude Opus, 2026-02-26)
**Priority:** Complete before demo day. Estimated 3-4 hours total.

---

## Context

Phase 5 audit came back at 88% complete. The core architecture is solid — auto-tag config flow works end-to-end, FastAPI migration is clean, tests are substantive, Chrome extension exceeded scope. What remains is a short punch list of gaps and polish items.

---

## Task 1: File Upload Endpoint + Drag-Drop UI (CRITICAL — ~2-3 hours)

The Ingest tab is missing file drag-drop, and the backend multipart upload endpoint doesn't exist. This is the biggest functional gap.

### Backend: `POST /v1/ingestions/files`

Follow existing API design standards (plural resource nouns, `/v1/` prefix).

```python
@app.post("/v1/ingestions/files")
async def ingest_file(
    file: UploadFile,
    group: str = Form("reference"),
    tags: str = Form(""),  # comma-separated
    save_to_vault: bool = Form(False),
):
    """Accept multipart file upload, save to data/incoming/, trigger ingestion pipeline."""
    # 1. Validate file extension (.pdf, .docx, .txt, .md, .html, .eml)
    # 2. Save to data/incoming/ with original filename (handle collisions)
    # 3. Parse tags from comma-separated string
    # 4. Call ingestion pipeline with group, tags, and save_to_vault flag
    # 5. Return { "status": "accepted", "filename": ..., "group": ..., "tags": [...] }
```

Requirements:
- Auth enforced (same `_enforce_api_key_if_configured()` pattern as all other endpoints)
- Rate limited
- Max file size: 50MB (configurable via `RECALL_MAX_UPLOAD_MB` env var, default 50)
- Return 415 for unsupported file types
- Return 413 for oversized files

### Frontend: Drag-Drop Zone on Ingest Tab

Add a drop zone to the Ingest tab between the URL paste box and Quick Actions. Behavior:

- Visual: dashed border container, "Drop PDF, DOCX, Markdown, or email files here — or click to browse"
- Drag over: border changes to amber, background lightens
- On drop: extract files, for each file call `POST /v1/ingestions/files` as multipart/form-data
- Include the currently selected group and tags from the group selector / tag picker
- Show upload progress per file (or at minimum a spinner → success/error state)
- Also trigger on click (opens native file picker)
- Accept: `.pdf, .docx, .txt, .md, .html, .eml`

The scaffold reference (`docs/scaffolds/recall-dashboard.jsx`, Ingest tab) has the drop zone UI pattern.

---

## Task 2: CI Pytest Step (CRITICAL — ~15 minutes)

30 tests exist but CI doesn't run them. Add a pytest step to `.github/workflows/quality_checks.yml`:

```yaml
- name: Run tests
  run: |
    pip install -r requirements.txt --break-system-packages
    pip install pytest --break-system-packages
    pytest tests/ -v --tb=short
```

This should run after the existing syntax checks. If any test dependencies are missing from `requirements.txt`, add them.

---

## Task 3: "Save to Vault" Checkbox in Chrome Extension (~30 minutes)

The extension popup currently has an "Include highlighted text" checkbox. Add a second checkbox: **"Save to vault"** that maps to `save_to_vault: true` in the ingest payload.

In `popup.html`, add below the existing checkbox:
```html
<label>
  <input type="checkbox" id="saveToVault">
  Save to vault
</label>
```

In `popup.js` / `shared.js`, include `save_to_vault` in the payload sent to the bridge:
```javascript
const payload = {
    url: tab.url,
    title: tab.title,
    group: selectedGroup,
    tags: selectedTags,
    save_to_vault: document.getElementById('saveToVault').checked,
    // ... existing fields
};
```

This ties the Chrome extension into the Obsidian integration story — capture from browser, optionally save as a vault note.

---

## Task 4: Docker Compose Consolidation (MEDIUM — ~2-3 hours)

Current `docker-compose.yml` only defines `recall-ui` and `mkdocs`. Replace with a full-stack compose file. The goal is: `docker-compose up` brings up everything from scratch.

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant-storage:/qdrant/storage"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: ["ollama-models:/root/.ollama"]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
    restart: unless-stopped

  n8n:
    image: n8nio/n8n:latest
    ports: ["5678:5678"]
    volumes: ["./n8n:/home/node/.n8n"]
    environment:
      - N8N_SECURE_COOKIE=false
    restart: unless-stopped

  recall-bridge:
    build:
      context: .
      dockerfile: docker/bridge/Dockerfile
    ports: ["8090:8090"]
    volumes:
      - ./data:/app/data
      - ./scripts:/app/scripts
      - ./prompts:/app/prompts
      - ./config:/app/config
    env_file: ./docker/.env
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8090/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  recall-ui:
    build:
      context: ./ui/dashboard
      dockerfile: Dockerfile
    ports: ["8170:8170"]
    depends_on: [recall-bridge]
    restart: unless-stopped

  mkdocs:
    build:
      context: .
      dockerfile: docker/mkdocs/Dockerfile
    ports: ["8100:8100"]
    volumes: ["./docs:/docs"]
    restart: unless-stopped

volumes:
  qdrant-storage:
  ollama-models:
```

Key requirements:
- Health checks on Qdrant and recall-bridge
- `depends_on` with `condition: service_healthy` so bridge waits for Qdrant
- GPU reservation for Ollama
- `restart: unless-stopped` on all services
- Named volumes for persistent data (Qdrant storage, Ollama models)
- Keep the existing "Approach B" file as `docker-compose.lite.yml` for users who already have services running

---

## Task 5: Font Swap (LOW — ~5 minutes)

In `ui/dashboard/src/App.css` and `ui/dashboard/src/index.css`, replace Space Mono references with IBM Plex Mono:

```css
/* Replace */
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&display=swap');
font-family: 'Space Mono', monospace;

/* With */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
font-family: 'IBM Plex Mono', monospace;
```

---

## Task 6: Verify No Broken References to Old Aliases (LOW — ~15 minutes)

Phase 5F removed legacy route aliases (e.g., `/config/auto-tags`). Grep the codebase for any remaining references to old paths:

```bash
grep -r "/config/auto-tags" --include="*.json" --include="*.js" --include="*.py" --include="*.yml" .
grep -r "/ingest/" --include="*.json" --include="*.js" --include="*.py" --include="*.yml" .
```

If n8n workflow JSONs, bookmarklets, or iOS Shortcut payloads reference old paths, update them to canonical `/v1/` routes.

---

## Implementation Order

| # | Task | Est. | Priority |
|---|------|------|----------|
| 1 | `POST /v1/ingestions/files` endpoint | 1 hour | CRITICAL |
| 2 | Drag-drop zone on Ingest tab | 1-2 hours | CRITICAL |
| 3 | CI pytest step | 15 min | CRITICAL |
| 4 | "Save to vault" checkbox in extension | 30 min | HIGH |
| 5 | Docker Compose full-stack | 2-3 hours | MEDIUM |
| 6 | Font swap | 5 min | LOW |
| 7 | Verify old alias references | 15 min | LOW |

**Total: ~5-7 hours**

---

## Notes for Codex

- The new file upload endpoint is `POST /v1/ingestions/files` — plural resource nouns per project API standards. Not `/ingest/file`.
- The drag-drop zone should reuse the same group selector and tag picker already on the Ingest tab. When a user selects a group and tags, then drops a file, those selections should carry through to the upload payload.
- For Docker Compose, preserve the existing lite file as `docker-compose.lite.yml` with a comment explaining it's for users with pre-existing services. The new full-stack file becomes the default `docker-compose.yml`.
- The 30 existing tests should all pass in CI without modification. If any fail due to missing dependencies, fix the dependency, not the test.
- After completing all tasks, run the full eval suite to confirm no regressions in RAG quality.
