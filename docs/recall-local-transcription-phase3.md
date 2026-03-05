# Phase 3: Automation Layer — File Watcher, n8n Webhook, Vault Integration

**Parent PRD:** `recall-local-interview-transcription-prd.md` (read this first for full context)
**Depends on:** Phase 1 and Phase 2 complete and passing all acceptance criteria
**Scope:** File watcher for audio drop directory, n8n webhook endpoint, Obsidian vault integration, audio file lifecycle management
**Goal:** Drop an audio file in a directory (or POST to a webhook) and the full pipeline runs automatically — transcription, diarization, LLM cleanup, Qdrant ingestion, and Obsidian vault save — with no manual intervention

---

## Context

Phases 1 and 2 built a working CLI pipeline: audio in → speaker-labeled transcript → LLM cleanup → Qdrant ingestion. Phase 3 wraps this in automation so the pipeline can be triggered without running a CLI command.

Three trigger mechanisms:
1. **File watcher** — drop an audio file in a directory, pipeline runs automatically
2. **n8n webhook** — POST audio to a webhook endpoint, pipeline runs (enables mobile/remote triggers)
3. **Obsidian vault integration** — save transcript as a vault note alongside ingestion

Plus: audio file lifecycle management (move to processed/failed after completion).

---

## Codebase Integration Points

| File | Why |
|---|---|
| `scripts/transcribe/transcribe_audio.py` | The `run_transcription_pipeline()` function from Phase 1 — the watcher and webhook call this directly |
| `scripts/transcribe/post_process.py` | Phase 2's post-processing — called as part of the full pipeline |
| `vault_sync.py` (~line 107, ~125) | Existing vault sync. Uses `source_ref: obsidian://<relative_path>` and `source_key: vault:<relative_path>`. Understand how it works so the transcript save doesn't conflict. |
| `config/auto_tag_rules.json` | Vault folder → group mappings. Verify or add `career/interview-transcripts` → `job-search`. |
| `ingest_incoming_once.py` (~line 26-32) | One-pass folder ingester. Scans only top-level files in `data/incoming/` (non-recursive). Audio files in `data/incoming/audio/` are intentionally NOT picked up by this. |

---

## Files to Create

```
recall-local/
├── scripts/
│   └── transcribe/
│       └── audio_watcher.py        # Watchdog-based file watcher for audio directory
├── n8n/
│   └── workflows/
│       └── transcribe-webhook.json # Exportable n8n workflow definition (if feasible)
└── tests/
    └── transcribe/
        ├── test_audio_watcher.py
        └── test_vault_integration.py
```

### Files to Modify

- `scripts/transcribe/transcribe_audio.py` — Add `--save-to-vault` flag, vault save logic
- `config/auto_tag_rules.json` — Add vault folder mapping if missing

---

## Implementation Details

### audio_watcher.py — File Watcher Service

Monitors `data/incoming/audio/` for new audio files and triggers the full pipeline.

**Public interface:**

```python
def start_watcher(
    watch_dir: str = None,       # Default from RECALL_AUDIO_WATCH_DIR env
    processed_dir: str = None,   # Default from RECALL_AUDIO_PROCESSED_DIR env
    failed_dir: str = None,      # Default from RECALL_AUDIO_FAILED_DIR env
    poll_interval: int = 5       # Seconds between checks
):
    """Start watching for audio files. Blocks until interrupted."""
```

**Behavior:**

