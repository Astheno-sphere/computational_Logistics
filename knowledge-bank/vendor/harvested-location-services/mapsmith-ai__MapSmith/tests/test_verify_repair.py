"""Preconditions, empty-result detection and bounded deterministic repair (#3).

Benchmark evidence (docs/benchmarks.md) puts the bulk of GIS-agent failures at
execution time rather than at plan time: parameters that are wrong in ways a
plan cannot show, and outputs that exist but mean nothing. These tests pin the
two behaviours that address it — a named, hinted check instead of silent
success, and mechanical repair that is recorded rather than hidden.
"""

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from mapsmith import verify
from mapsmith.engines import vector


def _gdf(geoms, crs="EPSG:32632"):
    return gpd.GeoDataFrame({"id": range(len(geoms))}, geometry=list(geoms), crs=crs)


# --- preconditions ---------------------------------------------------------

def test_empty_input_is_named_with_a_hint():
    checks = verify.verify_loaded_inputs("clip_layer", input_path=_gdf([]))
    empty = next(c for c in checks if c.name == "input_not_empty")
    assert empty.passed is False
    assert "no features" in empty.hint
    assert empty.critical is False  # the operation may legitimately run


def test_disjoint_extents_are_detected_before_running():
    left = _gdf([Point(0, 0).buffer(1)])
    right = _gdf([Point(1000, 1000).buffer(1)])
    checks = verify.verify_input_pairs("spatial_join", left_path=left, right_path=right)
    overlap = next(c for c in checks if c.name == "inputs_may_intersect")
    assert overlap.passed is False
    assert "do not overlap" in overlap.hint


def test_overlapping_extents_pass_without_a_hint():
    a = _gdf([Point(0, 0).buffer(10)])
    b = _gdf([Point(5, 5).buffer(10)])
    checks = verify.verify_input_pairs("clip_layer", input_path=a, mask_path=b)
    overlap = next(c for c in checks if c.name == "inputs_may_intersect")
    assert overlap.passed is True
    assert overlap.hint is None


# --- empty results are reported, not passed off as success ------------------

def test_empty_result_check_fires_on_empty_output(tmp_path):
    out = tmp_path / "empty.parquet"
    _gdf([]).to_parquet(out)
    checks = verify.verify_vector_output(str(out), on_empty="fail")
    result = next(c for c in checks if c.name == "result_not_empty")
    assert result.passed is False and result.critical is True
    assert "matched nothing" in result.hint


def test_clip_with_disjoint_mask_warns_instead_of_passing_silently(tmp_path):
    """The classic silent failure: a clip whose inputs cannot overlap writes an
    empty layer and reports success. An empty clip is legitimate (extents can
    overlap while geometries miss), so it must not raise — but the agent has to
    SEE it, in the result and in the manifest."""
    import json

    src = tmp_path / "src.parquet"
    mask = tmp_path / "mask.parquet"
    out = tmp_path / "out.parquet"
    _gdf([Point(0, 0).buffer(1)]).to_parquet(src)
    _gdf([Point(500, 500).buffer(1)]).to_parquet(mask)

    result = vector.clip(str(src), str(mask), str(out))

    assert result["feature_count"] == 0
    warned = {w["check"] for w in result["warnings"]}
    assert {"inputs_may_intersect", "result_not_empty"} <= warned
    assert any("do not overlap" in (w["hint"] or "") for w in result["warnings"])

    manifest = json.loads((tmp_path / "out.parquet.provenance.json").read_text(encoding="utf-8"))
    recorded = {c["name"] for c in manifest["verification"]}
    assert {"inputs_may_intersect", "result_not_empty"} <= recorded


def test_successful_clip_reports_no_warnings(tmp_path):
    src = tmp_path / "src.parquet"
    mask = tmp_path / "mask.parquet"
    out = tmp_path / "out.parquet"
    _gdf([Point(0, 0).buffer(5)]).to_parquet(src)
    _gdf([Point(0, 0).buffer(10)]).to_parquet(mask)

    result = vector.clip(str(src), str(mask), str(out))
    assert result["feature_count"] == 1
    assert "warnings" not in result


