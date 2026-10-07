"""Closed-form tests for raster description and describe routing.

The fixture is a 5x5 grid with value = row * 10 + column and two cells set to
nodata, so every reported number is checkable by hand: 23 valid cells, and the
masked mean excludes exactly the two masked values.
"""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from mapsmith.engines import dispatch, raster

NODATA = -9999.0


@pytest.fixture
def small_raster(tmp_path):
    from rasterio.transform import from_origin

    data = (np.arange(25, dtype="float64").reshape(5, 5) // 5) * 10 + np.arange(25).reshape(5, 5) % 5
    data[0, 0] = NODATA  # was 0
    data[4, 4] = NODATA  # was 44
    path = tmp_path / "grid.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=5, width=5, count=1, dtype="float64",
        crs="EPSG:32632", transform=from_origin(500_000, 5_000_000, 10, 10), nodata=NODATA,
    ) as ds:
        ds.write(data, 1)
    return str(path)


def test_describe_reports_grid_crs_and_masked_statistics(small_raster):
    info = raster.describe(small_raster)
    assert info["kind"] == "raster"
    assert (info["width"], info["height"], info["band_count"]) == (5, 5, 1)
    assert info["resolution"] == {"x": 10.0, "y": 10.0}
    assert "32632" in info["crs"]
    band = info["bands"][0]
    assert band["nodata"] == NODATA
    assert (band["valid_cells"], band["nodata_cells"]) == (23, 2)
    # Sum of value = row*10 + col over the grid: rows contribute 10*(0+..+4)*5
    # = 500, columns contribute (0+..+4)*5 = 50, total 550; minus the two
    # masked values (0 and 44) over the 23 remaining cells: 506/23.
    assert band["min"] == 1.0
    assert band["max"] == 43.0
    assert band["mean"] == pytest.approx(506 / 23)


def test_describe_routed_sends_rasters_and_vectors_to_the_right_reader(small_raster, tmp_path):
    assert dispatch.describe_routed(small_raster)["kind"] == "raster"

    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Point

    vec = tmp_path / "points.gpkg"
    gpd.GeoDataFrame(
        {"id": [1, 2]}, geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:32632"
    ).to_file(vec, layer="points", driver="GPKG")
    info = dispatch.describe_routed(str(vec))
    assert info["kind"] == "vector"
    assert info["feature_count"] == 2


def test_describe_routed_reports_the_vector_error_when_both_readers_fail(tmp_path):
    junk = tmp_path / "junk.gpkg"
    junk.write_bytes(b"not a dataset of any kind")
    with pytest.raises(Exception) as excinfo:
        dispatch.describe_routed(str(junk))
    # The vector error is the one re-raised: the caller most likely meant a
    # vector format, and a rasterio complaint about a .gpkg would mislead.
    assert "junk.gpkg" in str(excinfo.value)
