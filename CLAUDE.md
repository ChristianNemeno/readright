# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReadRight is a Phil-IRI (Philippine Informal Reading Inventory) ASR MVP. It records or accepts student audio, transcribes it with Whisper, aligns it with WhisperX, classifies miscues, and computes word recognition scores. No database, no auth — single-purpose assessment tool.

## Running the App

### Docker (recommended — runs everything together)

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`

Whisper models are downloaded on first run and cached in a Docker volume (`model_cache`), so initial startup is slow. Subsequent starts are fast.

To set a custom backend URL (e.g. for a remote VM):
```bash
API_URL=http://<host-ip>:8000 docker compose up --build
```

---

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

ffmpeg must be installed and on PATH. On Windows, `backend/media.py` also tries a hardcoded fallback path — update it to match your local ffmpeg installation if needed.

---

## Architecture

### Pipeline (`backend/pipeline/`)

The assessment pipeline runs sequentially inside `POST /assess`:

1. **`media.py`** — validates extension, saves upload to temp file, calls ffmpeg to normalize to 16 kHz mono WAV.
2. **`pipeline/transcribe.py`** — loads Whisper (LRU-cached, max 2 models) and returns word-level timestamps.
3. **`pipeline/align.py`** — runs WhisperX forced alignment (LRU-cached, max 4 models); falls back to Whisper timestamps on failure.
4. **`pipeline/miscue.py`** — Needleman-Wunsch sequence alignment maps spoken words to passage words, then classifies each pair (correct, mispronunciation, substitution, dialectal_variation, omission, refusal, insertion, repetition). Phonetic similarity uses Levenshtein + Metaphone via `jellyfish`.
5. **`pipeline/score.py`** — computes WPM, Word Recognition %, and Phil-IRI reading level (Independent ≥97%, Instructional 91–96%, Frustration <91%).

### Configuration (`backend/config.py`)

Runtime behaviour is controlled via environment variables (all prefixed `PHILIRI_`):
- `PHILIRI_WHISPER_MODEL` — model size (default: `base`)
- `PHILIRI_DEVICE` — `cpu` or `cuda` (default: `cpu`)
- `PHILIRI_MODEL_CACHE_DIR` — optional cache directory for downloaded models
- `PHILIRI_WHISPER_LANGUAGE` — optional language code
- `PHILIRI_ALIGN_MODEL` — optional WhisperX alignment model override
- `PHILIRI_LOCAL_MODELS_ONLY` — set to `1` to disable network model downloads
- `PHILIRI_CORS_ORIGINS` — comma-separated list of extra CORS origins beyond the localhost defaults

Allowed upload extensions: `.m4a`, `.mov`, `.mp3`, `.mp4`, `.ogg`, `.wav`, `.webm`

### Passages (`backend/passages/`)

Passages are stored in `passages/passages.json`. Each entry must have a `word_count` that exactly matches the token count produced by `WORD_RE = r"\b[\w']+\b"`. `service.py` validates this at startup and raises `PassageDataError` on mismatch.

### API (`backend/main.py`)

- `GET /passages` → list of `PassageSummary`, sorted by grade_level, language, title
- `GET /passages/{passage_id}` → full `Passage`, 404 if not found
- `POST /assess` → multipart form (`file` + `passage_id`) → `AssessmentResponse`

CORS is enabled for `localhost:3000`, `localhost:5173`, and their `127.0.0.1` equivalents. Additional origins can be added via `PHILIRI_CORS_ORIGINS`.

### Schemas (`backend/schemas.py`)

Key response types:
- **AssessmentResponse**: `passage_id`, `transcript`, `alignment_source` (`"whisper"` | `"whisperx"`), `aligned_words`, `wpm`, `word_recognition_pct`, `reading_level`, `reading_time_seconds`, `miscues`, `total_words`, `major_miscue_count`
- **MiscueRecord**: `target`, `spoken`, `type`, `start`, `end`, `counts_as_major_miscue`

Major miscue types (affect word recognition score): mispronunciation, substitution, omission, insertion, refusal.

### Frontend (`frontend/src/`)

Single-page React app (Vite, React 18) with three screens managed by a `screen` state variable in `App.jsx`:
- `SelectScreen` — passage grid cards
- `ReadScreen` — passage text, mic recording button, file upload, submit
- `ResultScreen` — WPM, word recognition %, reading level, miscue word chips, confetti on Independent level

Uses `MediaRecorder` for in-browser recording with MIME type detection for cross-browser compatibility. Backend URL comes from `VITE_API_BASE_URL` env var (falls back to `http://127.0.0.1:8000`).

### Validation workflow

Fill in `validation/teacher_scores.csv` (see `validation/README.md`) → run `validate_teacher_scores.py` → review `validation/results/`. The thesis success criterion is `within_5pct_word_recognition` (AI vs teacher word recognition within 5 percentage points).
