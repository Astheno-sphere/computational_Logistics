"""summarize_points_in_polygons: closed-form fixtures, and the three decisions about the number.

Three squares on EPSG:32632. A and B share the edge x = 10; C holds no point.

    A (0..10)   ph 4, 6, 8, and one sample with no value
    B (10..20)  ph 7, 9
    on x = 10   ph 11      <- the edge A and B share
    outside     ph 1       <- in no polygon

Under `intersects` the edge sample is in BOTH squares:
    A: 4, 6, 8, 11 -> count 4, sum 29, mean 7.25, min 4, max 11; point_count 5
    B: 7, 9, 11    -> count 3, sum 27, mean 9
Under `within` it is in NEITHER:
    A: 4, 6, 8     -> count 3, mean 6; point_count 4
    B: 7, 9        -> count 2, mean 8
C is kept either way, with point_count 0 and every statistic null.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

gpd = pytest.importorskip("geopandas")
from shapely.geometry import Point, box

from mapsmith.engines import vector

CRS = "EPSG:32632"


@pytest.fixture
def layers(tmp_path):
    polygons = tmp_path / "blocks.gpkg"
    gpd.GeoDataFrame(
        {"block": ["A", "B", "C"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10), box(30, 0, 40, 10)],
        crs=CRS,
    ).to_file(polygons, driver="GPKG")
    points = tmp_path / "samples.gpkg"
    gpd.GeoDataFrame(
        {"ph": [4.0, 6.0, 8.0, None, 7.0, 9.0, 11.0, 1.0]},
        geometry=[
            Point(2, 2), Point(5, 5), Point(8, 8), Point(3, 7),
            Point(15, 5), Point(12, 2),
            Point(10, 5),
            Point(50, 50),
        ],
        crs=CRS,
    ).to_file(points, driver="GPKG")
    return points, polygons


def _by_block(path: str) -> dict:
    out = gpd.read_file(path)
    return {row["block"]: row for _, row in out.iterrows()}


def test_intersects_counts_the_edge_sample_in_both_squares(layers, tmp_path):
    points, polygons = layers
    out = tmp_path / "ph.gpkg"
    result = vector.summarize_points_in_polygons(
        str(points), str(polygons), str(out), field="ph",
        statistics=["count", "sum", "mean", "min", "max"],
    )
    rows = _by_block(str(out))
    assert rows["A"]["point_count"] == 5
    assert rows["A"]["ph_count"] == 4
    assert rows["A"]["ph_sum"] == 29.0
    assert rows["A"]["ph_mean"] == 7.25
    assert rows["A"]["ph_min"] == 4.0 and rows["A"]["ph_max"] == 11.0
    assert rows["B"]["ph_count"] == 3 and rows["B"]["ph_mean"] == 9.0
    assert result["points_counted_twice"] == 1
    assert result["points_unplaced"] == 1
    assert result["points_without_value"] == 1


def test_within_drops_the_edge_sample_from_both(layers, tmp_path):
    points, polygons = layers
    out = tmp_path / "ph.gpkg"
    result = vector.summarize_points_in_polygons(
        str(points), str(polygons), str(out), field="ph", predicate="within"
    )
    rows = _by_block(str(out))
    assert rows["A"]["point_count"] == 4 and rows["A"]["ph_mean"] == 6.0
    assert rows["B"]["ph_count"] == 2 and rows["B"]["ph_mean"] == 8.0
    # The edge sample and the outside one: the two predicates are two numbers,
    # and the record has to say which the caller got.
    assert result["points_unplaced"] == 2
    assert result["points_counted_twice"] == 0


def test_a_polygon_with_no_points_is_kept_with_null_statistics(layers, tmp_path):
    """The mean of nothing is not zero, and a missing row fakes coverage."""
    points, polygons = layers
    out = tmp_path / "ph.gpkg"
    result = vector.summarize_points_in_polygons(
        str(points), str(polygons), str(out), field="ph"
    )
    rows = _by_block(str(out))
    assert "C" in rows, "a polygon with no samples disappeared from the output"
    assert rows["C"]["point_count"] == 0
    assert rows["C"]["ph_count"] == 0
    for name in ("mean", "min", "max"):
        value = rows["C"][f"ph_{name}"]
        assert pd.isna(value), (  # None, or NaN once written to a file
            f"block C has no samples and its ph_{name} is {value!r}: an empty "
            "polygon must not report a number"
        )
    assert result["polygons_without_points"] == 1


def test_the_manifest_records_the_three_decisions(layers, tmp_path):
    points, polygons = layers
    out = tmp_path / "ph.gpkg"
    vector.summarize_points_in_polygons(str(points), str(polygons), str(out), field="ph")
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    assert record["parameters"]["predicate"] == "intersects"
    notes = " ".join(record["notes"])
    assert "counted in more than one polygon" in notes
    assert "no value" in notes
    assert "hold no point" in notes
    placed = next(
        c for c in record["verification"] if c["name"] == "x-mapsmith:every_point_placed"
    )
    assert placed["passed"] is False and placed["critical"] is False


def test_points_in_another_crs_are_brought_onto_the_polygons(tmp_path):
    """No edge sample here: a round trip through degrees can move a point off a
    boundary by a rounding error, and this test is about the CRS record, not the
    boundary rule."""
    polygons = tmp_path / "blocks.gpkg"
    gpd.GeoDataFrame(
        {"block": ["A"]}, geometry=[box(500000, 5000000, 501000, 5001000)], crs=CRS
    ).to_file(polygons, driver="GPKG")
    points = tmp_path / "samples.gpkg"
    gpd.GeoDataFrame(
        {"ph": [5.0, 7.0]},
        geometry=[Point(500200, 5000200), Point(500800, 5000800)],
        crs=CRS,
    ).to_crs("EPSG:4326").to_file(points, driver="GPKG")
    out = tmp_path / "ph.gpkg"
    vector.summarize_points_in_polygons(str(points), str(polygons), str(out), field="ph")
    assert _by_block(str(out))["A"]["ph_mean"] == 6.0
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    moved = record["crs_decisions"]["x-mapsmith:inputs_reprojected"]
    assert moved == [{"argument": "points_path", "from": "EPSG:4326"}]
    assert record["crs_decisions"]["analysis_crs"] == CRS


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"field": "nope"}, "no attribute 'nope'"),
        ({"field": "ph", "statistics": ["mode"]}, "unknown statistic"),
        ({"field": "ph", "predicate": "touches"}, "predicate must be one of"),
    ],
)
def test_bad_arguments_are_refused_with_the_way_out(layers, tmp_path, kwargs, message):
    points, polygons = layers
    with pytest.raises(ValueError, match=message):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "x.gpkg"), **kwargs
        )


def test_a_text_attribute_is_refused(tmp_path):
    polygons = tmp_path / "p.gpkg"
    gpd.GeoDataFrame({"k": [1]}, geometry=[box(0, 0, 10, 10)], crs=CRS).to_file(polygons)
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"soil": ["clay"]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    with pytest.raises(ValueError, match="not numbers"):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "x.gpkg"), field="soil"
        )


def test_an_existing_column_is_not_overwritten(tmp_path):
    """The output must not silently replace a value that was in the input."""
    polygons = tmp_path / "p.gpkg"
    gpd.GeoDataFrame(
        {"ph_mean": [99.0]}, geometry=[box(0, 0, 10, 10)], crs=CRS
    ).to_file(polygons)
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"ph": [5.0]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    with pytest.raises(ValueError, match="would overwrite"):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "x.gpkg"), field="ph"
        )


def test_a_valueless_point_outside_every_polygon_is_not_said_to_be_counted(tmp_path):
    """The note about missing values may only speak of the points it placed.

    The first version counted every point with no value and said all of them
    were "in `point_count`". One that fell in no polygon is in no count at all,
    and the fixture above never showed it because its only valueless sample sat
    inside block A. Found by the `conformita-manifest` review.
    """
    polygons = tmp_path / "p.gpkg"
    gpd.GeoDataFrame({"block": ["A"]}, geometry=[box(0, 0, 10, 10)], crs=CRS).to_file(polygons)
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame(
        {"ph": [5.0, None]}, geometry=[Point(5, 5), Point(50, 50)], crs=CRS
    ).to_file(points)
    out = tmp_path / "ph.gpkg"
    result = vector.summarize_points_in_polygons(str(points), str(polygons), str(out), field="ph")
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    notes = " ".join(record["notes"])
    assert "placed points have no value" not in notes, (
        f"no PLACED point lacks a value, and the record says one does: {record['notes']}"
    )
    assert "are not in any polygon, so they are in no count" in notes
    assert result["points_without_value"] == 1


def test_a_repeated_statistic_is_recorded_once(tmp_path):
    polygons = tmp_path / "p.gpkg"
    gpd.GeoDataFrame({"block": ["A"]}, geometry=[box(0, 0, 10, 10)], crs=CRS).to_file(polygons)
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"ph": [5.0]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    out = tmp_path / "ph.gpkg"
    vector.summarize_points_in_polygons(
        str(points), str(polygons), str(out), field="ph", statistics=["mean", "mean"]
    )
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    assert record["parameters"]["statistics"] == ["count", "mean"]


# --- the defects the `geo-reviewer` measured on 2026-09-24 --------------------


def _one_block(tmp_path, *boxes):
    polygons = tmp_path / "p.gpkg"
    gpd.GeoDataFrame(
        {"block": [chr(65 + i) for i in range(len(boxes))]}, geometry=list(boxes), crs=CRS
    ).to_file(polygons)
    return polygons


@pytest.mark.parametrize("operation", ["count", "summarize"])
def test_contains_is_refused_because_it_never_placed_a_point(tmp_path, operation):
    """`sjoin(points, polygons, "contains")` asks whether a POINT contains a
    polygon: false for any polygon with area. Both operations returned all zeros
    under it with `verified: True`. It is refused now, and the refusal names the
    two predicates that mean something for points."""
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"ph": [5.0]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    with pytest.raises(ValueError, match="predicate must be one of"):
        if operation == "count":
            vector.count_in_polygons(
                str(points), str(polygons), str(tmp_path / "c.gpkg"), predicate="contains"
            )
        else:
            vector.summarize_points_in_polygons(
                str(points), str(polygons), str(tmp_path / "s_out.gpkg"),
                field="ph", predicate="contains",
            )


@pytest.mark.parametrize("predicate", sorted(vector.COUNT_PREDICATES))
def test_every_accepted_predicate_places_a_point_well_inside(tmp_path, predicate):
    """The guard that would have caught `contains`: a predicate that is accepted
    must place a point that sits in the middle of a polygon, far from any edge."""
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"ph": [5.0]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    result = vector.summarize_points_in_polygons(
        str(points), str(polygons), str(tmp_path / "o.gpkg"), field="ph", predicate=predicate
    )
    assert result["points_placed"] == 1, (
        f"`{predicate}` is accepted and did not place a point at the centre of a square"
    )


def test_a_point_in_three_overlapping_polygons_is_one_point_counted_twice_too_often(tmp_path):
    polygons = _one_block(tmp_path, box(0, 0, 10, 10), box(2, 2, 12, 12), box(4, 4, 14, 14))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"ph": [5.0]}, geometry=[Point(6, 6)], crs=CRS).to_file(points)
    out = tmp_path / "o.gpkg"
    result = vector.summarize_points_in_polygons(str(points), str(polygons), str(out), field="ph")
    assert result["points_counted_twice"] == 1
    notes = " ".join(json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))["notes"])
    assert "1 of them are counted in more than one polygon (2 extra memberships" in notes, notes


def test_points_without_geometry_are_counted_apart_and_not_blamed_on_the_polygons(tmp_path):
    """A null or empty geometry has no position. It used to land among the points
    "in no polygon", and the hint sent the reader to check the boundaries."""
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.parquet"
    gpd.GeoDataFrame(
        {"ph": [5.0, 6.0, 7.0]},
        geometry=gpd.GeoSeries.from_wkt(["POINT (5 5)", None, "POINT EMPTY"]),
        crs=CRS,
    ).to_parquet(points)
    out = tmp_path / "o.gpkg"
    result = vector.summarize_points_in_polygons(str(points), str(polygons), str(out), field="ph")
    assert result["points_without_geometry"] == 2
    assert result["points_unplaced"] == 0, (
        "points with no position were counted as points outside every polygon"
    )
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    placed = next(c for c in record["verification"] if c["name"] == "x-mapsmith:every_point_placed")
    assert placed["passed"] is True


def test_a_multipoint_is_refused_rather_than_counted_in_two_polygons(tmp_path):
    from shapely.geometry import MultiPoint

    polygons = _one_block(tmp_path, box(0, 0, 10, 10), box(10, 0, 20, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame(
        {"ph": [5.0]}, geometry=[MultiPoint([(5, 5), (15, 5)])], crs=CRS
    ).to_file(points)
    with pytest.raises(ValueError, match="explode_layer"):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "o.gpkg"), field="ph"
        )


@pytest.mark.parametrize("suffix", [".gpkg", ".parquet"])
def test_a_statistic_null_everywhere_is_still_written_as_a_number(tmp_path, suffix):
    """stdev over single samples is null in every polygon, and was written as
    TEXT in GeoPackage and as a null type in GeoParquet: the output's schema
    depended on the data."""
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"ph": [5.0]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    out = tmp_path / f"o{suffix}"
    vector.summarize_points_in_polygons(
        str(points), str(polygons), str(out), field="ph", statistics=["stdev"]
    )
    written = gpd.read_parquet(out) if suffix == ".parquet" else gpd.read_file(out)
    assert pd.api.types.is_float_dtype(written["ph_stdev"]), (
        f"ph_stdev was written as {written['ph_stdev'].dtype}, not a number"
    )
    assert pd.isna(written["ph_stdev"].iloc[0]), "stdev of one value must be null"
    assert pd.api.types.is_integer_dtype(written["ph_count"])


def test_a_shapefile_that_would_rename_a_column_is_refused(tmp_path):
    """`population_count` came back from the Shapefile driver as `population`:
    a count, sitting in a column that reads as the attribute."""
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"population": [5]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    with pytest.raises(ValueError, match="Shapefile cannot hold"):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "o.shp"), field="population"
        )


def test_the_summary_is_checked_back_from_the_file(layers, tmp_path):
    """A check on the number, not the shape: columns present under their names,
    counts adding up to the join's memberships."""
    points, polygons = layers
    out = tmp_path / "ph.gpkg"
    vector.summarize_points_in_polygons(str(points), str(polygons), str(out), field="ph")
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    intact = next(
        c for c in record["verification"] if c["name"] == "x-mapsmith:summary_columns_intact"
    )
    assert intact["passed"] is True
    # 5 in A (the edge sample included) + 3 in B (the edge sample again) = 8.
    assert "point_count sums to 8" in intact["detail"], intact["detail"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [({"statistics": []}, "empty list"), ({"field": "index_right"}, "Rename it first")],
)
def test_two_more_arguments_are_refused_with_a_reason(tmp_path, kwargs, message):
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame(
        {"ph": [5.0], "index_right": [1.0]}, geometry=[Point(5, 5)], crs=CRS
    ).to_file(points)
    arguments = {"field": "ph", **kwargs}
    with pytest.raises(ValueError, match=message):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "o.gpkg"), **arguments
        )


