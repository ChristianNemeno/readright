# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReadRight is a Phil-IRI (Philippine Informal Reading Inventory) ASR MVP. It records or accepts student audio, transcribes it with Whisper, aligns it with WhisperX, classifies miscues, and computes word recognition scores. No database, no auth — single-purpose assessment tool.

## Development Commands

### Backend

```bash
# Activate virtualenv (bash)
source .venv/Scripts/activate

# Run the API server
uvicorn backend.main:app --reload

# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_miscue.py

# Run a single test
python -m pytest tests/test_miscue.py::MiscueTests::test_classify_miscues_detects_mispronunciation

# Assess a single recording (without the server)
python scripts/inspect_recording.py <recording_path> <passage_id> [--model base] [--device cpu]

# Batch validate against teacher scores
python scripts/validate_teacher_scores.py --teacher-csv validation/teacher_scores.csv --output-csv validation/results/report.csv --inputs-dir <dir>
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # Dev server on port 5173
npm run build    # Production build to dist/
```

Copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_BASE_URL` if the backend is not on `http://127.0.0.1:8000`.

### External dependency

ffmpeg must be installed and on PATH (or the hardcoded fallback path in `backend/media.py` must be updated to match your local ffmpeg installation).

## Architecture

### Pipeline (`backend/pipeline/`)

The assessment pipeline runs sequentially inside `POST /assess`:

1. **`media.py`** — validates extension, saves upload to temp file, calls ffmpeg to normalize to 16 kHz mono WAV.
2. **`pipeline/transcribe.py`** — loads Whisper (LRU-cached, max 2 models) and returns word-level timestamps.
3. **`pipeline/align.py`** — runs WhisperX forced alignment (LRU-cached, max 4 models); falls back to Whisper timestamps on failure.
4. **`pipeline/miscue.py`** — Needleman-Wunsch sequence alignment maps spoken words to passage words, then classifies each pair (correct, mispronunciation, substitution, dialectal_variation, omission, refusal, insertion, repetition). Phonetic similarity uses Levenshtein + Metaphone via `jellyfish`.
5. **`pipeline/score.py`** — computes WPM, Word Recognition %, and Phil-IRI reading level (Independent ≥97%, Instructional 91–96%, Frustration <91%).

### Configuration (`backend/config.py`)

Runtime behaviour is controlled via environment variables:
- `WHISPER_MODEL` — model size (default: `base`)
- `RUNTIME_DEVICE` — `cpu` or `cuda` (default: `cpu`)
- `MODEL_CACHE_DIR` — optional cache directory for downloaded models
- `WHISPER_LANGUAGE` — optional language code
- `ALIGN_MODEL_NAME` — optional WhisperX alignment model override
- `LOCAL_MODELS_ONLY` — set to `1` to disable network model downloads

### Passages (`backend/passages/`)

Passages are stored in `passages/passages.json`. Each entry must have a `word_count` that exactly matches the token count produced by `WORD_RE = r"\b[\w']+\b"`. `service.py` validates this at startup and raises `PassageDataError` on mismatch.

### API (`backend/main.py`)

- `GET /passages` → list of `PassageSummary`
- `GET /passages/{passage_id}` → full `Passage`
- `POST /assess` → multipart form (`audio_file` + `passage_id`) → `AssessmentResponse`

CORS is enabled for `localhost:3000`, `localhost:5173`, and their `127.0.0.1` equivalents.

### Frontend (`frontend/src/`)

Single-page React app (Vite) with three screens managed by a `screen` state variable in `App.jsx`:
- `SelectScreen` — passage grid
- `ReadScreen` — recording/upload + passage text
- `ResultScreen` — scores, miscue word chips, confetti for Independent level

Uses `MediaRecorder` for in-browser recording with MIME type detection for cross-browser compatibility.

### Validation workflow

`validation/teacher_scores.template.csv` → fill with real data → run `validate_teacher_scores.py` → review `validation/results/`. The thesis success criterion is `within_5pct_word_recognition` (AI vs teacher word recognition within 5 percentage points).
