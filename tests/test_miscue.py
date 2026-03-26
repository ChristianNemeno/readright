import unittest

from backend.pipeline.miscue import classify_miscues
from backend.pipeline.types import AlignmentResult, WordSegment


class MiscueTests(unittest.TestCase):
    def test_classify_miscues_detects_mispronunciation(self) -> None:
        alignment = AlignmentResult(
            words=[
                WordSegment(word="The", start=0.0, end=0.2),
                WordSegment(word="forst", start=0.2, end=0.7),
                WordSegment(word="was", start=0.8, end=1.0),
            ],
            source="whisperx",
        )

        miscues = classify_miscues(["The", "forest", "was"], alignment)
        self.assertEqual([miscue.type for miscue in miscues], ["correct", "mispronunciation", "correct"])

    def test_classify_miscues_detects_repetition(self) -> None:
        alignment = AlignmentResult(
            words=[
                WordSegment(word="go", start=0.0, end=0.3),
                WordSegment(word="go", start=0.35, end=0.6),
            ],
            source="whisperx",
        )

        miscues = classify_miscues(["go"], alignment)
        self.assertEqual([miscue.type for miscue in miscues], ["repetition", "correct"])

    def test_classify_miscues_detects_refusal_from_long_gap(self) -> None:
        alignment = AlignmentResult(
            words=[
                WordSegment(word="one", start=0.0, end=0.4),
                WordSegment(word="three", start=4.8, end=5.2),
            ],
            source="whisperx",
        )

        miscues = classify_miscues(["one", "two", "three"], alignment)
        self.assertEqual([miscue.type for miscue in miscues], ["correct", "refusal", "correct"])


if __name__ == "__main__":
    unittest.main()
