from __future__ import annotations

import logging


def expand_wildcard_metrics(
    items: list,
    *,
    load_catalog_func,
    resolve_pack_source_func,
    load_source_metadata_func,
    metadata_metric_year_range_func,
) -> list:
    """
    Expand wildcard metrics (metric="*", "all", "all_metrics") into one item per metric.
    """
    expanded = []
    catalog = load_catalog_func()

    for item in items:
        if item.get("mode") == "events":
            expanded.append(item)
            continue

        metric = item.get("metric")
        if metric not in ("*", "all", "all_metrics"):
            expanded.append(item)
            continue

        source_id = item.get("source_id")
        if not source_id and item.get("pack_id"):
            resolved_source = resolve_pack_source_func(catalog, item.get("pack_id"), item.get("region"), item)
            if resolved_source:
                item["source_id"] = resolved_source
                item["_resolved_from_pack"] = True
                source_id = resolved_source

        if not source_id:
            expanded.append(item)
            continue

        metadata = load_source_metadata_func(source_id)
        if not metadata or not metadata.get("metrics"):
            expanded.append(item)
            continue

        metrics = metadata.get("metrics", {})
        single_metric_default = str(
            (((metadata.get("routing_hints") or {}).get("single_metric_default")) or "")
        ).strip()
        metric_keys = [single_metric_default] if single_metric_default in metrics else list(metrics.keys())

        for metric_key in metric_keys:
            new_item = dict(item)
            new_item["source_id"] = source_id
            new_item["metric"] = metric_key
            new_item.pop("_error", None)
            new_item.pop("_valid", None)

            metric_min_year, metric_max_year = metadata_metric_year_range_func(metadata, metric_key)
            has_explicit_time = bool(
                new_item.get("year") is not None or new_item.get("year_start") or new_item.get("year_end")
            )
            if not has_explicit_time and metric_min_year is not None and metric_max_year is not None:
                new_item["year_start"] = metric_min_year
                new_item["year_end"] = metric_max_year

            new_item = {k: v for k, v in new_item.items() if v is not None}
            expanded.append(new_item)

        logging.getLogger(__name__).info(
            f"Expanded wildcard metric for {source_id}: {len(metric_keys)} metrics"
        )

    return expanded