def test_a_boolean_attribute_is_refused(tmp_path):
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"wet": [True]}, geometry=[Point(5, 5)], crs=CRS).to_file(points)
    with pytest.raises(ValueError, match="not numbers"):
        vector.summarize_points_in_polygons(
            str(points), str(polygons), str(tmp_path / "o.gpkg"), field="wet"
        )


# --- the same two defects in the sibling, measured on 2026-09-24 ---------------


def test_count_in_polygons_counts_points_without_geometry_apart(tmp_path):
    """Measured before the fix: a null and an empty geometry were reported as
    "2 of 3 points fall in no polygon", with a hint about the boundaries."""
    polygons = _one_block(tmp_path, box(0, 0, 10, 10))
    points = tmp_path / "s.parquet"
    gpd.GeoDataFrame(
        {"n": [1, 2, 3]},
        geometry=gpd.GeoSeries.from_wkt(["POINT (5 5)", None, "POINT EMPTY"]),
        crs=CRS,
    ).to_parquet(points)
    out = tmp_path / "c.gpkg"
    result = vector.count_in_polygons(str(points), str(polygons), str(out))
    assert result["points_without_geometry"] == 2
    assert result["points_unplaced"] == 0
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    placed = next(c for c in record["verification"] if c["name"] == "x-mapsmith:every_point_placed")
    assert placed["passed"] is True, placed


