"""Shared timing policy for small catalog and registry control files."""

from __future__ import annotations

import os
import time


def _bounded_seconds(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


# catalog.json, the WIP catalog, geometry_catalog.json, the Agent Catalog,
# ops_feed_registry.json, and storefront projections all use this publication
# visibility window. Heavy data/query caches intentionally have their own policy.
CONTROL_CATALOG_CACHE_TTL_SECONDS = _bounded_seconds(
    "CONTROL_CATALOG_CACHE_TTL_SECONDS",
    300,
    minimum=30,
    maximum=3600,
)

# A missing control object is retried quickly; this is not the normal warm TTL.
CONTROL_CATALOG_MISS_TTL_SECONDS = _bounded_seconds(
    "CONTROL_CATALOG_MISS_TTL_SECONDS",
    15,
    minimum=1,
    maximum=60,
)


def control_catalog_cache_epoch() -> int:
    """Return the shared generation key for catalog-derived in-process views."""
    return int(time.monotonic() // CONTROL_CATALOG_CACHE_TTL_SECONDS)
