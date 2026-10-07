"""Lightweight preprocessor for Research mode.

Research preprocessing should reduce model effort without turning Research into an
order taker. It extracts a small set of corpus-safe hints from the user query and the
active corpus manifest.
"""

from __future__ import annotations

import re

from mapmover.runtime.preprocess_primitives import detect_time_patterns as detect_time_patterns_impl


DISPLAY_PATTERNS = [
    r"\bshow\b",
    r"\bdisplay\b",
    r"\bhighlight\b",
    r"\bmap\b",
    r"\bplot\b",
    r"\bput .* on the map\b",
]

RANKING_PATTERNS = [
    r"\btop\s+\d+\b",
    r"\bhighest\b",
    r"\bhottest\b",
    r"\blowest\b",
    r"\brank\b",
    r"\branking\b",
]

COMPARISON_PATTERNS = [
    r"\bcompare\b",
    r"\bversus\b",
    r"\bvs\b",
    r"\bcorrelat",
    r"\brelationship\b",
]

GEO_TERMS = [
    "block group",
    "block groups",
    "blocks",
    "block",
    "tracts",
    "tract",
    "counties",
    "county",
]


def _detect_boolean(query: str, patterns: list[str]) -> bool:
    text = str(query or "").lower()
    return any(re.search(pattern, text) for pattern in patterns)


def _detect_geography_terms(query: str) -> list[str]:
    text = str(query or "").lower()
    matched = []
    for term in GEO_TERMS:
        if term in text and term not in matched:
            matched.append(term)
    return matched


def preprocess_research_query(query: str, corpus_manifest: dict | None = None) -> dict:
    """Extract small corpus-safe hints for a Research turn."""
    time_hints = detect_time_patterns_impl(query)
    return {
        "display_request_likely": _detect_boolean(query, DISPLAY_PATTERNS),
        "ranking_request_likely": _detect_boolean(query, RANKING_PATTERNS),
        "comparison_request_likely": _detect_boolean(query, COMPARISON_PATTERNS),
        "geography_terms": _detect_geography_terms(query),
        "time": time_hints,
    }


def build_research_hint_context(hints: dict | None) -> str:
    """Format compact preprocessor hints for model context."""
    if not isinstance(hints, dict):
        return ""

    parts = []
    if hints.get("display_request_likely"):
        parts.append("User likely wants a map display in addition to analysis.")
    if hints.get("ranking_request_likely"):
        parts.append("User likely wants a ranking or ordered result.")
    if hints.get("comparison_request_likely"):
        parts.append("User may be asking for comparison or relationship analysis.")

    geo_terms = hints.get("geography_terms") or []
    if geo_terms:
        parts.append("Geography terms in query: " + ", ".join(geo_terms[:6]))

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
