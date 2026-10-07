"""Shared default warning-policy objects for lane orchestrators."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricWarningPolicy:
    threshold: int
    lane: str
    suggested_narrowing: tuple[str, ...]
    measure: str = "metric_count"
    fallback_strategy: str = "warn_then_override"
    override_allowed: bool = True


@dataclass(frozen=True)
class DisplayWarningPolicy:
    soft_cap: int
    hard_cap: int
    lane: str
    soft_narrowing: tuple[str, ...]
    hard_narrowing: tuple[str, ...]
    measure: str = "display_features"
    fallback_strategy: str = "warn_then_override"
    override_allowed: bool = True


DEFAULT_METRIC_WARNING_POLICY = MetricWarningPolicy(
    threshold=15,
    lane="human_web_metrics",
    suggested_narrowing=("choose a few metrics", "split by topic", "display one metric at a time"),
)


DEFAULT_DISPLAY_WARNING_POLICY = DisplayWarningPolicy(
    soft_cap=5000,
    hard_cap=10000,
    lane="human_web_display",
    soft_narrowing=("choose a smaller area", "ask for a top 100 subset", "focus on one state or county"),
    hard_narrowing=("choose a smaller area", "ask for a top 100 subset", "focus on one state or county"),
)
