"""Thinking (reasoning) switch: env resolution, serialization, request kwargs.

Only the OpenAI-compatible chat-completions surface is covered — there is no
per-model-family probing by design.
"""

from __future__ import annotations

import pickle

import pytest

from agentsociety2.config.config import get_llm_thinking
from agentsociety2.config.llm_dispatcher import LLMClient, ThinkingSettings

_THINKING_VARS = (
    "AGENTSOCIETY_LLM_THINKING",
    "AGENTSOCIETY_LLM_REASONING_EFFORT",
    "AGENTSOCIETY_LLM_EXTRA_BODY",
    "AGENTSOCIETY_CODER_LLM_THINKING",
    "AGENTSOCIETY_CODER_LLM_REASONING_EFFORT",
    "AGENTSOCIETY_CODER_LLM_EXTRA_BODY",
    "AGENTSOCIETY_EMBEDDING_LLM_THINKING",
)


@pytest.fixture(autouse=True)
def _clean_thinking_env(monkeypatch):
    for name in _THINKING_VARS:
        monkeypatch.delenv(name, raising=False)


def _kwargs(role: str = "default") -> dict:
    return ThinkingSettings(**get_llm_thinking(role)).request_kwargs()


# ------------------------ env resolution -------------------------


def test_unset_sends_nothing():
    """The backward-compatibility guarantee: unset env must add no parameter."""
    assert get_llm_thinking("default") == {
        "policy": "inherit",
        "reasoning_effort": None,
        "extra_body": None,
    }
    assert _kwargs() == {}
    assert _kwargs("coder") == {}


@pytest.mark.parametrize("value", ["on", "ON", "1", "true", "yes"])
def test_thinking_on_is_recognized(monkeypatch, value):
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", value)
    monkeypatch.setenv("AGENTSOCIETY_LLM_REASONING_EFFORT", "high")
    assert _kwargs() == {"reasoning_effort": "high"}


def test_thinking_on_without_effort_sends_nothing_extra(monkeypatch):
    """``on`` means "leave the model default alone" — only explicit config is sent."""
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "on")
    assert _kwargs() == {}


@pytest.mark.parametrize("value", ["off", "OFF", "0", "false", "no"])
def test_thinking_off_defaults_to_minimal(monkeypatch, value):
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", value)
    assert _kwargs() == {"reasoning_effort": "minimal"}


def test_thinking_off_honours_explicit_effort(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "off")
    monkeypatch.setenv("AGENTSOCIETY_LLM_REASONING_EFFORT", "low")
    assert _kwargs() == {"reasoning_effort": "low"}


def test_thinking_off_with_extra_body_sends_only_extra_body(monkeypatch):
    """A gateway-specific switch must not be accompanied by reasoning_effort,
    which the same gateway may reject."""
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "off")
    monkeypatch.setenv("AGENTSOCIETY_LLM_EXTRA_BODY", '{"enable_thinking": false}')
    assert _kwargs() == {"extra_body": {"enable_thinking": False}}


def test_thinking_on_can_combine_effort_and_extra_body(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "on")
    monkeypatch.setenv("AGENTSOCIETY_LLM_REASONING_EFFORT", "medium")
    monkeypatch.setenv("AGENTSOCIETY_LLM_EXTRA_BODY", '{"enable_thinking": true}')
    assert _kwargs() == {
        "reasoning_effort": "medium",
        "extra_body": {"enable_thinking": True},
    }


def test_unknown_policy_value_is_inert(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "maybe")
    assert _kwargs() == {}


@pytest.mark.parametrize("bad", ["{not json", "[1, 2]", '"a string"', "null"])
def test_malformed_extra_body_never_raises(monkeypatch, bad):
    """A bad env var must degrade to "send nothing", not abort a run."""
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "off")
    monkeypatch.setenv("AGENTSOCIETY_LLM_EXTRA_BODY", bad)
    assert _kwargs() == {"reasoning_effort": "minimal"}


# ------------------------ per-role overrides -------------------------


def test_coder_role_overrides_default(monkeypatch):
    """The split the switch exists for: agents reason, env-router codegen does not."""
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "on")
    monkeypatch.setenv("AGENTSOCIETY_LLM_REASONING_EFFORT", "high")
    monkeypatch.setenv("AGENTSOCIETY_CODER_LLM_THINKING", "off")
    monkeypatch.setenv("AGENTSOCIETY_CODER_LLM_REASONING_EFFORT", "low")
    assert _kwargs("default") == {"reasoning_effort": "high"}
    assert _kwargs("coder") == {"reasoning_effort": "low"}


