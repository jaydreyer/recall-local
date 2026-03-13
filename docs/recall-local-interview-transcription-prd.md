# PRD: Interview Transcription Pipeline for Recall.local

**Author:** Jay (via Claude)
**Date:** March 3, 2026
**Status:** Draft — Ready for Codex
**Priority:** High (interview scheduled for March 4, 2026)

---

## 1. Problem Statement

Jay is actively interviewing for Solutions Engineer roles at AI companies. These interviews contain high-value information — questions asked, answers given, technical discussions, company-specific details, and interpersonal dynamics — that decays rapidly from memory. There is currently no way to capture, transcribe, search, or learn from past interviews within the Recall.local system.

### Why This Matters

- **Post-interview analysis:** Review exact wording of questions and answers to identify areas for improvement.
- **Cross-interview patterns:** Track which topics recur across companies (e.g., "every company asks about RAG evaluation").
- **Searchable history:** Ask Arthur "what technical questions has Anthropic asked me?" and get cited answers.
- **Portfolio demonstration:** A working audio-to-RAG pipeline is itself a compelling demo of Recall.local's capabilities for SE interviews.

---

## 2. Solution Overview

Build an end-to-end pipeline that takes audio recordings of interviews, transcribes them locally using Whisper on the AI lab GPU, optionally performs speaker diarization, enriches the transcript with metadata, and ingests it into Recall.local's existing Qdrant-backed RAG pipeline.

### High-Level Flow

```
Audio File (.m4a/.mp4/.wav/.webm)
    │
    ▼
┌─────────────────────────┐
│  Trigger Layer          │
│  (CLI / file watcher /  │
│   n8n webhook)          │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Transcription          │
│  (faster-whisper,       │
│   large-v3, CUDA)       │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Speaker Diarization    │
│  (pyannote-audio)       │
│  → Merge with segments  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Post-Processing        │
│  (LLM cleanup, metadata │
│   extraction, Markdown  │
│   formatting)           │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Chunking + Embedding   │
│  (existing pipeline,    │
│   nomic-embed-text)     │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐         ┌──────────────────┐
│  Qdrant Upsert          │────────▶│  Obsidian Vault   │
│  (recall_docs collection)│        │  (optional .md    │
└─────────────────────────┘         │   transcript)     │
                                    └──────────────────┘
```

---

## 3. Infrastructure & Environment

### Existing Stack (Do Not Modify)

| Component | Details |
|---|---|
| Server | Ubuntu 24.04, AI home lab |
| GPU | NVIDIA RTX 5060 Ti 16GB |
| Ollama | Running, serves embedding + generation models |
| Qdrant | Running on port 6333, `nomic-embed-text` (768-dim, cosine) |
| n8n | Running on port 5678, handles workflow orchestration |
| Python | Virtual environment at `~/recall-local/.venv` (confirm path) |
| Ingestion | Unified webhook, folder watcher (`data/incoming/` top-level only), Obsidian vault sync |
| LLM Client | Abstraction layer supporting Ollama (primary) and cloud APIs (fallback) |
| Embedding Model | `nomic-embed-text` via Ollama (768 dimensions) |
| Doc IDs | UUID hex; chunk IDs follow pattern `{doc_id}:0000`, `{doc_id}:0001`, etc. |
| Groups | Fixed canonical groups: `job-search`, `learning`, `project`, `reference`, `meeting` (default: `reference`) |

### Codebase Integration Reference

These are confirmed details Codex should use when wiring into the existing codebase. Do not guess at function signatures — reference these files directly.

**Chunking:**
- There is no standalone chunker script. Chunking is implemented inside `ingestion_pipeline.py` (line ~450) via `chunk_text(text, max_tokens, overlap_tokens)`.
- It expects a single extracted plaintext string (`text: str`), then applies token/character windowing logic (lines ~493, ~527).
- For interview transcripts, the transcription pipeline should either: (a) produce a single plaintext string and let the existing `chunk_text()` handle it, or (b) implement custom time-window chunking in `transcript_chunker.py` and pass pre-chunked segments to the ingestion pipeline, bypassing `chunk_text()`. Option (b) is preferred for the richer timestamp metadata, but Codex should inspect the ingestion pipeline to determine how to pass pre-chunked content.

