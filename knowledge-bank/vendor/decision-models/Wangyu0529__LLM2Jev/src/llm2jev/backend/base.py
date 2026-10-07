from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from ..core.response import Usage
from ..utils.probability import validate_probabilities

if TYPE_CHECKING:
    from ..inference.prompt import ChatPrompt


@dataclass(frozen=True, slots=True, kw_only=True)
class BinaryBackendOutput:
    """Ordered yes probabilities and usage returned by a binary backend."""

    yes_probabilities: Sequence[float]
    usage: Usage = field(default_factory=Usage)

    def __post_init__(self) -> None:
        probabilities = validate_probabilities(self.yes_probabilities)
        if not isinstance(self.usage, Usage):
            raise ValueError("usage must be a Usage instance")
        object.__setattr__(self, "yes_probabilities", probabilities)


class BinaryBackend(Protocol):
    """Batch scorer that returns one P(yes) for each rendered prompt."""

    def score(
        self,
        *,
        model: str,
        prompts: Sequence[ChatPrompt],
    ) -> BinaryBackendOutput:
        """Score prompts in input order without generating text."""
