from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import TypeAlias

from ..core.answers import Answer, ChoiceAnswer, NoulAnswer, ScoreAnswer
from ..core.questions import Choice, Noul, Score
from ..core.request import JevRequest
from ..core.response import JevResponse, Usage
from ..utils.probability import validate_probabilities
from .binary import BinaryQuestion, compile_binary_questions
from .normalization import normalize_l1


Normalizer: TypeAlias = Callable[[Sequence[float]], Sequence[float]]


def _normalize(
    probabilities: Sequence[float],
    normalizer: Normalizer,
) -> tuple[float, ...]:
    normalized = validate_probabilities(tuple(normalizer(probabilities)))
    if len(normalized) != len(probabilities):
        raise ValueError("normalizer must preserve the number of probabilities")
    if not math.isclose(math.fsum(normalized), 1.0, abs_tol=1e-6):
        raise ValueError("normalized probabilities must sum to 1")
    return normalized


def _confidence(probabilities: Sequence[float]) -> float:
    count = len(probabilities)
    if count < 2:
        raise ValueError("confidence requires at least two candidates")
    confidence = (count * max(probabilities) - 1) / (count - 1)
    return min(1.0, max(0.0, confidence))


def assemble_response(
    *,
    request: JevRequest,
    tasks: Sequence[BinaryQuestion],
    yes_probabilities: Sequence[float],
    usage: Usage | None = None,
    normalizer: Normalizer = normalize_l1,
) -> JevResponse:
    """Assemble binary yes probabilities into a Jev response."""

    task_values = tuple(tasks)
    expected_tasks = compile_binary_questions(request)
    if task_values != expected_tasks:
        raise ValueError("tasks must exactly match the compiled request")

    raw_probabilities = validate_probabilities(yes_probabilities)
    if len(raw_probabilities) != len(task_values):
        raise ValueError("each binary task must have exactly one yes probability")

    grouped: dict[str, list[tuple[BinaryQuestion, float]]] = {
        question_id: [] for question_id in request.questions
    }
    for task, probability in zip(task_values, raw_probabilities):
        grouped[task.question_id].append((task, probability))

    answers: dict[str, Answer] = {}
    for question_id, question in request.questions.items():
        task_probabilities = grouped[question_id]
        candidates = [task.candidate for task, _ in task_probabilities]
        raw = [probability for _, probability in task_probabilities]

        if isinstance(question, Choice):
            if len(candidates) < 2:
                raise ValueError("choice answers require at least two candidates")
            probabilities = _normalize(raw, normalizer)
            labels = list(question.criteria)
            by_label = dict(zip(labels, probabilities))
            choice = max(labels, key=by_label.__getitem__)
            answers[question_id] = ChoiceAnswer(
                choice=choice,
                confidence=_confidence(probabilities),
                probabilities=by_label,
            )
        elif isinstance(question, Score):
            probabilities = _normalize(raw, normalizer)
            by_level = dict(enumerate(probabilities))
            score = math.fsum(level * probability for level, probability in by_level.items())
            answers[question_id] = ScoreAnswer(
                score=score,
                confidence=_confidence(probabilities),
                legend=dict(enumerate(question.criteria)),
                probabilities=by_level,
            )
        elif isinstance(question, Noul):
            if question.criteria:
                probabilities = _normalize(raw, normalizer)
                by_candidate = dict(zip(candidates, probabilities))
                answers[question_id] = NoulAnswer(noul=by_candidate["true"])
            else:
                answers[question_id] = NoulAnswer(noul=raw[0])
        else:
            raise TypeError(f"unsupported question type: {type(question).__name__}")

    return JevResponse(
        model=request.model,
        answers=answers,
        usage=usage if usage is not None else Usage(),
    )
