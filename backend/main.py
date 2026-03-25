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
from backend.pipeline.align import force_align_words
from backend.pipeline.transcribe import TranscriptionError, transcribe_audio
from backend.schemas import AlignedWordRecord, AssessmentResponse, PassageSummary
from backend.config import get_whisper_model_name


app = FastAPI(
    title="Phil-IRI ASR MVP",
    version="0.1.0",
    description="Phase 2 backend scaffold with Whisper transcription and WhisperX alignment.",
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
        transcription = None
        alignment = None

        try:
            await save_upload_file(file, upload_path)
            normalize_media_to_wav(upload_path, normalized_path)
            transcription = transcribe_audio(
                normalized_path,
                model_name=get_whisper_model_name(),
            )
            alignment = force_align_words(normalized_path, transcription)
        except AudioProcessingError as error:
            raise to_http_exception(error) from error
        except TranscriptionError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except HTTPException:
            raise
        except Exception as error:  # pragma: no cover - defensive API boundary
            raise HTTPException(status_code=500, detail="Unexpected assessment pipeline error.") from error

    return AssessmentResponse(
        passage_id=passage.id,
        transcript=transcription.transcript if transcription else "",
        alignment_source=alignment.source if alignment else None,
        aligned_words=[
            AlignedWordRecord(word=word.word, start=word.start, end=word.end)
            for word in (alignment.words if alignment else [])
        ],
        total_words=passage.word_count,
        major_miscue_count=0,
        miscues=[],
        wpm=None,
        word_recognition_pct=None,
        reading_level=None,
        reading_time_seconds=None,
    )
