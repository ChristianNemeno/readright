from functools import lru_cache
from pathlib import Path

import whisperx

from backend.config import get_align_model_name, get_model_cache_dir, get_runtime_device, use_local_models_only
from backend.pipeline.types import AlignmentResult, TranscriptionResult, WordSegment


def _fallback_alignment(
    transcription: TranscriptionResult,
    *,
    reason: str,
) -> AlignmentResult:
    return AlignmentResult(
        words=list(transcription.words),
        source="whisper",
        metadata={
            **transcription.metadata,
            "alignment_reason": reason,
            "alignment_source": "whisper",
        },
    )


@lru_cache(maxsize=4)
def _load_align_model(
    language_code: str,
    device: str,
    model_name: str | None,
    model_dir: str | None,
    model_cache_only: bool,
):
    return whisperx.load_align_model(
        language_code=language_code,
        device=device,
        model_name=model_name,
        model_dir=model_dir,
        model_cache_only=model_cache_only,
    )


def force_align_words(
    wav_path: Path,
    transcription: TranscriptionResult,
    device: str | None = None,
    model_name: str | None = None,
    model_dir: str | None = None,
    model_cache_only: bool | None = None,
) -> AlignmentResult:
    if not transcription.segments:
        return AlignmentResult(
            words=[],
            source="whisper",
            metadata={
                **transcription.metadata,
                "alignment_reason": "No transcription segments available.",
                "alignment_source": "whisper",
            },
        )

    resolved_device = device or get_runtime_device()
    resolved_model_name = model_name or get_align_model_name()
    resolved_model_dir = model_dir or get_model_cache_dir()
    resolved_model_cache_only = (
        use_local_models_only() if model_cache_only is None else model_cache_only
    )
    language_code = (transcription.metadata.get("language") or "en").strip().lower()

    try:
        align_model, align_metadata = _load_align_model(
            language_code,
            resolved_device,
            resolved_model_name,
            resolved_model_dir,
            resolved_model_cache_only,
        )
        aligned = whisperx.align(
            transcription.segments,
            align_model,
            align_metadata,
            str(wav_path),
            resolved_device,
            return_char_alignments=False,
        )
        aligned_words = [
            WordSegment(
                word=(word.get("word") or "").strip(),
                start=word.get("start"),
                end=word.get("end"),
            )
            for word in aligned.get("word_segments", [])
            if (word.get("word") or "").strip()
        ]
        if not aligned_words:
            return _fallback_alignment(
                transcription,
                reason="WhisperX returned no word_segments; falling back to Whisper timestamps.",
            )

        return AlignmentResult(
            words=aligned_words,
            source="whisperx",
            metadata={
                **transcription.metadata,
                "alignment_source": "whisperx",
                "alignment_language": language_code,
                "alignment_model_name": resolved_model_name,
            },
        )
    except Exception as error:
        return _fallback_alignment(
            transcription,
            reason=f"WhisperX alignment failed: {error}",
        )
