"""Closed-form tests for centroid_layer and convert_format.

Centroid fixture: a 10x10 square at the origin and the right triangle
(0,0)-(3,0)-(0,3), both in a metric CRS. On paper the centroids are exactly
(5,5) and (1,1). Convert fixture: the same layer written across formats must
come back with the same count and CRS; the two refusals (shapefile, non-WGS84
GeoJSON) are contracts, so they are tested as such.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from mapsmith.engines import vector

CRS = "EPSG:32632"


def _square(x0: float, y0: float, side: float) -> Polygon:
    return Polygon([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)])


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


@pytest.fixture
def shapes(tmp_path):
    path = tmp_path / "shapes.parquet"
    triangle = Polygon([(0, 0), (3, 0), (0, 3)])
    gpd.GeoDataFrame(
        {"name": ["square", "triangle"]},
        geometry=[_square(0, 0, 10), triangle],
        crs=CRS,
    ).to_parquet(path)
    return str(path)


def test_centroids_land_on_the_closed_form_points(shapes, tmp_path):
    out = tmp_path / "points.parquet"
    result = vector.centroid(shapes, str(out))
    assert result["feature_count"] == 2
    frame = gpd.read_parquet(out)
    assert set(frame.geom_type) == {"Point"}
    by_name = {row["name"]: row.geometry for _, row in frame.iterrows()}
    assert (by_name["square"].x, by_name["square"].y) == (5.0, 5.0)
    assert (by_name["triangle"].x, by_name["triangle"].y) == (1.0, 1.0)
    manifest = _manifest(out)
    assert manifest["operation"] == "centroid_layer"
    assert "native projected CRS" in manifest["crs_decisions"]["reason"]
    assert any("outside" in note for note in manifest["notes"])


def test_centroid_on_geographic_crs_records_utm_and_returns_the_input_crs(
    shapes, tmp_path
):
    geo = tmp_path / "shapes_geo.parquet"
    gpd.read_parquet(shapes).to_crs("EPSG:4326").to_parquet(geo)
    out = tmp_path / "points_geo.parquet"
    result = vector.centroid(str(geo), str(out))
    assert result["feature_count"] == 2
    frame = gpd.read_parquet(out)
    assert frame.crs.to_epsg() == 4326
    assert set(frame.geom_type) == {"Point"}
    manifest = _manifest(out)
    assert "UTM" in manifest["crs_decisions"]["reason"]
    # The metric centroid, reprojected back, must still sit inside the shape's
    # bounding box in degrees — a degrees-as-planar centroid can drift out.
    source = gpd.read_parquet(geo)
    minx, miny, maxx, maxy = source.total_bounds
    assert ((frame.geometry.x >= minx) & (frame.geometry.x <= maxx)).all()
    assert ((frame.geometry.y >= miny) & (frame.geometry.y <= maxy)).all()


def test_centroid_empty_geographic_layer_writes_a_manifest_not_a_crash(tmp_path):
    empty = tmp_path / "empty.parquet"
    gpd.GeoDataFrame({"i": []}, geometry=[], crs="EPSG:4326").to_parquet(empty)
    out = tmp_path / "empty_points.parquet"
    result = vector.centroid(str(empty), str(out))
    assert result["feature_count"] == 0
    manifest = _manifest(out)
    assert "empty input layer" in manifest["crs_decisions"]["reason"]


def test_centroid_refuses_a_crs_less_input(tmp_path):
    naked = tmp_path / "naked.parquet"
    gpd.GeoDataFrame({"i": [1]}, geometry=[_square(0, 0, 1)], crs=None).to_parquet(naked)
    with pytest.raises(ValueError, match="no CRS"):
        vector.centroid(str(naked), str(tmp_path / "x.parquet"))


def test_convert_round_trips_count_and_crs_across_formats(shapes, tmp_path):
    gpkg = tmp_path / "shapes.gpkg"
    result = vector.convert(shapes, str(gpkg))
    assert result["format"] == "GeoPackage"
    assert result["feature_count"] == 2
    back = tmp_path / "back.parquet"
    result = vector.convert(str(gpkg), str(back))
    assert result["format"] == "GeoParquet"
    frame = gpd.read_parquet(back)
    assert len(frame) == 2
    assert frame.crs.to_epsg() == 32632
    assert float(frame.area.sum()) == 104.5  # 100 + 4.5, carried exactly
    manifest = _manifest(back)
    assert manifest["operation"] == "convert_format"
    assert manifest["parameters"]["target_format"] == "GeoParquet"


def test_convert_writes_geojson_only_for_wgs84(shapes, tmp_path):
    with pytest.raises(ValueError, match="RFC 7946"):
        vector.convert(shapes, str(tmp_path / "shapes.geojson"))
    geo = tmp_path / "shapes_geo.parquet"
    gpd.read_parquet(shapes).to_crs("EPSG:4326").to_parquet(geo)
    out = tmp_path / "shapes.geojson"
    result = vector.convert(str(geo), str(out))
    assert result["format"] == "GeoJSON"
    assert result["feature_count"] == 2


def test_convert_accepts_crs84_for_geojson(shapes, tmp_path):
    # OGC:CRS84 is WGS84 lon-lat — exactly what RFC 7946 prescribes, and the
    # GeoParquet default when the `geo` key carries no CRS. It must not be
    # refused with an instruction to "reproject to WGS84" a layer already there.
    crs84 = tmp_path / "shapes_crs84.parquet"
    gpd.read_parquet(shapes).to_crs("OGC:CRS84").to_parquet(crs84)
    out = tmp_path / "shapes_crs84.geojson"
    result = vector.convert(str(crs84), str(out))
    assert result["format"] == "GeoJSON"
    assert result["feature_count"] == 2


def test_convert_refuses_shapefile_and_unknown_formats(shapes, tmp_path):
    with pytest.raises(ValueError, match="shapefile"):
        vector.convert(shapes, str(tmp_path / "shapes.shp"))
    with pytest.raises(ValueError, match="not supported"):
        vector.convert(shapes, str(tmp_path / "shapes.xyz"))
