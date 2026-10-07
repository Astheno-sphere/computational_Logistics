"""Contours and least-cost routes, on surfaces whose answer is arithmetic.

The contour fixture is a plane: `z = column index` on a 10 m grid whose origin
is (1000, 5000). The cell holding value 3 has its centre at x = 1035, so the
3-contour of that surface is the vertical line x = 1035, exactly. That single
number is the test — and it is also the number the engine got wrong, by half a
cell, until it was measured.

The cost fixture is uniform. Nine steps of 1 m across cells that all cost 1
comes to 9, and no implementation detail can make it anything else.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point

pytest.importorskip("whitebox_workflows")
rasterio = pytest.importorskip("rasterio")

from rasterio.transform import from_origin

from mapsmith.engines import network, whitebox_engine

CELL = 10.0
WEST = 1000.0
NORTH = 5000.0


@pytest.fixture
def ramp(tmp_path):
    """z = column index, 12x12 cells of 10 m, origin (1000, 5000).

    Column c holds the value c and its centre is at x = 1000 + (c + 0.5)·10.
    So the contour for height h is the vertical line x = 1000 + (h + 0.5)·10:
    h=0 at 1005, h=3 at 1035, h=6 at 1065, h=9 at 1095.
    """
    size = 12
    values = np.tile(np.arange(size, dtype="float32"), (size, 1))
    path = tmp_path / "ramp.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=size, width=size, count=1,
        dtype="float32", crs="EPSG:32632",
        transform=from_origin(WEST, NORTH, CELL, CELL),
    ) as dst:
        dst.write(values, 1)
    return str(path)


def manifest_of(result: dict) -> dict:
    return json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))


def test_a_contour_sits_on_the_cell_centre_that_holds_its_value(ramp, tmp_path):
    """The half-cell correction, pinned to a number worked out on paper.

    Whitebox returns these vertices at x = 1030 for the 3-contour: the WEST EDGE
    of the column holding 3, not its centre. On a 30 m DEM that is 15 m of
    horizontal error on every contour, plausible and invisible. If this test
    starts failing by exactly half a cell, the library changed its registration
    and `CONTOUR_REGISTRATION_SHIFT` is now doing harm.
    """
    out = tmp_path / "contours.parquet"
    result = whitebox_engine.contour_lines(ramp, str(out), interval=3.0)

    lines = gpd.read_parquet(out)
    assert set(lines["elevation"]) == {0.0, 3.0, 6.0, 9.0}
    for height in (0.0, 3.0, 6.0, 9.0):
        line = lines[lines["elevation"] == height].geometry.iloc[0]
        xs = {round(x, 6) for x, _ in line.coords}
        assert xs == {WEST + (height + 0.5) * CELL}, (
            f"the {height} contour is at {xs}, not at the centre of the column "
            f"holding {height}"
        )
    assert result["contours"] == 4


def test_the_dem_read_back_at_a_vertex_is_the_contour_height(ramp, tmp_path):
    """The check that looks at the NUMBER, not at the shape of the output.

    Seven checks passed on this project's first Argleton run and none of them
    asked whether the answer was right. This is that check, for contours: sample
    the surface where the line says it is and the elevation must match.
    """
    out = tmp_path / "contours.parquet"
    result = whitebox_engine.contour_lines(ramp, str(out), interval=3.0)

    assert result["largest_disagreement_with_the_dem"] < 1e-6
    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    verdict = checks["x-mapsmith:the_dem_at_a_contour_vertex_is_the_contour_height"]
    assert verdict["passed"] and verdict["critical"] is True


def test_smoothing_is_off_by_default_and_declares_itself_when_on(ramp, tmp_path):
    """A drawing and a measurement are different products.

    With smoothing the vertices are moved to look better, so the check above
    stops being critical and the manifest says the contours are a drawing. The
    default is off, which is not the library's default.
    """
    plain = whitebox_engine.contour_lines(
        ramp, str(tmp_path / "plain.parquet"), interval=3.0
    )
    assert plain["smoothing_filter_size"] == 0

    smoothed = whitebox_engine.contour_lines(
        ramp, str(tmp_path / "smooth.parquet"), interval=3.0, smoothing=5
    )
    notes = " ".join(manifest_of(smoothed)["notes"])
    assert "drawing, not" in notes
    checks = {c["name"]: c for c in manifest_of(smoothed)["verification"]}
    assert (
        checks["x-mapsmith:the_dem_at_a_contour_vertex_is_the_contour_height"][
            "critical"
        ]
        is False
    )


def test_the_base_shifts_the_whole_series(ramp, tmp_path):
    """base=1 with interval=3 gives 1, 4, 7, 10 — not 0, 3, 6, 9."""
    out = tmp_path / "based.parquet"
    result = whitebox_engine.contour_lines(ramp, str(out), interval=3.0, base=1.0)
    assert set(result["levels"]) <= {1.0, 4.0, 7.0, 10.0}
    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    assert checks["x-mapsmith:every_contour_sits_on_the_requested_interval"]["passed"]


def test_a_series_that_misses_the_surface_is_refused_with_the_reason(ramp, tmp_path):
    """base=100, interval=1000: the levels are 100, 1100, ... and the surface
    spans 0 to 11. An empty layer written as a success is a map of nothing."""
    with pytest.raises(ValueError, match="no contour crosses"):
        whitebox_engine.contour_lines(
            ramp, str(tmp_path / "none.parquet"), interval=1000.0, base=100.0
        )


def test_a_geographic_dem_is_refused(tmp_path):
    path = tmp_path / "deg.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=8, width=8, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_origin(9.0, 45.0, 0.001, 0.001),
    ) as dst:
        dst.write(np.tile(np.arange(8, dtype="float32"), (8, 1)), 1)
    with pytest.raises(ValueError, match="geographic CRS"):
        whitebox_engine.contour_lines(str(path), str(tmp_path / "o.parquet"), 1.0)


# --- least_cost_path -------------------------------------------------------


def cost_raster(tmp_path, values, name="cost.tif", nodata=None):
    path = tmp_path / name
    with rasterio.open(
        path, "w", driver="GTiff", height=values.shape[0], width=values.shape[1],
        count=1, dtype="float32", crs="EPSG:32632",
        transform=from_origin(0, values.shape[0], 1, 1),
        **({"nodata": nodata} if nodata is not None else {}),
    ) as dst:
        dst.write(values.astype("float32"), 1)
    return str(path)


def point_layer(tmp_path, name, x, y):
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(x, y)], crs="EPSG:32632")
    path = tmp_path / f"{name}.parquet"
    gdf.to_parquet(path)
    return str(path)


def test_a_uniform_surface_costs_the_distance_walked(tmp_path):
    """Nine 1 m steps across cells that all cost 1: the total is 9, exactly.

    Cost is charged per unit of DISTANCE, not per cell — the difference this
    fixture pins. An implementation charging one unit per cell would also answer
    9 here, which is why the diagonal test below exists.
    """
    cost = cost_raster(tmp_path, np.ones((10, 10)))
    start = point_layer(tmp_path, "start", 0.5, 9.5)
    end = point_layer(tmp_path, "end", 9.5, 9.5)
    out = tmp_path / "route.parquet"

    result = network.least_cost_path(cost, start, end, str(out))
    assert result["cells"] == 10
    assert result["total_cost"] == pytest.approx(9.0)
    assert result["path_length"] == pytest.approx(9.0)
    assert result["straight_line"] == pytest.approx(9.0)


def test_a_diagonal_step_costs_root_two_and_not_one(tmp_path):
    """Corner to corner of a 1 m grid: three diagonal steps, 3·√2 ≈ 4.2426.

    An implementation charging per cell would answer 3, and its route would look
    identical on a map. This is the arithmetic that separates them.
    """
    cost = cost_raster(tmp_path, np.ones((4, 4)))
    start = point_layer(tmp_path, "start", 0.5, 3.5)
    end = point_layer(tmp_path, "end", 3.5, 0.5)
    out = tmp_path / "diagonal.parquet"

    result = network.least_cost_path(cost, start, end, str(out))
    assert result["total_cost"] == pytest.approx(3 * 2**0.5, abs=1e-9)
    assert result["cells"] == 4


def test_a_wall_makes_the_route_go_round_and_the_detour_shows(tmp_path):
    """A costly column with a gap: the cheapest route uses the gap."""
    # Row 0 is the TOP of this raster (origin is its north edge), so the gap is
    # at y = 8.5 while both endpoints sit on the bottom row at y = 0.5. The
    # cheapest route has to climb to the gap and come back down.
    values = np.ones((9, 9))
    values[:, 4] = 500.0
    values[0, 4] = 1.0
    cost = cost_raster(tmp_path, values)
    start = point_layer(tmp_path, "start", 0.5, 0.5)
    end = point_layer(tmp_path, "end", 8.5, 0.5)
    out = tmp_path / "around.parquet"

    result = network.least_cost_path(cost, start, end, str(out))
    assert result["detour_ratio"] > 1.5
    crossing = [p for p in gpd.read_parquet(out).geometry.iloc[0].coords if p[0] == 4.5]
    assert crossing and all(y > 7.0 for _, y in crossing), (
        "the route crossed the wall somewhere other than the gap"
    )


def test_a_uniform_surface_is_flagged_as_having_avoided_nothing(tmp_path):
    """The commonest mistake: feeding in the DEM instead of a penalty surface.

    The map looks identical either way, so it is a check rather than a comment.
    Not critical — a uniform surface can be deliberate.
    """
    cost = cost_raster(tmp_path, np.ones((10, 10)))
    start = point_layer(tmp_path, "start", 0.5, 9.5)
    end = point_layer(tmp_path, "end", 9.5, 9.5)
    result = network.least_cost_path(
        cost, start, end, str(tmp_path / "flat.parquet")
    )
    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    avoided = checks["x-mapsmith:the_route_actually_avoided_something"]
    assert avoided["passed"] is False and avoided["critical"] is False


def test_zero_and_negative_costs_are_refused_with_the_reason(tmp_path):
    values = np.ones((6, 6))
    values[2, 2] = 0.0
    cost = cost_raster(tmp_path, values)
    start = point_layer(tmp_path, "start", 0.5, 5.5)
    end = point_layer(tmp_path, "end", 5.5, 0.5)
    with pytest.raises(ValueError, match="free"):
        network.least_cost_path(cost, start, end, str(tmp_path / "o.parquet"))


def test_nodata_is_impassable_and_a_severed_route_says_so(tmp_path):
    """A full column of nodata: there is no route, and that is not a zero-cost one."""
    values = np.ones((7, 7))
    values[:, 3] = -9999.0
    cost = cost_raster(tmp_path, values, nodata=-9999.0)
    start = point_layer(tmp_path, "start", 0.5, 6.5)
    end = point_layer(tmp_path, "end", 6.5, 6.5)
    with pytest.raises(ValueError, match="no route exists"):
        network.least_cost_path(cost, start, end, str(tmp_path / "o.parquet"))


def test_a_point_outside_the_surface_is_refused(tmp_path):
    cost = cost_raster(tmp_path, np.ones((5, 5)))
    start = point_layer(tmp_path, "start", 0.5, 4.5)
    end = point_layer(tmp_path, "end", 500.0, 500.0)
    with pytest.raises(ValueError, match="outside the cost surface"):
        network.least_cost_path(cost, start, end, str(tmp_path / "o.parquet"))


def test_two_start_points_are_two_questions(tmp_path):
    cost = cost_raster(tmp_path, np.ones((5, 5)))
    many = gpd.GeoDataFrame(
        {"id": [1, 2]}, geometry=[Point(0.5, 4.5), Point(1.5, 4.5)], crs="EPSG:32632"
    )
    start = tmp_path / "two.parquet"
    many.to_parquet(start)
    end = point_layer(tmp_path, "end", 4.5, 0.5)
    with pytest.raises(ValueError, match="exactly one point"):
        network.least_cost_path(cost, str(start), end, str(tmp_path / "o.parquet"))


def test_a_start_holding_a_line_beside_its_point_is_refused(tmp_path):
    """One point and one line used to pass as "one point", the line ignored."""
    cost = cost_raster(tmp_path, np.ones((5, 5)))
    mixed = gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[LineString([(0.5, 0.5), (4.5, 4.5)]), Point(0.5, 4.5)],
        crs="EPSG:32632",
    )
    start = tmp_path / "mixed.parquet"
    mixed.to_parquet(start)
    end = point_layer(tmp_path, "end", 4.5, 0.5)
    with pytest.raises(ValueError, match=r"\['LineString'\] geometries"):
        network.least_cost_path(cost, str(start), end, str(tmp_path / "o.parquet"))


def test_a_reprojected_start_is_the_point_itself(tmp_path):
    """The endpoint in another CRS lands where it is.

    A pin, not a catch: the old code reprojected the whole layer and re-read
    feature 0, which was right for a one-point layer and wrong only for the
    mixed layer the test above now refuses. It reprojects the point itself
    now, and this holds that path. A start given in WGS 84 at the centre of cell (row 0, column 0) of a UTM
    surface: the route begins in that cell. The 4326 coordinates are the
    exact inverse of (0.5, 4.5) in EPSG:32632, computed by the same PROJ.
    """
    from pyproj import Transformer

    cost = cost_raster(tmp_path, np.ones((5, 5)))
    lon, lat = Transformer.from_crs(32632, 4326, always_xy=True).transform(0.5, 4.5)
    wgs = gpd.GeoDataFrame({"id": [1]}, geometry=[Point(lon, lat)], crs="EPSG:4326")
    start = tmp_path / "start_wgs.parquet"
    wgs.to_parquet(start)
    end = point_layer(tmp_path, "end", 4.5, 4.5)
    result = network.least_cost_path(cost, str(start), end, str(tmp_path / "o.parquet"))
    assert result["cells"] == 5
    assert result["total_cost"] == pytest.approx(4.0)

