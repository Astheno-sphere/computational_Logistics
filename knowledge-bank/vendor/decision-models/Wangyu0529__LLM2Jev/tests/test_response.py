import json
import unittest

from llm2jev import ChoiceAnswer, JevResponse, NoulAnswer, ScoreAnswer, Usage


class ChoiceAnswerTests(unittest.TestCase):
    def test_serializes_choice_answer(self) -> None:
        answer = ChoiceAnswer(
            choice="returns",
            confidence=0.39,
            probabilities={"shipping": 0.02, "billing": 0.38, "returns": 0.60},
        )

        self.assertEqual(
            answer.to_dict(),
            {
                "type": "choice",
                "choice": "returns",
                "confidence": 0.39,
                "probabilities": {"shipping": 0.02, "billing": 0.38, "returns": 0.60},
            },
        )

    def test_choice_must_have_highest_probability(self) -> None:
        with self.assertRaises(ValueError):
            ChoiceAnswer(choice="a", confidence=0.5, probabilities={"a": 0.4, "b": 0.6})


class ScoreAnswerTests(unittest.TestCase):
    def test_serializes_integer_levels_as_json_keys(self) -> None:
        answer = ScoreAnswer(
            score=1.24,
            confidence=0.63,
            legend={0: "Cosmetic", 1: "Degraded", 2: "Blocking"},
            probabilities={0: 0.0, 1: 0.76, 2: 0.24},
        )

        self.assertEqual(
            answer.to_dict(),
            {
                "type": "score",
                "score": 1.24,
                "confidence": 0.63,
                "legend": {"0": "Cosmetic", "1": "Degraded", "2": "Blocking"},
                "probabilities": {"0": 0.0, "1": 0.76, "2": 0.24},
            },
        )

    def test_requires_matching_legend_and_probability_levels(self) -> None:
        with self.assertRaises(ValueError):
            ScoreAnswer(
                score=0.5,
                confidence=0.5,
                legend={0: "Low", 1: "High"},
                probabilities={0: 1.0},
            )

    def test_requires_weighted_average_score(self) -> None:
        with self.assertRaises(ValueError):
            ScoreAnswer(
                score=1.0,
                confidence=0.5,
                legend={0: "Low", 1: "High"},
                probabilities={0: 0.75, 1: 0.25},
            )


class NoulAnswerTests(unittest.TestCase):
    def test_serializes_noul_answer(self) -> None:
        self.assertEqual(
            NoulAnswer(noul=0.98).to_dict(),
            {"type": "noul", "noul": 0.98},
        )

    def test_rejects_out_of_range_probability(self) -> None:
        with self.assertRaises(ValueError):
            NoulAnswer(noul=1.1)


class UsageTests(unittest.TestCase):
    def test_allows_unreported_counts(self) -> None:
        self.assertEqual(
            Usage().to_dict(),
            {"input_tokens": None, "output_tokens": None},
        )

    def test_rejects_negative_counts(self) -> None:
        with self.assertRaises(ValueError):
            Usage(input_tokens=-1)


class JevResponseTests(unittest.TestCase):
    def test_serializes_and_groups_answers(self) -> None:
        choice = ChoiceAnswer(
            choice="returns",
            confidence=0.8,
            probabilities={"returns": 0.8, "billing": 0.2},
        )
        score = ScoreAnswer(
            score=0.25,
            confidence=0.7,
            legend={0: "Low", 1: "High"},
            probabilities={0: 0.75, 1: 0.25},
        )
        noul = NoulAnswer(noul=0.9)
        response = JevResponse(
            model="本地模型",
            answers={"department": choice, "severity": score, "refund": noul},
            usage=Usage(input_tokens=120, output_tokens=12),
        )

        self.assertEqual(response.choices, {"department": choice})
        self.assertEqual(response.scores, {"severity": score})
        self.assertEqual(response.nouls, {"refund": noul})
        self.assertEqual(response.to_dict()["usage"], {"input_tokens": 120, "output_tokens": 12})
        self.assertEqual(response.to_dict()["answers"]["refund"], {"type": "noul", "noul": 0.9})  # type: ignore[index]
        self.assertEqual(json.loads(response.json), response.to_dict())
        self.assertIn('"confidence": 0.80', response.json)
        self.assertIn('"noul": 0.90', response.json)
        self.assertIn('"input_tokens": 120', response.json)

    def test_json_rounds_floats_to_two_decimal_places_without_mutating_values(self) -> None:
        response = JevResponse(
            model="jev-latest",
            answers={"refund": NoulAnswer(noul=0.126)},
            usage=Usage(),
        )

        self.assertIn('"noul": 0.13', response.json)
        self.assertEqual(response.to_dict()["answers"]["refund"], {"type": "noul", "noul": 0.126})  # type: ignore[index]

    def test_rejects_empty_answers(self) -> None:
        with self.assertRaises(ValueError):
            JevResponse(model="jev-latest", answers={}, usage=Usage())


class ProbabilityValidationTests(unittest.TestCase):
    def test_probabilities_must_sum_to_one(self) -> None:
        with self.assertRaises(ValueError):
            ChoiceAnswer(choice="a", confidence=0.5, probabilities={"a": 0.6, "b": 0.3})

    def test_confidence_must_be_in_range(self) -> None:
        with self.assertRaises(ValueError):
            ChoiceAnswer(choice="a", confidence=-0.1, probabilities={"a": 1.0})


if __name__ == "__main__":
    unittest.main()
