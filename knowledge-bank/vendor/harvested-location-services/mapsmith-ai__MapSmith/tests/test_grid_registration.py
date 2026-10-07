"""Where a raster's values are, on the fixture that proved we did not know.

Argleton trap 024 plants a DEM that declares `AREA_OR_POINT=Point` and asks where
its lowest value is. The fixtures here are the trap's, rebuilt: the same 8x8
surface at 30 m spacing with a strict minimum at row 2, column 3, written once as
`Point` and once as `Area`.

**The answer is the same on both, and this file said otherwise until
2026-09-25 (D-096).** The trap's builder claimed GDAL "leaves the geotransform
alone" for a PixelIsPoint file. It does not: since RFC 33 GDAL shifts the stored
tie point half a cell on write and back on read, so its geotransform is always
area-oriented and the sample of cell (r, c) is at the centre of GDAL's cell. The
file written below with `from_origin(412000, ...)` and the Point tag stores its
first sample at 412015 -- and the lowest one at 412105, the answer this file
used to call the failure.

The oracle is the file's own statement, not GDAL and not MapSmith: the raw tie
point, read with `GTIFF_POINT_GEO_IGNORE=TRUE`, which under PixelIsPoint is the
position of the first sample (GeoTIFF 1.0, section 2.5.2.2).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from rasterio.transform import from_origin

from mapsmith import grid
from mapsmith.engines import raster, sampling

EAST0, NORTH0, SPACING, SIZE = 412000.0, 5108000.0, 30.0, 8
LOW_ROW, LOW_COLUMN = 2, 3

#: Where the lowest sample is: the centre of GDAL's cell (2, 3), on both files.
SAMPLE = (EAST0 + (LOW_COLUMN + 0.5) * SPACING, NORTH0 - (LOW_ROW + 0.5) * SPACING)
#: Where MapSmith and the trap put it until 2026-09-25: GDAL's correction made
#: a second time, half a cell north-west of the sample.
TWICE_CORRECTED = (EAST0 + LOW_COLUMN * SPACING, NORTH0 - LOW_ROW * SPACING)


def hollow(tmp_path: Path, tag: str) -> str:
    """The trap's surface: z = 300 + 0.5((c-3)² + (r-2)²), strict minimum at (2,3)."""
    rows, columns = np.mgrid[0:SIZE, 0:SIZE]
    surface = 300.0 + 0.5 * ((columns - LOW_COLUMN) ** 2 + (rows - LOW_ROW) ** 2)
    path = tmp_path / f"hollow_{tag.lower()}.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1,
        dtype="float32", crs="EPSG:32632",
        transform=from_origin(EAST0, NORTH0, SPACING, SPACING),
    ) as dst:
        dst.write(surface.astype("float32"), 1)
        dst.update_tags(AREA_OR_POINT=tag)
    return str(path)


def first_sample_as_the_file_states_it(path: str) -> tuple[float, float]:
    """The raw tie point of a PixelIsPoint GeoTIFF: where its first sample IS."""
    with rasterio.Env(GTIFF_POINT_GEO_IGNORE="TRUE"), rasterio.open(path) as raw:
        return raw.transform.c, raw.transform.f


# --- the module that decides ------------------------------------------------


def test_gdal_has_already_centred_the_cell_on_a_point_sample(tmp_path):
    """The premise, measured instead of asserted. The file stores its first
    sample half a cell inside GDAL's corner, and `sample_xy` must land there."""
    path = hollow(tmp_path, "Point")
    stored = first_sample_as_the_file_states_it(path)
    assert stored == pytest.approx((EAST0 + SPACING / 2, NORTH0 - SPACING / 2))
    with rasterio.open(path) as src:
        assert (src.transform.c, src.transform.f) == pytest.approx((EAST0, NORTH0))
        assert grid.sample_xy(src, 0, 0) == pytest.approx(stored)
        assert grid.sample_xy(src, 0, 0) == pytest.approx(src.xy(0, 0))


def test_the_tag_is_read_and_does_not_move_anything(tmp_path):
    """Area is the default and the safe reading of an unreadable tag. The tag
    says what a value represents; the offset is the centre either way."""
    with rasterio.open(hollow(tmp_path, "Point")) as src:
        assert grid.registration(src) == "point"
        assert grid.offset(src) == 0.5
    with rasterio.open(hollow(tmp_path, "Area")) as src:
        assert grid.registration(src) == "area"
        assert grid.offset(src) == 0.5

    plain = tmp_path / "untagged.tif"
    with rasterio.open(
        plain, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 10, 5, 5),
    ) as dst:
        dst.write(np.zeros((2, 2), dtype="float32"), 1)
    with rasterio.open(plain) as src:
        assert grid.registration(src) == "area"


