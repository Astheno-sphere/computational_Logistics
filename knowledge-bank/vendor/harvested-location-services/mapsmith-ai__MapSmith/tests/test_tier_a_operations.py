"""Closed-form tests for the ten operations that answered Argleton's tier A.

Every fixture here is the one from the trap that asked for the operation, so
the expected values are the traps' own derivations: a courtyard subtracted
(8400), a pipe that climbs (500), a rate that is a ratio of totals (1.38%), a
key that keeps its leading zero (100000), a join that must not multiply land
(50000 from 13 rows).
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, Polygon

from mapsmith.engines import vector

CRS = "EPSG:32632"
EAST, NORTH = 500_000.0, 5_030_000.0


def _manifest(output) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------- join_table
@pytest.fixture
def municipalities(tmp_path):
    codes = ["001", "002", "010", "020"] + [f"{i}00" for i in range(1, 9)]
    layer = tmp_path / "municipalities.parquet"
    gpd.GeoDataFrame(
        {"istat_code": codes},
        geometry=[
            Polygon([(EAST + i * 10, NORTH), (EAST + i * 10 + 10, NORTH),
                     (EAST + i * 10 + 10, NORTH + 10), (EAST + i * 10, NORTH + 10)])
            for i in range(len(codes))
        ],
        crs=CRS,
    ).to_parquet(layer)
    table = tmp_path / "population.csv"
    rows = ["istat_code,population"]
    rows += [f"{c},9500" for c in codes[:4]] + [f"{c},7750" for c in codes[4:]]
    table.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(layer), str(table)


def test_join_keeps_leading_zeros(municipalities, tmp_path):
    layer, table = municipalities
    out = tmp_path / "joined.parquet"
    result = vector.join_table(layer, table, str(out), on="istat_code")
    assert result["unmatched_features"] == 0
    assert result["feature_count"] == 12
    # 4 * 9500 + 8 * 7750 = 100000, the whole point of reading keys as text.
    assert int(gpd.read_parquet(out)["population"].sum()) == 100_000


def test_join_reports_the_fan_out(tmp_path):
    parcels = tmp_path / "parcels.parquet"
    gpd.GeoDataFrame(
        {"parcel_id": [f"P-{i}" for i in range(1, 11)], "area_m2": [5000.0] * 10},
        geometry=[
            Polygon([(EAST + i * 100, NORTH), (EAST + i * 100 + 50, NORTH),
                     (EAST + i * 100 + 50, NORTH + 100), (EAST + i * 100, NORTH + 100)])
            for i in range(10)
        ],
        crs=CRS,
    ).to_parquet(parcels)
    owners = tmp_path / "owners.csv"
    rows = ["parcel_id,owner", "P-1,a", "P-1,b", "P-2,c", "P-2,d", "P-3,e", "P-3,f"]
    rows += [f"P-{i},g" for i in range(4, 11)]
    owners.write_text("\n".join(rows) + "\n", encoding="utf-8")

    out = tmp_path / "owned.parquet"
    result = vector.join_table(str(parcels), str(owners), str(out), on="parcel_id")
    assert result["duplicate_keys"] == 3
    assert result["input_feature_count"] == 10
    assert result["feature_count"] == 13  # the fan-out, stated
    checks = {w["check"] for w in result["warnings"]}
    # `feature_count_exact` and not an extension name: the predicate is the core
    # definition, so §3.6 of the spec requires the core name. Asserting the name
    # here is the point -- a consumer branches on it.
    assert "feature_count_exact" in checks
    # 13 rows * 5000 = 65000 is the wrong answer this warning exists to prevent.
    assert float(gpd.read_parquet(out)["area_m2"].sum()) == 65_000.0
    assert any("counts the multiplied features" in n for n in _manifest(out)["notes"])


def test_join_refuses_a_missing_key_column(municipalities, tmp_path):
    layer, table = municipalities
    with pytest.raises(ValueError, match="is not in"):
        vector.join_table(layer, table, str(tmp_path / "x.parquet"), on="nonexistent")


# ------------------------------------------------------------ measure_length
@pytest.fixture
def pipeline(tmp_path):
    path = tmp_path / "pipeline.parquet"
    gpd.GeoDataFrame(
        {"pipe": ["PL-1"]},
        geometry=[LineString([(EAST, NORTH, 0), (EAST + 400, NORTH, 300)])],
        crs=CRS,
    ).to_parquet(path)
    return str(path)


def test_a_pipe_that_climbs_is_measured_through_space(pipeline, tmp_path):
    """3-4-5: 400 m across, 300 m up, 500 m of pipe."""
    out = tmp_path / "len3d.parquet"
    result = vector.measure_length(pipeline, str(out), method="3d")
    assert result["total_length_m"] == pytest.approx(500.0, abs=1e-6)


def test_a_flat_measurement_on_3d_geometry_says_so(pipeline, tmp_path):
    out = tmp_path / "len2d.parquet"
    result = vector.measure_length(pipeline, str(out), method="planar")
    assert result["total_length_m"] == pytest.approx(400.0, abs=1e-6)
    checks = {w["check"] for w in result["warnings"]}
    assert "x-mapsmith:flat_length_on_3d_geometry" in checks


def test_3d_is_refused_where_it_would_mean_nothing(tmp_path):
    flat = tmp_path / "flat.parquet"
    gpd.GeoDataFrame(
        {"i": [1]}, geometry=[LineString([(EAST, NORTH), (EAST + 100, NORTH)])], crs=CRS
    ).to_parquet(flat)
    with pytest.raises(ValueError, match="no Z coordinates"):
        vector.measure_length(str(flat), str(tmp_path / "x.parquet"), method="3d")


# -------------------------------------------------------- aggregate_weighted
def test_a_rate_is_the_ratio_of_totals(tmp_path):
    """1000 at 20%, 1000 at 20%, 98000 at 1% -> 1380/100000 = 1.38%."""
    path = tmp_path / "municipalities.parquet"
    gpd.GeoDataFrame(
        {"labour_force": [1000, 1000, 98000], "rate": [20.0, 20.0, 1.0]},
        geometry=[
            Polygon([(EAST, NORTH), (EAST + 10, NORTH), (EAST + 10, NORTH + 10), (EAST, NORTH + 10)]),
            Polygon([(EAST + 10, NORTH), (EAST + 20, NORTH), (EAST + 20, NORTH + 10), (EAST + 10, NORTH + 10)]),
            Polygon([(EAST, NORTH + 10), (EAST + 20, NORTH + 10), (EAST + 20, NORTH + 110), (EAST, NORTH + 110)]),
        ],
        crs=CRS,
    ).to_parquet(path)
    out = tmp_path / "rate.parquet"
    result = vector.aggregate_weighted(
        str(path), str(out), value_column="rate", weight_column="labour_force"
    )
    assert result["weighted_value"] == pytest.approx(1.38, abs=1e-9)
    assert result["unweighted_mean"] == pytest.approx(41 / 3, abs=1e-9)
    assert result["total_weight"] == 100_000
    checks = {w["check"] for w in result["warnings"]}
    assert "x-mapsmith:weighting_changed_the_answer" in checks


def test_a_weighted_aggregate_refuses_missing_values(tmp_path):
    path = tmp_path / "gaps.parquet"
    gpd.GeoDataFrame(
        {"labour_force": [1000, None], "rate": [20.0, 10.0]},
        geometry=[
            Polygon([(EAST, NORTH), (EAST + 10, NORTH), (EAST + 10, NORTH + 10), (EAST, NORTH + 10)]),
            Polygon([(EAST + 10, NORTH), (EAST + 20, NORTH), (EAST + 20, NORTH + 10), (EAST + 10, NORTH + 10)]),
        ],
        crs=CRS,
    ).to_parquet(path)
    with pytest.raises(ValueError, match="must both be numeric"):
        vector.aggregate_weighted(
            str(path), str(tmp_path / "x.parquet"),
            value_column="rate", weight_column="labour_force",
        )


# --------------------------------------------------------- parse_coordinates
def test_dms_converts_exactly(tmp_path):
    """41 deg 53' 24\" = 41 + 3180/3600 + 24/3600 = 41.89 exactly."""
    table = tmp_path / "stations.csv"
    table.write_text(
        "station_id,lat_deg,lat_min,lat_sec,lat_hem,lon_deg,lon_min,lon_sec,lon_hem\n"
        "ST-1,41,53,24,N,12,29,32,E\n",
        encoding="utf-8",
    )
    out = tmp_path / "points.parquet"
    result = vector.parse_coordinates(
        str(table), str(out),
        latitude_columns="lat_deg,lat_min,lat_sec,lat_hem",
        longitude_columns="lon_deg,lon_min,lon_sec,lon_hem",
    )
    assert result["feature_count"] == 1
    point = gpd.read_parquet(out).geometry.iloc[0]
    assert point.y == pytest.approx(41.89, abs=1e-9)
    assert point.x == pytest.approx(12 + 29 / 60 + 32 / 3600, abs=1e-9)


