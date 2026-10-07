"""Voronoi cells: equal quarters from a square, and each cell on its own point.

The join test is the one that matters. Shapely's default order is not the input
order — measured here, 0 of 5 cells land on their own point — so a positional
pairing produces a layer that is correct in shape and wrong in every value.
"""

import json
from pathlib import Path

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import Point

from mapsmith.engines import vector

CRS = "EPSG:32632"


def _manifest(result):
    return json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))


def _checks(result):
    return {c["name"]: c["passed"] for c in _manifest(result)["verification"]}


@pytest.fixture
def square_corners(tmp_path):
    """The four corners of a 100x100 square: each cell is exactly one quarter."""
    path = tmp_path / "corners.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a", "b", "c", "d"], "value": [1, 2, 3, 4]},
        geometry=[Point(0, 0), Point(100, 0), Point(0, 100), Point(100, 100)],
        crs=CRS,
    ).to_file(path, driver="GPKG")
    return str(path)


def test_shapely_default_order_is_not_the_input_order():
    """The reason `ordered=True` is not an optimisation.

    Not "sometimes wrong": on this input the default puts ZERO of five cells on
    their own point. Any code that zips shapely's default output with the input
    rows is wrong every time, and the output looks entirely reasonable.
    """
    points = shapely.MultiPoint([(0, 0), (100, 0), (0, 100), (100, 100), (50, 50)])
    parts = list(shapely.get_parts(points))
    unordered = list(shapely.get_parts(shapely.voronoi_polygons(points, ordered=False)))
    ordered = list(shapely.get_parts(shapely.voronoi_polygons(points, ordered=True)))
    assert sum(c.covers(p) for c, p in zip(unordered, parts)) == 0
    assert sum(c.covers(p) for c, p in zip(ordered, parts)) == 5


def test_four_corners_give_four_equal_quarters(square_corners, tmp_path):
    out = tmp_path / "vor.parquet"
    result = vector.voronoi_polygons(square_corners, str(out))
    cells = gpd.read_parquet(out)
    assert sorted(round(float(a), 6) for a in cells.geometry.area) == [2500.0] * 4
    assert result["total_area"] == pytest.approx(10000.0)
    assert result["cell_count"] == 4


def test_every_cell_carries_the_attributes_of_the_point_inside_it(
    square_corners, tmp_path
):
    out = tmp_path / "vor.parquet"
    result = vector.voronoi_polygons(square_corners, str(out))
    assert _checks(result)["x-mapsmith:each_cell_holds_its_own_point"] is True
    cells = gpd.read_parquet(out)
    original = gpd.read_file(square_corners)
    for _, row in cells.iterrows():
        point = original.loc[original["name"] == row["name"], "geometry"].iloc[0]
        assert row.geometry.covers(point), f"cell {row['name']} does not hold its point"
    assert set(cells["value"]) == {1, 2, 3, 4}


def test_the_boundary_choice_is_recorded_because_it_decides_the_outer_areas(
    square_corners, tmp_path
):
    result = vector.voronoi_polygons(
        square_corners, str(tmp_path / "hull.parquet"), boundary="convex_hull"
    )
    manifest = _manifest(result)
    assert manifest["parameters"]["boundary"] == "convex_hull"
    note = " ".join(manifest["notes"])
    assert "convex_hull" in note
    assert "not of the points" in note


def test_the_margin_expands_the_boundary_by_a_computable_amount(
    square_corners, tmp_path
):
    """0.5 of the larger side on each side: 100 becomes 200, so 10000 becomes
    40000. A closed form for a parameter that would otherwise be a feeling."""
    result = vector.voronoi_polygons(
        square_corners, str(tmp_path / "wide.parquet"), margin_fraction=0.5
    )
    assert result["total_area"] == pytest.approx((100 + 2 * 50) ** 2)


def test_polygons_are_refused_rather_than_reduced_to_their_vertices(tmp_path):
    path = tmp_path / "polys.gpkg"
    gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 10, 10)], crs=CRS).to_file(
        path, driver="GPKG"
    )
    with pytest.raises(ValueError, match="needs a point layer"):
        vector.voronoi_polygons(str(path), str(tmp_path / "x.parquet"))


def test_one_point_is_refused_because_there_is_no_boundary_to_draw(tmp_path):
    path = tmp_path / "one.gpkg"
    gpd.GeoDataFrame(geometry=[Point(0, 0)], crs=CRS).to_file(path, driver="GPKG")
    with pytest.raises(ValueError, match="at least 2 distinct points"):
        vector.voronoi_polygons(str(path), str(tmp_path / "x.parquet"))


def test_a_layer_without_a_crs_is_refused(tmp_path):
    path = tmp_path / "nocrs.parquet"
    gpd.GeoDataFrame(geometry=[Point(0, 0), Point(1, 1)]).to_parquet(path)
    with pytest.raises(ValueError, match="has no CRS"):
        vector.voronoi_polygons(str(path), str(tmp_path / "x.parquet"))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"boundary": "circle"}, "boundary must be one of"),
        ({"margin_fraction": -0.1}, "cannot be negative"),
    ],
)
def test_bad_arguments_are_refused(kwargs, message, square_corners, tmp_path):
    with pytest.raises(ValueError, match=message):
        vector.voronoi_polygons(square_corners, str(tmp_path / "x.parquet"), **kwargs)


def test_the_cells_are_built_in_the_layers_own_crs(square_corners, tmp_path):
    """Equidistance is a property of the plane it is measured in, so a diagram
    built after reprojection has different edges. The manifest says so."""
    result = vector.voronoi_polygons(square_corners, str(tmp_path / "vor.parquet"))
    decisions = _manifest(result)["crs_decisions"]
    assert decisions["analysis_crs"] == CRS
    assert "reprojection" in decisions["reason"]


def test_duplicate_points_are_refused_with_a_message_and_not_a_geos_exception(tmp_path):
    """Two sensors at one address is an ordinary layer, not a corner case.

    The precondition said "at least 2 distinct points" and only ever counted
    them, so a repeated coordinate reached GEOS and came back as
    `Multiple input coordinates in cell at 0 0` — an untranslated engine error
    from an operation whose every other refusal explains itself. They are
    refused rather than de-duplicated on purpose: which row should own the cell
    is the caller's question, since the attributes differ even when the
    geometry does not.
    """
    import geopandas as gpd
    import pytest
    from shapely.geometry import Point

    from mapsmith.engines import vector

    layer = tmp_path / "twins.gpkg"
    gpd.GeoDataFrame(
        {"sensor": ["a", "b", "c"]},
        geometry=[Point(0, 0), Point(0, 0), Point(10, 10)],
        crs="EPSG:32632",
    ).to_file(layer, layer="twins", driver="GPKG")

    with pytest.raises(ValueError) as raised:
        vector.voronoi_polygons(str(layer), str(tmp_path / "cells.parquet"))

    message = str(raised.value)
    assert "DISTINCT" in message and "(0.0, 0.0)" in message, (
        "the refusal does not name the repeated coordinate, so the caller has to "
        f"go and find it: {message}"
    )
    assert "Multiple input coordinates" in message, (
        "the message does not quote the engine error it is replacing, so somebody "
        "searching for that string will not land here"
    )
