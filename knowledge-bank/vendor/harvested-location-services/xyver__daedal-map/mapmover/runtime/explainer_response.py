"""Shared explainer-response helper.

Some recurring user questions are meta / explainer in shape rather than data
requests, for example:

  - "What is the distributed manufacturing source?"
  - "What is the CEJST classification and how does it work?"
  - "Why is this tract classified as disadvantaged?"

Pack metadata already carries enough structured material to answer most of
these (`description`, `llm_summary`, `facility_types`, etc.). This helper
turns that metadata into a chat-only response payload plus a stub order so
the user still has a "view the data" affordance.

Orchestrators should call `build_explainer_response` after the order-taker
declines to produce an executable order. If the question is not meta /
explainer shaped, the helper returns None and the order_first behavior is
preserved on real data requests.

See: county-map-private/docs/future/runtime_and_lane_unification_plan.md
section "Recently Identified Shared Helper Gaps" for the migration order and
call-site inventory.
"""

from __future__ import annotations

import re
from typing import Any, Optional


_EXPLAINER_PREFIXES = (
    "what is ",
    "what's ",
    "what are ",
    "how does ",
    "how do ",
    "why is ",
    "why are ",
    "tell me about ",
    "tell me more about ",
    "can you tell me about ",
    "give me more information about ",
    "give me information about ",
    "more information about ",
    "information about ",
    "explain ",
    "describe ",
)

_EXPLAINER_PATTERNS = (
    re.compile(r"\bhow does\b.*\bwork\b", re.IGNORECASE),
    re.compile(r"\bwhat does\b.*\bmean\b", re.IGNORECASE),
    re.compile(r"\bwhat kinds? of\b", re.IGNORECASE),
    re.compile(r"\bwhat types? of\b", re.IGNORECASE),
    re.compile(r"\b(?:more\s+)?information\s+about\b", re.IGNORECASE),
)

_CONTEXT_ORIENTATION_PATTERN = re.compile(
    r"\b(?:what(?:'s|\s+is)\s+(?:this|that|it|i\s+am\s+looking\s+at)|"
    r"what\s+am\s+i\s+looking\s+at|tell\s+me\s+more|"
    r"(?:explain|describe)\s+(?:this|that|the\s+(?:data|source|layer)))\b",
    re.IGNORECASE,
)

_DATA_REQUEST_BLOCKERS = (
    " per capita",
    " exposure",
    " trend",
    " over the last ",
    " over last ",
    " in the last ",
    " over time",
    " compare ",
    " count",
    " total",
    " average",
    " highest",
    " lowest",
    " counties in ",
    " tracts in ",
    " regions in ",
    " areas in ",
    " in japan",
    " in california",
    " in florida",
)