1. Use `watchdog` library (already a project dependency for vault sync) to monitor the watch directory
2. On file creation event for supported audio extensions (`.m4a`, `.mp4`, `.wav`, `.webm`, `.mp3`, `.ogg`, `.flac`):
   a. Wait 5 seconds after last modification (handles slow file copies/transfers)
   b. Verify file is complete (file size stable for 5 seconds)
   c. Log: "Processing audio file: {filename}"
   d. Call `run_transcription_pipeline()` with default settings:
      - `diarize=True`
      - `model="large-v3"` (or from env config)
      - `output_dir=data/processed/audio/`
      - `save_to_vault=True` (if `RECALL_SAVE_TO_VAULT_DEFAULT=true`)
      - No `--company`, `--role`, `--speakers` — metadata extraction relies entirely on the LLM post-processing step
   e. On success:
      - Move audio file to `data/processed/audio/{doc_id}_{original_filename}` (matching project convention)
      - Log: "Successfully processed: {filename} → {doc_id}"
   f. On failure:
      - Move audio file to `data/failed/audio/{original_filename}`
      - Write error log file: `data/failed/audio/{original_filename}.error.log` with traceback and timestamp
      - Log: "Failed to process: {filename} — see error log"

3. Ignore:
   - Temporary files (`.tmp`, `.part`, `.crdownload`, `._*`, `.DS_Store`)
   - Files already being processed (maintain an in-memory set of active files)
   - Subdirectories (non-recursive)

**Running as a service:**

Provide a systemd unit file template:

```ini
# /etc/systemd/system/recall-audio-watcher.service
[Unit]
Description=Recall.local Audio File Watcher
After=network.target docker.service

[Service]
Type=simple
User=jaydreyer
WorkingDirectory=/home/jaydreyer/recall-local
ExecStart=/home/jaydreyer/recall-local/.venv/bin/python scripts/transcribe/audio_watcher.py
Restart=on-failure
RestartSec=10
Environment=PATH=/home/jaydreyer/recall-local/.venv/bin:/usr/local/bin:/usr/bin

[Install]
WantedBy=multi-user.target
```

Also support running directly for testing: `python scripts/transcribe/audio_watcher.py`

### n8n Webhook

Create an n8n workflow that accepts audio file uploads and triggers the pipeline.

**Webhook endpoint:** `POST http://192.168.68.93:5678/webhook/recall-transcribe`

**n8n workflow nodes:**

```
[Webhook Trigger (POST, multipart/form-data)]
    │
    ▼
[Write Binary File to data/incoming/audio/]
    │
    ▼
[Execute Command: python scripts/transcribe/transcribe_audio.py <filepath> 
    --company "${{ $json.company }}" 
    --role "${{ $json.role }}" 
    --speakers "${{ $json.speakers }}"
    --save-to-vault]
    │
    ▼
[IF: exit code == 0]
    │
    ├── Success → [Respond: { "status": "ok", "message": "Transcription complete" }]
    │
    └── Failure → [Respond: { "status": "error", "message": stderr }]
```

**Webhook accepts:**

```
POST /webhook/recall-transcribe
Content-Type: multipart/form-data

Fields:
  - file: <audio binary> (required)
  - company: string (optional)
  - role: string (optional)  
  - speakers: string, comma-separated (optional)
  - group: string (optional, default: "job-search")
  - save_to_vault: boolean (optional, default: true)
```

**Async consideration:**
For recordings longer than ~15 minutes, the webhook may time out before transcription completes. Two approaches:

**Option A (simpler, recommended for V1):** The webhook just saves the file to `data/incoming/audio/` and immediately returns `{ "status": "queued", "filename": "..." }`. The file watcher picks it up and processes it. This is fire-and-forget — no status tracking.

**Option B (future):** Return a `job_id` immediately, process in background, expose a status endpoint. Out of scope for V1 but note the architecture should support it.

**Go with Option A.** The webhook becomes a thin file-drop mechanism, and the watcher does the actual work. This also means the webhook can include metadata by writing a sidecar JSON file:

```
data/incoming/audio/interview.m4a
data/incoming/audio/interview.m4a.meta.json  ← {"company": "Anthropic", "role": "SE", "speakers": "Jay,Sarah"}
```

The watcher should check for a `.meta.json` sidecar when processing an audio file and pass those values to the pipeline.

### Obsidian Vault Integration