def test_count_in_polygons_refuses_a_multipoint_it_would_count_twice(tmp_path):
    """Measured before the fix: a MultiPoint straddling A and B was counted in
    both, `{'A': 1, 'B': 1}`, as if it were two points."""
    from shapely.geometry import MultiPoint

    polygons = _one_block(tmp_path, box(0, 0, 10, 10), box(10, 0, 20, 10))
    points = tmp_path / "s.gpkg"
    gpd.GeoDataFrame({"n": [1]}, geometry=[MultiPoint([(5, 5), (15, 5)])], crs=CRS).to_file(points)
    with pytest.raises(ValueError, match="explode_layer"):
        vector.count_in_polygons(str(points), str(polygons), str(tmp_path / "c.gpkg"))


# --- the antimeridian, measured on 2026-09-24 -------------------------------


def _pacific_zone(tmp_path, geometry):
    path = tmp_path / "zone.gpkg"
    gpd.GeoDataFrame({"z": ["pacific"]}, geometry=[geometry], crs="EPSG:4326").to_file(path)
    return path


@pytest.mark.parametrize("operation", ["count", "summarize"])
def test_a_ring_drawn_across_180_is_refused(tmp_path, operation):
    """The plane reads it as the rest of the planet. Measured before this was
    refused: the point at 175E inside the zone was dropped and the point at 0
    was counted -- a total of 1, the same as the truth, so no number showed it."""
    from shapely.geometry import Polygon

    zone = _pacific_zone(tmp_path, Polygon([(170, -5), (-170, -5), (-170, 5), (170, 5)]))
    points = tmp_path / "p.gpkg"
    gpd.GeoDataFrame(
        {"n": [1.0]}, geometry=[Point(175, 0)], crs="EPSG:4326"
    ).to_file(points)
    with pytest.raises(ValueError, match="cross the 180th meridian"):
        if operation == "count":
            vector.count_in_polygons(str(points), str(zone), str(tmp_path / "c.gpkg"))
        else:
            vector.summarize_points_in_polygons(
                str(points), str(zone), str(tmp_path / "s_out.gpkg"), field="n"
            )