**Ingestion entry points:**
- Upstream ingestion expects an `IngestRequest` with `source_type` + `content` (`ingestion_pipeline.py`, line ~70).
- Supported `source_type` values: `file`, `url`, `gdoc`, `text`, `email` (`ingestion_pipeline.py`, line ~227). A new `interview-transcript` type may need to be added, OR the pipeline can use `source_type="file"` and rely on metadata to distinguish transcripts.
- JSON payload ingestion is handled by `ingest_from_payload.py` (line ~49) with fields: `type`, `content`, optional `group`, `tags`, `metadata`, `replace_existing`, `source_key`. This is likely the cleanest programmatic entry point.

**LLM client:**
- `llm_client.py` is the active abstraction layer.
- `generate()` routes across `ollama | anthropic | openai | gemini` based on `RECALL_LLM_PROVIDER` env var (lines ~27, ~40).
- `embed()` always uses Ollama via `OLLAMA_EMBED_MODEL` regardless of generation provider (line ~71).
- Core pipeline modules import and call this file directly (e.g., `rag_query.py`, `retrieval.py`, `ingestion_pipeline.py`).
- The transcription post-processing step should use `llm_client.generate()` for transcript cleanup and metadata extraction.

**Python environment:**
- Server venv: `<server-repo-root>/.venv`
- Mac workspace: `<repo-root>/.venv` (currently missing — Codex should create it if running locally)

| Package | Purpose | Install |
|---|---|---|
| `faster-whisper` | GPU-accelerated transcription via CTranslate2 | `pip install faster-whisper` |
| `pyannote.audio` | Speaker diarization | `pip install pyannote.audio` |
| `torch` + CUDA | GPU support for pyannote (may already be present) | `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124` |
| `pydub` | Audio format normalization | `pip install pydub` |
| `ffmpeg` | Audio processing backend (system package) | `sudo apt install ffmpeg` (likely already installed) |

### Hugging Face Token

pyannote-audio requires a Hugging Face token with acceptance of the model terms:

1. Create or use existing HF account
2. Accept terms at: `https://huggingface.co/pyannote/speaker-diarization-3.1`
3. Accept terms at: `https://huggingface.co/pyannote/segmentation-3.0`
4. Store token in `.env` as `HF_AUTH_TOKEN=hf_...`

### GPU VRAM Budget

The RTX 5060 Ti 16GB can comfortably run all components. Estimated VRAM usage during transcription:

| Component | VRAM |
|---|---|
| faster-whisper large-v3 | ~5-6 GB |
| pyannote diarization | ~2-3 GB |
| Ollama (if loaded) | ~4-6 GB (model dependent) |
| **Total peak** | **~11-15 GB** |

If VRAM is tight during transcription, the pipeline should unload Ollama models temporarily or run transcription and diarization sequentially rather than in parallel. Include a config flag for this.

---

## 4. Feature Requirements

### 4.1 Transcription Service

**Script:** `scripts/transcribe/transcribe_audio.py`

**Inputs:**
- Audio file path (supports: `.m4a`, `.mp4`, `.wav`, `.webm`, `.mp3`, `.ogg`, `.flac`)
- Optional: `--model` flag (default: `large-v3`, options: `medium`, `small`, `base`)
- Optional: `--language` flag (default: `en`)
- Optional: `--diarize` flag (default: `true`)
- Optional: `--output-format` flag (default: `markdown`, options: `json`, `srt`, `txt`)

**Outputs:**
- Structured transcript with timestamps and speaker labels
- Raw segment data as JSON (always saved alongside formatted output)
- Metadata summary (duration, word count, speaker count, model used, processing time)

**Behavior:**
1. Validate audio file exists and is a supported format
2. Convert to WAV 16kHz mono if needed (via ffmpeg/pydub)
3. Run faster-whisper with `large-v3` model, CUDA device, `float16` compute type
4. Return timestamped segments with text, start time, end time, and confidence

