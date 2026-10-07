"""Reading a surface at points, along a line, and between two positions.

Every expected value here is arithmetic done on paper first. The DEM is
`value = row * 10 + column` on 10 m cells, so the value at any position follows
from the position; the profile DEM is a linear ramp, so an elevation at distance
d is a straight-line function of d. Either the code returns those numbers or it
is wrong — there is no "close enough" to hide in.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import LineString, Point

from mapsmith.engines import sampling


@pytest.fixture
def grid(tmp_path: Path) -> Path:
    """10x10 cells of 10 m, origin at (0, 100), value = row * 10 + column.

    Cell (row, col) covers x in [col*10, col*10+10) and y in
    (100 - row*10 - 10, 100 - row*10]. Its centre is at
    (col*10 + 5, 95 - row*10).
    """
    path = tmp_path / "grid.tif"
    values = np.arange(100, dtype="float32").reshape(10, 10)
    with rasterio.open(
        path, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 100, 10, 10), nodata=-9999.0,
    ) as dst:
        dst.write(values, 1)
    return path


@pytest.fixture
def ramp(tmp_path: Path) -> Path:
    """Elevation rising 1 m per metre eastward: value = x at every cell centre.

    Cells are 1 m, origin (0, 20), so the centre of column c is at x = c + 0.5
    and carries the value c + 0.5. A bilinear read at any x inside the grid
    therefore returns x exactly, which makes a profile along a horizontal line a
    closed-form check of the sampling AND of the distance stepping at once.
    """
    path = tmp_path / "ramp.tif"
    row = np.arange(20, dtype="float32") + 0.5
    values = np.tile(row, (20, 1))
    with rasterio.open(
        path, "w", driver="GTiff", height=20, width=20, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 20, 1, 1),
    ) as dst:
        dst.write(values, 1)
    return path


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


# --------------------------------------------------------- sample at points

def test_nearest_reads_the_cell_the_point_falls_in(grid, tmp_path):
    """Three points whose cells can be worked out from the transform."""
    points = tmp_path / "points.gpkg"
    gpd.GeoDataFrame(
        {"name": ["top-left", "row2-col3", "bottom-right"]},
        geometry=[Point(5, 95), Point(35, 75), Point(95, 5)],
        crs="EPSG:32632",
    ).to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "sampled.parquet"
    result = sampling.sample_raster_at_points(str(grid), str(points), str(out), "nearest")

    got = gpd.read_parquet(out)["value"].tolist()
    # row*10 + col: (0,0) -> 0, (2,3) -> 23, (9,9) -> 99
    assert got == [0.0, 23.0, 99.0]
    assert result["sampled"] == 3 and result["unreadable"] == 0


def test_bilinear_interpolates_between_cell_centres_exactly(grid, tmp_path):
    """Halfway between two horizontally adjacent centres is their mean.

    Centres of (0,0) and (0,1) are at x=5 and x=15, carrying 0 and 1. At x=10,
    y=95 the answer is exactly 0.5 — and if the half-cell offset in the
    interpolation is dropped, it comes back 1.0 instead, which is the kind of
    error that looks like data.
    """
    points = tmp_path / "mid.gpkg"
    gpd.GeoDataFrame(
        {"n": [1, 2]}, geometry=[Point(10, 95), Point(5, 90)], crs="EPSG:32632"
    ).to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "bilinear.parquet"
    sampling.sample_raster_at_points(str(grid), str(points), str(out), "bilinear")

    got = gpd.read_parquet(out)["value"].tolist()
    # between (0,0)=0 and (0,1)=1 -> 0.5 ; between (0,0)=0 and (1,0)=10 -> 5.0
    assert got == pytest.approx([0.5, 5.0])


def test_a_point_outside_the_raster_is_null_and_counted_not_silent(grid, tmp_path):
    """The failure this module exists to prevent: a null that reads as a value.

    `rasterio.sample` would return the nodata value, -9999, which averages into
    a profile and produces a number nobody can defend.
    """
    points = tmp_path / "outside.gpkg"
    gpd.GeoDataFrame(
        {"n": [1, 2]}, geometry=[Point(5, 95), Point(500, 500)], crs="EPSG:32632"
    ).to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "partial.parquet"
    result = sampling.sample_raster_at_points(str(grid), str(points), str(out), "nearest")

    got = gpd.read_parquet(out)["value"].tolist()
    assert got[0] == 0.0
    assert got[1] is None or (isinstance(got[1], float) and np.isnan(got[1]))
    assert result["unreadable"] == 1

    named = {c["name"]: c for c in _manifest(out)["verification"]}
    check = named["x-mapsmith:every_position_had_a_value"]
    assert check["passed"] is False, "the null was not reported"
    assert check.get("critical") is False, (
        "sampling outside the raster is legitimate on purpose — making this "
        "critical would break the survey-comparison case it is best at"
    )
    assert "1 of 2" in check["detail"]


def test_a_nodata_cell_reads_as_null_rather_than_as_minus_9999(tmp_path):
    holed = tmp_path / "holed.tif"
    values = np.full((3, 3), 5.0, dtype="float32")
    values[1, 1] = -9999.0
    with rasterio.open(
        holed, "w", driver="GTiff", height=3, width=3, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 30, 10, 10), nodata=-9999.0,
    ) as dst:
        dst.write(values, 1)

    points = tmp_path / "hole.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[Point(15, 15)], crs="EPSG:32632"
    ).to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "hole.parquet"
    result = sampling.sample_raster_at_points(str(holed), str(points), str(out), "nearest")
    assert result["unreadable"] == 1, "the nodata cell came back as a number"


def test_the_points_are_reprojected_and_the_decision_is_recorded(grid, tmp_path):
    """A point layer in degrees still lands on the right cell, and says so."""
    points = tmp_path / "wgs84.gpkg"
    in_utm = gpd.GeoDataFrame(
        {"n": [1]}, geometry=[Point(35, 75)], crs="EPSG:32632"
    )
    in_utm.to_crs("EPSG:4326").to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "reprojected.parquet"
    sampling.sample_raster_at_points(str(grid), str(points), str(out), "nearest")

    assert gpd.read_parquet(out)["value"].tolist() == [23.0]
    decisions = _manifest(out)["crs_decisions"]
    assert "32632" in decisions["analysis_crs"]
    # Which input moved and how, not a sentence with the word "reprojected" in
    # it. The points carry the values onto the cells, so a ballpark here puts
    # them on the wrong cells — `is_ballpark` is the fact worth asserting.
    assert decisions["x-mapsmith:inputs_reprojected"] == [
        {"argument": "points_path", "from": "EPSG:4326"}
    ]
    assert decisions["transformation"]["is_ballpark"] is False


def test_the_method_has_to_be_stated(grid, tmp_path):
    points = tmp_path / "p.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[Point(5, 95)], crs="EPSG:32632"
    ).to_file(points, layer="p", driver="GPKG")
    with pytest.raises(ValueError, match="nearest"):
        sampling.sample_raster_at_points(
            str(grid), str(points), str(tmp_path / "x.parquet"), "cubic"
        )


def test_an_existing_column_is_not_overwritten_silently(grid, tmp_path):
    points = tmp_path / "clash.gpkg"
    gpd.GeoDataFrame(
        {"value": [42]}, geometry=[Point(5, 95)], crs="EPSG:32632"
    ).to_file(points, layer="p", driver="GPKG")
    with pytest.raises(ValueError, match="already has a column"):
        sampling.sample_raster_at_points(
            str(grid), str(points), str(tmp_path / "x.parquet"), "nearest"
        )


def test_polygons_are_refused_and_pointed_at_the_right_operation(grid, tmp_path):
    from shapely.geometry import box

    polys = tmp_path / "polys.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[box(0, 0, 10, 10)], crs="EPSG:32632"
    ).to_file(polys, layer="p", driver="GPKG")
    with pytest.raises(ValueError, match="zonal_statistics"):
        sampling.sample_raster_at_points(
            str(grid), str(polys), str(tmp_path / "x.parquet"), "nearest"
        )


# ------------------------------------------------------------------ profile

def test_a_profile_along_a_ramp_is_the_ramp(ramp, tmp_path):
    """Closed form twice over: the count and every value.

    The line runs from x=2 to x=18 at y=10, so its length is 16 m; sampled every
    4 m that is floor(16/4) + 1 = 5 points, at x = 2, 6, 10, 14, 18. The ramp
    reads value = x, so the elevations are those same numbers.
    """
    line = tmp_path / "line.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[LineString([(2, 10), (18, 10)])], crs="EPSG:32632"
    ).to_file(line, layer="l", driver="GPKG")

    out = tmp_path / "profile.parquet"
    result = sampling.elevation_profile(str(ramp), str(line), str(out), spacing=4.0)

    got = gpd.read_parquet(out)
    assert result["points"] == 5
    assert got["distance"].tolist() == [0.0, 4.0, 8.0, 12.0, 16.0]
    assert got["value"].tolist() == pytest.approx([2.0, 6.0, 10.0, 14.0, 18.0])
    assert result["total_length"] == pytest.approx(16.0)

    named = {c["name"]: c["passed"] for c in _manifest(out)["verification"]}
    assert named["x-mapsmith:each_profile_starts_at_zero_and_steps_by_the_spacing"] is True


def test_the_spacing_is_metres_along_the_line_even_on_a_dem_in_degrees(tmp_path):
    """Until 2026-09-25 the line was reprojected to the raster's CRS and the
    spacing measured after: on a DEM in degrees `spacing=100` meant 100
    degrees, and a 1000 m line came back as one point with nothing in the
    result to say so. Distances belong to the line's projected CRS; only the
    sample points go to the raster's to be read."""
    dem = tmp_path / "dem4326.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(11.0, 44.0, 0.001, 0.001),
    ) as dst:
        dst.write(np.full((200, 200), 7.0, dtype="float32"), 1)
    line = gpd.GeoDataFrame(
        geometry=[LineString([(670000, 4860000), (671000, 4860000)])], crs="EPSG:32632"
    )
    line.to_file(tmp_path / "line.gpkg")
    out = tmp_path / "p.parquet"
    result = sampling.elevation_profile(str(dem), str(tmp_path / "line.gpkg"), str(out), spacing=100)
    got = gpd.read_parquet(out)
    assert list(got["distance"]) == pytest.approx([100.0 * i for i in range(11)])
    assert list(got["value"]) == pytest.approx([7.0] * 11)  # every point landed on the DEM
    assert got.crs.to_epsg() == 32632
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    decisions = record["crs_decisions"]
    assert decisions["analysis_crs"] == "EPSG:32632"
    # Nothing of the caller's moved for the result: the points only visited the
    # DEM's CRS to be read. `inputs_reprojected` naming the line's own CRS said
    # the output never was in a CRS it is written in.
    assert "x-mapsmith:inputs_reprojected" not in decisions
    # What was transformed is the sample points, to be read: the spec's own pair.
    assert (decisions["source_crs"], decisions["target_crs"]) == ("EPSG:32632", "EPSG:4326")
    assert record["output"]["crs"] == "EPSG:32632"
    assert decisions["transformation"]["is_ballpark"] is False  # same datum, a real operation