@pytest.mark.parametrize("tag", ["Point", "Area"])
def test_the_position_of_a_cell_is_where_its_sample_is(tmp_path, tag):
    with rasterio.open(hollow(tmp_path, tag)) as src:
        assert grid.sample_xy(src, LOW_ROW, LOW_COLUMN) == pytest.approx(SAMPLE)


@pytest.mark.parametrize("tag", ["Point", "Area"])
def test_a_position_belongs_to_the_cell_whose_sample_is_nearest(tmp_path, tag):
    """Row first, column second. Unpacking it the other way is the axis-order
    defect, and it happened here once: the sampling tests caught it."""
    with rasterio.open(hollow(tmp_path, tag)) as src:
        assert grid.sample_index(src, *SAMPLE) == (LOW_ROW, LOW_COLUMN)
        assert grid.sample_index(src, SAMPLE[0] + 2, SAMPLE[1] - 2) == (LOW_ROW, LOW_COLUMN)


def test_the_registration_is_recorded_under_its_own_key(tmp_path):
    """It is merged into `crs_decisions`, which already has a `reason`.

    The first version used `reason` and silently replaced the sentence
    explaining a reprojection with one about cell registration. An existing test
    caught it. Two different reasons under one key is a defect wherever it
    happens, so the key is checked here rather than left to luck.
    """
    with rasterio.open(hollow(tmp_path, "Point")) as src:
        described = grid.describe(src)
        # Inside the `with`, because `registration` refuses a closed dataset on
        # purpose and a test that opens a second one without closing it argues
        # against that discipline while relying on it.
        for_manifest = grid.manifest_decisions(src)
    assert "reason" not in described
    assert described["raster_registration"] == "point"
    assert "AREA_OR_POINT=Point" in described["raster_registration_reason"]
    assert for_manifest == {
        f"x-mapsmith:{key}": value for key, value in described.items()
    }


# --- the operation that answers where ---------------------------------------


@pytest.mark.parametrize("tag", ["Point", "Area"])
def test_the_lowest_cell_is_where_its_sample_is(tmp_path, tag):
    """Argleton trap 024, answered from this side: 412105 on both files. The
    engine that says 412120 is whitebox, reading the raw tie point as a corner;
    the one that says 412090 corrects a second time what GDAL already did --
    which is what this operation shipped until 2026-09-25."""
    answer = raster.locate_extreme_cell(hollow(tmp_path, tag), "min")
    assert (answer["x"], answer["y"]) == pytest.approx(SAMPLE)
    assert (answer["x"], answer["y"]) != pytest.approx(TWICE_CORRECTED)
    assert answer["value"] == pytest.approx(300.0)
    assert (answer["row"], answer["column"]) == (LOW_ROW, LOW_COLUMN)
    assert answer["raster_registration"] == tag.lower()


def test_an_environment_that_reverts_gdal_to_its_old_reading_changes_nothing(tmp_path):
    """`GTIFF_POINT_GEO_IGNORE=TRUE` makes GDAL read a PixelIsPoint tie point as a
    corner, and the answer above moved half a cell south-east with nothing in it
    to say why (measured 2026-09-25). MapSmith pins the setting on import, so a
    process started with it set still answers where the sample is. A child
    process, because the pin is applied when `mapsmith` is imported."""
    import os
    import subprocess
    import sys

    path = hollow(tmp_path, "Point")
    code = (
        "from mapsmith.engines import raster; "
        f"print(raster.locate_extreme_cell({path!r}, 'min')['x'])"
    )
    env = {**os.environ, "GTIFF_POINT_GEO_IGNORE": "TRUE"}
    run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, check=False)
    assert run.returncode == 0, run.stderr[-500:]
    assert float(run.stdout.strip().splitlines()[-1]) == pytest.approx(SAMPLE[0])


def test_nodata_does_not_win_the_search_for_a_minimum(tmp_path):
    """A nodata of -9999 beats every real elevation, and the answer would be the
    position of a hole reported as the bottom of a valley."""
    path = tmp_path / "holed.tif"
    surface = np.full((4, 4), 100.0, dtype="float32")
    surface[1, 1] = 50.0
    surface[3, 3] = -9999.0
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 40, 10, 10), nodata=-9999.0,
    ) as dst:
        dst.write(surface, 1)

    answer = raster.locate_extreme_cell(str(path), "min")
    assert answer["value"] == pytest.approx(50.0)
    assert (answer["row"], answer["column"]) == (1, 1)
    assert answer["nodata_cells"] == 1


