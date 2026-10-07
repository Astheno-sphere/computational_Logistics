"""The line operations, on geometry whose answer can be worked out on paper.

A vertex 3 cm from its target moves 3 cm. A 90 m line at 20 m spacing gives six
points at 0, 20, 40, 60, 80, 90. Two lines crossing in a plus sign meet at one
point, in the middle. A 90-degree rotation about a known origin sends (0, 10) to
a place arithmetic can name. None of these needs a reference implementation to
check against, which is the point: a test that compares one implementation with
another only proves they agree.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon

from mapsmith import verify
from mapsmith.engines import linework


def layer(tmp_path, name, geometries, crs="EPSG:32632", **columns):
    gdf = gpd.GeoDataFrame(
        columns or {"id": list(range(len(geometries)))},
        geometry=list(geometries),
        crs=crs,
    )
    path = tmp_path / f"{name}.parquet"
    gdf.to_parquet(path)
    return str(path)


# --- snap_layer ------------------------------------------------------------


def test_a_vertex_within_the_tolerance_moves_exactly_onto_its_target(tmp_path):
    """3 cm away, 5 cm tolerance: it moves 3 cm and lands on the target exactly."""
    moving = layer(tmp_path, "moving", [LineString([(0, 0.03), (10, 0.03)])])
    reference = layer(tmp_path, "ref", [LineString([(0, 0), (10, 0)])])
    out = tmp_path / "snapped.parquet"

    result = linework.snap_layer(moving, reference, str(out), tolerance=0.05)
    assert result["vertices_moved"] == 2
    assert result["largest_move"] == pytest.approx(0.03)

    snapped = gpd.read_parquet(out)
    assert list(snapped.geometry.iloc[0].coords) == [(0.0, 0.0), (10.0, 0.0)]


def test_a_vertex_outside_the_tolerance_is_left_where_it_is(tmp_path):
    """The output must not silently look fixed when nothing was fixed."""
    moving = layer(tmp_path, "moving", [LineString([(0, 0.03), (10, 0.03)])])
    reference = layer(tmp_path, "ref", [LineString([(0, 0), (10, 0)])])
    out = tmp_path / "unsnapped.parquet"

    result = linework.snap_layer(moving, reference, str(out), tolerance=0.01)
    assert result["vertices_moved"] == 0
    assert result["largest_move"] == 0.0
    assert next(iter(gpd.read_parquet(out).geometry.iloc[0].coords)) == (0.0, 0.03)


def test_no_vertex_may_move_further_than_the_tolerance(tmp_path):
    """The contract, asserted in the manifest rather than assumed."""
    moving = layer(tmp_path, "moving", [LineString([(0, 0.03), (10, 0.03)])])
    reference = layer(tmp_path, "ref", [LineString([(0, 0), (10, 0)])])
    out = tmp_path / "snapped.parquet"
    result = linework.snap_layer(moving, reference, str(out), tolerance=0.05)

    manifest = _manifest(result)
    names = {check["name"]: check for check in manifest["verification"]}
    assert names["x-mapsmith:no_vertex_moved_further_than_the_tolerance"]["passed"]


def test_snapping_needs_a_projected_crs_because_the_tolerance_is_a_distance(tmp_path):
    moving = layer(
        tmp_path, "deg", [LineString([(9.0, 45.0), (9.1, 45.0)])], crs="EPSG:4326"
    )
    reference = layer(
        tmp_path, "degref", [LineString([(9.0, 45.001), (9.1, 45.001)])], crs="EPSG:4326"
    )
    with pytest.raises(ValueError, match="geographic CRS"):
        linework.snap_layer(moving, reference, str(tmp_path / "o.parquet"), 0.05)


def test_an_empty_reference_is_refused_rather_than_reported_as_snapped(tmp_path):
    moving = layer(tmp_path, "moving", [LineString([(0, 0), (10, 0)])])
    empty = gpd.GeoDataFrame({"id": []}, geometry=[], crs="EPSG:32632")
    reference = tmp_path / "empty.parquet"
    empty.to_parquet(reference)
    with pytest.raises(ValueError, match="no vertices"):
        linework.snap_layer(moving, str(reference), str(tmp_path / "o.parquet"), 1.0)


def test_a_polygon_reference_snaps_to_its_outer_ring_and_to_its_holes(tmp_path):
    """Parcels snapped to a block outline, the case the reference crashed on.

    A 100 m square with a 20 m square hole in the middle. One vertex 4 cm from
    the outer corner (100, 100), one 4 cm from the hole's corner (40, 40): both
    move exactly onto them. Until 2026-09-29 a polygon reference raised
    NotImplementedError from `Polygon.coords`.
    """
    block = Polygon(
        [(0, 0), (100, 0), (100, 100), (0, 100)],
        holes=[[(40, 40), (60, 40), (60, 60), (40, 60)]],
    )
    moving = layer(tmp_path, "moving", [LineString([(40.04, 40.0), (100.0, 100.04)])])
    reference = layer(tmp_path, "block", [block])
    out = tmp_path / "snapped.parquet"

    result = linework.snap_layer(moving, reference, str(out), tolerance=0.05)
    assert result["vertices_moved"] == 2
    assert list(gpd.read_parquet(out).geometry.iloc[0].coords) == [(40.0, 40.0), (100.0, 100.0)]


def test_a_multipart_reference_offers_the_vertices_of_every_part(tmp_path):
    """Two parts; the vertex near the SECOND part's end moves onto it."""
    reference = layer(
        tmp_path, "parts", [MultiLineString([[(0, 0), (10, 0)], [(20, 0), (30, 0)]])]
    )
    moving = layer(tmp_path, "moving", [LineString([(0, 5), (30.02, 0)])])
    out = tmp_path / "snapped.parquet"

    result = linework.snap_layer(moving, reference, str(out), tolerance=0.05)
    assert result["vertices_moved"] == 1
    assert list(gpd.read_parquet(out).geometry.iloc[0].coords) == [(0.0, 5.0), (30.0, 0.0)]