def test_a_plan_places_the_profile_in_the_crs_the_operation_writes(tmp_path):
    """The plan validator simulates each step's output CRS from its binding, and
    the binding kept saying the raster's after the operation stopped writing
    there. Derived from a run with two different CRSs, not from the binding's
    text: whatever input the binding names must be the one the output is in."""
    from mapsmith.plans.registry import BINDINGS

    dem = tmp_path / "dem4326.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(11.0, 44.0, 0.001, 0.001),
    ) as dst:
        dst.write(np.full((200, 200), 7.0, dtype="float32"), 1)
    line = tmp_path / "line.gpkg"
    gpd.GeoDataFrame(
        geometry=[LineString([(670000, 4860000), (671000, 4860000)])], crs="EPSG:32632"
    ).to_file(line)
    out = tmp_path / "p.parquet"
    sampling.elevation_profile(str(dem), str(line), str(out), spacing=100)
    kind, argument = BINDINGS["elevation_profile"].crs_effect
    assert kind == "same_as"
    named = {"raster_path": "EPSG:4326", "line_path": "EPSG:32632"}[argument]
    assert gpd.read_parquet(out).crs.to_string() == named


@pytest.fixture
def incline(tmp_path: Path) -> Path:
    """A plane rising 2 m per 100 m eastward: z = 0.02 * x, on 10 m cells.

    Bilinear interpolation on a plane is exact, so the gradient along any line
    is 2% times the cosine of its angle to the east -- by arithmetic."""
    path = tmp_path / "incline.tif"
    columns = np.arange(200, dtype="float32") * 10 + 5
    with rasterio.open(
        path, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0.0, 2000.0, 10.0, 10.0),
    ) as dst:
        dst.write(np.tile(0.02 * columns, (200, 1)), 1)
    return path


