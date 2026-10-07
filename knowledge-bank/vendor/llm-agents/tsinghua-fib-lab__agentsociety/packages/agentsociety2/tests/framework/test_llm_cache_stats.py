"""Prompt-cache hit accounting: usage parsing, merging, and aggregation.

Gateways disagree on where the cache-hit count lands in ``usage``, so the
extraction has to tolerate every shape we have seen and never raise on the hot
path. The merge has to stay compatible across a mixed-version Ray cluster.
"""

from __future__ import annotations

import pytest

from agentsociety2.config.llm_dispatcher import (
    cache_hit_rate,
    extract_cached_tokens,
    merge_token_stats,
)


class _Obj:
    """Stand-in for litellm's pydantic-style usage objects."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


class _Response:
    def __init__(self, usage):
        self.usage = usage


# ------------------------ extraction -------------------------


def test_reads_canonical_prompt_tokens_details():
    response = _Response(_Obj(prompt_tokens_details=_Obj(cached_tokens=1200)))
    assert extract_cached_tokens(response) == 1200


def test_reads_dict_shaped_usage():
    """Gateways that bypass litellm's normalization hand back plain dicts."""
    response = _Response({"prompt_tokens_details": {"cached_tokens": 33}})
    assert extract_cached_tokens(response) == 33


@pytest.mark.parametrize(
    "field",
    ["cached_tokens", "prompt_cache_hit_tokens", "cache_read_input_tokens"],
)
def test_reads_top_level_fallbacks(field):
    assert extract_cached_tokens(_Response(_Obj(**{field: 7}))) == 7


def test_canonical_shape_wins_over_fallbacks():
    response = _Response(
        _Obj(
            prompt_tokens_details=_Obj(cached_tokens=100),
            prompt_cache_hit_tokens=999,
        )
    )
    assert extract_cached_tokens(response) == 100


@pytest.mark.parametrize(
    "response",
    [
        None,
        _Response(None),
        _Response(_Obj()),
        _Response(_Obj(cached_tokens=0)),
        _Response(_Obj(cached_tokens="not-a-number")),
        _Response(_Obj(prompt_tokens_details=None)),
    ],
)
def test_missing_or_unusable_usage_yields_zero(response):
    """Called for every completion — it must never raise."""
    assert extract_cached_tokens(response) == 0


# ------------------------ client-level recording -------------------------


def test_record_tokens_tracks_cached_input():
    from agentsociety2.config.llm_dispatcher import LLMClient

    client = LLMClient(model_name="m", base_url="u", api_key="k")
    response = _Response(
        _Obj(
            prompt_tokens=100,
            completion_tokens=20,
            prompt_tokens_details=_Obj(cached_tokens=64),
        )
    )
    client._record_tokens("m", response)
    client._record_tokens("m", response)

    stats = client.take_token_stats()
    assert stats["m"] == {
        "calls": 2,
        "input": 200,
        "output": 40,
        "cached_input": 128,
    }
    assert cache_hit_rate(stats) == pytest.approx(0.64)


def test_record_tokens_ignores_usage_less_responses():
    from agentsociety2.config.llm_dispatcher import LLMClient

    client = LLMClient(model_name="m", base_url="u", api_key="k")
    client._record_tokens("m", _Response(None))
    assert client.take_token_stats() == {}


def test_take_token_stats_clears_the_delta():
    from agentsociety2.config.llm_dispatcher import LLMClient

    client = LLMClient(model_name="m", base_url="u", api_key="k")
    client._record_tokens("m", _Response(_Obj(prompt_tokens=5, completion_tokens=1)))
    assert client.take_token_stats()["m"]["calls"] == 1
    assert client.take_token_stats() == {}


# ------------------------ merge compatibility -------------------------


def test_merge_accumulates_cached_input():
    merged = merge_token_stats(
        {"m": {"calls": 1, "input": 10, "output": 2, "cached_input": 8}},
        {"m": {"calls": 1, "input": 10, "output": 2, "cached_input": 4}},
    )
    assert merged == {"m": {"calls": 2, "input": 20, "output": 4, "cached_input": 12}}


def test_merge_accepts_old_shape_delta():
    """A delta from a build without the cached counter must still merge."""
    merged = merge_token_stats({"m": {"calls": 1, "input": 10, "output": 2}})
    assert merged["m"]["cached_input"] == 0
    assert merged["m"]["input"] == 10


def test_merge_mixes_old_and_new_shape_deltas():
    merged = merge_token_stats(
        {"m": {"calls": 1, "input": 10, "output": 2}},
        {"m": {"calls": 1, "input": 10, "output": 2, "cached_input": 6}},
    )
    assert merged["m"] == {"calls": 2, "input": 20, "output": 4, "cached_input": 6}


def test_merge_keeps_models_separate():
    merged = merge_token_stats(
        {"a": {"calls": 1, "input": 1, "output": 1, "cached_input": 1}},
        {"b": {"calls": 1, "input": 2, "output": 2, "cached_input": 0}},
    )
    assert set(merged) == {"a", "b"}


# ------------------------ aggregation -------------------------


def test_cache_hit_rate_is_cached_over_input():
    assert cache_hit_rate({"m": {"input": 100, "cached_input": 18}}) == pytest.approx(
        0.18
    )


def test_cache_hit_rate_aggregates_across_models():
    rate = cache_hit_rate(
        {
            "a": {"input": 50, "cached_input": 50},
            "b": {"input": 50, "cached_input": 0},
        }
    )
    assert rate == pytest.approx(0.5)


def test_cache_hit_rate_is_clamped():
    """Anthropic-shaped usage reports prompt_tokens excluding cache reads."""
    assert cache_hit_rate({"m": {"input": 100, "cached_input": 300}}) == 1.0


@pytest.mark.parametrize("stats", [{}, {"m": {}}, {"m": {"input": 0}}])
def test_cache_hit_rate_without_input_is_zero(stats):
    assert cache_hit_rate(stats) == 0.0


def test_cache_hit_rate_accepts_old_shape_stats():
    assert cache_hit_rate({"m": {"input": 100, "output": 5}}) == 0.0