# --- points_along_lines ----------------------------------------------------


def test_a_line_that_divides_evenly_gives_the_points_the_spacing_implies(tmp_path):
    """100 m at 20 m: 0, 20, 40, 60, 80, 100 — six points, no extra endpoint."""
    lines = layer(tmp_path, "line", [LineString([(0, 0), (100, 0)])])
    out = tmp_path / "stations.parquet"

    result = linework.points_along_lines(lines, str(out), spacing=20.0)
    assert result["points"] == 6

    points = gpd.read_parquet(out)
    assert list(points["distance_along"]) == [0.0, 20.0, 40.0, 60.0, 80.0, 100.0]
    assert [round(p.x, 9) for p in points.geometry] == [0, 20, 40, 60, 80, 100]


def test_a_line_that_does_not_divide_evenly_keeps_its_end(tmp_path):
    """90 m at 20 m: 0, 20, 40, 60, 80 and then 90 — the last interval is short.

    A profile that stops 10 m before the end is a profile of the wrong thing,
    so the endpoint is added by default and the manifest records that it was.
    """
    lines = layer(tmp_path, "line", [LineString([(0, 0), (90, 0)])])
    out = tmp_path / "stations.parquet"

    result = linework.points_along_lines(lines, str(out), spacing=20.0)
    assert result["points"] == 6
    assert list(gpd.read_parquet(out)["distance_along"]) == [0, 20, 40, 60, 80, 90]

    without = linework.points_along_lines(
        lines, str(tmp_path / "no_end.parquet"), spacing=20.0, include_endpoint=False
    )
    assert without["points"] == 5


def test_distance_along_follows_the_line_and_not_the_straight_line(tmp_path):
    """An L-shaped line: the point at 15 m is 5 m up the second leg.

    Measuring along the chord instead of the geometry would put it at a
    plausible place that is not on the line at all — and the operation's own
    check would catch it, which is what this asserts.
    """
    lines = layer(tmp_path, "bend", [LineString([(0, 0), (10, 0), (10, 10)])])
    out = tmp_path / "bend_points.parquet"
    linework.points_along_lines(lines, str(out), spacing=5.0)

    points = gpd.read_parquet(out)
    at_fifteen = points[points["distance_along"] == 15.0].geometry.iloc[0]
    assert (round(at_fifteen.x, 9), round(at_fifteen.y, 9)) == (10.0, 5.0)


def test_the_expected_point_count_is_checked_against_the_arithmetic(tmp_path):
    lines = layer(tmp_path, "line", [LineString([(0, 0), (90, 0)])])
    out = tmp_path / "stations.parquet"
    result = linework.points_along_lines(lines, str(out), spacing=20.0)

    names = {c["name"]: c for c in _manifest(result)["verification"]}
    assert names["x-mapsmith:the_point_count_is_what_the_spacing_implies"]["passed"]
    assert names["x-mapsmith:every_point_lies_on_its_line"]["passed"]