def test_empty_result_is_critical_only_under_the_fail_policy(tmp_path):
    """The two policies must not be conflated: same empty output, different
    verdict depending on whether emptiness was possible at all."""
    out = tmp_path / "empty.parquet"
    _gdf([]).to_parquet(out)

    failing = verify.verify_vector_output(str(out), on_empty="fail")
    warning = verify.verify_vector_output(str(out), on_empty="warn")
    ignored = verify.verify_vector_output(str(out), on_empty="ignore")

    assert next(c for c in failing if c.name == "result_not_empty").critical is True
    assert next(c for c in warning if c.name == "result_not_empty").critical is False
    assert not any(c.name == "result_not_empty" for c in ignored)


def test_unknown_on_empty_policy_is_rejected(tmp_path):
    out = tmp_path / "x.parquet"
    _gdf([Point(0, 0).buffer(1)]).to_parquet(out)
    with pytest.raises(ValueError, match="on_empty"):
        verify.verify_vector_output(str(out), on_empty="maybe")


# --- bounded deterministic repair ------------------------------------------

def _bowtie() -> Polygon:
    """Self-intersecting polygon: invalid, and make_valid() fixes it."""
    return Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])


def test_repair_fixes_invalid_geometry_and_records_the_attempt(tmp_path):
    out = tmp_path / "invalid.parquet"
    _gdf([_bowtie()]).to_parquet(out)

    def checks():
        return verify.verify_vector_output(str(out))

    before = checks()
    assert not next(c for c in before if c.name == "geometry_valid").passed

    after, attempts = verify.repair_and_reverify(
        str(out), before, operation="test", reverify=checks
    )
    assert next(c for c in after if c.name == "geometry_valid").passed
    assert len(attempts) == 1
    assert attempts[0]["check"] == "geometry_valid"
    assert attempts[0]["resolved"] is True
    assert "make_valid" in attempts[0]["action"]


def test_repair_is_bounded_and_never_loops(tmp_path):
    """A check with no registered repair is left alone: no attempts, no loop."""
    out = tmp_path / "wrong_crs.parquet"
    _gdf([Point(0, 0).buffer(1)], crs="EPSG:32632").to_parquet(out)

    def checks():
        return verify.verify_vector_output(str(out), expect_crs="EPSG:4326")

    after, attempts = verify.repair_and_reverify(
        str(out), checks(), operation="test", reverify=checks
    )
    assert attempts == []
    assert not next(c for c in after if c.name == "crs_matches").passed


def test_clean_output_needs_no_repair(tmp_path):
    out = tmp_path / "clean.parquet"
    _gdf([Point(0, 0).buffer(1)]).to_parquet(out)

    def checks():
        return verify.verify_vector_output(str(out))

    after, attempts = verify.repair_and_reverify(
        str(out), checks(), operation="test", reverify=checks
    )
    assert attempts == []
    assert all(c.passed for c in after if c.critical)


# --- failures carry their hints into the error ------------------------------

def test_enforce_includes_hints_in_the_message():
    failed = verify.Check("result_not_empty", False, "0 features", hint="Check the extents.")
    with pytest.raises(verify.VerificationError, match="Check the extents."):
        verify.enforce([failed], "clip_layer")


# --- the bound itself, and the two ways repair could destroy data -----------

def test_repair_stops_after_max_rounds_when_it_never_converges(tmp_path, monkeypatch):
    """The bound is the property the feature is named for: a repair that does
    not fix anything must stop at MAX_REPAIR_ROUNDS, not spin."""
    out = tmp_path / "stubborn.parquet"
    _gdf([_bowtie()]).to_parquet(out)
    calls = []

    def useless_repair(path):
        calls.append(path)
        return "pretended to repair"

    monkeypatch.setitem(verify._REPAIRS, "geometry_valid", useless_repair)

    def checks():  # never improves
        return [verify.Check("geometry_valid", False, "still invalid")]

    final, attempts = verify.repair_and_reverify(
        str(out), checks(), operation="test", reverify=checks
    )
    assert len(calls) == verify.MAX_REPAIR_ROUNDS == 2
    assert len(attempts) == 2
    assert [a["x-mapsmith:round"] for a in attempts] == [1, 2]
    assert all(a["resolved"] is False for a in attempts)
    assert not final[0].passed