def test_a_zone_split_at_180_is_placed_right(tmp_path):
    """The form RFC 7946 prescribes, and the one this refusal points to."""
    from shapely.geometry import MultiPolygon

    zone = _pacific_zone(
        tmp_path, MultiPolygon([box(170, -5, 180, 5), box(-180, -5, -170, 5)])
    )
    points = tmp_path / "p.gpkg"
    gpd.GeoDataFrame(
        {"n": [1.0, 2.0]}, geometry=[Point(175, 0), Point(0, 0)], crs="EPSG:4326"
    ).to_file(points)
    out = tmp_path / "c.gpkg"
    result = vector.count_in_polygons(str(points), str(zone), str(out))
    assert int(gpd.read_file(out)["point_count"][0]) == 1
    assert result["points_placed"] == 1 and result["points_unplaced"] == 1


def test_the_detector_ignores_projected_layers_and_ordinary_zones():
    """No false alarm on a projected CRS, where a large jump is just metres, or
    on an ordinary zone in degrees."""
    from mapsmith import antimeridian

    projected = gpd.GeoDataFrame(geometry=[box(0, 0, 500000, 10)], crs="EPSG:32632")
    ordinary = gpd.GeoDataFrame(geometry=[box(-10, -5, 10, 5)], crs="EPSG:4326")
    assert antimeridian.naive_crossings(projected) == []
    assert antimeridian.naive_crossings(ordinary) == []


