"""Shared helpers for composing lane system prompts."""

from __future__ import annotations

from mapmover.runtime.shared_prompt_rules import build_shared_prompt_rules


def compose_lane_system_prompt(*, lane_prompt: str, turn_context_blocks: list[str] | None = None) -> str:
    """Compose shared rules, lane doctrine, and optional turn context."""
    parts = [build_shared_prompt_rules(), str(lane_prompt or "").strip()]
    for block in turn_context_blocks or []:
        text = str(block or "").strip()
        if text:
            parts.append(text)
    return "\n\n".join(part for part in parts if part).strip()
