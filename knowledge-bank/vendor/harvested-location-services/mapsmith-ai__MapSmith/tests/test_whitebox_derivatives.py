"""Curvature, flow direction, Euclidean distance and IDW: closed-form values.

Every expected number here is derivable by hand from the fixture, which is the
only kind of expectation that can fail for the right reason. The pointer-table
test is the important one: it does not check that the manifest CARRIES a table,
it checks that the table the manifest carries is the one the raster uses.
"""

import json
import math
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point

pytest.importorskip("whitebox_workflows")
rasterio = pytest.importorskip("rasterio")

import numpy as np
from rasterio.transform import from_origin

from mapsmith.engines import whitebox_engine as engine


def _write(path, data, *, crs="EPSG:32632", resolution=10.0):
    height, width = data.shape
    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype="float32", crs=crs, nodata=-9999.0,
        transform=from_origin(500000.0, 4500000.0, resolution, resolution),
    ) as dst:
        dst.write(data.astype("float32"), 1)
    return str(path)


def _read(path):
    with rasterio.open(path) as src:
        return src.read(1, masked=True)


def _manifest(result):
    return json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))


def _checks(result):
    return {c["name"]: c["passed"] for c in _manifest(result)["verification"]}


@pytest.fixture
def plane(tmp_path):
    """z = column * 10 on a 10 m grid: a plane of unit gradient rising eastward.

    Closed form on such a surface: curvature is exactly zero, and the downslope
    direction is due west in every cell. The outermost two rings are clamped
    windows and only approximate, so the assertions read the interior.
    """
    return _write(tmp_path / "plane.tif", np.fromfunction(lambda r, c: c * 10.0, (8, 8)))


# --------------------------------------------------------------- curvature


def test_curvature_of_a_plane_is_exactly_zero(plane, tmp_path):
    out = str(tmp_path / "curv.tif")
    engine.curvature(plane, out, kind="profile")
    interior = _read(out)[2:-2, 2:-2]
    assert float(np.abs(interior).max()) == 0.0


def test_every_curvature_kind_runs_and_is_recorded(plane, tmp_path):
    for kind, tool in engine.CURVATURE_KINDS.items():
        result = engine.curvature(plane, str(tmp_path / f"c-{kind}.tif"), kind=kind)
        parameters = _manifest(result)["parameters"]
        assert parameters["kind"] == kind
        # The tool name too, not only the kind: 'plan' and 'tangential' are one
        # rename apart upstream, and the manifest should say which ran.
        assert parameters["tool"] == tool


def test_curvature_refuses_an_unknown_kind_and_names_the_valid_ones(plane, tmp_path):
    with pytest.raises(ValueError, match="kind must be one of"):
        engine.curvature(plane, str(tmp_path / "x.tif"), kind="planar")


def test_curvature_refuses_a_geographic_dem(tmp_path):
    dem = _write(
        tmp_path / "geo.tif",
        np.fromfunction(lambda r, c: c * 10.0, (8, 8)),
        crs="EPSG:4326",
        resolution=0.001,
    )
    with pytest.raises(ValueError, match="geographic CRS"):
        engine.curvature(dem, str(tmp_path / "x.tif"), kind="profile")


# ---------------------------------------------------------- flow_direction

# Measured one direction at a time on whitebox-workflows 2.0.6 and asserted here
# so a library upgrade that changes the table fails loudly instead of mirroring
# every drainage network the day it lands.
_NEIGHBOURS = {
    "east": (0, 1), "northeast": (-1, 1), "north": (-1, 0), "northwest": (-1, -1),
    "west": (0, -1), "southwest": (1, -1), "south": (1, 0), "southeast": (1, 1),
}


@pytest.mark.parametrize("encoding", sorted(engine.POINTER_ENCODINGS))
def test_the_pointer_table_in_the_manifest_is_the_table_the_raster_uses(
    encoding, tmp_path
):
    """One low neighbour, so the code at the centre names it and nothing else.

    This is the check the operation exists for. A test that asserted the
    manifest CONTAINS a direction table would pass on a table that describes a
    different engine — which is exactly the failure mode, since nothing in a
    GeoTIFF says which convention it holds.
    """
    table = engine.POINTER_ENCODINGS[encoding]
    for direction, (dr, dc) in _NEIGHBOURS.items():
        grid = np.full((5, 5), 200.0)
        grid[2, 2] = 100.0
        grid[2 + dr, 2 + dc] = 0.0
        dem = _write(tmp_path / f"{encoding}-{direction}.tif", grid)
        out = str(tmp_path / f"{encoding}-{direction}-d8.tif")
        result = engine.flow_direction(dem, out, method="d8", encoding=encoding)
        code = int(_read(out)[2, 2])
        declared = _manifest(result)["parameters"]["direction_codes"]
        assert code == declared[direction], (
            f"{encoding}: the cell flows {direction} and holds {code}, while the "
            f"manifest says {direction} is {declared[direction]}"
        )
        assert declared == table


