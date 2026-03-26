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
from backend.pipeline.miscue import classify_miscues, tokenize_words
from backend.pipeline.score import compute_scores, estimate_reading_time_seconds
from backend.pipeline.transcribe import TranscriptionError, transcribe_audio
from backend.schemas import AlignedWordRecord, AssessmentResponse, Passage, PassageSummary
from backend.config import get_whisper_model_name


app = FastAPI(
    title="Phil-IRI ASR MVP",
    version="0.1.0",
    description="Phase 3 backend scaffold with ASR, alignment, miscue classification, and scoring.",
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


@app.get("/passages/{passage_id}", response_model=Passage)
async def get_passage(passage_id: str) -> Passage:
    return get_passage_or_404(passage_id)


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
        miscues = []
        reading_time_seconds = None
        total_words = len(tokenize_words(passage.text))
        major_miscue_count = 0
        wpm = None
        word_recognition_pct = None
        reading_level = None

        try:
            await save_upload_file(file, upload_path)
            normalize_media_to_wav(upload_path, normalized_path)
            transcription = transcribe_audio(
                normalized_path,
                model_name=get_whisper_model_name(),
            )
            alignment = force_align_words(normalized_path, transcription)
            miscues = classify_miscues(tokenize_words(passage.text), alignment)
            major_miscue_count = sum(
                1 for miscue in miscues if miscue.counts_as_major_miscue
            )
            reading_time_seconds = estimate_reading_time_seconds(
                [(word.start, word.end) for word in alignment.words]
            )
            if reading_time_seconds is None and transcription is not None:
                reading_time_seconds = estimate_reading_time_seconds(
                    [
                        (segment.get("start"), segment.get("end"))
                        for segment in transcription.segments
                    ]
                )
            wpm, word_recognition_pct, reading_level = compute_scores(
                total_words,
                major_miscue_count,
                reading_time_seconds,
            )
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
        total_words=total_words,
        major_miscue_count=major_miscue_count,
        miscues=miscues,
        wpm=wpm,
        word_recognition_pct=word_recognition_pct,
        reading_level=reading_level,
        reading_time_seconds=reading_time_seconds,
    )
