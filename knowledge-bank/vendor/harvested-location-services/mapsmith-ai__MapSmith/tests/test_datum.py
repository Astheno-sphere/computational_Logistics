"""The trap this repository measures in other people's software, on our own side.

Argleton trap 021: PROJ does not fail when it has no datum transformation for a
pair. It falls back to a *ballpark* operation that carries the coordinates
across as if the two datums coincided. The geometry is plausible, the output CRS
is genuinely the one that was asked for, `crs_matches` passes, and the numbers
are tens of metres out.

`reproject_layer` has answered that since 0.4.0. On 2026-09-02 a sweep found
that it was the ONLY answer: `transformation` appeared in one manifest out of
fifty-eight, and `reproject_raster` -- the head example of section 3.7 of the
manifest specification -- recorded two CRS labels and nothing about the
operation between them. No test in this suite mentioned `transformation` or
`accuracy_m` at all, so the fix we point at was guarded by nothing.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from mapsmith import datum

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ROOT / "src" / "mapsmith" / "engines"

# Monte Mario with the Rome prime meridian. PROJ's default for this pair really
# is a ballpark, a published 44 m operation exists, and the two differ by 83 m at
# the centre of the area of use -- measured 2026-09-03. This is the trap, whole.
BALLPARK_PAIR = ("EPSG:4806", "EPSG:4326")
# Same datum, different projection: a real operation with a stated accuracy.
SHIFTLESS_PAIR = ("EPSG:4326", "EPSG:32633")
# A PROJECTED source, which is what broke the probe: its area of use is stated in
# degrees while the transformer wants metres.
PROJECTED_PAIR = ("EPSG:3003", "EPSG:4326")


def test_a_pair_with_no_installed_grid_is_reported_as_a_ballpark():
    record = datum.default_operation(*BALLPARK_PAIR)
    assert record["is_ballpark"] is True
    assert record["accuracy_m"] is None
    # The distinction a reader needs in order to act: "there is no operation for
    # this pair" and "there is one and this machine has not got it" are
    # different problems with different fixes.
    assert record["better_available_m"] > 0, (
        "a published 44 m operation exists for this pair; saying only "
        "'ballpark' hides that the fix is to install its grid"
    )


def test_a_pair_within_one_datum_is_not_reported_as_a_ballpark():
    """The false positive is worse than the silence it replaces: a manifest
    saying `is_ballpark: true` accuses the engine of something it did not do."""
    record = datum.default_operation(*SHIFTLESS_PAIR)
    assert record["is_ballpark"] is False
    assert record["accuracy_m"] == 0.0
    assert record["pipeline"]


def test_a_projected_source_is_probed_in_its_own_units():
    """The defect this module was written to fix, found while fixing another one.

    `area_of_use` is always in degrees. EPSG:3003 is Gauss-Boaga in metres, and
    its area is 5.93..12.0 by 36.53..47.04, so probing at the midpoint handed
    (8.965, 41.785) to a transformer expecting metres -- nine metres from the
    false origin, nowhere near Italy. No location-restricted operation matches
    there, so PROJ returned a ballpark.

    It is not one. The default for this pair is "Monte Mario to WGS 84 (4)",
    stated accuracy 4 m. Since 0.4.0 `reproject_layer` has therefore written
    "the transformation this library selects by default for this pair is a
    ballpark one, which applies no datum shift at all" onto manifests for
    **every projected source**, which in this domain is most of them. That is a
    false statement in a shipped manifest, and it was in the one operation the
    project points at as its answer to trap 021.
    """
    record = datum.default_operation(*PROJECTED_PAIR)
    assert record["is_ballpark"] is False, (
        "EPSG:3003 -> EPSG:4326 has a 4 m default operation; reporting a "
        "ballpark means the probe is being handed degrees as metres again"
    )
    assert record["accuracy_m"] == 4.0


def test_the_answer_does_not_depend_on_how_the_caller_holds_the_crs():
    """A string, a pyproj CRS, a rasterio CRS and a bare WKT are the same CRS.

    They were not the same answer: routed through WKT the CRS loses
    `area_of_use` -- it comes from the EPSG registry, not the WKT -- and the
    probe fell back to (0, 0). Measured on 2026-09-03, NAD27 -> WGS84 came back
    7.0 m from a string and a ballpark from a rasterio object.
    """
    rasterio = pytest.importorskip("rasterio")
    from pyproj import CRS

    plain = "EPSG:4267"
    ways = [
        plain,
        CRS.from_user_input(plain),
        rasterio.crs.CRS.from_epsg(4267),
        CRS.from_user_input(rasterio.crs.CRS.from_epsg(4267).to_wkt()),
    ]
    answers = {
        (r["is_ballpark"], r["accuracy_m"])
        for r in (datum.default_operation(w, "EPSG:4326") for w in ways)
    }
    assert len(answers) == 1, (
        f"the same pair gives {len(answers)} different answers depending on how "
        f"the CRS was held: {answers}"
    )


def test_one_datum_is_not_a_ballpark_whatever_PROJ_reports_as_accuracy(monkeypatch):
    """The verdict must not depend on a number upstream is free to change.

    It did, and CI found out before this test existed. PROJ reported a stated
    accuracy of 0.0 for a projection change inside one datum, so
    `accuracy >= 0` happened to mean "not a ballpark"; **PROJ 9.8 reports -1.0
    for the same pair**, which is the value it also uses for a ballpark. Two
    different situations arrived at the same number and the discriminator
    stopped discriminating — so MapSmith on a current pyproj wrote
    `is_ballpark: true` into the manifest of a plain UTM projection, accusing
    the engine of skipping a datum shift that was never needed.

    Measured 2026-09-06, EPSG:4326 -> EPSG:32633: 0.0 on PROJ 9.5.1, -1.0 on
    PROJ 9.8.1, while `CRS.datum == CRS.datum` says True on both.

    Forcing the ballpark value here rather than pinning a pyproj version: the
    fix is that the answer comes from the datums, and the way to prove that is
    to make the accuracy say the opposite and watch the answer hold. A test
    that only ran the current build would go green on the machine that has the
    old PROJ, which is exactly what happened for a day.
    """
    monkeypatch.setattr(datum, "accuracy_of", lambda *_: -1.0)
    record = datum.default_operation(*SHIFTLESS_PAIR)
    assert record["is_ballpark"] is False
    assert record["accuracy_m"] == 0.0

    _, chosen = datum.best_operation(*SHIFTLESS_PAIR)
    assert chosen["is_ballpark"] is False, "best_operation shares the defect and the fix"

    # And the other half of the pair: a real ballpark must still be one, or
    # this fix would have bought silence instead of accuracy.
    assert datum.default_operation(*BALLPARK_PAIR)["is_ballpark"] is True


def test_a_rasterio_crs_does_not_get_reported_as_a_ballpark():
    """The bug this nearly shipped with.

    `accuracy_of` probes a point inside the CRS's `area_of_use`, and a
    `rasterio.crs.CRS` has no such attribute. Left alone it falls back to
    (0, 0) -- the Gulf of Guinea -- which is outside almost every real
    transformation's extent, so an ordinary pair comes back `is_ballpark: true`.
    Caught by running it, not by reading it.
    """
    rasterio = pytest.importorskip("rasterio")

    native = rasterio.crs.CRS.from_epsg(4326)
    assert not hasattr(native, "area_of_use"), (
        "rasterio grew area_of_use: this test now proves nothing and the "
        "conversion in datum._as_crs needs re-justifying, not deleting"
    )
    assert datum.default_operation(native, "EPSG:32633")["is_ballpark"] is False


def test_choosing_and_reporting_are_different_answers():
    """`best_operation` may substitute a better transformation; the record then
    describes what ran. `default_operation` never substitutes, because the
    caller that uses it (rasterio's warp) will not use our choice -- and a
    manifest describing an operation that never ran is worse than one that says
    nothing."""
    _, chosen = datum.best_operation(*BALLPARK_PAIR)
    reported = datum.default_operation(*BALLPARK_PAIR)

    assert reported["is_ballpark"] is True, "default_operation must not substitute"
    if not chosen["is_ballpark"]:
        # It found a better route and says so out loud rather than quietly
        # producing a different number from the one PROJ would have produced.
        assert chosen.get("x-mapsmith:default_was_ballpark") is True
    assert "x-mapsmith:chosen_by" in reported and (
        "MapSmith" in reported["x-mapsmith:chosen_by"]
    )


def test_reproject_raster_records_the_operation_and_not_only_the_two_crs_labels(tmp_path):
    """The head example of section 3.7, which recorded neither until 2026-09-03."""
    rasterio = pytest.importorskip("rasterio")
    pytest.importorskip("numpy")
    import numpy as np
    from rasterio.transform import from_origin

    from mapsmith.engines import raster

    source = tmp_path / "in.tif"
    profile = {
        "driver": "GTiff", "height": 4, "width": 4, "count": 1,
        # Monte Mario / Rome meridian: longitudes here are relative to 12.45E,
        # so -3.0 is roughly the middle of Italy. The CRS is the point of the
        # fixture; the pixels are not.
        "dtype": "float32", "crs": "EPSG:4806", "nodata": -9999.0,
        "transform": from_origin(-3.0, 43.0, 0.01, 0.01),
    }
    with rasterio.open(source, "w", **profile) as dst:
        dst.write(np.arange(16, dtype="float32").reshape(4, 4), 1)

    out = tmp_path / "out.tif"
    raster.reproject_raster(str(source), str(out), target_crs="EPSG:4326",
                            resampling="nearest")

    manifest = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    shift = manifest["crs_decisions"].get("transformation")
    assert shift is not None, (
        "reproject_raster recorded the two CRS labels and nothing about the "
        "operation between them - which is trap 021 with our name on it"
    )
    assert shift["is_ballpark"] is True

    named = {c["name"]: c for c in manifest["verification"]}
    assert named["crs_matches"]["passed"] is True, (
        "the point of the trap: the output really is in the CRS that was asked for"
    )
    shifted = named["x-mapsmith:datum_shift_applied"]
    assert shifted["passed"] is False
    assert shifted.get("critical") is not True, (
        "a ballpark is legitimate when the caller knows the datums coincide; "
        "refusing would break them. Saying nothing is what this fixes."
    )
    assert any("ballpark" in n.lower() for n in manifest.get("notes", [])), (
        "the note is where a human reads what happened"
    )


def test_buffering_a_geographic_layer_records_the_round_trip_it_makes(tmp_path):
    """The branch four operations take, that no fixture had ever taken.

    `x-mapsmith:round_trip` was written on 2026-09-06 and until this test
    nothing touched it: no test named it, and none of the fifty-eight records
    the conformance sweep collects contained it, because every fixture hands
    its operation inputs that already share a projected CRS. The declaration
    ratchet checks that the key is declared, not that the record it produces
    has a shape anyone has seen. A vocabulary entry for a claim no test has
    read is the same thing as no entry.

    NAD27 on purpose. `estimate_utm_crs()` answers with a **WGS 84** zone
    whatever the input's datum is, so this layer crosses a datum on the way out
    and again on the way back -- about seven metres each way, and the two legs
    largely cancel over one feature. That cancellation is exactly why the round
    trip went unrecorded for so long, and stating it is what the key is for.
    """
    gpd = pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    from shapely.geometry import Point

    from mapsmith.engines import vector
    from mapsmith.provenance import ROUND_TRIP

    source = tmp_path / "wells.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(-93.10, 34.50), Point(-93.00, 34.60)],
        crs="EPSG:4267",
    ).to_file(source, driver="GPKG")

    out = tmp_path / "buffered.gpkg"
    vector.buffer(str(source), 100.0, str(out))

    manifest = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    decisions = manifest["crs_decisions"]

    trip = decisions.get(ROUND_TRIP)
    assert trip is not None, (
        "the operation went out to an estimated UTM zone and came back, and the "
        f"manifest said nothing about the trip: {sorted(decisions)}"
    )
    # Deliberately NOT asserting an `output_crs` inside this object: section 3.7
    # says the output CRS belongs in `output`, and a claim about a file written
    # by code that has not written it yet is false on every failing path. The
    # CRS the output really ended in is checked below, from the file.
    assert decisions["analysis_crs"] != "EPSG:4267", (
        "a trip that ends where it started is not the thing this key records"
    )

    # BOTH legs, each measured. Until 2026-09-07 the record carried the outbound
    # one and `"applied_twice": True` -- a constant that called an operation and
    # its inverse the same operation. They are not: the way back carries `+inv`.
    outbound = trip["transformation"]
    inbound = trip["return_transformation"]
    for leg, shift in (("outbound", outbound), ("return", inbound)):
        assert shift["is_ballpark"] is False, (
            f"PROJ has a real operation for this pair; if the {leg} leg ever "
            "reports a ballpark the seven metres stopped being applied, and the "
            f"record has to say so: {shift}"
        )
        assert shift["accuracy_m"] and shift["accuracy_m"] > 0, (
            f"the {leg} leg crossed a datum and the record prices it at "
            f"nothing: {shift}"
        )
    # For NAD27 PROJ reports no pipeline string either way, so this fixture
    # cannot show that the legs are distinct operations. A pair where it does
    # can, and it is the pair in the README's example manifest: the way back
    # carries `+inv`. That is the evidence `applied_twice` was a description and
    # not a measurement -- it called an operation and its inverse the same one.
    from types import SimpleNamespace

    from mapsmith.provenance import record_round_trip

    scratch = SimpleNamespace(crs_decisions={})
    record_round_trip(scratch, "EPSG:32632", "EPSG:4326")
    legs = scratch.crs_decisions[ROUND_TRIP]
    assert legs["transformation"]["pipeline"] != legs["return_transformation"]["pipeline"], (
        "the two legs were asked of PROJ separately, so where it names them at "
        f"all they must not come back identical: {legs}"
    )
    assert "+inv" in legs["return_transformation"]["pipeline"], legs

    assert gpd.read_file(out).crs.to_epsg() == 4267, (
        "the output has to come back in the caller's CRS, or the key describes "
        "a trip that did not end where it claims"
    )


def _transforming_functions() -> dict[str, set[str]]:
    """Public engine functions that hand two CRSs to PROJ, derived from source.

    Derived rather than listed, for the reason 2026-09-02 made expensive four
    times over: a hand-written list is worth exactly what somebody remembered to
    put in it, and stops guarding the moment a new operation is added.
    """
    # Functions anywhere in the package that put a `transformation` key into a
    # dictionary. Derived, because "records the transformation" stopped meaning
    # "contains the word" the moment the recording was factored into a helper --
    # which is the ordinary thing to do with a decision made in nine places, and
    # it silently un-recorded five operations that had just been wired up. Same
    # shape as 2026-09-05, when extracting a check name into a constant removed
    # it from the vocabulary rule: the fix belongs in the derivation.
    recorders: set[str] = set()
    for path in sorted(ENGINES.parent.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            writes_key = any(
                isinstance(key, ast.Constant) and key.value == "transformation"
                for inner in ast.walk(node)
                if isinstance(inner, ast.Dict)
                for key in inner.keys
                if key is not None
            ) or any(
                isinstance(target, ast.Subscript)
                and isinstance(target.slice, ast.Constant)
                and target.slice.value == "transformation"
                for inner in ast.walk(node)
                if isinstance(inner, ast.Assign)
                for target in inner.targets
            )
            if writes_key:
                recorders.add(node.name)
    assert "alignment_decisions" in recorders, (
        "the derivation of what counts as recording found nothing that records - "
        f"it matched {sorted(recorders)}"
    )

    found: dict[str, set[str]] = {}
    reprojecting: dict[str, set[str]] = {}
    calls: dict[str, dict[str, set[str | None]]] = {}
    recorded_here: dict[tuple[str, str], bool] = {}
    for path in sorted(ENGINES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            # Private functions are NOT exempt, and skipping them was a hole with
            # two occupants: `_geodesic_areas` and `_geodesic_lengths` both cross
            # a datum with `to_crs("EPSG:4326")` and record nothing. A helper is
            # where a decision goes to stop being visible, which is the reason
            # the sweep above learned to follow them.
            reprojects = any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr == "to_crs"
                for inner in ast.walk(node)
            )
            # Silence is reprojecting WITHOUT recording, and the first version of
            # this derivation only saw the first half. So the ratchet could never
            # tighten for any of the twenty-one: wiring one of them up does not
            # remove its `to_crs` call, and it stayed on the list. A list that
            # cannot shrink is a list, not a ratchet, whatever its comment says --
            # and this one carried the sentence "it is a ratchet, not a
            # permission" while being unable to move in the direction it named.
            records = any(
                isinstance(inner, ast.Constant) and inner.value == "transformation"
                for inner in ast.walk(node)
            ) or any(
                isinstance(inner, ast.Call)
                and (
                    inner.func.attr
                    if isinstance(inner.func, ast.Attribute)
                    else getattr(inner.func, "id", None)
                )
                in recorders
                for inner in ast.walk(node)
            )
            if reprojects:
                reprojecting.setdefault(path.name, set()).add(node.name)
            if reprojects and not records:
                found.setdefault(path.name, set()).add(node.name)
            calls.setdefault(path.name, {})[node.name] = {
                (inner.func.attr if isinstance(inner.func, ast.Attribute)
                 else getattr(inner.func, "id", None))
                for inner in ast.walk(node)
                if isinstance(inner, ast.Call)
            }
            recorded_here[(path.name, node.name)] = records

    # A private helper that reprojects is not silent if every public function
    # that calls it records. It computes the transformation and hands it up --
    # `_geodesic_areas` and `_geodesic_lengths` do exactly that -- and the
    # operation writes it. Judging the helper alone was wrong in both
    # directions: the first version exempted every private function outright,
    # which hid these two for weeks; judging them in isolation calls them
    # silent when the record is complete.
    for module, functions in calls.items():
        for name in list(found.get(module, set())):
            if not name.startswith("_"):
                continue
            callers = [
                caller for caller, called in functions.items()
                if name in called and not caller.startswith("_")
            ]
            if callers and all(recorded_here.get((module, c)) for c in callers):
                found[module].discard(name)
        if not found.get(module):
            found.pop(module, None)
    return found, reprojecting


# Measured on 2026-09-03. These reproject a layer internally to align it with
# another CRS and do not yet record the operation, so a ballpark inside them is
# still silent. The list may only SHRINK: it is a ratchet, not a permission.
# `datum.default_operation` and `datum.best_operation` are the two answers; the
# work is wiring each call site to the one that matches who chooses.
STILL_SILENT: dict[str, set[str]] = {
    # EMPTY, as of 2026-09-06 — and it took the whole day to get here from
    # twenty-one. Every operation that hands two coordinate systems to PROJ now
    # records what PROJ will do with them, so a ballpark inside one of them is
    # a fact in the record instead of tens of metres nobody mentioned.
    #
    # The order they came off, because the shapes are the interesting part:
    # `linework` (3) and then five of `vector` bring a secondary input to the
    # analysis CRS; four more of `vector` compute in an estimated UTM zone and
    # come back, which is where `estimate_utm_crs()` turned out to answer in
    # WGS 84 whatever the input's datum is — seven metres out and seven back on
    # NAD27, cancelling, unmentioned; `sampling` (2) is the raster-alignment
    # shape; `summaries` (2) write no manifest at all, so their ANSWER became
    # the record, which matters because in `nearest_neighbour_index` the
    # reprojected boundary IS the study area that R is computed from; and the
    # last five are raster and third-party engines.
    #
    # **Do not add to this dictionary.** It is the ratchet's memory of work
    # finished, and the assertion below says a new silent operation is a defect
    # rather than a new entry here.
    # `sampling.py` came off on 2026-09-06: both operations bring a vector input
    # onto the raster's CRS, which is the same shape as the five in `vector.py`
    # and now the same helper.
    # `summaries.py` came off on 2026-09-06, and these two are the case that
    # needed thinking about: they write no manifest, so there was nowhere to
    # record a CRS decision. The answer is the record for them, the way it is
    # for `locate_extreme_cell` and its registration. Worth the trouble because
    # in `nearest_neighbour_index` the reprojected boundary IS the study area,
    # density is n/area, and R is a ratio built on density -- a ballpark there
    # moves the verdict between clustered, random and evenly spread.
    # `vector.py` came off entirely on 2026-09-06, all nine, in two shapes.
    # Five bring a secondary input to the analysis CRS; four compute in an
    # estimated UTM zone and write the output back where it came from. The
    # round trip is the one that was worth finding: `estimate_utm_crs()`
    # answers with a WGS 84 zone whatever the input's datum is, so buffering a
    # NAD27 layer crosses a datum on the way out and again on the way back --
    # seven metres each way, largely cancelling, and unmentioned.
}


def test_no_new_operation_transforms_coordinates_in_silence():
    """A ratchet over the operations that still reproject without recording.

    **The list is empty as of 2026-09-06**, and getting there broke the guard's
    own sanity check, which is worth writing down. It asserted `found` was
    non-empty, because a derivation that matches nothing passes every subset
    test ever written — the failure this suite spent 2026-09-02 finding in four
    disguises. But `found` is *the silent ones*, and an empty `found` is the
    goal. The check could not tell "the derivation broke" from "the work is
    done", so it fired on success.

    Two questions now, because they were always two: **does the derivation
    still see anything at all** (asked of the reprojecting functions, which
    stay in the dozens), and **is any of them silent** (asked of `found`, which
    should stay empty forever).
    """
    found, reprojecting = _transforming_functions()
    assert reprojecting, (
        "the derivation matched no call sites at all - `.to_crs` was renamed or "
        "the engines moved, and this guard is now vacuous"
    )
    assert sum(len(names) for names in reprojecting.values()) >= 15, (
        f"only {sum(len(n) for n in reprojecting.values())} reprojecting functions "
        "found, where there were twenty-one this morning: the derivation is seeing "
        "less than it did, which is how a guard goes quiet without going red"
    )
    new = {
        module: sorted(names - STILL_SILENT.get(module, set()))
        for module, names in found.items()
        if names - STILL_SILENT.get(module, set())
    }
    assert not new, (
        f"these operations reproject without recording the transformation: {new}. "
        "Wire them to datum.best_operation (the caller chooses) or "
        "datum.default_operation (the engine chooses), and record it under "
        "crs_decisions.transformation - do not add them to STILL_SILENT."
    )
    gone = {
        module: sorted(names - found.get(module, set()))
        for module, names in STILL_SILENT.items()
        if names - found.get(module, set())
    }
    assert not gone, (
        f"these are listed as silent but no longer reproject: {gone}. "
        "Remove them from STILL_SILENT - a ratchet that is not tightened is a list."
    )


def test_a_round_trip_that_never_came_home_is_not_recorded_as_one(tmp_path, monkeypatch):
    """The audit trail survives the error; the claim inside it must not.

    Invariant 3 says verification is recorded before a critical failure raises,
    so the diagnosis outlives the crash. `x-mapsmith:round_trip` used to be
    written by `alignment_decisions`, which three of the four callers invoke
    *before* the return leg runs -- and the return leg runs inside
    `audit_on_failure`. So a `to_crs` that raised on the way back produced a
    manifest asserting a trip that never completed: the mechanism that keeps the
    audit trail honest, carrying a sentence that had become false.

    `buffer_layer` was the only one with the right order, and it was right by
    accident: the Esri branch forced the assignment down the function, not a
    thought about the error path. That is why this test drives all four.

    The sabotage is the return leg itself, so the failure is the one the defect
    needs: the outbound trip happens, the work happens, and only the way home
    raises.
    """
    gpd = pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    from shapely.geometry import Point

    from mapsmith.engines import vector
    from mapsmith.provenance import ROUND_TRIP

    left = tmp_path / "wells.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(-104.9, 39.7), Point(-104.8, 39.8)],
        crs="EPSG:4267",
    ).to_file(left, layer="wells", driver="GPKG")
    right = tmp_path / "towns.gpkg"
    gpd.GeoDataFrame(
        {"town": ["x"]}, geometry=[Point(-104.85, 39.75)], crs="EPSG:4267"
    ).to_file(right, layer="towns", driver="GPKG")

    real_to_crs = gpd.GeoDataFrame.to_crs

    def to_crs_that_never_returns(self, crs=None, *args, **kwargs):
        # The RETURN leg only: the one heading back to the caller's geographic
        # CRS. The way out has to succeed, or the trip is never claimed at all
        # and there is nothing for this test to catch.
        target = crs if crs is not None else kwargs.get("crs")
        if target is not None and str(target).endswith("4267"):
            raise RuntimeError("the way back failed")
        return real_to_crs(self, crs, *args, **kwargs)

    monkeypatch.setattr(gpd.GeoDataFrame, "to_crs", to_crs_that_never_returns)

    cases = [
        ("buffer", lambda out: vector.buffer(str(left), 50.0, str(out))),
        ("simplify", lambda out: vector.simplify(str(left), 1.0, str(out))),
        ("centroid", lambda out: vector.centroid(str(left), str(out))),
        ("nearest_join", lambda out: vector.nearest_join(
            str(left), str(right), str(out))),
    ]
    audited = []
    for name, call in cases:
        destination = tmp_path / f"{name}.gpkg"
        # `RuntimeError` and not `Exception`: the first version of this test
        # asked for `Exception` and swallowed three `AttributeError`s, because
        # three of the four function names in it were wrong. It drove one
        # operation and passed anyway -- including with the defect put back.
        # The sabotage caught that; reading the green did not.
        with pytest.raises(RuntimeError, match="the way back failed"):
            call(destination)
        manifest_path = destination.with_suffix(
            destination.suffix + ".provenance.json"
        )
        if not manifest_path.exists():
            # An operation can fail before its audit opens: there is no record
            # there, so there is no claim to contradict.
            continue
        audited.append(name)
        written = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert ROUND_TRIP not in written.get("crs_decisions", {}), (
            f"{name}: the return leg raised and the manifest still claims a "
            f"completed round trip: {written['crs_decisions'][ROUND_TRIP]}"
        )
    # Three of the four write a manifest on the failing path, and they are the
    # three that had the wrong order. The count is asserted because on a day it
    # dropped, this test would keep passing while guarding less.
    assert len(audited) >= 3, (
        f"only {audited} reached their own audit on the way back: the sabotage "
        "is landing too early and this test guards less than it claims"
    )


def test_a_reprojection_that_raised_does_not_claim_the_coordinates_moved(
    tmp_path, monkeypatch
):
    """`reproject_layer` had the defect its three siblings were fixed for.

    Found by the `conformita-manifest` agent on 2026-09-23, straight after the
    round-trip fix, by asking the question that fix left open: is any other key
    assigned before the fact it asserts? One was. `target_crs` and
    `transformation` were written before the `with audit_on_failure`, while the
    coordinates only move inside it -- so a `_transformed` that raised left a
    manifest reporting `target_crs: EPSG:4326` and a seven-metre transformation
    beside geometry that had not gone anywhere.

    Section 3.7 defines `target_crs` as "the coordinate system they were put
    into". Nothing was put anywhere. `x-mapsmith:operation_completed` comes back
    false in that record, which a careful consumer sees -- and that mitigation
    was judged insufficient for the round trip this morning, so it is
    insufficient here.

    `source_crs`, `reason` and `analysis_crs` stay where they were: they are
    true before anything moves, and a failed run still needs them to be
    diagnosable.
    """
    gpd = pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    from shapely.geometry import Point

    from mapsmith.engines import vector

    source = tmp_path / "points.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a"]}, geometry=[Point(-104.9, 39.7)], crs="EPSG:4267"
    ).to_file(source, layer="points", driver="GPKG")

    def transform_that_fails(geometry, transformer):
        raise RuntimeError("the transform failed")

    monkeypatch.setattr(vector, "_transformed", transform_that_fails)

    out = tmp_path / "out.gpkg"
    with pytest.raises(RuntimeError, match="the transform failed"):
        vector.reproject(str(source), "EPSG:4326", str(out))

    manifest_path = out.with_suffix(out.suffix + ".provenance.json")
    assert manifest_path.exists(), (
        "audit_on_failure must still write the record: the diagnosis outliving "
        "the error is invariant 3, and this test is about what the record says, "
        "not about whether it exists"
    )
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    decisions = written["crs_decisions"]
    for claim in ("target_crs", "transformation"):
        assert claim not in decisions, (
            f"the transform raised and the manifest still reports {claim!r}: "
            f"{decisions[claim]}"
        )
    assert decisions["source_crs"] == "EPSG:4267", (
        "what was true before the attempt has to survive it, or a failed run "
        f"cannot be diagnosed: {decisions}"
    )
    assert not [n for n in written.get("notes", []) if "were carried across" in n], (
        "the ballpark note says the coordinates were carried across; on a run "
        "where nothing was carried anywhere it is the same false claim in prose"
    )


def test_every_operation_that_travels_records_the_trip(tmp_path):
    """All four callers of `record_round_trip`, on the branch that travels.

    The `conformita-manifest` agent measured, on 2026-09-23, that across the
    whole suite `record_round_trip` was reached by two of the four: `buffer`,
    through the test above, and `centroid`, through the conformance sweep.
    `simplify` and `nearest_join` reached it from nowhere.

    That mattered because of what the sibling test checks. It drives all four,
    but on a path where the return leg raises, so the call never runs and the
    assertion is about the key being ABSENT -- which stays true if somebody
    deletes the call. Two of the three operations that actually had the wrong
    order had no test that the key is written at all.

    So this is the positive half, and the two halves together pin the contract:
    the key appears when the output came home, and does not when it did not.
    """
    gpd = pytest.importorskip("geopandas")
    pytest.importorskip("shapely")
    from shapely.geometry import Point

    from mapsmith.engines import vector
    from mapsmith.provenance import ROUND_TRIP

    left = tmp_path / "wells.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(-93.10, 34.50), Point(-93.00, 34.60)],
        crs="EPSG:4267",
    ).to_file(left, layer="wells", driver="GPKG")
    right = tmp_path / "towns.gpkg"
    gpd.GeoDataFrame(
        {"town": ["x"]}, geometry=[Point(-93.05, 34.55)], crs="EPSG:4267"
    ).to_file(right, layer="towns", driver="GPKG")

    cases = [
        ("buffer", lambda out: vector.buffer(str(left), 100.0, str(out))),
        ("simplify", lambda out: vector.simplify(str(left), 1.0, str(out))),
        ("centroid", lambda out: vector.centroid(str(left), str(out))),
        ("nearest_join", lambda out: vector.nearest_join(
            str(left), str(right), str(out))),
    ]
    for name, call in cases:
        out = tmp_path / f"{name}.gpkg"
        call(out)
        manifest = json.loads(
            Path(f"{out}.provenance.json").read_text(encoding="utf-8")
        )
        trip = manifest["crs_decisions"].get(ROUND_TRIP)
        assert trip is not None, (
            f"{name} went out to an estimated UTM zone and came back in the "
            "caller's CRS, and its manifest says nothing about the trip: "
            f"{sorted(manifest['crs_decisions'])}"
        )
        assert set(trip) == {"transformation", "return_transformation"}, (
            f"{name}: both legs, and only the legs, belong in this key: {trip}"
        )
        assert gpd.read_file(out).crs.to_epsg() == 4267, (
            f"{name}: the output has to come back in the caller's CRS, or the "
            "key describes a trip that did not end where it claims"
        )


def test_keys_of_ours_inside_the_round_trip_legs_carry_the_prefix(tmp_path):
    """The prefix rule, inside the two legs of `round_trip`, on a run that fills them.

    Both legs are `transformation` objects, which the specification defines, so
    a key of ours in either has to be spelled `x-mapsmith:<name>` and declared.
    The conformance sweep checks that, but on its own records only one
    operation makes the trip, and none produces a leg carrying a key of ours --
    so the check over the legs had nothing to look at. Sabotaging the spelling
    of `x-mapsmith:chosen_by` was caught, but by the TOP-LEVEL check on
    `reproject_raster`, which proves nothing about the legs.

    NAD27 outside its area of use does fill them: PROJ picks the operation, so
    both legs carry `x-mapsmith:chosen_by`. The premise is asserted first, so a
    day when the legs stop carrying it is a failure here and not a pass over
    nothing.
    """
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Point

    from mapsmith.engines import vector
    from mapsmith.provenance import ROUND_TRIP, TRANSFORMATION_EXTENSIONS

    source = tmp_path / "outside_nad27.gpkg"
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(9.0, 45.0)], crs="EPSG:4267"
    ).to_file(source, driver="GPKG")
    out = tmp_path / "buffered.gpkg"
    vector.buffer(str(source), 100.0, str(out))
    record = json.loads(Path(f"{out}.provenance.json").read_text(encoding="utf-8"))
    trip = record["crs_decisions"][ROUND_TRIP]

    spec_keys = {"pipeline", "accuracy_m", "is_ballpark", "better_available_m"}
    # The premise is "the legs hold something beyond the specification's keys",
    # and NOT "a key starting with x-": the first version asked for the prefix,
    # so a sabotage that dropped it emptied the premise and failed there -- red,
    # for the wrong reason, which is the reading D-079 warns against.
    beyond = [key for leg in trip.values() for key in leg if key not in spec_keys]
    assert beyond, (
        "neither leg carries a key beyond the specification's, so this test "
        f"checks nothing: {trip}"
    )
    for leg_name, leg in trip.items():
        for key in leg:
            assert key in spec_keys or (
                key.startswith("x-mapsmith:") and key in TRANSFORMATION_EXTENSIONS
            ), (
                f"`crs_decisions.{ROUND_TRIP}.{leg_name}.{key}`: the legs are "
                "specification objects, so a key of ours needs the prefix and a "
                "declaration in `provenance.TRANSFORMATION_EXTENSIONS`"
            )