def test_failed_repair_is_recorded_and_the_output_survives(tmp_path):
    """A repair that cannot run must leave the file exactly as it was — GDAL
    truncates before writing, so repairing in place would destroy user data."""
    out = tmp_path / "invalid.shp"
    _gdf([_bowtie()]).to_file(out)
    before = out.read_bytes()

    def checks():
        return verify.verify_vector_output(str(out))

    final, attempts = verify.repair_and_reverify(
        str(out), checks(), operation="test", reverify=checks
    )
    assert len(attempts) == 1
    assert attempts[0]["action"] is None
    assert "not a single-file format" in attempts[0]["error"]
    assert attempts[0]["resolved"] is False
    assert out.read_bytes() == before, "the output must be byte-identical"
    # the defect is reported honestly rather than claimed as fixed
    assert not next(c for c in final if c.name == "geometry_valid").passed


def test_repair_targets_the_real_geometry_column(tmp_path):
    """Engines and ogr2ogr often name the active column 'geom'. Touching
    'geometry' instead would leave the defect in place while the manifest
    claimed a repair — a false audit entry, the worst possible bug here."""
    out = tmp_path / "geom_named.parquet"
    gdf = _gdf([_bowtie()]).rename_geometry("geom")
    gdf.to_parquet(out)

    def checks():
        return verify.verify_vector_output(str(out))

    final, attempts = verify.repair_and_reverify(
        str(out), checks(), operation="test", reverify=checks
    )
    assert "geom" in attempts[0]["action"]
    assert attempts[0]["resolved"] is True
    assert next(c for c in final if c.name == "geometry_valid").passed

    written = gpd.read_parquet(out)
    assert written.geometry.name == "geom"
    assert list(written.columns) == list(gdf.columns), "schema must be preserved"


def test_repair_preserves_the_geopackage_layer_name(tmp_path):
    out = tmp_path / "data.gpkg"
    _gdf([_bowtie()]).to_file(out, layer="zones", driver="GPKG")

    def checks():
        return verify.verify_vector_output(str(out))

    verify.repair_and_reverify(str(out), checks(), operation="test", reverify=checks)

    from pyogrio import list_layers

    assert [str(row[0]) for row in list_layers(out)] == ["zones"]


def test_repair_refuses_a_container_whose_layers_cannot_be_listed(tmp_path, monkeypatch):
    """Fail closed on "I do not know what is in this file".

    The multi-layer refusal only protects the case where listing *works*. When
    the probe fails, an unlistable container used to look like a single-layer
    one and the repair rewrote it — destroying layers this operation never read
    while recording success. The guard for that existed but was unreachable,
    because the probe reported failure as an empty list; this test is what makes
    the distinction between "no layers" and "unknown layers" load-bearing.
    """
    out = tmp_path / "data.gpkg"
    _gdf([_bowtie()]).to_file(out, layer="zones", driver="GPKG")
    before = verify.verify_vector_output(str(out))
    assert not next(c for c in before if c.name == "geometry_valid").passed

    import pyogrio

    def refuse(*args, **kwargs):
        raise RuntimeError("driver unavailable")

    monkeypatch.setattr(pyogrio, "list_layers", refuse)
    assert verify._gpkg_layers(str(out)) is None

    with pytest.raises(ValueError, match="could not be listed"):
        verify._repair_invalid_geometry(str(out))

    # and the file is untouched: no temp file left behind, geometry still invalid
    assert [p.name for p in tmp_path.iterdir()] == ["data.gpkg"]


def test_enforce_names_the_repair_when_one_was_attempted():
    failed = [verify.Check("geometry_types", False, "got GeometryCollection")]
    repairs = [{"check": "geometry_valid", "action": "make_valid()", "resolved": True}]
    with pytest.raises(verify.VerificationError, match="already attempted"):
        verify.enforce(failed, "reproject_layer", repairs)


