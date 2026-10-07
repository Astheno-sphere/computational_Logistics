"""Shared orchestrator policy objects and helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeartbeatPolicy:
    stage: str
    messages: tuple[str, ...]


@dataclass(frozen=True)
class ResearchRetryPolicy:
    max_tool_iterations: int
    guardrail_start_iteration: int
    strong_guardrail_iteration: int
    rescue_prompt: str


@dataclass(frozen=True)
class OpsRefreshRetryPolicy:
    max_refresh_attempts: int
    backoff_seconds: tuple[int, ...]
    degrade_to_cached: bool = True


@dataclass(frozen=True)
class ExploreComplexityPolicy:
    max_distinct_sources: int
    handoff_message: str


EXPLORE_HEARTBEAT_POLICY = HeartbeatPolicy(
    stage="thinking",
    messages=(
        "Still working through your request...",
        "Cross-checking the catalog...",
        "Putting your order together...",
    ),
)


RESEARCH_HEARTBEAT_POLICY = HeartbeatPolicy(
    stage="thinking",
    messages=(
        "Reviewing the workspace...",
        "Scanning the loaded artifacts...",
        "Working through the analysis...",
    ),
)


OPS_HEARTBEAT_POLICY = HeartbeatPolicy(
    stage="thinking",
    messages=(
        "Reviewing the watch scope...",
        "Checking live operational context...",
        "Building the status picture...",
    ),
)


DEFAULT_RESEARCH_RETRY_POLICY = ResearchRetryPolicy(
    max_tool_iterations=8,
    guardrail_start_iteration=3,
    strong_guardrail_iteration=5,
    rescue_prompt=(
        "Write the best grounded final answer now using only the evidence already gathered above. "
        "Do not call tools. If the evidence is partial, answer the grounded part first and then "
        "name the remaining limitation clearly."
    ),
)


DEFAULT_OPS_RETRY_POLICY = OpsRefreshRetryPolicy(
    max_refresh_attempts=2,
    backoff_seconds=(3, 10),
    degrade_to_cached=True,
)


DEFAULT_EXPLORE_COMPLEXITY_POLICY = ExploreComplexityPolicy(
    max_distinct_sources=2,
    handoff_message=(
        "Try simplifying the question so Explore can stay focused on one source or a "
        "straightforward two-source overlay. If you want the broader multi-source "
        "version, switch to Research mode."
    ),
)


def build_heartbeat_event(*, idle_count: int, policy: HeartbeatPolicy, progress_event_cls):
    message = policy.messages[idle_count % len(policy.messages)]
    return progress_event_cls(stage=policy.stage, message=message, extra={"heartbeat": True})
