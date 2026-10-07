"""Shared prompt-runtime helpers."""

from __future__ import annotations


def build_cached_system_prompt_blocks(prompt_text: str) -> list[dict]:
    text = str(prompt_text or "").strip()
    if not text:
        return []
    return [{
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }]
