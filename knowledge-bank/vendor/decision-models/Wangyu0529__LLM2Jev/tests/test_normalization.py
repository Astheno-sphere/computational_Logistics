import math
import unittest

from llm2jev import normalize_l1


class NormalizeL1Tests(unittest.TestCase):
    def test_normalizes_probabilities(self) -> None:
        self.assertEqual(normalize_l1([0.9, 0.3]), (0.75, 0.25))

    def test_returns_uniform_distribution_for_all_zeroes(self) -> None:
        self.assertEqual(normalize_l1([0.0, 0.0, 0.0]), (1 / 3, 1 / 3, 1 / 3))

    def test_rejects_empty_input(self) -> None:
        with self.assertRaises(ValueError):
            normalize_l1([])

    def test_rejects_invalid_probabilities(self) -> None:
        for probabilities in ([1.1], [-0.1], [math.nan], [True]):
            with self.subTest(probabilities=probabilities):
                with self.assertRaises(ValueError):
                    normalize_l1(probabilities)


if __name__ == "__main__":
    unittest.main()
