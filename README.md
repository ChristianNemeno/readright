# Phil-IRI ASR MVP

This repository now covers the MVP build in `plan.md`: backend assessment pipeline, frontend assessment UI, and the validation tooling needed for the Week 4 benchmark.

## Current Endpoints

- `GET /passages`: returns the available development passages.
- `POST /assess`: accepts `multipart/form-data` with `file` and `passage_id`, validates the upload, normalizes it to 16kHz mono WAV, runs Whisper transcription, attempts WhisperX alignment, aligns the spoken words to the passage text, classifies miscues, and computes Phil-IRI word-recognition scoring fields.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

```powershell
cd frontend
npm install
npm run dev
```

## Test

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Validation Workflow

Inspect one recording from the command line:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_recording.py recordings\student.wav grade4_english_A_pretest
```

Run the Week 4 teacher-vs-AI benchmark:

```powershell
.\.venv\Scripts\python.exe scripts\validate_teacher_scores.py `
  --teacher-csv validation\teacher_scores.csv `
  --inputs-dir recordings `
  --output-csv validation\results\benchmark_report.csv
```

The benchmark template and instructions are in [validation/README.md](C:\Nemeno\3rd year\2nd sem\readright\validation\README.md).

## Notes

- `ffmpeg` must be installed and available on `PATH` for `POST /assess` and the validation scripts to work.
- Whisper model downloads and WhisperX alignment-model downloads must be available locally or via network access on first run.
- Passage loading now validates that `word_count` matches the passage text so scoring inputs stay consistent.
- The current reading level reflects Word Recognition Level only. Comprehension is still out of scope for this MVP.
- The frontend reads `VITE_API_BASE_URL` and defaults to `http://127.0.0.1:8000`. See [frontend/.env.example](C:\Nemeno\3rd year\2nd sem\readright\frontend\.env.example).
