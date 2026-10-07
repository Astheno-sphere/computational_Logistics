"""Shared runtime surface for tier-context assembly."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..data_loading import get_source_path, load_catalog, load_source_metadata
from ..foundation_helpers import load_reference_dict
from ..paths import COUNTRIES_DIR, GEOMETRY_DIR
from ..preprocessor_context import (
    build_tier3_context as build_tier3_context_impl,
    build_tier4_context as build_tier4_context_impl,
    format_filter_description as format_filter_description_impl,
)
from .preprocess_primitives import (
    get_countries_in_viewport as get_countries_in_viewport_impl,
    get_relevant_sources_with_metrics as get_relevant_sources_with_metrics_impl,
    get_sorted_location_names as get_sorted_location_names_impl,
    load_country_index as load_country_index_impl,
    load_parquet_names as load_parquet_names_impl,
)


logger = logging.getLogger(__name__)

REFERENCE_DIR = Path(__file__).resolve().parent.parent / "reference"


def load_reference_file(filepath: Path) -> Optional[dict]:
    return load_reference_dict(filepath)


def get_countries_in_viewport(bounds: dict) -> list:
    return get_countries_in_viewport_impl(bounds, geometry_dir=GEOMETRY_DIR, logger=logger)


def load_parquet_names(iso3: str) -> dict:
    return load_parquet_names_impl(iso3, geometry_dir=GEOMETRY_DIR, logger=logger)


def get_sorted_location_names(iso3: str) -> list:
    return get_sorted_location_names_impl(
        iso3,
        load_parquet_names_func=load_parquet_names,
        logger=logger,
    )


def load_country_index(iso3: str) -> Optional[dict]:
    return load_country_index_impl(iso3, countries_dir=COUNTRIES_DIR, logger=logger)


def get_relevant_sources_with_metrics(topics: list, iso3: str | None = None) -> dict:
    return get_relevant_sources_with_metrics_impl(
        topics,
        iso3,
        load_catalog=load_catalog,
        load_source_metadata=load_source_metadata,
        load_country_index_func=load_country_index,
    )


def format_filter_description(filters: dict, overlay_type: str) -> str:
    return format_filter_description_impl(filters, overlay_type)


def build_tier3_context(hints: dict) -> str:
    return build_tier3_context_impl(
        hints,
        format_filter_description_func=format_filter_description,
        get_countries_in_viewport=get_countries_in_viewport,
        load_reference_file=load_reference_file,
        reference_dir=REFERENCE_DIR,
        load_source_metadata=load_source_metadata,
        get_source_path=get_source_path,
        get_relevant_sources_with_metrics=get_relevant_sources_with_metrics,
        logger=logger,
        countries_dir=COUNTRIES_DIR,
    )


def build_tier4_context(hints: dict) -> str:
    return build_tier4_context_impl(hints)


__all__ = [
    "build_tier3_context",
    "build_tier4_context",
    "format_filter_description",
]
