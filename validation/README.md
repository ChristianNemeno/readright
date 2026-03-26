# Validation Workflow

This folder holds the repeatable workflow for the Week 4 benchmark in `plan.md`.

## Files

- `teacher_scores.template.csv`: template for your teacher-scored benchmark set.
- `results/`: recommended output folder for generated comparison reports.

## 1. Collect benchmark recordings

Create a set of 5-10 recordings that already have teacher-scored Phil-IRI results.

For each recording, capture at least:

- `recording_path`
- `passage_id`
- `teacher_major_miscues`
- `teacher_word_recognition_pct`
- `teacher_wpm`

You can optionally include a `student_id` column.

## 2. Fill the template

Copy `teacher_scores.template.csv` and replace the placeholder rows with your real recordings.

Relative `recording_path` values can be resolved from either:

- the CSV file location, or
- the `--inputs-dir` argument when you run the validator.

## 3. Run the comparison script

```powershell
.\.venv\Scripts\python.exe scripts\validate_teacher_scores.py `
  --teacher-csv validation\teacher_scores.csv `
  --inputs-dir recordings `
  --output-csv validation\results\benchmark_report.csv
```

Add `--local-models-only` if you already downloaded the required Whisper and WhisperX models.

## 4. Interpret the report

The generated CSV includes:

- AI major miscues, WPM, and Word Recognition %
- deltas versus the teacher values
- a `within_5pct_word_recognition` flag for the thesis success criterion
- an `error` column for rows that failed to process

The Week 4 benchmark in `plan.md` is satisfied once you populate this workflow with real teacher-scored recordings and review the resulting report.
