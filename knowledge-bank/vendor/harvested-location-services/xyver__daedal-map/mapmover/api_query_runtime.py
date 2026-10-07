from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from functools import lru_cache
import json
from pathlib import Path
from typing import Any
import re

import pandas as pd

from .data_loading import get_source_path, load_catalog, load_source_metadata
from .catalog_cache_policy import control_catalog_cache_epoch
from .catalog_surface import has_catalog_product_surface, is_mcp_distribution_source
from .duckdb_helpers import parquet_available, parquet_columns, path_to_uri, quote_ident, run_df
from .paths import DATA_ROOT
from .runtime.aggregate_primitives import resolve_aggregate_admin2_dir


DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


@dataclass(frozen=True)
class ApiMetricSpec:
    metric_id: str
    column: str
    description: str


@dataclass(frozen=True)
class ApiAnalysisDimensionSpec:
    """A source-approved entity dimension for aggregate research queries."""

    dimension_id: str
    column: str
    label_fields: tuple[str, ...] = ()
    max_groups: int = 100
    requires_time_filter: bool = False


@dataclass(frozen=True)
class ApiSourceSpec:
    source_id: str
    pack_id: str
    parquet_name: str
    query_mode: str
    location_field: str
    time_field: str | None
    time_granularity: str | None
    metrics: dict[str, ApiMetricSpec]
    filterable_fields: set[str]
    sortable_fields: set[str]
    location_filter_mode: str = "hierarchical_loc_id"
    location_lookup_field: str | None = None
    hierarchical_filter_fields: tuple[str, ...] = ()
    delimited_hierarchical_filter_fields: tuple[str, ...] = ()
    derive_usa_iso3166_2_prefixes: bool = False
    filter_value_aliases: dict[str, dict[str, tuple[Any, ...]]] = field(default_factory=dict)
    family_admin_crosswalks: tuple[dict[str, Any], ...] = ()
    default_limit: int = DEFAULT_LIMIT
    max_limit: int = MAX_LIMIT
    metadata_source_id: str | None = None
    analysis_dimensions: dict[str, ApiAnalysisDimensionSpec] = field(default_factory=dict)


CURRENCY_SOURCE_SPEC = ApiSourceSpec(
    source_id="fx_usd_historical",
    pack_id="currency",
    parquet_name="data.parquet",
    query_mode="single_source",
    location_field="loc_id",
    time_field="date",
    time_granularity="date",
    metrics={
        "local_per_usd": ApiMetricSpec(
            metric_id="local_per_usd",
            column="local_per_usd",
            description="Local currency units per one USD",
        ),
    },
    filterable_fields={"loc_id", "date"},
    sortable_fields={"loc_id", "date", "local_per_usd"},
    location_filter_mode="hierarchical_loc_id",
)


