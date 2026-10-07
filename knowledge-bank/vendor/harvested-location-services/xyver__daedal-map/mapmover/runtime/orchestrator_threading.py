"""Shared async helpers for catalog-scoped lane orchestrator execution."""

from __future__ import annotations

import asyncio

from mapmover.catalog_surface import catalog_surface_scope


async def run_catalog_scoped_to_thread(
    *,
    catalog_surface: str | None,
    func,
    **kwargs,
):
    """Run one blocking lane helper inside the selected catalog surface."""
    with catalog_surface_scope(catalog_surface):
        return await asyncio.to_thread(func, **kwargs)


async def run_catalog_scoped_to_thread_with_progress(
    *,
    catalog_surface: str | None,
    progress_bus_cls,
    func,
    **kwargs,
) -> tuple[object, asyncio.Task]:
    """Run one blocking lane helper with a shared progress bus wrapper."""
    bus = progress_bus_cls()
    with catalog_surface_scope(catalog_surface):
        task = asyncio.create_task(
            asyncio.to_thread(
                func,
                progress=bus.thread_emitter(),
                **kwargs,
            )
        )
    return bus, task
