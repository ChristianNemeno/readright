from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.config import (
    get_model_cache_dir,
    get_runtime_device,
    get_whisper_language,
    get_whisper_model_name,
)
from backend.media import normalize_media_to_wav
from backend.passages.service import get_passage_or_404
from backend.pipeline.align import force_align_words
from backend.pipeline.miscue import classify_miscues, tokenize_words
from backend.pipeline.score import compute_scores, estimate_reading_time_seconds
from backend.pipeline.transcribe import transcribe_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one Phil-IRI assessment from the command line and print the aligned output."
    )
    parser.add_argument("recording", type=Path, help="Path to the audio or video recording.")
    parser.add_argument("passage_id", help="Passage id from backend/passages/passages.json.")
    parser.add_argument("--model", default=None, help="Override the Whisper model name.")
    parser.add_argument("--device", default=None, help="Override the runtime device.")
    parser.add_argument("--language", default=None, help="Override the Whisper language code.")
    parser.add_argument("--align-model", default=None, help="Override the WhisperX alignment model.")
    parser.add_argument(
        "--model-cache-dir",
        default=None,
        help="Optional directory for cached Whisper and WhisperX models.",
    )
    parser.add_argument(
        "--local-models-only",
        action="store_true",
        help="Require models to be present locally instead of downloading them.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    recording_path = args.recording.expanduser().resolve()
    if not recording_path.exists():
        raise SystemExit(f"Recording not found: {recording_path}")

    passage = get_passage_or_404(args.passage_id)
    resolved_device = args.device or get_runtime_device()
    resolved_language = args.language or get_whisper_language()
    resolved_cache_dir = args.model_cache_dir or get_model_cache_dir()

    with TemporaryDirectory(prefix="philiri-inspect-") as temp_dir:
        normalized_path = Path(temp_dir) / "normalized.wav"
        normalize_media_to_wav(recording_path, normalized_path)

        transcription = transcribe_audio(
            normalized_path,
            model_name=args.model or get_whisper_model_name(),
            device=resolved_device,
            language=resolved_language,
            download_root=resolved_cache_dir,
        )
        alignment = force_align_words(
            normalized_path,
            transcription,
            device=resolved_device,
            model_name=args.align_model,
            model_dir=resolved_cache_dir,
            model_cache_only=args.local_models_only,
        )
        miscues = classify_miscues(tokenize_words(passage.text), alignment)
        major_miscues = sum(1 for miscue in miscues if miscue.counts_as_major_miscue)
        reading_time_seconds = estimate_reading_time_seconds(
            [(word.start, word.end) for word in alignment.words]
        )
        if reading_time_seconds is None:
            reading_time_seconds = estimate_reading_time_seconds(
                [(segment.get("start"), segment.get("end")) for segment in transcription.segments]
            )
        wpm, word_recognition_pct, reading_level = compute_scores(
            passage.word_count,
            major_miscues,
            reading_time_seconds,
        )

    print(f"Passage: {passage.id} | {passage.title}")
    print(f"Alignment source: {alignment.source}")
    print(f"Transcript: {transcription.transcript}")
    print(
        "Score: "
        f"WPM={wpm if wpm is not None else 'N/A'} | "
        f"Word Recognition={word_recognition_pct if word_recognition_pct is not None else 'N/A'} | "
        f"Level={reading_level or 'N/A'} | "
        f"Major miscues={major_miscues}"
    )
    print()
    print("Word-by-word miscues:")
    for miscue in miscues:
        start = f"{miscue.start:.2f}" if miscue.start is not None else "-"
        end = f"{miscue.end:.2f}" if miscue.end is not None else "-"
        print(
            f"[{miscue.type:20}] "
            f"target={miscue.target or '-':15} "
            f"spoken={miscue.spoken or '-':15} "
            f"time={start}-{end}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