def test_a_tie_is_reported_rather_than_broken_in_silence(tmp_path):
    """A plateau is a fact about the data. Reporting one of its cells as *the*
    position, with nothing said, turns it into a confident single answer."""
    path = tmp_path / "plateau.tif"
    surface = np.full((3, 3), 5.0, dtype="float32")
    surface[0, 0] = 1.0
    surface[2, 2] = 1.0
    with rasterio.open(
        path, "w", driver="GTiff", height=3, width=3, count=1, dtype="float32",
        crs="EPSG:32632", transform=from_origin(0, 30, 10, 10),
    ) as dst:
        dst.write(surface, 1)

    answer = raster.locate_extreme_cell(str(path), "min")
    assert answer["tied_cells"] == 2
    assert "plateau" in answer["note"]


def test_a_raster_without_a_crs_is_refused(tmp_path):
    path = tmp_path / "nocrs.tif"
    with rasterio.open(
        path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
        transform=from_origin(0, 10, 5, 5),
    ) as dst:
        dst.write(np.zeros((2, 2), dtype="float32"), 1)
    with pytest.raises(ValueError, match="no CRS"):
        raster.locate_extreme_cell(str(path), "min")


# --- everything that samples ------------------------------------------------


def _points_at(tmp_path, xy, name):
    import geopandas as gpd
    from shapely.geometry import Point

    points = tmp_path / f"{name}.parquet"
    gpd.GeoDataFrame({"n": [1]}, geometry=[Point(*xy)], crs="EPSG:32632").to_parquet(points)
    return str(points)


@pytest.mark.parametrize("tag", ["Point", "Area"])
@pytest.mark.parametrize("method", ["nearest", "bilinear"])
def test_sampling_at_the_sample_reads_its_value_exactly(tmp_path, tag, method):
    """`sample_raster_at_points`, `elevation_profile` and `line_of_sight` all
    go through the same reader, so this covers the three of them."""
    import geopandas as gpd

    out = tmp_path / f"sampled_{tag}_{method}.parquet"
    sampling.sample_raster_at_points(
        hollow(tmp_path, tag), _points_at(tmp_path, SAMPLE, "at_sample"), str(out), method
    )
    assert gpd.read_parquet(out)["value"].iloc[0] == pytest.approx(300.0)


@pytest.mark.parametrize("tag", ["Point", "Area"])
def test_the_twice_corrected_position_is_between_samples(tmp_path, tag):
    """The position MapSmith used to call the sample of a Point file sits
    between four samples, and bilinear there averages them: 300.5, not 300."""
    import geopandas as gpd

    out = tmp_path / f"twice_{tag}.parquet"
    sampling.sample_raster_at_points(
        hollow(tmp_path, tag), _points_at(tmp_path, TWICE_CORRECTED, "twice"), str(out),
        "bilinear",
    )
    assert gpd.read_parquet(out)["value"].iloc[0] == pytest.approx(300.5)


def test_zonal_statistics_weights_cells_around_their_own_samples(tmp_path):
    """A zone one cell wide, centred on the sample, covers exactly that cell.
    Until 2026-09-25 the zones were moved half a cell for a Point raster on
    the premise that exactextract read the raw tie point; it reads GDAL's
    geotransform, and the move put the zone across four cells."""
    import geopandas as gpd
    from shapely.geometry import box

    zones = tmp_path / "zone.parquet"
    half = SPACING / 2
    gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[box(SAMPLE[0] - half, SAMPLE[1] - half, SAMPLE[0] + half, SAMPLE[1] + half)],
        crs="EPSG:32632",
    ).to_parquet(zones)

    out = tmp_path / "zonal.parquet"
    result = raster.zonal_statistics(
        hollow(tmp_path, "Point"), str(zones), str(out), stats=["mean"]
    )
    assert gpd.read_parquet(out)["mean"].iloc[0] == pytest.approx(300.0, abs=1e-4)
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    # Prefixed here and bare in the tool answer above, and the difference is
    # the point: this object's other keys belong to the manifest specification,
    # that one's are ours all the way down.
    assert manifest["crs_decisions"][grid.REGISTRATION_KEY] == "point"


# --- what gets written out --------------------------------------------------


def _mask_for(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    mask = tmp_path / "mask.parquet"
    gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[box(412000.0, 5107800.0, 412150.0, 5108000.0)],
        crs="EPSG:32632",
    ).to_parquet(mask)
    return str(mask)


def _points_file(tmp_path, xy, name):
    return _points_at(tmp_path, xy, name)


def _streams(source, out, tmp_path):
    from mapsmith.engines import whitebox_engine

    accumulation = str(tmp_path / "acc_for_streams.tif")
    whitebox_engine.flow_accumulation(source, accumulation)
    return whitebox_engine.extract_streams(accumulation, out, threshold=2.0)


