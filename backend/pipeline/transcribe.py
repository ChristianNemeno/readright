from pathlib import Path

from backend.pipeline.types import TranscriptionResult


def transcribe_audio(wav_path: Path, model_name: str = "base") -> TranscriptionResult:
    raise NotImplementedError(
        "Whisper transcription is scheduled for Phase 2. "
        f"Requested model '{model_name}' for '{wav_path.name}'."
    )
