# Phil-IRI ASR MVP

This repository is being built in reviewable phases. Phase 1 establishes the backend scaffold, passage catalog, upload validation, and `ffmpeg`-based media normalization.

## Current Endpoints

- `GET /passages`: returns the available development passages.
- `POST /assess`: accepts `multipart/form-data` with `file` and `passage_id`, validates the upload, normalizes it to 16kHz mono WAV, and returns the stable assessment response shape with placeholder scoring fields.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

## Notes

- `ffmpeg` must be installed and available on `PATH` for `POST /assess` to work.
- Whisper, WhisperX, miscue classification, scoring, and the frontend are scheduled for later phases.
