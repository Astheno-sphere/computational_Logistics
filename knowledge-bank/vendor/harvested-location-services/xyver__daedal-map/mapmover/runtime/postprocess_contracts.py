"""Shared postprocess result/display contract helpers."""

from __future__ import annotations


def build_processed_order_result(
    order: dict,
    *,
    validated_items: list,
    derived_specs: list,
    validation_summary: str,
    all_valid: bool,
    summary: str | None,
    metric_warning: dict | None = None,
) -> dict:
    """Build the shared processed-order result payload."""
    result = {
        "items": validated_items,
        "derived_specs": derived_specs,
        "validation_summary": validation_summary,
        "all_valid": all_valid,
        "summary": summary,
        "region": order.get("region"),
        "year": order.get("year"),
        "year_start": order.get("year_start"),
        "year_end": order.get("year_end"),
    }
    if metric_warning:
        result["metric_warning"] = metric_warning
    return result


def get_display_items(items: list, derived_specs: list | None = None) -> list:
    """Return the display-facing subset of postprocessed order items."""
    display = []
    for item in items:
        if not item.get("for_derivation"):
            display.append(item)

    if derived_specs:
        for spec in derived_specs:
            display.append(
                {
                    "type": "derived",
                    "metric": spec.get("label", "Derived"),
                    "metric_label": f"{spec.get('label', 'Derived')} (calculated)",
                    "_valid": True,
                    "_is_derived": True,
                }
            )

    return display


def format_validation_messages(order: dict) -> list[str]:
    """Format validation results as lightweight human-readable messages."""
    messages: list[str] = []
    items = order.get("items", [])

    for item in items:
        if item.get("for_derivation"):
            continue

        if item.get("_valid"):
            source = item.get("source_id", "?")
            metric = item.get("metric_label") or item.get("metric", "?")
            messages.append(f"+ {metric}: Found in {source}")
        else:
            metric = item.get("metric", "?")
            error = item.get("_error", "Unknown error")
            messages.append(f"- {metric}: {error}")

    for spec in order.get("derived_specs", []):
        label = spec.get("label", "Derived")
        messages.append(f"+ {label} (calculated)")

    return messages
