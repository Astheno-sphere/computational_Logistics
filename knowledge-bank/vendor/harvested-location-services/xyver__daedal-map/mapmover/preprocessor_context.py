"""Tier-context formatting helpers extracted from preprocessor.py."""

from __future__ import annotations

import json
from typing import Callable

from .paths import DATA_ROOT
from .runtime.country_geography import build_country_geometry_alias_context_lines
from .runtime.source_hints import (
    build_pack_family_preference_guidance,
    build_query_specific_disaster_relationship_guidance,
    build_query_matched_metric_guidance,
    build_reference_summary,
    build_shared_disaster_relationship_guidance,
    build_source_routing_guidance,
    get_routing_hints,
)


def format_filter_description(filters: dict, overlay_type: str) -> str:
    """Format filter settings as a human-readable description."""
    if not filters:
        return "no filters"

    parts = []
    if overlay_type == "earthquakes":
        if filters.get("minMagnitude"):
            parts.append(f"mag >= {filters['minMagnitude']}")
        if filters.get("maxMagnitude"):
            parts.append(f"mag <= {filters['maxMagnitude']}")
    elif overlay_type == "hurricanes":
        if filters.get("minCategory"):
            parts.append(f"cat >= {filters['minCategory']}")
    elif overlay_type == "volcanoes":
        if filters.get("minVei"):
            parts.append(f"VEI >= {filters['minVei']}")
    elif overlay_type == "wildfires":
        if filters.get("minAreaKm2"):
            parts.append(f"area >= {filters['minAreaKm2']} km2")
    elif overlay_type == "tornadoes":
        if filters.get("minScale"):
            parts.append(f"scale >= EF{filters['minScale']}")

    return ", ".join(parts) if parts else "no filters"