def test_polygons_are_refused_by_name(tmp_path):
    from shapely.geometry import Polygon

    polygons = layer(tmp_path, "poly", [Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])])
    with pytest.raises(ValueError, match="works on lines"):
        linework.points_along_lines(polygons, str(tmp_path / "o.parquet"), 1.0)


# --- line_intersections ----------------------------------------------------


def test_a_plus_sign_crosses_once_in_the_middle(tmp_path):
    across = layer(tmp_path, "across", [LineString([(0, 5), (10, 5)])])
    down = layer(tmp_path, "down", [LineString([(5, 0), (5, 10)])])
    out = tmp_path / "crossings.parquet"

    result = linework.line_intersections(across, down, str(out))
    assert result["crossings"] == 1

    found = gpd.read_parquet(out)
    assert (found["x"].iloc[0], found["y"].iloc[0]) == (5.0, 5.0)
    assert found["kind"].iloc[0] == "crossing"


def test_lines_meeting_end_to_end_are_a_junction_and_not_a_crossing(tmp_path):
    """Reporting them would bury the real crossings under every node."""
    first = layer(tmp_path, "first", [LineString([(0, 0), (10, 0)])])
    second = layer(tmp_path, "second", [LineString([(10, 0), (20, 0)])])
    out = tmp_path / "none.parquet"

    result = linework.line_intersections(first, second, str(out))
    assert result["crossings"] == 0


def test_within_one_layer_each_pair_is_reported_once(tmp_path):
    """Three lines through one point: three pairs, not six, and never a self-pair."""
    lines = layer(
        tmp_path,
        "star",
        [
            LineString([(0, 5), (10, 5)]),
            LineString([(5, 0), (5, 10)]),
            LineString([(0, 0), (10, 10)]),
        ],
    )
    out = tmp_path / "nodes.parquet"
    result = linework.line_intersections(lines, None, str(out))
    assert result["crossings"] == 3
    found = gpd.read_parquet(out)
    assert all(found["first_index"] < found["second_index"])


def test_a_line_drawn_on_top_of_another_is_reported_as_an_overlap(tmp_path):
    """A different defect with a different fix, so it gets a different label."""
    first = layer(tmp_path, "first", [LineString([(0, 0), (10, 0)])])
    second = layer(tmp_path, "second", [LineString([(2, 0), (8, 0)])])
    out = tmp_path / "overlap.parquet"

    result = linework.line_intersections(first, second, str(out))
    assert result["overlapping_pairs"] == 1
    assert result["crossings"] == 0
    assert set(gpd.read_parquet(out)["kind"]) == {"overlap"}


# --- transform_by_control_points -------------------------------------------


def _control(tmp_path, pairs, crs="EPSG:32632"):
    """pairs: [((local_x, local_y), (known_x, known_y)), ...]"""
    gdf = gpd.GeoDataFrame(
        {
            "source_x": [p[0][0] for p in pairs],
            "source_y": [p[0][1] for p in pairs],
        },
        geometry=[Point(*p[1]) for p in pairs],
        crs=crs,
    )
    path = tmp_path / "control.parquet"
    gdf.to_parquet(path)
    return str(path)


def test_a_quarter_turn_and_a_shift_is_recovered_exactly(tmp_path):
    """Rotate 90 degrees about the origin, then move to (100, 200).

    Under that transform (0,0) -> (100,200) and (10,0) -> (100,210), which are
    the two control points. The fit must then send (0,10) to (90,200):
        x' = 0·0 - 1·10 + 100 = 90
        y' = 1·0 + 0·10 + 200 = 200
    """
    local = layer(tmp_path, "local", [Point(0, 10)], crs="EPSG:32632")
    control = _control(tmp_path, [((0, 0), (100, 200)), ((10, 0), (100, 210))])
    out = tmp_path / "fixed.parquet"

    result = linework.transform_by_control_points(
        local, control, str(out), target_crs="EPSG:32632"
    )
    moved = gpd.read_parquet(out).geometry.iloc[0]
    assert (round(moved.x, 9), round(moved.y, 9)) == (90.0, 200.0)
    assert result["exactly_determined"] is True
    assert result["rms_residual"] == pytest.approx(0.0, abs=1e-9)


