"""Tests for raster tools — sandboxing and round-trip computation."""

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from locusync.config import Config, set_config  # noqa: E402
from locusync.tools.raster import (  # noqa: E402
    calculate_slope,
    raster_calculator,
    read_raster,
)


@pytest.fixture
def sandbox(tmp_path):
    cfg = Config()
    cfg.workdir = str(tmp_path)
    set_config(cfg)
    return tmp_path


def _write_tiff(path, array):
    array = array.astype(np.float32)
    transform = rasterio.transform.from_origin(0, array.shape[0], 1, 1)
    with rasterio.open(
        str(path), "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
        count=1, dtype="float32", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(array, 1)


class TestReadRaster:
    @pytest.mark.asyncio
    async def test_read_and_stats(self, sandbox):
        _write_tiff(sandbox / "r.tif", np.arange(25).reshape(5, 5))
        result = await read_raster("r.tif")
        assert result["success"] is True
        assert result["data"]["metadata"]["width"] == 5
        stats = result["data"]["statistics"][0]
        assert stats["min"] == 0.0 and stats["max"] == 24.0

    @pytest.mark.asyncio
    async def test_outside_sandbox_blocked(self, sandbox):
        result = await read_raster("/etc/hosts")
        assert result["success"] is False
        assert "outside" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_file(self, sandbox):
        result = await read_raster("nope.tif")
        assert result["success"] is False


class TestSlope:
    @pytest.mark.asyncio
    async def test_flat_dem_zero_slope(self, sandbox):
        _write_tiff(sandbox / "flat.tif", np.ones((5, 5)) * 100)
        result = await calculate_slope("flat.tif")
        assert result["success"] is True
        assert result["data"]["statistics"]["max"] == pytest.approx(0.0, abs=1e-6)


class TestRasterCalculator:
    @pytest.mark.asyncio
    async def test_expression_round_trip(self, sandbox):
        _write_tiff(sandbox / "a.tif", np.full((4, 4), 2.0))
        _write_tiff(sandbox / "b.tif", np.full((4, 4), 3.0))
        result = await raster_calculator(
            "A + B", {"A": "a.tif", "B": "b.tif"}, "out.tif"
        )
        assert result["success"] is True
        assert result["data"]["statistics"]["mean"] == pytest.approx(5.0)
        assert (sandbox / "out.tif").exists()

    @pytest.mark.asyncio
    async def test_invalid_expression_chars(self, sandbox):
        _write_tiff(sandbox / "a.tif", np.ones((3, 3)))
        result = await raster_calculator(
            "__import__('os')", {"A": "a.tif"}, "out.tif"
        )
        assert result["success"] is False
        assert "invalid characters" in result["error"].lower()