def _grade_run(incline, tmp_path, line, **kwargs):
    lines = tmp_path / "track.gpkg"
    gpd.GeoDataFrame(geometry=[line], crs="EPSG:32632").to_file(lines)
    out = tmp_path / "grade.parquet"
    result = sampling.elevation_profile(
        str(incline), str(lines), str(out), spacing=10.0, grade_base_length=100.0, **kwargs
    )
    return result, gpd.read_parquet(out)


def test_the_grade_along_a_track_is_not_the_slope_of_the_ground(incline, tmp_path):
    """The trap Fable named for the four railway requests: `slope` here is 2%
    everywhere, and a track crossing the incline at 45 degrees climbs 2*cos45."""
    result, points = _grade_run(
        incline, tmp_path, LineString([(100, 1000), (1100, 1000)]), grade_threshold_percent=1.5
    )
    grades = points["grade_percent"].dropna()
    assert len(grades) == len(points) - 10  # the last window-length of points has none
    assert list(grades) == pytest.approx([2.0] * len(grades))
    summary = result["grade"][0]
    assert summary["steepest_grade_percent"] == pytest.approx(2.0)
    assert summary["total_ascent"] == pytest.approx(20.0)
    assert summary["total_descent"] == pytest.approx(0.0)
    assert summary["stretches_above_threshold"] == [
        {"from": 0.0, "to": 1000.0, "direction": "up"}
    ]
    assert result["grade_units"] == {
        "base_length": "metre", "heights": "metre", "heights_assumed": True
    }

    diagonal = LineString([(100, 100), (800, 800)])
    result, points = _grade_run(incline, tmp_path, diagonal, grade_threshold_percent=1.5)
    assert list(points["grade_percent"].dropna()) == pytest.approx(
        [2.0 * np.cos(np.pi / 4)] * int(points["grade_percent"].notna().sum())
    )
    assert result["grade"][0]["stretches_above_threshold"] == []
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    assert record["parameters"]["grade_base_length"] == 100.0
    assert record["parameters"]["grade_window_steps"] == 10
    check = next(
        c for c in record["verification"]
        if c["name"] == "x-mapsmith:grades_follow_the_written_profile"
    )
    assert check["passed"] is True


