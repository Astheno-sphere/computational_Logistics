"""The configuration that changed the answer, and the record that says so.

Section 3.8 of the manifest specification had no implementation until
2026-08-31: the field did not exist in `ProvenanceRecord`, so a whole section of
a published specification described something MapSmith could not produce.

Argleton trap 030 is what made that concrete. A GeoTIFF and the `.aux.xml`
beside it declare different georeferencing; GDAL prefers the sidecar by
documented design, because that is how somebody overrides georeferencing they
know to be wrong. Both readings are the library behaving as written. What was
missing is the sentence naming which one produced the numbers — and MapSmith
answered 160 000 m² where the file's own tags say 40 000, silently.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from conftest import _spec_problems
from mapsmith import grid
from mapsmith.engines import raster, sampling
from mapsmith.provenance import REDACTED, InputRecord, ProvenanceRecord

CRS = "EPSG:32632"
SIZE = 20
INTERNAL = (500000.0, 5030000.0, 10.0)
SIDECAR = (600000.0, 5040000.0, 20.0)

AUX_XML = """<PAMDataset>
  <SRS dataAxisToSRSAxisMapping="1,2">EPSG:32632</SRS>
  <GeoTransform> {ox},  {cell},  0.0,  {oy},  0.0, -{cell}</GeoTransform>
