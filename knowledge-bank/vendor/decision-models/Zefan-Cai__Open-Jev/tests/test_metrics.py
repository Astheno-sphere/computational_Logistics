import math
import unittest

from jev.metrics import (
    choice_confidence,
    evaluate_probabilities,
    fit_temperature,
    score_confidence,
    sigmoid,
    softmax,
)


class ProbabilityMetricsTest(unittest.TestCase):
    def test_hard_outcomes_have_known_scores_and_coverage(self):
        result = evaluate_probabilities([0, 1], [[0.8, 0.2], [0.6, 0.4]], thresholds=(0.7, 0.9))
        self.assertEqual(result["accuracy"], 0.5)
        self.assertEqual(result["expected_accuracy"], 0.5)
        self.assertAlmostEqual(result["nll"], -(math.log(0.8) + math.log(0.4)) / 2)
        self.assertAlmostEqual(result["brier"], 0.4)
        self.assertAlmostEqual(result["multiclass_ece"], 0.4)
        self.assertEqual(result["coverage"][0]["coverage"], 0.5)
        self.assertEqual(result["coverage"][0]["expected_risk"], 0.0)
        self.assertEqual(result["coverage"][1]["selected"], 0)
        self.assertIsNone(result["coverage"][1]["accuracy"])
        self.assertIsNone(result["coverage"][1]["expected_risk"])

    def test_soft_targets_are_not_argmax_ground_truth(self):
        result = evaluate_probabilities([[0.7, 0.3]], [[0.7, 0.3]])
        self.assertIsNone(result["accuracy"])
        self.assertEqual(result["hard_count"], 0)
        self.assertEqual(result["expected_accuracy"], 0.7)
        self.assertAlmostEqual(result["brier"], 0.0)
        self.assertAlmostEqual(result["expected_brier"], 0.42)
        self.assertAlmostEqual(result["multiclass_ece"], 0.0)

    def test_mixed_targets_and_variable_cardinality(self):
        result = evaluate_probabilities(
            [0, [0.2, 0.3, 0.5], [0.0, 1.0]],
            [[0.9, 0.1], [0.1, 0.2, 0.7], [0.2, 0.8]],
        )
        self.assertEqual(result["hard_count"], 2)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertAlmostEqual(result["expected_accuracy"], 2.5 / 3)

    def test_perfect_probabilities_fit_last_ece_bin(self):
        result = evaluate_probabilities([0, 1], [[1.0, 0.0], [0.0, 1.0]], thresholds=(1.0,))
        self.assertEqual(result["nll"], 0.0)
        self.assertEqual(result["multiclass_ece"], 0.0)
        self.assertEqual(result["coverage"][0]["coverage"], 1.0)

    def test_invalid_probability_data_is_rejected(self):
        for targets, probabilities in [([], []), ([0], []), ([2], [[0.5, 0.5]]),
                                       ([0], [[0.2, 0.2]]), ([0], [[-0.1, 1.1]]),
                                       ([[0.5, 0.5]], [[0.2, 0.3, 0.5]])]:
            with self.subTest(targets=targets, probabilities=probabilities):
                with self.assertRaises(ValueError):
                    evaluate_probabilities(targets, probabilities)


class CalibrationTest(unittest.TestCase):
    def test_temperature_recovers_known_bernoulli_frequency(self):
        logits = [[3.0, 0.0]] * 10
        targets = [0] * 8 + [1] * 2
        temperature = fit_temperature(logits, targets)
        self.assertAlmostEqual(temperature, 3.0 / math.log(4.0), places=4)
        before = evaluate_probabilities(targets, [softmax(row) for row in logits])
        after = evaluate_probabilities(targets, [softmax(row, temperature) for row in logits])
        self.assertLess(after["nll"], before["nll"])
        self.assertLess(after["multiclass_ece"], before["multiclass_ece"])
        self.assertEqual(after["accuracy"], before["accuracy"])

    def test_soft_labels_and_constant_logits(self):
        temperature = fit_temperature([[3.0, 0.0]], [[0.75, 0.25]])
        self.assertAlmostEqual(temperature, 3.0 / math.log(3.0), places=4)
        flat_temperature = fit_temperature([[0.0, 0.0]], [[0.5, 0.5]])
        self.assertEqual(flat_temperature, 1.0)
        self.assertEqual(softmax([0.0, 0.0], flat_temperature), [0.5, 0.5])

    def test_extreme_logits_and_binary_probabilities(self):
        self.assertEqual(softmax([1000.0, -1000.0, -math.inf]), [1.0, 0.0, 0.0])
        self.assertEqual(sigmoid(1000.0), 1.0)
        self.assertEqual(sigmoid(-1000.0), 0.0)
        self.assertAlmostEqual(sigmoid(2.0), softmax([0.0, 2.0])[1])
        with self.assertRaises(ValueError):
            softmax([-math.inf, -math.inf])
        with self.assertRaises(ValueError):
            fit_temperature([[math.nan, 0.0]], [0])


class OfficialConfidenceTest(unittest.TestCase):
    def test_uniform_and_deterministic_distributions(self):
        for function in (choice_confidence, score_confidence):
            self.assertEqual(function([0.25] * 4), 0.0)
            self.assertEqual(function([0.0] * 4), 0.0)
            self.assertEqual(function([0.0, 1.0, 0.0]), 1.0)
            self.assertEqual(function([1.0]), 1.0)

    def test_choice_uses_scaled_peak(self):
        self.assertAlmostEqual(choice_confidence([0.8, 0.1, 0.1]), 0.7)
        self.assertAlmostEqual(choice_confidence([8.0, 1.0, 1.0]), 0.7)

    def test_score_depends_on_ordinal_distance_and_first_mode(self):
        self.assertAlmostEqual(score_confidence([0.0, 0.7, 0.3]), 0.55)
        self.assertAlmostEqual(score_confidence([0.5, 0.5, 0.0]), 0.25)
        self.assertEqual(score_confidence([0.5, 0.0, 0.5]), 0.0)


if __name__ == "__main__":
    unittest.main()