def test_a_window_never_spans_the_gap_between_two_parts(incline, tmp_path):
    """Two north-south tracks 100 m long and 1000 m apart, stored as ONE
    MultiLineString on the eastward 2% plane. Both are level: 0% everywhere.
    Shapely measures the parts end to end, so before runs existed a 50 m window
    starting 60 m in reached across the gap and came back 40%, every check green."""
    from shapely.geometry import MultiLineString

    track = MultiLineString([[(500, 500), (500, 600)], [(1500, 500), (1500, 600)]])
    lines = tmp_path / "two_parts.gpkg"
    gpd.GeoDataFrame(geometry=[track], crs="EPSG:32632").to_file(lines)
    out = tmp_path / "parts.parquet"
    result = sampling.elevation_profile(
        str(incline), str(lines), str(out), spacing=10.0,
        grade_base_length=50.0, grade_threshold_percent=1.0,
    )
    points = gpd.read_parquet(out)
    assert points["run_index"].tolist() == [0] * 11 + [1] * 10
    assert list(points["grade_percent"].dropna()) == pytest.approx(
        [0.0] * int(points["grade_percent"].notna().sum())
    )
    summary = result["grade"][0]
    assert summary["runs"] == 2
    assert summary["steepest_grade_percent"] == pytest.approx(0.0)
    assert summary["stretches_above_threshold"] == []
    # And the rise between the parts is not an ascent: 20 m of it, none walked.
    assert summary["total_ascent"] == pytest.approx(0.0)
    check = next(
        c for c in _manifest(out)["verification"]
        if c["name"] == "x-mapsmith:grades_follow_the_written_profile"
    )
    assert check["passed"] is True
    assert check["detail"].startswith("11 grade(s)")  # 6 windows on the first run, 5 on the second


