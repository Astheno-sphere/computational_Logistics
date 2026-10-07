"""Order-dispatch helpers extracted from the main executor."""

from __future__ import annotations


def prepare_execution_items(
    *,
    items: list,
    load_catalog_func,
    normalize_order_items_func,
    get_source_data_type_func,
    source_supports_disaster_aggregates_func,
    validate_execution_items_func,
) -> tuple[list, str | None]:
    """Normalize items, infer aggregate mode, and validate execution inputs."""
    prepared_items = normalize_order_items_func(items, load_catalog_func())
    for item in prepared_items:
        if item.get("mode"):
            continue
        source_id = item.get("source_id")
        if not source_id:
            continue
        if (
            get_source_data_type_func(source_id) == "metrics"
            and source_supports_disaster_aggregates_func(source_id)
        ):
            item["mode"] = "aggregate"
    validation_error = validate_execution_items_func(prepared_items)
    return prepared_items, validation_error
