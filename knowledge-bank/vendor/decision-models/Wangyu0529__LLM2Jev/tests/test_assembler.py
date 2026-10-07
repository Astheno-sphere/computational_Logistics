import unittest

from llm2jev import (
    Choice,
    ChoiceAnswer,
    JevRequest,
    Noul,
    NoulAnswer,
    Score,
    ScoreAnswer,
    Usage,
    assemble_response,
    compile_binary_questions,
)


class AssembleResponseTests(unittest.TestCase):
    def test_assembles_mixed_response(self) -> None:
        request = JevRequest(
            state="Customer requests a refund for a duplicate charge.",
            model="jev-latest",
            questions={
                "department": Choice(
                    criteria={"billing": None, "returns": None, "shipping": None},
                ),
                "severity": Score(criteria=["Low", "Medium", "High"]),
                "refund": Noul(),
                "explicit_refund": Noul(
                    criteria={"true": "Refund requested", "false": "No refund requested"},
                ),
            },
        )
        tasks = compile_binary_questions(request)

        response = assemble_response(
            request=request,
            tasks=tasks,
            yes_probabilities=[0.6, 0.2, 0.2, 0.0, 0.76, 0.24, 0.91, 0.8, 0.2],
            usage=Usage(input_tokens=120, output_tokens=0),
        )

        department = response.answers["department"]
        self.assertIsInstance(department, ChoiceAnswer)
        self.assertEqual(department.choice, "billing")  # type: ignore[union-attr]
        self.assertAlmostEqual(department.confidence, 0.4)  # type: ignore[union-attr]

        severity = response.answers["severity"]
        self.assertIsInstance(severity, ScoreAnswer)
        self.assertAlmostEqual(severity.score, 1.24)  # type: ignore[union-attr]
        self.assertAlmostEqual(severity.confidence, 0.64)  # type: ignore[union-attr]

        self.assertEqual(response.answers["refund"], NoulAnswer(noul=0.91))
        self.assertEqual(response.answers["explicit_refund"], NoulAnswer(noul=0.8))
        self.assertEqual(response.usage, Usage(input_tokens=120, output_tokens=0))

    def test_normalizes_independent_choice_probabilities(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"tone": Choice(criteria={"calm": None, "angry": None})},
        )
        tasks = compile_binary_questions(request)

        response = assemble_response(
            request=request,
            tasks=tasks,
            yes_probabilities=[0.9, 0.3],
        )

        answer = response.answers["tone"]
        self.assertIsInstance(answer, ChoiceAnswer)
        self.assertEqual(answer.probabilities, {"calm": 0.75, "angry": 0.25})  # type: ignore[union-attr]
        self.assertEqual(response.usage, Usage())

    def test_all_zero_candidates_become_uniform(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"severity": Score(criteria=["Low", "Medium", "High"])},
        )
        tasks = compile_binary_questions(request)

        response = assemble_response(
            request=request,
            tasks=tasks,
            yes_probabilities=[0.0, 0.0, 0.0],
        )

        answer = response.answers["severity"]
        self.assertIsInstance(answer, ScoreAnswer)
        self.assertAlmostEqual(answer.score, 1.0)  # type: ignore[union-attr]
        self.assertAlmostEqual(answer.confidence, 0.0)  # type: ignore[union-attr]

    def test_uses_custom_normalizer(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"tone": Choice(criteria={"calm": None, "angry": None})},
        )
        tasks = compile_binary_questions(request)

        response = assemble_response(
            request=request,
            tasks=tasks,
            yes_probabilities=[0.9, 0.1],
            normalizer=lambda _: (0.6, 0.4),
        )

        answer = response.answers["tone"]
        self.assertIsInstance(answer, ChoiceAnswer)
        self.assertEqual(answer.probabilities, {"calm": 0.6, "angry": 0.4})  # type: ignore[union-attr]

    def test_rejects_task_mismatch(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"tone": Choice(criteria={"calm": None, "angry": None})},
        )
        tasks = tuple(reversed(compile_binary_questions(request)))

        with self.assertRaises(ValueError):
            assemble_response(
                request=request,
                tasks=tasks,
                yes_probabilities=[0.5, 0.5],
            )

    def test_rejects_probability_count_mismatch(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"check": Noul()},
        )

        with self.assertRaises(ValueError):
            assemble_response(
                request=request,
                tasks=compile_binary_questions(request),
                yes_probabilities=[],
            )

    def test_rejects_invalid_normalizer_output(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"tone": Choice(criteria={"calm": None, "angry": None})},
        )
        tasks = compile_binary_questions(request)

        with self.assertRaises(ValueError):
            assemble_response(
                request=request,
                tasks=tasks,
                yes_probabilities=[0.5, 0.5],
                normalizer=lambda _: (1.0,),
            )

    def test_rejects_single_choice_candidate(self) -> None:
        request = JevRequest(
            state="message",
            model="jev-latest",
            questions={"only": Choice(criteria={"one": None})},
        )

        with self.assertRaises(ValueError):
            assemble_response(
                request=request,
                tasks=compile_binary_questions(request),
                yes_probabilities=[0.8],
            )


if __name__ == "__main__":
    unittest.main()
