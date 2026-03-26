import unittest

from backend.passages.service import count_passage_words, list_passage_summaries, load_passages


class PassageTests(unittest.TestCase):
    def test_declared_word_counts_match_passage_text(self) -> None:
        for passage in load_passages().values():
            self.assertEqual(count_passage_words(passage.text), passage.word_count, passage.id)

    def test_summaries_are_sorted_and_available(self) -> None:
        summaries = list_passage_summaries()
        self.assertGreaterEqual(len(summaries), 2)
        self.assertEqual(
            [(summary.grade_level, summary.language, summary.title) for summary in summaries],
            sorted((summary.grade_level, summary.language, summary.title) for summary in summaries),
        )


if __name__ == "__main__":
    unittest.main()
