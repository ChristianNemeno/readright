from functools import lru_cache
from pathlib import Path

import whisper
from whisper import Whisper

from backend.config import get_model_cache_dir, get_runtime_device, get_whisper_language
from backend.pipeline.types import TranscriptionResult, WordSegment


class TranscriptionError(RuntimeError):
    """Raised when Whisper transcription cannot complete."""


def _normalize_word(text: str | None) -> str:
    return (text or "").strip()


@lru_cache(maxsize=2)
def _load_model(model_name: str, device: str, download_root: str | None) -> Whisper:
    return whisper.load_model(
        model_name,
        device=device,
        download_root=download_root,
    )


def transcribe_audio(
    wav_path: Path,
    model_name: str = "base",
    device: str | None = None,
    language: str | None = None,
    download_root: str | None = None,
) -> TranscriptionResult:
    resolved_device = device or get_runtime_device()
    resolved_language = language or get_whisper_language()
    resolved_download_root = download_root or get_model_cache_dir()

    try:
        model = _load_model(model_name, resolved_device, resolved_download_root)
        result = model.transcribe(
            str(wav_path),
            language=resolved_language,
            verbose=False,
            condition_on_previous_text=False,
            word_timestamps=True,
            fp16=resolved_device.startswith("cuda"),
        )
    except Exception as error:
        raise TranscriptionError(
            "Whisper transcription failed. Ensure the selected model is available and the runtime can load it."
        ) from error

    segments = list(result.get("segments", []))
    words = []
    for segment in segments:
        for word in segment.get("words", []):
            normalized_word = _normalize_word(word.get("word"))
            if not normalized_word:
                continue
            words.append(
                WordSegment(
                    word=normalized_word,
                    start=word.get("start"),
                    end=word.get("end"),
                )
            )

    return TranscriptionResult(
        transcript=(result.get("text") or "").strip(),
        segments=segments,
        words=words,
        metadata={
            "device": resolved_device,
            "language": result.get("language") or resolved_language,
            "model_name": model_name,
            "source": "whisper",
        },
    )
