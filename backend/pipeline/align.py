from pathlib import Path

from backend.pipeline.types import AlignmentResult, TranscriptionResult


def force_align_words(wav_path: Path, transcription: TranscriptionResult) -> AlignmentResult:
    raise NotImplementedError(
        "WhisperX forced alignment is scheduled for Phase 2. "
        f"Attempted to align '{wav_path.name}' with {len(transcription.segments)} segments."
    )
