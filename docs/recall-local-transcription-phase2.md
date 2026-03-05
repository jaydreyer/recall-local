# Phase 2: LLM Post-Processing + Ingestion

**Parent PRD:** `recall-local-interview-transcription-prd.md` (read this first for full context)
**Depends on:** Phase 1 complete and passing all acceptance criteria
**Scope:** LLM transcript cleanup, metadata extraction, interview-specific chunking, Qdrant ingestion via existing pipeline
**Goal:** CLI produces a clean Markdown transcript, chunks appear in Qdrant with correct metadata, RAG queries return cited results from interview content

---

## Context

Phase 1 built the core transcription and diarization pipeline. It produces a `_segments.json` file with timestamped, speaker-labeled segments. Phase 2 takes that output and:

1. Cleans it up using a local LLM (via `llm_client.py`)
2. Extracts structured metadata (company, role, questions asked, summary)
3. Formats it as a Markdown document with YAML frontmatter
4. Chunks it using an interview-aware time-window strategy
5. Ingests chunks into Qdrant via the existing `ingest_from_payload.py` entry point

Phase 3 (next) adds the file watcher, n8n webhook, and Obsidian vault integration.

---

## Codebase Integration Points

Read these files before writing any code:

| File | Why |
|---|---|
| `llm_client.py` | LLM abstraction. Use `generate()` for cleanup/extraction. Routes via `RECALL_LLM_PROVIDER` env var. |
| `ingest_from_payload.py` (~line 49) | Recommended ingestion entry point. Accepts JSON with `type`, `content`, `group`, `tags`, `metadata`, `replace_existing`, `source_key`. |
| `ingestion_pipeline.py` (~line 70) | `IngestRequest` definition. Supported source types: `file`, `url`, `gdoc`, `text`, `email`. |
| `ingestion_pipeline.py` (~line 450) | `chunk_text(text, max_tokens, overlap_tokens)` — existing chunking logic. Understand this to decide whether to use it or bypass it for custom time-window chunking. |
| `ingestion_pipeline.py` (~line 579) | Chunk ID generation: `{doc_id}:0000`, `{doc_id}:0001`, etc. |
| `ingestion_pipeline.py` (~line 740, ~756) | Processed file naming: `{doc_id}_{original_filename}`, moved to `data/processed/`. |
| `config/auto_tag_rules.json` | Vault folder → group mappings. May need to verify `career/` maps to `job-search`. |

---

## Files to Create

```
recall-local/
├── scripts/
│   └── transcribe/
│       ├── post_process.py         # LLM cleanup + metadata extraction
│       └── transcript_chunker.py   # Interview-specific chunking logic
├── prompts/
│   ├── transcribe_cleanup.txt      # LLM prompt for transcript cleanup
│   └── transcribe_metadata.txt     # LLM prompt for metadata extraction
└── tests/
    └── transcribe/
        ├── test_post_process.py
        └── test_transcript_chunker.py
```

### Files to Modify

- `scripts/transcribe/transcribe_audio.py` — Add Phase 2 CLI flags and wire in post-processing + ingestion steps

---

## Implementation Details

### post_process.py

Uses `llm_client.generate()` to clean up and enrich the raw transcript.

**Public interface:**

```python
def post_process_transcript(
    merged_transcript: MergedTranscript,  # From Phase 1's merge_segments
    company: str | None = None,           # Pre-supplied metadata (skips extraction)
    role: str | None = None,
    interview_date: str | None = None
) -> ProcessedTranscript:
    """
    Clean up transcript and extract metadata using local LLM.
    
    Returns a ProcessedTranscript with:
      - markdown: str (formatted Markdown with YAML frontmatter)
      - metadata: dict (company, role, date, speakers, tags, summary, questions_asked)
      - clean_segments: list of cleaned/corrected segments
    """
```

**Two-pass LLM approach:**

**Pass 1: Transcript cleanup** (prompt: `prompts/transcribe_cleanup.txt`)
- Input: Raw segments as speaker-attributed text
- Tasks: Fix punctuation, sentence boundaries, capitalize proper nouns, correct obvious transcription errors (e.g., "anthropic" → "Anthropic"), remove filler words/false starts if excessive
- Output: Cleaned segment text
- Keep this prompt focused — don't ask for metadata extraction in the same pass

