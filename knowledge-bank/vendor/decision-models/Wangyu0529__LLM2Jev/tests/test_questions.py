import unittest

from llm2jev import Choice, Noul, Score


class ChoiceTests(unittest.TestCase):
    def test_serializes_choice(self) -> None:
        question = Choice(
            instructions="Which team should handle this?",
            criteria={"returns": "Refunds and exchanges", "billing": None},
        )

        self.assertEqual(
            question.to_dict(),
            {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {"returns": "Refunds and exchanges", "billing": None},
            },
        )

    def test_accepts_structured_content_and_optional_instructions(self) -> None:
        question = Choice(criteria={"match": {"codes": [1, 2]}, "other": None})

        self.assertEqual(
            question.to_dict(),
            {
                "type": "choice",
                "criteria": {"match": {"codes": [1, 2]}, "other": None},
            },
        )


class ScoreTests(unittest.TestCase):
    def test_serializes_score_and_preserves_order(self) -> None:
        question = Score(
            instructions="How severe is this?",
            criteria=["Low", "Medium", "High"],
        )

        self.assertEqual(
            question.to_dict(),
            {
                "type": "score",
                "instructions": "How severe is this?",
                "criteria": ["Low", "Medium", "High"],
            },
        )

    def test_requires_between_two_and_ten_levels(self) -> None:
        with self.assertRaises(ValueError):
            Score(instructions="Rate this.", criteria=["Only"])
        with self.assertRaises(ValueError):
            Score(instructions="Rate this.", criteria=[str(index) for index in range(11)])

    def test_accepts_structured_levels_and_instructions(self) -> None:
        question = Score(
            instructions={"task": "Rate urgency"},
            criteria=[{"urgency": "low"}, ["high", {"sla_hours": 1}]],
        )

        self.assertEqual(
            question.to_dict()["criteria"],
            [{"urgency": "low"}, ["high", {"sla_hours": 1}]],
        )


class NoulTests(unittest.TestCase):
    def test_omits_optional_criteria(self) -> None:
        question = Noul(instructions="Is a refund requested?")

        self.assertEqual(
            question.to_dict(),
            {"type": "noul", "instructions": "Is a refund requested?"},
        )

    def test_serializes_true_and_false_criteria(self) -> None:
        question = Noul(
            instructions="Is a refund requested?",
            criteria={"true": "A refund is requested", "false": "No refund is requested"},
        )

        self.assertEqual(
            question.to_dict()["criteria"],
            {"true": "A refund is requested", "false": "No refund is requested"},
        )

    def test_accepts_partial_and_null_criteria(self) -> None:
        question = Noul(criteria={"true": {"meaning": "Yes"}, "false": None})

        self.assertEqual(
            question.to_dict(),
            {"type": "noul", "criteria": {"true": {"meaning": "Yes"}, "false": None}},
        )

    def test_rejects_unknown_criteria(self) -> None:
        with self.assertRaises(ValueError):
            Noul(criteria={"yes": "Yes"})


class SharedValidationTests(unittest.TestCase):
    def test_rejects_non_json_instructions(self) -> None:
        with self.assertRaises(ValueError):
            Choice(instructions=object(), criteria={"a": None})  # type: ignore[arg-type]

    def test_rejects_non_json_nested_values(self) -> None:
        with self.assertRaises(ValueError):
            Choice(criteria={"a": {"invalid": object()}})  # type: ignore[dict-item]


if __name__ == "__main__":
    unittest.main()
