from __future__ import annotations

import argparse
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

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
        description="Batch-compare AI Phil-IRI results against teacher-scored recordings."
    )
    parser.add_argument(
        "--teacher-csv",
        required=True,
        type=Path,
        help="CSV file with recording_path, passage_id, and teacher scoring columns.",
    )
    parser.add_argument(
        "--output-csv",
        required=True,
        type=Path,
        help="Where to write the comparison report.",
    )
    parser.add_argument(
        "--inputs-dir",
        type=Path,
        default=None,
        help="Optional base directory for relative recording_path values.",
    )
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


def parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def resolve_recording_path(
    raw_path: str,
    *,
    csv_path: Path,
    inputs_dir: Path | None,
) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    if inputs_dir is not None:
        return (inputs_dir / candidate).resolve()
    return (csv_path.parent / candidate).resolve()


def run_assessment(
    recording_path: Path,
    passage_id: str,
    *,
    model_name: str,
    device: str,
    language: str | None,
    align_model: str | None,
    model_cache_dir: str | None,
    local_models_only: bool,
) -> dict[str, Any]:
    passage = get_passage_or_404(passage_id)

    with TemporaryDirectory(prefix="philiri-benchmark-") as temp_dir:
        normalized_path = Path(temp_dir) / "normalized.wav"
        normalize_media_to_wav(recording_path, normalized_path)

        transcription = transcribe_audio(
            normalized_path,
            model_name=model_name,
            device=device,
            language=language,
            download_root=model_cache_dir,
        )
        alignment = force_align_words(
            normalized_path,
            transcription,
            device=device,
            model_name=align_model,
            model_dir=model_cache_dir,
            model_cache_only=local_models_only,
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

    return {
        "ai_alignment_source": alignment.source,
        "ai_major_miscues": major_miscues,
        "ai_word_recognition_pct": word_recognition_pct,
        "ai_wpm": wpm,
        "ai_reading_level": reading_level,
        "ai_reading_time_seconds": reading_time_seconds,
    }


def main() -> int:
    args = build_parser().parse_args()
    teacher_csv = args.teacher_csv.expanduser().resolve()
    output_csv = args.output_csv.expanduser().resolve()
    inputs_dir = args.inputs_dir.expanduser().resolve() if args.inputs_dir else None
    if not teacher_csv.exists():
        raise SystemExit(f"Teacher-score CSV not found: {teacher_csv}")

    resolved_model_name = args.model or get_whisper_model_name()
    resolved_device = args.device or get_runtime_device()
    resolved_language = args.language or get_whisper_language()
    resolved_cache_dir = args.model_cache_dir or get_model_cache_dir()

    output_rows: list[dict[str, Any]] = []

    with teacher_csv.open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for row in reader:
            recording_path = resolve_recording_path(
                row.get("recording_path", ""),
                csv_path=teacher_csv,
                inputs_dir=inputs_dir,
            )
            output_row: dict[str, Any] = {
                "student_id": row.get("student_id", "").strip(),
                "recording_path": str(recording_path),
                "passage_id": row.get("passage_id", "").strip(),
                "teacher_major_miscues": row.get("teacher_major_miscues", "").strip(),
                "teacher_word_recognition_pct": row.get("teacher_word_recognition_pct", "").strip(),
                "teacher_wpm": row.get("teacher_wpm", "").strip(),
            }

            try:
                if not output_row["passage_id"]:
                    raise ValueError("passage_id is required.")
                if not recording_path.exists():
                    raise FileNotFoundError(f"Recording not found: {recording_path}")

                assessment = run_assessment(
                    recording_path,
                    output_row["passage_id"],
                    model_name=resolved_model_name,
                    device=resolved_device,
                    language=resolved_language,
                    align_model=args.align_model,
                    model_cache_dir=resolved_cache_dir,
                    local_models_only=args.local_models_only,
                )
                output_row.update(assessment)

                teacher_major_miscues = parse_optional_float(output_row["teacher_major_miscues"])
                teacher_word_recognition_pct = parse_optional_float(
                    output_row["teacher_word_recognition_pct"]
                )
                teacher_wpm = parse_optional_float(output_row["teacher_wpm"])
                ai_major_miscues = float(assessment["ai_major_miscues"])
                ai_word_recognition_pct = assessment["ai_word_recognition_pct"]
                ai_wpm = assessment["ai_wpm"]

                output_row["delta_major_miscues"] = (
                    round(ai_major_miscues - teacher_major_miscues, 2)
                    if teacher_major_miscues is not None
                    else ""
                )
                output_row["delta_word_recognition_pct"] = (
                    round(ai_word_recognition_pct - teacher_word_recognition_pct, 2)
                    if ai_word_recognition_pct is not None and teacher_word_recognition_pct is not None
                    else ""
                )
                output_row["delta_wpm"] = (
                    round(ai_wpm - teacher_wpm, 2)
                    if ai_wpm is not None and teacher_wpm is not None
                    else ""
                )
                output_row["within_5pct_word_recognition"] = (
                    abs(ai_word_recognition_pct - teacher_word_recognition_pct) <= 5
                    if ai_word_recognition_pct is not None and teacher_word_recognition_pct is not None
                    else ""
                )
                output_row["error"] = ""
            except Exception as error:  # pragma: no cover - defensive batch boundary
                output_row.update(
                    {
                        "ai_alignment_source": "",
                        "ai_major_miscues": "",
                        "ai_word_recognition_pct": "",
                        "ai_wpm": "",
                        "ai_reading_level": "",
                        "ai_reading_time_seconds": "",
                        "delta_major_miscues": "",
                        "delta_word_recognition_pct": "",
                        "delta_wpm": "",
                        "within_5pct_word_recognition": "",
                        "error": str(error),
                    }
                )

            output_rows.append(output_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "student_id",
        "recording_path",
        "passage_id",
        "teacher_major_miscues",
        "teacher_word_recognition_pct",
        "teacher_wpm",
        "ai_alignment_source",
        "ai_major_miscues",
        "ai_word_recognition_pct",
        "ai_wpm",
        "ai_reading_level",
        "ai_reading_time_seconds",
        "delta_major_miscues",
        "delta_word_recognition_pct",
        "delta_wpm",
        "within_5pct_word_recognition",
        "error",
    ]
    with output_csv.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    comparable_rows = [
        row
        for row in output_rows
        if row.get("within_5pct_word_recognition") != "" and not row.get("error")
    ]
    within_5_count = sum(1 for row in comparable_rows if row["within_5pct_word_recognition"])
    abs_deltas = [
        abs(float(row["delta_word_recognition_pct"]))
        for row in comparable_rows
        if row.get("delta_word_recognition_pct") not in {"", None}
    ]

    print(f"Rows processed: {len(output_rows)}")
    print(f"Successful assessments: {sum(1 for row in output_rows if not row.get('error'))}")
    print(f"Rows with teacher WR comparison: {len(comparable_rows)}")
    print(f"Within +/-5 WR percentage points: {within_5_count}")
    if abs_deltas:
        mean_abs_delta = round(sum(abs_deltas) / len(abs_deltas), 2)
        print(f"Mean absolute WR delta: {mean_abs_delta}")
    print(f"Report written to: {output_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