def test_a_hemisphere_letter_sets_the_sign(tmp_path):
    table = tmp_path / "south.csv"
    table.write_text(
        "station_id,lat_deg,lat_min,lat_sec,lat_hem,lon_deg,lon_min,lon_sec,lon_hem\n"
        "ST-1,33,55,0,S,18,25,0,E\n",
        encoding="utf-8",
    )
    out = tmp_path / "cape.parquet"
    vector.parse_coordinates(
        str(table), str(out),
        latitude_columns="lat_deg,lat_min,lat_sec,lat_hem",
        longitude_columns="lon_deg,lon_min,lon_sec,lon_hem",
    )
    assert gpd.read_parquet(out).geometry.iloc[0].y == pytest.approx(-33.916667, abs=1e-6)


def test_impossible_coordinates_are_refused(tmp_path):
    table = tmp_path / "bad.csv"
    table.write_text("station_id,latitude,longitude\nST-1,91.5,12.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        vector.parse_coordinates(
            str(table), str(tmp_path / "x.parquet"),
            latitude_columns="latitude", longitude_columns="longitude",
        )


# ----------------------------------------------------------- point_on_surface
def test_a_representative_point_is_on_its_own_feature(tmp_path):
    """The L-shape whose centroid falls in the notch."""
    path = tmp_path / "ell.parquet"
    shape = Polygon([
        (EAST, NORTH), (EAST + 100, NORTH), (EAST + 100, NORTH + 20),
        (EAST + 20, NORTH + 20), (EAST + 20, NORTH + 100), (EAST, NORTH + 100),
    ])
    gpd.GeoDataFrame({"i": [1]}, geometry=[shape], crs=CRS).to_parquet(path)
    assert not shape.contains(shape.centroid)  # the premise

    out = tmp_path / "pos.parquet"
    result = vector.point_on_surface(str(path), str(out))
    assert result["feature_count"] == 1
    assert shape.contains(gpd.read_parquet(out).geometry.iloc[0])
    assert [c["name"] for c in _manifest(out)["verification"] if not c["passed"]] == []


