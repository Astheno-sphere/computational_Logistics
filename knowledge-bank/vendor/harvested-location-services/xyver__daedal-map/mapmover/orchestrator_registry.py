"""Shared orchestrator registry."""

from __future__ import annotations

from mapmover.explore.orchestrator import ExploreOrchestrator
from mapmover.ops.orchestrator import OpsOrchestrator
from mapmover.research_orchestrator import ResearchOrchestrator


_ORCHESTRATOR_REGISTRY = {
    "explore": ExploreOrchestrator(),
    "research": ResearchOrchestrator(),
    "ops": OpsOrchestrator(),
}


def get_orchestrator(lane_id: str):
    """Return the shared orchestrator instance for one lane."""
    key = str(lane_id or "").strip().lower()
    try:
        return _ORCHESTRATOR_REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"Unknown orchestrator lane: {lane_id}") from exc


def list_orchestrators() -> dict[str, object]:
    """Return the shared orchestrator registry."""
    return dict(_ORCHESTRATOR_REGISTRY)