def test_an_exactly_determined_fit_says_its_zero_residual_proves_nothing(tmp_path):
    """The whole reason this operation is worth building here.

    Two control points always fit perfectly, including when one was typed
    wrong. A run that reports 'residual 0.0' and nothing else is telling a
    caller their georeferencing is perfect on no evidence at all.
    """
    local = layer(tmp_path, "local", [Point(0, 10)])
    control = _control(tmp_path, [((0, 0), (100, 200)), ((10, 0), (100, 210))])
    out = tmp_path / "fixed.parquet"
    result = linework.transform_by_control_points(
        local, control, str(out), target_crs="EPSG:32632"
    )

    notes = " ".join(_manifest(result)["notes"])
    assert "exactly determined" in notes
    assert "say nothing" in notes or "whatever the points are" in notes


def test_a_mistyped_control_point_shows_up_in_the_residuals(tmp_path):
    """Three points, one moved 5 m off the transform the other two describe.

    A similarity fit cannot absorb it, so the residual is non-zero and the
    worst point is named. This is the number the operation exists to surface.
    """
    local = layer(tmp_path, "local", [Point(0, 0)])
    control = _control(
        tmp_path,
        [((0, 0), (100, 200)), ((10, 0), (100, 210)), ((0, 10), (85, 200))],
    )
    out = tmp_path / "fixed.parquet"
    result = linework.transform_by_control_points(
        local, control, str(out), target_crs="EPSG:32632"
    )
    assert result["exactly_determined"] is False
    assert result["rms_residual"] > 0.5
    assert result["largest_residual"] > 1.0
    assert len(result["residuals"]) == 3

    names = {c["name"]: c for c in _manifest(result)["verification"]}
    trust = names["x-mapsmith:the_residuals_are_small_enough_to_trust"]
    assert trust["passed"] is False and trust.get("critical") is False


def test_too_few_control_points_for_the_chosen_transform_are_refused(tmp_path):
    local = layer(tmp_path, "local", [Point(0, 0)])
    control = _control(tmp_path, [((0, 0), (100, 200)), ((10, 0), (100, 210))])
    with pytest.raises(ValueError, match="at least 3"):
        linework.transform_by_control_points(
            local, control, str(tmp_path / "o.parquet"),
            target_crs="EPSG:32632", kind="affine",
        )


def test_the_output_is_declared_in_the_control_points_crs_and_says_why(tmp_path):
    """The fit IS the georeferencing, so whatever the input claimed is discarded.

    Silently keeping the input's CRS would produce a layer whose coordinates are
    in one system and whose declaration says another — the exact defect
    `readers` and `verify.same_crs` exist to prevent elsewhere.
    """
    local = layer(tmp_path, "local", [Point(0, 10)], crs="EPSG:3857")
    control = _control(tmp_path, [((0, 0), (100, 200)), ((10, 0), (100, 210))])
    out = tmp_path / "fixed.parquet"
    result = linework.transform_by_control_points(
        local, control, str(out), target_crs="EPSG:32632"
    )

    assert verify.same_crs(gpd.read_parquet(out).crs, "EPSG:32632")
    decisions = _manifest(result)["crs_decisions"]
    # The spec's names where the spec has one. Until 2026-09-06 this operation
    # wrote `declared_output_crs`, which means exactly `target_crs` and was
    # readable by nobody holding the specification. `analysis_crs` is the
    # target because the least-squares functional is a sum of squared
    # discrepancies in target coordinates -- the same unit the residuals below
    # are recorded in.
    assert decisions["target_crs"] == "EPSG:32632"
    assert decisions["analysis_crs"] == "EPSG:32632"
    # And NOT `source_crs`, deliberately: everywhere else in MapSmith that key
    # comes with `transformation`, describing a reprojection, and no
    # reprojection happened here. What the input declared is recorded under a
    # name of ours, which can say the thing that is true of it.
    assert "source_crs" not in decisions
    assert decisions["x-mapsmith:input_crs_discarded"] == "EPSG:3857"
    assert "EPSG:3857" in decisions["reason"]


def _manifest(result: dict) -> dict:
    import json
    from pathlib import Path

    return json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))


