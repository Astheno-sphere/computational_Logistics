"""Warm the small shared runtime control catalogs through canonical loaders."""

from __future__ import annotations

from mapmover import logger
from mapmover.data_loading import load_catalog, load_full_catalog
from mapmover.ops_feed_registry import load_ops_feed_records
from mapmover.runtime.geometry_catalog import load_geometry_catalog


def _record_count(payload: dict, *keys: str) -> int:
    return max(
        (
            len(payload.get(key) or [])
            for key in keys
            if isinstance(payload.get(key), list)
        ),
        default=0,
    )


def prewarm_control_catalogs() -> dict[str, int]:
    """Populate caches for small catalogs shared across app and MCP surfaces."""
    published = load_catalog()
    wip = load_full_catalog()
    geometry = load_geometry_catalog()
    ops_feeds = load_ops_feed_records()

    counts = {
        "published": _record_count(published, "sources", "packs"),
        "wip": _record_count(wip, "sources", "packs"),
        "geometry": _record_count(
            geometry,
            "geometry_banks",
            "geometry_products",
            "country_profiles",
            "geometry_collections",
        ),
        "ops_feeds": len(ops_feeds),
    }
    missing = [name for name, count in counts.items() if count <= 0]
    if missing:
        raise RuntimeError(
            "control catalog prewarm returned no records for: " + ", ".join(missing)
        )
    logger.info(
        "Control catalogs warmed: published=%d wip=%d geometry=%d ops_feeds=%d",
        counts["published"],
        counts["wip"],
        counts["geometry"],
        counts["ops_feeds"],
    )
    return counts