</PAMDataset>
"""


def _raster(path: Path, origin_x: float, origin_y: float, cell: float) -> None:
    values = np.tile(np.arange(SIZE, dtype="float32"), (SIZE, 1))
    with rasterio.open(
        path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1,
        dtype="float32", crs=CRS,
        transform=Affine(cell, 0.0, origin_x, 0.0, -cell, origin_y),
    ) as destination:
        destination.write(values, 1)


@pytest.fixture
def two_georeferencings(tmp_path):
    """A raster whose sidecar disagrees with it — the shape of trap 030."""
    path = tmp_path / "terrain.tif"
    _raster(path, *INTERNAL)
    ox, oy, cell = SIDECAR
    Path(f"{path}.aux.xml").write_text(
        AUX_XML.format(ox=ox, oy=oy, cell=cell), encoding="utf-8", newline="\n"
    )
    return str(path)


@pytest.fixture
def agreeing_sidecar(tmp_path):
    """A raster with a sidecar that declares the SAME georeferencing.

    The fixture the recording tests need once the disagreeing case refuses
    (D-059). A sidecar is present, so there is something to record — which
    source produced the numbers, and that a sidecar was there at all — and there
    is nothing to refuse, because both readings give the same answer. Recording
    is not the alternative to refusing: it is what stays on the disk afterwards.
    """
    path = tmp_path / "agreeing.tif"
    _raster(path, *INTERNAL)
    ox, oy, cell = INTERNAL
    Path(f"{path}.aux.xml").write_text(
        AUX_XML.format(ox=ox, oy=oy, cell=cell), encoding="utf-8", newline="\n"
    )
    return str(path)


@pytest.fixture
def one_georeferencing(tmp_path):
    path = tmp_path / "plain.tif"
    _raster(path, *INTERNAL)
    return str(path)


def test_the_sidecar_wins_and_the_source_says_so(two_georeferencings):
    """GDAL's default, and the sentence that was missing.

    Not a bug to file: a sidecar is how an override works, so it has to beat
    the file it overrides. What was missing is anywhere saying which was used.
    """
    found = grid.georeferencing_source(two_georeferencings)
    assert found["georeferencing_source"] == "sidecar (.aux.xml)"
    assert found["georeferencing_sidecar_present"] == "terrain.tif.aux.xml"
    # The other branch's numbers, because "there was a choice" is weaker than
    # "here is what the other choice says".
    assert "cell 10 x 10 at (500000, 5030000)" == found[
        "georeferencing_internal_would_give"
    ]


def test_a_coordinate_is_never_reported_in_scientific_notation(two_georeferencings):
    """`5.03e+06` is a northing nobody can compare with the one in front of
    them, and this string exists to be compared."""
    found = grid.georeferencing_source(two_georeferencings)
    assert "e+" not in found["georeferencing_internal_would_give"]


def test_one_georeferencing_says_nothing(one_georeferencing):
    """An empty `environment` claims nothing, exactly like an absent
    `crs_decisions` — and a field that fires on every raster is a field its
    reader learns to skip."""
    assert grid.georeferencing_source(one_georeferencing) == {}


def test_computing_refuses_where_describing_reports(two_georeferencings):
    """The twin of the multi-layer refusal (#29), on a different axis.

    There, GDAL's default is the first layer of a container; here it is the
    sidecar. Both answer a question the caller never asked. Describing is
    different: a file with two georeferencings is a thing to be told about, and
    `describe_dataset` is the operation whose whole job is to tell you.
    """
    from mapsmith.engines import dispatch

    described = dispatch.describe_routed(two_georeferencings)
    assert described["georeferencing"]["georeferencing_source"].startswith("sidecar")

    with pytest.raises(ValueError, match="georeferenced twice"):
        grid.refuse_ambiguous_georeferencing(two_georeferencings, "resample_raster")

    # And it says how to choose, rather than only that a choice exists.
    try:
        grid.refuse_ambiguous_georeferencing(two_georeferencings, "resample_raster")
    except ValueError as refusal:
        assert "GDAL_GEOREF_SOURCES=INTERNAL" in str(refusal)


def test_a_writer_that_bypasses_audited_still_records_it(agreeing_sidecar, tmp_path):
    """`resample_raster` builds its record by hand, and that is the point.

    The first version filled `environment` inside `verify.audited`, which
    `mapsmith/CLAUDE.md` describes as the place the invariants become
    unmissable. Seventeen writers of fifty-seven do not go through it, and they
    are concentrated in raster — where georeferencing decides the numbers. The
    field is filled in `write_for` instead, which is the single point where a
    manifest becomes a file.

    The fixture is a sidecar that **agrees**, and it has to be: the disagreeing
    case now refuses before any manifest exists (D-059), so it cannot show that
    a record was written. A sidecar that agrees leaves something worth recording
    — which source produced the numbers, and that a sidecar was there — and
    nothing to refuse. Recording is not the alternative to refusing; it is what
    stays on the disk afterwards.
    """
    source = tmp_path / "in.tif"
    shutil.copy(agreeing_sidecar, source)
    shutil.copy(f"{agreeing_sidecar}.aux.xml", f"{source}.aux.xml")

    result = raster.resample(str(source), str(tmp_path / "out.tif"), 40, "nearest")
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    # Prefixed in the MANIFEST and bare in the answer `describe_dataset`
    # returns, and the difference is the rule: section 3.8 asks for the
    # configuration as the engine reports it, so `GDAL_PAM_ENABLED` keeps its
    # own name while our reading of it says whose reading it is.
    assert record["environment"]["x-mapsmith:georeferencing_source"] == "internal"
    assert (
        record["environment"]["x-mapsmith:georeferencing_sidecar_present"]
        == "in.tif.aux.xml"
    )


def test_a_record_with_a_filled_environment_conforms_to_the_spec(agreeing_sidecar, tmp_path):
    """The field is checked for its CONTENT everywhere and for conformance nowhere.

    Found on 2026-09-05 by the `conformita-manifest` agent, counting rather than
    reading: this file asserts what `environment` holds and never calls the
    validators, and the conformance sweep in `test_verify.py` validates
    fifty-eight real manifests that all carry `environment: {}` — no fixture
    there has a sidecar. So the only field of the record that answers "was the
    answer decided by configuration nobody can see" had its shape verified by
    nothing.

    It matters because the validator makes a demand the schema does not: section
    3.8 records configuration *as the engine reports it*, so **every value must
    be a string**. The values are built by formatting coordinates by hand in
    `grid.georeferencing_source`, and that function already carries a `plain()`
    helper written to keep `5.03e+06` out of a northing — which is the same
    place a float would escape as a float. Both halves are correct today; the
    point is that until now nothing would have said so.
    """
    from mapsmith.engines import raster

    source = tmp_path / "in.tif"
    shutil.copy(agreeing_sidecar, source)
    shutil.copy(f"{agreeing_sidecar}.aux.xml", f"{source}.aux.xml")

    result = raster.resample(str(source), str(tmp_path / "out.tif"), 40, "nearest")
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))

    assert record["environment"], (
        "this test is worthless without a filled environment: the fixture no "
        "longer produces one, so the conformance assertion below proves nothing"
    )
    assert _spec_problems(record) == [], _spec_problems(record)
    assert all(isinstance(v, str) for v in record["environment"].values()), (
        f"section 3.8 wants strings: {record['environment']}"
    )


def test_an_ordinary_raster_leaves_the_field_empty(one_georeferencing, tmp_path):
    from mapsmith.engines import raster

    result = raster.resample(one_georeferencing, str(tmp_path / "out.tif"), 40, "nearest")
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    assert record["environment"] == {}


def test_a_credential_in_a_dictionary_key_is_masked():
    """The gap adding this field exposed, and it was never about this field.

    `{"AWS_SECRET_ACCESS_KEY": "AKIA..."}` passed through untouched: the scanner
    looks for `name=value` INSIDE a string, and in a dictionary the name is the
    key. That was true of every dict a manifest carries; `environment` is
    merely the one that makes it obvious, holding environment variables by
    definition.
    """
    record = ProvenanceRecord(
        operation="x", parameters={"api_key": "abc123"}, inputs=[],
        environment={"AWS_SECRET_ACCESS_KEY": "AKIAnotreally", "GDAL_PAM_ENABLED": "NO"},
    )
    assert record.environment["AWS_SECRET_ACCESS_KEY"] == REDACTED
    assert record.parameters["api_key"] == REDACTED
    # And the record says a redaction happened, because a manifest that quietly
    # differs from what ran would be worse than the leak.
    assert record.parameters_redacted is True


@pytest.mark.parametrize(
    "key", ["sort_key", "primary_key", "key", "GDAL_PAM_ENABLED", "georeferencing_source"]
)
def test_an_ordinary_key_is_left_alone(key):
    """A redaction that fires on `sort_key` teaches its reader to distrust the
    mask, which leaves less protection than a narrower rule nobody doubts."""
    record = ProvenanceRecord(
        operation="x", parameters={key: "ordinary"}, inputs=[]
    )
    assert record.parameters[key] == "ordinary"
    assert record.parameters_redacted is False


def test_the_field_is_never_a_dump_of_the_environment(agreeing_sidecar, tmp_path):
    """A record listing forty variables would bury the one that mattered.

    The specification says a producer records what it knows influenced the
    result. This pins the discipline rather than the wording: whatever is in
    there has to be about the georeferencing decision, not about the machine.
    """
    from mapsmith.engines import raster

    source = tmp_path / "in.tif"
    shutil.copy(agreeing_sidecar, source)
    shutil.copy(f"{agreeing_sidecar}.aux.xml", f"{source}.aux.xml")
    result = raster.resample(str(source), str(tmp_path / "out.tif"), 40, "nearest")
    record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))

    assert record["environment"], (
        "the fixture has a sidecar, so there is something to record; an empty "
        "field here would make the rest of this test vacuous"
    )
    assert len(record["environment"]) <= 5, (
        "the environment field is growing into a dump; a reader who has to scan "
        "it stops reading it"
    )
    assert all(
        "georef" in key.lower() or key in grid.GEOREF_VARIABLES
        for key in record["environment"]
    )


def test_an_operation_can_say_more_than_this_does(two_georeferencings, tmp_path):
    """Anything the engine set itself is kept.

    An operation that knows something about its own environment knows it better
    than a generic sweep over the inputs does, and overwriting it would be this
    helper claiming an authority it has not got.
    """
    record = ProvenanceRecord(
        operation="x",
        parameters={},
        inputs=[InputRecord.from_path(two_georeferencings)],
        environment={
            "x-mapsmith:georeferencing_source": "internal, forced by the operation"
        },
    )
    output = tmp_path / "out.txt"
    output.write_text("x", encoding="utf-8")
    record.write_for(str(output))

    assert record.environment["x-mapsmith:georeferencing_source"] == (
        "internal, forced by the operation"
    )
    # And the rest is still added: keeping one key is not skipping the sweep.
    assert "x-mapsmith:georeferencing_sidecar_present" in record.environment


def test_the_refusal_stays_quiet_when_there_is_nothing_to_refuse(one_georeferencing):
    """A guard that refuses everything is not a guard, and nothing covered it.

    Found by sabotage: removing the early return from
    `refuse_ambiguous_georeferencing` — so that it raised on every raster —
    left all fourteen other tests green. The refusing branch was tested and the
    quiet branch was not, which is the half that every ordinary call takes.
    """
    assert grid.refuse_ambiguous_georeferencing(one_georeferencing, "resample_raster") == {}


def test_a_sidecar_that_agrees_is_not_a_conflict(tmp_path):
    """Two sources saying the same thing is not two answers.

    A `.aux.xml` often carries statistics or a colour table and repeats the
    georeferencing unchanged. Refusing there would be refusing an ordinary file,
    and this suite's own admission rule says a check that fires on the ordinary
    case gets switched off.
    """
    path = tmp_path / "agreeing.tif"
    _raster(path, *INTERNAL)
    ox, oy, cell = INTERNAL
    Path(f"{path}.aux.xml").write_text(
        AUX_XML.format(ox=ox, oy=oy, cell=cell), encoding="utf-8", newline="\n"
    )
    found = grid.georeferencing_source(str(path))
    assert found["georeferencing_source"] == "internal"
    assert grid.refuse_ambiguous_georeferencing(str(path), "resample_raster") == found


#: Every raster operation that computes from the georeferencing, and one call
#: each. The refusal these check had **no caller in `src/`** when it shipped:
#: `README.md` promised it publicly and D-059 recorded it as decided, while the
#: only thing invoking it was a test calling the function directly. Green, and
#: proving nothing about the product — which is the failure this file's own
#: docstrings warn about elsewhere.
COMPUTES_FROM_THE_GEOREFERENCING = {
    "resample_raster": lambda path, out: raster.resample(path, out, 20.0, "nearest"),
    "reclassify_raster": lambda path, out: raster.reclassify(path, out, ["0:10000:1"]),
    "band_math": lambda path, out: raster.band_math(path, out, "b1*2"),
    "reproject_raster": lambda path, out: raster.reproject_raster(
        path, out, "EPSG:3857", "nearest"
    ),
    "extract_band": lambda path, out: raster.extract_band(path, out, 1),
    "band_statistics": lambda path, out: raster.band_statistics(path, 1),
    "locate_extreme_cell": lambda path, out: raster.locate_extreme_cell(path, "max"),
    # These two were missing from the list while their code refused: seven
    # entries for nine callers. Exactly the rule this file's other docstrings
    # state — a parametrised test is worth what its list is worth — flagged by
    # review rather than caught here, which is why the guard below exists now.
    "zonal_statistics": lambda path, out: raster.zonal_statistics(
        path, _zones_beside(path), out.replace(".tif", ".parquet")
    ),
    "clip_raster": lambda path, out: raster.clip_raster(
        path, _zones_beside(path), out
    ),
    # The three that read the grid to place a coordinate, and had no guard at
    # all until 2026-09-02. `sample_raster_at_points` is the operation most
    # dependent on georeferencing in the whole product: measured on 31/08, the
    # same DEM gave 10.0 and 30.0 with no sidecar and 2.0 and 6.0 with a 40 m
    # one — five times out, no refusal, no warning.
    "sample_raster_at_points": lambda path, out: sampling.sample_raster_at_points(
        path, _points_beside(path), out.replace(".tif", ".parquet"), "nearest"
    ),
    "elevation_profile": lambda path, out: sampling.elevation_profile(
        path, _line_beside(path), out.replace(".tif", ".parquet"), 10.0
    ),
    # Coordinates, not a layer, and no output: it answers rather than writing.
    "line_of_sight": lambda path, out: sampling.line_of_sight(
        path, 500050.0, 5029950.0, 500150.0, 5029850.0, False
    ),
}


def _zones_beside(raster_path):
    """A one-polygon zone layer next to a raster, for the two operations that
    need a second input before they can refuse the first."""
    import geopandas as gpd
    from shapely.geometry import box

    zones = Path(raster_path).with_suffix(".zones.parquet")
    if not zones.exists():
        ox, oy, cell = INTERNAL
        gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[box(ox, oy - cell * SIZE, ox + cell * SIZE, oy)],
            crs=CRS,
        ).to_parquet(zones)
    return str(zones)


def _points_beside(raster_path):
    """Two points inside the raster, for the operation that samples at points."""
    import geopandas as gpd
    from shapely.geometry import Point

    points = Path(raster_path).with_suffix(".points.parquet")
    if not points.exists():
        ox, oy, cell = INTERNAL
        gpd.GeoDataFrame(
            {"id": [1, 2]},
            geometry=[
                Point(ox + cell * 5, oy - cell * 5),
                Point(ox + cell * 15, oy - cell * 15),
            ],
            crs=CRS,
        ).to_parquet(points)
    return str(points)


def _line_beside(raster_path):
    """One line across the raster, for the profile operation."""
    import geopandas as gpd
    from shapely.geometry import LineString

    line = Path(raster_path).with_suffix(".line.parquet")
    if not line.exists():
        ox, oy, cell = INTERNAL
        gpd.GeoDataFrame(
            {"id": [1]},
            geometry=[
                LineString(
                    [
                        (ox + cell * 2, oy - cell * 2),
                        (ox + cell * 18, oy - cell * 18),
                    ]
                )
            ],
            crs=CRS,
        ).to_parquet(line)
    return str(line)


def test_the_refusal_list_holds_every_operation_that_actually_refuses():
    """The list above is only worth what it covers.

    It had seven entries while `src/` had nine callers, so two operations
    refused with nothing going through them. Read from the source rather than
    maintained by hand, because that is the only version that cannot drift.

    **Every module in `engines/`, not just `raster.py`.** Reading one file was
    true of the day it was written and an assumption about every day after: the
    three operations most dependent on georeferencing — `sample_raster_at_points`,
    `elevation_profile`, `line_of_sight` — live in `sampling.py`, so the day the
    refusal reached them the derivation would not have seen them, the
    parametrised list below would have stayed at nine, and the guard would have
    passed. It would have stopped guarding exactly when the work it protects got
    done.
    """
    import re

    callers = set()
    for module in sorted(Path(raster.__file__).parent.glob("*.py")):
        for match in re.finditer(
            r"""refuse_ambiguous_georeferencing\([^,]+,\s*["']([a-z_]+)["']""",
            module.read_text(encoding="utf-8"),
        ):
            callers.add(match.group(1))
    assert callers, (
        "no call to refuse_ambiguous_georeferencing found anywhere in engines/ — "
        "the pattern stopped matching and this guard would pass on an empty set"
    )
    missing = sorted(callers - set(COMPUTES_FROM_THE_GEOREFERENCING))
    assert not missing, (
        f"these operations refuse an ambiguous raster and nothing tests it "
        f"through the operation: {missing}"
    )


@pytest.mark.parametrize("operation", sorted(COMPUTES_FROM_THE_GEOREFERENCING))
def test_every_computing_operation_refuses_an_ambiguously_georeferenced_raster(
    operation, two_georeferencings, tmp_path
):
    """Through the operation, not the helper. That distinction is the defect.

    A test that calls `refuse_ambiguous_georeferencing` directly proves the
    function raises. It says nothing about whether anything calls it, and for
    one release nothing did.
    """
    out = tmp_path / f"{operation}_out.tif"
    with pytest.raises(ValueError, match="georeferenced twice") as refusal:
        COMPUTES_FROM_THE_GEOREFERENCING[operation](two_georeferencings, str(out))
    # It names both readings and how to choose, rather than only that a choice
    # exists — a refusal a caller cannot act on is an obstacle, not a check.
    assert "GDAL_GEOREF_SOURCES=INTERNAL" in str(refusal.value)


@pytest.mark.parametrize("operation", sorted(COMPUTES_FROM_THE_GEOREFERENCING))
def test_a_single_georeferencing_is_computed_from_without_a_word(
    operation, one_georeferencing, tmp_path
):
    """The other half: the refusal must not fire on the ordinary case.

    A guard that refuses everything is indistinguishable from a guard that
    refuses the right thing until somebody tries an ordinary file. A sabotage of
    this exact function once left every test green for that reason.
    """
    out = tmp_path / f"{operation}_ok.tif"
    COMPUTES_FROM_THE_GEOREFERENCING[operation](one_georeferencing, str(out))


def test_describing_never_refuses_because_describing_is_not_computing(
    two_georeferencings,
):
    """D-059's other half, and the reason the split exists.

    `describe_dataset`'s whole job is to say what a file is, and a file with two
    georeferencings is a thing to be told about rather than turned away.
    """
    from mapsmith.engines import dispatch

    described = dispatch.describe_routed(two_georeferencings)
    assert described["georeferencing"]["georeferencing_source"].startswith("sidecar")
    assert "georeferencing_internal_would_give" in described["georeferencing"]


@pytest.fixture
def sidecar_overrides_only_the_crs(tmp_path):
    """A PAM sidecar that changes the `<SRS>` and leaves the geotransform alone.

    GDAL applies the PAM SRS unconditionally when the PAM georeferencing source
    is enabled, which it is by default, so the numbers come out in a coordinate
    system the file's own tags do not name.
    """
    path = tmp_path / "srs.tif"
    _raster(path, *INTERNAL)
    Path(f"{path}.aux.xml").write_text(
        "<PAMDataset><SRS>EPSG:3857</SRS></PAMDataset>", encoding="utf-8", newline="\n"
    )
    return str(path)


def test_a_sidecar_that_overrides_only_the_crs_is_still_a_sidecar(
    sidecar_overrides_only_the_crs,
):
    """Detection compared only the geotransform, so this said `internal`.

    An absent field claims nothing. That one claimed something false: the
    numbers came out in the sidecar's CRS and the manifest said they came from
    the file's own tags. It is also the more consequential axis — a wrong CRS
    changes every area, length and reprojection downstream, which is the family
    Argleton measures as `projection-distortion`.
    """
    found = grid.georeferencing_source(sidecar_overrides_only_the_crs)
    assert found["georeferencing_source"] == "sidecar (.aux.xml)"
    other = found["georeferencing_internal_would_give"]
    assert "EPSG:32632" in other and "EPSG:3857" in other, other


def test_an_operation_refuses_a_crs_only_override_as_well(
    sidecar_overrides_only_the_crs, tmp_path
):
    """And the refusal follows from the detection, rather than being separate."""
    with pytest.raises(ValueError, match="georeferenced twice"):
        raster.resample(
            sidecar_overrides_only_the_crs, str(tmp_path / "out.tif"), 40, "nearest"
        )


@pytest.fixture
def only_the_sidecar_georeferences_it(tmp_path):
    """A plain image plus an `.aux.xml` that supplies its georeferencing.

    The documented GDAL way to georeference something that has none. There is
    ONE georeferencing here, not two.
    """
    path = tmp_path / "bare.tif"
    values = np.tile(np.arange(SIZE, dtype="float32"), (SIZE, 1))
    with rasterio.open(
        path, "w", driver="GTiff", height=SIZE, width=SIZE, count=1, dtype="float32"
    ) as destination:
        destination.write(values, 1)
    ox, oy, cell = INTERNAL
    Path(f"{path}.aux.xml").write_text(
        AUX_XML.format(ox=ox, oy=oy, cell=cell), encoding="utf-8", newline="\n"
    )
    return str(path)


def test_a_georeferencing_supplied_by_a_sidecar_is_not_a_choice(
    only_the_sidecar_georeferences_it, tmp_path
):
    """Refusing this was a regression introduced by the refusal itself.

    `from_sidecar` could not tell "the two disagree" from "the file has none and
    the sidecar supplies it", so a plain image with an `.aux.xml` was refused —
    and the refusal *asserted* the file was georeferenced twice when it was
    georeferenced once, then offered a remedy ("remove the sidecar, or read the
    file's own") that would have destroyed or ignored the only georeferencing
    there was. A well-formed, confident, false statement about the data, which
    is the class this project measures in other software.
    """
    found = grid.georeferencing_source(only_the_sidecar_georeferences_it)
    assert found["georeferencing_source"] == "sidecar (.aux.xml)"
    assert "georeferencing_supplied_by_sidecar" in found, (
        "the record must say the sidecar supplied it rather than overrode "
        "something — those are different facts"
    )

    # And the operation runs, because there was nothing to choose.
    raster.band_statistics(only_the_sidecar_georeferences_it, 1)


def test_a_disagreeing_sidecar_is_still_refused(two_georeferencings, tmp_path):
    """The other half, so the fix above is not just "stop refusing"."""
    with pytest.raises(ValueError, match="georeferenced twice"):
        raster.band_statistics(two_georeferencings, 1)