def _terrain(name, **kwargs):
    def call(source, out, tmp_path):
        from mapsmith.engines import whitebox_engine

        return getattr(whitebox_engine, name)(source, out, **kwargs)

    return call


#: Every operation that writes a raster, and one call each. Parametrised rather
#: than written once because the single-operation version of this test picked
#: `clip_raster`, which was one of the three that already worked — `reclassify`,
#: `band_math` and `extract_band` shipped point-registered inputs as
#: area-registered outputs while it stayed green.
RASTER_WRITERS = {
    "resample": lambda source, out, tmp_path: raster.resample(source, out, 20.0, "nearest"),
    "clip_raster": lambda source, out, tmp_path: raster.clip_raster(
        source, _mask_for(tmp_path), out
    ),
    "reproject_raster": lambda source, out, tmp_path: raster.reproject_raster(
        source, out, "EPSG:3857", "nearest"
    ),
    "reclassify": lambda source, out, tmp_path: raster.reclassify(
        source, out, ["0:10000:1"]
    ),
    "band_math": lambda source, out, tmp_path: raster.band_math(source, out, "b1*2"),
    "extract_band": lambda source, out, tmp_path: raster.extract_band(source, out, 1),
}

#: The terrain operations, which refused every point-registered DEM until
#: 2026-09-25 -- the Copernicus DEM included -- because the engine reads the raw
#: tie point as a corner. They now get an area copy on GDAL's geotransform and
#: give the output the input's registration back (D-096).
TERRAIN_WRITERS = {
    "slope": _terrain("slope"),
    "aspect": _terrain("aspect"),
    "curvature": _terrain("curvature", kind="profile"),
    "hillshade": _terrain("hillshade"),
    "flow_direction": _terrain("flow_direction"),
    "flow_accumulation": _terrain("flow_accumulation"),
    "focal_statistics": _terrain("focal_statistics", statistic="mean", window=3),
    "euclidean_distance": _terrain("euclidean_distance"),
    "watershed": lambda source, out, tmp_path: __import__(
        "mapsmith.engines.whitebox_engine", fromlist=["watershed"]
    ).watershed(source, _points_file(tmp_path, SAMPLE, "pour"), out),
    "viewshed": lambda source, out, tmp_path: __import__(
        "mapsmith.engines.whitebox_engine", fromlist=["viewshed"]
    ).viewshed(source, _points_file(tmp_path, SAMPLE, "station"), out, station_height=2.0),
    "extract_streams": _streams,
}


@pytest.mark.parametrize("operation", sorted(RASTER_WRITERS))
def test_the_registration_survives_every_operation_that_writes_a_raster(
    operation, tmp_path
):
    """`profile.copy()` does not carry tags, so every raster MapSmith wrote came
    back area-registered whatever went in — the same silent error one step
    downstream, with nothing in the output to say so.

    Parametrised over all of them because the defect that made this necessary
    was not the carrying but *where* it was done: three writers called
    `preserve` after their input's `with` block had closed. Asking a closed
    dataset for its tags does not raise — GDAL returns nothing — so the answer
    came back "area" and nothing anywhere said otherwise.
    """
    source = hollow(tmp_path, "Point")
    out = tmp_path / f"{operation}.tif"
    RASTER_WRITERS[operation](source, str(out), tmp_path)

    with rasterio.open(out) as dst:
        assert grid.registration(dst) == "point", (
            f"{operation} lost the point registration, so the output no longer "
            "says its values are samples"
        )


@pytest.mark.parametrize("operation", sorted(TERRAIN_WRITERS))
def test_a_terrain_operation_runs_on_a_point_dem_and_answers_as_on_its_twin(
    operation, tmp_path
):
    """The same values on the same geotransform, one tagged Point and one Area:
    the samples are in the same places, so the outputs must be the same grid
    with the same numbers -- and the Point one must still say Point."""
    pytest.importorskip("whitebox_workflows")
    outputs = {}
    for tag in ("Point", "Area"):
        folder = tmp_path / tag
        folder.mkdir()
        out = folder / f"{operation}.tif"
        TERRAIN_WRITERS[operation](hollow(folder, tag), str(out), folder)
        with rasterio.open(out) as dst:
            outputs[tag] = (grid.registration(dst), dst.transform, dst.read(1, masked=True))
        manifest = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
        # The record says what the output is, and -- on the Point twin -- that
        # MapSmith changed its bytes after the engine wrote them.
        assert manifest["crs_decisions"][grid.REGISTRATION_KEY] == tag.lower()
        retagged = any("tagged it Point in place" in note for note in manifest["notes"])
        assert retagged is (tag == "Point")
    (point_tag, point_transform, point_values) = outputs["Point"]
    (area_tag, area_transform, area_values) = outputs["Area"]
    assert (point_tag, area_tag) == ("point", "area")
    assert point_transform == area_transform
    assert np.ma.allequal(point_values, area_values)