**Example output (pre-diarization):**

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "text": "Thanks for joining us today. Can you tell me a bit about your background?",
      "confidence": 0.94
    },
    {
      "start": 4.5,
      "end": 12.1,
      "text": "Sure, I have about 25 years of experience in technical product management...",
      "confidence": 0.91
    }
  ],
  "metadata": {
    "duration_seconds": 3420,
    "model": "large-v3",
    "language": "en",
    "processing_time_seconds": 142
  }
}
```

### 4.2 Speaker Diarization

**Script:** `scripts/transcribe/diarize.py` (or integrated into `transcribe_audio.py`)

**Behavior:**
1. Run pyannote `speaker-diarization-3.1` pipeline on the audio file
2. Produce speaker segments with start/end times and speaker labels (`SPEAKER_00`, `SPEAKER_01`, etc.)
3. Merge diarization output with Whisper segments by aligning timestamps
4. Where a Whisper segment spans a speaker change, split the segment at the diarization boundary

**Speaker label mapping:**
- Default labels are `SPEAKER_00`, `SPEAKER_01`, etc.
- Accept an optional `--speakers` flag: `--speakers "Jay,Interviewer"` to map labels in order of first appearance
- If not provided, keep generic labels — the post-processing LLM step can attempt to infer names from context

**Conflict resolution:**
- If a Whisper segment overlaps two diarization speakers, assign to the speaker with the majority of the time overlap
- Log conflicts for manual review

### 4.3 Post-Processing (LLM Cleanup)

**Script:** `scripts/transcribe/post_process.py`

**Purpose:** Use a local LLM (via the existing `llm_client.py` abstraction) to clean up and enrich the raw transcript.

**Tasks:**
1. **Punctuation and formatting cleanup** — Fix sentence boundaries, capitalize proper nouns, correct obvious transcription errors
2. **Metadata extraction** — From the transcript content, extract:
   - Company name (if mentioned)
   - Interviewer name(s) (if introduced)
   - Role discussed
   - Key topics covered (as tags)
   - Questions asked by the interviewer (extracted as a list)
3. **Summary generation** — 3-5 sentence summary of the interview
4. **Markdown formatting** — Produce a clean, readable Markdown document with:
   - YAML frontmatter (date, company, role, duration, speakers, tags)
   - Speaker-attributed dialogue
   - Extracted questions section
   - Summary section

**LLM routing:**
- Use Ollama (local) as primary
- Fall back to cloud API if local model fails or produces low-quality output
- The post-processing prompt should be stored in `prompts/transcribe_cleanup.txt` for easy iteration

**Example Markdown output:**

```markdown
---
type: interview-transcript
date: 2026-03-04
company: Anthropic
role: Solutions Engineer
duration: 57:00
speakers:
  - Jay
  - Sarah Chen
tags:
  - anthropic
  - solutions-engineer
  - rag
  - technical-interview
source: audio-transcription
audio_file: 2026-03-04-anthropic-interview.m4a
---

# Interview Transcript: Anthropic — Solutions Engineer

**Date:** March 4, 2026
**Duration:** 57 minutes
**Speakers:** Jay, Sarah Chen

## Summary

Jay interviewed with Sarah Chen for the Solutions Engineer role at Anthropic.
The conversation focused on RAG implementation experience, API governance
background, and a live technical scenario involving retrieval optimization.
Sarah expressed interest in Jay's Recall.local project as a demonstration
of hands-on AI engineering.

## Questions Asked

1. "Can you walk me through a time you helped a customer implement a RAG pipeline?"
2. "How would you approach a situation where retrieval quality is degrading?"
3. "What's your experience with API governance at enterprise scale?"
4. [...]

## Transcript

**Sarah Chen** [00:00:00]
Thanks for joining us today. Can you tell me a bit about your background?

**Jay** [00:00:04]
Sure, I have about 25 years of experience in technical product management,
most recently at Gap Inc. where I managed enterprise AI chatbots and led
API governance initiatives...

