"""
mapmover package - Runtime application logic for the county-map application.

This package provides:
- Path configuration (paths.py)
- Geography and regional groupings (geography.py)
- Data loading and catalog management (data_loading.py)
- Geometry enrichment (geometry_enrichment.py)
- Geometry joining (geometry_joining.py)
- Geometry endpoint handlers (geometry_handlers.py)
- Order Taker LLM (order_taker.py)
- Order Executor (order_executor.py)
- Logging and analytics (logging_analytics.py)
- Utility functions (utils.py)
- Constants (constants.py)

Note: Build tools (geometry processing, catalog generation) are in the build/ folder.
"""

# Path configuration (import first as other modules may depend on it)
from .paths import (
    APP_ROOT,
    DATA_ROOT,
    # Data paths
    COUNTRIES_DIR,
    GLOBAL_DIR,
    GEOMETRY_DIR,
    CATALOG_PATH,
    INDEX_PATH,
    # App paths
    STATIC_DIR,
    TEMPLATES_DIR,
    CONFIG_DIR,
    STATE_DIR,
    CACHE_DIR,
    LOGS_DIR,
    RUNTIME_CONFIG_PATH,
    SETTINGS_PATH,
    PACKS_ROOT,
    INSTALL_MODE,
    RUNTIME_MODE,
    # Deployment URLs
    APP_HOST,
    APP_PORT,
    APP_URL,
    SITE_URL,
    ACCOUNT_URL,
    # Helper functions
    get_country_dir,
    get_country_index,
    get_dataset_path,
    get_geometry_path,
    ensure_dir,
    validate_paths,
)

# Re-export key functions for convenience
from .constants import (
    UNIT_MULTIPLIERS,
)

from .utils import (
    convert_unit,
    state_from_abbr,
    normalize,
    parse_year_value,
    clean_nans,
    apply_unit_multiplier,
)

from .geography import (
    load_conversions,
    get_conversions_data,
    get_countries_in_region,
    get_country_names_from_codes,
    get_limited_geometry_countries,
    get_fallback_coordinates,
    get_region_patterns,
    get_supported_regions_text,
    CONVERSIONS_DATA,
)

from .data_loading import (
    initialize_catalog,
    get_data_catalog,
    get_data_folder,
    get_catalog_path,
    load_catalog,
    load_full_catalog,
    load_source_metadata,
    get_source_by_topic,
    clear_metadata_cache,
    data_catalog,
)

from .logging_analytics import (
    log_missing_geometry,
    log_error_to_cloud,
    log_missing_region_to_cloud,
    logger,
)

from .pack_state import (
    PACK_STATE_PATH,
    build_active_catalog,
    get_runtime_pack_summary,
    load_pack_state,
    materialize_active_data_root,
    save_pack_state,
    set_active_pack_ids,
)

from .pack_manager import (
    install_pack_from_manifest,
    install_pack_from_manifest_ref,
    install_pack_from_local_catalog,
    uninstall_pack,
)

from .pack_downloader import (
    PACK_STAGING_ROOT,
    stage_pack_artifact,
)

from .foundation_helpers import (
    load_global_countries_frame as load_global_countries,
)

from .geometry_enrichment import (
    get_geometry_lookup,
    get_country_coordinates,
    enrich_with_geometry,
    detect_missing_geometry,
    get_geometry_source,
)

from .geometry_joining import (
    detect_join_key,
    auto_join_geometry,
)

from .geometry_handlers import (
    get_countries_geometry,
    get_location_children,
    get_location_places,
    get_location_info,
    load_country_parquet,
    clear_cache,
)

# Order Taker system
from .order_taker import interpret_request
from .order_executor import execute_order

# Preprocessor for tiered context
from .preprocessor import preprocess_query

# Postprocessor for validation and derived fields
from .postprocessor import postprocess_order, get_display_items

# Cache signature system for unified data identification
from .cache_signature import (
    CacheSignature,
    DataPackage,
    CacheInventory,
    CoverageClaim,
    ClaimScope,
    ClaimTime,
    SEEDED_FILTERS,
)

