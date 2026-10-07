import math
import unittest

from llm2jev.utils.json import copy_json_content, is_json_content
from llm2jev.utils.probability import (
    copy_probability_distribution,
    validate_probabilities,
    validate_probability,
)


class JsonUtilsTests(unittest.TestCase):
    def test_copies_nested_json_containers(self) -> None:
        original = {"items": [{"value": 1}]}

        copied = copy_json_content(original)
        original["items"][0]["value"] = 2

        self.assertEqual(copied, {"items": [{"value": 1}]})

    def test_rejects_non_json_nested_values(self) -> None:
        self.assertFalse(is_json_content({"invalid": object()}))


class ProbabilityUtilsTests(unittest.TestCase):
    def test_validates_scalar_and_sequence_probabilities(self) -> None:
        self.assertEqual(validate_probability(1), 1.0)
        self.assertEqual(validate_probabilities([0, 0.25, 1]), (0.0, 0.25, 1.0))

    def test_rejects_non_finite_and_boolean_probabilities(self) -> None:
        for probability in (math.nan, math.inf, True):
            with self.subTest(probability=probability):
                with self.assertRaises(ValueError):
                    validate_probability(probability)

    def test_copies_and_validates_distribution(self) -> None:
        original = {"a": 0.75, "b": 0.25}

        copied = copy_probability_distribution(original)
        original["a"] = 1.0

        self.assertEqual(copied, {"a": 0.75, "b": 0.25})

    def test_rejects_distribution_that_does_not_sum_to_one(self) -> None:
        with self.assertRaises(ValueError):
            copy_probability_distribution({"a": 0.5, "b": 0.4})


if __name__ == "__main__":
    unittest.main()
