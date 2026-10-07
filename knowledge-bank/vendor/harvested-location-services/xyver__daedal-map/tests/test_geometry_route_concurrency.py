import asyncio
import time
from unittest.mock import patch

import pytest

from mapmover.routes import geometry


@pytest.mark.parametrize(
    "endpoint",
    (
        geometry.get_selection_geometry_endpoint,
        geometry.get_geometry_features_endpoint,
        geometry.get_display_geometry_features_endpoint,
    ),
)
def test_geometry_loading_does_not_block_event_loop(endpoint) -> None:
    async def decode_request_body(_request):
        return {"loc_ids": ["USA-VA-600"]}

    def slow_geometry_load(_loc_ids):
        time.sleep(0.2)
        return {"type": "FeatureCollection", "features": []}

    async def run_check() -> None:
        started = time.monotonic()
        task = asyncio.create_task(endpoint(object()))
        await asyncio.sleep(0.02)

        assert time.monotonic() - started < 0.1
        assert not task.done()
        await task

    with (
        patch.object(geometry, "decode_request_body", decode_request_body),
        patch.object(geometry, "get_selection_geometries_handler", slow_geometry_load),
        patch.object(geometry, "get_display_geometries_handler", slow_geometry_load),
    ):
        asyncio.run(run_check())
