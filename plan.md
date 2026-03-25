# Phil-IRI ASR-Only MVP — Build Plan

**Goal:** A stripped-down, single-purpose tool that records or accepts a student's reading video/audio, runs it through an ASR pipeline, and outputs a Phil-IRI oral reading assessment result. No user accounts, no classes, no document generation. Just: _audio in → assessment out_.

---

## What This MVP Does (and Only This)

1. Accept an audio or video recording of a student reading a Phil-IRI passage
2. Transcribe the speech using ASR (Whisper)
3. Align the transcript to the target passage (forced alignment)
4. Classify miscues word by word
5. Compute WPM, Word Recognition %, and Reading Level
6. Display the result on screen

That's it.

---

## Tech Stack (Minimal)

| Layer | Tool | Why |
|---|---|---|
| Frontend | Plain HTML + JS (or simple React) | No framework overhead; fastest to ship |
| Backend | FastAPI (Python) | You're already using Python for AI; one language |
| ASR | OpenAI Whisper (`large-v3` or `base` for speed) | Core of the system |
| Forced Alignment | WhisperX | Word-level timestamps needed for miscue mapping |
| Sequence Alignment | Needleman-Wunsch (via `biopython` or custom) | Maps ASR tokens → passage words |
| Audio Processing | `ffmpeg` (extract audio from video) | Handles MP4, MOV, WebM |
| Storage | Local filesystem (temp files only) | No database, no S3; files deleted after processing |

No database. No authentication. No PDF generation. No MediaPipe. No librosa (prosody is out of scope for this MVP).

---

## Project Structure

```
philiri-asr-mvp/
├── frontend/
│   └── index.html          # Single-page UI: upload + results display
├── backend/
│   ├── main.py             # FastAPI app; single /assess endpoint
│   ├── pipeline/
│   │   ├── transcribe.py   # Whisper ASR
│   │   ├── align.py        # WhisperX forced alignment
│   │   ├── miscue.py       # Miscue classifier (rule-based)
│   │   └── score.py        # WPM, Word Recognition %, Reading Level
│   └── passages/
│       └── passages.json   # Hardcoded Phil-IRI passages (text + word count)
├── requirements.txt
└── README.md
```

---

## The One API Endpoint

```
POST /assess
Content-Type: multipart/form-data

Fields:
  - file: audio or video file (MP4, MOV, WebM, WAV)
  - passage_id: string (e.g. "grade4_english_A_pretest")

Response (JSON):
{
  "passage_id": "grade4_english_A_pretest",
  "transcript": "...",
  "wpm": 95,
  "word_recognition_pct": 91.3,
  "reading_level": "Instructional",
  "miscues": [
    { "target": "the", "spoken": "the", "type": "correct" },
    { "target": "forest", "spoken": "forst", "type": "mispronunciation" },
    ...
  ],
  "total_words": 115,
  "major_miscue_count": 10,
  "reading_time_seconds": 72.4
}
```

---

## Pipeline — Step by Step

