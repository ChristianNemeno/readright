import re
from typing import Optional

import jellyfish

from backend.pipeline.types import AlignmentResult, WordSegment
from backend.schemas import MiscueRecord

TOKEN_RE = re.compile(r"\b[\w']+\b", re.UNICODE)
MAJOR_MISCUE_TYPES = {"mispronunciation", "substitution", "omission", "insertion", "refusal"}
COMMON_FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "to",
    "was",
    "we",
    "were",
    "will",
    "with",
    "you",
}


def tokenize_words(text: str) -> list[str]:
    return TOKEN_RE.findall(text)


def normalize_token(token: str) -> str:
    return re.sub(r"[^\w']+", "", token.lower()).strip("_'")


def phonetic_similarity(word_a: str, word_b: str) -> float:
    normalized_a = normalize_token(word_a)
    normalized_b = normalize_token(word_b)
    if not normalized_a or not normalized_b:
        return 0.0
    if normalized_a == normalized_b:
        return 1.0

    direct_ratio = 1 - (
        jellyfish.levenshtein_distance(normalized_a, normalized_b)
        / max(len(normalized_a), len(normalized_b))
    )
    metaphone_a = jellyfish.metaphone(normalized_a) or normalized_a
    metaphone_b = jellyfish.metaphone(normalized_b) or normalized_b
    phonetic_ratio = 1 - (
        jellyfish.levenshtein_distance(metaphone_a, metaphone_b)
        / max(len(metaphone_a), len(metaphone_b), 1)
    )

    return (direct_ratio * 0.4) + (phonetic_ratio * 0.6)


def _looks_like_real_word(spoken_word: str, target_word: str) -> bool:
    normalized_spoken = normalize_token(spoken_word)
    normalized_target = normalize_token(target_word)
    if not normalized_spoken or not normalized_spoken.isalpha():
        return False
    if normalized_spoken in COMMON_FUNCTION_WORDS:
        return True
    if len(normalized_spoken) <= 2:
        return True
    if (
        normalized_target
        and jellyfish.levenshtein_distance(normalized_spoken, normalized_target) <= 1
        and len(normalized_spoken) >= 4
    ):
        return False
    return any(vowel in normalized_spoken for vowel in "aeiou")


def _pair_score(target_word: str, spoken_word: str) -> int:
    target_normalized = normalize_token(target_word)
    spoken_normalized = normalize_token(spoken_word)
    if not target_normalized or not spoken_normalized:
        return -1
    if target_normalized == spoken_normalized:
        return 3
    if phonetic_similarity(target_normalized, spoken_normalized) >= 0.8:
        return 1
    return -1


def align_to_passage(
    spoken_words: list[WordSegment],
    target_words: list[str],
) -> list[tuple[Optional[str], Optional[WordSegment]]]:
    target_count = len(target_words)
    spoken_count = len(spoken_words)
    gap_penalty = -1

    scores = [[0] * (spoken_count + 1) for _ in range(target_count + 1)]
    trace = [[None] * (spoken_count + 1) for _ in range(target_count + 1)]

    for target_index in range(1, target_count + 1):
        scores[target_index][0] = scores[target_index - 1][0] + gap_penalty
        trace[target_index][0] = "up"
    for spoken_index in range(1, spoken_count + 1):
        scores[0][spoken_index] = scores[0][spoken_index - 1] + gap_penalty
        trace[0][spoken_index] = "left"

    for target_index in range(1, target_count + 1):
        for spoken_index in range(1, spoken_count + 1):
            diagonal_score = scores[target_index - 1][spoken_index - 1] + _pair_score(
                target_words[target_index - 1],
                spoken_words[spoken_index - 1].word,
            )
            up_score = scores[target_index - 1][spoken_index] + gap_penalty
            left_score = scores[target_index][spoken_index - 1] + gap_penalty

            best_score = max(diagonal_score, up_score, left_score)
            scores[target_index][spoken_index] = best_score
            if best_score == diagonal_score:
                trace[target_index][spoken_index] = "diag"
            elif best_score == up_score:
                trace[target_index][spoken_index] = "up"
            else:
                trace[target_index][spoken_index] = "left"

    aligned_pairs: list[tuple[Optional[str], Optional[WordSegment]]] = []
    target_index = target_count
    spoken_index = spoken_count

    while target_index > 0 or spoken_index > 0:
        direction = trace[target_index][spoken_index]
        if direction == "diag":
            aligned_pairs.append(
                (
                    target_words[target_index - 1],
                    spoken_words[spoken_index - 1],
                )
            )
            target_index -= 1
            spoken_index -= 1
        elif direction == "up":
            aligned_pairs.append((target_words[target_index - 1], None))
            target_index -= 1
        else:
            aligned_pairs.append((None, spoken_words[spoken_index - 1]))
            spoken_index -= 1

    aligned_pairs.reverse()
    return aligned_pairs