# ---------------------------------------------------------------- hull_layer
def test_a_hull_contains_its_feature_and_says_how_much_it_added(tmp_path):
    path = tmp_path / "ell.parquet"
    shape = Polygon([
        (EAST, NORTH), (EAST + 100, NORTH), (EAST + 100, NORTH + 20),
        (EAST + 20, NORTH + 20), (EAST + 20, NORTH + 100), (EAST, NORTH + 100),
    ])
    gpd.GeoDataFrame({"i": [1]}, geometry=[shape], crs=CRS).to_parquet(path)
    out = tmp_path / "hull.parquet"
    result = vector.hull(str(path), str(out), kind="convex")
    assert result["feature_area"] == pytest.approx(3600.0)
    assert result["hull_area"] == pytest.approx(6800.0)  # the L's convex hull
    envelope = vector.hull(str(path), str(tmp_path / "env.parquet"), kind="envelope")
    assert envelope["hull_area"] == pytest.approx(10000.0)  # the bounding box
    assert any("claims the difference" in n for n in _manifest(out)["notes"])


# ---------------------------------------------------------- validate_geometry
def test_validation_reports_without_repairing(tmp_path):
    path = tmp_path / "bowtie.parquet"
    bowtie = Polygon([
        (EAST, NORTH), (EAST + 100, NORTH + 100), (EAST + 100, NORTH), (EAST, NORTH + 100),
    ])
    gpd.GeoDataFrame({"i": [1]}, geometry=[bowtie], crs=CRS).to_parquet(path)
    out = tmp_path / "checked.parquet"
    result = vector.validate_geometry(str(path), str(out))
    assert result["invalid_count"] == 1
    assert result["reasons"] and "Self-intersection" in result["reasons"][0]
    frame = gpd.read_parquet(out)
    assert bool(frame["is_valid"].iloc[0]) is False
    # Nothing was repaired: the geometry on disk is still the bowtie.
    assert not frame.geometry.iloc[0].is_valid
    assert "repairs" not in result or not result["repairs"]


# --------------------------------------------------------- count_in_polygons
def test_the_boundary_rule_changes_the_count_and_the_missing_points_are_named(tmp_path):
    wells = tmp_path / "wells.parquet"
    coordinates = [(10, 10), (20, 30), (30, 60), (40, 80), (60, 10), (70, 30),
                   (80, 60), (90, 80), (50, 20), (50, 40), (50, 60), (50, 80)]
    gpd.GeoDataFrame(
        {"well_id": [f"W-{i + 1}" for i in range(12)]},
        geometry=[Point(EAST + x, NORTH + y) for x, y in coordinates],
        crs=CRS,
    ).to_parquet(wells)
    districts = tmp_path / "districts.parquet"
    gpd.GeoDataFrame(
        {"district": ["west", "east"]},
        geometry=[
            Polygon([(EAST, NORTH), (EAST + 50, NORTH), (EAST + 50, NORTH + 100), (EAST, NORTH + 100)]),
            Polygon([(EAST + 50, NORTH), (EAST + 100, NORTH), (EAST + 100, NORTH + 100), (EAST + 50, NORTH + 100)]),
        ],
        crs=CRS,
    ).to_parquet(districts)

    touching = vector.count_in_polygons(
        str(wells), str(districts), str(tmp_path / "a.parquet"), predicate="intersects"
    )
    assert touching["points_placed"] == 12
    assert touching["points_unplaced"] == 0

    strict = vector.count_in_polygons(
        str(wells), str(districts), str(tmp_path / "b.parquet"), predicate="within"
    )
    # The four wells on x = 50 belong to neither district under `within`.
    assert strict["points_placed"] == 8
    assert strict["points_unplaced"] == 4
    checks = {w["check"] for w in strict["warnings"]}
    assert "x-mapsmith:every_point_placed" in checks