def test_a_climb_and_the_descent_after_it_are_two_stretches(incline, tmp_path):
    """East 500 m and back: +2% then -2%. One merged stretch [0, 1000] said
    neither which way nor that the crest was in the middle of it."""
    result, _ = _grade_run(
        incline, tmp_path, LineString([(100, 1000), (600, 1000), (100, 1000.001)]),
        grade_threshold_percent=1.5,
    )
    summary = result["grade"][0]
    directions = [s["direction"] for s in summary["stretches_above_threshold"]]
    assert directions == ["up", "down"]
    assert summary["total_ascent"] == pytest.approx(10.0)
    assert summary["total_descent"] == pytest.approx(10.0)


def test_a_window_over_an_unreadable_point_has_no_grade(tmp_path):
    """One nodata column across the path. The windows that contain it carry no
    grade rather than a rise between two readable ends -- and the summary says
    how many points it could not read instead of quietly summing around them."""
    path = tmp_path / "holed.tif"
    values = np.tile(0.02 * (np.arange(200, dtype="float32") * 10 + 5), (200, 1))
    values[:, 50] = -9999.0
    with rasterio.open(
        path, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0.0, 2000.0, 10.0, 10.0), nodata=-9999.0,
    ) as dst:
        dst.write(values, 1)
    result, points = _grade_run(path, tmp_path, LineString([(100, 1000), (1100, 1000)]))
    unreadable = points["value"].isna().to_numpy()
    assert unreadable.any()
    grades = points["grade_percent"].to_numpy()
    for start in range(len(points) - 10):
        if unreadable[start:start + 11].any():
            assert np.isnan(grades[start])
        else:
            assert grades[start] == pytest.approx(2.0)
    assert result["grade"][0]["unreadable_points"] == int(unreadable.sum())
    check = next(
        c for c in _manifest(tmp_path / "grade.parquet")["verification"]
        if c["name"] == "x-mapsmith:grades_follow_the_written_profile"
    )
    assert check["passed"] is True


@pytest.fixture
def incline_feet(tmp_path: Path) -> Path:
    """The same 2% plane in NY State Plane (US survey feet): z rises 0.02 per
    foot of easting -- in whatever unit the values are, which the file cannot say."""
    path = tmp_path / "incline_ft.tif"
    columns = np.arange(200, dtype="float32") * 10 + 5
    with rasterio.open(
        path, "w", driver="GTiff", height=200, width=200, count=1, dtype="float32",
        crs="EPSG:2263", transform=from_origin(980000.0, 202000.0, 10.0, 10.0),
    ) as dst:
        dst.write(np.tile(0.02 * columns, (200, 1)), 1)
    return path


def _feet_run(raster, tmp_path, **kwargs):
    lines = tmp_path / "track_ft.gpkg"
    gpd.GeoDataFrame(
        geometry=[LineString([(980100, 201000), (981100, 201000)])], crs="EPSG:2263"
    ).to_file(lines)
    out = tmp_path / "grade_ft.parquet"
    return sampling.elevation_profile(
        str(raster), str(lines), str(out), spacing=10.0, grade_base_length=100.0, **kwargs
    ), gpd.read_parquet(out)


def test_a_line_in_feet_needs_the_height_unit_said(incline_feet, tmp_path):
    """Heights in metres over a run in feet come out 3.28 times too steep, on
    every point, plausibly. Nothing in either file settles it, so the caller does."""
    with pytest.raises(ValueError, match="grade_height_unit"):
        _feet_run(incline_feet, tmp_path)
    result, points = _feet_run(incline_feet, tmp_path, grade_height_unit="US survey foot")
    assert list(points["grade_percent"].dropna()) == pytest.approx([2.0] * 91)
    assert result["grade_units"]["heights_assumed"] is False
    _, points = _feet_run(incline_feet, tmp_path, grade_height_unit="metre")
    # 0.2 m of rise over 10 US survey feet (3.048 m): 2% times 3937/1200.
    assert list(points["grade_percent"].dropna()) == pytest.approx([2.0 * 3937 / 1200] * 91)