def _find_neighbor_gap(
    aligned_pairs: list[tuple[Optional[str], Optional[WordSegment]]],
    current_index: int,
) -> float | None:
    previous_end = None
    next_start = None

    for index in range(current_index - 1, -1, -1):
        spoken_word = aligned_pairs[index][1]
        if spoken_word and spoken_word.end is not None:
            previous_end = spoken_word.end
            break

    for index in range(current_index + 1, len(aligned_pairs)):
        spoken_word = aligned_pairs[index][1]
        if spoken_word and spoken_word.start is not None:
            next_start = spoken_word.start
            break

    if previous_end is None or next_start is None:
        return None
    return max(0.0, next_start - previous_end)


def _previous_target_word(
    aligned_pairs: list[tuple[Optional[str], Optional[WordSegment]]],
    current_index: int,
) -> str | None:
    for index in range(current_index - 1, -1, -1):
        target_word = aligned_pairs[index][0]
        if target_word:
            return target_word
    return None


def _next_target_word(
    aligned_pairs: list[tuple[Optional[str], Optional[WordSegment]]],
    current_index: int,
) -> str | None:
    for index in range(current_index + 1, len(aligned_pairs)):
        target_word = aligned_pairs[index][0]
        if target_word:
            return target_word
    return None


def classify_miscues(
    target_words: list[str],
    alignment: AlignmentResult,
) -> list[MiscueRecord]:
    aligned_pairs = align_to_passage(alignment.words, target_words)
    miscues: list[MiscueRecord] = []

    for index, (target_word, spoken_word) in enumerate(aligned_pairs):
        if target_word is None and spoken_word is not None:
            spoken_normalized = normalize_token(spoken_word.word)
            previous_target = _previous_target_word(aligned_pairs, index)
            next_target = _next_target_word(aligned_pairs, index)
            is_repetition = spoken_normalized in {
                normalize_token(previous_target) if previous_target else "",
                normalize_token(next_target) if next_target else "",
            }
            miscue_type = "repetition" if is_repetition else "insertion"
            miscues.append(
                MiscueRecord(
                    target="",
                    spoken=spoken_word.word,
                    type=miscue_type,
                    start=spoken_word.start,
                    end=spoken_word.end,
                    counts_as_major_miscue=miscue_type in MAJOR_MISCUE_TYPES,
                )
            )
            continue

        if target_word is not None and spoken_word is None:
            gap_duration = _find_neighbor_gap(aligned_pairs, index)
            miscue_type = "refusal" if gap_duration is not None and gap_duration > 3.0 else "omission"
            miscues.append(
                MiscueRecord(
                    target=target_word,
                    spoken=None,
                    type=miscue_type,
                    start=None,
                    end=None,
                    counts_as_major_miscue=miscue_type in MAJOR_MISCUE_TYPES,
                )
            )
            continue

        if target_word is None or spoken_word is None:
            continue

        target_normalized = normalize_token(target_word)
        spoken_normalized = normalize_token(spoken_word.word)
        if target_normalized == spoken_normalized:
            miscue_type = "correct"
        else:
            similarity = phonetic_similarity(target_normalized, spoken_normalized)
            if _looks_like_real_word(spoken_normalized, target_normalized):
                miscue_type = "substitution"
            elif (
                similarity > 0.92
                and abs(len(spoken_normalized) - len(target_normalized)) == 0
            ):
                miscue_type = "dialectal_variation"
            else:
                miscue_type = "mispronunciation"

        miscues.append(
            MiscueRecord(
                target=target_word,
                spoken=spoken_word.word,
                type=miscue_type,
                start=spoken_word.start,
                end=spoken_word.end,
                counts_as_major_miscue=miscue_type in MAJOR_MISCUE_TYPES,
            )
        )

    return miscues