# Session cache management
from .session_cache import (
    SessionCache,
    SessionManager,
    session_manager,
)

# Package optimizer for merging data requests
from .package_optimizer import (
    PackageOptimizer,
    merge_results,
)

# Disaster filters for location-based API queries
from .disaster_filters import (
    apply_location_filters,
    get_affected_event_ids,
    get_events_for_location,
    get_disaster_metadata,
    get_default_min_year,
    get_all_disaster_metadata,
)

__version__ = "0.4.0"
__all__ = [
    # Paths
    "APP_ROOT",
    "DATA_ROOT",
    "COUNTRIES_DIR",
    "GLOBAL_DIR",
    "GEOMETRY_DIR",
    "CATALOG_PATH",
    "INDEX_PATH",
    "STATIC_DIR",
    "TEMPLATES_DIR",
    "CONFIG_DIR",
    "STATE_DIR",
    "CACHE_DIR",
    "LOGS_DIR",
    "RUNTIME_CONFIG_PATH",
    "SETTINGS_PATH",
    "PACKS_ROOT",
    "INSTALL_MODE",
    "RUNTIME_MODE",
    "APP_HOST",
    "APP_PORT",
    "APP_URL",
    "SITE_URL",
    "ACCOUNT_URL",
    "get_country_dir",
    "get_country_index",
    "get_dataset_path",
    "get_geometry_path",
    "ensure_dir",
    "validate_paths",
    # Constants
    "UNIT_MULTIPLIERS",
    # Utils
    "convert_unit",
    "state_from_abbr",
    "normalize",
    "parse_year_value",
    "clean_nans",
    "apply_unit_multiplier",
    # Geography
    "load_conversions",
    "get_conversions_data",
    "get_countries_in_region",
    "get_country_names_from_codes",
    "get_limited_geometry_countries",
    "get_fallback_coordinates",
    "get_region_patterns",
    "get_supported_regions_text",
    "CONVERSIONS_DATA",
    # Data loading
    "initialize_catalog",
    "get_data_catalog",
    "get_data_folder",
    "get_catalog_path",
    "load_catalog",
    "load_full_catalog",
    "load_source_metadata",
    "get_source_by_topic",
    "clear_metadata_cache",
    "data_catalog",
    # Logging
    "log_missing_geometry",
    "log_error_to_cloud",
    "log_missing_region_to_cloud",
    "logger",
    "PACK_STATE_PATH",
    "build_active_catalog",
    "get_runtime_pack_summary",
    "load_pack_state",
    "materialize_active_data_root",
    "save_pack_state",
    "set_active_pack_ids",
    "install_pack_from_local_catalog",
    "install_pack_from_manifest",
    "install_pack_from_manifest_ref",
    "uninstall_pack",
    "PACK_STAGING_ROOT",
    "stage_pack_artifact",
    # Geometry
    "get_geometry_lookup",
    "enrich_with_geometry",
    "detect_missing_geometry",
    "get_geometry_source",
    # Geometry handlers
    "get_countries_geometry",
    "get_location_children",
    "get_location_places",
    "get_location_info",
    "load_country_parquet",
    "load_global_countries",
    "clear_cache",
    # Order Taker
    "interpret_request",
    "execute_order",
    # Preprocessor
    "preprocess_query",
    # Postprocessor
    "postprocess_order",
    "get_display_items",
    # Cache signature
    "CacheSignature",
    "DataPackage",
    "CacheInventory",
    "CoverageClaim",
    "ClaimScope",
    "ClaimTime",
    "SEEDED_FILTERS",
    # Session cache
    "SessionCache",
    "SessionManager",
    "session_manager",
    # Package optimizer
    "PackageOptimizer",
    "merge_results",
    # Disaster filters
    "apply_location_filters",
    "get_affected_event_ids",
    "get_events_for_location",
    # Disaster metadata
    "get_disaster_metadata",
    "get_default_min_year",
    "get_all_disaster_metadata",
]