def test_contours_on_a_point_dem_are_where_the_heights_are(tmp_path):
    """`contour_lines` used to pick -0.5 for a Point DEM, a branch nobody could
    reach because the reader refused the DEM first. The check that reads the
    DEM back at the vertices is the arbiter, and it must pass on both twins
    with the same lines."""
    pytest.importorskip("whitebox_workflows")
    import geopandas as gpd

    from mapsmith.engines import whitebox_engine

    lines = {}
    for tag in ("Point", "Area"):
        out = tmp_path / f"contours_{tag}.parquet"
        result = whitebox_engine.contour_lines(hollow(tmp_path, tag), str(out), interval=2.0)
        record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
        failing = [(c["name"], c["detail"]) for c in record["verification"] if not c["passed"]]
        assert not failing, (tag, failing)
        # By height, as one geometry per height: several lines share a height
        # and their order in the file is the engine's, not a property of them.
        written = gpd.read_parquet(out)
        lines[tag] = {
            height: group.geometry.union_all() for height, group in written.groupby("elevation")
        }
    assert lines["Point"].keys() == lines["Area"].keys()
    for height, geometry in lines["Point"].items():
        assert geometry.hausdorff_distance(lines["Area"][height]) < 1e-6, height


def test_every_raster_writer_is_covered_by_the_registration_test():
    """A writer added later must not be able to be quiet in the same way.

    The parametrised tests above are only worth their names if the lists they
    run over are the real ones. This compares them against the operations the
    catalogue says write a raster, so adding one and forgetting the fixture
    fails here rather than passing everywhere.
    """
    from mapsmith import catalog

    writes_a_raster = {
        entry["name"]
        for entry in catalog.OPERATIONS
        if entry.get("status") == "available"
        and entry.get("produces") == "dataset:raster"
    }
    assert writes_a_raster, (
        "no operation in the catalogue declares `produces: dataset:raster` — the "
        "field was renamed and this guard is now checking an empty set, which is "
        "how it would pass forever"
    )
    covered = {RASTER_WRITER_OPERATIONS[name] for name in RASTER_WRITERS} | set(TERRAIN_WRITERS)
    missing = sorted(writes_a_raster - covered - _NO_INPUT_RASTER)
    assert not missing, (
        f"these operations write a raster and nothing checks their registration: "
        f"{missing}. Add a call to RASTER_WRITERS or TERRAIN_WRITERS, or account "
        "for it below with the reason — measured, not assumed."
    )


#: The catalogue name for each entry in RASTER_WRITERS, which is keyed by the
#: engine function. They differ (`resample` writes `resample_raster`).
RASTER_WRITER_OPERATIONS = {
    "resample": "resample_raster",
    "clip_raster": "clip_raster",
    "reproject_raster": "reproject_raster",
    "reclassify": "reclassify_raster",
    "band_math": "band_math",
    "extract_band": "extract_band",
}

#: Takes a vector layer, so there is no input raster whose registration could be
#: carried: the grid it writes is one it invented.
_NO_INPUT_RASTER = {"idw_interpolation"}


def test_only_one_module_decides_where_a_cell_is(tmp_path):
    """The guard that keeps this from being half-applied again.

    #28 happened because "open a vector file" was six copies of one decision.
    This was the same shape: every place that turned a cell index into a
    coordinate decided for itself. The decision lives in `grid`, and since
    D-096 it agrees with `dataset.xy` -- but a second copy of it is still the
    only way to reintroduce a second answer, so the second copy is what fails.
    """
    import re

    import mapsmith

    package = Path(mapsmith.__file__).parent
    allowed = {"grid.py"}
    pattern = re.compile(r"\.xy\s*\(|\btransform\.xy\s*\(|(?<!sample_)\bindex\s*\(\s*\w+\.x")
    offenders = []
    for module in package.rglob("*.py"):
        if module.name in allowed:
            continue
        for number, line in enumerate(
            module.read_text(encoding="utf-8").splitlines(), 1
        ):
            if pattern.search(line) and "grid." not in line:
                offenders.append(f"{module.name}:{number}: {line.strip()}")
    assert not offenders, (
        "these lines turn a cell index into a coordinate without going through "
        f"`grid`: {offenders}"
    )
