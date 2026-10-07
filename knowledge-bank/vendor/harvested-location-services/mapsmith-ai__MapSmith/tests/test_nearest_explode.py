"""Closed-form tests for nearest_join and explode_layer.

Nearest fixture: schools at (0,0) and (100,0), hospitals at (0,30) and
(100,40) in a metric CRS — distances exactly 30 and 40 by construction, and a
max_distance of 35 keeps exactly one pair. The geographic case places two
points ~300 m apart in EPSG:4326 and expects the distance column in METERS.
Explode fixture: a 3-part multipoint plus a single point — four features out,
counted before the engine ran.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

from mapsmith.engines import vector

CRS = "EPSG:32632"


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


@pytest.fixture
def schools_hospitals(tmp_path):
    schools = tmp_path / "schools.parquet"
    hospitals = tmp_path / "hospitals.parquet"
    gpd.GeoDataFrame(
        {"school": ["s1", "s2"]}, geometry=[Point(0, 0), Point(100, 0)], crs=CRS
    ).to_parquet(schools)
    gpd.GeoDataFrame(
        {"hospital": ["h1", "h2"]}, geometry=[Point(0, 30), Point(100, 40)], crs=CRS
    ).to_parquet(hospitals)
    return str(schools), str(hospitals)


def test_nearest_join_distances_are_exact(schools_hospitals, tmp_path):
    schools, hospitals = schools_hospitals
    out = tmp_path / "joined.parquet"
    result = vector.nearest_join(schools, hospitals, str(out))
    assert result["feature_count"] == 2
    frame = gpd.read_parquet(out)
    pairs = dict(zip(frame["school"], zip(frame["hospital"], frame["nearest_distance_m"], strict=True), strict=True))
    assert pairs == {"s1": ("h1", 30.0), "s2": ("h2", 40.0)}


def test_nearest_join_max_distance_drops_the_far_pair(schools_hospitals, tmp_path):
    schools, hospitals = schools_hospitals
    out = tmp_path / "near.parquet"
    result = vector.nearest_join(schools, hospitals, str(out), max_distance_meters=35)
    assert result["feature_count"] == 1
    assert gpd.read_parquet(out)["hospital"].tolist() == ["h1"]
    with pytest.raises(ValueError, match="positive"):
        vector.nearest_join(schools, hospitals, str(tmp_path / "x.parquet"), max_distance_meters=0)


def test_nearest_join_measures_meters_on_a_geographic_crs(tmp_path):
    left = tmp_path / "a.parquet"
    right = tmp_path / "b.parquet"
    # ~300 m north of each other at 41.9N (0.0027 degrees of latitude).
    gpd.GeoDataFrame(
        {"a": [1]}, geometry=[Point(12.40, 41.90)], crs="EPSG:4326"
    ).to_parquet(left)
    gpd.GeoDataFrame(
        {"b": [2]}, geometry=[Point(12.40, 41.9027)], crs="EPSG:4326"
    ).to_parquet(right)
    out = tmp_path / "joined.parquet"
    vector.nearest_join(str(left), str(right), str(out))
    frame = gpd.read_parquet(out)
    # Meters, not degrees: a degree-distance here would be 0.0027.
    assert float(frame["nearest_distance_m"].iloc[0]) == pytest.approx(300, abs=2)
    assert frame.crs.to_epsg() == 4326  # geometries returned in the input CRS
    manifest = _manifest(out)
    assert "UTM" in manifest["crs_decisions"]["reason"]


def test_explode_counts_the_parts_before_the_engine_runs(tmp_path):
    source = tmp_path / "multi.parquet"
    gpd.GeoDataFrame(
        {"i": [1, 2]},
        geometry=gpd.GeoSeries.from_wkt(
            ["MULTIPOINT(0 0, 1 1, 2 2)", "POINT(9 9)"]
        ),
        crs=CRS,
    ).to_parquet(source)
    out = tmp_path / "parts.parquet"
    result = vector.explode(str(source), str(out))
    assert result["feature_count"] == 4
    frame = gpd.read_parquet(out)
    assert frame["i"].tolist() == [1, 1, 1, 2]
    counts = [c for c in _manifest(out)["verification"] if c["name"] == "feature_count_exact"]
    assert counts and counts[0]["passed"]
