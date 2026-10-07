from __future__ import annotations

from access_policy_shared import resolve_effective_access
from tool_access_shared import (
    tool_account_item_limit,
    tool_free_item_limit,
    tool_inline_item_limit,
    tool_is_paid_bulk,
    tool_paid_item_limit,
    tool_pricing,
)

# Shared structured registry for the live agent/API/MCP pack set.
# This is the intended single authored source for:
# - published pack order
# - free vs paid pricing lane
# - MCP facade metadata
# - public display names
# - preferred MCP routing hints
#
# Keep this module stdlib-only so runtime, site, stdio, and helper scripts can
# import it safely.

PACK_REGISTRY: dict[str, dict] = {
    "earthquakes": {
        "display_name": "earthquakes",
        "pricing": "paid_x402_base_usdc",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("largest_earthquake_in_range", "count_disaster_events"),
        "mcp_name": "com.daedalmap/earthquakes",
        "mcp_title": "DaedalMap Earthquake Data",
        "mcp_description": "Historical earthquake events from 2150 BC to present. Paid per call from account credit. Small queries stay cheap; very broad scans cost more or need narrower filters. Call unpaid first to see the exact price before committing.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "Historical earthquake event data with structured filters",
                "Paid MCP access for earthquake counts and event rows",
                "Country and region lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "floods": {
        "display_name": "floods",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("count_disaster_events",),
        "mcp_name": "com.daedalmap/floods",
        "mcp_title": "DaedalMap Flood Events",
        "mcp_description": "Global large flood events from 1985 to present from the Dartmouth Flood Observatory Global Flood Records (CC0 public domain), including flood extent polygons, fatalities, displaced, severity, main cause, and a flood impact index, plus MODIS satellite-mapped extents from the Global Flood Database. Free - no payment required.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "Global flood event records 1985-present with extent polygons",
                "Free MCP access for flood counts, fatalities, displaced, and severity",
                "Country and region lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "hurricanes": {
        "display_name": "hurricanes",
        "pricing": "paid_x402_base_usdc",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("count_disaster_events",),
        "mcp_name": "com.daedalmap/hurricanes",
        "mcp_title": "DaedalMap Hurricane and Tropical Cyclone Data",
        "mcp_description": "Global tropical cyclone tracks from IBTrACS, 1842-present. Wind, pressure, and paths. Paid per call from account credit. Small queries stay cheap; very broad scans cost more or need narrower filters. Call unpaid first to see the exact price before committing.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "Global tropical cyclone and hurricane track records",
                "Paid MCP access for hurricane and cyclone event queries",
                "Country and basin lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "tornadoes": {
        "display_name": "tornadoes",
        "pricing": "paid_x402_base_usdc",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("count_disaster_events",),
        "mcp_name": "com.daedalmap/tornadoes",
        "mcp_title": "DaedalMap Tornado Events",
        "mcp_description": "United States tornado events from 1950 to present from the NOAA Storm Prediction Center, including track paths, EF/Fujita intensity ratings, casualties, and damage estimates. Paid per call from account credit. Small queries stay cheap; very broad scans cost more or need narrower filters. Call unpaid first to see the exact price before committing.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "US tornado event records 1950-present with track paths and intensity",
                "Paid MCP access for tornado counts, casualties, and damage estimates",
                "State and region lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "tsunamis": {
        "display_name": "tsunamis",
        "pricing": "paid_x402_base_usdc",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("count_disaster_events",),
        "mcp_name": "com.daedalmap/tsunamis",
        "mcp_title": "DaedalMap Tsunami Data",
        "mcp_description": "Historical tsunami events from 2000 BC to present. Paid per call from account credit. Small queries stay cheap; very broad scans cost more or need narrower filters. Call unpaid first to see the exact price before committing.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "Historical tsunami event data and wave-height metrics",
                "Paid MCP access for tsunami counts and event rows",
                "Country and coastal-region lookups tied to DaedalMap geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "wildfires": {
        "display_name": "wildfires",
        "pricing": "paid_x402_base_usdc",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("count_disaster_events",),
        "mcp_name": "com.daedalmap/wildfires",
        "mcp_title": "DaedalMap Wildfire Events",
        "mcp_description": "Global, U.S., and Canada wildfire event and aggregate data, including burned area, duration, and source-aware regional routing. Paid per call from account credit. Start with an unpaid call to inspect the exact price before committing.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "Source-aware wildfire coverage across global, U.S., and Canada event lanes",
                "Paid MCP access for wildfire event discovery, burned-area questions, and regional rollups",
                "Country, province, state, and county lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "un_sdg": {
        "display_name": "UN SDG",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/un_sdg",
        "mcp_title": "DaedalMap UN Sustainable Development Goals",
        "mcp_description": "UN Sustainable Development Goal indicators across all 17 goals - poverty, health, education, gender, energy, climate, and institutions - as curated country-year panels normalized to the DaedalMap loc_id spine. Free.",
        "registry_meta": {
            "categories": ["development", "data", "geospatial"],
            "highlights": [
                "210 curated SDG indicators across all 17 goal families",
                "Normalized country-year panels on the shared DaedalMap loc_id spine",
                "Free MCP access; complements World Development Indicators and country reference data",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "world_bank_wdi": {
        "display_name": "World Bank WDI",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/world-development-indicators",
        "mcp_title": "DaedalMap World Development Indicators",
        "mcp_description": "World Bank World Development Indicators as curated country-year panels: economy, health, education, environment, debt, infrastructure, and social - normalized to the DaedalMap loc_id spine with tiered metrics. Free.",
        "registry_search_alias": "world-development-indicators",
        "registry_meta": {
            "categories": ["development", "economics", "data", "geospatial"],
            "highlights": [
                "Curated World Development Indicators across seven category sources",
                "Free MCP access for economic, health, education, and environment metrics",
                "Country-level lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "un_wpp": {
        "display_name": "UN World Population Prospects",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/world-population-prospects",
        "mcp_title": "DaedalMap UN World Population Prospects",
        "mcp_description": "UN World Population Prospects country-year population, births, deaths, migration, and life expectancy metrics from 1950 through projections to 2100. Free.",
        "registry_search_alias": "world-population-prospects",
        "registry_meta": {
            "categories": ["demographic", "development", "data", "geospatial"],
            "highlights": [
                "UN WPP historical estimates and medium-variant projections",
                "Free MCP access for population, fertility, mortality, and migration metrics",
                "Country-level lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "nri": {
        "display_name": "FEMA NRI",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/fema-nri",
        "mcp_title": "DaedalMap FEMA National Risk Index",
        "mcp_description": "FEMA National Risk Index county hazard-risk layers, including baseline risk, expected annual loss, social vulnerability, resilience, and selected future scenario fields. Free.",
        "registry_search_alias": "fema-nri",
        "registry_meta": {
            "categories": ["hazard", "risk", "geospatial", "data"],
            "highlights": [
                "County-level FEMA National Risk Index hazard members",
                "Free MCP access for risk scores, expected annual loss, social vulnerability, and resilience",
                "USA county loc_id filtering for hazard-specific risk layers",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "cejst": {
        "display_name": "CEJST",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/cejst",
        "mcp_title": "DaedalMap Climate and Economic Justice Screening Tool",
        "mcp_description": "CEJST v2.0 U.S. census-tract disadvantaged-community classifications, burden-category flags, and supporting burden metrics. Free.",
        "registry_meta": {
            "categories": ["environmental-justice", "policy", "geospatial", "data"],
            "highlights": [
                "CEJST v2.0 disadvantaged-community classifications",
                "Burden-category flags and supporting tract metrics",
                "U.S. census-tract lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "era5_land_temperature": {
        "display_name": "ERA5-Land Temperature",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/era5-land-temperature",
        "mcp_title": "DaedalMap ERA5-Land Temperature",
        "mcp_description": "Historical monthly ERA5-Land 2-metre air temperature and anomaly data with global raster coverage and country comparisons. Free.",
        "registry_meta": {
            "categories": ["climate", "temperature", "geospatial", "data"],
            "highlights": [
                "Historical monthly 2-metre air temperature",
                "Temperature anomalies and country comparisons",
                "ERA5 reanalysis with global raster coverage",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "nws_alerts": {
        "display_name": "NWS Historical Alerts",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_name": "com.daedalmap/nws-alerts",
        "mcp_title": "DaedalMap NWS Historical Alerts",
        "mcp_description": "Historical U.S. National Weather Service watches, warnings, and advisories from the IEM VTEC archive, including lifecycle records, affected areas, available warning polygons, and bulletin text. Free.",
        "registry_meta": {
            "categories": ["weather", "hazard", "geospatial", "data"],
            "highlights": [
                "Historical NWS watch, warning, and advisory lifecycles",
                "Affected counties and native warning polygons where available",
                "Event retrieval with preserved bulletin text",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "usa_cbp": {
        "display_name": "U.S. County Business Patterns",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/usa-county-business-patterns",
        "mcp_title": "DaedalMap U.S. County Business Patterns",
        "mcp_description": "Annual county-level establishments, employment, payroll, and establishment-size structure by NAICS from the U.S. Census County Business Patterns program. Free.",
        "registry_meta": {
            "categories": ["economic", "business", "geospatial", "data"],
            "highlights": [
                "County-level establishments, employment, and payroll",
                "NAICS industry and establishment-size detail",
                "Annual U.S. county lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "usa_lodes": {
        "display_name": "U.S. LEHD LODES",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/usa-lodes",
        "mcp_title": "DaedalMap U.S. LEHD LODES",
        "mcp_description": "Annual census-tract workplace job counts by industry and worker characteristics from the U.S. Census LEHD LODES program. Free.",
        "registry_meta": {
            "categories": ["economic", "employment", "geospatial", "data"],
            "highlights": [
                "Census-tract workplace job counts",
                "Industry and worker-characteristic dimensions",
                "Annual U.S. tract lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "usa_opportunity_zones": {
        "display_name": "U.S. Opportunity Zones",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/usa-opportunity-zones",
        "mcp_title": "DaedalMap U.S. Opportunity Zones",
        "mcp_description": "Federal Opportunity Zone designation and eligibility status by U.S. census tract across the 2010 and 2020 tract vintages. Free.",
        "registry_meta": {
            "categories": ["economic-policy", "investment", "geospatial", "data"],
            "highlights": [
                "OZ 1.0 designated and OZ 2.0 eligible census tracts",
                "2010-to-2020 tract-vintage crosswalk support",
                "U.S. census-tract lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "usa_susb": {
        "display_name": "U.S. Statistics of U.S. Businesses",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/usa-susb",
        "mcp_title": "DaedalMap Statistics of U.S. Businesses",
        "mcp_description": "Annual county-level firms, establishments, employment, payroll, receipts, and enterprise-size structure by NAICS from the U.S. Census SUSB program. Free.",
        "registry_meta": {
            "categories": ["economic", "business", "geospatial", "data"],
            "highlights": [
                "County-level firms, establishments, employment, and receipts",
                "NAICS industry and enterprise-size detail",
                "Annual U.S. county lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {"preferred_tool": "get_data"},
    },
    "volcanoes": {
        "display_name": "volcanoes",
        "pricing": "free",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data", "get_event"),
        "mcp_prompt_allowlist": ("count_disaster_events",),
        "mcp_name": "com.daedalmap/volcanoes",
        "mcp_title": "DaedalMap Volcanic Activity",
        "mcp_description": "Historical volcanic eruption records from Holocene to present, including VEI and location data. Free - no payment required.",
        "registry_meta": {
            "categories": ["hazard", "geospatial", "data"],
            "highlights": [
                "Historical volcanic eruption records and VEI data",
                "Free MCP access for volcanic activity queries",
                "Country and region lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "world_factbook": {
        "display_name": "World Factbook",
        "pricing": "paid_x402_base_usdc",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "get_data"),
        "mcp_name": "com.daedalmap/world_factbook",
        "mcp_title": "DaedalMap CIA World Factbook",
        "mcp_description": "CIA World Factbook country indicators for infrastructure, energy, demographics, and economy. Paid per call from account credit. Small queries stay cheap; very broad scans cost more or need narrower filters. Call unpaid first to see the exact price before committing.",
        "registry_meta": {
            "categories": ["economic", "data", "geospatial"],
            "highlights": [
                "111 CIA World Factbook indicators from 2002-2026 editions",
                "Paid MCP access for country infrastructure and economy metrics",
                "Country-level lookups tied to DaedalMap loc_id geography",
            ],
        },
        "routing": {
            "preferred_tool": "get_data",
        },
    },
    "geography": {
        "display_name": "Geography Tools",
        "kind": "tool_family",
        "pricing": "mixed",
        "mcp_tool_allowlist": (
            "get_catalog",
            "get_pack",
            "identify_dataset_geography",
            "identify_reference_system",
            "convert_reference",
            "compare_geographies",
            "get_geometry",
            "resolve_point",
            "resolve_deep_point",
            "get_loc_id_info",
        ),
        "mcp_name": "com.daedalmap/geography",
        "mcp_version": "1.6.2",
        "mcp_title": "DaedalMap Geography Tools (loc_id)",
        "mcp_description": "Geography utilities built on the DaedalMap loc_id spine. Identify dataset geography, recognize and convert external references, resolve shallow or deep coordinate batches, inspect loc_ids, compare places, and retrieve bounded shapes. Future estimate/create/status workflows remain private until durable job delivery is ready.",
        "registry_meta": {
            "categories": ["geospatial", "geocoding", "data"],
            "highlights": [
                "Catalog-backed reference exchange: external geography systems <-> DaedalMap loc_id",
                "Convert ZIP/ZCTA, tribal, NWS public zones, and NWS fire weather zones through the same loc_id spine",
                "Compact reverse geocoding: latitude/longitude to the available administrative chain and coverage status",
                "Boundary and bounding-box lookup for any loc_id",
                "Inspect loc_id identity, lifecycle, hierarchy, references, and geometry coverage",
            ],
        },
        "routing": {
            "preferred_tool": "get_catalog",
        },
        "tool_summaries": (
            {"name": "get_tool_help", "summary": "per-tool contracts plus topic-level workflows and the loc_id mental model"},
            {"name": "get_catalog", "summary": "discover geometry families and the countries where each exists"},
            {"name": "get_pack", "summary": "inspect one geometry family globally or within one country"},
            {"name": "identify_dataset_geography", "summary": "bounded table-column samples -> ranked geography column, country, level, and reference binding"},
            {"name": "identify_reference_system", "summary": "unknown or declared identifiers -> ranked reference systems and matching geometry banks"},
            {"name": "convert_reference", "summary": "one reference or reference batch -> loc_id by default, or any target system through loc_id"},
            {"name": "compare_geographies", "summary": "two loc_ids -> supported containment/common-ancestry and temporal-validity evidence"},
            {"name": "get_geometry", "summary": "loc_id, loc_ids, or admin scope -> available/missing shape preflight, metadata, and optional polygons"},
            {"name": "resolve_point", "summary": "one point or point array -> compact Admin 0-3 chains and Admin 1 routing keys"},
            {"name": "resolve_deep_point", "summary": "one point or scoped point array + one Admin 1 loc_id -> compact Admin 4-6 chains"},
            {"name": "get_loc_id_info", "summary": "loc_id or loc_id array -> available data packs and geometry families, with executable next calls"},
        ),
    },
    "reverse-geocoding": {
        "display_name": "Reverse Geocoding",
        "kind": "tool_family_alias",
        "pricing": "mixed",
        "mcp_tool_allowlist": ("get_catalog", "get_pack", "resolve_point", "resolve_deep_point"),
        "mcp_name": "com.daedalmap/reverse-geocoding",
        "mcp_version": "1.4.2",
        "mcp_title": "DaedalMap Reverse Geocoding (coordinates to loc_id)",
        "mcp_description": "Two reverse-geocoding tools accept one point or a bounded point array. resolve_point returns available Admin 0-3 levels; resolve_deep_point uses a returned Admin 1 loc_id for available Admin 4-6 levels.",
        "registry_meta": {
            "categories": ["geospatial", "geocoding", "data"],
            "highlights": [
                "Latitude/longitude to available administrative levels with coverage status",
                "Small point batches in one MCP call for table cleanup",
                "Small chain rows with loc_id, name, level, and available vintage",
                "The first 100 points per call are free; larger hosted batches use paid throughput",
            ],
        },
        "routing": {"preferred_tool": "resolve_point"},
        "tool_summaries": (
            {"name": "resolve_point", "summary": "one point or point array -> compact Admin 0-3 chains"},
            {"name": "resolve_deep_point", "summary": "one point or scoped point array + one Admin 1 loc_id -> compact Admin 4-6 chains"},
        ),
    },
    "boundaries": {
        "display_name": "Boundaries",
        "kind": "tool_family_alias",
        "pricing": "mixed",
        "mcp_tool_allowlist": (
            "get_catalog",
            "get_pack",
            "get_geometry",
            "compare_geographies",
            "get_loc_id_info",
        ),
        "mcp_name": "com.daedalmap/boundaries",
        "mcp_version": "1.3.2",
        "mcp_title": "DaedalMap Administrative Boundaries (loc_id to polygon)",
        "mcp_description": "Inspect loc_id identity and relationships, then retrieve bounded boundary metadata, bounding boxes, centroids, or polygons for exact loc_ids and supported administrative scopes.",
        "registry_meta": {
            "categories": ["geospatial", "boundaries", "data"],
            "highlights": [
                "Bounding box and centroid for any loc_id",
                "Full boundary polygon on request",
                "Clip or index your own grid/raster data against administrative areas",
            ],
        },
        "routing": {"preferred_tool": "get_geometry"},
        "tool_summaries": (
            {"name": "get_geometry", "summary": "exact loc_ids or admin scope -> availability, shape metadata, and optional polygons"},
            {"name": "compare_geographies", "summary": "two loc_ids -> supported containment/common-ancestry and temporal-validity evidence"},
            {"name": "get_loc_id_info", "summary": "loc_id or loc_id array -> available data packs and geometry families, with executable next calls"},
        ),
    },
}


def pack_kind(pack_id: str | None) -> str:
    profile = PACK_REGISTRY.get(str(pack_id or "").strip()) or {}
    return str(profile.get("kind") or "data_pack")


def published_pack_ids() -> tuple[str, ...]:
    # Data packs only. Tool families (e.g. geography) are listed separately via
    # tool_family_ids() so existing pack/catalog/llms surfaces stay unchanged.
    return tuple(pid for pid, p in PACK_REGISTRY.items() if str(p.get("kind") or "data_pack") == "data_pack")


def tool_family_ids() -> tuple[str, ...]:
    return tuple(pid for pid, p in PACK_REGISTRY.items() if str(p.get("kind") or "data_pack") == "tool_family")


def tool_family_alias_ids() -> tuple[str, ...]:
    # Registry-discovery-only facades that route to the same geography tools under
    # their own searchable name/endpoint (the disaster-pack pattern). Excluded
    # from tool_family_ids() so the catalog still shows one geography family.
    return tuple(pid for pid, p in PACK_REGISTRY.items() if str(p.get("kind") or "data_pack") == "tool_family_alias")


def tool_family_catalog_entry(pack_id: str | None) -> dict:
    normalized = str(pack_id or "").strip()
    profile = PACK_REGISTRY.get(normalized) or {}
    pricing = str(profile.get("pricing") or "free")
    tools = []
    for raw_tool in profile.get("tool_summaries") or ():
        tool = dict(raw_tool)
        name = str(tool.get("name") or "")
        limits = {
            "free_item_limit": tool_free_item_limit(name),
            "account_item_limit": tool_account_item_limit(name),
            "paid_item_limit": tool_paid_item_limit(name),
            "inline_item_limit": tool_inline_item_limit(name),
        }
        tool["access"] = {
            "pricing": tool_pricing(name),
            "limits": {key: value for key, value in limits.items() if value is not None},
        }
        tool["effective_access"] = resolve_effective_access(
            resource_kind="tool",
            resource_id=name,
            authored_pricing=tool_pricing(name),
            # This public discovery projection answers what the operator policy
            # does to an otherwise eligible tool. Exact geometry licence and
            # release clearance are rechecked by the execution route.
            license_permissions={"paid"},
        )
        tools.append(tool)
    paid_tools = [tool["name"] for tool in tools if tool_is_paid_bulk(str(tool.get("name") or ""))]
    return {
        "pack_id": normalized,
        "kind": "tool_family",
        "display_name": str(profile.get("display_name") or normalized.replace("_", " ")),
        "title": profile.get("mcp_title"),
        "description": profile.get("mcp_description"),
        "pricing": pricing,
        "paid_data_calls": pricing != "free",
        "effective_paid_data_calls": any(
            bool((tool.get("effective_access") or {}).get("settlement_required"))
            for tool in tools
        ),
        "tools": tools,
        "access_summary": {
            "model": "mixed" if paid_tools else "free",
            "free_discovery_tool": "get_tool_help",
            "paid_bulk_tools": paid_tools,
            "rule": "Paying raises throughput; it does not unlock different geography data.",
            "trusted_artifact_qa": "Bypasses route/tool call limits, item caps, and payment challenges with a separately labeled analytics lane.",
        },
        "shared_discovery_tools": [
            {"name": "get_tool_help", "pricing": "free", "summary": "usage contract and working example for any tool visible on this facade"}
        ],
    }


def agent_data_workflow() -> tuple[dict, ...]:
    """Registry-owned first-call flow used by generated human documentation."""
    visible = {
        str(tool)
        for profile in PACK_REGISTRY.values()
        for tool in profile.get("mcp_tool_allowlist") or ()
    }
    steps = (
        ("get_catalog", "Choose one pack_id from its topic, geography, and time coverage."),
        ("get_pack", "Choose exact metrics, dimensions, filters, geography, and time bounds."),
        ("get_data", "Return the requested published data rows."),
    )
    missing = [name for name, _outcome in steps if name not in visible]
    if missing:
        raise ValueError(f"agent data workflow references hidden tools: {missing}")
    return tuple({"tool": name, "outcome": outcome} for name, outcome in steps)


def tool_family_pack_detail(pack_id: str | None) -> dict:
    normalized = str(pack_id or "").strip()
    profile = PACK_REGISTRY.get(normalized) or {}
    entry = tool_family_catalog_entry(normalized)
    tools = [dict(tool) for tool in entry.get("tools") or ()]
    preferred_tool = str((profile.get("routing") or {}).get("preferred_tool") or "").strip()
    first_arguments: dict[str, object]
    start_here: list[str]
    important_rules: list[str]
    if preferred_tool == "get_catalog":
        first_arguments = {"catalog": "geometry", "detail": "lite"}
        start_here = [
            "Call get_catalog with catalog='geometry' to see each geometry family and the countries where it exists.",
            "Call get_pack for one family; add country_scope only when country-specific versions, vintages, levels, or artifacts are needed.",
            "Use identify_dataset_geography when the caller has a table sample but has not selected or classified its geography column.",
            "Use identify_reference_system when the caller has identifier values but needs to discover or verify their system, level, vintage, and shape bank. Translate natural language into the strict schema first and preserve identifiers as strings with leading zeros.",
            "Use convert_reference for outside identifiers or names; omit to_system to return loc_id, or provide it for another system.",
        ]
        important_rules = [
            "These are direct utility tools, not a get_data pack; discovery and small calls are free, while hosted resolve_point arrays follow the applicable access policy.",
            "loc_id is the reserve identifier: generic conversions should flow X -> loc_id -> Y.",
            "Use get_catalog for live catalog-backed family discovery instead of assuming a fixed list of countries or admin depths.",
            "Use get_pack for reference-system and bridge detail after selecting a family and, when needed, a country.",
            "Use identify_dataset_geography for neutral table samples; callers must not hard-code country or reference-system eligibility before that call.",
            "Use identify_reference_system before bulk conversion when geography identifiers are unknown or only informally declared.",
            "Use convert_reference for ZIP/ZCTA, tribal-area, NWS public forecast-zone, NWS fire weather-zone, admin-name, and named-geometry inputs.",
            "Use get_loc_id_info with include_references=true for reverse lookup from an existing loc_id to overlapping or equivalent external references.",
            "Use get_geometry only when geometry metadata, bbox, centroid, or polygon is needed.",
            "Use convert_reference for both side-chain-to-admin and admin-to-side-chain conversions.",
        ]
    elif preferred_tool == "resolve_point":
        first_arguments = {"lat": 34.0522, "lon": -118.2437}
        start_here = [
            "Call resolve_point first when you have coordinates; its compact stack is the normal answer.",
            "Take the returned deepest_resolved_loc_id or any level from the stack for filtering.",
            "Only when more detail is requested, pass all stack loc_ids to get_loc_id_info; call get_geometry separately for shapes.",
        ]
        important_rules = [
            "These are direct utility tools, not a get_data pack; bulk throughput uses the points input on resolve_point or resolve_deep_point.",
            "Coordinates must be WGS84 decimal degrees.",
            "Use resolve_point for one coordinate or a shallow array. Use resolve_deep_point for one coordinate or an array already split by Admin 1, with one shallow_loc_id per call.",
            "A mixed-vintage point chain is context. get_loc_id_info hierarchy and resolve_loc_id_scope follow strict stored parentage within a coherent release.",
            "get_geometry returns bbox and centroid by default; request include_polygon only when you need the full geometry payload.",
            "Use convert_reference for ZIP/ZCTA, tribal-area, NWS public forecast-zone, or NWS fire weather-zone conversions in either direction.",
            "Use get_loc_id_info for chain details and set include_references=true only for attached or overlapping reference systems.",
        ]
    elif preferred_tool == "get_geometry":
        first_arguments = {"loc_id": "USA-CA-037"}
        start_here = [
            "Call get_geometry when you already have a loc_id and need its extent.",
            "Use bbox and centroid for lightweight indexing and clipping.",
            "Request include_polygon only when you need the exact perimeter.",
        ]
        important_rules = [
            "These are free utility tools, not a get_data pack.",
            "Use canonical loc_ids such as USA, CAN-BC, or USA-CA-037.",
            "BBox/centroid is the default response shape because full polygons can be large.",
            "Use get_geometry with include_polygon=false to check larger shape lists without reading polygon coordinates.",
            "Use get_loc_id_info for hierarchy, lifecycle, catalog coverage, provenance, or non-geometry references; get_geometry stays shape-focused.",
        ]
    else:
        first_arguments = {"loc_id": "USA-CA-037"}
        start_here = [
            "Call the preferred tool first, then expand to the other geography helpers as needed.",
        ]
        important_rules = [
            "These are free utility tools, not a get_data pack.",
        ]
    entry["mcp"] = {"name": profile.get("mcp_name"), "facade_url": f"/mcp/{normalized}"}
    entry["registry_meta"] = dict(profile.get("registry_meta") or {})
    entry["routing"] = dict(profile.get("routing") or {})
    entry["quick_start"] = {
        "why_it_exists": "Use the geography tool family to map coordinates and loc_ids onto the same shared loc_id spine the DaedalMap packs use.",
        "start_here": start_here,
        "first_query_template": {
            "tool": preferred_tool,
            "arguments": first_arguments,
        },
        "bridge_examples": [
            {
                "question": "What geometry coverage does DaedalMap expose right now?",
                "tool": "get_catalog",
                "arguments": {"catalog": "geometry", "detail": "lite"},
            },
            {
                "question": "Which countries have postal geography?",
                "tool": "get_pack",
                "arguments": {"catalog": "geometry", "pack_id": "postal_area", "detail": "lite"},
            },
            {
                "question": "Do these values match 2020 US Census tract GEOIDs and a shape bank?",
                "tool": "identify_reference_system",
                "arguments": {
                    "identifiers": ["06073000100", "06073000201"],
                    "expected": {"system": "us_census_geoid", "geo_level": "tract", "vintage": "2020"},
                    "country_scope": "USA",
                },
            },
            {
                "question": "What county does ZIP/ZCTA 00601 resolve to?",
                "tool": "convert_reference",
                "arguments": {
                    "from_system": "zip",
                    "value": "00601",
                    "target_admin_level": "county",
                    "limit": 5,
                },
            },
            {
                "question": "Which NWS fire weather zones overlap this county?",
                "tool": "get_loc_id_info",
                "arguments": {
                    "loc_id": "USA-AK-282",
                    "include_references": True,
                    "systems": ["nws_fire"],
                    "target_admin_level": "county",
                    "limit_per_system": 5,
                },
            },
            {
                "question": "Convert ZIP/ZCTA 00601 to overlapping NWS fire weather zones.",
                "tool": "convert_reference",
                "arguments": {
                    "from_system": "zip",
                    "value": "00601",
                    "to_system": "nws_fire",
                    "target_admin_level": "county",
                    "limit": 5,
                },
            },
        ],
        "important_rules": important_rules,
        "starter_tools": [tool.get("name") for tool in tools if tool.get("name")],
    }
    entry["notes"] = (
        "Utility tool family on the DaedalMap loc_id spine. Free, and not a queryable "
        "dataset pack - call the listed tools directly rather than get_data."
    )
    return entry


def free_pack_ids() -> tuple[str, ...]:
    return tuple(
        pack_id
        for pack_id, profile in PACK_REGISTRY.items()
        if str(profile.get("kind") or "data_pack") == "data_pack"
        and not str(profile.get("pricing") or "free").startswith("paid")
    )


def paid_pack_ids() -> tuple[str, ...]:
    return tuple(
        pack_id
        for pack_id, profile in PACK_REGISTRY.items()
        if str(profile.get("kind") or "data_pack") == "data_pack"
        and str(profile.get("pricing") or "free").startswith("paid")
    )


def pack_profile(pack_id: str | None) -> dict:
    normalized = str(pack_id or "").strip()
    return dict(PACK_REGISTRY.get(normalized) or {})


def pack_display_name(pack_id: str | None) -> str:
    normalized = str(pack_id or "").strip()
    profile = PACK_REGISTRY.get(normalized) or {}
    return str(profile.get("display_name") or normalized.replace("_", " "))


def pack_registry_alias(pack_id: str | None) -> str | None:
    normalized = str(pack_id or "").strip()
    profile = PACK_REGISTRY.get(normalized) or {}
    alias = str(profile.get("registry_search_alias") or "").strip()
    return alias or None


def pack_mcp_server_profile(pack_id: str | None) -> dict:
    normalized = str(pack_id or "").strip()
    profile = PACK_REGISTRY.get(normalized) or {}
    return {
        "name": profile.get("mcp_name"),
        "title": profile.get("mcp_title"),
        "description": profile.get("mcp_description"),
        "version": profile.get("mcp_version"),
        "pricing": profile.get("pricing"),
        "registry_meta": dict(profile.get("registry_meta") or {}),
    }


def pack_routing_hints() -> dict[str, dict[str, str]]:
    hints: dict[str, dict[str, str]] = {}
    for pack_id, profile in PACK_REGISTRY.items():
        routing = profile.get("routing")
        if isinstance(routing, dict) and routing:
            hints[pack_id] = dict(routing)
    return hints


def pack_tool_allowlists() -> dict[str, set[str]]:
    allowlists: dict[str, set[str]] = {}
    for pack_id, profile in PACK_REGISTRY.items():
        raw = profile.get("mcp_tool_allowlist") or ()
        allowlists[pack_id] = {str(tool) for tool in raw if str(tool).strip()} | {"get_tool_help"}
    return allowlists


def pack_prompt_allowlists() -> dict[str, set[str]]:
    allowlists: dict[str, set[str]] = {}
    for pack_id, profile in PACK_REGISTRY.items():
        raw = profile.get("mcp_prompt_allowlist") or ()
        allowlists[pack_id] = {str(prompt) for prompt in raw if str(prompt).strip()}
    return allowlists