@pytest.mark.parametrize("kwargs, match", [
    ({"grade_base_length": 105.0}, "not a whole number of spacing steps"),
    ({"grade_base_length": -1.0}, "positive finite"),
    ({"grade_threshold_percent": 2.5}, "needs grade_base_length"),
    ({"grade_base_length": 100.0, "grade_threshold_percent": -1.0}, "must not be negative"),
    ({"grade_base_length": 100.0, "grade_height_unit": "yard"}, "must be one of"),
    ({"grade_base_length": 100.0, "grade_threshold_percent": float("nan")}, "finite"),
    ({"grade_base_length": float("nan")}, "positive finite"),
    ({"grade_base_length": float("inf")}, "positive finite"),
])
def test_the_gradient_window_is_the_caller_s_and_must_fit_the_steps(incline, tmp_path, kwargs, match):
    lines = tmp_path / "t.gpkg"
    gpd.GeoDataFrame(geometry=[LineString([(100, 1000), (600, 1000)])], crs="EPSG:32632").to_file(lines)
    with pytest.raises(ValueError, match=match):
        sampling.elevation_profile(
            str(incline), str(lines), str(tmp_path / "x.parquet"), spacing=10.0, **kwargs
        )


@pytest.mark.parametrize("spacing", [float("nan"), float("inf"), 0.0, -1.0])
def test_a_spacing_that_is_not_a_positive_finite_length_is_refused(ramp, tmp_path, spacing):
    """NaN fails every comparison, so `spacing <= 0` let it through."""
    line = tmp_path / "l.gpkg"
    gpd.GeoDataFrame(geometry=[LineString([(2, 10), (10, 10)])], crs="EPSG:32632").to_file(line)
    with pytest.raises(ValueError, match="positive finite"):
        sampling.elevation_profile(str(ramp), str(line), str(tmp_path / "x.parquet"), spacing=spacing)


def test_a_profile_includes_both_ends_even_when_the_step_does_not_divide(ramp, tmp_path):
    """15 m at 4 m is three whole steps and a remainder. The far end still
    appears, as a last shorter step, because a profile that silently stops
    short of the summit is the worst kind of nearly-right. Until 2026-09-25
    this test had that docstring and asserted [0, 4, 8, 12]: it stopped short."""
    line = tmp_path / "odd.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[LineString([(2, 10), (17, 10)])], crs="EPSG:32632"
    ).to_file(line, layer="l", driver="GPKG")

    out = tmp_path / "odd.parquet"
    sampling.elevation_profile(str(ramp), str(line), str(out), spacing=4.0)
    got = gpd.read_parquet(out)
    assert got["distance"].tolist() == [0.0, 4.0, 8.0, 12.0, 15.0]
    assert got["value"].tolist() == pytest.approx([2.0, 6.0, 10.0, 14.0, 17.0])
    named = {c["name"]: c["passed"] for c in _manifest(out)["verification"]}
    assert named["x-mapsmith:each_profile_starts_at_zero_and_steps_by_the_spacing"] is True


def test_two_lines_profile_separately_and_say_which_is_which(ramp, tmp_path):
    line = tmp_path / "two.gpkg"
    gpd.GeoDataFrame(
        {"n": [1, 2]},
        geometry=[
            LineString([(2, 10), (10, 10)]),
            LineString([(2, 15), (6, 15)]),
        ],
        crs="EPSG:32632",
    ).to_file(line, layer="l", driver="GPKG")

    out = tmp_path / "two.parquet"
    result = sampling.elevation_profile(str(ramp), str(line), str(out), spacing=4.0)
    got = gpd.read_parquet(out)
    assert result["points"] == 5  # 3 on the first line, 2 on the second
    assert got["line_index"].tolist() == [0, 0, 0, 1, 1]
    assert got.groupby("line_index")["distance"].max().tolist() == [8.0, 4.0]


def test_a_geographic_line_is_refused_because_the_spacing_would_be_degrees(tmp_path):
    dem = tmp_path / "geo.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(11.0, 45.0, 0.01, 0.01),
    ) as dst:
        dst.write(np.ones((4, 4), dtype="float32"), 1)

    line = tmp_path / "geo.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[LineString([(11.001, 44.99), (11.02, 44.99)])],
        crs="EPSG:4326",
    ).to_file(line, layer="l", driver="GPKG")

    with pytest.raises(ValueError, match="degrees"):
        sampling.elevation_profile(
            str(dem), str(line), str(tmp_path / "x.parquet"), spacing=20.0
        )


