"""Terrain/hydrology on Whitebox: closed-form values, CRS discipline, provenance."""

import json
import math

import geopandas as gpd
import pytest
from shapely.geometry import Point

wb = pytest.importorskip("whitebox_workflows")
rasterio = pytest.importorskip("rasterio")

import numpy as np
from rasterio.transform import from_origin

from mapsmith.engines import whitebox_engine


def _write_dem(path, data, crs="EPSG:32631"):
    height, width = data.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=from_origin(0.0, float(height), 1.0, 1.0),
        nodata=-32768.0,
    ) as dst:
        dst.write(data, 1)
    return str(path)


@pytest.fixture()
def flat_dem(tmp_path):
    """10x10 flat DEM at elevation 100: hillshade must be uniform."""
    return _write_dem(tmp_path / "flat.tif", np.full((10, 10), 100.0, dtype=np.float32))


@pytest.fixture()
def tilted_dem(tmp_path):
    """5x5 plane z=col (rises eastward): every cell drains due west."""
    zz = np.tile(np.arange(5, dtype=np.float32), (5, 1))
    return _write_dem(tmp_path / "tilt.tif", zz)


@pytest.fixture()
def valley_dem(tmp_path):
    """5x5 V-valley along col 2, channel descending south: all drains to (4,2)."""
    vz = np.zeros((5, 5), dtype=np.float32)
    for r in range(5):
        for c in range(5):
            vz[r, c] = abs(c - 2) * 10 + (4 - r)
    return _write_dem(tmp_path / "valley.tif", vz)


def test_hillshade_flat_dem_closed_form(flat_dem, tmp_path):
    """Flat terrain: hillshade = 32767*sin(altitude) everywhere (upstream clamp: +-6)."""
    out = tmp_path / "hs.tif"
    result = whitebox_engine.hillshade(flat_dem, str(out), altitude=30.0)
    assert result["verified"] is True
    with rasterio.open(out) as ds:
        assert ds.crs.to_epsg() == 32631  # CRS preserved
        arr = ds.read(1)
        valid = arr[arr != ds.nodata]
    assert len(np.unique(valid)) == 1  # perfectly uniform on flat ground
    expected = 32767 * math.sin(math.radians(30.0))
    assert abs(float(valid[0]) - expected) <= 6


def test_hillshade_provenance_and_verification(flat_dem, tmp_path):
    out = tmp_path / "hs45.tif"
    whitebox_engine.hillshade(flat_dem, str(out), altitude=45.0)
    manifest = json.loads((tmp_path / "hs45.tif.provenance.json").read_text())
    assert manifest["operation"] == "hillshade"
    assert manifest["parameters"]["altitude"] == 45.0
    assert manifest["engine"]["name"] == "whitebox-workflows"
    assert manifest["inputs"][0]["sha256"]
    assert manifest["crs_decisions"]["analysis_crs"] == "EPSG:32631"
    names = {c["name"]: c["passed"] for c in manifest["verification"]}
    assert names["crs_matches"] is True
    assert names["shape_preserved"] is True
    assert names["values_in_expected_range"] is True


def test_hillshade_rejects_dem_without_crs(tmp_path):
    dem = _write_dem(tmp_path / "nocrs.tif", np.ones((5, 5), dtype=np.float32), crs=None)
    with pytest.raises(ValueError, match="no CRS"):
        whitebox_engine.hillshade(dem, str(tmp_path / "x.tif"))


def test_hillshade_rejects_bad_angles(flat_dem, tmp_path):
    with pytest.raises(ValueError, match="azimuth"):
        whitebox_engine.hillshade(flat_dem, str(tmp_path / "x.tif"), azimuth=400)
    with pytest.raises(ValueError, match="altitude"):
        whitebox_engine.hillshade(flat_dem, str(tmp_path / "x.tif"), altitude=91)


def test_flow_accumulation_closed_form(tilted_dem, tmp_path):
    """On z=col every row accumulates 1,2,3,4,5 from east to west — exactly."""
    out = tmp_path / "acc.tif"
    result = whitebox_engine.flow_accumulation(tilted_dem, str(out))
    assert result["verified"] is True
    with rasterio.open(out) as ds:
        arr = ds.read(1)
    expected_row = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    for r in range(5):
        assert np.array_equal(arr[r], expected_row), f"row {r}: {arr[r]}"


