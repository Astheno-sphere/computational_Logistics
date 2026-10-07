"""Shared orchestrator spec registry for chat lanes."""

from __future__ import annotations

from dataclasses import dataclass

from mapmover.runtime.orchestrator_policy import (
    DEFAULT_OPS_RETRY_POLICY,
    DEFAULT_RESEARCH_RETRY_POLICY,
    EXPLORE_HEARTBEAT_POLICY,
    OPS_HEARTBEAT_POLICY,
    RESEARCH_HEARTBEAT_POLICY,
)
from mapmover.runtime.warning_policy import DEFAULT_DISPLAY_WARNING_POLICY


@dataclass(frozen=True)
class OrchestratorSpec:
    """Declarative lane configuration for one orchestrator."""

    lane_id: str
    orchestrator_class: str
    prompt_provider: str
    preload_provider: str
    model_policy: str
    helper_policy: str
    tool_policy: str
    discovery_scope: str
    history_policy: str
    warning_policy: str
    retry_policy: str
    display_policy: str
    heartbeat_policy_obj: object | None = None
    display_warning_policy_obj: object | None = None
    retry_policy_obj: object | None = None


EXPLORE_ORCHESTRATOR_SPEC = OrchestratorSpec(
    lane_id="explore",
    orchestrator_class="ExploreOrchestrator",
    prompt_provider="ExploreOrchestrator.build_system_prompt",
    preload_provider="explore.preprocess_explore_request",
    model_policy="explore_fast_haiku_default",
    helper_policy="runtime_shared_helpers_standard",
    tool_policy="explore_order_taker_minimal",
    discovery_scope="whole_catalog_published_or_selected_surface",
    history_policy="chat_history_default",
    warning_policy="explore_execute_when_feasible",
    retry_policy="explore_event_aggregate_fallback",
    display_policy="map_first",
    heartbeat_policy_obj=EXPLORE_HEARTBEAT_POLICY,
    display_warning_policy_obj=DEFAULT_DISPLAY_WARNING_POLICY,
)


RESEARCH_ORCHESTRATOR_SPEC = OrchestratorSpec(
    lane_id="research",
    orchestrator_class="ResearchOrchestrator",
    prompt_provider="ResearchOrchestrator.build_system_prompt",
    preload_provider="research.corpus_manifest_and_memory",
    model_policy="research_deep_sonnet_opus_default",
    helper_policy="runtime_shared_helpers_plus_research_tools",
    tool_policy="research_tool_loop_enabled",
    discovery_scope="active_corpus_workspace",
    history_policy="research_history_with_compacted_memory",
    warning_policy="research_analysis_and_display_warning",
    retry_policy="research_tool_guardrail_and_rescue",
    display_policy="analysis_first_map_capable",
    heartbeat_policy_obj=RESEARCH_HEARTBEAT_POLICY,
    display_warning_policy_obj=DEFAULT_DISPLAY_WARNING_POLICY,
    retry_policy_obj=DEFAULT_RESEARCH_RETRY_POLICY,
)


OPS_ORCHESTRATOR_SPEC = OrchestratorSpec(
    lane_id="ops",
    orchestrator_class="OpsOrchestrator",
    prompt_provider="OpsOrchestrator.build_system_prompt",
    preload_provider="ops.preload_ops_watch_scope",
    model_policy="ops_fast_haiku_default",
    helper_policy="runtime_shared_helpers_live_watch",
    tool_policy="ops_watch_and_triage_tools",
    discovery_scope="live_watch_scope",
    history_policy="ops_short_focus_history",
    warning_policy="ops_direct_triage_warning",
    retry_policy="ops_live_refresh_retry",
    display_policy="watch_first",
    heartbeat_policy_obj=OPS_HEARTBEAT_POLICY,
    display_warning_policy_obj=DEFAULT_DISPLAY_WARNING_POLICY,
    retry_policy_obj=DEFAULT_OPS_RETRY_POLICY,
)


ORCHESTRATOR_SPECS = {
    EXPLORE_ORCHESTRATOR_SPEC.lane_id: EXPLORE_ORCHESTRATOR_SPEC,
    RESEARCH_ORCHESTRATOR_SPEC.lane_id: RESEARCH_ORCHESTRATOR_SPEC,
    OPS_ORCHESTRATOR_SPEC.lane_id: OPS_ORCHESTRATOR_SPEC,
}


def get_orchestrator_spec(lane_id: str) -> OrchestratorSpec:
    """Return the declared spec for one lane."""
    key = str(lane_id or "").strip().lower()
    try:
        return ORCHESTRATOR_SPECS[key]
    except KeyError as exc:
        raise KeyError(f"Unknown orchestrator lane: {lane_id}") from exc


def list_orchestrator_specs() -> dict[str, OrchestratorSpec]:
    """Return the full orchestrator spec registry."""
    return dict(ORCHESTRATOR_SPECS)