[...]
```

### 4.4 Chunking & Ingestion Integration

Interview transcripts must integrate with the existing ingestion pipeline (`ingestion_pipeline.py`), not bypass it. The transcription pipeline produces a Markdown file and metadata, then hands off to the existing pipeline for chunking, embedding, and Qdrant upsert.

#### Integration Approach

The transcription pipeline should call into the existing ingestion pipeline rather than directly writing to Qdrant. This ensures all existing logic — doc_id generation, chunk_id formatting, deduplication, group assignment — is respected.

**Recommended entry point: `ingest_from_payload.py`**
This accepts a JSON payload with fields: `type`, `content`, `group`, `tags`, `metadata`, `replace_existing`, `source_key`. After producing the Markdown transcript, call this with:

```python
payload = {
    "type": "file",  # or add "interview-transcript" as a new source_type
    "content": transcript_markdown_string,
    "group": "job-search",
    "tags": ["interview", company_name, role_name],
    "metadata": {
        "source_type": "interview-transcript",
        "company": company_name,
        "role": role_name,
        "date": interview_date,
        "speakers": speaker_list,
        "duration_seconds": duration,
        "audio_file": original_audio_filename
    },
    "replace_existing": True,
    "source_key": f"audio:{original_audio_filename}"
}
```

If custom time-window chunking is implemented (preferred — see Chunking Strategy below), Codex should inspect `ingestion_pipeline.py` to determine how to inject pre-chunked segments that bypass `chunk_text()` but still flow through embedding and Qdrant upsert. The `IngestRequest` at line ~70 and `chunk_text()` at line ~450 are the key code paths to understand.

**Simpler fallback: Drop into `data/incoming/`**
Save the Markdown transcript as a file at the top level of `data/incoming/` (not in a subdirectory — the one-pass folder ingester is non-recursive) and let the existing ingester pick it up. This loses the custom chunking and rich metadata but works immediately.

#### Chunking Strategy for Transcripts

Interview transcripts benefit from a different chunking approach than general documents. Codex should evaluate whether the existing `chunker.py` handles this well, or whether a custom chunking pass should be applied *before* handing off to the ingestion pipeline.

**Recommended approach: time-window chunks with speaker context**
- Chunk by 3-5 minute windows (configurable via `RECALL_TRANSCRIPT_CHUNK_MINUTES`)
- Each chunk includes: timestamp range, full speaker dialogue within that window, and the previous chunk's last 2-3 exchanges as overlap for context continuity
- Chunk boundaries should prefer natural conversation breaks (speaker turns, topic shifts) when possible
- If custom chunking is used, the pipeline should produce pre-chunked text segments and pass them to the ingestion pipeline in a way that bypasses its default chunking but still uses its embedding and upsert logic

#### Document & Chunk ID Conventions

Follow existing conventions exactly:
- `doc_id`: Generated UUID hex (e.g., `a1b2c3d4e5f6...`)
- `chunk_id`: `{doc_id}:0000`, `{doc_id}:0001`, etc. (zero-padded 4 digits)
- Processed files are renamed to `{doc_id}_{original_filename}` and moved to `data/processed/`

#### Metadata Per Chunk

All chunks from a transcript should carry these metadata fields in the Qdrant payload:

- `source_type`: `"interview-transcript"`
- `group`: `"job-search"`
- `company`: Extracted company name (string)
- `role`: Role discussed (string)
- `date`: Interview date (ISO format string)
- `speakers`: List of speaker names in this chunk
- `timestamp_start`: Start time of chunk in seconds (float)
- `timestamp_end`: End time of chunk in seconds (float)
- `chunk_index`: Sequential position in transcript (int)
- `total_chunks`: Total chunk count for this transcript (int)
- `tags`: List of tags inherited from document-level metadata
- `audio_file`: Original audio filename (for provenance)
- `source_identity`: Absolute path to the audio file
- `source_key`: `audio:<filename>`

#### Deduplication

- `source_identity` uses the absolute resolved path of the original audio file
- Re-processing the same audio file should replace existing chunks (set `replace_existing=true`)
- If the transcript is also saved to the Obsidian vault, the vault sync will create a separate set of chunks with `source_ref: obsidian://career/interview-transcripts/...` — this is acceptable and expected (two ingestion pathways, same content, different source identities)

