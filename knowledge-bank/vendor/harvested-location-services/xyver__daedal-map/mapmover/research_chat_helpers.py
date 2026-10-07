"""Shared helper functions for the Research chat pipeline."""

from __future__ import annotations

import json
from mapmover import logger


PROMPT_ARTIFACT_WINDOW = 64
RESEARCH_MAX_TOKENS = 5000
PROMPT_METRIC_LIMIT = 24
PROMPT_FIELD_LIMIT = 12
PROMPT_SCENE_PERIOD_LIMIT = 4
TOOL_ROWS_PREVIEW_LIMIT = 10

_MAP_PAYLOAD_FIELDS = (
    "artifact_id",
    "source_id",
    "data_type",
    "declared_data_type",
    "geographic_level",
    "geojson",
    "loc_ids",
    "feature_count",
    "time_data",
    "time_range",
    "year_data",
    "years",
    "year_range",
    "time_field",
    "multi_year",
    "metric",
    "metric_key",
    "available_metrics",
    "metric_time_ranges",
    "metric_year_ranges",
    "scene_periods",
    "raster_clip_levels",
    "fit",
    "context_visibility",
    "style",
)


def _manifest_prompt_window_warning(manifest: dict | None) -> str | None:
    artifact_count = int((manifest or {}).get("artifact_count") or 0)
    if artifact_count <= PROMPT_ARTIFACT_WINDOW:
        return None
    return (
        f"This corpus has {artifact_count} loaded artifacts, which is larger than the current "
        f"prompt-friendly window of {PROMPT_ARTIFACT_WINDOW}. Research can still work, "
        "but broad questions may be less reliable unless you narrow the corpus or ask about a smaller subset."
    )


def _sample_prompt_metrics(metrics: list | None, limit: int) -> list[str]:
    values = [str(metric).strip() for metric in (metrics or []) if str(metric).strip()]
    if len(values) <= limit:
        return values

    grouped: dict[str, list[str]] = {}
    ordered_prefixes: list[str] = []
    for metric in values:
        prefix = metric.split("_", 1)[0] if "_" in metric else "__root__"
        if prefix not in grouped:
            grouped[prefix] = []
            ordered_prefixes.append(prefix)
        grouped[prefix].append(metric)

    preview: list[str] = []
    seen = set()
    round_index = 0
    while len(preview) < limit:
        added = False
        for prefix in ordered_prefixes:
            items = grouped.get(prefix) or []
            if round_index < len(items):
                metric = items[round_index]
                if metric not in seen:
                    preview.append(metric)
                    seen.add(metric)
                    added = True
                    if len(preview) >= limit:
                        break
        if not added:
            break
        round_index += 1
    return preview


def _temperature_kwargs(model: str, temperature: float) -> dict:
    """Research-lane alias for the shared sampling-capability helper.

    Kept as a named function because the research runtimes take it as an
    injected `temperature_kwargs_func`. The model list itself lives in
    runtime/llm_policy.py alongside model selection.
    """
    from .runtime.llm_policy import sampling_kwargs

    return sampling_kwargs(model, temperature)


def _extract_text(content_blocks) -> str:
    parts = []
    for block in content_blocks or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def _content_block_types(content_blocks) -> list[str]:
    types: list[str] = []
    for block in content_blocks or []:
        block_type = getattr(block, "type", None)
        if block_type:
            types.append(str(block_type))
            continue
        if isinstance(block, dict) and block.get("type"):
            types.append(str(block.get("type")))
    return types