### Step 1 — File Ingestion
- Accept the uploaded file via FastAPI
- Use `ffmpeg` to extract a clean mono `.wav` at 16kHz (Whisper's preferred format)
- Save temporarily to `/tmp/`

```bash
ffmpeg -i input.mp4 -ac 1 -ar 16000 output.wav
```

### Step 2 — ASR with Whisper
- Run `whisper large-v3` (or `base` for faster dev iteration) on the `.wav`
- Get raw transcript + approximate word timestamps

```python
import whisper
model = whisper.load_model("base")
result = model.transcribe("output.wav", word_timestamps=True)
```

> **Dev tip:** Start with `base` model (~145MB) during development. Switch to `large-v3` for accuracy testing. `base` is fast enough to iterate on the rest of the pipeline.

### Step 3 — Forced Alignment with WhisperX
- WhisperX refines Whisper's approximate timestamps to exact word-level boundaries
- Output: list of `{ word, start_time, end_time }` for every spoken word

```python
import whisperx
model_a, metadata = whisperx.load_align_model(language_code="en", device="cpu")
aligned = whisperx.align(result["segments"], model_a, metadata, "output.wav", device="cpu")
# aligned["word_segments"] → [{ "word": "the", "start": 0.12, "end": 0.34 }, ...]
```

### Step 4 — Passage Alignment (ASR tokens → target words)
- The ASR output won't perfectly match the passage (miscues, skipped words, insertions)
- Use Needleman-Wunsch sequence alignment to map each ASR token to its target passage word

```python
# Simplified logic
def align_to_passage(asr_words, passage_words):
    # Returns list of (target_word, spoken_word_or_None) pairs
    # Uses edit-distance / sequence alignment
    ...
```

- Each aligned pair gets a miscue label in the next step.

### Step 5 — Miscue Classification
Apply this decision tree per word pair:

```
1. No ASR token aligned to this position + silence > 3s  → REFUSAL
2. No ASR token aligned to this position               → OMISSION
3. ASR token == target word (case-insensitive)         → CORRECT
4. ASR token is a real word, different from target      → SUBSTITUTION
5. ASR token is not a real word:
     phonetic similarity > 0.80                        → DIALECTAL VARIATION (not an error)
     phonetic similarity ≤ 0.80                        → MISPRONUNCIATION
6. Extra ASR token with no matching target word         → INSERTION
7. Same target word aligned to 2+ ASR tokens           → REPETITION (not counted as error)
```

For phonetic similarity, use `jellyfish` (Soundex / Metaphone) or `editdistance`.

```python
import jellyfish
def phonetic_similar(word_a, word_b, threshold=0.80):
    # Compare Metaphone codes + Levenshtein distance ratio
    ...
```

**Major miscues** (counted against Word Recognition): Mispronunciation, Substitution, Omission, Insertion, Refusal.  
**Not counted**: Repetition, Dialectal Variation.

### Step 6 — Score Computation (Phil-IRI Formulas)

```python
def compute_scores(passage_word_count, major_miscues, reading_time_seconds):
    words_correct = passage_word_count - major_miscues
    word_recognition_pct = (words_correct / passage_word_count) * 100
    wpm = (passage_word_count / reading_time_seconds) * 60

    # Phil-IRI Word Recognition Level thresholds
    if word_recognition_pct >= 97:
        wr_level = "Independent"
    elif word_recognition_pct >= 91:
        wr_level = "Instructional"
    else:
        wr_level = "Frustration"

    return wpm, word_recognition_pct, wr_level
```

> **Note:** In the full system, Reading Level = combined Word Recognition + Comprehension. In this MVP (no comprehension questions), the result is **Word Recognition Level only**. Label it clearly in the output.

---

## Frontend — Single Page

The UI is intentionally minimal:

```
[ Phil-IRI ASR Assessment — MVP ]

Passage: [ dropdown: select passage ]

Upload Recording: [ file input: .mp4 / .wav / .mov ]
                  or [ Record button — uses browser MediaRecorder API ]

[ Assess ] button

--- Results ---
WPM: 95
Word Recognition: 91.3% → Instructional Level
Reading Time: 1:12

Transcript with Miscues:
  The [✓] forest [MISP: "forst"] was [✓] dark [✓] and [✓] quiet [SUB: "quite"]...

Miscue Summary:
  Mispronunciations: 4
  Substitutions: 3
  Omissions: 2
  Insertions: 1
  Total Major Miscues: 10
```

Color-code the transcript: green = correct, red = mispronunciation, orange = substitution, gray = omission.

---

## Passages Data Format

Store passages as a JSON file. No database needed for MVP.

```json
{
  "grade4_english_A_pretest": {
    "title": "The Old Balete Tree",
    "grade_level": 4,
    "language": "English",
    "set": "A",
    "cycle": "pre-test",
    "word_count": 115,
    "text": "Once upon a time, in a small village ..."
  }
}
```

Start with just 1–2 passages during development. Expand later.

---

## Build Sequence (Recommended Order)

### Week 1 — Core Pipeline (Backend Only)
- [ ] Set up FastAPI project, `/assess` endpoint skeleton
- [ ] `ffmpeg` audio extraction working
- [ ] Whisper ASR running on a test `.wav` file
- [ ] WhisperX forced alignment producing word timestamps
- [ ] Test with a manually recorded reading and print aligned output

### Week 2 — Miscue Classifier + Scoring
- [ ] Implement passage alignment (Needleman-Wunsch or simple greedy alignment)
- [ ] Implement miscue decision tree
- [ ] Implement Phil-IRI score formulas (WPM, Word Recognition %)
- [ ] Test end-to-end: audio file → JSON result
- [ ] Validate results manually against a teacher-scored sample

### Week 3 — Frontend + Integration
- [ ] Build single HTML page with file upload
- [ ] Connect to `/assess` endpoint
- [ ] Display results: WPM, Word Recognition %, color-coded transcript, miscue table
- [ ] Add browser recording (MediaRecorder API) as an alternative to file upload
- [ ] Add passage selector (dropdown driven by `passages.json`)

### Week 4 — Testing & Accuracy Benchmarking
- [ ] Collect 5–10 recorded readings with known teacher-scored results
- [ ] Run pipeline on each; compare AI miscue counts vs teacher counts
- [ ] Document accuracy gaps (this becomes your thesis baseline measurement)
- [ ] Adjust phonetic similarity thresholds based on results

---

## What This MVP Intentionally Skips

| Feature | Skipped Because |
|---|---|
| User accounts / login | Adds auth complexity; not needed to validate ASR accuracy |
| Class and roster management | Out of scope for this experiment |
| Comprehension questions | Manual scoring; Phase 2 feature |
| Computer vision (finger-pointing, etc.) | Separate module; test ASR first |
| Prosody analysis | Out of scope for this experiment |
| Document generation (Form 3A, etc.) | Only needed after assessment is validated |
| Database (PostgreSQL) | Local JSON + temp files are enough for MVP |
| Admin dashboard | No multi-user system needed yet |

Add these only after the ASR pipeline is validated against real Phil-IRI assessments.

---

## Key Risks to Watch

| Risk | Mitigation |
|---|---|
| Whisper struggles with Filipino passages | Test with Filipino passages early; switch to a multilingual Whisper model if needed (`large-v3` is multilingual by default) |
| Dialectal Cebuano pronunciation flagged as mispronunciation | Tune phonetic similarity threshold; build a small Bisaya pronunciation exception list |
| Forced alignment fails on fast or unclear speech | WhisperX handles this better than raw Whisper; fall back to Whisper-only timestamps if alignment confidence is low |
| Processing time too slow for demo | Use `base` or `small` Whisper model during demos; `large-v3` only for final accuracy testing |

---

## Definition of "Done" for This MVP

The MVP is complete when:
1. You can upload a 1–2 minute reading recording
2. The system returns WPM, Word Recognition %, and a word-by-word miscue breakdown in under 3 minutes
3. You manually verify 10 recordings and the system's Word Recognition % is within ±5% of the teacher's score on at least 7 of them

That threshold gives you a working baseline to report in your thesis and a foundation to build the full system on.