"""Closed-form tests for overlay_layers and dissolve_layer.

Overlay fixture: square A = [0,10]², square B = [5,15]², same metric CRS. On
paper: intersection is the square [5,10]² (1 feature, area 25); union splits
into A-only, B-only and A∩B (3 features, total area 175); difference A−B keeps
75. Dissolve fixture: four unit squares keyed {a,a,b,b} with values {1,2,3,4}:
by=zone/sum gives exactly two features with v = {a: 3, b: 7}.
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


@pytest.fixture
def two_squares(tmp_path):
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    gpd.GeoDataFrame({"ida": [1]}, geometry=[_square(0, 0, 10)], crs=CRS).to_parquet(a)
    gpd.GeoDataFrame({"idb": [2]}, geometry=[_square(5, 5, 10)], crs=CRS).to_parquet(b)
    return str(a), str(b)


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def test_overlay_intersection_has_the_closed_form_area(two_squares, tmp_path):
    a, b = two_squares
    out = tmp_path / "inter.parquet"
    result = vector.overlay(a, b, str(out))
    assert result["feature_count"] == 1
    assert float(gpd.read_parquet(out).area.sum()) == 25.0
    manifest = _manifest(out)
    assert manifest["operation"] == "overlay_layers"
    assert manifest["parameters"]["how"] == "intersection"
    assert any("lower dimension" in note for note in manifest["notes"])


def test_overlay_union_and_difference_split_as_derived(two_squares, tmp_path):
    a, b = two_squares
    union_out = tmp_path / "union.parquet"
    assert vector.overlay(a, b, str(union_out), how="union")["feature_count"] == 3
    assert float(gpd.read_parquet(union_out).area.sum()) == 175.0
    diff_out = tmp_path / "diff.parquet"
    assert vector.overlay(a, b, str(diff_out), how="difference")["feature_count"] == 1
    assert float(gpd.read_parquet(diff_out).area.sum()) == 75.0


def test_overlay_records_the_reprojection_decision(two_squares, tmp_path):
    a, _ = two_squares
    b_geo = tmp_path / "b_geo.parquet"
    gpd.GeoDataFrame(
        {"idb": [2]}, geometry=[_square(5, 5, 10)], crs=CRS
    ).to_crs("EPSG:4326").to_parquet(b_geo)
    out = tmp_path / "inter_mixed.parquet"
    result = vector.overlay(a, str(b_geo), str(out))
    assert result["feature_count"] == 1
    manifest = _manifest(out)
    # Which input moved and how, rather than a sentence containing the word.
    # A prose assertion passes on any rewording and fails on every rewording,
    # which is the wrong way round: it survives a change of meaning and breaks
    # on a change of style.
    decisions = manifest["crs_decisions"]
    assert decisions["x-mapsmith:inputs_reprojected"] == [
        {"argument": "overlay_path", "from": "EPSG:4326"}
    ]
    assert decisions["transformation"]["is_ballpark"] is False
    # The reprojection round-trip costs float precision, not correctness.
    assert float(gpd.read_parquet(out).area.sum()) == pytest.approx(25.0, abs=1e-6)


def test_overlay_refuses_a_bad_how_and_a_crs_less_input(two_squares, tmp_path):
    a, b = two_squares
    with pytest.raises(ValueError, match="intersection.*union|how must be"):
        vector.overlay(a, b, str(tmp_path / "x.parquet"), how="clip")
    naked = tmp_path / "naked.parquet"
    gpd.GeoDataFrame({"i": [1]}, geometry=[_square(0, 0, 1)], crs=None).to_parquet(naked)
    with pytest.raises(Exception, match="CRS"):
        vector.overlay(str(naked), b, str(tmp_path / "y.parquet"))


@pytest.fixture
def zoned(tmp_path):
    path = tmp_path / "zones.parquet"
    gpd.GeoDataFrame(
        {"zone": ["a", "a", "b", "b"], "v": [1, 2, 3, 4]},
        geometry=[_square(0, 0, 1), _square(1, 0, 1), _square(0, 2, 1), _square(1, 2, 1)],
        crs=CRS,
    ).to_parquet(path)
    return str(path)


def test_dissolve_by_key_sums_exactly(zoned, tmp_path):
    out = tmp_path / "dissolved.parquet"
    result = vector.dissolve(zoned, str(out), by="zone", aggfunc="sum")
    assert result["feature_count"] == 2
    frame = gpd.read_parquet(out)
    assert dict(zip(frame["zone"], frame["v"], strict=True)) == {"a": 3, "b": 7}
    assert float(frame.area.sum()) == 4.0
    manifest = _manifest(out)
    assert manifest["parameters"] == {"by": "zone", "aggfunc": "sum"}
    counts = [c for c in manifest["verification"] if c["name"] == "feature_count_exact"]
    assert counts and counts[0]["passed"]


def test_dissolve_without_a_key_yields_one_feature(zoned, tmp_path):
    out = tmp_path / "one.parquet"
    assert vector.dissolve(zoned, str(out))["feature_count"] == 1
    assert float(gpd.read_parquet(out).area.sum()) == 4.0


def test_dissolve_counts_the_dropped_null_keys_in_the_manifest(tmp_path):
    path = tmp_path / "gaps.parquet"
    gpd.GeoDataFrame(
        {"zone": ["a", None, "b"], "v": [1, 2, 3]},
        geometry=[_square(0, 0, 1), _square(1, 0, 1), _square(2, 0, 1)],
        crs=CRS,
    ).to_parquet(path)
    out = tmp_path / "dissolved.parquet"
    result = vector.dissolve(str(path), str(out), by="zone")
    assert result["feature_count"] == 2  # the null-keyed feature is dropped, not merged
    manifest = _manifest(out)
    assert any("null" in note and "dropped" in note for note in manifest["notes"])


def test_dissolve_refuses_a_missing_column_and_names_the_real_ones(zoned, tmp_path):
    with pytest.raises(ValueError, match="does not exist.*zone"):
        vector.dissolve(zoned, str(tmp_path / "x.parquet"), by="region")
    with pytest.raises(ValueError, match="aggfunc must be"):
        vector.dissolve(zoned, str(tmp_path / "y.parquet"), by="zone", aggfunc="std")