**Pass 2: Metadata extraction** (prompt: `prompts/transcribe_metadata.txt`)
- Input: Cleaned transcript text
- Tasks: Extract company name, interviewer name(s), role discussed, key topics as tags, questions asked by the interviewer, 3-5 sentence summary
- Output: Structured JSON
- If `company` or `role` were passed as CLI args, include them in the prompt as confirmed facts (don't re-extract)

**LLM routing:**
- Call `llm_client.generate()` which routes based on `RECALL_LLM_PROVIDER`
- If LLM call fails or returns unparseable output, fall back gracefully:
  - Cleanup pass fails → use raw segments (uncleaned)
  - Metadata pass fails → use whatever was supplied via CLI args, leave the rest as `null`
  - Never crash because the LLM had a bad day

**Prompt files:**
- Store in `prompts/transcribe_cleanup.txt` and `prompts/transcribe_metadata.txt`
- Prompts should instruct the model to return structured output (JSON for metadata, cleaned text for cleanup)
- Include examples in the prompts for reliability

### Markdown Formatting

After both LLM passes, format the final Markdown document:

```markdown
---
type: interview-transcript
date: 2026-03-04
company: Anthropic
role: Solutions Engineer
duration: "57:00"
speakers:
  - Jay
  - Sarah Chen
tags:
  - interview
  - anthropic
  - solutions-engineer
source_type: interview-transcript
audio_file: 2026-03-04-anthropic-interview.m4a
---

# Interview Transcript: Anthropic — Solutions Engineer

**Date:** March 4, 2026
**Duration:** 57 minutes
**Speakers:** Jay, Sarah Chen

## Summary

[3-5 sentence summary from LLM extraction]

## Questions Asked

1. [Question extracted by LLM]
2. [Question extracted by LLM]
3. [...]

## Transcript

**Sarah Chen** [00:00:00]
Thanks for joining us today. Can you tell me a bit about your background?

**Jay** [00:00:04]
Sure, I have about 25 years of experience in technical product management...

[...]
```

### transcript_chunker.py

Interview-specific chunking that produces time-window chunks with speaker context.

**Public interface:**

```python
def chunk_transcript(
    processed: ProcessedTranscript,
    chunk_minutes: int = 4,
    overlap_exchanges: int = 3
) -> list[TranscriptChunk]:
    """
    Chunk a processed transcript into time-window segments.
    
    Args:
        chunk_minutes: Target chunk size in minutes
        overlap_exchanges: Number of speaker exchanges from previous chunk
                          to include as context overlap
    
    Returns list of TranscriptChunk, each with:
      - text: str (chunk content including speaker labels and timestamps)
      - metadata: dict (all per-chunk metadata for Qdrant payload)
    """
```

**Chunking logic:**
1. Walk through cleaned segments sequentially
2. Accumulate segments into a chunk until the time window (`chunk_minutes`) is reached
3. Prefer to break at speaker turn boundaries rather than mid-utterance
4. Each chunk includes the last `overlap_exchanges` speaker turns from the previous chunk as context prefix (clearly marked, e.g., `[context from previous segment]`)
5. Each chunk is a self-contained readable text block with speaker names and timestamps

**Per-chunk metadata:**

```python
{
    "source_type": "interview-transcript",
    "group": "job-search",
    "company": "Anthropic",           # From document-level metadata
    "role": "Solutions Engineer",     # From document-level metadata
    "date": "2026-03-04",            # ISO format
    "speakers": ["Jay", "Sarah Chen"],# Speakers present in THIS chunk
    "timestamp_start": 0.0,          # Start time in seconds
    "timestamp_end": 240.0,          # End time in seconds
    "chunk_index": 0,                # Sequential position
    "total_chunks": 15,              # Total for this transcript
    "tags": ["interview", "anthropic", "solutions-engineer"],
    "audio_file": "2026-03-04-anthropic-interview.m4a",
    "source_key": "audio:2026-03-04-anthropic-interview.m4a"
}
```

### Ingestion Integration

After chunking, ingest into Qdrant via the existing pipeline.

**Recommended approach: Call `ingest_from_payload.py`**

For each chunk, construct a payload:

```python
payload = {
    "type": "text",              # Use "text" source type — content is already extracted text
    "content": chunk.text,
    "group": "job-search",
    "tags": chunk.metadata["tags"],
    "metadata": chunk.metadata,  # All the per-chunk metadata above
    "replace_existing": True,
    "source_key": chunk.metadata["source_key"]
}
```

**Important considerations:**
- Inspect `ingest_from_payload.py` to understand the exact function signature and how to call it programmatically (not just via HTTP)
- If ingesting chunk-by-chunk produces separate `doc_id`s per chunk (likely, since each payload is a separate ingest call), consider whether the full transcript should be ingested as a single document that gets chunked by the pipeline. Evaluate the tradeoff:
  - **One ingest call with full transcript text** → uses existing `chunk_text()`, simpler, but loses time-window chunking and per-chunk timestamp metadata
  - **Multiple ingest calls, one per chunk** → preserves rich metadata per chunk, but each chunk gets its own `doc_id` rather than sharing one with sequential `chunk_id`s
  - **Best option if feasible:** Find a way to pass pre-chunked segments into the ingestion pipeline so they share a single `doc_id` with sequential `chunk_id`s. Inspect `ingestion_pipeline.py` to see if this is supported.
- Use `source_key: "audio:{filename}"` for deduplication — re-processing the same audio should replace existing chunks
- Set `replace_existing: True`

### CLI Extensions

Add these flags to `transcribe_audio.py`:

| Flag | Default | Description |
|---|---|---|
| `--company` | None | Pre-tag with company name (skips LLM extraction for this field) |
| `--role` | None | Pre-tag with role title |
| `--skip-ingest` | False | Transcribe and post-process only, do not push to Qdrant |
| `--skip-postprocess` | False | Skip LLM cleanup (output raw transcript, still ingest if not skipped) |
| `--output-format` | `markdown` | Change default from `json` to `markdown` (JSON segments file is still always saved) |

The full CLI now looks like:

```bash
python scripts/transcribe/transcribe_audio.py \
  /path/to/interview.m4a \
  --speakers "Jay,Sarah Chen" \
  --company "Anthropic" \
  --role "Solutions Engineer" \
  --model large-v3 \
  --diarize \
  --num-speakers 2 \
  --output-format markdown \
  --skip-ingest  # optional: just produce the transcript without ingesting
```

**Updated pipeline flow in `transcribe_audio.py`:**

```
1. Parse args
2. Transcribe (Phase 1: whisper_service)
3. Diarize + merge (Phase 1: diarize + merge_segments)
4. Save raw segments JSON (Phase 1)
5. [NEW] Post-process with LLM (post_process.py) — skip if --skip-postprocess
6. [NEW] Save Markdown transcript to output dir
7. [NEW] Chunk transcript (transcript_chunker.py) — skip if --skip-ingest
8. [NEW] Ingest chunks into Qdrant (via ingest_from_payload) — skip if --skip-ingest
9. Print summary
```

---

## Configuration

Add to `.env`:

```env
# Phase 2 additions
RECALL_TRANSCRIPT_CHUNK_MINUTES=4
RECALL_TRANSCRIPT_CHUNK_OVERLAP_EXCHANGES=3
RECALL_TRANSCRIPT_GROUP=job-search
```

These should be read by `transcript_chunker.py` with the CLI/function args as overrides.

---

## Testing

### test_post_process.py

- Test with a sample `MergedTranscript` (synthetic data, no audio needed)
- Verify Markdown output has correct YAML frontmatter structure
- Verify metadata extraction returns expected fields
- Test with `company` and `role` pre-supplied → verify they appear in output and aren't re-extracted
- Test LLM failure gracefully → raw segments used, no crash
- Mock `llm_client.generate()` for unit tests to avoid actual LLM calls

### test_transcript_chunker.py

- Test with a synthetic `ProcessedTranscript` containing ~20 minutes of segments
- Verify chunks are roughly `chunk_minutes` in size
- Verify overlap: each chunk (except first) starts with context from previous chunk
- Verify per-chunk metadata has all required fields
- Verify `chunk_index` is sequential and `total_chunks` is correct
- Test edge case: transcript shorter than one chunk → single chunk returned

### Integration Test

- Run full CLI on a real or fixture audio file with `--company "TestCo" --role "Test Role"`
- Verify Markdown transcript file is produced with correct frontmatter
- Verify chunks appear in Qdrant (query the collection for `source_key: "audio:{filename}"`)
- Run a RAG query like "what was discussed in the TestCo interview?" and verify relevant results return

---

## Error Handling

| Scenario | Handling |
|---|---|
| LLM cleanup call fails | Log warning, use raw (uncleaned) segments. Continue pipeline. |
| LLM metadata extraction fails | Log warning, use CLI-supplied metadata where available, `null` for rest. Continue. |
| LLM returns unparseable JSON | Log warning with the raw response, fall back to defaults. |
| Qdrant unavailable | Save Markdown transcript to disk (don't lose the work). Log error with instructions to retry. |
| Ingestion pipeline error | Log the error, save transcript. Suggest manual ingest via `data/incoming/`. |
| Transcript too long for LLM context | Split into sections, process each separately, merge results. |

---

## Acceptance Criteria

Phase 2 is complete when:

- [ ] `python scripts/transcribe/transcribe_audio.py test.m4a --company "TestCo" --role "SE"` produces a clean Markdown transcript with YAML frontmatter, summary, and extracted questions
- [ ] LLM post-processing uses `llm_client.generate()` correctly
- [ ] Transcript chunks appear in Qdrant with interview-specific metadata (company, role, date, speakers, timestamps)
- [ ] A RAG query like "what questions were asked?" returns relevant cited results from the transcript
- [ ] `--skip-ingest` produces transcript without touching Qdrant
- [ ] `--skip-postprocess` ingests raw transcript without LLM cleanup
- [ ] LLM failure is handled gracefully (pipeline continues with raw data)
- [ ] Qdrant unavailability is handled gracefully (transcript saved to disk)
- [ ] Prompt files exist at `prompts/transcribe_cleanup.txt` and `prompts/transcribe_metadata.txt`
- [ ] All unit tests pass (with mocked LLM calls)
- [ ] Integration test passes end-to-end

---

## What NOT to Build in Phase 2

Explicitly out of scope — these come in Phase 3:

- File watcher service for `data/incoming/audio/`
- n8n webhook endpoint
- Obsidian vault integration (`--save-to-vault` flag)
- Async job queue / status endpoint
- Audio file management (move to processed/failed directories — that's Phase 3's watcher responsibility)