def test_an_edge_along_the_seam_is_not_a_crossing():
    """The first detector refused all four of these, found by the 0.6.0
    pre-release review before it shipped -- including Antarctica in Natural
    Earth, which would have refused "points per country". Their jumps run from
    -180 to 180 along the edge of the plane, where the planar reading is meant."""
    from shapely.geometry import Polygon

    from mapsmith import antimeridian

    antarctica_like = Polygon(
        [(-180, -90), (-180, -84.7), (-60, -63), (60, -66), (180, -84.7), (180, -90)]
    )
    legitimate = gpd.GeoDataFrame(
        {"what": ["world", "tropics", "arctic", "antarctica"]},
        geometry=[
            box(-180, -90, 180, 90),
            box(-180, -23.4, 180, 23.4),
            box(-180, 66.5, 180, 90),
            antarctica_like,
        ],
        crs="EPSG:4326",
    )
    assert antimeridian.naive_crossings(legitimate) == []
    # One end on the seam and the other inside is still the artefact.
    touching = gpd.GeoDataFrame(
        geometry=[Polygon([(180, -5), (-170, -5), (-170, 5), (180, 5)])], crs="EPSG:4326"
    )
    assert antimeridian.naive_crossings(touching) == [0]
    # And a layer with no polygon in it is answered without looking at a ring.
    points = gpd.GeoDataFrame(geometry=[Point(175, 0), Point(-175, 0)], crs="EPSG:4326")
    assert antimeridian.naive_crossings(points) == []