# --- CRS preconditions: the promise the manifesto makes ---------------------

def test_missing_crs_is_a_critical_precondition():
    checks = verify.verify_loaded_inputs("clip_layer", input_path=_gdf([Point(0, 0)], crs=None))
    crs = next(c for c in checks if c.name == "input_crs_present")
    assert crs.passed is False and crs.critical is True
    assert "no coordinate reference system" in crs.hint


def test_reproject_refuses_a_crs_less_input_with_a_useful_message(tmp_path):
    src = tmp_path / "naive.parquet"
    out = tmp_path / "out.parquet"
    _gdf([Point(0, 0).buffer(1)], crs=None).to_parquet(src)

    with pytest.raises(verify.VerificationError, match="input_crs_present"):
        vector.reproject(str(src), "EPSG:4326", str(out))
    assert (tmp_path / "out.parquet.provenance.json").exists()


def test_extents_are_not_compared_across_coordinate_systems():
    a = _gdf([Point(0, 0).buffer(1)], crs="EPSG:32632")
    b = _gdf([Point(0, 0).buffer(1)], crs="EPSG:4326")
    checks = verify.verify_input_pairs("spatial_join", left_path=a, right_path=b)
    assert not any(c.name == "inputs_may_intersect" for c in checks)
    comparable = next(c for c in checks if c.name == "inputs_share_crs")
    assert comparable.passed is False and comparable.critical is False


def test_all_input_pairs_are_checked_not_just_the_first_two():
    a = _gdf([Point(0, 0).buffer(1)])
    b = _gdf([Point(1, 1).buffer(1)])
    c = _gdf([Point(9000, 9000).buffer(1)])
    checks = verify.verify_input_pairs("op", a_path=a, b_path=b, c_path=c)
    pairs = [k for k in checks if k.name == "inputs_may_intersect"]
    assert len(pairs) == 3, "every pair must be checked, not only the first two"
    assert any(not k.passed for k in pairs), "the disjoint third input must be caught"


# --- total erosion: the wrong-parameter failure the benchmark pointed at ----

def test_total_erosion_is_flagged_with_a_hint(tmp_path):
    """A negative buffer larger than the features keeps every row and empties
    every geometry: verified=true with no explanation would be exactly the
    silent execution-time failure we set out to catch."""
    src = tmp_path / "src.parquet"
    out = tmp_path / "eroded.parquet"
    _gdf([Point(0, 0).buffer(5)]).to_parquet(src)

    result = vector.buffer(str(src), -50, str(out))
    # The check was renamed from `result_not_empty` to
    # `x-mapsmith:no_geometry_is_empty` on 2026-08-29: the core name means "the
    # output has at least one feature" and was being emitted twice with two
    # different meanings, which section 3.6 of the manifest spec forbids.
    hints = [
        w["hint"]
        for w in result["warnings"]
        if w["check"] == "x-mapsmith:no_geometry_is_empty"
    ]
    assert hints and "wrong sign or magnitude" in hints[0]


# --- the failures the review caught: they must not come back ---------------

def test_multi_layer_geopackage_is_never_rewritten(tmp_path):
    """Repairing a container would drop the layers this operation did not
    write — silent destruction of the user's project, with a manifest claiming
    a successful repair."""
    from pyogrio import list_layers

    gpkg = tmp_path / "project.gpkg"
    _gdf([_bowtie()]).to_file(gpkg, layer="zones", driver="GPKG")
    _gdf([Point(0, 0)]).to_file(gpkg, layer="wells", driver="GPKG", mode="a")
    before = {str(row[0]) for row in list_layers(gpkg)}
    assert before == {"zones", "wells"}

    def checks():
        return verify.verify_vector_output(str(gpkg))

    final, attempts = verify.repair_and_reverify(
        str(gpkg), checks(), operation="test", reverify=checks
    )
    assert attempts[0]["action"] is None
    assert "layers" in attempts[0]["error"]
    assert {str(row[0]) for row in list_layers(gpkg)} == before, "no layer may be lost"
    assert not next(c for c in final if c.name == "geometry_valid").passed


