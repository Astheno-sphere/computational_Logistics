"""Routing, on a network whose answers are arithmetic.

The fixture is a grid of 100 m streets, so every route length is a multiple of
100 and can be counted on paper. The interesting tests are not the routes: they
are the two ways a network analysis lies quietly — a graph that is secretly in
pieces because two endpoints missed each other by a millimetre, and an origin
that snapped somewhere else entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from mapsmith.engines import network


def _write(lines, tmp_path: Path, name: str, extra: dict | None = None) -> Path:
    path = tmp_path / f"{name}.gpkg"
    data = extra or {}
    data.setdefault("id", list(range(len(lines))))
    gpd.GeoDataFrame(data, geometry=lines, crs="EPSG:32632").to_file(
        path, layer="net", driver="GPKG"
    )
    return path


@pytest.fixture
def grid_streets(tmp_path: Path) -> Path:
    """A 3x3 lattice of junctions, 100 m apart: 12 segments, all connected.

    Junction (i, j) sits at (i*100, j*100). From (0,0) to (200,200) the cheapest
    route is 400 m, and there are several of them — which is why the tie-break
    has to be deterministic.
    """
    lines = []
    for i in range(3):
        for j in range(3):
            if i < 2:
                lines.append(LineString([(i * 100, j * 100), ((i + 1) * 100, j * 100)]))
            if j < 2:
                lines.append(LineString([(i * 100, j * 100), (i * 100, (j + 1) * 100)]))
    return _write(lines, tmp_path, "grid")


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def _named(output: Path) -> dict:
    return {c["name"]: c for c in _manifest(output)["verification"]}


def test_the_shortest_route_across_the_lattice_is_four_hundred_metres(
    grid_streets, tmp_path
):
    out = tmp_path / "route.parquet"
    result = network.network_shortest_path(
        str(grid_streets), str(out), 0, 0, 200, 200, tolerance=0.01
    )
    assert result["total_cost"] == pytest.approx(400.0)
    assert result["segments"] == 4
    assert result["components"] == 1
    assert result["junctions"] == 9

    route = gpd.read_parquet(out)
    assert route["cumulative_cost"].tolist() == pytest.approx([100.0, 200.0, 300.0, 400.0])
    assert route["step"].tolist() == [1, 2, 3, 4]
    assert _named(out)["x-mapsmith:segment_costs_add_up_to_the_route_cost"]["passed"]


def test_the_same_call_twice_gives_the_same_route(grid_streets, tmp_path):
    """Several routes cost 400 m. A path that changes between runs cannot be put
    in a manifest, so the tie-break is by node index and this says so."""
    first = tmp_path / "a.parquet"
    second = tmp_path / "b.parquet"
    for out in (first, second):
        network.network_shortest_path(
            str(grid_streets), str(out), 0, 0, 200, 200, tolerance=0.01
        )
    assert (
        gpd.read_parquet(first)["id"].tolist()
        == gpd.read_parquet(second)["id"].tolist()
    )


def test_a_cost_field_replaces_length_and_the_route_follows_it(tmp_path):
    """Two ways round a block: the short one in metres is the slow one in minutes.

    Straight from A to C is 200 m in two hops; the detour is 300 m in three. With
    length as the cost the direct way wins; with a minutes column where the
    direct hops are congested, the detour wins. If the cost field were ignored
    the answer would still look like a route.
    """
    lines = [
        LineString([(0, 0), (100, 0)]),      # 0: direct, congested
        LineString([(100, 0), (200, 0)]),    # 1: direct, congested
        LineString([(0, 0), (0, 100)]),      # 2: detour
        LineString([(0, 100), (200, 100)]),  # 3: detour
        LineString([(200, 100), (200, 0)]),  # 4: detour
    ]
    path = _write(lines, tmp_path, "costed", {"minutes": [10.0, 10.0, 1.0, 2.0, 1.0]})

    by_length = tmp_path / "by_length.parquet"
    result = network.network_shortest_path(
        str(path), str(by_length), 0, 0, 200, 0, tolerance=0.01
    )
    assert result["total_cost"] == pytest.approx(200.0)
    assert gpd.read_parquet(by_length)["id"].tolist() == [0, 1]

    by_time = tmp_path / "by_time.parquet"
    result = network.network_shortest_path(
        str(path), str(by_time), 0, 0, 200, 0, tolerance=0.01, cost_field="minutes"
    )
    assert result["total_cost"] == pytest.approx(4.0)
    assert gpd.read_parquet(by_time)["id"].tolist() == [2, 3, 4]


def test_a_millimetre_gap_disconnects_the_network_and_the_manifest_says_so(tmp_path):
    """The failure this module is built around.

    Two streets that miss each other by 1 mm are one junction on the ground and
    two nodes in the graph. At tolerance 0 the route is impossible; at tolerance
    0.01 it is 200 m. Nothing about the data changed.
    """
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(100.001, 0), (200, 0)]),
    ]
    path = _write(lines, tmp_path, "gapped")

    with pytest.raises(ValueError, match="different part of the network"):
        network.network_shortest_path(
            str(path), str(tmp_path / "x.parquet"), 0, 0, 200, 0, tolerance=0.0
        )

    out = tmp_path / "joined.parquet"
    result = network.network_shortest_path(
        str(path), str(out), 0, 0, 200, 0, tolerance=0.01
    )
    assert result["total_cost"] == pytest.approx(199.999)
    assert result["components"] == 1

    checks = _named(out)
    assert checks["x-mapsmith:network_is_one_connected_piece"]["passed"] is True
    # The merged-endpoint count lives in `parameters`, beside the tolerance that
    # produced it. It used to be a check whose predicate was the constant True —
    # a counter wearing a check's name, which cannot fail and inflates the passed
    # count of every network manifest.
    # Two counters, because they measure two different things: what the data
    # already agreed on, and what the tolerance pulled together. One counter for
    # both reported "15 endpoints merged at tolerance 0.0" on a perfectly noded
    # lattice — at a tolerance where nothing can be welded.
    assert _manifest(out)["parameters"]["welded_by_tolerance"] == 1
    assert _manifest(out)["parameters"]["coincident_endpoints"] == 0
    assert _manifest(out)["parameters"]["junctions"] == 3


def test_a_disconnected_network_is_reported_even_when_the_route_succeeds(tmp_path):
    """An island elsewhere in the layer does not stop this route — and is still
    worth knowing about, because it means some destinations are unreachable by
    construction rather than by distance."""
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(100, 0), (200, 0)]),
        LineString([(900, 900), (1000, 900)]),  # an island
    ]
    path = _write(lines, tmp_path, "island")
    out = tmp_path / "island.parquet"
    result = network.network_shortest_path(
        str(path), str(out), 0, 0, 200, 0, tolerance=0.01
    )
    assert result["total_cost"] == pytest.approx(200.0)
    assert result["components"] == 2
    check = _named(out)["x-mapsmith:network_is_one_connected_piece"]
    assert check["passed"] is False and check["critical"] is False


def test_an_origin_far_from_the_network_is_reported_rather_than_absorbed(
    grid_streets, tmp_path
):
    """Snapping is the point; snapping four kilometres is a different analysis."""
    out = tmp_path / "far.parquet"
    result = network.network_shortest_path(
        str(grid_streets), str(out), -4000, 0, 200, 200, tolerance=0.01
    )
    assert result["origin_snap_distance"] == pytest.approx(4000.0)
    check = _named(out)["x-mapsmith:origin_is_close_to_the_network"]
    assert check["passed"] is False
    assert check["critical"] is False


def test_a_negative_cost_is_refused_instead_of_answered_confidently(tmp_path):
    """Dijkstra is only correct on non-negative costs. With one negative edge it
    does not fail — it returns a wrong answer that looks like a route."""
    lines = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])]
    path = _write(lines, tmp_path, "neg", {"weight": [1.0, -5.0]})
    with pytest.raises(ValueError, match="non-negative"):
        network.network_shortest_path(
            str(path), str(tmp_path / "x.parquet"), 0, 0, 200, 0,
            tolerance=0.01, cost_field="weight",
        )


def test_a_missing_cost_is_refused_rather_than_treated_as_free(tmp_path):
    lines = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])]
    path = _write(lines, tmp_path, "holes", {"weight": [1.0, None]})
    with pytest.raises(ValueError, match="no value in the cost field"):
        network.network_shortest_path(
            str(path), str(tmp_path / "x.parquet"), 0, 0, 200, 0,
            tolerance=0.01, cost_field="weight",
        )


def test_length_costs_on_a_geographic_network_are_refused(tmp_path):
    path = tmp_path / "geo.gpkg"
    gpd.GeoDataFrame(
        {"id": [0]}, geometry=[LineString([(11.0, 45.0), (11.01, 45.0)])],
        crs="EPSG:4326",
    ).to_file(path, layer="net", driver="GPKG")
    with pytest.raises(ValueError, match="DEGREES"):
        network.network_shortest_path(
            str(path), str(tmp_path / "x.parquet"), 11.0, 45.0, 11.01, 45.0,
            tolerance=0.0001,
        )


# ----------------------------------------------------------- service area

def test_a_budget_of_one_hundred_and_fifty_cuts_the_second_segment_in_half(tmp_path):
    """Closed form: a straight 100 m + 100 m corridor, budget 150.

    The first segment fits whole. The second is entered with 50 left, so half of
    it is reachable: the output holds one whole segment and one 50 m piece
    marked partial. Including the second segment whole would overstate the reach
    by 50 m; dropping it would understate by the same.
    """
    lines = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])]
    path = _write(lines, tmp_path, "corridor")
    out = tmp_path / "area.parquet"

    result = network.service_area(
        str(path), str(out), 0, 0, budget=150.0, tolerance=0.01
    )
    got = gpd.read_parquet(out)
    assert result["segments"] == 2
    assert result["partial_segments"] == 1
    assert sorted(got.geometry.length.round(6).tolist()) == pytest.approx([50.0, 100.0])
    assert got["cost_at_end"].max() == pytest.approx(150.0)
    assert _named(out)["x-mapsmith:nothing_exceeds_the_budget"]["passed"] is True


def test_the_service_area_stops_at_the_gap_a_buffer_would_cross(tmp_path):
    """Why this is not a buffer.

    A house 120 m along the road is out of reach on a 100 m budget; a house 60 m
    away across a river with no bridge is out of reach at any budget. A circle
    gets both wrong in opposite directions.
    """
    lines = [
        LineString([(0, 0), (200, 0)]),        # the road
        LineString([(0, 60), (200, 60)]),      # the far bank, no bridge
    ]
    path = _write(lines, tmp_path, "riverside")
    out = tmp_path / "bank.parquet"
    result = network.service_area(
        str(path), str(out), 0, 0, budget=1000.0, tolerance=0.01
    )
    got = gpd.read_parquet(out)
    assert result["components"] == 2
    assert got["line_index"].tolist() == [0], (
        "the far bank is 60 m away in a straight line and unreachable on this "
        "network; a buffer would have included it"
    )


def test_a_whole_reachable_edge_appears_once_not_twice(tmp_path):
    """An undirected edge is walkable from both ends. Emitting it once per
    direction doubles the length of the service area, which is the sort of
    number that gets published."""
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(100, 0), (200, 0)]),
        LineString([(0, 0), (200, 0)]),
    ]
    path = _write(lines, tmp_path, "loop")
    out = tmp_path / "loop.parquet"
    network.service_area(str(path), str(out), 0, 0, budget=1000.0, tolerance=0.01)
    got = gpd.read_parquet(out)
    assert sorted(got["line_index"].tolist()) == [0, 1, 2]


def test_the_budget_has_to_be_positive(grid_streets, tmp_path):
    with pytest.raises(ValueError, match="budget must be positive"):
        network.service_area(
            str(grid_streets), str(tmp_path / "x.parquet"), 0, 0,
            budget=0.0, tolerance=0.01,
        )


def test_the_snap_check_declines_to_judge_a_distance_in_degrees(tmp_path):
    """A threshold of 50 applied to a number in degrees passes 1,600 km.

    A geographic network reaches the snap check only when a `cost_field` was
    given — length-based costs are refused in degrees — which is exactly the
    case a unit-blind threshold gets wrong. It used to pass an origin 19.8
    degrees away, because 19.8 is less than 50, and print the number with no
    unit so a human could not judge it either.
    """
    path = tmp_path / "geo.gpkg"
    gpd.GeoDataFrame(
        {"id": [0, 1], "minutes": [1.0, 1.0]},
        geometry=[
            LineString([(11.0, 45.0), (11.01, 45.0)]),
            LineString([(11.01, 45.0), (11.02, 45.0)]),
        ],
        crs="EPSG:4326",
    ).to_file(path, layer="net", driver="GPKG")

    out = tmp_path / "geo_route.parquet"
    result = network.network_shortest_path(
        str(path), str(out), -8.8, 45.0, 11.02, 45.0,
        tolerance=0.0001, cost_field="minutes",
    )
    assert result["origin_snap_distance"] > 19
    check = _named(out)["x-mapsmith:origin_is_close_to_the_network"]
    assert "degree" in check["detail"], (
        "the distance is printed without its unit, so neither the threshold nor "
        "a human reader can judge it"
    )
    assert "not judged" in check["detail"], (
        "a distance in degrees was compared against a threshold in metres and "
        "the check reported a pass"
    )


def test_a_projected_snap_distance_still_carries_its_unit(grid_streets, tmp_path):
    out = tmp_path / "unit.parquet"
    network.network_shortest_path(
        str(grid_streets), str(out), -4000, 0, 200, 200, tolerance=0.01
    )
    detail = _named(out)["x-mapsmith:origin_is_close_to_the_network"]["detail"]
    assert "metre" in detail, f"no unit in {detail!r}"


def test_an_edge_reachable_from_both_ends_is_not_counted_twice(tmp_path):
    """The number that gets published, and the way it was inflated.

    A triangle: the origin reaches both ends of the far edge, so walking it from
    each end independently emitted two overlapping pieces. Measured before the
    fix: 8.0 metres of segments over an edge whose union is 6.83 — and
    `nothing_exceeds_the_budget` passed, because each piece did respect the
    budget on its own. "How many metres of road are within ten minutes" is
    exactly the number computed from this output.
    """
    from shapely import union_all

    lines = [
        LineString([(0, 0), (2, 0)]),
        LineString([(0, 0), (0, 2)]),
        LineString([(2, 0), (0, 2)]),
    ]
    path = _write(lines, tmp_path, "triangle")
    out = tmp_path / "triangle.parquet"
    network.service_area(str(path), str(out), 0, 0, budget=4.0, tolerance=0.01)

    got = gpd.read_parquet(out)
    total = got.geometry.length.sum()
    on_the_ground = union_all(list(got.geometry)).length
    assert total == pytest.approx(on_the_ground, abs=1e-9), (
        f"{total:.4f} m of segments over {on_the_ground:.4f} m of ground"
    )
    assert _named(out)["x-mapsmith:no_edge_is_emitted_over_itself_twice"]["passed"]


def test_two_stubs_appear_when_the_budget_cannot_bridge_the_gap(tmp_path):
    """The other half of the same decision: when the two reaches do NOT meet,
    the edge really is walkable from both ends and the output is two disjoint
    pieces with an unreachable middle. Emitting the whole edge there would
    overstate the reach in the opposite direction."""
    from shapely import union_all

    lines = [
        LineString([(0, 0), (10, 0)]),
        LineString([(0, 0), (0, 10)]),
        LineString([(10, 0), (0, 10)]),   # about 14.14 long
    ]
    path = _write(lines, tmp_path, "gap")
    out = tmp_path / "gap.parquet"
    result = network.service_area(
        str(path), str(out), 0, 0, budget=14.0, tolerance=0.01
    )
    got = gpd.read_parquet(out)
    on_the_far_edge = got[got["line_index"] == 2]
    assert len(on_the_far_edge) == 2, "the unreachable middle was bridged"
    assert result["partial_segments"] >= 2
    assert got.geometry.length.sum() == pytest.approx(
        union_all(list(got.geometry)).length, abs=1e-9
    )


def test_overlapping_input_geometries_are_not_called_an_error(tmp_path):
    """A bridge over the road beneath it is two edges on the same ground.

    The first version of the overlap check compared the total emitted length
    against the union of everything, and called that network wrong: three
    correct edges summed to 400 metres over 200 metres of ground. The property
    that matters is narrower — no single edge emitted twice over itself — and
    the difference is a real network the check would have rejected.
    """
    lines = [
        LineString([(0, 0), (100, 0)]),
        LineString([(100, 0), (200, 0)]),
        LineString([(0, 0), (200, 0)]),   # the shortcut, lying on both
    ]
    path = _write(lines, tmp_path, "bridge")
    out = tmp_path / "bridge.parquet"
    network.service_area(str(path), str(out), 0, 0, budget=1000.0, tolerance=0.01)

    check = _named(out)["x-mapsmith:no_edge_is_emitted_over_itself_twice"]
    assert check["passed"] is True, check["detail"]
    assert sorted(gpd.read_parquet(out)["line_index"].tolist()) == [0, 1, 2]


def test_a_cost_column_whose_name_is_not_an_identifier_still_works(tmp_path):
    """`"travel time"` is an ordinary column name in a shapefile or an OSM export.

    `itertuples()` renames anything that is not a Python identifier, so the
    column-exists check passed and the engine then died on
    `AttributeError: 'Pandas' object has no attribute 'travel time'` — an
    untranslated pandas error for a perfectly valid input.
    """
    lines = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])]
    path = _write(lines, tmp_path, "spacey", {"travel time": [1.0, 2.0]})
    out = tmp_path / "spacey.parquet"
    result = network.network_shortest_path(
        str(path), str(out), 0, 0, 200, 0, tolerance=0.01, cost_field="travel time"
    )
    assert result["total_cost"] == pytest.approx(3.0)


def test_the_osm_convention_for_one_way_does_not_make_everything_one_way(tmp_path):
    """`bool("no")` is True.

    A layer using the OSM convention — where `oneway = "no"` means two-way —
    came out entirely directed, every reverse route failed, and the error blamed
    the tolerance and told the caller to widen it. That is the module's OTHER
    declared trap, so the diagnosis actively pointed at the wrong repair.
    """
    lines = [LineString([(0, 0), (100, 0)]), LineString([(100, 0), (200, 0)])]
    path = _write(lines, tmp_path, "osm", {"oneway": ["no", "no"]})
    out = tmp_path / "osm.parquet"
    result = network.network_shortest_path(
        str(path), str(out), 200, 0, 0, 0, tolerance=0.01, oneway_field="oneway"
    )
    assert result["total_cost"] == pytest.approx(200.0), (
        "routing against the line order failed on a layer that says it is two-way"
    )


def test_a_one_way_value_nobody_understands_is_refused_not_guessed(tmp_path):
    lines = [LineString([(0, 0), (100, 0)])]
    path = _write(lines, tmp_path, "odd", {"oneway": ["reversible"]})
    with pytest.raises(ValueError, match="neither true nor false"):
        network.network_shortest_path(
            str(path), str(tmp_path / "x.parquet"), 0, 0, 100, 0,
            tolerance=0.01, oneway_field="oneway",
        )