def test_the_two_encodings_produce_different_rasters(plane, tmp_path):
    """Otherwise `encoding` would be a parameter that records a choice it did
    not make — the manifest would be true about nothing."""
    first = str(tmp_path / "ne.tif")
    second = str(tmp_path / "e.tif")
    engine.flow_direction(plane, first, method="d8", encoding="northeast_first")
    engine.flow_direction(plane, second, method="d8", encoding="east_first")
    assert not np.array_equal(_read(first), _read(second))
    # And each says west with its own code: 32 clockwise-from-northeast, 16
    # clockwise-from-east.
    assert set(np.unique(_read(first)[1:-1, 1:-1].compressed())) == {32}
    assert set(np.unique(_read(second)[1:-1, 1:-1].compressed())) == {16}


def test_pointer_codes_are_verified_as_a_set_not_a_range(plane, tmp_path):
    result = engine.flow_direction(plane, str(tmp_path / "d8.tif"), method="d8")
    assert _checks(result)["values_in_expected_range"] is True
    detail = next(
        c["detail"] for c in _manifest(result)["verification"]
        if c["name"] == "values_in_expected_range"
    )
    assert "powers of two" in detail


@pytest.mark.parametrize("method", sorted(engine.FLOW_DIRECTION_METHODS))
def test_every_flow_direction_method_runs(method, plane, tmp_path):
    result = engine.flow_direction(plane, str(tmp_path / f"fd-{method}.tif"), method=method)
    parameters = _manifest(result)["parameters"]
    assert parameters["method"] == method
    # dinf and fd8 write continuous values: a direction table would be a lie.
    assert ("direction_codes" in parameters) == (method in ("d8", "rho8"))


def test_an_encoding_is_refused_where_there_is_no_table(plane, tmp_path):
    with pytest.raises(ValueError, match="meaningless for method"):
        engine.flow_direction(
            plane, str(tmp_path / "x.tif"), method="dinf", encoding="east_first"
        )


# ------------------------------------------------------ euclidean_distance


def test_euclidean_distance_from_one_source_cell_is_closed_form(tmp_path):
    grid = np.zeros((5, 5))
    grid[2, 2] = 1.0
    source = _write(tmp_path / "mask.tif", grid)
    out = str(tmp_path / "dist.tif")
    result = engine.euclidean_distance(source, out)
    values = _read(out)
    assert float(values[2, 2]) == 0.0
    assert float(values[2, 0]) == pytest.approx(20.0)
    assert float(values[0, 0]) == pytest.approx(math.hypot(20.0, 20.0))
    assert _checks(result)["values_in_expected_range"] is True


def test_euclidean_distance_refuses_a_geographic_crs(tmp_path):
    grid = np.zeros((5, 5))
    grid[2, 2] = 1.0
    source = _write(tmp_path / "geo.tif", grid, crs="EPSG:4326", resolution=0.001)
    with pytest.raises(ValueError, match="not a length"):
        engine.euclidean_distance(source, str(tmp_path / "x.tif"))


# ------------------------------------------------------ idw_interpolation


@pytest.fixture
def four_equal_points(tmp_path):
    path = tmp_path / "points.parquet"
    gpd.GeoDataFrame(
        {"height": [7.0, 7.0, 7.0, 7.0]},
        geometry=[Point(0, 0), Point(100, 0), Point(0, 100), Point(100, 100)],
        crs="EPSG:32632",
    ).to_parquet(path)
    return str(path)


def test_idw_of_equal_values_is_that_value_everywhere(four_equal_points, tmp_path):
    """Closed form regardless of the weighting: a weighted mean of identical
    values is the value, so any deviation is the interpolation misbehaving."""
    out = str(tmp_path / "idw.tif")
    result = engine.idw_interpolation(
        four_equal_points, out, field_name="height", cell_size=10.0
    )
    values = _read(out)
    assert float(values.min()) == pytest.approx(7.0)
    assert float(values.max()) == pytest.approx(7.0)
    parameters = _manifest(result)["parameters"]
    # The exponent travels with the surface: an IDW raster without it cannot be
    # reproduced, and 2 versus 3 is a visibly different map.
    assert parameters["weight"] == 2.0
    assert parameters["field_name"] == "height"
    assert parameters["cell_size"] == 10.0


def test_idw_requires_the_field_because_the_library_default_is_row_numbers(
    four_equal_points, tmp_path
):
    with pytest.raises(ValueError, match="field_name is required"):
        engine.idw_interpolation(
            four_equal_points, str(tmp_path / "x.tif"), field_name="", cell_size=10.0
        )


def test_idw_refuses_a_non_positive_cell_size(four_equal_points, tmp_path):
    with pytest.raises(ValueError, match="cell_size must be positive"):
        engine.idw_interpolation(
            four_equal_points, str(tmp_path / "x.tif"), field_name="height", cell_size=0.0
        )


# ------------------------------------------------------------------ viewshed