# ------------------------------------------------------------- line of sight

@pytest.fixture
def ridge(tmp_path: Path) -> Path:
    """Flat ground at 0 with a single 100 m ridge in the middle column.

    100 cells of 10 m from x=0 to x=1000; the ridge is the column whose centre
    is at x=505. An observer at x=5 and a target at x=995 are 990 m apart with
    the ridge exactly halfway, so a sight line between two points at ground
    level is blocked and one from 200 m up at both ends is not.
    """
    path = tmp_path / "ridge.tif"
    values = np.zeros((3, 100), dtype="float32")
    values[:, 50] = 100.0
    with rasterio.open(
        path, "w", driver="GTiff", height=3, width=100, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 30, 10, 10),
    ) as dst:
        dst.write(values, 1)
    return path


def test_a_ridge_blocks_the_view_and_the_answer_says_where(ridge):
    result = sampling.line_of_sight(
        str(ridge), 5, 15, 995, 15, earth_curvature=False
    )
    assert result["visible"] is False
    assert result["first_obstruction_at"] == pytest.approx(490.0, abs=15.0), (
        "the ridge centre is 500 m from the observer; the obstruction should "
        "start where the ground first rises above the line"
    )
    assert result["minimum_clearance"] < 0


def test_enough_height_clears_the_same_ridge(ridge):
    result = sampling.line_of_sight(
        str(ridge), 5, 15, 995, 15, earth_curvature=False,
        observer_height=200.0, target_height=200.0,
    )
    assert result["visible"] is True
    assert result["minimum_clearance"] == pytest.approx(100.0, abs=1.0)


def test_curvature_lowers_the_sight_line_by_the_sagitta(tmp_path):
    """Closed form: over a 20 km chord the mid-line drop is
    (1 - 0.13) * d * (L - d) / 2R = 0.87 * 10000 * 10000 / (2 * 6371008.8) ≈ 6.83 m.

    Flat ground at 6 m is under a level sight line without curvature and above
    it with curvature, which is the whole point of making the caller state it.
    """
    flat = tmp_path / "flat.tif"
    values = np.zeros((3, 200), dtype="float32")
    values[:, 100] = 6.0
    with rasterio.open(
        flat, "w", driver="GTiff", height=3, width=200, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 300, 100, 100),
    ) as dst:
        dst.write(values, 1)

    common = {"observer_height": 10.0, "target_height": 10.0}
    without = sampling.line_of_sight(
        str(flat), 50, 150, 19950, 150, earth_curvature=False, **common
    )
    with_curve = sampling.line_of_sight(
        str(flat), 50, 150, 19950, 150, earth_curvature=True, **common
    )
    assert without["visible"] is True
    assert with_curve["visible"] is False, (
        "a 6.8 m drop over 20 km did not move a 6 m obstacle above a 10 m sight "
        "line, so the curvature correction is not being applied"
    )
    assert with_curve["refraction_coefficient"] == 0.13
    drop = without["minimum_clearance"] - with_curve["minimum_clearance"]
    assert drop == pytest.approx(6.83, abs=0.15)


def test_the_curvature_question_has_to_be_answered(ridge):
    with pytest.raises(TypeError):
        sampling.line_of_sight(str(ridge), 5, 15, 995, 15)  # type: ignore[call-arg]


def test_an_observer_off_the_raster_is_refused_rather_than_assumed_to_be_at_zero(ridge):
    with pytest.raises(ValueError, match="outside the raster"):
        sampling.line_of_sight(
            str(ridge), -500, 15, 995, 15, earth_curvature=False
        )


def test_a_geographic_raster_is_refused_for_a_sight_line(tmp_path):
    dem = tmp_path / "geo.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(11.0, 45.0, 0.01, 0.01),
    ) as dst:
        dst.write(np.zeros((4, 4), dtype="float32"), 1)
    with pytest.raises(ValueError, match="geographic"):
        sampling.line_of_sight(
            str(dem), 11.005, 44.995, 11.025, 44.995, earth_curvature=False
        )


