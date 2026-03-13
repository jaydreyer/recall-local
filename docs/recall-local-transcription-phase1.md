# Phase 1: Core Transcription + Diarization

**Parent PRD:** `recall-local-interview-transcription-prd.md` (read this first for full context)
**Scope:** Install dependencies, build transcription and diarization services, wire up CLI
**Goal:** `python scripts/transcribe/transcribe_audio.py test.m4a` produces a structured transcript with speaker labels and timestamps

---

## Context

This is Phase 1 of a 3-phase feature that adds an interview transcription pipeline to Recall.local. Read the full PRD for the complete picture — Phase 2 adds LLM post-processing and ingestion into Qdrant, Phase 3 adds the file watcher, n8n webhook, and vault integration.

Make architectural decisions in this phase with Phases 2 and 3 in mind. In particular:

- The segment data format you output here will be consumed by Phase 2's post-processor and chunker
- The CLI flags you define here will be extended in Phase 2 (e.g., `--save-to-vault`, `--skip-ingest`)
- The module structure should be clean enough that Phase 3's file watcher can import and call the transcription pipeline as a function, not just as a CLI subprocess

---

## Environment

| Component | Details |
|---|---|
| Server | Ubuntu 24.04, AI home lab |
| GPU | NVIDIA RTX 5060 Ti 16GB |
| Python venv | `<server-repo-root>/.venv` |
| Project root | `<server-repo-root>/` |
| Existing LLM client | `llm_client.py` (not needed this phase, but don't conflict with it) |

---

## Dependencies to Install

Install all of these in the existing venv (`<server-repo-root>/.venv`):

| Package | Purpose | Install |
|---|---|---|
| `faster-whisper` | GPU-accelerated transcription via CTranslate2 | `pip install faster-whisper` |
| `pyannote.audio` | Speaker diarization | `pip install pyannote.audio` |
| `torch` + CUDA | GPU support for pyannote (may already be present — check first) | `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124` |
| `pydub` | Audio format normalization | `pip install pydub` |
| `ffmpeg` | Audio processing backend (system package) | `sudo apt install ffmpeg` (likely already installed — check first) |

### Hugging Face Token

pyannote-audio requires a Hugging Face token with model terms accepted:

1. Token should be in `.env` as `HF_AUTH_TOKEN=hf_...`
2. The user must have accepted terms at:
   - `https://huggingface.co/pyannote/speaker-diarization-3.1`
   - `https://huggingface.co/pyannote/segmentation-3.0`
3. If the token is missing or invalid, diarization should fail gracefully with a clear error message — not crash the whole pipeline

---

## Files to Create

```
recall-local/
├── scripts/
│   └── transcribe/
│       ├── __init__.py
│       ├── transcribe_audio.py     # Main entry point / CLI
│       ├── whisper_service.py      # faster-whisper wrapper
│       ├── diarize.py              # pyannote diarization
│       └── merge_segments.py       # Merge whisper + diarization output
├── data/
│   ├── incoming/
│   │   └── audio/                  # Create this directory (watch target for Phase 3)
│   ├── processed/
│   │   └── audio/                  # Create this directory
│   └── failed/
│       └── audio/                  # Create this directory
└── tests/
    └── transcribe/
        ├── test_whisper_service.py
        ├── test_diarize.py
        ├── test_merge_segments.py
        └── fixtures/
            └── (test audio file — see Testing section)
```

Also create the placeholder directories even though they won't be used until Phase 3. This avoids path errors later.

---

## Implementation Details

### whisper_service.py

A wrapper around faster-whisper that handles model loading and transcription.

**Public interface:**

```python
def transcribe(
    audio_path: str,
    model_size: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    language: str = "en"
) -> TranscriptionResult:
    """
    Transcribe an audio file using faster-whisper.
    
    Returns a TranscriptionResult with:
      - segments: list of dicts with keys: start, end, text, confidence
      - metadata: dict with keys: duration_seconds, model, language, processing_time_seconds
    """
```

**Behavior:**
1. Validate the audio file exists and has a supported extension (`.m4a`, `.mp4`, `.wav`, `.webm`, `.mp3`, `.ogg`, `.flac`)
2. Load the faster-whisper model with specified device and compute type
3. Run transcription
4. Return structured result

**Model caching:** faster-whisper downloads models on first use to `~/.cache/huggingface/`. The model should persist across runs — do not re-download each time.

**VRAM management:** If CUDA OOM occurs, catch the error and retry with `compute_type="float32"` or fall back to `model_size="medium"`. Log a warning when falling back.

### diarize.py

A wrapper around pyannote-audio for speaker diarization.

**Public interface:**

```python
def diarize(
    audio_path: str,
    hf_token: str,
    num_speakers: int | None = None
) -> DiarizationResult:
    """
    Run speaker diarization on an audio file.
    
    Args:
        num_speakers: If known, pass the expected speaker count for better accuracy.
                      For interviews, this is typically 2.
    
    Returns a DiarizationResult with:
      - segments: list of dicts with keys: start, end, speaker (e.g., "SPEAKER_00")
      - num_speakers: int, number of distinct speakers detected
    """
```

**Behavior:**
1. Load pyannote `speaker-diarization-3.1` pipeline with HF token
2. Run diarization (pass `num_speakers` if provided)
3. Return speaker segments

**Error handling:**
- Missing/invalid HF token → raise a specific `DiarizationAuthError` with a message explaining the token setup steps
- CUDA OOM → log warning, return None (caller should proceed without diarization)

### merge_segments.py

Merges Whisper transcription segments with pyannote diarization segments by aligning timestamps.

**Public interface:**

```python
def merge(
    transcription: TranscriptionResult,
    diarization: DiarizationResult | None,
    speaker_names: list[str] | None = None
) -> MergedTranscript:
    """
    Merge transcription segments with diarization speaker labels.
    
    Args:
        speaker_names: Optional list of names to map to speakers in order
                       of first appearance. E.g., ["Jay", "Sarah Chen"]
    
    Returns a MergedTranscript with:
      - segments: list of dicts with keys: start, end, text, speaker, confidence
      - speakers: list of unique speaker names/labels
      - metadata: inherited from transcription, plus speaker_count
    """
```

**Merge logic:**
1. For each Whisper segment, find the diarization segment(s) that overlap in time
2. Assign the speaker label with the majority time overlap
3. If a Whisper segment spans a speaker boundary, split it at the boundary point (proportional text split by word count is acceptable)
4. If `speaker_names` is provided, map `SPEAKER_00` → first name, `SPEAKER_01` → second name, etc.
5. If diarization is None (skipped or failed), assign all segments to `"UNKNOWN"`

**Conflict logging:** When a Whisper segment has ambiguous speaker assignment (e.g., 45%/55% split), log it at DEBUG level for potential manual review.

### transcribe_audio.py (CLI entry point)

The main script that orchestrates the pipeline and provides the CLI interface.

**CLI usage:**

```bash
# Basic usage
python scripts/transcribe/transcribe_audio.py /path/to/interview.m4a

# Full options (Phase 1 flags only)
python scripts/transcribe/transcribe_audio.py \
  /path/to/interview.m4a \
  --speakers "Jay,Sarah Chen" \
  --model large-v3 \
  --language en \
  --diarize \
  --num-speakers 2 \
  --output-dir ./output \
  --output-format json
```

**Phase 1 flags:**

| Flag | Default | Description |
|---|---|---|
| `audio_path` | (required, positional) | Path to audio file |
| `--speakers` | None | Comma-separated speaker names in order of first appearance |
| `--model` | `large-v3` | Whisper model size: `large-v3`, `medium`, `small`, `base` |
| `--language` | `en` | Language code |
| `--diarize / --no-diarize` | `--diarize` | Enable/disable speaker diarization |
| `--num-speakers` | None | Expected number of speakers (helps diarization accuracy) |
| `--output-dir` | `./output` | Where to save output files |
| `--output-format` | `json` | Output format: `json`, `txt`, `srt` |

**Phase 2 will add:** `--company`, `--role`, `--save-to-vault`, `--skip-ingest`, `--skip-postprocess`. Define the argument parser in a way that's easy to extend.

**Behavior:**
1. Parse arguments
2. Load config from environment variables (with CLI flags as overrides)
3. Run `whisper_service.transcribe()`
4. If `--diarize`: run `diarize.diarize()`, then `merge_segments.merge()`
5. Save output to `--output-dir`:
   - Always save raw JSON segments file: `{filename}_segments.json`
   - Save formatted output based on `--output-format`
6. Print summary to stdout: duration, speaker count, segment count, processing time

**The pipeline should also be callable as a Python function** (not just CLI) so Phase 3's file watcher can import it:

```python
def run_transcription_pipeline(
    audio_path: str,
    speakers: list[str] | None = None,
    model: str = "large-v3",
    diarize: bool = True,
    num_speakers: int | None = None,
    output_dir: str = "./output",
    output_format: str = "json"
) -> MergedTranscript:
    """Programmatic entry point for the transcription pipeline."""
```

---

## Output Format

### JSON segments file (`{filename}_segments.json`)

Always saved regardless of `--output-format`. This is the canonical output that Phase 2 will consume.

```json
{
  "segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "text": "Thanks for joining us today. Can you tell me a bit about your background?",
      "speaker": "Sarah Chen",
      "confidence": 0.94
    },
    {
      "start": 4.5,
      "end": 12.1,
      "text": "Sure, I have about 25 years of experience in technical product management...",
      "speaker": "Jay",
      "confidence": 0.91
    }
  ],
  "metadata": {
    "audio_file": "2026-03-04-anthropic-interview.m4a",
    "duration_seconds": 3420,
    "model": "large-v3",
    "language": "en",
    "processing_time_seconds": 142,
    "speakers": ["Sarah Chen", "Jay"],
    "num_speakers": 2,
    "diarization_enabled": true,
    "transcription_timestamp": "2026-03-04T15:30:00Z"
  }
}
```

### Plain text output (`--output-format txt`)

```
[00:00:00] Sarah Chen: Thanks for joining us today. Can you tell me a bit about your background?

[00:00:04] Jay: Sure, I have about 25 years of experience in technical product management...
```

### SRT output (`--output-format srt`)

Standard SRT subtitle format with speaker names prepended to text.

---

## VRAM Budget

| Component | VRAM | Notes |
|---|---|---|
| faster-whisper large-v3 | ~5-6 GB | float16 compute type |
| pyannote diarization | ~2-3 GB | Runs after transcription if sequential |
| **Total peak** | **~8-9 GB** | Well within 16 GB budget |

If Ollama has models loaded, VRAM may be tighter. The pipeline should handle CUDA OOM gracefully (see error handling in each module). Consider adding a `--sequential` flag (default: true) that runs transcription first, frees VRAM, then runs diarization, rather than keeping both models loaded.

---

## Testing

### Test Audio Fixture

Create a synthetic two-speaker test audio file using `edge-tts` or any text-to-speech tool. The fixture should be:
- ~30-60 seconds long
- Two distinct voices (different TTS voices)
- Alternating speakers with clear turns
- Save as `tests/transcribe/fixtures/test_interview_2speaker.wav`

If TTS generation is too complex, create a minimal fixture and document that a real audio file should be substituted for integration testing.

### Unit Tests

**test_whisper_service.py:**
- Test transcription of the fixture file
- Verify output has `segments` list with `start`, `end`, `text`, `confidence` keys
- Verify `metadata` has expected fields
- Test with unsupported file extension → clear error
- Test with nonexistent file → clear error

**test_diarize.py:**
- Test diarization of the fixture file
- Verify at least 2 distinct speaker labels are returned
- Test with missing HF token → `DiarizationAuthError`
- Test with `num_speakers=2` → exactly 2 speakers

**test_merge_segments.py:**
- Test with synthetic data (no audio needed):
  - Create fake Whisper segments and fake diarization segments
  - Verify correct speaker assignment based on time overlap
  - Verify segment splitting at speaker boundaries
  - Test with `speaker_names` mapping
  - Test with `diarization=None` → all segments get `"UNKNOWN"`

### Integration Test

- Run full CLI on the fixture file: `python scripts/transcribe/transcribe_audio.py tests/transcribe/fixtures/test_interview_2speaker.wav --output-dir /tmp/test_output`
- Verify JSON output file exists and is valid
- Verify segments have speaker labels
- Verify metadata is complete

---

## Error Handling Summary

| Scenario | Handling |
|---|---|
| Unsupported audio format | Exit with error listing supported formats |
| Audio file not found | Exit with clear error |
| Audio file corrupted / unreadable | Exit with error (ffmpeg/pydub will raise) |
| CUDA out of memory (Whisper) | Retry with `float32` or fall back to `medium` model. Log warning. |
| CUDA out of memory (pyannote) | Skip diarization, continue without speaker labels. Log warning. |
| HF token missing | Skip diarization with clear message about setup steps |
| HF token invalid / terms not accepted | Skip diarization with clear message |
| No speakers detected by diarization | Assign all to `"SPEAKER_00"`, log warning |

---

## Acceptance Criteria

Phase 1 is complete when:

- [ ] `faster-whisper` and `pyannote.audio` are installed in the venv with CUDA support
- [ ] `python scripts/transcribe/transcribe_audio.py test.m4a` produces a JSON file with timestamped, speaker-labeled segments
- [ ] Diarization correctly identifies 2 speakers in a two-speaker recording
- [ ] `--no-diarize` flag works and produces segments with `"UNKNOWN"` speaker
- [ ] `--speakers "Jay,Interviewer"` correctly maps speaker labels to names
- [ ] CUDA OOM is handled gracefully (fallback, not crash)
- [ ] Missing HF token is handled gracefully (skip diarization, not crash)
- [ ] All unit tests pass
- [ ] Integration test passes
- [ ] `data/incoming/audio/`, `data/processed/audio/`, `data/failed/audio/` directories exist
- [ ] The pipeline is importable as a Python function (`run_transcription_pipeline()`)

---

## What NOT to Build in Phase 1

Explicitly out of scope — these come in Phase 2 and 3:

- LLM post-processing / transcript cleanup
- Markdown formatting with frontmatter
- Qdrant ingestion
- Chunking (time-window or otherwise)
- File watcher service
- n8n webhook
- Obsidian vault integration
- `--company`, `--role`, `--save-to-vault`, `--skip-ingest` flags
