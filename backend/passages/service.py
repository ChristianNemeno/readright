import json
import re
from functools import lru_cache

from fastapi import HTTPException, status

from backend.config import PASSAGES_PATH
from backend.schemas import Passage, PassageSummary

WORD_RE = re.compile(r"\b[\w']+\b", re.UNICODE)


class PassageDataError(RuntimeError):
    """Raised when the passage catalog contains inconsistent scoring data."""


def count_passage_words(text: str) -> int:
    return len(WORD_RE.findall(text))


@lru_cache(maxsize=1)
def load_passages() -> dict[str, Passage]:
    with PASSAGES_PATH.open("r", encoding="utf-8-sig") as passages_file:
        raw_passages = json.load(passages_file)

    passages: dict[str, Passage] = {}
    for passage_id, payload in raw_passages.items():
        passage = Passage(id=passage_id, **payload)
        actual_word_count = count_passage_words(passage.text)
        if actual_word_count != passage.word_count:
            raise PassageDataError(
                "Passage word-count mismatch for "
                f"'{passage_id}': declared {passage.word_count}, actual {actual_word_count}."
            )
        passages[passage_id] = passage

    return passages


def list_passage_summaries() -> list[PassageSummary]:
    passages = load_passages().values()
    summaries = [
        PassageSummary(
            id=passage.id,
            title=passage.title,
            grade_level=passage.grade_level,
            language=passage.language,
            set=passage.set,
            cycle=passage.cycle,
            word_count=passage.word_count,
        )
        for passage in passages
    ]
    return sorted(summaries, key=lambda item: (item.grade_level, item.language, item.title))


def get_passage_or_404(passage_id: str) -> Passage:
    passage = load_passages().get(passage_id)
    if passage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown passage_id '{passage_id}'.",
        )
    return passage