def test_the_outer_half_cell_is_readable_and_outside_the_extent_is_not(grid, tmp_path):
    """Two different "outside", and conflating them made the boundary unreadable.

    A position inside the raster's extent but within the outer half-cell has a
    value; its bilinear stencil simply has no outer neighbour, so the stencil is
    clamped to the edge cell — what GDAL does. A position beyond the extent has
    no value at all. The first version refused both, and a sight line to a
    target 5 m from the edge came back "outside the raster".
    """
    points = tmp_path / "edges.gpkg"
    gpd.GeoDataFrame(
        {"where": ["inside the outer half-cell", "beyond the extent"]},
        geometry=[Point(1, 99), Point(-1, 99)],
        crs="EPSG:32632",
    ).to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "edges.parquet"
    result = sampling.sample_raster_at_points(
        str(grid), str(points), str(out), "bilinear"
    )
    got = gpd.read_parquet(out)["value"].tolist()
    assert got[0] == pytest.approx(0.0), (
        "a point inside the extent came back null because its interpolation "
        "window poked over the edge"
    )
    assert got[1] is None or np.isnan(got[1])
    assert result["unreadable"] == 1


def test_a_ridge_hidden_in_a_nodata_gap_withholds_the_verdict(tmp_path):
    """The wrong answer this cost: `visible: True` over a 100 m ridge.

    The first version skipped unreadable samples and reported nothing, so a
    ridge buried in a nodata hole produced a confident yes. The module's own
    docstring promises that every operation here counts what it could not read,
    and this is the one that answers yes-or-no rather than returning a table —
    so it is where a silent null costs the most.
    """
    path = tmp_path / "holed_ridge.tif"
    values = np.zeros((3, 100), dtype="float32")
    values[:, 45:56] = -9999.0        # a nodata gap
    values[:, 50] = -9999.0           # with a 100 m ridge inside it, unreadable
    with rasterio.open(
        path, "w", driver="GTiff", height=3, width=100, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 30, 10, 10), nodata=-9999.0,
    ) as dst:
        dst.write(values, 1)

    result = sampling.line_of_sight(str(path), 5, 15, 995, 15, earth_curvature=False)
    assert result["unreadable_samples"] > 5
    assert result["verdict_withheld"] is True
    assert result["visible"] is None, (
        "a sight line with a tenth of its profile missing came back with a "
        "yes-or-no answer"
    )


def test_a_couple_of_missing_samples_do_not_withhold_the_verdict(ridge):
    """The threshold is a twentieth, not zero: refusing to answer whenever a
    single cell is nodata would make the operation useless on real DEMs, which
    have holes."""
    result = sampling.line_of_sight(
        str(ridge), 5, 15, 995, 15, earth_curvature=False
    )
    assert result["verdict_withheld"] is False
    assert result["visible"] is False
    assert result["unreadable_samples"] == 0


def test_a_nodata_corner_with_no_weight_does_not_lose_an_exact_value(tmp_path):
    """The loss this module exists to prevent, in the opposite direction.

    A point on a cell centre has three of its four bilinear corners at weight
    zero. Checking the nodata mask before the weight threw the sample away when
    any of those three happened to be nodata — returning None for a position
    whose value was sitting right there, and inflating the very counter the
    unreadable check reads.
    """
    path = tmp_path / "corner.tif"
    values = np.full((3, 3), 5.0, dtype="float32")
    values[1, 1] = -9999.0
    with rasterio.open(
        path, "w", driver="GTiff", height=3, width=3, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 30, 10, 10), nodata=-9999.0,
    ) as dst:
        dst.write(values, 1)

    # Centre of cell (0,0): (5, 25). Its bilinear window reaches (1,1), the
    # nodata cell, at weight exactly zero.
    points = tmp_path / "on_centre.gpkg"
    gpd.GeoDataFrame(
        {"n": [1]}, geometry=[Point(5, 25)], crs="EPSG:32632"
    ).to_file(points, layer="p", driver="GPKG")

    out = tmp_path / "corner.parquet"
    result = sampling.sample_raster_at_points(
        str(path), str(points), str(out), "bilinear"
    )
    assert result["unreadable"] == 0, "an exact value was discarded"
    assert gpd.read_parquet(out)["value"].tolist() == pytest.approx([5.0])