def test_a_t_junction_is_a_crossing_because_it_is_the_forgotten_node(tmp_path):
    """The defect: `touches` is true for a T as well as for an end-to-end join.

    A line ending on the middle of another is exactly the node somebody forgot
    to split, and it is what the single-layer mode exists to find. Skipping it
    reported no crossings and then wrote into the manifest that the network may
    already be noded — a confident, well-formed, false statement about the data.
    """
    source = tmp_path / "unnoded.parquet"
    gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[
            LineString([(0, 0), (10, 0)]),
            LineString([(5, 0), (5, 10)]),  # ends on the middle of the first
        ],
        crs="EPSG:32632",
    ).to_parquet(source)
    out = tmp_path / "found.parquet"

    result = linework.line_intersections(str(source), None, str(out))

    assert result["crossings"] == 1, (
        "the T junction was not reported, which is the only kind of forgotten "
        "node this operation is asked about"
    )
    found = gpd.read_parquet(out)
    assert (float(found.geometry.iloc[0].x), float(found.geometry.iloc[0].y)) == (5.0, 0.0)


def test_two_segments_joined_end_to_end_are_not_a_crossing(tmp_path):
    """The other half, so the fix above is not just "report everything".

    A shared endpoint is an ordinary junction and reporting it would bury the
    real findings in one row per node.
    """
    source = tmp_path / "noded.parquet"
    gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[LineString([(0, 0), (10, 0)]), LineString([(10, 0), (20, 0)])],
        crs="EPSG:32632",
    ).to_parquet(source)
    out = tmp_path / "none.parquet"

    result = linework.line_intersections(str(source), None, str(out))
    assert result["crossings"] == 0


def test_a_survey_with_no_crs_is_the_case_this_operation_exists_for(tmp_path):
    """It refused the one input it was built for.

    The docstring says this is for "data in a local, assumed or shifted grid: a
    traverse that plots in the river, a scanned plan, an old site grid nobody has
    the parameters for" — none of which has a CRS. The preconditions required one
    on the input, so the operation computed the right answer, wrote the right
    output and the right manifest, and then raised with advice to assign a CRS
    first: the thing it replaces. Every existing test passed a `crs=`.

    The control points still need one. They ARE the georeferencing.
    """
    survey = tmp_path / "traverse.parquet"
    gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[LineString([(0, 0), (100, 0), (100, 100)])],
    ).to_parquet(survey)

    control = tmp_path / "control.parquet"
    gpd.GeoDataFrame(
        {"source_x": [0.0, 100.0, 100.0], "source_y": [0.0, 0.0, 100.0]},
        geometry=[
            Point(500000, 5030000),
            Point(500100, 5030000),
            Point(500100, 5030100),
        ],
        crs="EPSG:32632",
    ).to_parquet(control)

    out = tmp_path / "placed.parquet"
    result = linework.transform_by_control_points(
        str(survey), str(control), str(out), "EPSG:32632"
    )

    # The reason is DERIVED from the input, not asserted about it. It used to
    # say "the input carried a local or assumed system" on every run, including
    # the runs where the input declared a perfectly good CRS -- the one field
    # whose whole job is the *why*, stating a fact about the input that nobody
    # had checked. Here there really is no CRS, and the record says so.
    decisions = _manifest(result)["crs_decisions"]
    assert decisions["x-mapsmith:input_crs_discarded"] is None
    assert "carried no coordinate reference system" in decisions["reason"]

    placed = gpd.read_parquet(out)
    assert placed.crs.to_epsg() == 32632
    # The first control point maps (0, 0) onto (500000, 5030000) exactly, and a
    # similarity fit on three consistent points reproduces it.
    first = next(iter(placed.geometry.iloc[0].coords))
    assert first == pytest.approx((500000.0, 5030000.0))


def test_control_points_without_a_crs_are_still_refused(tmp_path):
    """The other half: dropping the input's requirement must not drop theirs."""
    survey = tmp_path / "traverse.parquet"
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[LineString([(0, 0), (100, 0)])]
    ).to_parquet(survey)
    control = tmp_path / "control.parquet"
    gpd.GeoDataFrame(
        {"source_x": [0.0, 100.0], "source_y": [0.0, 0.0]},
        geometry=[Point(500000, 5030000), Point(500100, 5030000)],
    ).to_parquet(control)

    out = tmp_path / "placed.parquet"
    with pytest.raises(Exception, match="(?i)crs"):
        linework.transform_by_control_points(
            str(survey), str(control), str(out), "EPSG:32632"
        )