def test_verification_reads_the_layer_the_writer_wrote(tmp_path):
    """With several layers present, GDAL hands back the first one by default:
    verifying that would certify a layer the operation never touched."""
    gpkg = tmp_path / "out.gpkg"
    _gdf([Point(0, 0)], crs="EPSG:4326").to_file(gpkg, layer="aaa_other", driver="GPKG")
    _gdf([_bowtie()], crs="EPSG:32632").to_file(gpkg, layer="out", driver="GPKG", mode="a")

    checks = verify.verify_vector_output(str(gpkg), expect_crs="EPSG:32632")
    assert next(c for c in checks if c.name == "crs_matches").passed
    assert not next(c for c in checks if c.name == "geometry_valid").passed


@pytest.mark.parametrize("naive", ["input", "mask"])
def test_clip_refuses_a_crs_less_input_before_touching_pyproj(tmp_path, naive):
    """The CRS gate must run BEFORE the CRS alignment, or the raw pyproj error
    wins and the promise in the catalog is false."""
    src, mask, out = tmp_path / "s.parquet", tmp_path / "m.parquet", tmp_path / "o.parquet"
    _gdf([Point(0, 0).buffer(2)], crs=None if naive == "input" else "EPSG:32632").to_parquet(src)
    _gdf([Point(0, 0).buffer(5)], crs=None if naive == "mask" else "EPSG:32632").to_parquet(mask)

    with pytest.raises(verify.VerificationError, match="input_crs_present"):
        vector.clip(str(src), str(mask), str(out))
    assert (tmp_path / "o.parquet.provenance.json").exists()


def test_spatial_join_refuses_a_crs_less_input(tmp_path):
    left, right, out = tmp_path / "l.parquet", tmp_path / "r.parquet", tmp_path / "o.parquet"
    _gdf([Point(0, 0).buffer(2)], crs="EPSG:32632").to_parquet(left)
    _gdf([Point(0, 0)], crs=None).to_parquet(right)

    with pytest.raises(verify.VerificationError, match="input_crs_present"):
        vector.spatial_join(str(left), str(right), str(out))


def test_a_repair_is_reported_in_the_result_not_only_the_manifest(tmp_path):
    """MapSmith rewriting the user's geometry is exactly what must not live
    only in a file the agent has to go and read."""
    src, out = tmp_path / "inv.parquet", tmp_path / "out.parquet"
    _gdf([_bowtie()], crs="EPSG:32632").to_parquet(src)

    result = vector.reproject(str(src), "EPSG:3857", str(out))
    assert result["repairs"], "the result must say the output was repaired"
    assert result["repairs"][0]["check"] == "geometry_valid"
    assert result["repairs"][0]["resolved"] is True


def test_preconditions_survive_an_engine_crash(tmp_path):
    """The diagnosis is most valuable exactly when the engine blows up."""
    src, mask, out = tmp_path / "s.parquet", tmp_path / "m.parquet", tmp_path / "o.parquet"
    _gdf([_bowtie()], crs="EPSG:32632").to_parquet(src)
    _gdf([Point(0, 0).buffer(1)], crs="EPSG:32632").to_parquet(mask)

    import json

    with pytest.raises(Exception, match="(?i)topology|geos|precondition|verification"):
        vector.clip(str(src), str(mask), str(out))
    manifest = tmp_path / "o.parquet.provenance.json"
    assert manifest.exists(), "preconditions must reach disk even on a crash"
    names = {c["name"] for c in json.loads(manifest.read_text(encoding="utf-8"))["verification"]}
    assert "input_crs_present" in names


def test_checks_name_the_argument_they_are_about():
    """Two inputs produce two identically named checks: without the argument a
    consumer indexing the manifest by name collapses them."""
    a = _gdf([Point(0, 0).buffer(1)])
    b = _gdf([], crs="EPSG:32632")
    checks = verify.verify_loaded_inputs("clip_layer", input_path=a, mask_path=b)
    empties = {c.argument: c.passed for c in checks if c.name == "input_not_empty"}
    assert empties == {"input_path": True, "mask_path": False}
