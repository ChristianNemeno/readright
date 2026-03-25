# Phil-IRI ASR MVP

This repository is being built in reviewable phases. Phase 2 adds Whisper transcription and WhisperX-based word alignment on top of the Phase 1 backend scaffold.

## Current Endpoints

- `GET /passages`: returns the available development passages.
- `POST /assess`: accepts `multipart/form-data` with `file` and `passage_id`, validates the upload, normalizes it to 16kHz mono WAV, runs Whisper transcription, attempts WhisperX alignment, and returns transcript plus aligned words. Miscues and scoring fields remain placeholders until the next phase.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

## Notes

- `ffmpeg` must be installed and available on `PATH` for `POST /assess` to work.
- Whisper model downloads and WhisperX alignment-model downloads must be available locally or via network access on first run.
- Miscue classification, scoring, and the frontend are scheduled for later phases.