def test_the_viewshed_counts_stations_and_does_not_flag_them(tmp_path):
    """The tool's own documentation says the opposite, so this is measured.

    Whitebox's help for Viewshed states "the output image will be a Boolean
    raster, containing 1's and 0's". On flat ground with two stations, every
    cell here comes back 2.0 — the classic source calls `increment`, not
    `set_value`. A caller who summed the raster expecting a visible area would
    be out by a factor of the station count, and nothing would raise.

    This test is the reason that claim is safe to put in a docstring: if a
    future version really does turn the output into a flag, this fails.
    """
    pytest.importorskip("whitebox_workflows")
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import Point

    dem = tmp_path / "flat.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=21, width=21, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 210, 10, 10),
    ) as dst:
        dst.write(np.zeros((21, 21), dtype="float32"), 1)

    stations = tmp_path / "stations.gpkg"
    gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=[Point(55, 105), Point(155, 105)],
        crs="EPSG:32632",
    ).to_file(stations, layer="s", driver="GPKG")

    out = tmp_path / "seen.tif"
    result = engine.viewshed(
        str(dem), str(stations), str(out), station_height=2.0
    )
    assert result["stations"] == 2

    with rasterio.open(out) as ds:
        values = ds.read(1, masked=True)
    assert float(values.max()) == 2.0, (
        "two stations on flat ground see every cell, so a count says 2 and a "
        "boolean says 1 — this is the measurement the docstring rests on"
    )

    manifest = json.loads((tmp_path / "seen.tif.provenance.json").read_text(encoding="utf-8"))
    assert manifest["parameters"]["output_meaning"].startswith("number of stations")
    assert any("NUMBER of stations" in note for note in manifest["notes"])


def test_the_station_height_unit_is_stated_because_it_is_not_metres(tmp_path):
    """`station_height` is in the DEM's Z unit. On a DEM in feet, 2.0 is two
    feet, and an eye height of 0.6 m would be a silent error with a
    plausible-looking viewshed to show for it."""
    pytest.importorskip("whitebox_workflows")
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin
    from shapely.geometry import Point

    dem = tmp_path / "flat.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=5, width=5, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 50, 10, 10),
    ) as dst:
        dst.write(np.zeros((5, 5), dtype="float32"), 1)
    stations = tmp_path / "s.gpkg"
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(25, 25)], crs="EPSG:32632"
    ).to_file(stations, layer="s", driver="GPKG")

    out = tmp_path / "one.tif"
    engine.viewshed(str(dem), str(stations), str(out), station_height=1.7)
    manifest = json.loads((tmp_path / "one.tif.provenance.json").read_text(encoding="utf-8"))
    assert manifest["parameters"]["height_unit"].startswith("the DEM's Z unit")
    assert manifest["parameters"]["station_height"] == 1.7


def test_a_viewshed_with_no_stations_is_refused_not_answered_with_zeros(tmp_path):
    pytest.importorskip("whitebox_workflows")
    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    dem = tmp_path / "flat.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=5, width=5, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 50, 10, 10),
    ) as dst:
        dst.write(np.zeros((5, 5), dtype="float32"), 1)
    empty = tmp_path / "none.gpkg"
    gpd.GeoDataFrame(
        {"id": []}, geometry=gpd.GeoSeries([], dtype="geometry"), crs="EPSG:32632"
    ).to_file(empty, layer="s", driver="GPKG")

    with pytest.raises(ValueError, match="nothing to see from"):
        engine.viewshed(
            str(dem), str(empty), str(tmp_path / "x.tif"), station_height=2.0
        )


def test_confusing_the_two_pointer_tables_rotates_the_network_by_one_step():
    """The reason the manifest carries the table and not its name.

    Both conventions are clockwise and use the same set of codes -- the powers
    of two from 1 to 128 -- one position apart. So a consumer that reads a
    pointer raster under the wrong table gets a legal direction in every cell
    and a drainage network rotated 45 degrees, uniformly, in one turn. Nothing
    raises, the set check in the engine passes, and a rotated network still
    looks like a drainage network.

    Closed form, and it holds the comment above POINTER_ENCODINGS honest: until
    2026-09-22 that comment said the two tables "agree on no direction at all"
    and that reading one as the other mirrors the network about the NE-SW axis.
    Both followed from a table attributed to the WhiteboxTools manual that the
    manual does not contain -- `d8_pointer.rs` documents the engine's default
    exactly as the engine writes it. This test is what that paragraph now rests
    on, so a future edit that reintroduces the mirror claim fails here.
    """
    clockwise = [
        "north", "northeast", "east", "southeast",
        "south", "southwest", "west", "northwest",
    ]
    ne_first = engine.POINTER_ENCODINGS["northeast_first"]
    e_first = engine.POINTER_ENCODINGS["east_first"]

    assert set(ne_first.values()) == set(e_first.values()), (
        "the two tables no longer share a code set, so a wrong reading would be "
        "detectable by the set check and this whole argument changes"
    )

    for index, direction in enumerate(clockwise):
        code = ne_first[direction]
        read_as = next(k for k, v in e_first.items() if v == code)
        expected = clockwise[(index + 1) % len(clockwise)]
        assert read_as == expected, (
            f"a cell flowing {direction} holds {code}; read with the other table "
            f"that is {read_as}, and one step clockwise from {direction} is "
            f"{expected} -- the rotation is no longer uniform"
        )