def test_a_layer_in_0_to_360_has_its_seam_at_0_and_360(tmp_path):
    """Found on 2026-09-25 writing the message below: the world written as
    box(0, -90, 360, 90) was refused as Antarctica had been, because the seam
    was hard-coded at +/-180. And the ring that IS naive in such a layer crosses
    0/360, so the refusal must say so instead of sending its author to 180."""
    from shapely.geometry import Polygon

    from mapsmith import antimeridian

    world = gpd.GeoDataFrame(geometry=[box(0, -90, 360, 90)], crs="EPSG:4326")
    assert antimeridian.naive_crossings(world) == []
    across_zero = Polygon([(350, -5), (10, -5), (10, 5), (350, 5)])
    assert antimeridian.naive_crossings(
        gpd.GeoDataFrame(geometry=[across_zero], crs="EPSG:4326")
    ) == [0]

    zone = _pacific_zone(tmp_path, across_zero)
    points = tmp_path / "p.gpkg"
    gpd.GeoDataFrame({"n": [1.0]}, geometry=[Point(355, 0)], crs="EPSG:4326").to_file(points)
    with pytest.raises(ValueError, match=r"prime meridian \(0/360") as refused:
        vector.count_in_polygons(str(points), str(zone), str(tmp_path / "c.gpkg"))
    assert "180th" not in str(refused.value)


def test_one_vertex_past_180_does_not_move_the_seam_of_the_layer(tmp_path):
    """The first 0..360 fix picked the convention from the maximum alone, and
    the 0.6.1 pre-release review measured two refusals 0.6.0 had not made: the
    world beside a polygon overshooting 180 by 1e-7 (ordinary reprojection
    noise), and a polar cap beside a Fiji zone written as 177..182."""
    from shapely.geometry import Polygon

    from mapsmith import antimeridian

    noisy = gpd.GeoDataFrame(
        geometry=[box(-180, -90, 180, 90), box(170, 0, 180.0000001, 1)], crs="EPSG:4326"
    )
    assert antimeridian.naive_crossings(noisy) == []
    fiji = gpd.GeoDataFrame(
        geometry=[box(-180, -90, 180, -80), box(177, -18, 182, -16)], crs="EPSG:4326"
    )
    assert antimeridian.naive_crossings(fiji) == []

    # And the message reads the seam from the same vertices the detector does:
    # a point at 200 beside a ring drawn 170 -> -170 used to send its author to
    # 0/360, the one meridian that ring does not cross.
    zone = tmp_path / "z.gpkg"
    gpd.GeoDataFrame(
        geometry=[Polygon([(170, -5), (-170, -5), (-170, 5), (170, 5)])], crs="EPSG:4326"
    ).to_file(zone)
    mixed = gpd.GeoDataFrame(
        geometry=[Polygon([(170, -5), (-170, -5), (-170, 5), (170, 5)]), Point(200, 0)],
        crs="EPSG:4326",
    )
    assert antimeridian.layer_seam(mixed) == (-180.0, 180.0)
    points = tmp_path / "p.gpkg"
    gpd.GeoDataFrame({"n": [1.0]}, geometry=[Point(175, 0)], crs="EPSG:4326").to_file(points)
    with pytest.raises(ValueError, match="180th meridian"):
        vector.count_in_polygons(str(points), str(zone), str(tmp_path / "c.gpkg"))


