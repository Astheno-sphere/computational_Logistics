"""Shared lane-owned LLM selection helpers.

Model/provider choice should live at the orchestrator boundary, not inside
individual lane internals. This module resolves the default selection for one
lane and leaves room for future per-user overrides.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Mapping


@dataclass(frozen=True)
class LLMSelection:
    provider: str
    model: str
    temperature: float


_DEFAULT_SELECTIONS: dict[str, tuple[str, str, float]] = {
    "explore_fast_haiku_default": ("anthropic", "claude-haiku-4-5-20251001", 0.0),
    "research_deep_sonnet_opus_default": ("anthropic", "claude-sonnet-4-6", 0.1),
    "ops_fast_haiku_default": ("anthropic", "claude-haiku-4-5-20251001", 0.0),
    "ops_balanced_sonnet_default": ("anthropic", "claude-sonnet-4-6", 0.1),
}

_ENV_PREFIX_BY_POLICY: dict[str, str] = {
    "explore_fast_haiku_default": "EXPLORE",
    "research_deep_sonnet_opus_default": "RESEARCH",
    "ops_fast_haiku_default": "OPS",
    "ops_balanced_sonnet_default": "OPS",
}


def _env_text(
    env: Mapping[str, str],
    *names: str,
    default: str,
) -> str:
    for name in names:
        value = str(env.get(name, "") or "").strip()
        if value:
            return value
    return default


def _env_float(
    env: Mapping[str, str],
    *names: str,
    default: float,
) -> float:
    for name in names:
        raw = str(env.get(name, "") or "").strip()
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return default


def resolve_lane_llm_selection(
    model_policy: str,
    *,
    override: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> LLMSelection:
    """Resolve provider/model/temperature for one orchestrator model policy."""
    policy_key = str(model_policy or "").strip()
    if policy_key not in _DEFAULT_SELECTIONS:
        raise KeyError(f"Unknown orchestrator model policy: {model_policy}")

    default_provider, default_model, default_temperature = _DEFAULT_SELECTIONS[policy_key]
    prefix = _ENV_PREFIX_BY_POLICY[policy_key]
    source_env = env or os.environ

    provider = _env_text(
        source_env,
        f"{prefix}_LLM_PROVIDER",
        "DEFAULT_LLM_PROVIDER",
        default=default_provider,
    ).lower()
    model = _env_text(
        source_env,
        f"{prefix}_MODEL",
        "DEFAULT_LLM_MODEL",
        "ORDER_TAKER_MODEL" if prefix == "EXPLORE" else "",
        default=default_model,
    )
    temperature = _env_float(
        source_env,
        f"{prefix}_TEMPERATURE",
        "DEFAULT_LLM_TEMPERATURE",
        "ORDER_TAKER_TEMPERATURE" if prefix == "EXPLORE" else "",
        default=default_temperature,
    )

    if override:
        override_provider = str(override.get("provider") or "").strip().lower()
        override_model = str(override.get("model") or "").strip()
        override_temperature = override.get("temperature")
        if override_provider:
            provider = override_provider
        if override_model:
            model = override_model
        if override_temperature is not None:
            try:
                temperature = float(override_temperature)
            except (TypeError, ValueError):
                pass

    return LLMSelection(
        provider=provider,
        model=model,
        temperature=temperature,
    )


# Models that reject non-default sampling parameters (temperature / top_p /
# top_k) with a 400. Matched as substrings against the resolved model id, so
# both the bare alias and any dated variant are covered.
#
# Anything not listed here still accepts temperature: Haiku 4.5, Sonnet 4.6,
# Opus 4.6, and older models. Add a marker when adopting a newer model rather
# than special-casing the call site.
_NO_SAMPLING_MODEL_MARKERS: tuple[str, ...] = (
    "opus-4-7",
    "opus-4-8",
    "opus-5",
    "sonnet-5",
    "fable-5",
    "mythos-5",
)


def model_rejects_sampling(model: str) -> bool:
    """True when this model 400s on temperature/top_p/top_k."""
    normalized = str(model or "").lower()
    return any(marker in normalized for marker in _NO_SAMPLING_MODEL_MARKERS)


def sampling_kwargs(model: str, temperature: float) -> dict:
    """Return the sampling kwargs to splat into messages.create() for a model.

    Empty for models that reject sampling parameters, so one call site works
    across model generations without the lane knowing which is which.
    """
    if model_rejects_sampling(model):
        return {}
    return {"temperature": temperature}


def build_provider_client(selection: LLMSelection):
    """Return the provider client for this selection.

    Only Anthropic is wired today, but the selection object is provider-aware so
    future user/provider preference work has one shared entry point.
    """
    provider = str(selection.provider or "").strip().lower()
    if provider == "anthropic":
        from anthropic import Anthropic

        return Anthropic()
    raise ValueError(f"Unsupported LLM provider: {selection.provider}")


def build_provider_runtime_context(
    *,
    model_policy: str | None = None,
    selection: LLMSelection | None = None,
    override: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the normalized provider runtime context for one lane call."""
    resolved = selection or resolve_lane_llm_selection(
        str(model_policy or "").strip(),
        override=override,
        env=env,
    )
    return {
        "llm_selection": resolved,
        "client": build_provider_client(resolved),
        "model": resolved.model,
        "temperature": resolved.temperature,
    }
