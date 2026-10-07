"""Canonical Explore preprocessing adapter for local evaluation clients.

The browser route calls :class:`ExploreOrchestrator` before invoking the
order-taker.  Local MCP evaluations need the same compiled model context, not
an independently maintained approximation of the preprocessor.

This module deliberately stops before order interpretation and response
postprocessing.  MCP clients return prose after executing their own tools,
while the app postprocessor consumes a structured Explore order.  Keeping that
boundary explicit prevents the evaluator from claiming browser-response
parity it does not have.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .orchestrator import ExploreOrchestrator
from .explore_request_context import apply_selected_popup_override
from ..runtime.preprocessor_context_runtime import build_tier3_context, build_tier4_context


DEFAULT_EVALUATION_CONTEXT = {
    "viewport": {"west": -180, "south": -85, "east": 180, "north": 85, "zoom": 1},
    "active_overlays": {},
    "cache_stats": {},
    "saved_order_names": [],
    "time_state": None,
    "loaded_data": [],
    "resolved_location": None,
    "selected_popup": None,
}

_CONTRACT_SOURCES = (
    Path(__file__),
    Path(__file__).with_name("orchestrator.py"),
    Path(__file__).with_name("explore_runtime.py"),
    Path(__file__).with_name("explore_request_context.py"),
    Path(__file__).with_name("preprocessor_runtime.py"),
    Path(__file__).parents[1] / "runtime" / "preprocessor_context_runtime.py",
    Path(__file__).parents[1] / "preprocessor_context.py",
)
_CONTRACT_TREES = (
    Path(__file__).parent,
    Path(__file__).parents[1] / "runtime",
)


def _tree_sha256(root: Path) -> str:
    """Hash relevant runtime code as one deterministic evidence dependency."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def explore_evaluation_contract() -> dict[str, Any]:
    """Return versioned, hashable provenance for the reused runtime path."""
    sources = []
    for path in _CONTRACT_SOURCES:
        if not path.exists():
            continue
        sources.append({
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    return {
        "contract": "explore_runtime_preprocessor_context_v1",
        "response_postprocessor_executed": False,
        "sources": sources,
        # The adapter executes these live modules, not a copied implementation.
        # Tree hashes make a prior evidence file stale whenever a supporting
        # Explore/runtime helper changes, including a new helper that was not
        # manually added to _CONTRACT_SOURCES.
        "runtime_trees": [
            {"path": str(root), "sha256": _tree_sha256(root)}
            for root in _CONTRACT_TREES
        ],
    }


def build_explore_evaluation_context(
    query: str,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compile the exact preprocessor context supplied to the Explore LLM.

    ``request_context`` mirrors the browser request fields.  Evaluation callers
    normally omit it and receive a stable world-view fixture; suites that need
    viewport, active-overlay, or selected-popup behavior can provide only the
    fields they need to override.
    """
    context = dict(DEFAULT_EVALUATION_CONTEXT)
    if request_context:
        for key in context:
            if key in request_context:
                context[key] = request_context[key]

    hints = ExploreOrchestrator().preprocess(
        query=query,
        viewport=context["viewport"],
        active_overlays=context["active_overlays"],
        cache_stats=context["cache_stats"],
        saved_order_names=context["saved_order_names"],
        time_state=context["time_state"],
        loaded_data=context["loaded_data"],
        resolved_location=context["resolved_location"],
        selected_popup=context["selected_popup"],
    )
    # The route applies this override immediately after orchestration. Mirror
    # that final request-preparation step so selected-popup suites receive the
    # same location/event context as the browser request.
    if context["selected_popup"]:
        hints = apply_selected_popup_override(hints, context["selected_popup"])
    tier3 = build_tier3_context(hints)
    tier4 = build_tier4_context(hints)
    model_context = "\n".join(part for part in (tier3, tier4) if part).strip()
    return {
        "contract": explore_evaluation_contract()["contract"],
        "request_context": context,
        "model_context": model_context,
        "model_context_sha256": hashlib.sha256(model_context.encode("utf-8")).hexdigest(),
    }
