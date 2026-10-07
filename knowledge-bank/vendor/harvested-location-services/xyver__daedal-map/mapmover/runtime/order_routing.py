"""Shared order-item routing helpers extracted from the executor."""

from __future__ import annotations


def _currency_granularity_source_id(item: dict) -> str | None:
    if str(item.get("pack_id") or "").strip() != "currency":
        return None
    granularity = str(item.get("time_granularity") or "").strip().lower()
    if granularity == "weekly":
        return "fx_usd_historical_weekly"
    if granularity == "monthly":
        return "fx_usd_historical_monthly"
    if granularity == "daily":
        return "fx_usd_historical"
    return None


def resolve_source_for_item(item: dict, catalog: dict, *, resolve_pack_source_func) -> str | None:
    """Resolve the correct source_id for an order item."""
    pack_id = item.get("pack_id")
    source_id = item.get("source_id")

    if not pack_id:
        return source_id

    resolved_source = resolve_pack_source_func(catalog, pack_id, item.get("region"), item)
    if resolved_source:
        return resolved_source

    return None


def normalize_order_items(
    items: list,
    catalog: dict,
    *,
    resolve_source_for_item_func,
    logger,
) -> list:
    """Resolve pack_id -> source_id for all items in an order."""
    catalog_sources = {
        str(src.get("source_id") or "").strip(): src
        for src in catalog.get("sources", [])
        if src.get("source_id")
    }
    resolved = []
    for item in items:
        item = dict(item)
        source_id = str(item.get("source_id") or "").strip()
        pack_id = item.get("pack_id")
        currency_source_id = _currency_granularity_source_id(item)
        if currency_source_id:
            item["source_id"] = currency_source_id
            resolved.append(item)
            continue
        if pack_id and source_id:
            src = catalog_sources.get(source_id)
            if src and src.get("pack_id") == pack_id:
                resolved.append(item)
                continue
        if pack_id:
            item["source_id"] = resolve_source_for_item_func(item, catalog)
            logger.debug(f"[routing] pack_id={item['pack_id']} region={item.get('region')} -> source_id={item['source_id']}")
        resolved.append(item)
    return resolved
