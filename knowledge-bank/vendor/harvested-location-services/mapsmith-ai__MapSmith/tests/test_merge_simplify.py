"""Closed-form tests for merge_layers and simplify_layer.

Merge fixture: layer A holds 3 unit squares with column `a`; layer B holds 2
unit squares with columns `a` and `b`. On paper: the merge has exactly 5
features, column `b` is null on A's 3 rows, and the manifest names `b` as
null-filled. Simplify fixture: a 10x10 square densified to one vertex per
metre (41 ring coordinates). Douglas-Peucker at any tolerance below the corner
deviation removes only collinear points, so the ring collapses to 5
coordinates and the area stays exactly 100.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

from mapsmith.engines import vector

CRS = "EPSG:32632"


def _square(x0: float, y0: float, side: float) -> Polygon:
    return Polygon([(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)])


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


@pytest.fixture
def two_layers(tmp_path):
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    gpd.GeoDataFrame(
        {"a": [1, 2, 3]},
        geometry=[_square(0, 0, 1), _square(2, 0, 1), _square(4, 0, 1)],
        crs=CRS,
    ).to_parquet(a)
    gpd.GeoDataFrame(
        {"a": [4, 5], "b": ["x", "y"]},
        geometry=[_square(0, 3, 1), _square(2, 3, 1)],
        crs=CRS,
    ).to_parquet(b)
    return str(a), str(b)


def test_merge_count_is_the_sum_and_partial_columns_are_named(two_layers, tmp_path):
    a, b = two_layers
    out = tmp_path / "merged.parquet"
    result = vector.merge([a, b], str(out))
    assert result["feature_count"] == 5
    assert result["layer_count"] == 2
    frame = gpd.read_parquet(out)
    assert len(frame) == 5
    assert int(frame["b"].isna().sum()) == 3
    assert float(frame.area.sum()) == 5.0
    manifest = _manifest(out)
    assert manifest["operation"] == "merge_layers"
    assert any("'b'" in note and "null-filled" in note for note in manifest["notes"])
    # The ordinary branch says which CRS it worked in, and says that nothing
    # moved by carrying no `inputs_reprojected` at all. Until 2026-09-06 several
    # sibling operations left `crs_decisions` empty here, which cannot be told
    # apart from nobody having looked.
    decisions = manifest["crs_decisions"]
    assert decisions["analysis_crs"] == "EPSG:32632"
    assert "nothing was reprojected" in decisions["reason"]
    assert "x-mapsmith:inputs_reprojected" not in decisions


def test_merge_reprojects_to_the_first_layer_and_records_it(two_layers, tmp_path):
    a, b = two_layers
    b_geo = tmp_path / "b_geo.parquet"
    gpd.read_parquet(b).to_crs("EPSG:4326").to_parquet(b_geo)
    out = tmp_path / "merged_mixed.parquet"
    result = vector.merge([a, str(b_geo)], str(out))
    assert result["feature_count"] == 5
    frame = gpd.read_parquet(out)
    assert frame.crs.to_epsg() == 32632
    manifest = _manifest(out)
    # Which layer moved, and from where — not a count. "1 of 2 were
    # reprojected" leaves the reader to work out which one, and the answer is
    # not recoverable from the output.
    decisions = manifest["crs_decisions"]
    assert decisions["analysis_crs"] == "EPSG:32632"
    assert decisions["x-mapsmith:inputs_reprojected"] == [
        {"argument": "input_2", "from": "EPSG:4326"}
    ]
    # And how. One layer moved, so the transformation goes in the key the
    # specification has for it.
    assert decisions["transformation"]["is_ballpark"] is False
    # The reprojection round-trip costs float precision, not correctness.
    assert float(frame.area.sum()) == pytest.approx(5.0, abs=1e-6)


def test_merge_notes_mixed_geometry_classes(two_layers, tmp_path):
    a, _ = two_layers
    points = tmp_path / "points.parquet"
    square = gpd.read_parquet(a)
    gpd.GeoDataFrame(
        {"a": [9]}, geometry=square.geometry.head(1).centroid, crs=CRS
    ).to_parquet(points)
    out = tmp_path / "mixed.parquet"
    result = vector.merge([a, str(points)], str(out))
    assert result["feature_count"] == 4
    manifest = _manifest(out)
    assert any("mixes geometry classes" in note for note in manifest["notes"])


def test_merge_refuses_one_layer_and_a_crs_less_input(two_layers, tmp_path):
    a, _ = two_layers
    with pytest.raises(ValueError, match="at least two"):
        vector.merge([a], str(tmp_path / "x.parquet"))
    naked = tmp_path / "naked.parquet"
    gpd.GeoDataFrame({"i": [1]}, geometry=[_square(0, 0, 1)], crs=None).to_parquet(naked)
    with pytest.raises(Exception, match="CRS"):
        vector.merge([a, str(naked)], str(tmp_path / "y.parquet"))


@pytest.fixture
def dense_square(tmp_path):
    side = [(float(i), 0.0) for i in range(11)]
    side += [(10.0, float(i)) for i in range(1, 11)]
    side += [(float(i), 10.0) for i in range(9, -1, -1)]
    side += [(0.0, float(i)) for i in range(9, 0, -1)]
    ring = Polygon(side)
    assert len(ring.exterior.coords) == 41
    path = tmp_path / "dense.parquet"
    gpd.GeoDataFrame({"i": [1]}, geometry=[ring], crs=CRS).to_parquet(path)
    return str(path)


def test_simplify_removes_collinear_points_and_keeps_the_area(dense_square, tmp_path):
    out = tmp_path / "light.parquet"
    result = vector.simplify(dense_square, 0.5, str(out))
    assert result["feature_count"] == 1
    assert result["vertices_before"] == 41
    assert result["vertices_after"] == 5
    frame = gpd.read_parquet(out)
    assert float(frame.area.sum()) == 100.0
    manifest = _manifest(out)
    assert manifest["operation"] == "simplify_layer"
    assert manifest["parameters"]["preserve_topology"] is True
    # Collinear removal moves no boundary: the recorded drift is exactly zero.
    assert any("+0.0000%" in note and "area" in note for note in manifest["notes"])
    assert any("41 -> 5" in note for note in manifest["notes"])


def test_simplify_line_length_shrinks_by_the_closed_form(tmp_path):
    zigzag = tmp_path / "zigzag.parquet"
    gpd.GeoDataFrame(
        {"i": [1]}, geometry=[LineString([(0, 0), (1, 1), (2, 0)])], crs=CRS
    ).to_parquet(zigzag)
    out = tmp_path / "straight.parquet"
    result = vector.simplify(str(zigzag), 2.0, str(out))
    assert result["vertices_after"] == 2
    assert float(gpd.read_parquet(out).length.sum()) == 2.0


def test_simplify_on_geographic_crs_records_the_utm_decision(dense_square, tmp_path):
    geo = tmp_path / "dense_geo.parquet"
    gpd.read_parquet(dense_square).to_crs("EPSG:4326").to_parquet(geo)
    out = tmp_path / "light_geo.parquet"
    vector.simplify(str(geo), 0.5, str(out))
    frame = gpd.read_parquet(out)
    assert frame.crs.to_epsg() == 4326
    manifest = _manifest(out)
    assert "UTM" in manifest["crs_decisions"]["reason"]


def test_simplify_points_are_a_verified_noop(tmp_path):
    from shapely.geometry import Point

    points = tmp_path / "points.parquet"
    gpd.GeoDataFrame(
        {"i": [1, 2]}, geometry=[Point(0, 0), Point(5, 5)], crs=CRS
    ).to_parquet(points)
    out = tmp_path / "points_out.parquet"
    result = vector.simplify(str(points), 1.0, str(out))
    assert result["feature_count"] == 2
    assert result["vertices_before"] == result["vertices_after"] == 2


def test_simplify_empty_geographic_layer_writes_a_manifest_not_a_crash(tmp_path):
    # estimate_utm_crs() raises a raw pyproj error on an empty frame; the
    # operation must not reach it — an empty layer passes through, audited.
    empty = tmp_path / "empty.parquet"
    gpd.GeoDataFrame({"i": []}, geometry=[], crs="EPSG:4326").to_parquet(empty)
    out = tmp_path / "empty_out.parquet"
    result = vector.simplify(str(empty), 1.0, str(out))
    assert result["feature_count"] == 0
    manifest = _manifest(out)
    assert "empty input layer" in manifest["crs_decisions"]["reason"]


def test_simplify_refuses_a_non_positive_tolerance_and_no_crs(dense_square, tmp_path):
    with pytest.raises(ValueError, match="positive"):
        vector.simplify(dense_square, 0, str(tmp_path / "x.parquet"))
    naked = tmp_path / "naked.parquet"
    gpd.GeoDataFrame({"i": [1]}, geometry=[_square(0, 0, 1)], crs=None).to_parquet(naked)
    with pytest.raises(ValueError, match="no CRS"):
        vector.simplify(str(naked), 1.0, str(tmp_path / "y.parquet"))