def test_flow_accumulation_rejects_bad_out_type(tilted_dem, tmp_path):
    with pytest.raises(ValueError, match="out_type"):
        whitebox_engine.flow_accumulation(tilted_dem, str(tmp_path / "x.tif"), out_type="acres")


def test_flow_accumulation_rejects_sca_on_geographic_dem(tmp_path):
    """SCA divides by cell width: meaningless in degrees, must be refused."""
    zz = np.tile(np.arange(5, dtype=np.float32), (5, 1))
    dem = _write_dem(tmp_path / "geo.tif", zz, crs="EPSG:4326")
    with pytest.raises(ValueError, match="projected"):
        whitebox_engine.flow_accumulation(dem, str(tmp_path / "x.tif"), out_type="sca")


def test_hillshade_on_geographic_dem_records_the_caveat(tmp_path):
    """Geographic DEMs are allowed but the manifest must say cells are degrees."""
    dem = _write_dem(tmp_path / "geo30.tif", np.full((6, 6), 55.0, dtype=np.float32), crs="EPSG:4326")
    out = tmp_path / "hs_geo.tif"
    whitebox_engine.hillshade(dem, str(out))
    manifest = json.loads((tmp_path / "hs_geo.tif.provenance.json").read_text())
    assert "geographic" in manifest["crs_decisions"]["reason"]


def test_hillshade_handles_nan_nodata(tmp_path):
    """NaN nodata must not leak into the value-range verification."""
    data = np.full((8, 8), 200.0, dtype=np.float32)
    data[0, 0] = np.nan
    path = tmp_path / "nan_dem.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=8,
        width=8,
        count=1,
        dtype="float32",
        crs="EPSG:32631",
        transform=from_origin(0.0, 8.0, 1.0, 1.0),
        nodata=float("nan"),
    ) as dst:
        dst.write(data, 1)
    out = tmp_path / "hs_nan.tif"
    result = whitebox_engine.hillshade(str(path), str(out))
    assert result["verified"] is True


def test_watershed_single_outlet_captures_whole_valley(valley_dem, tmp_path):
    """One outlet at the valley mouth: all 25 cells belong to watershed 1."""
    pts = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(2.5, 0.5)], crs="EPSG:32631")
    pts_path = tmp_path / "outlet.gpkg"
    pts.to_file(pts_path)
    out = tmp_path / "ws.tif"
    result = whitebox_engine.watershed(valley_dem, str(pts_path), str(out))
    assert result["verified"] is True
    assert result["n_pour_points"] == 1
    with rasterio.open(out) as ds:
        arr = ds.read(1)
    assert np.array_equal(arr, np.ones((5, 5), dtype=arr.dtype))


def test_watershed_reprojects_pour_points_and_records_it(valley_dem, tmp_path):
    """Pour points in WGS84: engine must align them to the DEM CRS and record it."""
    pts = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(2.5, 0.5)], crs="EPSG:32631")
    pts_4326 = pts.to_crs("EPSG:4326")
    pts_path = tmp_path / "outlet4326.gpkg"
    pts_4326.to_file(pts_path)
    out = tmp_path / "ws2.tif"
    result = whitebox_engine.watershed(valley_dem, str(pts_path), str(out))
    manifest = json.loads((tmp_path / "ws2.tif.provenance.json").read_text())
    # A pour point on the wrong cell delineates a different watershed, so the
    # transformation that put it there belongs in the record by name.
    decisions = manifest["crs_decisions"]
    assert decisions["x-mapsmith:inputs_reprojected"] == [
        {"argument": "pour_points_path", "from": "EPSG:4326"}
    ]
    assert decisions["transformation"]["is_ballpark"] is False
    assert result["verified"] is True


def test_watershed_rejects_non_point_geometries(valley_dem, tmp_path):
    from shapely.geometry import box

    polys = gpd.GeoDataFrame({"id": [1]}, geometry=[box(0, 0, 1, 1)], crs="EPSG:32631")
    p = tmp_path / "polys.gpkg"
    polys.to_file(p)
    with pytest.raises(ValueError, match="Point"):
        whitebox_engine.watershed(valley_dem, str(p), str(tmp_path / "x.tif"))


def test_watershed_rejects_points_without_crs(valley_dem, tmp_path):
    pts = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(2.5, 0.5)], crs=None)
    p = tmp_path / "nocrs_pts.gpkg"
    pts.to_file(p)
    with pytest.raises(ValueError, match="no CRS"):
        whitebox_engine.watershed(valley_dem, str(p), str(tmp_path / "x.tif"))