Add `--save-to-vault` flag to the CLI and integrate with the existing vault structure.

**Behavior when `--save-to-vault` is active:**

1. After producing the Markdown transcript (Phase 2 output), save a copy to the Obsidian vault
2. Target path: `{RECALL_VAULT_PATH}/career/interview-transcripts/YYYY-MM-DD-{company}-{role}.md`
   - Sanitize company and role for filesystem safety (lowercase, replace spaces with hyphens, strip special chars)
   - Handle filename collisions with `-1`, `-2` suffix (matching existing convention)
3. The existing vault sync file watcher (`vault_sync.py`) will detect the new file and ingest it via the Obsidian pathway
4. This creates a second set of chunks in Qdrant with:
   - `source_ref: obsidian://career/interview-transcripts/2026-03-04-anthropic-solutions-engineer.md`
   - `source_key: vault:career/interview-transcripts/2026-03-04-anthropic-solutions-engineer.md`
5. This dual-ingestion (audio pipeline + vault sync) is intentional and acceptable — they have different `source_key` values and serve different access patterns

**Vault folder → group mapping:**

Check `config/auto_tag_rules.json` for a `vault_folders` mapping. Ensure `career/interview-transcripts` (or `career/`) maps to the `job-search` group. If the mapping doesn't exist, add it.

**Frontmatter compatibility:**

The YAML frontmatter in the Markdown file must be compatible with both:
- Obsidian's metadata/properties parsing
- The vault sync ingestion pipeline's frontmatter extraction

Use standard YAML types (strings, lists, dates). Avoid complex nested objects in frontmatter.

### CLI Flag Addition

Add to `transcribe_audio.py`:

| Flag | Default | Description |
|---|---|---|
| `--save-to-vault / --no-save-to-vault` | From `RECALL_SAVE_TO_VAULT_DEFAULT` env (default: `true`) | Save Markdown transcript to Obsidian vault |

---

## Configuration

Add/verify in `.env`:

```env
# Phase 3 additions
RECALL_VAULT_PATH=/path/to/obsidian-vault    # Should already exist from vault_sync
RECALL_SAVE_TO_VAULT_DEFAULT=true
RECALL_AUDIO_WATCHER_POLL_INTERVAL=5
RECALL_AUDIO_WATCHER_SETTLE_TIME=5           # Seconds to wait for file write completion
```

---

## Metadata Sidecar Format

When the n8n webhook (or any external tool) drops an audio file into the watch directory, it can include a `.meta.json` sidecar with pre-supplied metadata:

```json
{
  "company": "Anthropic",
  "role": "Solutions Engineer", 
  "speakers": ["Jay", "Sarah Chen"],
  "date": "2026-03-04",
  "group": "job-search",
  "tags": ["technical-interview", "second-round"],
  "save_to_vault": true
}
```

**File naming:** The sidecar must be named `{audio_filename}.meta.json` (e.g., `interview.m4a.meta.json`).

The audio watcher should:
1. Check for a sidecar when processing each audio file
2. Parse it and pass values as arguments to `run_transcription_pipeline()`
3. Delete the sidecar after successful processing (or move alongside the audio file to processed/failed)

If no sidecar exists, the pipeline runs with defaults and relies on LLM metadata extraction.

---

## Testing

### test_audio_watcher.py

- Test file detection: create a file in the watch dir → verify the handler is triggered
- Test settle time: create a file, modify it within 5 seconds → verify processing waits
- Test ignored files: create `.tmp`, `.DS_Store` → verify they're ignored
- Test sidecar loading: create `test.wav` + `test.wav.meta.json` → verify metadata is passed to pipeline
- Test error handling: trigger with an invalid audio file → verify it moves to failed dir with error log
- Mock `run_transcription_pipeline()` for unit tests — don't actually run transcription

### test_vault_integration.py

