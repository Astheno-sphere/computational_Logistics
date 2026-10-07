from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

from .questions import Choice, Noul, Score
from ..utils.json import is_json_content
from .types import State
from .multimodal import validate_multimodal


Question: TypeAlias = Choice | Score | Noul


@dataclass(frozen=True, slots=True, kw_only=True)
class JevRequest:
    """A collection of questions about shared state for a specific model."""

    state: State
    model: str
    questions: Mapping[str, Question]

    def __post_init__(self) -> None:
        if not is_json_content(self.state):
            raise ValueError("state must be a string, JSON object, or JSON array")
        validate_multimodal(self.state)
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")

        questions = dict(self.questions)
        if not questions:
            raise ValueError("questions must contain at least one question")
        if any(not isinstance(question_id, str) or not question_id for question_id in questions):
            raise ValueError("question IDs must be non-empty strings")
        if any(not isinstance(question, (Choice, Score, Noul)) for question in questions.values()):
            raise ValueError("questions must contain Choice, Score, or Noul instances")
        object.__setattr__(self, "questions", questions)

    def to_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "model": self.model,
            "questions": {
                question_id: question.to_dict()
                for question_id, question in self.questions.items()
            },
        }
