from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mapmover.runtime.llm_policy import model_rejects_sampling, sampling_kwargs
from mapmover.research_chat_helpers import _temperature_kwargs


@pytest.mark.parametrize("model", [
    "claude-sonnet-5",
    "claude-sonnet-5-20260601",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-opus-5",
    "claude-fable-5-1",
    "claude-mythos-5",
])
def test_new_sampling_restricted_models_omit_temperature(model: str) -> None:
    assert model_rejects_sampling(model)
    assert sampling_kwargs(model, 0.1) == {}


@pytest.mark.parametrize("model", [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-5",
    "claude-opus-4-6",
])
def test_existing_sampling_models_keep_temperature(model: str) -> None:
    assert not model_rejects_sampling(model)
    assert sampling_kwargs(model, 0.1) == {"temperature": 0.1}


def test_research_compatibility_alias_delegates_to_shared_policy() -> None:
    assert _temperature_kwargs("claude-sonnet-5", 0.1) == {}
    assert _temperature_kwargs("claude-sonnet-4-6", 0.1) == {"temperature": 0.1}


def test_production_messages_calls_do_not_pass_temperature_directly() -> None:
    """Keep future model switches behind the shared capability policy."""
    mapmover_root = Path(__file__).resolve().parents[1] / "mapmover"
    offenders: list[str] = []
    for path in mapmover_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and func.attr == "create"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "messages"
            ):
                continue
            if any(keyword.arg == "temperature" for keyword in node.keywords):
                offenders.append(f"{path.relative_to(mapmover_root)}:{node.lineno}")
    assert offenders == []