def build_tier3_context(
    hints: dict,
    *,
    format_filter_description_func: Callable[[dict, str], str],
    get_countries_in_viewport: Callable[[dict], list],
    load_reference_file: Callable,
    reference_dir,
    load_source_metadata: Callable[[str], dict | None],
    get_source_path: Callable[[str], object],
    get_relevant_sources_with_metrics: Callable[[list, str | None], dict],
    logger,
    countries_dir: Path | None = None,
) -> str:
    """Build Tier 3 (Just-in-Time) context string from preprocessor hints."""
    context_parts = []

    if hints.get("summary"):
        context_parts.append(f"[Preprocessor hints: {hints['summary']}]")

    candidates = hints.get("candidates")
    if candidates:
        candidate_lines = ["[INTERPRETATION CANDIDATES - Review all options before deciding:]"]
        intents = candidates.get("intents", {}).get("candidates", [])
        if intents:
            candidate_lines.append("\nPossible intents (pick most likely based on full query):")
            for intent in intents[:3]:
                conf = intent.get("confidence", 0)
                itype = intent.get("type", "unknown")
                reason = f" [{intent.get('adjusted_reason')}]" if intent.get("adjusted_reason") else ""
                candidate_lines.append(f"  - {itype}: {conf:.2f}{reason}")

        sources = candidates.get("sources", {}).get("candidates", [])
        if sources:
            candidate_lines.append("\nPossible data sources mentioned:")
            for src in sources[:3]:
                conf = src.get("confidence", 0)
                name = src.get("source_name", "?")
                matched = src.get("matched_text", "")
                candidate_lines.append(f"  - {name}: {conf:.2f} (matched: '{matched}')")

        locations = candidates.get("locations", {}).get("candidates", [])
        if locations:
            candidate_lines.append("\nPossible locations:")
            for loc in locations[:5]:
                conf = loc.get("confidence", 0)
                term = loc.get("matched_term", "?")
                loc_id = loc.get("loc_id", loc.get("iso3", "?"))
                mtype = loc.get("match_type", "")
                penalty = ""
                if loc.get("penalized_reason") == "term_in_source_name":
                    penalty = " [LIKELY FALSE POSITIVE - term appears in source name]"
                candidate_lines.append(f"  - '{term}' -> {loc_id}: {conf:.2f} ({mtype}){penalty}")

        ignored_locations = candidates.get("locations", {}).get("ignored_locations", [])
        if ignored_locations:
            candidate_lines.append("\nIgnored location-like tokens:")
            for item in ignored_locations[:5]:
                term = item.get("term", "?")
                iso3 = item.get("iso3", "?")
                country_name = item.get("country_name", iso3)
                reason = item.get("reason", "ignored")
                candidate_lines.append(
                    f"  - '{term}' was not treated as {country_name} ({iso3}): {reason}"
                )

        if len(candidate_lines) > 1:
            candidate_lines.append("\nBased on the full query context, determine which interpretation is correct.")
            candidate_lines.append("If the query is about data/statistics, prefer data_request intent even if it starts with 'show me'.")
            context_parts.append("\n".join(candidate_lines))

    active_overlays = hints.get("active_overlays")
    if active_overlays and active_overlays.get("type"):
        overlay_type = active_overlays["type"]
        filters = active_overlays.get("filters", {})
        filter_desc = format_filter_description_func(filters, overlay_type)
        context_parts.append(f"[ACTIVE OVERLAY: {overlay_type}]")
        if filters:
            context_parts.append(f"[CURRENT FILTERS: {filter_desc}]")

    overlay_intent = hints.get("overlay_intent")
    if overlay_intent:
        overlay = overlay_intent.get("overlay", "unknown")
        action = overlay_intent.get("action", "unknown")
        is_active = overlay_intent.get("is_active", False)
        severity = overlay_intent.get("severity")
        if action == "enable" and not is_active:
            context_parts.append(
                f"[OVERLAY INTENT: User mentioned '{overlay}' but overlay is NOT active. "
                f"Consider responding with overlay_toggle to enable {overlay} overlay.]"
            )
        elif action == "filter" and severity:
            severity_str = ", ".join(f"{k}={v}" for k, v in severity.items())
            context_parts.append(
                f"[OVERLAY INTENT: User wants to filter {overlay} with: {severity_str}. "
                f"Respond with filter_update or overlay_toggle with filters.]"
            )

    cache_stats = hints.get("cache_stats")
    if cache_stats:
        for overlay_id, stats in cache_stats.items():
            count = stats.get("count", 0)
            if count > 0:
                extra_info = []
                if stats.get("minMag") is not None:
                    extra_info.append(f"mag {stats['minMag']}-{stats.get('maxMag', '?')}")
                if stats.get("years"):
                    years = stats["years"]
                    if years:
                        extra_info.append(f"years {years[0]}-{years[-1]}")
                info_str = f" ({', '.join(extra_info)})" if extra_info else ""
                context_parts.append(f"[CACHE: {count} {overlay_id} loaded{info_str}]")

    loaded_data = hints.get("loaded_data")
    if loaded_data:
        loaded_lines = []
        for entry in loaded_data:
            src = entry.get("source_id", "unknown")
            region = entry.get("region", "global")
            metric = entry.get("metric")
            years = entry.get("years", "")
            overlay_type = entry.get("overlay_type")
            if overlay_type:
                loaded_lines.append(f"- {src}: {overlay_type} overlay for {region}")
            elif metric:
                loaded_lines.append(f"- {src}: {metric} for {region} ({years})")
            else:
                loaded_lines.append(f"- {src}: {region} ({years})")
        if loaded_lines:
            context_parts.append("[LOADED DATA - use this to match regions for removal requests]\n" + "\n".join(loaded_lines))

    explicit_location = hints.get("location")
    viewport = hints.get("viewport")
    if viewport:
        admin_level = viewport.get("adminLevel", 0)
        level_names = {0: "countries", 1: "states/provinces", 2: "counties/districts", 3: "subdivisions"}
        level_name = level_names.get(admin_level, f"level {admin_level}")
        context_parts.append(f"[VIEWPORT: User is viewing at {level_name} level]")

        zoom_level = viewport.get("zoom", 0)
        if not explicit_location and viewport.get("bounds") and zoom_level >= 3:
            countries_in_view = get_countries_in_viewport(viewport["bounds"])
            if len(countries_in_view) == 1:
                iso3 = countries_in_view[0]
                iso_data = load_reference_file(reference_dir / "iso_codes.json")
                country_name = iso_data.get("iso3_to_name", {}).get(iso3, iso3) if iso_data else iso3
                context_parts.append(
                    f"[INFERRED LOCATION: User appears to be viewing {country_name} ({iso3}). "
                    f"Use this country's data sources unless they specify otherwise.]"
                )

    disambiguation = hints.get("disambiguation")
    if disambiguation and disambiguation.get("needed"):
        options = disambiguation.get("options", [])
        term = disambiguation.get("query_term", "location")
        option_strs = []
        for i, opt in enumerate(options[:5], 1):
            loc_id = opt.get("loc_id", "")
            country = opt.get("country_name", opt.get("iso3", ""))
            option_strs.append(f"{i}. {opt.get('matched_term', term).title()} in {country} ({loc_id})")
        context_parts.append(
            f"[DISAMBIGUATION REQUIRED: '{term}' matches {len(options)} locations. "
            f"Ask user to clarify which one:\n" + "\n".join(option_strs) + "]"
        )
        return "\n".join(context_parts)

    location = hints.get("location")
    if location:
        location_loc_id = str(location.get("loc_id") or location.get("iso3") or "").strip()
        if location.get("is_subregion"):
            context_parts.append(
                f"[LOCATION RESOLUTION: '{location['matched_term']}' is in {location['country_name']}. "
                f"Use loc_id={location_loc_id} for data queries about {location['matched_term']}]"
            )
        else:
            context_parts.append(f"[LOCATION: {location['country_name']} (loc_id={location_loc_id})]")

        iso3 = location.get("iso3")
        if iso3 and countries_dir:
            try:
                context_lines = build_country_geometry_alias_context_lines(iso3)
                if context_lines:
                    context_parts.append(
                        f"[COUNTRY GEOMETRY ALIASES FOR {iso3}]\n" + "\n".join(context_lines)
                    )
            except Exception as e:
                logger.debug(f"Could not load crosswalk alias context for {iso3}: {e}")

    detected_source = hints.get("detected_source")
    if detected_source:
        source_id = detected_source.get("source_id")
        source_name = detected_source.get("source_name")
        metadata = load_source_metadata(source_id)
        if metadata:
            metrics = metadata.get("metrics", {})
            temporal = metadata.get("temporal_coverage", {})
            year_range = f"{temporal.get('start', '?')}-{temporal.get('end', '?')}"
            routing_hints = get_routing_hints(metadata)
            metrics_mapping = {}
            for col, info in metrics.items():
                human_name = info.get("name", col)
                if len(human_name) > 80:
                    human_name = human_name[:77] + "..."
                metrics_mapping[col] = human_name

            reference_context = ""
            try:
                source_path = get_source_path(source_id)
                ref_path = source_path / "reference.json"
                if ref_path.exists():
                    with open(ref_path, encoding="utf-8") as f:
                        ref_data = json.load(f)
                    summary = build_reference_summary(ref_data)
                    if summary:
                        reference_context = "\n" + summary
            except Exception:
                pass

            msg = f"[SOURCE DETECTED: {source_name}]"
            msg += f"\nYears: {year_range}. Total metrics: {len(metrics)}."
            if reference_context:
                msg += reference_context
            pack_id = str((metadata or {}).get("pack_id") or "").strip()
            if pack_id:
                try:
                    pack_ref_path = DATA_ROOT / "packs" / pack_id / "reference.json"
                    if pack_ref_path.exists():
                        with open(pack_ref_path, encoding="utf-8") as f:
                            pack_ref_data = json.load(f)
                        pack_summary = build_reference_summary(pack_ref_data)
                        if pack_summary:
                            msg += "\n" + pack_summary
                except Exception:
                    pass
                relationship_guidance = build_shared_disaster_relationship_guidance(pack_id)
                if relationship_guidance:
                    msg += "\n" + relationship_guidance
                relationship_query_guidance = build_query_specific_disaster_relationship_guidance(
                    hints.get("original_query"),
                    pack_id,
                )
                if relationship_query_guidance:
                    msg += "\n" + relationship_query_guidance
            msg += "\n\nALL METRICS (use column name in JSON 'metric' field, human name when talking to user):\n"
            for col, human in metrics_mapping.items():
                msg += f'  "{col}": {human}\n'
            routing_lines = build_source_routing_guidance(metadata, source_id)
            if routing_lines:
                msg += "\n\nROUTING GUIDANCE:\n"
                for line in routing_lines:
                    msg += f"- {line}\n"
            matched_metric_lines = build_query_matched_metric_guidance(
                metadata,
                hints.get("original_query"),
            )
            if matched_metric_lines:
                msg += "\nQUERY-MATCHED METRIC GUIDANCE:\n"
                for line in matched_metric_lines:
                    msg += f"- {line}\n"
            pack_family_lines = build_pack_family_preference_guidance(
                detected_source,
                hints.get("candidates", {}).get("sources", {}),
            )
            if pack_family_lines:
                msg += "\nPACK FAMILY GUIDANCE:\n"
                for line in pack_family_lines:
                    msg += f"- {line}\n"
            msg += "\n(REPLY RULES: When listing metrics to user, show max 10 and use human names only. Say 'I can get them all' not '*'.)"
            context_parts.append(msg)

    if hints.get("regions"):
        for region in hints["regions"][:3]:
            context_parts.append(f"Region '{region['match']}' = {region['grouping']} ({region['count']} countries)")

    if hints.get("time", {}).get("is_time_series"):
        time = hints["time"]
        if time.get("year_start") and time.get("year_end"):
            context_parts.append(f"User wants data from {time['year_start']} to {time['year_end']}")

    query_constraints = hints.get("query_constraints") or {}
    region_loc_id = str(query_constraints.get("region_loc_id") or "").strip()
    if region_loc_id:
        context_parts.append(f"Canonical region filter: loc_id prefix {region_loc_id}")
    area_constraint = query_constraints.get("area_constraint") or {}
    if area_constraint.get("normalized_value") is not None:
        context_parts.append(
            "Canonical numeric filter: "
            f"{area_constraint.get('normalized_field')} >= {float(area_constraint['normalized_value']):.5f} "
            f"({area_constraint.get('source_value')} {area_constraint.get('source_unit')})"
        )

    topics = hints.get("topics", [])
    iso3 = None
    if location:
        iso3 = location.get("iso3")
    elif hints.get("navigation") and hints["navigation"].get("locations"):
        nav_locs = hints["navigation"]["locations"]
        if nav_locs and nav_locs[0].get("iso3"):
            iso3 = nav_locs[0]["iso3"]
    elif viewport and not explicit_location:
        zoom_level = viewport.get("zoom", 0)
        if viewport.get("bounds") and zoom_level >= 3:
            countries_in_view = get_countries_in_viewport(viewport["bounds"])
            if len(countries_in_view) == 1:
                iso3 = countries_in_view[0]
                logger.debug(f"Using viewport-inferred country: {iso3}")

    if topics or iso3:
        source_hints = get_relevant_sources_with_metrics(topics, iso3)
        relevant_sources = source_hints.get("sources", [])
        country_summary = source_hints.get("country_summary")
        country_index = source_hints.get("country_index")

        if country_index:
            datasets = country_index.get("datasets", [])
            admin_levels = country_index.get("admin_levels", [])
            admin_counts = country_index.get("admin_counts", {})
            if datasets:
                level_info = []
                for level in admin_levels:
                    count = admin_counts.get(str(level))
                    if count:
                        level_info.append(f"admin_{level}={count}")
                admin_str = f" ({', '.join(level_info)})" if level_info else ""
                context_parts.append(f"[COUNTRY DATASETS: {', '.join(datasets)}{admin_str}]")

        if country_summary:
            context_parts.append(f"[COUNTRY DATA SUMMARY: {country_summary}]")

        if relevant_sources:
            country_sources = [s for s in relevant_sources if s.get("is_country_source")]
            global_sources = [s for s in relevant_sources if not s.get("is_country_source")]
            hints_lines = [
                "[CRITICAL - EXACT METRIC NAMES FOR ORDER JSON ONLY:]",
                "Use these EXACT column names in your JSON orders. But NEVER show column names to the user - only show the human-readable name in parentheses:",
            ]
            for src in country_sources[:3]:
                metrics_list = [f'"{m["column"]}" ({m["name"]})' for m in src["metrics"]]
                hints_lines.append(f"- {src['source_id']}: [{', '.join(metrics_list)}]")
            for src in global_sources[:2]:
                metrics_list = [f'"{m["column"]}" ({m["name"]})' for m in src["metrics"][:5]]
                hints_lines.append(f"- {src['source_id']}: [{', '.join(metrics_list)}]")
            if len(hints_lines) > 2:
                context_parts.append("\n".join(hints_lines))

    return "\n".join(context_parts) if context_parts else ""


