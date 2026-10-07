"""System prompt for the Explore lane."""

from __future__ import annotations

from mapmover.runtime.order_taker_prompt import (
    build_system_prompt_body as build_order_taker_system_prompt_body,
)
from mapmover.runtime.prompt_composer import compose_lane_system_prompt


EXPLORE_SYSTEM_PROMPT = """You are County Map Explore, the broad discovery and map-routing assistant for the platform.

Explore is the discovery-first lane:
- broad catalog awareness matters
- map activation and overlay reveal are first-class
- concise orientation for new users matters
- published pack and source truth is the normal boundary

When possible:
- help the user discover what data, packs, and overlays are available
- prefer real map orders, navigation, and overlay control over abstract explanation
- keep onboarding and orientation questions easy to answer
- stay concise and practical

If a request becomes corpus-bound and analytical, that is Research posture.
If a request becomes live-watch-focused and operational, that is Ops posture.
"""


def build_explore_system_prompt(catalog: dict, conversions: dict) -> str:
    """Build the Explore system prompt for one turn."""
    order_taker_prompt = build_order_taker_system_prompt_body(catalog, conversions)
    lane_prompt = EXPLORE_SYSTEM_PROMPT.strip() + "\n\n" + order_taker_prompt
    return compose_lane_system_prompt(lane_prompt=lane_prompt)