def test_no_utm_zone_says_why_and_what_to_use():
    """It said "centred on the antimeridian" for data centred anywhere, and
    gave no way out. Polar data is the realistic case: UTM stops at 84N."""
    from mapsmith import antimeridian

    arctic = gpd.GeoDataFrame(geometry=[Point(10, 88), Point(20, 89)], crs="EPSG:4326")
    with pytest.raises(RuntimeError, match="EPSG:32661") as refused:
        antimeridian.estimate_utm_crs(arctic)
    assert "antimeridian" not in str(refused.value)


def test_natural_earth_countries_are_not_refused():
    """The real file the review measured: Antarctica is feature 159."""
    from pathlib import Path

    import pyogrio

    from mapsmith import antimeridian

    shp = (
        Path(pyogrio.__file__).parent
        / "tests" / "fixtures" / "naturalearth_lowres" / "naturalearth_lowres.shp"
    )
    if not shp.exists():
        pytest.skip("this pyogrio build does not ship its Natural Earth fixture")
    countries = gpd.read_file(shp)
    assert len(countries) > 150
    assert antimeridian.naive_crossings(countries) == []


@pytest.mark.parametrize("side", ["first", "second"])
@pytest.mark.parametrize("operation", ["clip", "overlay", "spatial_join", "nearest_join"])
def test_the_other_region_operations_refuse_a_ring_drawn_across_180(tmp_path, operation, side):
    """Measured on 2026-09-24 before the refusal: clip, spatial_join and overlay
    each returned the feature on the FAR side of the world instead of the one
    inside the zone, and nearest_join returned nothing. Not measure_area, whose
    geodesic area follows the edge the short way and is right.

    On either input, which the CHANGELOG says and the first version of this
    test did not check: the review deleted the refusal of the first input and
    the suite stayed green."""
    from shapely.geometry import Polygon

    zone = _pacific_zone(tmp_path, Polygon([(170, -5), (-170, -5), (-170, 5), (170, 5)]))
    other = tmp_path / "other.gpkg"
    gpd.GeoDataFrame(
        {"id": ["inside", "far"]}, geometry=[box(172, -2, 178, 2), box(0, -2, 6, 2)],
        crs="EPSG:4326",
    ).to_file(other)
    a, b = (str(other), str(zone)) if side == "second" else (str(zone), str(other))
    out = str(tmp_path / "o.gpkg")
    calls = {
        "clip": lambda: vector.clip(a, b, out),
        "overlay": lambda: vector.overlay(a, b, out, how="intersection"),
        "spatial_join": lambda: vector.spatial_join(a, b, out),
        "nearest_join": lambda: vector.nearest_join(a, b, out),
    }
    with pytest.raises(ValueError, match="cross the 180th meridian"):
        calls[operation]()


@pytest.mark.parametrize("side", ["first", "second"])
def test_the_routed_spatial_join_refuses_it_on_the_fast_engines_too(tmp_path, side):
    """GeoParquet inputs in one CRS are routed to DuckDB, which is planar too.
    Measured by the 0.6.0 pre-release review before the refusal moved into the
    router: `engine_used: duckdb`, `verified: True`, and only the feature on the
    far side of the world in the output."""
    from shapely.geometry import Polygon

    from mapsmith.engines import dispatch

    zone = tmp_path / "zone.parquet"
    gpd.GeoDataFrame(
        {"z": ["pacific"]},
        geometry=[Polygon([(170, -5), (-170, -5), (-170, 5), (170, 5)])],
        crs="EPSG:4326",
    ).to_parquet(zone)
    other = tmp_path / "other.parquet"
    gpd.GeoDataFrame(
        {"id": ["inside", "far"]}, geometry=[box(172, -2, 178, 2), box(0, -2, 6, 2)],
        crs="EPSG:4326",
    ).to_parquet(other)
    a, b = (str(other), str(zone)) if side == "second" else (str(zone), str(other))
    with pytest.raises(ValueError, match="cross the 180th meridian"):
        dispatch.spatial_join_routed(a, b, str(tmp_path / "j.parquet"))


