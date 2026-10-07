from __future__ import annotations

from dataclasses import dataclass, field

from ..backend.base import BinaryBackend
from ..core.request import JevRequest
from ..core.response import JevResponse
from .assembler import Normalizer, assemble_response
from .binary import compile_binary_questions
from .normalization import normalize_l1
from .prompt import DefaultPromptRenderer, PromptRenderer


@dataclass(slots=True, kw_only=True)
class LLM2Jev:
    """Compile, score, and assemble Jev requests."""

    backend: BinaryBackend
    renderer: PromptRenderer = field(default_factory=DefaultPromptRenderer)
    normalizer: Normalizer = normalize_l1

    def evaluate(self, request: JevRequest) -> JevResponse:
        tasks = compile_binary_questions(request)
        prompts = tuple(self.renderer.render(task) for task in tasks)
        output = self.backend.score(model=request.model, prompts=prompts)
        return assemble_response(
            request=request,
            tasks=tasks,
            yes_probabilities=output.yes_probabilities,
            usage=output.usage,
            normalizer=self.normalizer,
        )