- Test Markdown file is written to correct vault path
- Test filename sanitization (special chars, spaces, long names)
- Test filename collision handling
- Test frontmatter is valid YAML parseable by standard libraries
- Test with `--no-save-to-vault` → no file written

### Integration Test

Full end-to-end:
1. Start the audio watcher
2. Drop a test audio file (with sidecar) into `data/incoming/audio/`
3. Wait for processing to complete
4. Verify:
   - Audio file moved to `data/processed/audio/`
   - Markdown transcript exists in output dir
   - Chunks exist in Qdrant with correct metadata
   - Transcript file exists in Obsidian vault (if save_to_vault=true)
   - RAG query returns results from the transcript
5. Drop an invalid file → verify it moves to `data/failed/audio/` with error log

---

## Error Handling

| Scenario | Handling |
|---|---|
| File watcher crashes | systemd restarts it (RestartSec=10). In-progress file will be retried on next startup. |
| Partial file copy (interrupted transfer) | Settle time check catches this. If file size changes within 5 seconds, wait longer. |
| Sidecar JSON is malformed | Log warning, ignore sidecar, proceed with defaults |
| Vault path doesn't exist | Log error, skip vault save, continue with Qdrant ingestion |
| Vault sync picks up file before audio pipeline finishes writing | File watcher should write to a temp path and atomically rename to final path |
| n8n webhook receives non-audio file | Validate file extension before saving. Return 400 error. |
| Duplicate audio file dropped | `replace_existing=True` on ingestion handles this — new chunks replace old ones |

---

## Acceptance Criteria

Phase 3 is complete when:

- [ ] File watcher detects new audio files in `data/incoming/audio/` and triggers full pipeline
- [ ] Watcher handles settle time correctly (waits for file write completion)
- [ ] Processed audio files move to `data/processed/audio/{doc_id}_{filename}`
- [ ] Failed audio files move to `data/failed/audio/` with `.error.log`
- [ ] Sidecar `.meta.json` files are parsed and metadata is passed to pipeline
- [ ] n8n webhook accepts audio uploads and drops files into the watch directory
- [ ] `--save-to-vault` saves Markdown transcript to Obsidian vault at correct path
- [ ] Vault folder → group mapping is correct in `auto_tag_rules.json`
- [ ] Vault frontmatter is valid YAML and compatible with Obsidian
- [ ] Systemd unit file template is provided and documented
- [ ] Temp files, `.DS_Store`, etc. are ignored by the watcher
- [ ] All unit tests pass
- [ ] Integration test passes end-to-end (drop file → Qdrant + vault)

---

## Full Pipeline Summary (All Phases Combined)

After all three phases, the complete flow is:

```
[Audio file arrives via:]
  ├── CLI command (manual)
  ├── File drop in data/incoming/audio/ (watcher)
  ├── n8n webhook POST (remote/mobile)
  └── (optional .meta.json sidecar for pre-supplied metadata)
         │
         ▼
[Phase 1: Transcription]
  faster-whisper (large-v3, CUDA) → timestamped segments
  pyannote (speaker-diarization-3.1) → speaker labels
  Merge → speaker-attributed segments JSON
         │
         ▼
[Phase 2: Post-Processing + Ingestion]
  LLM cleanup (llm_client.generate) → clean segments
  LLM metadata extraction → company, role, questions, summary, tags
  Markdown formatting → frontmatter + transcript document
  Time-window chunking → interview-aware chunks with per-chunk metadata
  Qdrant ingestion (via ingest_from_payload.py) → searchable via RAG
         │
         ▼
[Phase 3: Automation + Storage]
  Audio file → data/processed/audio/ (or data/failed/audio/)
  Markdown transcript → Obsidian vault (career/interview-transcripts/)
  Vault sync picks up → second ingestion pathway into Qdrant
         │
         ▼
[Arthur can now answer:]
  "What technical questions has Anthropic asked me?"
  "How did I describe my RAG experience in the Cohere interview?"
  "What topics come up most across all my interviews?"
```