def test_coder_role_falls_back_to_default_settings(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_LLM_THINKING", "off")
    monkeypatch.setenv("AGENTSOCIETY_LLM_EXTRA_BODY", '{"x": 1}')
    assert _kwargs("coder") == {"extra_body": {"x": 1}}


def test_non_coder_roles_ignore_coder_overrides(monkeypatch):
    monkeypatch.setenv("AGENTSOCIETY_CODER_LLM_THINKING", "off")
    assert _kwargs("embedding") == {}


# ------------------------ ThinkingSettings -------------------------


def test_inherit_policy_contributes_nothing_even_with_payloads():
    settings = ThinkingSettings(
        policy="inherit", reasoning_effort="high", extra_body={"x": 1}
    )
    assert settings.request_kwargs() == {}


def test_request_kwargs_returns_a_copy_of_extra_body():
    settings = ThinkingSettings(policy="off", extra_body={"x": 1})
    kwargs = settings.request_kwargs()
    kwargs["extra_body"]["x"] = 2
    assert settings.extra_body == {"x": 1}


# ------------------------ serialization (Ray boundary) -------------------------


def test_thinking_survives_pickle_round_trip():
    client = LLMClient(
        model_name="m",
        base_url="u",
        api_key="k",
        model_type="default",
        thinking=ThinkingSettings(policy="off", reasoning_effort="minimal"),
    )
    restored = pickle.loads(pickle.dumps(client))
    assert restored.thinking == ThinkingSettings(
        policy="off", reasoning_effort="minimal"
    )
    assert restored._resolve_thinking_kwargs("inherit", {})["reasoning_effort"] == (
        "minimal"
    )


def test_state_dict_without_thinking_still_loads():
    """A client pickled by an older build must not break on the new field."""
    client = LLMClient.__new__(LLMClient)
    client.__setstate__({"model_name": "m", "base_url": "u", "api_key": "k"})
    assert client.thinking == ThinkingSettings()
    assert client.thinking.request_kwargs() == {}


def test_explicit_none_thinking_normalizes_to_inert_default():
    client = LLMClient.__new__(LLMClient)
    client.__setstate__(
        {"model_name": "m", "base_url": "u", "api_key": "k", "thinking": None}
    )
    assert client._resolve_thinking_kwargs("inherit", {}) == {}


# ------------------------ merge precedence -------------------------


def _client(policy: str = "off", effort: str = "minimal") -> LLMClient:
    return LLMClient(
        model_name="m",
        base_url="u",
        api_key="k",
        thinking=ThinkingSettings(policy=policy, reasoning_effort=effort),
    )


def test_inherit_applies_the_role_settings():
    assert _client()._resolve_thinking_kwargs("inherit", {"tools": []}) == {
        "reasoning_effort": "minimal",
        "allowed_openai_params": ["reasoning_effort"],
        "tools": [],
    }


def test_per_call_off_suppresses_the_role_settings():
    assert _client()._resolve_thinking_kwargs("off", {"tools": []}) == {"tools": []}


def test_caller_kwargs_win_over_role_settings():
    assert _client()._resolve_thinking_kwargs(
        "inherit", {"reasoning_effort": "high"}
    ) == {"reasoning_effort": "high", "allowed_openai_params": ["reasoning_effort"]}


def test_client_without_thinking_sends_nothing():
    client = LLMClient(model_name="m", base_url="u", api_key="k", thinking=None)
    assert client._resolve_thinking_kwargs("inherit", {"tools": []}) == {"tools": []}


# ------------------------ litellm param allow-listing -------------------------


def test_reasoning_effort_is_allow_listed():
    """litellm's openai/ adapter rejects reasoning_effort for models outside its
    model map — i.e. any OpenAI-compatible gateway. Without this the switch
    400s on the very deployments it exists for (verified against a real
    gateway), so the parameter has to be explicitly allowed."""
    resolved = _client()._resolve_thinking_kwargs("inherit", {})
    assert resolved["reasoning_effort"] == "minimal"
    assert resolved["allowed_openai_params"] == ["reasoning_effort"]


def test_allow_list_is_absent_when_no_reasoning_param_is_sent():
    assert "allowed_openai_params" not in _client()._resolve_thinking_kwargs("off", {})
    assert "allowed_openai_params" not in _client("inherit")._resolve_thinking_kwargs(
        "inherit", {}
    )


def test_caller_allow_list_is_preserved_and_deduplicated():
    resolved = _client()._resolve_thinking_kwargs(
        "inherit", {"allowed_openai_params": ["temperature", "reasoning_effort"]}
    )
    assert resolved["allowed_openai_params"] == ["temperature", "reasoning_effort"]


def test_extra_body_only_directive_skips_the_allow_list():
    """A gateway-specific extra_body switch carries no reasoning_effort, so it
    must not gain an allow-list entry for one."""
    client = LLMClient(
        model_name="m",
        base_url="u",
        api_key="k",
        thinking=ThinkingSettings(policy="off", extra_body={"enable_thinking": False}),
    )
    resolved = client._resolve_thinking_kwargs("inherit", {})
    assert resolved == {"extra_body": {"enable_thinking": False}}