def build_tier4_context(hints: dict) -> str:
    """Build Tier 4 (Reference) context string from preprocessor hints."""
    ref_lookup = hints.get("reference_lookup")
    if not ref_lookup:
        return ""

    ref_type = ref_lookup["type"]
    country_data = ref_lookup.get("country_data")
    if country_data:
        formatted = country_data.get("formatted", "")
        return f"[REFERENCE ANSWER: {formatted}]"

    content = ref_lookup.get("content")
    if ref_type == "sdg" and content:
        goal = content.get("goal", {})
        parts = [
            f"SDG {goal.get('number')}: {goal.get('name')}",
            f"Full title: {goal.get('full_title')}",
            f"Description: {goal.get('description')}",
        ]
        if goal.get("targets"):
            parts.append("Targets:")
            for target in goal["targets"][:5]:
                parts.append(f"  {target['id']}: {target['text']}")
        return "\n".join(parts)

    if ref_type == "data_source" and content:
        about = content.get("about", {})
        this_dataset = content.get("this_dataset", {})
        parts = [
            f"Data Source: {about.get('name', 'Unknown')}",
            f"Publisher: {about.get('publisher', 'Unknown')}",
            f"URL: {about.get('url', 'N/A')}",
            f"License: {about.get('license', 'Unknown')}",
        ]
        if about.get("history"):
            parts.append(f"Background: {about['history'][:200]}...")
        if this_dataset.get("focus"):
            parts.append(f"Focus: {this_dataset['focus']}")
        return "\n".join(parts)

    if ref_type == "capital":
        return "[Reference: Country capital data available. Ask about a specific country.]"
    if ref_type == "currency":
        return "[Reference: Currency data for 215 countries available from World Factbook. Ask about a specific country.]"
    if ref_type == "language":
        return "[Reference: Language data for 200+ countries available from World Factbook. Ask about a specific country.]"
    if ref_type == "timezone":
        return "[Reference: Timezone data for 200+ countries available from World Factbook. Ask about a specific country.]"
    if ref_type in ["country_info", "economy_info", "government_info", "trade_info"]:
        return "[Reference: Detailed country information available from World Factbook.]"

    if ref_type == "system_help" and content:
        about = content.get("about", {})
        how = content.get("how_it_works", {})
        capabilities = content.get("capabilities", [])
        examples = content.get("example_queries", {})
        tips = content.get("tips", [])
        parts = [
            "[SYSTEM HELP REFERENCE]",
            f"Name: {about.get('name', 'Geographic Data Explorer')}",
            f"Description: {about.get('description', '')}",
            "",
            f"How it works: {how.get('summary', '')}",
            "",
            "Capabilities:",
        ]
        for cap in capabilities:
            parts.append(f"  - {cap}")
        parts.append("")
        parts.append("Example queries the user can try:")
        for category, queries in examples.items():
            parts.append(f"  {category}:")
            for q in queries[:2]:
                parts.append(f'    - "{q}"')
        parts.append("")
        parts.append("Tips:")
        for tip in tips[:3]:
            parts.append(f"  - {tip}")
        return "\n".join(parts)

    return ""
