"""Shared support helpers for order execution wiring."""

from __future__ import annotations


def load_runtime_catalog():
    """Load catalog via data_loading with its normal cache behavior."""
    from mapmover.data_loading import load_catalog as load_catalog_impl

    return load_catalog_impl()


def validate_runtime_execution_items(
    items: list,
    *,
    get_source_from_catalog_func,
    execution_requires_metric_func,
    validate_execution_items_func,
):
    return validate_execution_items_func(
        items,
        get_source_from_catalog_func=get_source_from_catalog_func,
        execution_requires_metric_func=execution_requires_metric_func,
    )


def build_runtime_source_path(
    source_id: str,
    *,
    get_source_path_func,
    load_catalog_func,
    data_root,
):
    return get_source_path_func(
        source_id,
        load_catalog_func=load_catalog_func,
        data_root=data_root,
    )