### 4.5 Trigger Mechanisms

Implement three ways to trigger the transcription pipeline:

#### 4.5.1 CLI (Manual)

```bash
cd ~/recall-local
source .venv/bin/activate

# Basic usage
python scripts/transcribe/transcribe_audio.py /path/to/interview.m4a

# Full options
python scripts/transcribe/transcribe_audio.py \
  /path/to/interview.m4a \
  --speakers "Jay,Sarah Chen" \
  --company "Anthropic" \
  --role "Solutions Engineer" \
  --model large-v3 \
  --diarize \
  --save-to-vault \
  --output-format markdown
```

**Flags:**
- `--speakers`: Comma-separated speaker names in order of first appearance
- `--company`: Pre-tag with company name (skips LLM extraction for this field)
- `--role`: Pre-tag with role title
- `--model`: Whisper model size (default: `large-v3`)
- `--diarize / --no-diarize`: Enable/disable speaker diarization (default: enabled)
- `--save-to-vault`: Also save the Markdown transcript to the Obsidian vault
- `--output-format`: Output format (default: `markdown`)
- `--skip-ingest`: Transcribe only, do not push to Qdrant
- `--skip-postprocess`: Skip LLM cleanup step (output raw transcript)

#### 4.5.2 File Watcher (Drop Directory)

**Watch directory:** `data/incoming/audio/`

> **Important:** The existing one-pass folder ingester (`ingest_incoming_once.py`) scans only top-level files in `data/incoming/` (non-recursive). Audio files placed in `data/incoming/audio/` will NOT be picked up by the existing ingester — this is intentional. The audio watcher is a separate service that monitors this subdirectory and runs the transcription pipeline, which then either calls the ingestion pipeline programmatically or places the resulting Markdown transcript at the top level of `data/incoming/` for the existing ingester to pick up.

**Behavior:**
- Use `watchdog` (already a dependency for vault sync) to monitor the directory
- When an audio file appears, wait 5 seconds for write completion, then trigger the full pipeline
- Use default settings (diarize=true, model=large-v3)
- Metadata is extracted automatically by the LLM post-processing step
- Move processed audio files to `data/processed/audio/` named `{doc_id}_{original_filename}` (matching existing convention)
- On error, move to `data/failed/audio/` with an error log file alongside

**Integration:** Add the audio watcher as a separate `systemd` unit or integrate it into the existing file watcher service if one exists.

#### 4.5.3 n8n Webhook

**Endpoint:** Create a dedicated webhook (separate from the existing unified ingest webhook since audio requires a different processing path):

```
POST /webhook/recall-transcribe
Content-Type: multipart/form-data

Fields:
  - file: <audio file binary>
  - company: "Anthropic" (optional)
  - role: "Solutions Engineer" (optional)
  - speakers: "Jay,Sarah Chen" (optional)
  - save_to_vault: true (optional)
  - group: "job-search" (optional, defaults to "job-search")
```

**n8n Workflow Design:**

```
[Webhook Trigger]
    │
    ▼
[Save file to data/incoming/audio/]
    │
    ▼
[Execute Command: python scripts/transcribe/transcribe_audio.py ...]
    │
    ▼
[Check exit code]
    │
    ├── Success → [Send notification (optional)]
    │
    └── Failure → [Log error, send alert]
```

**Alternative approach:** If the transcription takes too long for a synchronous webhook response (likely for 1+ hour recordings), use an async pattern:

1. Webhook receives file, saves to incoming directory, returns job ID immediately
2. File watcher picks it up and processes
3. Job status is queryable via a separate endpoint: `GET /webhook/recall-transcribe/status/{job_id}`

---

## 5. Obsidian Vault Integration

When `--save-to-vault` is set (or always, if `RECALL_SAVE_TO_VAULT_DEFAULT=true`):

