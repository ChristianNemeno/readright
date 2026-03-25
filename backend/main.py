from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from backend.media import (
    AudioProcessingError,
    normalize_media_to_wav,
    save_upload_file,
    to_http_exception,
    validate_upload_extension,
)
from backend.passages.service import get_passage_or_404, list_passage_summaries
from backend.schemas import AssessmentResponse, PassageSummary


app = FastAPI(
    title="Phil-IRI ASR MVP",
    version="0.1.0",
    description="Phase 1 backend scaffold for upload validation and audio normalization.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/passages", response_model=list[PassageSummary])
async def get_passages() -> list[PassageSummary]:
    return list_passage_summaries()


@app.post("/assess", response_model=AssessmentResponse)
async def assess_recording(
    file: UploadFile = File(...),
    passage_id: str = Form(...),
) -> AssessmentResponse:
    passage = get_passage_or_404(passage_id)

    try:
        file_extension = validate_upload_extension(file.filename)
    except AudioProcessingError as error:
        raise to_http_exception(error) from error

    with TemporaryDirectory(prefix="philiri-assess-") as temp_dir:
        temp_path = Path(temp_dir)
        upload_path = temp_path / f"upload{file_extension}"
        normalized_path = temp_path / "normalized.wav"

        try:
            await save_upload_file(file, upload_path)
            normalize_media_to_wav(upload_path, normalized_path)
        except AudioProcessingError as error:
            raise to_http_exception(error) from error
        except HTTPException:
            raise
        except Exception as error:  # pragma: no cover - defensive API boundary
            raise HTTPException(status_code=500, detail="Unexpected assessment pipeline error.") from error

    return AssessmentResponse(
        passage_id=passage.id,
        transcript="",
        total_words=passage.word_count,
        major_miscue_count=0,
        miscues=[],
        wpm=None,
        word_recognition_pct=None,
        reading_level=None,
        reading_time_seconds=None,
    )
