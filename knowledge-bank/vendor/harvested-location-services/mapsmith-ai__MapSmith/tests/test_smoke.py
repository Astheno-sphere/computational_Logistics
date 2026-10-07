"""Smoke tests: the core promise — deterministic ops + provenance manifests."""

import json

import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from mapsmith import catalog
from mapsmith.engines import vector


@pytest.fixture()
def points_gpkg(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(9.19, 45.46), Point(9.20, 45.47)],  # Milan-ish, EPSG:4326
        crs="EPSG:4326",
    )
    path = tmp_path / "points.gpkg"
    gdf.to_file(path)
    return path


def test_describe(points_gpkg):
    info = vector.describe(str(points_gpkg))
    assert info["feature_count"] == 2
    assert info["crs"] == "EPSG:4326"
    assert "Point" in info["geometry_types"]


def test_buffer_writes_output_and_provenance(points_gpkg, tmp_path):
    out = tmp_path / "buffered.gpkg"
    result = vector.buffer(str(points_gpkg), 300.0, str(out))
    assert out.exists()
    manifest = json.loads((tmp_path / "buffered.gpkg.provenance.json").read_text())
    assert manifest["operation"] == "buffer_layer"
    assert manifest["parameters"]["distance_meters"] == 300.0
    assert manifest["inputs"][0]["sha256"]
    assert "UTM" in manifest["crs_decisions"]["reason"] or "utm" in manifest["crs_decisions"]["reason"].lower()
    assert manifest["finished_at"]
    assert result["feature_count"] == 2
    # buffered geometries must be polygons back in the original CRS
    buffered = gpd.read_file(out)
    assert str(buffered.crs) == "EPSG:4326"
    assert set(buffered.geom_type) == {"Polygon"}


def test_buffer_writes_geoparquet(points_gpkg, tmp_path):
    """GeoParquet is the canonical format: writers must produce it natively."""
    out = tmp_path / "buffered.parquet"
    result = vector.buffer(str(points_gpkg), 100.0, str(out))
    assert result["verified"] is True
    round_trip = gpd.read_parquet(out)
    assert len(round_trip) == 2
    assert round_trip.crs.to_epsg() == 4326


def test_buffer_refuses_missing_crs(tmp_path):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(0, 0)], crs=None)
    src = tmp_path / "nocrs.gpkg"
    gdf.to_file(src)
    with pytest.raises(ValueError, match="no CRS"):
        vector.buffer(str(src), 10.0, str(tmp_path / "out.gpkg"))


def test_clip(points_gpkg, tmp_path):
    mask = gpd.GeoDataFrame(geometry=[box(9.185, 45.455, 9.195, 45.465)], crs="EPSG:4326")
    mask_path = tmp_path / "mask.gpkg"
    mask.to_file(mask_path)
    out = tmp_path / "clipped.gpkg"
    result = vector.clip(str(points_gpkg), str(mask_path), str(out))
    assert result["feature_count"] == 1  # only point "a" falls inside the mask


def test_catalog_search():
    assert any(op["name"] == "buffer_layer" for op in catalog.search("buffer"))
    assert all(op["status"] in {"available", "planned"} for op in catalog.search())
    # Empty is a property of BM25, which shares no term with this; the default
    # engine answers with a clarification instead. See test_catalog.py.
    assert catalog.search("nonexistent-xyz", engine="lexical") == []


def test_server_tools_carry_mcp_annotations():
    from mapsmith import server

    tools = {t.name: t for t in server.mcp._tool_manager.list_tools()}
    assert tools["describe_dataset"].annotations.readOnlyHint is True
    assert tools["buffer_layer"].annotations.destructiveHint is False
    assert tools["buffer_layer"].annotations.idempotentHint is True
    assert tools["run_sql"].annotations.destructiveHint is True
    assert all(t.annotations is not None for t in tools.values())