- Save the formatted Markdown transcript to the vault at `career/interview-transcripts/YYYY-MM-DD-{company}-{role}.md`
- The existing vault sync file watcher will detect the new file and ingest it via the Obsidian pathway
- This creates a second set of chunks with `source_ref: obsidian://career/interview-transcripts/...` and `source_key: vault:career/interview-transcripts/...` — this is expected and provides redundant access through both the audio-source and vault-source pathways
- Frontmatter tags should align with the existing vault taxonomy
- The `career/` vault folder should map to the `job-search` group via `auto_tag_rules.json` (vault_folders) — verify this mapping exists, add it if not
- YAML frontmatter in the Markdown file should be compatible with Obsidian's metadata parsing

---

## 6. Configuration

Add a new section to the project's config file (or `.env`):

```env
# Transcription Pipeline
RECALL_WHISPER_MODEL=large-v3
RECALL_WHISPER_DEVICE=cuda
RECALL_WHISPER_COMPUTE_TYPE=float16
RECALL_DIARIZE_DEFAULT=true
RECALL_AUDIO_WATCH_DIR=data/incoming/audio
RECALL_AUDIO_PROCESSED_DIR=data/processed/audio
RECALL_AUDIO_FAILED_DIR=data/failed/audio
RECALL_TRANSCRIPT_VAULT_SUBDIR=career/interview-transcripts
RECALL_SAVE_TO_VAULT_DEFAULT=true
RECALL_TRANSCRIPT_CHUNK_MINUTES=4
RECALL_TRANSCRIPT_CHUNK_OVERLAP_EXCHANGES=3
RECALL_TRANSCRIPT_GROUP=job-search

# Hugging Face (for pyannote)
HF_AUTH_TOKEN=hf_...
```

---

## 7. File Structure

New files to create:

```
recall-local/
├── scripts/
│   └── transcribe/
│       ├── __init__.py
│       ├── transcribe_audio.py     # Main entry point / CLI
│       ├── whisper_service.py      # faster-whisper wrapper
│       ├── diarize.py              # pyannote diarization
│       ├── merge_segments.py       # Merge whisper + diarization output
│       ├── post_process.py         # LLM cleanup + metadata extraction
│       ├── transcript_chunker.py   # Interview-specific chunking logic
│       └── audio_watcher.py        # Watchdog-based file watcher for audio dir
├── prompts/
│   ├── transcribe_cleanup.txt      # LLM prompt for transcript cleanup
│   └── transcribe_metadata.txt     # LLM prompt for metadata extraction
├── data/
│   ├── incoming/
│   │   └── audio/                  # Drop zone for audio files
│   ├── processed/
│   │   └── audio/                  # Successfully processed files
│   └── failed/
│       └── audio/                  # Failed processing with error logs
├── config/
│   └── transcribe_config.json      # Optional: override defaults without env vars
└── tests/
    └── transcribe/
        ├── test_whisper_service.py
        ├── test_diarize.py
        ├── test_merge_segments.py
        ├── test_post_process.py
        └── test_transcript_chunker.py
```

---

## 8. Testing Strategy

### Unit Tests

- `test_whisper_service.py` — Test with a short (~10 second) audio sample. Verify segments returned with timestamps, text, and confidence.
- `test_diarize.py` — Test with a two-speaker audio sample. Verify at least 2 distinct speaker labels returned.
- `test_merge_segments.py` — Test merge logic with synthetic whisper + diarization data. Verify correct speaker assignment and segment splitting at speaker boundaries.
- `test_post_process.py` — Test LLM cleanup with a sample raw transcript. Verify Markdown output structure, frontmatter fields, and extracted questions list.
- `test_transcript_chunker.py` — Test chunking with a sample transcript. Verify chunk size, overlap, and metadata attachment.

### Integration Test

- End-to-end: Drop a known audio file (include a ~60 second two-speaker test recording in `tests/fixtures/`) into the CLI and verify:
  1. Transcript is generated with correct speaker labels
  2. Chunks appear in Qdrant with correct metadata
  3. A RAG query against the transcript returns cited results
  4. If `--save-to-vault`, file appears in the expected vault directory

### Test Audio Fixture

Include or generate a short test audio file. Options:
- Use `edge-tts` or `pyttsx3` to synthesize a two-speaker conversation
- Or record a short test conversation manually
- Save as `tests/fixtures/test_interview_2speaker.wav`

