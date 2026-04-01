import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

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
from backend.schemas import AlignedWordRecord, AssessmentResponse, MiscueRecord, Passage, PassageSummary
from backend.config import get_cors_origins, get_whisper_model_name


app = FastAPI(
    title="Phil-IRI ASR MVP",
    version="0.1.0",
    description="Phase 3 backend scaffold with ASR, alignment, miscue classification, and scoring.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
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


def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/assess-stream")
async def assess_recording_stream(
    file: UploadFile = File(...),
    passage_id: str = Form(...),
) -> StreamingResponse:
    """
    SSE streaming endpoint for assessment with real-time progress.
    
    Emits progress events as each pipeline stage completes:
    - upload_received (5%)
    - media_normalized (15%)
    - transcription_complete (65%)
    - alignment_complete (85%)
    - miscue_complete (95%)
    - complete (100%) with full result
    """
    passage = get_passage_or_404(passage_id)

    try:
        file_extension = validate_upload_extension(file.filename)
    except AudioProcessingError as error:
        raise to_http_exception(error) from error

    # Read file content upfront since we can't await inside the generator
    file_content = await file.read()

    async def generate_events() -> AsyncGenerator[str, None]:
        with TemporaryDirectory(prefix="philiri-assess-stream-") as temp_dir:
            temp_path = Path(temp_dir)
            upload_path = temp_path / f"upload{file_extension}"
            normalized_path = temp_path / "normalized.wav"
            
            try:
                # Stage 1: Save upload (5%)
                upload_path.write_bytes(file_content)
                yield _sse_event("progress", {
                    "stage": "upload_received",
                    "percent": 5,
                    "message": "Upload received"
                })

                # Stage 2: Normalize media (15%)
                normalize_media_to_wav(upload_path, normalized_path)
                yield _sse_event("progress", {
                    "stage": "media_normalized",
                    "percent": 15,
                    "message": "Audio normalized"
                })

                # Stage 3: Transcription (65%)
                transcription = transcribe_audio(
                    normalized_path,
                    model_name=get_whisper_model_name(),
                )
                yield _sse_event("progress", {
                    "stage": "transcription_complete",
                    "percent": 65,
                    "message": "Transcription complete"
                })

                # Stage 4: Alignment (85%)
                alignment = force_align_words(normalized_path, transcription)
                yield _sse_event("progress", {
                    "stage": "alignment_complete",
                    "percent": 85,
                    "message": "Alignment complete"
                })

                # Stage 5: Miscue classification (95%)
                passage_words = tokenize_words(passage.text)
                total_words = len(passage_words)
                miscues = classify_miscues(passage_words, alignment)
                major_miscue_count = sum(1 for m in miscues if m.counts_as_major_miscue)
                yield _sse_event("progress", {
                    "stage": "miscue_complete",
                    "percent": 95,
                    "message": "Miscue analysis complete"
                })

                # Stage 6: Scoring & complete (100%)
                reading_time_seconds = estimate_reading_time_seconds(
                    [(word.start, word.end) for word in alignment.words]
                )
                if reading_time_seconds is None and transcription is not None:
                    reading_time_seconds = estimate_reading_time_seconds(
                        [(seg.get("start"), seg.get("end")) for seg in transcription.segments]
                    )
                
                wpm, word_recognition_pct, reading_level = compute_scores(
                    total_words, major_miscue_count, reading_time_seconds
                )

                result = AssessmentResponse(
                    passage_id=passage.id,
                    transcript=transcription.transcript if transcription else "",
                    alignment_source=alignment.source if alignment else None,
                    aligned_words=[
                        AlignedWordRecord(word=w.word, start=w.start, end=w.end)
                        for w in (alignment.words if alignment else [])
                    ],
                    total_words=total_words,
                    major_miscue_count=major_miscue_count,
                    miscues=[MiscueRecord(
                        target=m.target,
                        spoken=m.spoken,
                        type=m.type,
                        start=m.start,
                        end=m.end,
                        counts_as_major_miscue=m.counts_as_major_miscue,
                    ) for m in miscues],
                    wpm=wpm,
                    word_recognition_pct=word_recognition_pct,
                    reading_level=reading_level,
                    reading_time_seconds=reading_time_seconds,
                )

                yield _sse_event("complete", {
                    "percent": 100,
                    "message": "Assessment complete",
                    "result": result.model_dump()
                })

            except AudioProcessingError as error:
                yield _sse_event("error", {
                    "message": str(error),
                    "code": error.code if hasattr(error, 'code') else "audio_error"
                })
            except TranscriptionError as error:
                yield _sse_event("error", {
                    "message": str(error),
                    "code": "transcription_error"
                })
            except Exception as error:
                yield _sse_event("error", {
                    "message": "Unexpected assessment pipeline error.",
                    "code": "internal_error"
                })

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