def _normalize(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return text.strip().lower()


def looks_like_explainer_question(question: Any) -> bool:
    """Return True when the question is shaped like an explainer/meta query.

    Conservative detection - real data requests with the same prefix still
    fall through to the data path. The caller decides when to consult this
    helper (typically after the order-taker returns no executable order).
    """
    norm = _normalize(question)
    if not norm:
        return False
    if any(token in norm for token in _DATA_REQUEST_BLOCKERS):
        return False
    if any(norm.startswith(prefix) for prefix in _EXPLAINER_PREFIXES):
        return True
    return any(pattern.search(norm) for pattern in _EXPLAINER_PATTERNS)


def looks_like_orientation_question(question: Any) -> bool:
    """True for named-source explainers and context-only map orientation."""
    return looks_like_explainer_question(question) or bool(
        _CONTEXT_ORIENTATION_PATTERN.search(str(question or ""))
    )


def _summarize_upstream_sources(source_metadata: dict) -> Optional[str]:
    raw = source_metadata.get("upstream_sources")
    if not isinstance(raw, list) or not raw:
        return None
    pieces = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("agency_short") or entry.get("agency")
        if name:
            pieces.append(str(name))
    if not pieces:
        return None
    return ", ".join(pieces)


def _format_structured_dict(name: str, payload: Any) -> Optional[str]:
    """Render a structured metadata dict (like `facility_types`) as a list block."""
    if not isinstance(payload, dict) or not payload:
        return None
    lines = [f"{name}:"]
    for key, value in payload.items():
        if isinstance(value, str) and value.strip():
            lines.append(f"- {key}: {value.strip()}")
        else:
            lines.append(f"- {key}")
    return "\n".join(lines)


def _build_stub_order(source_metadata: dict) -> Optional[dict]:
    """Return a minimal order pointing at the pack so the user can still view it."""
    source_id = source_metadata.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        return None
    return {
        "type": "explainer_stub",
        "source_id": source_id,
        "pack_id": source_metadata.get("pack_id"),
        "intent": "view_pack",
    }


def _first_nonempty(*values: Any) -> Optional[str]:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_reference_sections(source_reference: dict) -> dict[str, Any]:
    sections: dict[str, Any] = {}
    if not isinstance(source_reference, dict):
        return sections

    source_info = source_reference.get("source")
    if isinstance(source_info, dict):
        description = _first_nonempty(
            source_info.get("description"),
            source_info.get("summary"),
        )
        if description:
            sections["reference_description"] = description

    context = source_reference.get("context")
    if isinstance(context, str) and context.strip():
        sections["reference_context"] = context.strip()
    elif isinstance(context, dict):
        context_parts = []
        for key in ("overview", "methodology", "usage_notes", "interpretation"):
            value = context.get(key)
            if isinstance(value, str) and value.strip():
                context_parts.append(value.strip())
        if context_parts:
            sections["reference_context"] = "\n\n".join(context_parts)

    about = source_reference.get("about")
    if isinstance(about, dict):
        about_parts = []
        for key in ("summary", "history", "methodology", "source_context"):
            value = about.get(key)
            if isinstance(value, str) and value.strip():
                about_parts.append(value.strip())
        if about_parts and "reference_context" not in sections:
            sections["reference_context"] = "\n\n".join(about_parts)

    goal = source_reference.get("goal")
    if isinstance(goal, dict):
        goal_title = _first_nonempty(goal.get("full_title"), goal.get("name"))
        goal_description = _first_nonempty(goal.get("description"))
        if goal_title:
            sections["reference_title"] = goal_title
        if goal_description:
            sections["reference_description"] = goal_description
        targets = goal.get("targets")
        if isinstance(targets, list) and targets:
            lines = []
            for entry in targets[:8]:
                if isinstance(entry, dict):
                    text = _first_nonempty(entry.get("description"), entry.get("title"), entry.get("name"))
                    code = _first_nonempty(entry.get("code"), entry.get("id"))
                    if text and code:
                        lines.append(f"- {code}: {text}")
                    elif text:
                        lines.append(f"- {text}")
                elif isinstance(entry, str) and entry.strip():
                    lines.append(f"- {entry.strip()}")
            if lines:
                sections["reference_targets"] = "Targets:\n" + "\n".join(lines)

    return sections


def _extract_source_info_sections(source_reference: dict, lane: str | None) -> dict[str, Any]:
    """Extract the deliberately short, reusable source-info contract."""
    if not isinstance(source_reference, dict):
        return {}
    info = source_reference.get("source_info")
    if not isinstance(info, dict):
        return {}

    sections: dict[str, Any] = {}
    for key in ("short_answer", "what_it_is", "coverage", "interpretation", "attribution", "source_link"):
        value = info.get(key)
        if isinstance(value, str) and value.strip():
            sections[key] = value.strip()
    for key in ("measures", "not"):
        values = info.get(key)
        if isinstance(values, list):
            cleaned = [str(value).strip() for value in values if str(value).strip()]
            if cleaned:
                sections[key] = cleaned

    normalized_lane = str(lane or "").strip().lower()
    guidance = source_reference.get("lane_guidance")
    lane_info = guidance.get(normalized_lane) if isinstance(guidance, dict) and normalized_lane else None
    if isinstance(lane_info, dict):
        availability = str(lane_info.get("availability") or "").strip().replace("_", " ")
        answer_note = lane_info.get("answer_note")
        if availability:
            sections["lane_availability"] = f"{normalized_lane.title()} availability: {availability}."
        if isinstance(answer_note, str) and answer_note.strip():
            sections["lane_note"] = answer_note.strip()
    return sections


def _extract_view_context_sections(view_context: dict | None) -> dict[str, Any]:
    """Create a compact, deterministic description of the current map state.

    This is deliberately a presentation boundary: callers pass their existing
    request context, while future overlay/event/time contracts can add fields
    here without creating another "what am I looking at" response path.
    """
    if not isinstance(view_context, dict):
        return {}
    parts: list[str] = []
    loaded = view_context.get("loaded_data") or []
    loaded_bits: list[str] = []
    for entry in loaded[:4]:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source_name") or entry.get("source_id") or "").strip()
        metric = str(entry.get("metric") or "").strip()
        region = str(entry.get("region") or "").strip()
        years = entry.get("years") or entry.get("year") or entry.get("year_range")
        bit = source
        if metric:
            bit += f" ({metric})"
        if region and region.lower() != "global":
            bit += f" in {region}"
        if years not in (None, "", []):
            bit += f", {years}"
        if bit:
            loaded_bits.append(bit)
    if loaded_bits:
        suffix = "" if len(loaded) <= len(loaded_bits) else " and additional layers"
        parts.append("Loaded data: " + "; ".join(loaded_bits) + suffix + ".")

    time_state = view_context.get("time_state") or {}
    if isinstance(time_state, dict):
        if time_state.get("isLiveLocked"):
            parts.append("Time: live current conditions.")
        elif str(time_state.get("currentTimeFormatted") or "").strip():
            parts.append(f"Time: {str(time_state['currentTimeFormatted']).strip()}.")

    selected = view_context.get("selected_popup") or {}
    if isinstance(selected, dict):
        label = selected.get("name") or selected.get("event_id") or selected.get("loc_id")
        if isinstance(label, str) and label.strip():
            parts.append(f"Selected item: {label.strip()}.")

    overlays = view_context.get("active_overlays") or {}
    if isinstance(overlays, dict):
        overlay_type = str(overlays.get("type") or "").strip()
        if overlay_type:
            parts.append(f"Active overlay: {overlay_type}.")
    return {"view_context": "\n".join(parts)} if parts else {}


def build_view_orientation_response(view_context: dict | None, lane: str | None = None) -> Optional[dict]:
    """Explain map state when no single source can honestly be selected."""
    sections = _extract_view_context_sections(view_context)
    text = sections.get("view_context")
    if not text:
        return None
    lane_label = str(lane or "").strip().title()
    prefix = f"{lane_label} map context:" if lane_label else "Map context:"
    return {
        "intent": "explainer",
        "source_id": None,
        "pack_id": None,
        "text": f"{prefix}\n{text}",
        "sections": sections,
        "stub_order": None,
    }


def build_explainer_response(
    source_metadata: Optional[dict],
    question: Any,
    source_reference: Optional[dict] = None,
    lane: str | None = None,
    view_context: dict | None = None,
    allow_orientation: bool = False,
) -> Optional[dict]:
    """Build an explainer response from pack metadata, or return None.

    Returns None when:
      - source_metadata is missing or unusable
      - the question does not look like an explainer/meta query
      - the metadata carries no `description` or `llm_summary`

    `allow_orientation` widens the question gate to context-orientation phrasing
    ("what am I looking at here?"). Callers that have already established the
    orientation context, and resolved which source is loaded, should pass it;
    otherwise a question that cleared `looks_like_orientation_question` upstream
    would be dropped here by the stricter explainer test.

    Returned dict shape:
      {
        "intent": "explainer",
        "source_id": ...,
        "pack_id": ...,
        "text": <assembled chat-only answer>,
        "sections": {description, summary, facility_types, upstream_sources, last_updated},
        "stub_order": <minimal order pointing at the pack> | None,
      }
    """
    if not isinstance(source_metadata, dict) and not isinstance(source_reference, dict):
        return None
    question_matches = (
        looks_like_orientation_question(question)
        if allow_orientation
        else looks_like_explainer_question(question)
    )
    if not question_matches:
        return None

    reference_sections = _extract_reference_sections(source_reference or {})
    source_info_sections = _extract_source_info_sections(source_reference or {}, lane)
    view_context_sections = _extract_view_context_sections(view_context)
    description = source_metadata.get("description") if isinstance(source_metadata, dict) else None
    llm_summary = source_metadata.get("llm_summary") if isinstance(source_metadata, dict) else None
    if not reference_sections and not source_info_sections and not (
        (isinstance(description, str) and description.strip())
        or (isinstance(llm_summary, str) and llm_summary.strip())
    ):
        return None

    sections: dict[str, Any] = {}
    for key in ("reference_title", "reference_description", "reference_context", "reference_targets"):
        if key in reference_sections:
            sections[key] = reference_sections[key]
    sections.update(source_info_sections)
    sections.update(view_context_sections)
    if isinstance(description, str) and description.strip():
        sections["description"] = description.strip()
    if isinstance(llm_summary, str) and llm_summary.strip():
        sections["summary"] = llm_summary.strip()

    if isinstance(source_metadata, dict):
        facility_types_block = _format_structured_dict(
            "Facility types", source_metadata.get("facility_types")
        )
        if facility_types_block:
            sections["facility_types"] = facility_types_block

    upstream_summary = _summarize_upstream_sources(source_metadata or {})
    if upstream_summary:
        sections["upstream_sources"] = upstream_summary

    last_updated = source_metadata.get("last_updated") if isinstance(source_metadata, dict) else None
    if isinstance(last_updated, str) and last_updated.strip():
        sections["last_updated"] = last_updated.strip()

    text_parts = []
    if "reference_title" in sections:
        text_parts.append(sections["reference_title"])
    if "short_answer" in sections:
        text_parts.append(sections["short_answer"])
    elif "reference_description" in sections:
        text_parts.append(sections["reference_description"])
    elif "summary" in sections:
        text_parts.append(sections["summary"])
    elif "description" in sections:
        text_parts.append(sections["description"])
    if "reference_context" in sections:
        text_parts.append(sections["reference_context"])
    elif "summary" in sections and sections["summary"] not in text_parts:
        text_parts.append(sections["summary"])
    if "facility_types" in sections:
        text_parts.append(sections["facility_types"])
    if "reference_targets" in sections:
        text_parts.append(sections["reference_targets"])
    if "what_it_is" in sections:
        text_parts.append(sections["what_it_is"])
    if "coverage" in sections:
        text_parts.append(f"Coverage: {sections['coverage']}")
    if "measures" in sections:
        text_parts.append("Measures: " + ", ".join(sections["measures"]) + ".")
    if "not" in sections:
        text_parts.append("It is not: " + ", ".join(sections["not"]) + ".")
    if "interpretation" in sections:
        text_parts.append(sections["interpretation"])
    if "lane_availability" in sections:
        text_parts.append(sections["lane_availability"])
    if "lane_note" in sections:
        text_parts.append(sections["lane_note"])
    if "attribution" in sections:
        text_parts.append(f"Attribution: {sections['attribution']}")
    if "source_link" in sections:
        text_parts.append(f"Source: {sections['source_link']}")
    if "view_context" in sections:
        text_parts.append("Current map context:\n" + sections["view_context"])
    if "upstream_sources" in sections:
        text_parts.append(f"Upstream sources: {sections['upstream_sources']}.")
    if "last_updated" in sections:
        text_parts.append(f"Last updated: {sections['last_updated']}.")
    text = "\n\n".join(part for part in text_parts if part)

    source_payload = source_metadata if isinstance(source_metadata, dict) else (source_reference or {})

    return {
        "intent": "explainer",
        "source_id": source_payload.get("source_id"),
        "pack_id": source_payload.get("pack_id"),
        "text": text,
        "sections": sections,
        "stub_order": _build_stub_order(source_payload),
    }
