from backend.pipeline.types import AlignmentResult
from backend.schemas import MiscueRecord


def classify_miscues(
    target_words: list[str],
    alignment: AlignmentResult,
) -> list[MiscueRecord]:
    raise NotImplementedError(
        "Miscue classification is scheduled for Phase 3. "
        f"Received {len(target_words)} target words and {len(alignment.words)} aligned words."
    )
