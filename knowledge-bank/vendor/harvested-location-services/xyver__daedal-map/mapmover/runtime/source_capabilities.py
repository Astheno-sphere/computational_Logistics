from __future__ import annotations


def get_source_data_type(
    source_id: str,
    *,
    load_catalog_func,
) -> str:
    """
    Return the declared data_type for a source, defaulting to metrics.
    """
    catalog = load_catalog_func()
    for src in catalog.get("sources", []):
        if src.get("source_id") == source_id:
            return src.get("data_type", "metrics")
    return "metrics"