SUPPORTED_DYNAMIC_SOURCES: dict[str, dict[str, Any]] = {
    "fx_usd_historical": {
        "pack_id": "currency",
        "parquet_name": "data.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "date",
        "time_granularity": "date",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "fx_usd_historical_weekly": {
        "pack_id": "currency",
        "parquet_name": "data.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "date",
        "time_granularity": "weekly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "fx_usd_historical_monthly": {
        "pack_id": "currency",
        "parquet_name": "data.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "date",
        "time_granularity": "monthly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "world_factbook": {
        "pack_id": "world_factbook",
        "parquet_name": "all_countries.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "world_factbook_static": {
        "pack_id": "world_factbook",
        "parquet_name": "all_countries.parquet",
        "query_mode": "single_source_static",
        "location_field": "loc_id",
        "time_field": None,
        "time_granularity": None,
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "worldpop": {
        "pack_id": "worldpop",
        "parquet_name": "population.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "yearly",
        "default_limit": 200,
        "max_limit": 5000,
    },
    "distributed_manufacturing": {
        "pack_id": "distributed_manufacturing",
        "parquet_name": "locations.parquet",
        "query_mode": "single_source_static",
        "location_field": "loc_id",
        "time_field": None,
        "time_granularity": None,
        "default_limit": 100,
        "max_limit": 1000,
    },
    "cbp": {
        "pack_id": "usa_cbp",
        "parquet_name": "USA.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "lodes": {
        "pack_id": "usa_lodes",
        "parquet_name": "USA_tract.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "susb": {
        "pack_id": "usa_susb",
        "parquet_name": "USA_county_naics.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "owid_co2": {
        "pack_id": "owid",
        "parquet_name": "owid_co2.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "un_wpp": {
        "pack_id": "un_wpp",
        "parquet_name": "un_wpp.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "cejst_burdens": {
        "pack_id": "cejst",
        "parquet_name": "burdens.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "cejst_classification": {
        "pack_id": "cejst",
        "parquet_name": "classification.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "era5_land_temperature": {
        "pack_id": "era5_land_temperature",
        "parquet_name": "data.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "monthly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "nws_alerts_historical": {
        "pack_id": "nws_alerts",
        "parquet_name": "events_with_zones.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
    "usa_opportunity_zones": {
        "pack_id": "usa_opportunity_zones",
        "parquet_name": "oz_tracts_2020.parquet",
        "query_mode": "single_source_static",
        "location_field": "loc_id",
        "time_field": None,
        "time_granularity": None,
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    },
    "earthquakes_events": {
        "pack_id": "earthquakes",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
    "volcanoes_events": {
        "pack_id": "volcanoes",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 500,
    },
    "tsunamis_events": {
        "pack_id": "tsunamis",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 500,
    },
    "hurricanes": {
        "pack_id": "hurricanes",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "global_fire_atlas": {
        "pack_id": "wildfires",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
    "wildfires_usa": {
        "pack_id": "wildfires",
        "parquet_name": "fires_enriched.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
    "can_wildfires": {
        "pack_id": "wildfires",
        "parquet_name": "fires_enriched.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
    "wildfire_aggregates": {
        "pack_id": "wildfires",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "flood_aggregates": {
        "pack_id": "floods",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "hurricane_aggregates": {
        "pack_id": "hurricanes",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "tornado_aggregates": {
        "pack_id": "tornadoes",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "earthquake_aggregates": {
        "pack_id": "earthquakes",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "tsunami_aggregates": {
        "pack_id": "tsunamis",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "volcano_aggregates": {
        "pack_id": "volcanoes",
        "parquet_name": "yearly.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "floods": {
        "pack_id": "floods",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
    "noaa_storm_events_floods": {
        "pack_id": "floods",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 1000,
    },
    "tornadoes": {
        "pack_id": "tornadoes",
        "parquet_name": "events.parquet",
        "query_mode": "single_source_events",
        "location_field": "loc_id",
        "time_field": "timestamp",
        "time_granularity": "timestamp",
        "default_limit": 100,
        "max_limit": 500,
    },
}

# UN SDG sources 01-17 share the same parquet shape; entries are generated to avoid repetition
for _sdg_i in range(1, 18):
    SUPPORTED_DYNAMIC_SOURCES[f"{_sdg_i:02d}"] = {
        "pack_id": "un_sdg",
        "parquet_name": "all_countries.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    }
del _sdg_i

# World Bank WDI category sources share the same yearly country-panel shape; each
# source stores its parquet as "<source_id>.parquet" under global/<source_id>/.
for _wb_source in (
    "wb_economy",
    "wb_environment",
    "wb_health",
    "wb_education",
    "wb_debt",
    "wb_infrastructure",
    "wb_social",
):
    SUPPORTED_DYNAMIC_SOURCES[_wb_source] = {
        "pack_id": "world_bank_wdi",
        "parquet_name": f"{_wb_source}.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    }
del _wb_source

# NRI hazard member sources share the same county-static shape; each source
# stores one USA.parquet under countries/USA/<source_id>/.
for _nri_source in (
    "nri_avalanche",
    "nri_coastal_flood",
    "nri_cold_wave",
    "nri_drought",
    "nri_earthquake",
    "nri_extreme_heat",
    "nri_hail",
    "nri_hurricane",
    "nri_ice_storm",
    "nri_inland_flood",
    "nri_landslide",
    "nri_lightning",
    "nri_strong_wind",
    "nri_tornado",
    "nri_tsunami",
    "nri_volcano",
    "nri_wildfire",
    "nri_winter_weather",
):
    SUPPORTED_DYNAMIC_SOURCES[_nri_source] = {
        "pack_id": "nri",
        "parquet_name": "USA.parquet",
        "query_mode": "single_source_static",
        "location_field": "loc_id",
        "time_field": None,
        "time_granularity": None,
        "default_limit": 100,
        "max_limit": 1000,
    }
del _nri_source

# OWID topic sources share the same yearly country-panel shape and all belong to the
# single "owid" pack (alongside owid_co2 above), mirroring how un_sdg's "01".."17"
# entries belong to one pack. Each source's parquet is nested under
# global/owid/<base>/core/ (not the flat global/<source_id>/ layout used by wb_*
# above). The catalog's "path" field for each "<base>_core" source_id resolves to that
# nested core/ directory, so only the parquet filename needs to be specified here.
for _owid_core_base in (
    "owid_climate_emissions",
    "owid_education",
    "owid_energy",
    "owid_food_agriculture_nutrition",
    "owid_governance_conflict",
    "owid_health_mortality_disease",
    "owid_labor_gender",
    "owid_land_biodiversity",
    "owid_population_demography",
    "owid_poverty_inequality_income",
    "owid_water_sanitation",
):
    _owid_core_source_id = f"{_owid_core_base}_core"
    SUPPORTED_DYNAMIC_SOURCES[_owid_core_source_id] = {
        "pack_id": "owid",
        "parquet_name": f"{_owid_core_base}_core.parquet",
        "query_mode": "single_source",
        "location_field": "loc_id",
        "time_field": "year",
        "time_granularity": "yearly",
        "default_limit": DEFAULT_LIMIT,
        "max_limit": MAX_LIMIT,
    }
del _owid_core_base, _owid_core_source_id


API_SOURCE_SPECS: dict[str, ApiSourceSpec] = {
    CURRENCY_SOURCE_SPEC.source_id: CURRENCY_SOURCE_SPEC,
}

MIXED_TEMPORAL_TRANSITION_YEARS: dict[str, int | None] = {}
PLAIN_YEAR_RE = re.compile(r"^-?\d{1,6}$")


def _catalog_api_source(source_id: str) -> dict[str, Any] | None:
    return next(
        (
            source
            for source in (load_catalog() or {}).get("sources", [])
            if isinstance(source, dict)
            and str(source.get("source_id") or "").strip() == source_id
            and has_catalog_product_surface(source, "api")
        ),
        None,
    )


def _normalize_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        str(item).strip()
        for item in value
        if str(item or "").strip()
    )


def _metadata_bool(metadata: dict[str, Any], source_defaults: dict[str, Any], key: str) -> bool:
    value = metadata.get(key)
    if value is None:
        value = source_defaults.get(key)
    return bool(value)


def _normalize_filter_value_aliases(value: Any) -> dict[str, dict[str, tuple[Any, ...]]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, tuple[Any, ...]]] = {}
    for field, aliases in value.items():
        field_name = str(field or "").strip()
        if not field_name or not isinstance(aliases, dict):
            continue
        field_aliases: dict[str, tuple[Any, ...]] = {}
        for alias, replacements in aliases.items():
            alias_key = str(alias or "").strip().lower()
            if not alias_key:
                continue
            if isinstance(replacements, list):
                values = tuple(item for item in replacements if item is not None)
            elif replacements is not None:
                values = (replacements,)
            else:
                values = ()
            if values:
                field_aliases[alias_key] = values
        if field_aliases:
            normalized[field_name] = field_aliases
    return normalized


def _metadata_filter_value_aliases(
    metadata: dict[str, Any],
    source_defaults: dict[str, Any],
) -> dict[str, dict[str, tuple[Any, ...]]]:
    routing_hints = metadata.get("routing_hints")
    routing_aliases = (
        routing_hints.get("filter_value_aliases")
        if isinstance(routing_hints, dict)
        else None
    )
    return (
        _normalize_filter_value_aliases(metadata.get("filter_value_aliases"))
        or _normalize_filter_value_aliases(routing_aliases)
        or _normalize_filter_value_aliases(source_defaults.get("filter_value_aliases"))
    )


def _normalize_family_admin_crosswalks(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        source_family = str(item.get("source_family") or "").strip()
        target_admin_level = str(item.get("target_admin_level") or "").strip()
        if not source_family or not target_admin_level:
            continue
        crosswalk: dict[str, Any] = {
            "source_family": source_family,
            "target_admin_level": target_admin_level,
        }
        if item.get("iso3"):
            crosswalk["iso3"] = str(item.get("iso3") or "").strip().upper()
        if item.get("crosswalk_path"):
            crosswalk["crosswalk_path"] = str(item.get("crosswalk_path") or "").strip()
        if item.get("min_source_area_share") is not None:
            try:
                crosswalk["min_source_area_share"] = float(item.get("min_source_area_share"))
            except (TypeError, ValueError):
                pass
        if item.get("limit") is not None:
            try:
                crosswalk["limit"] = int(item.get("limit"))
            except (TypeError, ValueError):
                pass
        normalized.append(crosswalk)
    return tuple(normalized)


def _coerce_year_token(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value == int(value) else None
    text = str(value).strip()
    if not text:
        return None
    if PLAIN_YEAR_RE.match(text):
        try:
            return int(text)
        except ValueError:
            return None
    if len(text) >= 4 and text[:4].lstrip("-").isdigit():
        try:
            return int(text[:4])
        except ValueError:
            return None
    return None


def _extract_requested_year_bounds(time_filter: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not isinstance(time_filter, dict):
        return None, None
    exact_value = time_filter.get("value")
    start_value = time_filter.get("start")
    end_value = time_filter.get("end")
    if exact_value is None and "year" in time_filter:
        exact_value = time_filter.get("year")
    if start_value is None and "year_start" in time_filter:
        start_value = time_filter.get("year_start")
    if end_value is None and "year_end" in time_filter:
        end_value = time_filter.get("year_end")
    if exact_value is not None:
        exact_year = _coerce_year_token(exact_value)
        return exact_year, exact_year
    return _coerce_year_token(start_value), _coerce_year_token(end_value)


def _compute_contiguous_timestamp_suffix_start(parquet_path: Path) -> int | None:
    try:
        df = run_df(
            "SELECT year, COUNT(*) AS row_count, COUNT(timestamp) AS timestamp_count "
            "FROM read_parquet(?) GROUP BY year",
            [path_to_uri(parquet_path)],
        )
    except Exception:
        return None
    if df.empty:
        return None
    full_years = sorted(
        int(row["year"])
        for row in df.to_dict("records")
        if row.get("year") is not None
        and int(row.get("row_count") or 0) == int(row.get("timestamp_count") or -1)
    )
    if not full_years:
        return None
    suffix_start = full_years[-1]
    previous = full_years[-1]
    for year in reversed(full_years[:-1]):
        if year == previous - 1:
            suffix_start = year
            previous = year
            continue
        break
    return int(suffix_start)


@lru_cache(maxsize=512)
def _usa_admin1_aliases_for_region_id(loc_id: str) -> tuple[str, ...]:
    loc_text = str(loc_id or "").strip().upper()
    if not loc_text.startswith("USA-"):
        return ()
    geometry_path = DATA_ROOT / "geometry" / "USA.parquet"
    if not geometry_path.exists():
        return ()
    try:
        if re.fullmatch(r"USA-[A-Z]{2}", loc_text):
            iso_3166_2 = f"US-{loc_text[-2:]}"
            rows = run_df(
                "SELECT loc_id, admin_level, iso_3166_2 FROM read_parquet(?) "
                "WHERE admin_level = 1 AND upper(iso_3166_2) = ?",
                [path_to_uri(geometry_path), iso_3166_2],
            )
        else:
            rows = run_df(
                "SELECT loc_id, admin_level, iso_3166_2 FROM read_parquet(?) "
                "WHERE upper(loc_id) = ?",
                [path_to_uri(geometry_path), loc_text],
            )
    except Exception:
        return ()
    if re.fullmatch(r"USA-[A-Z]{2}", loc_text):
        if rows.empty:
            return ()
        return (str(rows.iloc[0].get("loc_id") or "").strip(),)

    if rows.empty:
        return ()
    row = rows.iloc[0]
    try:
        admin_level = int(row.get("admin_level"))
    except (TypeError, ValueError):
        return ()
    if admin_level != 1:
        return ()
    iso_3166_2 = str(row.get("iso_3166_2") or "").strip().upper()
    if not iso_3166_2.startswith("US-") or len(iso_3166_2) != 5:
        return ()
    return (f"USA-{iso_3166_2[-2:]}",)


def _expand_hierarchical_prefixes_for_spec(spec: ApiSourceSpec, prefixes: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()

    def append_candidate(candidate: Any) -> None:
        text = str(candidate or "").strip()
        if not text:
            return
        key = text.upper()
        if key not in seen:
            expanded.append(text)
            seen.add(key)

    for value in prefixes:
        prefix = str(value or "").strip()
        if not prefix:
            continue
        append_candidate(prefix)
        if spec.derive_usa_iso3166_2_prefixes or prefix.upper().startswith("USA-"):
            for alias in _usa_admin1_aliases_for_region_id(prefix):
                append_candidate(alias)
        for crosswalk in spec.family_admin_crosswalks:
            source_family = str(crosswalk.get("source_family") or "").strip()
            if not source_family:
                continue
            try:
                from .runtime.geography_reference import classify_loc_id_family
                from .runtime.family_admin_crosswalk import resolve_family_to_admin
            except Exception:
                continue
            if classify_loc_id_family(prefix) != source_family:
                continue
            crosswalk_path_raw = str(crosswalk.get("crosswalk_path") or "").strip()
            crosswalk_path = Path(crosswalk_path_raw) if crosswalk_path_raw else None
            result = resolve_family_to_admin(
                prefix,
                source_family=source_family,
                target_admin_level=str(crosswalk.get("target_admin_level") or "").strip(),
                iso3=str(crosswalk.get("iso3") or "USA").strip().upper(),
                crosswalk_path=crosswalk_path,
                min_source_area_share=crosswalk.get("min_source_area_share"),
                limit=crosswalk.get("limit"),
            )
            for overlap in result.get("overlaps") or []:
                append_candidate(overlap.get("match_loc_id"))
    return expanded


def _append_hierarchical_prefix_where(
    *,
    col: str,
    prefixes: list[str],
    delimited: bool,
    params: list[Any],
) -> list[str]:
    exact_or_descendant_parts: list[str] = []
    for prefix in prefixes:
        prefix_upper = prefix.upper()
        if delimited:
            exact_or_descendant_parts.append(f"upper({quote_ident(col)}) = ?")
            params.append(prefix_upper)
            exact_or_descendant_parts.append(f"starts_with(upper({quote_ident(col)}), ?)")
            params.append(f"{prefix_upper}|")
            exact_or_descendant_parts.append(f"contains(upper({quote_ident(col)}), ?)")
            params.append(f"|{prefix_upper}|")
            exact_or_descendant_parts.append(f"ends_with(upper({quote_ident(col)}), ?)")
            params.append(f"|{prefix_upper}")
            exact_or_descendant_parts.append(f"starts_with(upper({quote_ident(col)}), ?)")
            params.append(f"{prefix_upper}-")
            exact_or_descendant_parts.append(f"contains(upper({quote_ident(col)}), ?)")
            params.append(f"|{prefix_upper}-")
        else:
            exact_or_descendant_parts.append(f"upper({quote_ident(col)}) = ?")
            params.append(prefix_upper)
            exact_or_descendant_parts.append(f"starts_with(upper({quote_ident(col)}), ?)")
            params.append(f"{prefix_upper}-")
    return exact_or_descendant_parts


def _build_metric_specs_from_metadata(metadata: dict[str, Any] | None) -> dict[str, ApiMetricSpec]:
    metrics = metadata.get("metrics") if isinstance(metadata, dict) else {}
    if not isinstance(metrics, dict):
        return {}

    built: dict[str, ApiMetricSpec] = {}
    for metric_id, metric_info in metrics.items():
        metric_key = str(metric_id).strip()
        if not metric_key:
            continue
        description = ""
        if isinstance(metric_info, dict):
            description = (
                str(metric_info.get("description") or "").strip()
                or str(metric_info.get("name") or "").strip()
                or str(metric_info.get("unit") or "").strip()
            )
        else:
            description = str(metric_info).strip()
        built[metric_key] = ApiMetricSpec(
            metric_id=metric_key,
            column=metric_key,
            description=description,
        )
    return built


def _build_dynamic_source_spec(source_id: str) -> ApiSourceSpec | None:
    source_defaults = dict(SUPPORTED_DYNAMIC_SOURCES.get(source_id) or {})
    catalog_source = _catalog_api_source(source_id)
    # API publication is the admission contract. The Python defaults above are
    # optional layout specializers; they must not be a second source registry.
    if catalog_source is None:
        return None

    metadata_source_id = str(source_defaults.get("metadata_source_id") or source_id)
    metadata = load_source_metadata(metadata_source_id) or catalog_source or {}
    runtime_primary_file = str(metadata.get("runtime_primary_file") or "").strip()
    pack_id = str(metadata.get("pack_id") or source_defaults.get("pack_id") or "").strip()
    location_field_default = str(metadata.get("location_field") or "loc_id").strip()
    temporal_coverage = metadata.get("temporal_coverage") if isinstance(metadata.get("temporal_coverage"), dict) else {}
    declared_time_field = temporal_coverage.get("field") or metadata.get("time_field")
    if not source_defaults:
        if not pack_id or not runtime_primary_file:
            return None
        data_type = str(metadata.get("data_type") or "").strip().lower()
        source_defaults = {
            "pack_id": pack_id,
            "parquet_name": runtime_primary_file,
            "query_mode": (
                str(metadata.get("query_mode") or "").strip()
                or ("single_source_events" if data_type in {"event", "events"} else "single_source" if declared_time_field else "single_source_static")
            ),
            "location_field": location_field_default,
            "time_field": declared_time_field,
            "time_granularity": temporal_coverage.get("granularity") or metadata.get("time_granularity"),
            "default_limit": DEFAULT_LIMIT,
            "max_limit": MAX_LIMIT,
        }
    metrics = _build_metric_specs_from_metadata(metadata)
    if str(source_defaults.get("query_mode") or "").strip() == "single_source_events":
        metrics.setdefault(
            "event_count",
            ApiMetricSpec(
                metric_id="event_count",
                column="event_count",
                description="Count of events matching the applied filters",
            ),
        )
    # Source metadata owns the canonical filter location. The runtime defaults
    # only seed legacy sources that have not declared their own contract.
    # Event identity lives in ``event_id``. ``loc_id`` is always the
    # geometry-backed filter location, including reviewed named-water events.
    location_field = str(
        metadata.get("location_field") or source_defaults["location_field"]
    ).strip()
    time_field = temporal_coverage.get("field") or source_defaults.get("time_field")
    time_granularity = normalize_time_granularity(
        temporal_coverage.get("granularity") or source_defaults.get("time_granularity")
    )
    source_path = Path(get_source_path(source_id))
    parquet_name = str(metadata.get("runtime_primary_file") or source_defaults["parquet_name"]).strip()
    primary_candidate = source_path / parquet_name
    wrapper_aggregate_path = None
    if source_path.name.lower() == "aggregates" and source_path.parent.name.lower() == "sources":
        aggregate_dir = resolve_aggregate_admin2_dir(source_path, data_root=DATA_ROOT)
        wrapper_aggregate_path = aggregate_dir / parquet_name

    local_pack_path = DATA_ROOT / "global" / str(source_defaults["pack_id"]) / parquet_name
    if wrapper_aggregate_path is not None and (wrapper_aggregate_path.exists() or parquet_available(wrapper_aggregate_path)):
        parquet_path = wrapper_aggregate_path
    elif primary_candidate.exists() or parquet_available(primary_candidate):
        parquet_path = primary_candidate
    elif local_pack_path.exists():
        parquet_path = local_pack_path
    else:
        parquet_path = wrapper_aggregate_path or None
    available_cols: set[str] = set()
    if isinstance(parquet_path, Path) and parquet_path.exists():
        try:
            available_cols = parquet_columns(parquet_path)
        except Exception:
            available_cols = set()
    elif parquet_path and parquet_available(parquet_path):
        available_cols = parquet_columns(parquet_path)
    normalized_time_field = str(time_field or "").strip() or None
    if normalized_time_field and normalized_time_field not in available_cols:
        fallback_time_field = None
        if "year" in available_cols and normalize_time_granularity(time_granularity) == "yearly":
            fallback_time_field = "year"
        elif "timestamp" in available_cols:
            fallback_time_field = "timestamp"
        elif "date" in available_cols:
            fallback_time_field = "date"
        if fallback_time_field:
            normalized_time_field = fallback_time_field
        else:
            normalized_time_field = None
    if not time_granularity and str(time_field or "").strip().lower() == "timestamp":
        time_granularity = "timestamp"
    location_filter_mode = str(
        metadata.get("location_filter_mode")
        or source_defaults.get("location_filter_mode")
        or "hierarchical_loc_id"
    ).strip()
    location_lookup_field_raw = metadata.get("location_lookup_field") or source_defaults.get("location_lookup_field")
    location_lookup_field = str(location_lookup_field_raw).strip() if location_lookup_field_raw else None

    filterable_fields = {location_field}
    sortable_fields = {location_field}
    if normalized_time_field:
        filterable_fields.add(normalized_time_field)
        sortable_fields.add(normalized_time_field)
    # Stable event identity is part of every event-row contract.  Agents need
    # it to move from broad get_data discovery into exact get_event traversal.
    if str(source_defaults.get("query_mode") or "").strip() == "single_source_events":
        for identity_field in ("event_id", "source_event_id"):
            if identity_field in available_cols:
                filterable_fields.add(identity_field)
                sortable_fields.add(identity_field)
    metadata_filterable = metadata.get("filterable_fields") if isinstance(metadata.get("filterable_fields"), list) else []
    for field in metadata_filterable:
        field_name = str(field).strip()
        if field_name:
            filterable_fields.add(field_name)
    # Auto-promote dimension columns to filterable fields. Sources that declare
    # a `dimensions` block (e.g. fairfax_lst's geo_level) want those columns
    # available as filters without having to repeat them in filterable_fields.
    metadata_dimensions = metadata.get("dimensions") if isinstance(metadata.get("dimensions"), dict) else {}
    for dim_key, dim_spec in metadata_dimensions.items():
        if isinstance(dim_spec, dict):
            column = str(dim_spec.get("column") or dim_key).strip()
            if column:
                filterable_fields.add(column)
    metadata_sortable = metadata.get("sortable_fields") if isinstance(metadata.get("sortable_fields"), list) else []
    for field in metadata_sortable:
        field_name = str(field).strip()
        if field_name:
            sortable_fields.add(field_name)
    sortable_fields.update(metrics.keys())
    analysis_dimensions = parse_analysis_dimensions(metadata, available_columns=available_cols)

    return ApiSourceSpec(
        source_id=source_id,
        pack_id=str(metadata.get("pack_id") or source_defaults["pack_id"]),
        parquet_name=parquet_name,
        query_mode=str(source_defaults["query_mode"]),
        location_field=location_field,
        time_field=normalized_time_field,
        time_granularity=str(time_granularity) if time_granularity else None,
        metrics=metrics,
        filterable_fields=filterable_fields,
        sortable_fields=sortable_fields,
        location_filter_mode=location_filter_mode,
        location_lookup_field=location_lookup_field,
        hierarchical_filter_fields=_normalize_string_tuple(
            metadata.get("hierarchical_filter_fields")
            or source_defaults.get("hierarchical_filter_fields")
        ),
        delimited_hierarchical_filter_fields=_normalize_string_tuple(
            metadata.get("delimited_hierarchical_filter_fields")
            or source_defaults.get("delimited_hierarchical_filter_fields")
        ),
        derive_usa_iso3166_2_prefixes=_metadata_bool(
            metadata,
            source_defaults,
            "derive_usa_iso3166_2_prefixes",
        ),
        filter_value_aliases=_metadata_filter_value_aliases(metadata, source_defaults),
        family_admin_crosswalks=_normalize_family_admin_crosswalks(
            metadata.get("family_admin_crosswalks")
            or source_defaults.get("family_admin_crosswalks")
        ),
        default_limit=int(metadata.get("default_limit") or source_defaults["default_limit"]),
        max_limit=int(metadata.get("max_limit") or source_defaults["max_limit"]),
        metadata_source_id=metadata_source_id,
        analysis_dimensions=analysis_dimensions,
    )


def is_temporal_time_field(spec: ApiSourceSpec) -> bool:
    time_field = str(spec.time_field or "").strip().lower()
    if time_field in {"timestamp", "datetime", "date"}:
        return True
    return str(spec.time_granularity or "").strip().lower() in {
        "date",
        "daily",
        "weekly",
        "monthly",
        "event",
        "timestamp",
        "datetime",
    }


def normalize_time_value_for_response(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def parse_analysis_dimensions(
    metadata: dict[str, Any],
    *,
    available_columns: set[str] | None = None,
) -> dict[str, ApiAnalysisDimensionSpec]:
    """Read the small, source-owned aggregate-query contract.

    This deliberately does not promote arbitrary Parquet columns into public
    group-bys.  A source must opt a stable entity key in explicitly.
    """
    contract = metadata.get("analysis_contract")
    contract = contract if isinstance(contract, dict) else {}
    declared = contract.get("groupable_dimensions")
    if not isinstance(declared, dict):
        return {}
    parsed: dict[str, ApiAnalysisDimensionSpec] = {}
    for raw_id, raw_spec in declared.items():
        dimension_id = str(raw_id or "").strip()
        detail = raw_spec if isinstance(raw_spec, dict) else {}
        column = str(detail.get("column") or dimension_id).strip()
        if not dimension_id or not column:
            continue
        if available_columns is not None and column not in available_columns:
            continue
        raw_labels = detail.get("label_fields")
        labels = tuple(
            field_name
            for field_name in (str(value).strip() for value in (raw_labels or []))
            if field_name and (available_columns is None or field_name in available_columns)
        ) if isinstance(raw_labels, list) else ()
        try:
            max_groups = int(detail.get("max_groups") or 100)
        except (TypeError, ValueError):
            max_groups = 100
        parsed[dimension_id] = ApiAnalysisDimensionSpec(
            dimension_id=dimension_id,
            column=column,
            label_fields=labels,
            max_groups=max(1, min(max_groups, MAX_LIMIT)),
            requires_time_filter=bool(detail.get("requires_time_filter", False)),
        )
    return parsed


@lru_cache(maxsize=512)
def _get_dynamic_api_source_spec(source_id: str, _catalog_epoch: int) -> ApiSourceSpec | None:
    return _build_dynamic_source_spec(source_id)


def get_api_source_spec(source_id: str) -> ApiSourceSpec | None:
    normalized_source_id = str(source_id or "").strip()
    if _catalog_api_source(normalized_source_id) is None:
        return None
    cached = API_SOURCE_SPECS.get(normalized_source_id)
    if cached is not None:
        return cached
    return _get_dynamic_api_source_spec(normalized_source_id, control_catalog_cache_epoch())


def clear_api_source_spec_cache() -> None:
    """Invalidate source contracts derived from the current published catalog."""
    _get_dynamic_api_source_spec.cache_clear()


def get_mixed_temporal_transition_year(spec: ApiSourceSpec) -> int | None:
    cached = MIXED_TEMPORAL_TRANSITION_YEARS.get(spec.source_id, None)
    if spec.source_id in MIXED_TEMPORAL_TRANSITION_YEARS:
        return cached

    if normalize_time_granularity(spec.time_granularity) != "yearly":
        MIXED_TEMPORAL_TRANSITION_YEARS[spec.source_id] = None
        return None

    metadata = load_source_metadata(spec.metadata_source_id or spec.source_id) or {}
    if not metadata:
        local_metadata_path = (
            DATA_ROOT
            / "global"
            / "disasters"
            / spec.pack_id
            / "sources"
            / (spec.metadata_source_id or spec.source_id)
            / "metadata.json"
        )
        if local_metadata_path.exists():
            try:
                metadata = json.loads(local_metadata_path.read_text(encoding="utf-8"))
            except Exception:
                metadata = {}
    temporal_precision = metadata.get("temporal_precision") if isinstance(metadata.get("temporal_precision"), dict) else {}
    timestamp_coverage = temporal_precision.get("timestamp_coverage") if isinstance(temporal_precision, dict) else {}
    metadata_transition_year = _coerce_year_token(
        timestamp_coverage.get("complete_from_year") if isinstance(timestamp_coverage, dict) else None
    )
    if metadata_transition_year is not None:
        MIXED_TEMPORAL_TRANSITION_YEARS[spec.source_id] = metadata_transition_year
        return metadata_transition_year

    parquet_path = get_source_parquet_path(spec)
    try:
        available_cols = parquet_columns(parquet_path)
    except Exception:
        MIXED_TEMPORAL_TRANSITION_YEARS[spec.source_id] = None
        return None
    if "year" not in available_cols or "timestamp" not in available_cols:
        MIXED_TEMPORAL_TRANSITION_YEARS[spec.source_id] = None
        return None

    try:
        transition_year = _compute_contiguous_timestamp_suffix_start(parquet_path)
    except Exception:
        transition_year = None
    MIXED_TEMPORAL_TRANSITION_YEARS[spec.source_id] = transition_year
    return transition_year


def resolve_effective_time_spec(spec: ApiSourceSpec, time_filter: dict[str, Any] | None) -> ApiSourceSpec:
    if normalize_time_granularity(spec.time_granularity) != "yearly":
        return spec

    requested_granularity = normalize_time_granularity(
        time_filter.get("granularity") if isinstance(time_filter, dict) else None
    )
    if requested_granularity == "yearly":
        return spec

    transition_year = get_mixed_temporal_transition_year(spec)
    if transition_year is None:
        return spec

    requested_start_year, requested_end_year = _extract_requested_year_bounds(time_filter)
    if requested_start_year is None and requested_end_year is None:
        return spec

    lower_bound_year = requested_start_year if requested_start_year is not None else requested_end_year
    upper_bound_year = requested_end_year if requested_end_year is not None else requested_start_year
    if lower_bound_year is None or upper_bound_year is None:
        return spec
    if lower_bound_year < transition_year or upper_bound_year < transition_year:
        return spec

    return replace(spec, time_field="timestamp", time_granularity="timestamp")


def get_pack_source_ids(pack_id: str) -> list[str]:
    normalized_pack_id = str(pack_id or "").strip()
    if not normalized_pack_id:
        return []
    catalog = load_catalog()
    source_ids = []
    for source in catalog.get("sources", []):
        if str(source.get("pack_id") or "").strip() == normalized_pack_id:
            source_id = str(source.get("source_id") or "").strip()
            if source_id and source_id != "world_factbook_overlap":
                source_ids.append(source_id)
    return sorted(set(source_ids))


def _get_mcp_pack_source_ids(pack_id: str) -> list[str]:
    source_ids: list[str] = []
    catalog = load_catalog()
    normalized_pack_id = str(pack_id or "").strip()
    for source in catalog.get("sources", []):
        if str(source.get("pack_id") or "").strip() != normalized_pack_id:
            continue
        if not is_mcp_distribution_source(source):
            continue
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            continue
        try:
            source_spec = get_api_source_spec(source_id)
        except Exception:
            # Pack discovery considers optional companion sources. A missing or
            # unreadable companion artifact must not hide the usable canonical
            # source for the whole pack.
            continue
        if source_spec is not None:
            source_ids.append(source_id)
    return sorted(set(source_ids))


def normalize_time_granularity(value: str | None) -> str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    alias_map = {
        "event": "timestamp",
        "events": "timestamp",
        "day": "daily",
        "daily": "daily",
        "date": "daily",
        "week": "weekly",
        "weekly": "weekly",
        "month": "monthly",
        "monthly": "monthly",
        "year": "yearly",
        "yearly": "yearly",
        "timestamp": "timestamp",
        "datetime": "timestamp",
    }
    return alias_map.get(normalized, normalized)


def resolve_pack_sources_for_metrics(pack_id: str, metrics: list[str]) -> dict[str, Any]:
    normalized_pack_id = str(pack_id or "").strip()
    normalized_metrics = [str(metric).strip() for metric in (metrics or []) if str(metric).strip()]
    if not normalized_pack_id or not normalized_metrics:
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": normalized_metrics,
            "resolution": "invalid_request",
            "selected_source_id": None,
            "required_sources": [],
            "metrics_by_source": {},
            "unknown_metrics": normalized_metrics,
        }

    candidate_sources = _get_mcp_pack_source_ids(normalized_pack_id)
    if not candidate_sources:
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": normalized_metrics,
            "resolution": "unknown_pack_sources",
            "selected_source_id": None,
            "required_sources": [],
            "metrics_by_source": {},
            "unknown_metrics": normalized_metrics,
        }
    per_source_metadata: dict[str, dict[str, Any]] = {}
    per_source_metric_keys: dict[str, set[str]] = {}
    metric_to_sources: dict[str, list[str]] = {}
    for source_id in candidate_sources:
        # Pack routing must not fail because an optional companion source has
        # no separately readable metadata object in the deployed artifact
        # lane. The normalized runtime spec is sufficient for capability
        # selection; source metadata only contributes a density tie-breaker.
        try:
            metadata = load_source_metadata(source_id) or {}
        except Exception:
            metadata = {}
        per_source_metadata[source_id] = metadata
        # Use the resolved source spec's metrics, which include synthetic metrics
        # such as event_count injected for event sources. Reading raw
        # metadata["metrics"] here misses them, so a pack-path query for
        # event_count was wrongly rejected as metric_not_available even though
        # the source-path validate_metrics accepts it.
        spec = get_api_source_spec(source_id)
        if spec is not None and spec.metrics:
            metric_keys = {str(key).strip() for key in spec.metrics.keys() if str(key).strip()}
        else:
            metrics_map = metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {}
            metric_keys = {str(key).strip() for key in metrics_map.keys() if str(key).strip()}
        per_source_metric_keys[source_id] = metric_keys
        for metric_key in metric_keys:
            metric_to_sources.setdefault(metric_key, []).append(source_id)

    unknown_metrics = [metric for metric in normalized_metrics if metric not in metric_to_sources]
    if unknown_metrics:
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": normalized_metrics,
            "resolution": "unknown_metrics",
            "selected_source_id": None,
            "required_sources": [],
            "metrics_by_source": {},
            "unknown_metrics": unknown_metrics,
        }

    source_scores: list[tuple[int, float, str]] = []
    for source_id in candidate_sources:
        metadata = per_source_metadata.get(source_id) or {}
        metric_keys = per_source_metric_keys.get(source_id, set())
        if any(metric not in metric_keys for metric in normalized_metrics):
            continue
        metrics_map = metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {}
        score = 0.0
        for metric in normalized_metrics:
            metric_info = metrics_map.get(metric)
            if isinstance(metric_info, dict):
                density = metric_info.get("density")
                if isinstance(density, (int, float)):
                    score += float(density)
        # ``event_count`` is synthetic on event sources and commonly also
        # exists on yearly aggregate companions.  Density metadata cannot
        # distinguish those lanes because the synthetic event metric is not in
        # the raw metadata map.  Pack quick starts promise event-first routing,
        # so prefer the canonical event source; callers that want yearly
        # aggregates can still select that source explicitly.
        spec = get_api_source_spec(source_id)
        is_event_source = bool(
            normalized_metrics == ["event_count"]
            and spec is not None
            and str(spec.query_mode or "").strip() == "single_source_events"
        )
        # Some packs have supplemental event sources alongside the canonical
        # source (for example NOAA Storm Events beside the maintained Floods
        # event archive).  When the canonical source id equals the pack id,
        # keep that pack-default promise ahead of supplemental event lanes.
        event_source_priority = 2 if is_event_source and source_id == normalized_pack_id else int(is_event_source)
        source_scores.append((event_source_priority, score, source_id))

    if source_scores:
        source_scores.sort(key=lambda item: (-item[0], -item[1], item[2]))
        selected_source_id = source_scores[0][2]
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": normalized_metrics,
            "resolution": "single_source",
            "selected_source_id": selected_source_id,
            "required_sources": [selected_source_id],
            "metrics_by_source": {selected_source_id: normalized_metrics},
            "unknown_metrics": [],
        }

    metrics_by_source: dict[str, list[str]] = {}
    for metric in normalized_metrics:
        candidate_metric_sources = metric_to_sources.get(metric, [])
        ranked_sources: list[tuple[float, str]] = []
        for source_id in candidate_metric_sources:
            metadata = per_source_metadata.get(source_id) or {}
            metric_info = (metadata.get("metrics") or {}).get(metric)
            density = None
            if isinstance(metric_info, dict):
                density = metric_info.get("density")
            ranked_sources.append((float(density) if isinstance(density, (int, float)) else -1.0, source_id))
        ranked_sources.sort(key=lambda item: (-item[0], item[1]))
        chosen_source = ranked_sources[0][1]
        metrics_by_source.setdefault(chosen_source, []).append(metric)

    required_sources = sorted(metrics_by_source.keys())
    return {
        "pack_id": normalized_pack_id,
        "requested_metrics": normalized_metrics,
        "resolution": "multi_source_required",
        "selected_source_id": None,
        "required_sources": required_sources,
        "metrics_by_source": metrics_by_source,
        "unknown_metrics": [],
    }


def _resolve_default_pack_source(
    pack_id: str,
    *,
    requested_granularity: str | None = None,
) -> dict[str, Any]:
    normalized_pack_id = str(pack_id or "").strip()
    normalized_granularity = normalize_time_granularity(requested_granularity)

    if normalized_pack_id == "currency":
        granularity_to_source = {
            "daily": "fx_usd_historical",
            "weekly": "fx_usd_historical_weekly",
            "monthly": "fx_usd_historical_monthly",
        }
        selected_source_id = granularity_to_source.get(normalized_granularity or "daily")
        spec = get_api_source_spec(selected_source_id) if selected_source_id else None
        if spec is None:
            return {
                "pack_id": normalized_pack_id,
                "requested_metrics": [],
                "resolution": "unsupported_granularity",
                "selected_source_id": None,
                "required_sources": [],
                "metrics_by_source": {},
                "unknown_metrics": [],
                "requested_granularity": normalized_granularity,
                "supported_granularities": sorted(granularity_to_source.keys()),
            }
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": [],
            "resolution": "default_source",
            "selected_source_id": selected_source_id,
            "required_sources": [selected_source_id],
            "metrics_by_source": {selected_source_id: []},
            "unknown_metrics": [],
            "requested_granularity": normalized_granularity,
            "supported_granularities": sorted(granularity_to_source.keys()),
        }

    candidate_sources = _get_mcp_pack_source_ids(normalized_pack_id)
    if not candidate_sources:
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": [],
            "resolution": "unknown_pack_sources",
            "selected_source_id": None,
            "required_sources": [],
            "metrics_by_source": {},
            "unknown_metrics": [],
            "requested_granularity": normalized_granularity,
        }

    if len(candidate_sources) == 1:
        selected_source_id = candidate_sources[0]
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": [],
            "resolution": "default_source",
            "selected_source_id": selected_source_id,
            "required_sources": [selected_source_id],
            "metrics_by_source": {selected_source_id: []},
            "unknown_metrics": [],
            "requested_granularity": normalized_granularity,
        }

    ranked_sources: list[tuple[int, str]] = []
    for source_id in candidate_sources:
        spec = get_api_source_spec(source_id)
        if spec is None:
            continue
        score = {
            "single_source_events": 40,
            "single_source": 30,
            "single_source_static": 20,
        }.get(str(spec.query_mode or "").strip(), 0)
        ranked_sources.append((score, source_id))

    ranked_sources.sort(key=lambda item: (-item[0], item[1]))
    if not ranked_sources:
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": [],
            "resolution": "unknown_pack_sources",
            "selected_source_id": None,
            "required_sources": [],
            "metrics_by_source": {},
            "unknown_metrics": [],
            "requested_granularity": normalized_granularity,
        }

    best_score = ranked_sources[0][0]
    best_sources = [source_id for score, source_id in ranked_sources if score == best_score]
    if len(best_sources) != 1:
        return {
            "pack_id": normalized_pack_id,
            "requested_metrics": [],
            "resolution": "ambiguous_default_source",
            "selected_source_id": None,
            "required_sources": sorted(best_sources),
            "metrics_by_source": {},
            "unknown_metrics": [],
            "requested_granularity": normalized_granularity,
        }

    selected_source_id = best_sources[0]
    return {
        "pack_id": normalized_pack_id,
        "requested_metrics": [],
        "resolution": "default_source",
        "selected_source_id": selected_source_id,
        "required_sources": [selected_source_id],
        "metrics_by_source": {selected_source_id: []},
        "unknown_metrics": [],
        "requested_granularity": normalized_granularity,
    }


def resolve_pack_source_for_query(
    pack_id: str,
    metrics: list[str],
    *,
    requested_granularity: str | None = None,
) -> dict[str, Any]:
    normalized_metrics = [str(metric).strip() for metric in (metrics or []) if str(metric).strip()]
    if not normalized_metrics:
        return _resolve_default_pack_source(
            pack_id,
            requested_granularity=requested_granularity,
        )

    base = resolve_pack_sources_for_metrics(pack_id, metrics)
    if base.get("resolution") != "single_source":
        base["requested_granularity"] = normalize_time_granularity(requested_granularity)
        return base

    normalized_pack_id = str(pack_id or "").strip()
    normalized_granularity = normalize_time_granularity(requested_granularity)
    base["requested_granularity"] = normalized_granularity
    if normalized_pack_id != "currency" or not normalized_granularity:
        return base

    granularity_to_source = {
        "daily": "fx_usd_historical",
        "weekly": "fx_usd_historical_weekly",
        "monthly": "fx_usd_historical_monthly",
    }
    selected_source_id = granularity_to_source.get(normalized_granularity)
    if not selected_source_id:
        base["resolution"] = "unsupported_granularity"
        base["selected_source_id"] = None
        base["required_sources"] = []
        base["metrics_by_source"] = {}
        base["supported_granularities"] = sorted(granularity_to_source.keys())
        return base

    spec = get_api_source_spec(selected_source_id)
    if spec is None:
        base["resolution"] = "unsupported_granularity"
        base["selected_source_id"] = None
        base["required_sources"] = []
        base["metrics_by_source"] = {}
        base["supported_granularities"] = sorted(granularity_to_source.keys())
        return base

    base["selected_source_id"] = selected_source_id
    base["required_sources"] = [selected_source_id]
    base["metrics_by_source"] = {selected_source_id: [str(metric).strip() for metric in (metrics or []) if str(metric).strip()]}
    base["supported_granularities"] = sorted(granularity_to_source.keys())
    return base


def get_source_parquet_path(spec: ApiSourceSpec) -> Path:
    local_parquet_path = getattr(spec, "local_parquet_path", None)
    if local_parquet_path:
        return Path(local_parquet_path)

    source_dir = Path(get_source_path(spec.source_id))
    primary_path = source_dir / spec.parquet_name
    if primary_path.exists():
        return primary_path

    if source_dir.name.lower() == "aggregates" and source_dir.parent.name.lower() == "sources":
        aggregate_dir = resolve_aggregate_admin2_dir(source_dir, data_root=DATA_ROOT)
        aggregate_primary_path = aggregate_dir / spec.parquet_name
        if aggregate_primary_path.exists():
            return aggregate_primary_path
        if str(spec.parquet_name or "").strip().lower() == "yearly.parquet":
            return aggregate_primary_path

    if spec.metadata_source_id and spec.metadata_source_id != spec.source_id:
        metadata_source_dir = Path(get_source_path(spec.metadata_source_id))
        metadata_primary_path = metadata_source_dir / spec.parquet_name
        if metadata_primary_path.exists():
            return metadata_primary_path

    disaster_source_path = DATA_ROOT / "global" / "disasters" / spec.pack_id / "sources" / spec.source_id / spec.parquet_name
    if disaster_source_path.exists():
        return disaster_source_path
    if spec.metadata_source_id and spec.metadata_source_id != spec.source_id:
        disaster_metadata_path = (
            DATA_ROOT / "global" / "disasters" / spec.pack_id / "sources" / spec.metadata_source_id / spec.parquet_name
        )
        if disaster_metadata_path.exists():
            return disaster_metadata_path

    # API sources may execute from a pack-shaped folder before local catalog.json
    # is present. Prefer a direct pack fallback over assuming source_id == folder.
    pack_path = DATA_ROOT / "global" / spec.pack_id / spec.parquet_name
    if pack_path.exists():
        return pack_path

    return primary_path


def get_api_source_columns(spec: ApiSourceSpec) -> set[str]:
    parquet_path = get_source_parquet_path(spec)
    return parquet_columns(parquet_path)


def get_api_source_time_bounds(spec: ApiSourceSpec) -> tuple[Any | None, Any | None]:
    if not spec.time_field:
        return None, None
    parquet_path = get_source_parquet_path(spec)
    available_cols = parquet_columns(parquet_path)
    if spec.time_field not in available_cols:
        return None, None

    time_col = quote_ident(spec.time_field)
    df = run_df(
        f"SELECT MIN({time_col}) AS min_value, MAX({time_col}) AS max_value FROM read_parquet(?)",
        [path_to_uri(parquet_path)],
    )
    if df.empty:
        return None, None

    row = df.iloc[0]
    min_value = row.get("min_value")
    max_value = row.get("max_value")
    if is_temporal_time_field(spec):
        return (
            normalize_time_value_for_response(min_value),
            normalize_time_value_for_response(max_value),
        )
    return (
        int(min_value) if min_value is not None else None,
        int(max_value) if max_value is not None else None,
    )


def api_source_ready(spec: ApiSourceSpec) -> bool:
    parquet_path = get_source_parquet_path(spec)
    return parquet_available(parquet_path)


def execute_dataset_query(
    spec: ApiSourceSpec,
    *,
    select_columns: list[str],
    exact_filters: dict[str, Any] | None = None,
    in_filters: dict[str, list[Any]] | None = None,
    hierarchical_prefix_filters: dict[str, list[str]] | None = None,
    compare_filters: list[tuple[str, str, Any]] | None = None,
    sort_items: list[tuple[str, str]] | None = None,
    limit: int | None = None,
    aggregate_dimension_columns: list[str] | None = None,
    aggregate_label_columns: list[str] | None = None,
    require_any_non_null_columns: list[str] | None = None,
) -> list[dict[str, Any]]:
    from .duckdb_helpers import _normalize_ts_for_duckdb

    parquet_path = get_source_parquet_path(spec)
    available_cols = parquet_columns(parquet_path)
    synthetic_event_count = "event_count" in {spec.metrics[column].column for column in spec.metrics if column == "event_count"}
    requested_event_count_only = (
        synthetic_event_count
        and len(select_columns) >= 1
        and "event_count" in [col for col in select_columns if col == "event_count"]
    )
    selected = [col for col in select_columns if col in available_cols]
    if not selected and not requested_event_count_only:
        return []

    groupable_selected = [col for col in selected if col in available_cols]
    where_parts: list[str] = []
    params: list[Any] = [path_to_uri(parquet_path)]
    having_parts: list[str] = []
    having_params: list[Any] = []

    for col, value in (exact_filters or {}).items():
        if col not in available_cols:
            raise ValueError(f"Filter column {col!r} is absent from source {spec.source_id!r}")
        if value is not None:
            alias_values = spec.filter_value_aliases.get(col, {}).get(str(value).strip().lower())
            if alias_values:
                normalized_upper_values = [str(alias_value).upper() for alias_value in alias_values]
                placeholders = ", ".join("?" for _ in normalized_upper_values)
                where_parts.append(f"upper({quote_ident(col)}) IN ({placeholders})")
                params.extend(normalized_upper_values)
                continue
            if col == spec.time_field and is_temporal_time_field(spec):
                where_parts.append(f"CAST({quote_ident(col)} AS TIMESTAMP) = CAST(? AS TIMESTAMP)")
                params.append(_normalize_ts_for_duckdb(str(value)))
            else:
                where_parts.append(f"{quote_ident(col)} = ?")
                params.append(value)

    for col, values in (in_filters or {}).items():
        normalized_values = [value for value in (values or []) if value is not None]
        if col not in available_cols:
            raise ValueError(f"Filter column {col!r} is absent from source {spec.source_id!r}")
        if not normalized_values:
            return []
        if normalized_values:
            normalized_upper_values = [str(value).upper() for value in normalized_values]
            placeholders = ", ".join("?" for _ in normalized_upper_values)
            where_parts.append(f"upper({quote_ident(col)}) IN ({placeholders})")
            params.extend(normalized_upper_values)

    for col, prefixes in (hierarchical_prefix_filters or {}).items():
        normalized_prefixes = [str(value).strip() for value in (prefixes or []) if str(value).strip()]
        if not normalized_prefixes:
            continue
        expanded_prefixes = _expand_hierarchical_prefixes_for_spec(spec, normalized_prefixes)
        prefix_fields = [col, *spec.hierarchical_filter_fields]
        delimited_fields = set(spec.delimited_hierarchical_filter_fields)
        exact_or_descendant_parts: list[str] = []
        for field in dict.fromkeys(prefix_fields):
            if field in available_cols:
                exact_or_descendant_parts.extend(
                    _append_hierarchical_prefix_where(
                        col=field,
                        prefixes=expanded_prefixes,
                        delimited=field in delimited_fields,
                        params=params,
                    )
                )
        if exact_or_descendant_parts:
            where_parts.append("(" + " OR ".join(exact_or_descendant_parts) + ")")
        else:
            raise ValueError(
                f"Hierarchical filter {col!r} has no physical column in source {spec.source_id!r}"
            )

    for col, op, value in (compare_filters or []):
        if value is None:
            continue
        if op not in {"=", "!=", ">", ">=", "<", "<="}:
            continue
        if col == "event_count":
            having_parts.append(f"COUNT(*) {op} ?")
            having_params.append(value)
        elif col == spec.time_field and col in available_cols and is_temporal_time_field(spec):
            where_parts.append(f"CAST({quote_ident(col)} AS TIMESTAMP) {op} CAST(? AS TIMESTAMP)")
            params.append(_normalize_ts_for_duckdb(str(value)))
        elif col in available_cols:
            where_parts.append(f"{quote_ident(col)} {op} ?")
            params.append(value)
        else:
            raise ValueError(f"Comparison column {col!r} is absent from source {spec.source_id!r}")

    order_parts: list[str] = []
    for sort_field, sort_direction in (sort_items or []):
        direction = "DESC" if str(sort_direction).lower() == "desc" else "ASC"
        if sort_field == "event_count":
            order_parts.append(f"event_count {direction} NULLS LAST")
        elif sort_field and sort_field in available_cols:
            order_parts.append(f"{quote_ident(sort_field)} {direction} NULLS LAST")

    if requested_event_count_only:
        parquet_uri = params[0]
        where_params = params[1:]
        # Legacy event-count requests group by the regular selected columns
        # (location/time).  An explicit aggregate request instead groups only
        # by its source-approved entity dimensions.
        group_by_columns = (
            [col for col in (aggregate_dimension_columns or []) if col in available_cols]
            if aggregate_dimension_columns is not None
            else [col for col in groupable_selected if col != "event_count"]
        )
        label_columns = [
            col for col in (aggregate_label_columns or [])
            if col in available_cols and col not in group_by_columns
        ]
        select_parts: list[str] = []
        group_by_ordinals: list[str] = []
        event_count_params: list[Any] = []
        group_index = 1
        for col in group_by_columns:
            if col == spec.location_field and (hierarchical_prefix_filters or {}).get(col):
                prefixes = [str(value).strip().upper() for value in (hierarchical_prefix_filters or {}).get(col, []) if str(value).strip()]
                if prefixes:
                    case_parts = ["CASE"]
                    for prefix in prefixes:
                        case_parts.append(f"WHEN upper({quote_ident(col)}) = ? OR starts_with(upper({quote_ident(col)}), ?) THEN ?")
                        event_count_params.extend([prefix, f"{prefix}-", prefix])
                    case_parts.append(f"ELSE upper({quote_ident(col)}) END AS {quote_ident(col)}")
                    select_parts.append(" ".join(case_parts))
                    group_by_ordinals.append(str(group_index))
                    group_index += 1
                    continue
            select_parts.append(quote_ident(col))
            group_by_ordinals.append(str(group_index))
            group_index += 1
        # Labels are descriptive only.  They are deliberately aggregated, not
        # added to GROUP BY, because names can be null or non-unique.
        for col in label_columns:
            select_parts.append(f"MIN({quote_ident(col)}) AS {quote_ident(col)}")
        select_parts.append("COUNT(*) AS event_count")
        sql = f"SELECT {', '.join(select_parts)} FROM read_parquet(?)"
        aggregate_params: list[Any] = [*event_count_params, parquet_uri, *where_params]
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if group_by_columns:
            sql += " GROUP BY " + ", ".join(group_by_ordinals)
        if having_parts:
            sql += " HAVING " + " AND ".join(having_parts)
            aggregate_params.extend(having_params)
        if order_parts:
            sql += " ORDER BY " + ", ".join(order_parts)
        if limit is not None and limit > 0:
            sql += " LIMIT ?"
            aggregate_params.append(limit)
        df = run_df(sql, aggregate_params)
        if df.empty:
            return []
        return df.to_dict("records")

    normal_where_parts = list(where_parts)
    required_non_null = [
        str(col).strip()
        for col in (require_any_non_null_columns or [])
        if str(col).strip() in available_cols
    ]
    if required_non_null:
        normal_where_parts.append(
            "(" + " OR ".join(f"{quote_ident(col)} IS NOT NULL" for col in dict.fromkeys(required_non_null)) + ")"
        )

    select_expr = ", ".join(quote_ident(col) for col in selected)
    sql = f"SELECT {select_expr} FROM read_parquet(?)"
    if normal_where_parts:
        sql += " WHERE " + " AND ".join(normal_where_parts)
    if order_parts:
        sql += " ORDER BY " + ", ".join(order_parts)

    if limit is not None and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)

    df = run_df(sql, params)
    if df.empty:
        return []
    return df.to_dict("records")