---

## 9. Error Handling

| Scenario | Handling |
|---|---|
| Unsupported audio format | Exit with clear error message listing supported formats |
| Audio file corrupted or unreadable | Log error, move to `failed/` dir with error details |
| CUDA out of memory | Fall back to `float32` compute type or `medium` model. Log warning. |
| Diarization fails | Continue without speaker labels. Log warning. Output transcript with `UNKNOWN` speaker. |
| LLM post-processing fails | Save raw transcript (pre-cleanup) and ingest that. Log warning. |
| Qdrant unavailable | Save transcript to disk, queue for retry. Do not lose work. |
| HF token missing/invalid | Skip diarization with clear error message about token setup |
| File watcher: partial file write | Wait 5 seconds after last file modification before processing |

---

## 10. Performance Expectations

Based on RTX 5060 Ti 16GB with faster-whisper large-v3:

| Recording Length | Expected Transcription Time | Expected Diarization Time | Total Pipeline |
|---|---|---|---|
| 15 minutes | ~30-60 seconds | ~20-40 seconds | ~2-3 minutes |
| 30 minutes | ~1-2 minutes | ~40-80 seconds | ~3-5 minutes |
| 60 minutes | ~2-4 minutes | ~1-2 minutes | ~5-10 minutes |

(Includes post-processing and ingestion. Times are estimates — actual performance depends on audio complexity and model load.)

---

## 11. Future Enhancements (Out of Scope for V1)

These are explicitly **not** part of this build but are noted for future consideration:

- **Real-time transcription** — Live streaming audio to Whisper during a call (requires different architecture)
- **Sentiment analysis** — Track interviewer engagement/tone over time
- **Auto-coaching** — Arthur analyzes transcripts and suggests answer improvements
- **Calendar integration** — Auto-detect upcoming interviews and prompt for recording
- **Multi-language support** — Whisper supports it, but diarization + post-processing would need adaptation
- **Video recording with screen capture** — For technical interviews involving screen shares
- **Transcript comparison** — Diff two interviews to see how answers evolved
- **Dashboard widget** — Interview stats in the Mission Control UI (count, companies, question frequency)

---

## 12. Recording Setup Notes (For Jay, Not for Codex)

For the March 4 interview, before the pipeline is built:

**If the interview is a video call (Zoom/Meet/Teams):**
- **QuickTime Player** → File → New Audio Recording → select your Mac's microphone → hit Record
- This captures both sides of the conversation through your speakers/headphones
- Save as `.m4a` when done

**If you want cleaner audio (optional, more setup):**
- **OBS Studio** (free): Add an Audio Output Capture source (captures system audio) + Audio Input Capture (your mic). Record as `.mkv` or `.mp4`. Extract audio later with: `ffmpeg -i recording.mkv -vn -acodec copy audio.m4a`

**After recording:**
- Transfer the audio file to the server via `scp`, AirDrop → transfer, or directly over Tailscale
- Once the pipeline is built, either drop it in the watch directory or run the CLI command

---

## 13. Acceptance Criteria

The feature is complete when:

- [ ] `faster-whisper` and `pyannote.audio` are installed and functional on the server with CUDA
- [ ] CLI transcription works: `python scripts/transcribe/transcribe_audio.py test.m4a` produces a Markdown transcript with speaker labels and timestamps
- [ ] Diarization correctly identifies 2+ speakers in test audio
- [ ] Post-processing LLM step produces clean Markdown with frontmatter, summary, and extracted questions
- [ ] Chunks are ingested into Qdrant with interview-specific metadata
- [ ] A RAG query like "what questions were asked in my interview?" returns relevant, cited results
- [ ] File watcher triggers pipeline when audio is dropped in the watch directory
- [ ] n8n webhook accepts audio upload and triggers pipeline
- [ ] Transcript is saved to Obsidian vault when configured
- [ ] Error handling works: corrupted audio, missing HF token, CUDA OOM all handled gracefully
- [ ] All unit tests pass
- [ ] Integration test passes end-to-end
