"""
Source Registry Example - Template for data source configuration.

This module shows the pattern for registering data sources with metadata.
Copy this to your private build folder and add your actual sources.

Usage:
    from source_registry import SOURCE_REGISTRY, get_source_config

    config = get_source_config('my_source')
"""

# =============================================================================
# GLOBAL SOURCES (country-level data)
# =============================================================================

GLOBAL_SOURCES = {
    # Example: Time-series demographic data
    "example_population": {
        "source_name": "Example Population Dataset",
        "source_url": "https://example.com/population",
        "license": "CC-BY 4.0",
        "description": "Annual population estimates by country.",
        "category": "demographic",
        "topic_tags": ["population", "demographics"],
        "keywords": ["population", "census", "country"],
        "update_schedule": "annual",
        "has_reference": False,
        "has_events": False
    },

    # Example: Event-based disaster data
    "example_earthquakes": {
        "source_name": "Example Earthquake Catalog",
        "source_url": "https://example.com/earthquakes",
        "license": "Public Domain",
        "description": "Global earthquake events with magnitude and location.",
        "category": "hazard",
        "topic_tags": ["earthquake", "seismic", "geology"],
        "keywords": ["earthquake", "seismic", "magnitude"],
        "update_schedule": "continuous",
        "has_reference": False,
        "has_events": True,
        # Optional: Link to affected areas table
        "event_areas_file": "global/event_areas/earthquakes.parquet"
    },
}


# =============================================================================
# COUNTRY-SPECIFIC SOURCES (sub-national data)
# =============================================================================

USA_SOURCES = {
    # Example: County-level data
    "example_county_data": {
        "source_name": "Example County Dataset",
        "source_url": "https://example.com/counties",
        "license": "Public Domain (U.S. Government)",
        "description": "County-level statistics for the United States.",
        "category": "demographic",
        "topic_tags": ["demographics", "county"],
        "keywords": ["county", "population", "statistics"],
        "update_schedule": "annual",
        "has_reference": False,
        "has_events": False
    },
}


# =============================================================================
# COMBINED REGISTRY
# =============================================================================

SOURCE_REGISTRY = {}

for source_id, config in GLOBAL_SOURCES.items():
    SOURCE_REGISTRY[source_id] = {**config, "scope": "global"}

for source_id, config in USA_SOURCES.items():
    SOURCE_REGISTRY[source_id] = {**config, "scope": "usa"}


def get_source_config(source_id: str) -> dict:
    """Get configuration for a source by ID."""
    if source_id not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown source_id: {source_id}")
    return SOURCE_REGISTRY[source_id]


def list_sources(scope: str = None) -> list:
    """List all source IDs, optionally filtered by scope."""
    if scope is None:
        return list(SOURCE_REGISTRY.keys())
    return [sid for sid, cfg in SOURCE_REGISTRY.items() if cfg.get("scope") == scope]


# =============================================================================
# REQUIRED FIELDS REFERENCE
# =============================================================================
"""
Required fields for each source:
- source_name: Human-readable name
- source_url: Original data source URL
- license: Data license (CC-BY, Public Domain, etc.)
- description: What the data contains
- category: One of: demographic, economic, health, hazard, environmental, general
- topic_tags: List of topic categories for filtering
- keywords: Search keywords for discovery
- update_schedule: How often data updates (annual, monthly, continuous, etc.)
- has_reference: True if source has reference/lookup data
- has_events: True if source has event-based data (vs aggregates)

Optional fields:
- event_areas_file: Path to event_areas parquet (for disaster events)
- secondary_source_url: Additional source URL
"""
