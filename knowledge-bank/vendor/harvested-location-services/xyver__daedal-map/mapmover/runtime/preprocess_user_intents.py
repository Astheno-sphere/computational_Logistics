"""Shared query normalization and UI-intent preprocessing helpers."""

from __future__ import annotations

import re
from typing import Optional


def normalize_query_for_location_matching(query: str) -> str:
    """Normalize query text to improve location matching."""
    query = re.sub(r"'s\b", "", query)
    query = query.replace("'", " ")
    query = re.sub(
        r"\b(\w+?)s\s+(population|gdp|economy|data|capital|government|president|leader)",
        r"\1 \2",
        query,
        flags=re.IGNORECASE,
    )
    return query


def detect_tutorial_mode_intent(query: str) -> Optional[dict]:
    """Detect tutorial mode on/off/toggle commands before the LLM call."""
    query_lower = (query or "").strip().lower()
    if not query_lower:
        return None

    has_tutorial = "tutorial" in query_lower
    has_ui_help = "help me understand the ui" in query_lower or "show me what everything does" in query_lower
    if not has_tutorial and not has_ui_help:
        return None

    if re.search(r"\b(turn|switch|set|make)\s+(the\s+)?tutorial(\s+mode)?\s+(off|disable|disabled)\b", query_lower):
        return {"action": "off"}
    if re.search(r"\b(turn|switch|set|make)\s+(the\s+)?tutorial(\s+mode)?\s+(on|enable|enabled)\b", query_lower):
        return {"action": "on"}
    if re.search(r"\b(enable|start|show)\s+(the\s+)?tutorial(\s+mode)?\b", query_lower):
        return {"action": "on"}
    if re.search(r"\b(disable|stop|hide)\s+(the\s+)?tutorial(\s+mode)?\b", query_lower):
        return {"action": "off"}
    if re.search(r"\btutorial(\s+mode)?\s+on\b", query_lower):
        return {"action": "on"}
    if re.search(r"\btutorial(\s+mode)?\s+off\b", query_lower):
        return {"action": "off"}
    if re.search(r"\btoggle\s+(the\s+)?tutorial(\s+mode)?\b", query_lower) or re.search(
        r"\btutorial(\s+mode)?\s+toggle\b",
        query_lower,
    ):
        return {"action": "toggle"}
    if has_ui_help or re.search(r"\btutorial(\s+mode)?\b", query_lower):
        return {"action": "on"}
    return None


def detect_address_prompt_intent(query: str) -> Optional[dict]:
    """Detect explicit requests to open the address entry UI."""
    query_lower = (query or "").strip().lower()
    if not query_lower:
        return None

    trigger_patterns = [
        r"\b(add|enter|use|check|view|show|open|start)\s+(an?\s+)?address\b",
        r"\baddress\s+(lookup|input|entry|search|mode|finder)\b",
        r"\b(type|search)\s+(for\s+)?an?\s+address\b",
        r"\bfind\s+an?\s+address\b",
    ]
    if any(re.search(pattern, query_lower) for pattern in trigger_patterns):
        return {
            "action": "open",
            "message": "Start typing an address and pick the best match from autocomplete.",
            "placeholder": "Search for an address...",
        }
    return None
