from typing import Optional


def compute_scores(
    passage_word_count: int,
    major_miscues: int,
    reading_time_seconds: Optional[float],
) -> tuple[Optional[float], Optional[float], Optional[str]]:
    raise NotImplementedError(
        "Phil-IRI scoring is scheduled for Phase 3. "
        f"Received passage_word_count={passage_word_count}, major_miscues={major_miscues}, "
        f"reading_time_seconds={reading_time_seconds}."
    )