def test_the_routed_spatial_join_keeps_the_fast_path_on_ordinary_data(tmp_path):
    """The refusal must not push ordinary GeoParquet off the fast engine."""
    from mapsmith.engines import dispatch

    left = tmp_path / "l.parquet"
    gpd.GeoDataFrame({"a": [1]}, geometry=[box(0, 0, 1, 1)], crs="EPSG:4326").to_parquet(left)
    right = tmp_path / "r.parquet"
    gpd.GeoDataFrame({"b": [2]}, geometry=[box(0.5, 0.5, 2, 2)], crs="EPSG:4326").to_parquet(right)
    result = dispatch.spatial_join_routed(str(left), str(right), str(tmp_path / "j.parquet"))
    assert result["engine_used"] in ("duckdb", "sedonadb")


def test_the_utm_estimate_centres_on_the_antimeridian_when_the_data_does(tmp_path):
    """GeoPandas centres on the mean of minx and maxx, which for data straddling
    180 is about 0: two points at 175E and 175W came back with EPSG:32630,
    centred on 3W, the opposite side of the planet."""
    from mapsmith import antimeridian

    both = gpd.GeoDataFrame(geometry=[Point(175, 0), Point(-175, 1)], crs="EPSG:4326")
    zone = antimeridian.estimate_utm_crs(both).to_epsg()
    assert zone in (32601, 32660), f"data around 180 was given UTM EPSG:{zone}"
    # Data that does not cross goes straight to GeoPandas, unchanged.
    rome = gpd.GeoDataFrame(geometry=[Point(12.5, 41.9)], crs="EPSG:4326")
    assert antimeridian.estimate_utm_crs(rome) == rome.estimate_utm_crs()


def test_one_feature_split_at_180_is_read_as_crossing():
    """The form the refusal tells a caller to produce, as ONE feature. Its
    feature bounds are -180..180, and read per feature the layer spanned the
    world: the UTM estimate came back EPSG:32730, centred on 3W (found by the
    0.6.0 pre-release review). The same shape as two features was right."""
    from shapely.geometry import MultiPolygon

    from mapsmith import antimeridian

    split = gpd.GeoDataFrame(
        geometry=[MultiPolygon([box(178, -1, 180, 1), box(-180, -1, -178, 1)])],
        crs="EPSG:4326",
    )
    extent = antimeridian.describe_extent(split)
    assert extent.get("crosses_antimeridian") is True
    assert extent["true_extent"]["width_degrees"] == pytest.approx(4.0)
    zone = antimeridian.estimate_utm_crs(split).to_epsg()
    assert zone in (32601, 32660, 32701, 32760), f"split zone given UTM EPSG:{zone}"


def test_nearest_join_measures_true_distances_across_the_antimeridian(tmp_path):
    """Measured before the fix: 351.7 and 354.0 km where the truth is about 334,
    five to six per cent too far, with no warning -- because the distances were
    computed in a UTM zone 180 degrees away. After: within one per cent."""
    from pyproj import Geod
    from shapely.geometry import MultiPolygon

    points = tmp_path / "p.gpkg"
    gpd.GeoDataFrame(
        {"id": ["175E", "175W"]}, geometry=[Point(175, 0), Point(-175, 0)], crs="EPSG:4326"
    ).to_file(points)
    zone = _pacific_zone(tmp_path, MultiPolygon([box(178, -1, 180, 1), box(-180, -1, -178, 1)]))
    result = vector.nearest_join(str(points), str(zone), str(tmp_path / "n.gpkg"))
    out = gpd.read_file(result["output"])
    truth = Geod(ellps="WGS84").inv(175, 0, 178, 0)[2]  # three degrees along the equator
    for _, row in out.iterrows():
        measured = float(row[result["distance_column"]])
        assert abs(measured / truth - 1) < 0.01, (
            f"{row['id']}: {measured / 1000:.1f} km, the truth is {truth / 1000:.1f}"
        )
