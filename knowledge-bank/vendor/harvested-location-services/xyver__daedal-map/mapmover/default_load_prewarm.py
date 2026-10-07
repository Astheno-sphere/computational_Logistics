"""Catalog-driven prewarm helpers for authored Explore defaults."""

from __future__ import annotations

import copy
import logging
import time
from typing import Callable

from .duckdb_helpers import is_cloud_mode


logger = logging.getLogger(__name__)


def _default_load_kind(default_load: dict) -> str:
    return str(default_load.get("kind") or default_load.get("type") or "").strip()


def iter_pack_confirmed_order_defaults(catalog: dict) -> list[tuple[str, dict]]:
    """Return pack-level confirmed_order defaults from a catalog payload."""
    defaults: list[tuple[str, dict]] = []
    for pack in catalog.get("packs") or []:
        if not isinstance(pack, dict):
            continue
        pack_id = str(pack.get("pack_id") or "").strip()
        default_load = pack.get("default_load")
        if not pack_id or not isinstance(default_load, dict):
            continue
        if _default_load_kind(default_load) != "confirmed_order":
            continue
        items = default_load.get("items")
        if not isinstance(items, list) or not items:
            continue
        defaults.append((pack_id, copy.deepcopy(default_load)))
    return defaults


def prewarm_catalog_default_loads(
    *,
    load_catalog_func: Callable[[], dict] | None = None,
    execute_order_func: Callable[[dict], dict] | None = None,
) -> None:
    """Execute authored pack-level confirmed_order defaults at startup.

    Disaster ``overlay_range_load`` defaults keep their specialized DataFrame
    prewarm path in ``prewarm_disaster_sources`` because those routes cache
    exact rolling window slices. Confirmed orders do not share that route cache,
    but executing them here warms the catalog-selected DuckDB/httpfs path and
    keeps authored pack defaults from requiring a separate hand-maintained
    prewarm list.
    """
    if not is_cloud_mode():
        return

    if load_catalog_func is None:
        from .data_loading import load_catalog

        load_catalog_func = load_catalog
    if execute_order_func is None:
        from .runtime.order_executor_runtime import execute_order

        execute_order_func = execute_order

    catalog = load_catalog_func() or {}
    defaults = iter_pack_confirmed_order_defaults(catalog)
    if not defaults:
        logger.info("prewarm catalog default loads: no confirmed_order defaults found")
        return

    warmed = 0
    failed = 0
    t0 = time.monotonic()
    for pack_id, default_load in defaults:
        try:
            started = time.monotonic()
            result = execute_order_func(default_load)
            result_type = result.get("type") if isinstance(result, dict) else type(result).__name__
            result_count = result.get("count") if isinstance(result, dict) else None
            warmed += 1
            logger.info(
                "prewarm catalog default %s: type=%s count=%s in %.1fs",
                pack_id,
                result_type,
                result_count,
                time.monotonic() - started,
            )
        except Exception as exc:
            failed += 1
            logger.warning("prewarm catalog default %s failed: %s", pack_id, exc)

    logger.info(
        "prewarm catalog default loads complete: warmed=%d failed=%d total=%d in %.1fs",
        warmed,
        failed,
        len(defaults),
        time.monotonic() - t0,
    )
