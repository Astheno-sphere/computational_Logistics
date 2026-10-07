"""Lightweight watch-focused preprocessor for Ops mode."""

from __future__ import annotations

import re

from mapmover.runtime.preprocess_primitives import detect_time_patterns as detect_time_patterns_impl


LIVE_PATTERNS = [
    r"\blive\b",
    r"\bright now\b",
    r"\bcurrent\b",
    r"\bactive\b",
    r"\brecent\b",
]

TRIAGE_PATTERNS = [
    r"\bwatch\b",
    r"\bmonitor\b",
    r"\btriage\b",
    r"\balert\b",
    r"\brespond\b",
]

REPORT_PATTERNS = [
    r"\breport\b",
    r"\bbrief\b",
    r"\bsummary\b",
    r"\bupdate\b",
]

GEO_TERMS = [
    "country",
    "countries",
    "state",
    "states",
    "province",
    "provinces",
    "county",
    "counties",
    "region",
    "regions",
]


def _detect_boolean(query: str, patterns: list[str]) -> bool:
    text = str(query or "").lower()
    return any(re.search(pattern, text) for pattern in patterns)


def _detect_geography_terms(query: str) -> list[str]:
    text = str(query or "").lower()
    matched: list[str] = []
    for term in GEO_TERMS:
        if term in text and term not in matched:
            matched.append(term)
    return matched


def preprocess_ops_query(query: str, watch_context: dict | None = None) -> dict:
    """Extract lightweight hints for an Ops watch or triage turn."""
    watch_context = watch_context if isinstance(watch_context, dict) else {}
    time_hints = detect_time_patterns_impl(query)
    return {
        "live_request_likely": _detect_boolean(query, LIVE_PATTERNS),
        "triage_request_likely": _detect_boolean(query, TRIAGE_PATTERNS),
        "report_request_likely": _detect_boolean(query, REPORT_PATTERNS),
        "geography_terms": _detect_geography_terms(query),
        "time": time_hints,
        "watch_context_label": str(watch_context.get("label") or watch_context.get("focus") or "").strip(),
        "watch_context_sources": list(watch_context.get("sources") or []),
    }


def build_ops_hint_context(hints: dict | None) -> str:
    """Format compact Ops hint context for the system prompt."""
    if not isinstance(hints, dict):
        return ""

    parts: list[str] = []
    if hints.get("live_request_likely"):
        parts.append("User likely wants a live or current-time operational view.")
    if hints.get("triage_request_likely"):
        parts.append("User likely wants triage or monitoring support.")
    if hints.get("report_request_likely"):
        parts.append("User likely wants a concise brief or status update.")

    geo_terms = hints.get("geography_terms") or []
    if geo_terms:
        parts.append("Geography terms in query: " + ", ".join(geo_terms[:6]))

    watch_context_label = str(hints.get("watch_context_label") or "").strip()
    if watch_context_label:
        parts.append(f"Active watch scope: {watch_context_label}")

    watch_sources = hints.get("watch_context_sources") or []
    if watch_sources:
        parts.append("Watch sources in scope: " + ", ".join(str(value) for value in watch_sources[:8]))

    time_hints = hints.get("time") or {}
    if time_hints:
        explicit_bits = []
        for key in ("specific_year", "start_year", "end_year", "time_type"):
            value = time_hints.get(key)
            if value not in (None, "", [], {}):
                explicit_bits.append(f"{key}={value}")
        if explicit_bits:
            parts.append("Time hints: " + ", ".join(explicit_bits))

    return "\n".join(parts).strip()
