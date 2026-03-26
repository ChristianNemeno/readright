from typing import Optional


def estimate_reading_time_seconds(
    starts_and_ends: list[tuple[Optional[float], Optional[float]]],
) -> Optional[float]:
    starts = [start for start, _ in starts_and_ends if start is not None]
    ends = [end for _, end in starts_and_ends if end is not None]
    if not starts or not ends:
        return None
    duration = max(0.0, max(ends) - min(starts))
    return round(duration, 2)


def compute_scores(
    passage_word_count: int,
    major_miscues: int,
    reading_time_seconds: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    if passage_word_count <= 0:
        return None, None, None

    words_correct = max(0, passage_word_count - major_miscues)
    word_recognition_pct = round((words_correct / passage_word_count) * 100, 2)

    wpm = None
    if reading_time_seconds and reading_time_seconds > 0:
        wpm = round((passage_word_count / reading_time_seconds) * 60, 2)

    if word_recognition_pct >= 97:
        word_recognition_level = "Independent"
    elif word_recognition_pct >= 91:
        word_recognition_level = "Instructional"
    else:
        word_recognition_level = "Frustration"

    return wpm, word_recognition_pct, word_recognition_level
