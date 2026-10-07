"""Explore-specific follow-up and early-response helpers."""

from __future__ import annotations

import re


def address_prompt_response(prompt: dict | None) -> dict:
    """Build the structured address prompt response."""
    prompt = prompt or {}
    return {
        "type": "address_prompt",
        "message": prompt.get("message") or "Start typing an address and choose a suggestion.",
        "placeholder": prompt.get("placeholder") or "Search for an address...",
    }


def compact_followup_message(message: str) -> str:
    """Trim branchy follow-up text into a shorter Explore-friendly response."""
    text = str(message or "").strip()
    if not text or text.count("?") <= 2:
        return text

    lower = text.lower()
    cue_patterns = (
        r"\bwould you like me to\b",
        r"\bwhich approach\b",
        r"\blet me know which approach\b",
        r"\bwould you like me\b",
    )
    cut_idx = None
    for pattern in cue_patterns:
        match = re.search(pattern, lower)
        if match and (cut_idx is None or match.start() < cut_idx):
            cut_idx = match.start()

    if cut_idx is None:
        return text

    lead = text[:cut_idx].rstrip()
    lead = re.sub(r"\n{3,}", "\n\n", lead).strip()
    if lead and lead[-1] not in ".!?":
        lead += "."

    if "volcan" in lower and ("increasing" in lower or "trend" in lower):
        followup = "If you want, I can focus on a recent period such as the last 100 or 500 years for a cleaner trend analysis."
    elif "wildfire" in lower and "population" in lower and ("burned" in lower or "areas" in lower):
        followup = "If you want, I can either show the burned areas for Canada in 2023 or narrow this to a population-exposure estimate path."
    else:
        followup = "If you want, I can narrow this to one concrete metric, region, or time window."

    return f"{lead}\n\n{followup}".strip()


def build_show_borders_response(previous_options: list, *, original_query: str, geojson: dict) -> dict:
    """Build the show-borders navigation response."""
    loc_ids_to_show = [opt.get("loc_id") for opt in previous_options if opt.get("loc_id")]
    return {
        "type": "navigate",
        "message": f"Showing {len(loc_ids_to_show)} locations on the map. Click any location to see data options.",
        "locations": previous_options if previous_options else [{"loc_id": lid} for lid in loc_ids_to_show],
        "loc_ids": loc_ids_to_show,
        "original_query": original_query,
        "geojson": geojson,
    }


def build_drilldown_response(location: dict, *, original_query: str) -> dict:
    """Build the drilldown response for one navigation target."""
    return {
        "type": "drilldown",
        "message": f"Showing {location.get('drill_to_level')} of {location.get('matched_term', location.get('loc_id'))}...",
        "loc_id": location.get("loc_id"),
        "name": location.get("matched_term", location.get("loc_id")),
        "drill_to_level": location.get("drill_to_level"),
        "original_query": original_query,
    }
