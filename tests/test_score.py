import unittest

from backend.pipeline.score import compute_scores, estimate_reading_time_seconds


class ScoreTests(unittest.TestCase):
    def test_compute_scores_uses_philiri_thresholds(self) -> None:
        self.assertEqual(compute_scores(100, 3, 60.0), (100.0, 97.0, "Independent"))
        self.assertEqual(compute_scores(100, 9, 60.0), (100.0, 91.0, "Instructional"))
        self.assertEqual(compute_scores(100, 10, 60.0), (100.0, 90.0, "Frustration"))

    def test_compute_scores_handles_missing_duration(self) -> None:
        self.assertEqual(compute_scores(42, 4, None), (None, 90.48, "Frustration"))

    def test_estimate_reading_time_uses_min_start_and_max_end(self) -> None:
        self.assertEqual(
            estimate_reading_time_seconds([(0.4, 0.7), (1.0, 1.5), (2.1, 2.9)]),
            2.5,
        )
        self.assertIsNone(estimate_reading_time_seconds([(None, None)]))


if __name__ == "__main__":
    unittest.main()
