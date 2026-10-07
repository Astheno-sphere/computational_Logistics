"""Two defects Argleton found on 2026-08-30, on the fixtures that found them.

Trap 026 asked how steep a plane is, on a DEM whose rows run south to north.
MapSmith answered 45 degrees where the truth is 5.71, wrote the output raster at
the origin with metre cells, and passed all five of its own checks — because the
CRS survived and nothing compared the output's grid with the input's.

Trap 027 asked how many metres of pipe are in a layer that also holds a
treatment plant. MapSmith answered 3000 where the pipe is 2000, adding the
plant's perimeter, with nothing in the manifest to say a second kind of feature
had been measured.

Both are here as the trap saw them: same shapes, same numbers, same questions.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("whitebox_workflows")

from affine import Affine

from mapsmith.engines import vector, whitebox_engine

WEST, SOUTH, CELL, SIZE = 500000.0, 4500000.0, 10.0, 40

#: The plane rises 1 m per cell eastwards on 10 m cells, so it slopes at
#: atan(1/10) everywhere. Read with the cell size lost — 1 m instead of 10 — it
#: slopes at atan(1/1), which is 45 degrees.
TRUE_SLOPE = math.degrees(math.atan(1 / 10))
LOST_CELL_SLOPE = math.degrees(math.atan(1 / 1))


def plane(tmp_path: Path, south_up: bool) -> str:
    surface = np.array(
        [[100.0 + 1.0 * column for column in range(SIZE)] for _ in range(SIZE)],
        dtype="float32",
    )
    transform = (
        Affine(CELL, 0.0, WEST, 0.0, CELL, SOUTH)
        if south_up
        else Affine(CELL, 0.0, WEST, 0.0, -CELL, SOUTH + SIZE * CELL)
    )
    path = tmp_path / f"plane_{'south' if south_up else 'north'}.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1,
        dtype="float32", crs="EPSG:32633", transform=transform,
    ) as dst:
        dst.write(surface, 1)
    return str(path)


def manifest_of(result: dict) -> dict:
    return json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))


# --- the south-up grid ------------------------------------------------------


def test_a_south_up_dem_gives_the_slope_of_the_ground(tmp_path):
    """5.7 degrees, not 45.

    The engine cannot express a positive fifth element of the geotransform and
    does not say so: it discards the georeferencing and reads unit cells at the
    origin. A slope is a rise over a run, and a run ten times too short makes
    the site eight times steeper.
    """
    out = tmp_path / "slope.tif"
    whitebox_engine.slope(plane(tmp_path, south_up=True), str(out))

    with rasterio.open(out) as src:
        values = src.read(1, masked=True)
    median = float(np.ma.median(values))
    assert median == pytest.approx(TRUE_SLOPE, abs=1e-3), (
        f"the slope came back {median:.4f} where the ground is {TRUE_SLOPE:.4f}; "
        f"{LOST_CELL_SLOPE} would mean the cell size was lost again"
    )


def test_the_output_is_georeferenced_where_the_input_was(tmp_path):
    """The half of the defect no check was looking at.

    The slope raster used to come back with `c=0.0, a=1.0` — the origin, at a
    tenth of the site's size — carrying the input's correct EPSG code on top of
    it. `crs_matches` passed precisely because the error was not in the CRS.
    """
    out = tmp_path / "slope.tif"
    whitebox_engine.slope(plane(tmp_path, south_up=True), str(out))

    with rasterio.open(out) as src:
        assert src.transform.c == pytest.approx(WEST)
        assert abs(src.transform.a) == pytest.approx(CELL)
        assert src.transform.e < 0, "the output should be north-up whatever went in"


def test_the_rewrite_is_disclosed_in_the_manifest(tmp_path):
    """MapSmith hands the engine a different file, so it has to say so.

    The same disclosure the TIFF-predictor workaround makes. A manifest that
    does not mention the rewrite describes an operation on a file that was never
    read.
    """
    out = tmp_path / "slope.tif"
    result = whitebox_engine.slope(plane(tmp_path, south_up=True), str(out))
    notes = " ".join(manifest_of(result)["notes"])
    assert "south-up" in notes


def test_a_north_up_dem_is_untouched(tmp_path):
    """The other half of Argleton's pair, and the guard against over-correcting.

    A fix that flipped every raster would answer this one upside down. On a
    plane tilted east that is invisible in the slope, which is why the transform
    is asserted rather than the number.
    """
    source = plane(tmp_path, south_up=False)
    out = tmp_path / "slope.tif"
    result = whitebox_engine.slope(source, str(out))

    with rasterio.open(out) as src:
        median = float(np.ma.median(src.read(1, masked=True)))
        assert src.transform.c == pytest.approx(WEST)
        assert src.transform.e == pytest.approx(-CELL)
    assert median == pytest.approx(TRUE_SLOPE, abs=1e-3)
    assert "south-up" not in " ".join(manifest_of(result)["notes"])


def test_a_grid_the_engine_reads_differently_is_refused(tmp_path, monkeypatch):
    """The general guard, not the specific workaround.

    The known cause is handled by rewriting the input. This is what happens if
    a future version of the engine diverges some other way: the operation stops
    instead of producing a number carrying a correct-looking CRS. Simulated by
    disabling the rewrite, which is the only way to reach the guard now.
    """
    monkeypatch.setattr(whitebox_engine, "_needs_plain_copy", lambda path: None)
    with pytest.raises(ValueError, match="read .* as a grid of"):
        whitebox_engine.slope(
            plane(tmp_path, south_up=True), str(tmp_path / "slope.tif")
        )


# --- the mixed layer --------------------------------------------------------


def network(tmp_path: Path, with_plant: bool) -> str:
    import geopandas as gpd
    from shapely.geometry import LineString, Polygon

    rows = [
        {"asset_id": f"P-{n:02d}", "geometry": LineString(points)}
        for n, points in enumerate(
            [
                [(500000, 4500000), (500600, 4500000)],
                [(500600, 4500000), (500600, 4500400)],
                [(500600, 4500400), (500850, 4500400)],
                [(500000, 4500000), (500000, 4500250)],
                [(500000, 4500250), (500500, 4500250)],
            ],
            start=1,
        )
    ]
    if with_plant:
        rows.append(
            {
                "asset_id": "WTP-1",
                "geometry": Polygon(
                    [
                        (500850, 4500400),
                        (501150, 4500400),
                        (501150, 4500600),
                        (500850, 4500600),
                        (500850, 4500400),
                    ]
                ),
            }
        )
    path = tmp_path / f"network_{'mixed' if with_plant else 'lines'}.parquet"
    gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:32633").to_parquet(path)
    return str(path)


def test_measuring_a_mixed_layer_says_that_is_what_happened(tmp_path):
    """2000 m of pipe plus a 1000 m fence line, and the manifest says so.

    The total is not refused: measuring a mixed layer is a legitimate thing to
    ask for and MapSmith cannot know which features the question was about. What
    it must not do is let the number arrive without the sentence.
    """
    out = tmp_path / "measured.parquet"
    result = vector.measure_length(network(tmp_path, True), str(out), method="planar")
    assert result["total_length_m"] == pytest.approx(3000.0), (
        "2000 m of pipe plus the plant's 1000 m perimeter; the number itself is "
        "not the defect, its arriving unannounced is"
    )

    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    mixed = checks["x-mapsmith:one_geometry_type_in_the_layer"]
    assert mixed["passed"] is False
    assert mixed["critical"] is False
    assert "Polygon" in mixed["detail"] and "LineString" in mixed["detail"]
    assert "perimeter" in mixed["hint"]


def test_a_layer_of_one_kind_passes_the_check(tmp_path):
    out = tmp_path / "measured.parquet"
    result = vector.measure_length(network(tmp_path, False), str(out), method="planar")
    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    assert checks["x-mapsmith:one_geometry_type_in_the_layer"]["passed"] is True


def test_measure_area_asks_the_same_question(tmp_path):
    """A line's area is zero, which is true and is not an answer to add up.

    `area_is_measurable` already reported how many features were polygonal, and
    it PASSED as soon as one of them was — with the count buried in its detail.
    A total over two kinds of feature gets a check that fails.
    """
    out = tmp_path / "areas.parquet"
    result = vector.measure_area(network(tmp_path, True), str(out))
    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    assert checks["x-mapsmith:one_geometry_type_in_the_layer"]["passed"] is False


def test_multi_and_single_of_one_kind_are_one_kind(tmp_path):
    """A layer of LineString and MultiLineString is not mixed in the sense that
    matters: both are lines, both answer the same question, and flagging them
    would make the check noise on ordinary data."""
    import geopandas as gpd
    from shapely.geometry import LineString, MultiLineString

    path = tmp_path / "multi.parquet"
    gpd.GeoDataFrame(
        [
            {"id": 1, "geometry": LineString([(0, 0), (100, 0)])},
            {
                "id": 2,
                "geometry": MultiLineString(
                    [[(0, 10), (50, 10)], [(60, 10), (100, 10)]]
                ),
            },
        ],
        geometry="geometry",
        crs="EPSG:32633",
    ).to_parquet(path)

    out = tmp_path / "measured.parquet"
    result = vector.measure_length(str(path), str(out), method="planar")
    checks = {c["name"]: c for c in manifest_of(result)["verification"]}
    assert checks["x-mapsmith:one_geometry_type_in_the_layer"]["passed"] is True