def _tool_call_signature(tool_name: str, tool_input: dict | None) -> str:
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    filters = tool_input.get("filters") if isinstance(tool_input.get("filters"), dict) else {}
    order_by = tool_input.get("order_by") if isinstance(tool_input.get("order_by"), list) else []
    payload = {
        "tool": tool_name,
        "artifact_id": tool_input.get("artifact_id"),
        "filter_keys": sorted(str(key) for key in filters.keys()),
        "group_by": sorted(str(value) for value in (tool_input.get("group_by") or [])),
        "metrics": sorted(str(value) for value in (tool_input.get("metrics") or [])),
        "fields": sorted(str(value) for value in (tool_input.get("fields") or [])),
        "order_by": [
            {
                "field": str(item.get("field") or ""),
                "direction": str(item.get("direction") or "desc"),
            }
            for item in order_by
            if isinstance(item, dict)
        ],
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _broad_research_fallback_message(query: str, manifest: dict, research_hints: dict | None = None) -> str:
    artifact_count = int(manifest.get("artifact_count") or 0)
    saved = manifest.get("saved_corpus") or {}
    pack_count = int(saved.get("pack_count") or 0)
    query_text = str(query or "").strip()
    lowered = query_text.lower()
    broad_markers = (
        "other metrics",
        "what can you tell me",
        "what changed",
        "how were",
        "after its biggest earthquake",
    )
    if artifact_count >= 8 or any(marker in lowered for marker in broad_markers):
        return (
            f'That question is broad for the current Research workspace: it spans {artifact_count} loaded artifacts'
            + (f" across {pack_count} packs" if pack_count else "")
            + ". Try narrowing it to one event plus a smaller metric set. For example:\n"
              "- `What changed in Japan after the 2011 Tohoku earthquake in SDG Goal 1 and Goal 8?`\n"
              "- `Compare Japan before vs after 2011 for poverty, population, GDP, and energy use.`\n"
              "- `What was Japan's biggest earthquake, and which 3-5 later indicators moved the most after it?`"
        )
    return "I could not produce a research answer from the active corpus."


def _word_chunks(text: str, words_per_chunk: int = 4):
    words = str(text or "").split(" ")
    for idx in range(0, len(words), words_per_chunk):
        chunk = " ".join(words[idx:idx + words_per_chunk])
        if idx + words_per_chunk < len(words):
            chunk += " "
        yield chunk


def _fallback_display_message(display: dict | None) -> str | None:
    if not isinstance(display, dict):
        return None
    feature_count = len(((display.get("geojson") or {}).get("features") or []))
    if feature_count <= 0:
        return None
    source_id = str(display.get("source_id") or "").strip()
    source_lower = source_id.lower()
    if "building" in source_lower:
        noun = "building footprint"
    elif "parcel" in source_lower:
        noun = "parcel"
    elif "station" in source_lower or "buoy" in source_lower or "facility" in source_lower:
        noun = "entity point"
    elif "lst" in source_id or "raster" in source_id:
        noun = "raster area"
    else:
        noun = "matching feature"
    suffix = "" if feature_count == 1 else "s"
    return f"Highlighted {feature_count} {noun}{suffix} on the map."


def _history_messages(history: list, max_messages: int = 12) -> list[dict]:
    messages = []
    for msg in (history or [])[-max_messages:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        messages.append({"role": role, "content": content})
    return messages


def _research_memory_messages(research_memory: dict | None) -> list[dict]:
    if not isinstance(research_memory, dict):
        return []

    messages = []
    original_goal = str(research_memory.get("originalGoal") or "").strip()
    summary = str(research_memory.get("summary") or "").strip()
    compacted_count = research_memory.get("compactedMessageCount")
    active_display_state = research_memory.get("activeDisplayState")

    if original_goal:
        messages.append(
            {
                "role": "user",
                "content": f"Original research goal from earlier in this session: {original_goal}",
            }
        )
    if summary:
        label = "Compacted memory from earlier research turns"
        if compacted_count:
            label += f" ({compacted_count} earlier messages)"
        messages.append(
            {
                "role": "assistant",
                "content": f"{label}:\n{summary}",
            }
        )
    if isinstance(active_display_state, dict) and active_display_state:
        messages.append(
            {
                "role": "assistant",
                "content": "Current active Research display state:\n```json\n" + json.dumps(active_display_state, indent=2, default=str) + "\n```",
            }
        )
    return messages


def _compact_manifest_for_prompt(manifest: dict) -> dict:
    saved_corpus = manifest.get("saved_corpus") or {}
    compact_saved = None
    if saved_corpus:
        compact_saved = {
            "id": saved_corpus.get("id"),
            "name": saved_corpus.get("name"),
            "pack_count": saved_corpus.get("pack_count"),
            "source_count": saved_corpus.get("source_count"),
            "estimated_row_count_total": saved_corpus.get("estimated_row_count_total"),
            "estimated_file_size_mb_total": saved_corpus.get("estimated_file_size_mb_total"),
            "source_ids": saved_corpus.get("source_ids") or [],
        }

    manifest_artifacts = manifest.get("artifacts") or []
    artifacts = []
    for artifact in manifest_artifacts[:PROMPT_ARTIFACT_WINDOW]:
        artifacts.append(
            {
                "artifact_id": artifact.get("artifact_id"),
                "source_id": artifact.get("source_id"),
                "source_name": artifact.get("source_name"),
                "data_type": artifact.get("data_type"),
                "geographic_level": artifact.get("geographic_level"),
                "future_available": artifact.get("future_available"),
                "routing_summary": artifact.get("routing_summary"),
                "metric_groups": artifact.get("metric_groups") or {},
                "metrics": _sample_prompt_metrics(artifact.get("metrics") or [], PROMPT_METRIC_LIMIT),
                "metric_count": len(artifact.get("metrics") or []),
                "metric_time_ranges": artifact.get("metric_time_ranges") or artifact.get("metric_year_ranges") or {},
                "fields": (artifact.get("fields") or [])[:PROMPT_FIELD_LIMIT],
                "time_range": artifact.get("time_range") or artifact.get("year_range"),
                "feature_count": artifact.get("feature_count"),
                "row_count": artifact.get("row_count"),
                "summary": artifact.get("summary"),
                "scene_periods": (artifact.get("scene_periods") or [])[:PROMPT_SCENE_PERIOD_LIMIT],
                "raster_clip_levels": artifact.get("raster_clip_levels") or [],
            }
        )

    compact = {
        "session_id": manifest.get("session_id"),
        "mode": manifest.get("mode"),
        "artifact_count": manifest.get("artifact_count"),
        "artifacts": artifacts,
        "saved_corpus": compact_saved,
    }
    omitted = max(0, len(manifest_artifacts) - len(artifacts))
    if omitted:
        compact["artifacts_omitted"] = omitted
        compact["omitted_source_ids"] = [
            str((artifact or {}).get("source_id") or "").strip()
            for artifact in manifest_artifacts[len(artifacts):len(artifacts) + 20]
            if str((artifact or {}).get("source_id") or "").strip()
        ]
    return compact


def _research_map_payload_from_tool_result(tool_result: dict) -> dict:
    payload: dict = {}
    for key in _MAP_PAYLOAD_FIELDS:
        if key in tool_result:
            payload[key] = tool_result[key]
    return payload


def _compact_tool_result_for_prompt(tool_name: str, tool_result: dict) -> dict:
    if not isinstance(tool_result, dict):
        return {"type": "unsupported_tool_result"}

    compact = {}
    for key in ("error", "artifact_id", "row_count", "truncated"):
        if key in tool_result:
            compact[key] = tool_result.get(key)

    if tool_name == "ask_research_sources":
        compact.update({
            "outcome": tool_result.get("outcome"),
            "pack_ids": tool_result.get("pack_ids") or [],
            "source_ids": tool_result.get("source_ids") or [],
            "source_boundary": tool_result.get("source_boundary") or [],
            "binding_rule": tool_result.get("binding_rule"),
        })
        return compact

    if tool_name == "get_research_pack":
        pack = tool_result.get("pack") or {}
        compact.update({
            "outcome": tool_result.get("outcome"),
            "source_boundary": tool_result.get("source_boundary") or [],
            "pack": {
                "pack_id": pack.get("pack_id"),
                "source_ids": pack.get("source_ids") or [],
                "sources": pack.get("sources") or [],
            },
            "research_query_contract": tool_result.get("research_query_contract") or {},
        })
        return compact

    if tool_name == "query_research_source_data":
        rows = tool_result.get("rows") or []
        compact.update({
            "outcome": tool_result.get("outcome"),
            "source_id": tool_result.get("source_id"),
            "metrics": tool_result.get("metrics") or [],
            "filters_applied": tool_result.get("filters_applied") or {},
            "source_boundary": tool_result.get("source_boundary") or [],
            "rows_preview": rows[:TOOL_ROWS_PREVIEW_LIMIT],
            "returned_row_count": len(rows),
            "warnings": tool_result.get("warnings") or [],
        })
        return compact

    if tool_name == "list_artifacts":
        artifacts = tool_result.get("artifacts") or []
        compact["artifacts"] = [
            {
                "artifact_id": artifact.get("artifact_id"),
                "source_id": artifact.get("source_id"),
                "source_name": artifact.get("source_name"),
                "data_type": artifact.get("data_type"),
                "geographic_level": artifact.get("geographic_level"),
                "future_available": artifact.get("future_available"),
                "metric_groups": artifact.get("metric_groups") or {},
                "metrics": _sample_prompt_metrics(artifact.get("metrics") or [], min(12, PROMPT_METRIC_LIMIT)),
                "metric_count": len(artifact.get("metrics") or []),
            }
            for artifact in artifacts[:PROMPT_ARTIFACT_WINDOW]
        ]
        compact["artifact_count"] = len(artifacts)
        omitted = max(0, len(artifacts) - len(compact["artifacts"]))
        if omitted:
            compact["artifacts_omitted"] = omitted
            compact["omitted_source_ids"] = [
                str((artifact or {}).get("source_id") or "").strip()
                for artifact in artifacts[len(compact["artifacts"]):len(compact["artifacts"]) + 20]
                if str((artifact or {}).get("source_id") or "").strip()
            ]
        return compact

    if tool_name == "describe_artifact":
        artifact = tool_result.get("artifact") or {}
        compact["artifact"] = {
            "artifact_id": artifact.get("artifact_id"),
            "source_id": artifact.get("source_id"),
            "source_name": artifact.get("source_name"),
            "data_type": artifact.get("data_type"),
            "time_field": artifact.get("time_field"),
            "geographic_level": artifact.get("geographic_level"),
            "future_available": artifact.get("future_available"),
            "routing_summary": artifact.get("routing_summary"),
            "metric_groups": artifact.get("metric_groups") or {},
            "metrics": _sample_prompt_metrics(artifact.get("metrics") or [], PROMPT_METRIC_LIMIT),
            "metric_count": len(artifact.get("metrics") or []),
            "metric_time_ranges": artifact.get("metric_time_ranges") or artifact.get("metric_year_ranges") or {},
            "fields": (artifact.get("fields") or [])[:PROMPT_FIELD_LIMIT],
            "time_range": artifact.get("time_range") or artifact.get("year_range"),
            "feature_count": artifact.get("feature_count"),
            "row_count": artifact.get("row_count"),
            "summary": artifact.get("summary"),
            "scene_periods": (artifact.get("scene_periods") or [])[:PROMPT_SCENE_PERIOD_LIMIT],
            "raster_clip_levels": artifact.get("raster_clip_levels") or [],
            "foundation_helpers": artifact.get("foundation_helpers") or {},
        }
        return compact

    if tool_name == "bridge_loc_ids":
        compact["target_family"] = tool_result.get("target_family")
        compact["mapping_count"] = tool_result.get("mapping_count")
        compact["changed_count"] = tool_result.get("changed_count")
        compact["foundation_helper_family"] = tool_result.get("foundation_helper_family")
        compact["mappings_preview"] = (tool_result.get("mappings") or [])[:TOOL_ROWS_PREVIEW_LIMIT]
        return compact

    if tool_name in {"query_artifact_slice", "query_artifact_subset_join", "build_artifact_display_subset"}:
        rows = tool_result.get("rows") or []
        compact["rows_preview"] = rows[:TOOL_ROWS_PREVIEW_LIMIT]
        compact["preview_count"] = min(len(rows), TOOL_ROWS_PREVIEW_LIMIT)
        compact["returned_row_count"] = len(rows)
        compact["preview_note"] = (
            "rows_preview is only a capped sample of the returned rows. "
            "Use row_count for total matched rows and returned_row_count for rows actually returned by the tool."
        )
        if tool_name == "query_artifact_subset_join":
            compact["subset_artifact_id"] = tool_result.get("subset_artifact_id")
            compact["subset_row_count"] = tool_result.get("subset_row_count")
            compact["subset_loc_id_count"] = tool_result.get("subset_loc_id_count")
        if isinstance(tool_result.get("display_warning"), dict):
            compact["display_warning"] = tool_result.get("display_warning")
        if tool_name == "build_artifact_display_subset":
            geojson = tool_result.get("geojson") or {}
            compact["display"] = {
                "data_type": tool_result.get("data_type"),
                "source_id": tool_result.get("source_id"),
                "geographic_level": tool_result.get("geographic_level"),
                "fit": tool_result.get("fit"),
                "context_visibility": tool_result.get("context_visibility"),
                "feature_count": len((geojson.get("features") or [])),
                "loc_id_count": len(tool_result.get("loc_ids") or []),
                "year_count": len(tool_result.get("years") or []),
                "metric": tool_result.get("metric"),
            }
        return compact

    return tool_result
