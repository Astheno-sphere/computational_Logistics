"""Deterministic verification: checks recorded in manifests, critical failures raise."""

import json

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from conftest import (
    _EXTENSION_KEY,
    _SETTING_NAME,
    SPEC_OBJECTS_NOT_OURS,
    _spec_crs_keys,
    _spec_object_paths,
    _spec_problems,
    _spec_transformation_keys,
)
from mapsmith import verify
from mapsmith.engines import vector
from mapsmith.grid import DERIVED_ENVIRONMENT
from mapsmith.provenance import INPUTS_REPROJECTED, TRANSFORMATION_EXTENSIONS


@pytest.fixture()
def points_gpkg(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"name": ["a", "b"]},
        geometry=[Point(9.19, 45.46), Point(9.20, 45.47)],
        crs="EPSG:4326",
    )
    path = tmp_path / "points.gpkg"
    gdf.to_file(path)
    return path


def test_buffer_manifest_contains_passed_verification(points_gpkg, tmp_path):
    out = tmp_path / "buffered.gpkg"
    result = vector.buffer(str(points_gpkg), 250.0, str(out))
    assert result["verified"] is True
    manifest = json.loads((tmp_path / "buffered.gpkg.provenance.json").read_text())
    names = {c["name"] for c in manifest["verification"]}
    assert {"crs_present", "crs_matches", "geometry_valid", "feature_count_exact"} <= names
    assert all(c["passed"] for c in manifest["verification"])


def test_invalid_geometry_fails_critical_check(tmp_path):
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1)])  # self-intersecting
    gdf = gpd.GeoDataFrame({"id": [1]}, geometry=[bowtie], crs="EPSG:4326")
    path = tmp_path / "bowtie.gpkg"
    gdf.to_file(path)
    checks = verify.verify_vector_output(str(path))
    failed = [c for c in checks if c.name == "geometry_valid" and not c.passed]
    assert failed, "the invalid geometry must be detected"
    with pytest.raises(verify.VerificationError, match="geometry_valid"):
        verify.enforce(checks, "test_op")


def test_count_mismatch_raises(points_gpkg):
    checks = verify.verify_vector_output(str(points_gpkg), expect_count=99)
    with pytest.raises(verify.VerificationError, match="feature_count_exact"):
        verify.enforce(checks, "test_op")


def test_non_critical_failure_does_not_raise(points_gpkg):
    # extent check is non-critical: a failing bounds check alone must not raise
    checks = verify.verify_vector_output(
        str(points_gpkg), within_bounds=(0.0, 0.0, 0.1, 0.1)
    )
    extent = [c for c in checks if c.name == "extent_within_expected"]
    assert extent and not extent[0].passed
    verify.enforce(checks, "test_op")  # no exception


def test_reproject_verifies_target_crs(points_gpkg, tmp_path):
    out = tmp_path / "utm.gpkg"
    result = vector.reproject(str(points_gpkg), "EPSG:32632", str(out))
    assert result["verified"] is True
    manifest = json.loads((tmp_path / "utm.gpkg.provenance.json").read_text())
    crs_checks = [c for c in manifest["verification"] if c["name"] == "crs_matches"]
    assert crs_checks and crs_checks[0]["passed"]


def test_a_manifest_path_does_not_depend_on_the_host(tmp_path):
    """Two correct manifests for the same run must differ in no field but time.

    `str(path)` recorded the host's separator, so the same operation on the same
    bytes produced a backslash path on Windows and a forward-slash one elsewhere
    — a difference that describes nothing about the computation, and one that
    gives any consumer keying on the path two entries for one file (#30).

    The assertion is written with a path this host BUILT, not with a literal,
    and that is the whole subtlety. A first version asserted that a literal
    Windows string normalises everywhere, and CI on Linux disagreed — correctly:
    there, a backslash is a legal character in a filename, so rewriting one
    would corrupt a real path. Normalisation happens on the host that has
    separators, which is the only host that can produce the problem.
    """
    from pathlib import PurePath, PureWindowsPath

    from mapsmith.provenance import InputRecord, posix_path

    assert posix_path(PurePath("data") / "wells.gpkg") == "data/wells.gpkg"
    assert posix_path(PurePath("/srv/data") / "dem.tif").endswith("/srv/data/dem.tif")
    # The Windows flavour explicitly, so the behaviour is pinned from any host.
    assert PureWindowsPath(r"data\wells.gpkg").as_posix() == "data/wells.gpkg"
    assert PureWindowsPath(r"C:\work\dem.tif").as_posix() == "C:/work/dem.tif"
    # Only the separator: rewriting an absolute path to a relative one, or the
    # reverse, would misstate what actually ran.
    assert posix_path("data/wells.gpkg") == "data/wells.gpkg"

    source = tmp_path / "wells.gpkg"
    source.write_bytes(b"not really a geopackage")
    recorded = InputRecord.from_path(source)
    assert recorded.path == PurePath(source).as_posix()



def test_every_manifest_mapsmith_writes_conforms_to_the_spec(tmp_path):
    """MapSmith is an implementation of the manifest spec, not its definition.

    The day our manifest stops passing our own published validator, CI says so
    here — instead of a reader finding out. The validator is a vendored copy of
    the spec repository's stdlib-only implementation; the record under test is
    a REAL one, written by a real writer on a real file, because a hand-built
    record would validate the test's idea of a manifest rather than MapSmith's.
    """
    import json

    import geopandas as gpd

    from mapsmith.engines import vector

    source = tmp_path / "wells.parquet"
    gpd.GeoDataFrame(
        {"id": [1, 2]},
        geometry=gpd.GeoSeries.from_wkt(["POINT (500000 5000000)", "POINT (500100 5000100)"]),
        crs="EPSG:32632",
    ).to_parquet(source)
    out = tmp_path / "wells_100m.parquet"
    vector.buffer(str(source), 100.0, str(out))

    record = json.loads((tmp_path / "wells_100m.parquet.provenance.json")
                        .read_text(encoding="utf-8"))
    assert _spec_problems(record) == [], "a MapSmith manifest no longer conforms to the spec"
    assert record["spec_version"].startswith("1.")

    # The record must describe the bytes it sits beside — recomputed here from
    # the file, not trusted from the record.
    import hashlib

    assert record["output"]["path"].endswith("wells_100m.parquet")
    assert "\\" not in record["output"]["path"]
    assert record["output"]["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()


def test_every_writing_operation_conforms_to_the_spec(tmp_path):
    """The test above proves one operation conforms. This one proves they all do.

    The catalog is the list, so an operation added tomorrow is covered the day
    it is added — which is the point: the previous version of this file
    validated `buffer_layer` and nothing else, and four raster operations
    shipped without anyone checking whether their manifests were still
    manifests. They were, and that was luck rather than a control.

    Operations behind an absent extra are skipped rather than silently passed,
    and the test says how many it actually validated: a conformance test that
    quietly checks nothing is worse than no conformance test.
    """
    import json
    from pathlib import Path

    from mapsmith import catalog
    from mapsmith.plans.registry import BINDINGS

    fixtures = _spec_fixtures(tmp_path)
    spec_crs_keys = _spec_crs_keys()
    spec_transformation_keys = _spec_transformation_keys()
    writing = [
        entry["name"]
        for entry in catalog.OPERATIONS
        if entry["status"] == "available"
        and (binding := BINDINGS.get(entry["name"])) is not None
        and binding.output_arg is not None
    ]
    validated: list[str] = []
    skipped: list[str] = []
    with_environment: list[str] = []
    with_crs: list[str] = []
    with_repairs: list[str] = []
    undeclared: list[str] = []
    containers_seen: set[str] = set()
    _records_seen: dict[str, dict] = {}
    spec_objects = _spec_object_paths()
    from pathlib import Path as _Path

    # The PUBLISHED page, not a fresh derivation of the source. Deriving both
    # sides here would be circular in the way conftest already warns about:
    # renaming the literal at the repair site renames it in the derivation too,
    # and the check agrees with itself. Measured -- that sabotage passed green
    # before this line changed. The page is the artefact a reader actually has,
    # and a separate guard keeps it in step with the source, so comparing
    # against it asks the question that matters: could somebody look this up?
    _page = (
        _Path(__file__).resolve().parent.parent / "docs" / "manifest-vocabulary.md"
    ).read_text(encoding="utf-8")
    for entry in catalog.OPERATIONS:
        if entry["status"] != "available":
            continue
        name = entry["name"]
        binding = BINDINGS.get(name)
        if binding is None or binding.output_arg is None:
            continue  # readers write no manifest
        call = fixtures.get(name)
        if call is None:
            skipped.append(name)
            continue
        try:
            result = call()
        except ImportError:
            skipped.append(name)
            continue
        record = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
        _records_seen[name] = record
        assert _spec_problems(record) == [], f"{name} writes a manifest the spec rejects"
        assert record["operation"] == name
        assert record["spec_version"].startswith("1."), name
        # `output.crs`, and checked against a SECOND reading of the file rather
        # than against the same one. `write_for` fills it from
        # `verify.probe_crs`, which answers from metadata alone; here the file
        # is opened properly, the way a consumer would. Two paths to one fact,
        # which is the only form of this check worth running -- calling
        # `probe_crs` again would agree with itself.
        # Every name in `repairs[].check` has to be findable. There are two
        # kinds and both must be: a `Check` name, which is in the vocabulary of
        # `verification[]` already, or a literal written at the repair site --
        # and the second kind belongs to no `verification[]` entry, so unless
        # the page lists it a reader who meets it in a manifest has nowhere to
        # look. The source sweep in `benchmarks/manifest_vocabulary.py` reads
        # the literals, including on branches no fixture takes; this reads what
        # actually lands in a record, including a name a `Check` put there.
        # Neither sees what the other sees.
        for repair in record.get("repairs") or []:
            named = repair.get("check")
            with_repairs.append(name)
            assert f"`{named}`" in _page, (
                f"{name} wrote `repairs[].check` = {named!r}, and "
                "`docs/manifest-vocabulary.md` does not name it. A reader who "
                "meets it in a manifest has nowhere to look it up, which is the "
                "one thing that page exists to prevent. Either use the name of "
                "the check the repair was made for -- those are listed -- or "
                "write it as a literal at the repair site and regenerate."
            )
        declared = (record.get("output") or {}).get("crs")
        if declared is not None:
            with_crs.append(name)
            opened = _crs_by_a_second_route(result["output"])
            assert opened is not None and verify.same_crs(opened, declared), (
                f"{name} writes `output.crs` = {declared!r}, and opening the "
                f"file gives {verify.crs_label(opened) if opened else None!r}. "
                "One of the two readings is wrong, and the record is the one a "
                "stranger believes."
            )
        # No shipped operation may reach the fallback. `write_for` appends a
        # failed `verification_present` check when a record would otherwise
        # carry none, because a dataset with a non-conforming manifest beside
        # it is worse than one with an honest "nobody looked". That net exists
        # for the seventeen writers that build their record by hand and never
        # pass through `verify.audited` — and a net nobody watches becomes a
        # place to land. This is the watching: if a real operation ever writes
        # a manifest whose only content is that nothing was checked, the sweep
        # says so here instead of the manifest saying it to a stranger.
        assert verify.VERIFICATION_ABSENT not in [
            c["name"] for c in record["verification"]
        ], (
            f"{name} verified nothing and only the fallback in write_for kept its "
            "manifest conforming. The fallback is a net, not a licence: give the "
            "operation at least one real check."
        )
        # The other half of the `crs_decisions` rule. The AST sweep reads the
        # keys written out at the 68 sites, including the branches no fixture
        # takes; this reads the keys that are actually in the record, including
        # the ones a merged dict put there -- `grid.describe` contributes two
        # that no literal at a call site shows. Neither sees what the other
        # sees, and the drift they caught on 2026-09-06 was invisible to both
        # until one of them existed.
        # D-077 on EVERY container the specification describes, and this is the
        # general form of the two rules below it. Those read one container each
        # and were each written the day a key drifted inside it; the container
        # nobody had been bitten by yet was `engine`, which carried an
        # unprefixed `geometry_library` for four days in three engine modules.
        # A guard that is green while not looking is the shape this project
        # keeps finding in itself, so the containers are derived instead of
        # listed.
        _collect_undeclared(record, spec_objects, name, undeclared, containers_seen)
        for key in record.get("crs_decisions", {}):
            # The SAME predicate the AST sweep uses, imported rather than
            # restated. The first version wrote `key.startswith("x-mapsmith:")`
            # here and used the section 3.6 regex there, so the two halves of
            # one rule disagreed: this one accepted `x-mapsmith:Bad Name!` and
            # that one did not.
            assert key in spec_crs_keys or _EXTENSION_KEY.fullmatch(key), (
                f"{name} wrote `crs_decisions.{key}`, which is neither a key section "
                "3.7 recommends nor a MapSmith extension `x-mapsmith:<name>` (D-077)."
            )
        # ONE LEVEL DOWN, since 2026-09-07, and the rule changes with the
        # container rather than repeating. D-077 rule 3: the prefix follows the
        # container, not the datum.
        #
        # Inside `transformation` -- an object the SPECIFICATION defines -- a key
        # of ours has to say it is ours and be declared. Two were neither for
        # weeks (`chosen_by`, `default_was_ballpark`), and they passed because
        # the schema has `additionalProperties: true` and every guard here
        # stopped at the first level. Inside a container of OURS, by the same
        # rule, sub-keys carry no prefix and there is nothing to check: the whole
        # object already said whose it is.
        #
        # And in THREE places since `1.0.0-draft.6`, not one: the two legs of
        # `round_trip` are the same specification object. This read only the
        # top-level `transformation`, so a key of ours without the prefix inside
        # a leg would have passed -- the `conformita-manifest` review measured
        # `x-mapsmith:chosen_by` in both legs of a NAD27 buffer, conforming only
        # because nobody had got the spelling wrong yet.
        decisions = record.get("crs_decisions") or {}
        trip = decisions.get("round_trip") if isinstance(decisions.get("round_trip"), dict) else {}
        holders = {
            "crs_decisions.transformation": decisions.get("transformation"),
            "crs_decisions.round_trip.transformation": trip.get("transformation"),
            "crs_decisions.round_trip.return_transformation": trip.get("return_transformation"),
        }
        for where, inner in holders.items():
            if not isinstance(inner, dict):
                continue
            for key in inner:
                assert key in spec_transformation_keys or (
                    _EXTENSION_KEY.fullmatch(key) and key in TRANSFORMATION_EXTENSIONS
                ), (
                    f"{name} wrote `{where}.{key}`. That object "
                    "belongs to section 3.7, so a key of ours in it must be spelled "
                    "`x-mapsmith:<name>` AND declared in "
                    "`provenance.TRANSFORMATION_EXTENSIONS` with the sentence saying "
                    "why it is not one the specification already has -- a prefix says "
                    "whose a key is and never that."
                )
        # Saying an input was reprojected and not saying how is the silence this
        # whole line of work is about: across two datums with no grid installed
        # it is tens of metres, and `is_ballpark` is the boolean a consumer
        # branches on. The AST ratchet in `test_datum` reads the source and can
        # be satisfied by the word "transformation" appearing anywhere in the
        # function; this reads the record, so the two together mean the word has
        # to be there AND has to have put something in the manifest.
        # And the object next door, under the same rule with one difference:
        # section 3.8 asks for the configuration AS THE ENGINE REPORTS IT, so a
        # real setting name stays exactly as the engine spells it and only our
        # own readings carry the prefix. UPPER_SNAKE is the shape of a setting
        # -- `PROJ_NETWORK`, `GDAL_PAM_ENABLED`, both named by the specification
        # itself -- and it is derived from the key
        # rather than checked against a list of variables somebody keeps
        # filling in.
        for key in record.get("environment", {}):
            assert _SETTING_NAME.fullmatch(key) or _EXTENSION_KEY.fullmatch(key), (
                f"{name} wrote `environment.{key}`, which is neither a setting "
                "named the way an engine names one nor a MapSmith reading "
                "prefixed `x-mapsmith:` (D-077)."
            )
            # And DECLARED, for the reason `CRS_EXTENSIONS` is declared: the
            # prefix says a key is ours and cannot say it is not a synonym.
            # `PROJ_NETWORK` is named by section 3.8 itself, so
            # `x-mapsmith:proj_network` passes the shape rule above and is
            # precisely the mistake that produced D-077 -- one object over. The
            # ratchet cannot judge synonymy; it makes whoever adds a key write
            # the answer down next to the declaration.
            if key.startswith("x-mapsmith:"):
                assert key.removeprefix("x-mapsmith:") in DERIVED_ENVIRONMENT, (
                    f"{name} wrote `environment.{key}`, which is ours and "
                    "undeclared. Add it to `grid.DERIVED_ENVIRONMENT` with the "
                    "sentence saying what it claims -- and why a setting the "
                    "engine already reports does not say it."
                )
        if record.get("environment"):
            with_environment.append(name)
        decisions = record.get("crs_decisions", {})
        if INPUTS_REPROJECTED in decisions:
            shift = decisions.get("transformation")
            assert isinstance(shift, dict) and isinstance(shift.get("is_ballpark"), bool), (
                f"{name} recorded that an input was reprojected and did not record "
                f"how: {decisions.get('transformation')!r}. Wire the call site to "
                "`datum.default_operation` where the engine chooses, or "
                "`datum.best_operation` where we do."
            )
        validated.append(name)

    # An invariant, not a threshold. `>= 32` was wrong in both directions: with
    # every extra installed there are 34 writing operations and 34 fixtures, so
    # the number let TWO fixtures disappear in silence -- exactly the defect
    # this test exists to close. And on a checkout without [raster]/[whitebox]
    # only 21 fixtures can run, so the same number FAILED while blaming missing
    # fixtures for an absent extra. Comparing the two sets says the true thing
    # in either environment, and needs no maintenance when the 35th operation
    # lands.
    # The loop over `environment` keys above passes on a sweep where no record
    # has the field at all, which is the state this sweep was in until
    # 2026-09-06 and would return to in silence if the agreeing sidecar next to
    # `grid.tif` went away. The raster operations read that grid, so when they
    # ran, at least one record must carry the field the key rules are about.
    if "resample_raster" in validated:
        assert with_environment, (
            "no record in the sweep carries `environment`, so its shape rules "
            "checked nothing: the agreeing .aux.xml beside grid.tif is gone or no "
            "longer recorded"
        )
    assert set(validated) | set(skipped) == set(writing), (
        "every writing operation must be either validated or explicitly skipped; "
        f"unaccounted for: {sorted(set(writing) - set(validated) - set(skipped))}"
    )
    assert validated, "the sweep validated nothing at all"
    # ANTI-VACUITY on `output.crs`, and a ratchet rather than a floor. The
    # cross-check above runs only where the field is present, so the day
    # `write_for` stops writing it every one of those assertions passes by never
    # running -- the shape this project keeps finding. A floor was the first
    # form of this, with a number in the message that had been typed rather than
    # measured; measured, it is **58 of 58**. Every operation that writes a
    # dataset writes a georeferenced one, so "all of them" is a property and not
    # a coincidence, and asserting the property is stronger than asserting most.
    #
    # An operation that legitimately has no output CRS -- a table of statistics
    # with no geometry, say -- belongs in the set below, declared, rather than
    # quietly lowering a threshold.
    # ANTI-VACUITY on the repairs rule above, and it needs saying: until
    # 2026-09-09 **zero** of the fifty-eight records carried a `repairs` entry,
    # so every rule about their shape -- this one, and the vocabulary page's
    # claim to list the names that appear only there -- was checked against
    # nothing at all. One fixture now crosses a ring with itself, which is the
    # defect `measure_area`'s repair exists for.
    # ANTI-VACUITY on the sweep above, and it goes on what the walk must SEE.
    # Asserting that no key is undeclared would pass on a walk that visited
    # nothing, which is exactly how `engine` went unwatched: something was
    # green. So the containers actually reached are compared against the
    # containers the schema describes, minus the ones declared as nobody's.
    policeable = {p for p in spec_objects if p not in SPEC_OBJECTS_NOT_OURS}
    missed = policeable - containers_seen - {"crs_decisions.transformation"}
    assert not missed, (
        f"the sweep never reached these described containers: {sorted(missed)}. "
        "Either no operation emits them -- in which case the rule below is "
        "checked against less than it appears to be -- or the walk stopped "
        "descending. `crs_decisions.transformation` is excused because only a "
        "datum crossing produces it and one fixture does."
    )
    assert not undeclared, (
        "keys inside containers the specification describes that are neither "
        f"described there nor declared as ours: {sorted(undeclared)}. D-077: "
        "the prefix follows the CONTAINER, so a key of ours inside a field of "
        "the specification's must say it is ours -- `x-mapsmith:<name>`. If "
        "the key is not ours to name, add its container to "
        "SPEC_OBJECTS_NOT_OURS with the reason."
    )

    carried = [
        name for name, record in _records_seen.items()
        if INPUTS_REPROJECTED in (record.get("crs_decisions") or {})
    ]
    assert carried, (
        f"no record in this sweep carries `{INPUTS_REPROJECTED}`, so it is a key "
        "the vocabulary page documents and nothing emits end to end. The clip "
        "fixture gives the mask another CRS for exactly this; if it stopped "
        "producing the key, restore it rather than letting the page describe a "
        "record nobody has seen."
    )

    assert with_repairs, (
        "no record in this sweep carries a `repairs` entry, so the rule above "
        "ran on nothing. A fixture that produced one has stopped producing it: "
        "restore it rather than leaving the rule to pass by not running."
    )

    without_a_crs = set(validated) - set(with_crs) - NO_OUTPUT_CRS
    assert not without_a_crs, (
        f"these operations write a dataset and record no `output.crs`: "
        f"{sorted(without_a_crs)}. Either `write_for` stopped filling it, or "
        "`probe_crs` no longer recognises what they write, or the output really "
        "has no CRS -- and that last one is a fact to declare in "
        "`NO_OUTPUT_CRS`, not a reason to check less."
    )
    print(
        f"conformance sweep: {len(validated)} of {len(writing)} writing operations "
        f"validated, {len(skipped)} skipped for a missing extra ({sorted(skipped)})"
    )



def test_a_hand_built_record_cannot_write_a_manifest_the_spec_rejects(tmp_path):
    """The seventeen writers that never reach `verify.audited`.

    `audited` learned on 2026-09-05 to record an absent verification instead of
    raising and leaving the dataset orphaned. Seventeen writers of fifty-seven
    build their record by hand — `run_sql`, six in `raster.py`,
    `sedona_engine.spatial_join`, nine in `whitebox_engine` — and they reach
    none of that. Reproduced the day after: their exact shape wrote
    `verification: []`, which BOTH implementations reject, and
    `verify.enforce([])` does not raise, so the caller got `success` beside a
    manifest that is not a manifest. Strictly worse than the case just fixed,
    which was at least loud.

    The net is in `write_for` because that is the one place every manifest
    becomes a file. It appends rather than raising on purpose: raising there
    would leave the dataset with no record at all, which is the defect one
    level down and the reason the whole pair of fixes exists.

    This test walks the hand-built path exactly as those writers do — no
    `audited`, no `enforce` — and asserts the record that lands on disk is
    conforming, says which operation failed to check anything, and does not
    pretend the absence was a pass.
    """
    from mapsmith.provenance import ProvenanceRecord

    out = tmp_path / "hand_built.parquet"
    out.write_bytes(b"")
    record = ProvenanceRecord(
        operation="hand_built_writer",
        parameters={},
        inputs=[],
        engine={"name": "test", "version": "0"},
    )
    # Deliberately the shape of a writer that forgot: nothing added, and
    # `enforce` on an empty list, which does not raise and never did.
    verify.enforce([], "hand_built_writer")
    written = record.finish().write_for(str(out))

    manifest = json.loads(written.read_text(encoding="utf-8"))
    assert _spec_problems(manifest) == [], _spec_problems(manifest)
    absent = [c for c in manifest["verification"] if c["name"] == verify.VERIFICATION_ABSENT]
    assert len(absent) == 1, manifest["verification"]
    assert absent[0]["passed"] is False
    assert "hand_built_writer" in absent[0]["detail"]


def _check_names_in_source() -> tuple[dict[str, str], list[str]]:
    """Every `Check` name written in the source, and the ones it cannot read.

    Extracted on 2026-09-06 when a second caller appeared: the generator behind
    `docs/manifest-vocabulary.md` reads the same set to LIST it, and a test
    compares the two. Two copies of one reading is how a rule quietly becomes
    two rules -- this repository has watched that happen to a validator and its
    schema, which had drifted on every recommended field.
    """
    import ast
    from pathlib import Path

    import mapsmith

    root = Path(mapsmith.__file__).parent
    found: dict[str, str] = {}
    dynamic: list[str] = []
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        # Module-level tables of literal check names, so a lookup at the call
        # site is still statically readable. Only all-string dicts count.
        tables: dict[str, list[str]] = {}
        # And module-level constants holding one literal name. Same reasoning as
        # the tables, learned the hard way on 2026-09-05: moving a check name
        # out of the call and into `VERIFICATION_ABSENT` — because two distant
        # points had to agree on it — made it invisible to this sweep, and this
        # test went red. Red was the right answer and the fix is here, not
        # there: the alternative is that extracting a constant, which is the
        # normal thing to do with a name used twice, quietly removes that name
        # from the vocabulary rule.
        constants: dict[str, str] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            values = node.value.values
            if not values or not all(
                isinstance(v, ast.Constant) and isinstance(v.value, str) for v in values
            ):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    tables[target.id] = [v.value for v in values]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = node.func
            name = (
                callee.attr if isinstance(callee, ast.Attribute)
                else callee.id if isinstance(callee, ast.Name)
                else None
            )
            if name != "Check" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.setdefault(first.value, module.name)
            elif isinstance(first, ast.Name) and first.id in constants:
                # A module-level constant in THIS module. One imported from
                # another falls through to `dynamic` on purpose: this sweep
                # reads one file at a time, so a name it cannot see written out
                # is a name it cannot police, and saying so is the point.
                found.setdefault(constants[first.id], module.name)
            elif isinstance(first, ast.Subscript) and isinstance(first.value, ast.Name):
                # A lookup into a module-level table of literal names. The names
                # ARE written out, just not at the call, so the sweep reads the
                # table instead of giving up — and if the table holds anything
                # that is not a plain string, this falls through to `dynamic`.
                table = tables.get(first.value.id)
                if table:
                    for literal in table:
                        found.setdefault(literal, module.name)
                else:
                    dynamic.append(f"{module.name}:{first.lineno}")
            else:
                # A name this cannot read is a name it cannot police, and it used
                # to skip them in silence: `f"x-mapsmith:{name}_is_close_to_..."`
                # in network.py was invisible to the whole sweep, and legal by
                # luck. Refusing outright is stronger than half-evaluating an
                # f-string, and it costs nothing: a check name is short.
                dynamic.append(f"{module.name}:{getattr(first, 'lineno', '?')}")

    return found, dynamic


def test_every_check_name_in_the_source_obeys_the_vocabulary():
    """Not only the names a fixture happens to trigger.

    The conformance sweep above sees the checks that actually fire on its
    fixtures, which on 2026-08-26 was 12 of the 16 extension names in the
    source: four live on conditional branches -- the axis-order probe in
    `run_sql`, the invented-class-code guard, the flat-length warning on 3D
    geometries, the repair-path input check -- and no fixture reaches them. All
    four turned out to be well formed, checked by hand. The next one might not
    be, and "checked by hand" is not a control.

    Read from the source with `ast` rather than by executing anything: a name on
    a branch nothing takes is exactly the case that matters here.
    """
    import sys
    from pathlib import Path

    # The rule is read from the vendored spec copy, not from a local
    # restatement of it: two copies of one mistake agree perfectly.
    sys.path.insert(0, str(Path(__file__).parent / "data"))
    from manifest_spec_validator import CORE_CHECK_NAMES, EXTENSION_CHECK_NAME

    found, dynamic = _check_names_in_source()

    assert not dynamic, (
        f"these check names are built at runtime rather than written out: {dynamic}. "
        "Write them literally — a name assembled from an f-string is invisible to "
        "this sweep, so the vocabulary rule stops applying to exactly the newest "
        "code, which is where it is most needed."
    )
    assert len(found) >= 25, f"only {len(found)} check names found in the source: {sorted(found)}"
    offenders = {
        check: where
        for check, where in found.items()
        if check not in CORE_CHECK_NAMES and not EXTENSION_CHECK_NAME.fullmatch(check)
    }
    assert not offenders, (
        f"these check names are neither a core name from section 3.6 of the spec nor an "
        f"extension `x-<producer>:<name>`: {offenders}. An unconstrained vocabulary makes "
        "two records incomparable, which is the point of having a format."
    )


def _collect_undeclared(
    node: object,
    spec_objects: dict[str, frozenset[str]],
    operation: str,
    undeclared: list[str],
    seen: set[str],
    path: str = "",
) -> None:
    """Walk a record beside the schema's described objects, collecting strays.

    Collecting rather than asserting, so one run names every offender instead
    of the first: a sweep that stops at the first stray turns a five-minute fix
    into five sweeps.
    """
    if isinstance(node, dict):
        described = spec_objects.get(path)
        if described is not None and path not in SPEC_OBJECTS_NOT_OURS:
            seen.add(path)
            for key in node:
                if key not in described and not _EXTENSION_KEY.fullmatch(key):
                    where = path or "<root>"
                    undeclared.append(f"{operation}: {where}.{key}")
        for key, value in node.items():
            _collect_undeclared(
                value, spec_objects, operation, undeclared, seen,
                f"{path}.{key}" if path else key,
            )
    elif isinstance(node, list):
        for item in node:
            _collect_undeclared(
                item, spec_objects, operation, undeclared, seen, f"{path}[]"
            )


def test_every_crs_decisions_key_in_the_source_obeys_the_spec():
    """The same rule as the sweep above, for the object beside it. D-077.

    **This is a MapSmith rule, stricter than the specification, and saying so is
    part of it.** Section 3.6 makes the check-name vocabulary a MUST with the
    syntax `x-<producer>:<name>`; that MUST is about `verification[].name` and
    nothing else. For FIELDS, section 3.5 only recommends -- "a producer prefix
    does this well", a SHOULD with no syntax -- and section 3.7 permits extra
    keys in `crs_decisions` under that rule. So a third-party producer reading
    only the specification would not emit our prefix, and this test is house
    policy rather than conformance until the specification says otherwise.

    What made the policy worth having is what a SHOULD with nothing reading it
    did. Derived from the source on 2026-09-06: **two sites had invented
    synonyms of keys section 3.7 already recommends and MapSmith already used
    everywhere else** -- `measurement_crs` in `points_along_lines`,
    `declared_output_crs` and `input_crs_before` in
    `transform_by_control_points`. A consumer asking those two records "what did
    you compute in?" read `analysis_crs`, found nothing, and had no way to know
    the answer sat under another name.

    Nothing could have caught it, because nothing compared the sites to each
    other -- each one is defensible alone. So the recommended keys are read from
    the vendored schema rather than restated here, the prefix predicate is
    shared with the runtime half in `conftest`, and the sites are read from the
    source rather than from the fixtures: a key on a branch no fixture reaches
    is exactly the case that produced this.
    """
    import ast
    from pathlib import Path

    import mapsmith

    fixed = _spec_crs_keys()
    root = Path(mapsmith.__file__).parent

    # Module-level string constants across the whole package, so a key written
    # as an IMPORTED name is still readable. The sibling sweep over check names
    # deliberately gives up on those, one file at a time; here it would give up
    # on exactly the right thing to do with a name used at three call sites --
    # `INPUTS_REPROJECTED` lives in `provenance` and is written in `linework`.
    # A name defined twice with different values is dropped rather than guessed.
    package_constants: dict[str, str | None] = {}
    for module in sorted(root.rglob("*.py")):
        for node in ast.parse(module.read_text(encoding="utf-8")).body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                seen = package_constants.get(target.id, node.value.value)
                package_constants[target.id] = (
                    node.value.value if seen == node.value.value else None
                )

    found: dict[str, str] = {}
    dynamic: list[str] = []
    merged_from: set[str] = set()
    sites = 0
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        # Module-level string constants only, as in the sweep above: a
        # function-local name that happens to match one is a different name.
        constants: dict[str, str] = {
            target.id: node.value.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        # ALL three tables map a name to a LIST, and every association is
        # resolved. The first version used dict comprehensions, so two functions
        # in one module that use the same local name collapsed into one and the
        # last won -- and `linework.py` binds a literal to `crs_decisions`
        # twice, in `snap_layer` and in `line_intersections`. An illegal key
        # injected into the first was invisible, which is to say this sweep was
        # blind exactly where it had just been used to find something. Two
        # reviewers found it independently on the day it was written; it was
        # only `subscripts`, written last, that already accumulated.
        from_call: dict[str, list[str]] = {}
        literals: dict[str, list[ast.Dict]] = {}
        subscripts: dict[str, list[ast.Constant]] = {}
        subscript_names: dict[str, list[ast.Name]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and isinstance(node.value, ast.Dict):
                    literals.setdefault(node.target.id, []).append(node.value)
                continue
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if isinstance(node.value, ast.Dict):
                        literals.setdefault(target.id, []).append(node.value)
                    elif isinstance(node.value, ast.Call):
                        callee = node.value.func
                        from_call.setdefault(target.id, []).append(
                            callee.attr if isinstance(callee, ast.Attribute)
                            else getattr(callee, "id", "?")
                        )
                elif isinstance(target, ast.Subscript) and isinstance(
                    target.value, ast.Name
                ):
                    # The key may be a literal or a constant's name. Anything
                    # else is recorded as unreadable rather than skipped: the
                    # first version required a literal and silently ignored
                    # `local[SOME_CONSTANT] = ...`, so three sites writing
                    # `crs_decisions[INPUTS_REPROJECTED]` were invisible to this
                    # sweep with no complaint. A guard that quietly declines to
                    # look is worse than one that says it cannot.
                    key = target.slice
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        subscripts.setdefault(target.value.id, []).append(key)
                    elif isinstance(key, ast.Name):
                        subscript_names.setdefault(target.value.id, []).append(key)

        def resolve(
            value: ast.expr,
            where: str,
            depth: int = 0,
            # Bound here rather than closed over: this is redefined once per
            # module, and a closure over the loop's tables would read whichever
            # module happened to be last.
            *,
            subscripts: dict[str, list[ast.Constant]] = subscripts,
            subscript_names: dict[str, list[ast.Name]] = subscript_names,
            literals: dict[str, list[ast.Dict]] = literals,
            constants: dict[str, str] = constants,
            from_call: dict[str, list[str]] = from_call,
        ) -> None:
            """The keys this expression puts into `crs_decisions`, or a blind spot."""
            if depth > 3:  # pragma: no cover - a chain that deep is a defect anyway
                dynamic.append(f"{where}:{getattr(value, 'lineno', '?')}")
                return
            if isinstance(value, ast.IfExp):
                resolve(value.body, where, depth + 1)
                resolve(value.orelse, where, depth + 1)
                return
            if isinstance(value, ast.Call):
                # A dict this cannot read, built by a function. Named rather
                # than ignored: see the ratchet below.
                callee = value.func
                merged_from.add(
                    callee.attr if isinstance(callee, ast.Attribute)
                    else getattr(callee, "id", "?")
                )
                return
            if isinstance(value, ast.Name):
                seen = False
                for key in subscripts.get(value.id, []):
                    found.setdefault(key.value, f"{where}:{key.lineno}")
                    seen = True
                for name in subscript_names.get(value.id, []):
                    resolved = constants.get(name.id) or package_constants.get(name.id)
                    if resolved is None:
                        dynamic.append(f"{where}:{name.lineno}")
                    else:
                        found.setdefault(resolved, f"{where}:{name.lineno}")
                    seen = True
                for literal in literals.get(value.id, []):
                    resolve(literal, where, depth + 1)
                    seen = True
                for callee_name in from_call.get(value.id, []):
                    merged_from.add(callee_name)
                    seen = True
                if not seen:
                    dynamic.append(f"{where}:{value.lineno}")
                return
            if not isinstance(value, ast.Dict):
                dynamic.append(f"{where}:{getattr(value, 'lineno', '?')}")
                return
            for position, key in enumerate(value.keys):
                if key is None:
                    # `**something` inside the literal. Its keys are not here;
                    # name what built it, same as a merged call.
                    resolve(value.values[position], where, depth + 1)
                elif isinstance(key, ast.Constant) and isinstance(key.value, str):
                    found.setdefault(key.value, f"{where}:{key.lineno}")
                elif isinstance(key, ast.Name) and key.id in constants:
                    found.setdefault(constants[key.id], f"{where}:{key.lineno}")
                else:
                    dynamic.append(f"{where}:{getattr(key, 'lineno', '?')}")

        # Closed, not enumerative. The first version listed the three shapes it
        # knew -- assignment, keyword, `.update(dict)` -- and said nothing about
        # any other, so `record.crs_decisions["k"] = v`, `|= {...}`,
        # `.update(k=v)` and `.setdefault("k", v)` were all invisible rather
        # than red. That is the guard-that-cannot-fail turned on the guard's own
        # input: it could only ever report what it already understood. Now every
        # mention of the attribute is classified, and a shape with no branch
        # here fails the test instead of being skipped.
        parents: dict[int, ast.AST] = {
            id(child): node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        #: Methods that cannot introduce a key. Anything else on the attribute
        #: is reported rather than assumed harmless.
        reading = {"get", "items", "keys", "values", "copy"}
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg == "crs_decisions":
                sites += 1
                resolve(node.value, module.name)
                continue
            if not (isinstance(node, ast.Attribute) and node.attr == "crs_decisions"):
                continue
            spot = f"{module.name}:{node.lineno}"
            parent = parents.get(id(node))
            # `record.crs_decisions = {...}` and `record.crs_decisions |= {...}`:
            # both hand the whole object over, so both resolve the right side.
            if (
                isinstance(parent, ast.Assign)
                and any(t is node for t in parent.targets)
            ) or (isinstance(parent, ast.AugAssign) and parent.target is node):
                sites += 1
                resolve(parent.value, module.name)
            elif isinstance(parent, ast.Attribute):
                call = parents.get(id(parent))
                if parent.attr in reading:
                    continue
                if parent.attr == "update" and isinstance(call, ast.Call):
                    sites += 1
                    for argument in call.args:
                        resolve(argument, module.name)
                    for keyword in call.keywords:
                        # `.update(analysis_crs=...)`: the key is the argument
                        # name, and `**other` has no name at all.
                        if keyword.arg is None:
                            resolve(keyword.value, module.name)
                        else:
                            found.setdefault(keyword.arg, spot)
                elif parent.attr == "setdefault" and isinstance(call, ast.Call):
                    sites += 1
                    first = call.args[0] if call.args else None
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        found.setdefault(first.value, spot)
                    else:
                        dynamic.append(spot)
                else:
                    dynamic.append(spot)
            elif isinstance(parent, ast.Subscript):
                grandparent = parents.get(id(parent))
                stored = isinstance(grandparent, ast.Assign) and any(
                    t is parent for t in grandparent.targets
                )
                if not stored:
                    continue  # a read: `record.crs_decisions["k"]` on the right
                sites += 1
                key = parent.slice
                resolved = (
                    key.value
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                    else (constants.get(key.id) or package_constants.get(key.id))
                    if isinstance(key, ast.Name)
                    else None
                )
                if resolved is None:
                    dynamic.append(spot)
                else:
                    found.setdefault(resolved, spot)
            elif isinstance(getattr(node, "ctx", None), ast.Load):
                continue  # the attribute read as a whole value
            else:
                dynamic.append(spot)

    assert not dynamic, (
        f"these `crs_decisions` writes are not in a shape this can read: {dynamic}. "
        "Write the keys literally, or as a module-level constant -- and if the shape "
        "itself is new, teach this sweep about it rather than letting it pass."
    )
    # A smoke floor, and it says what it is: the control is `dynamic` being
    # empty, not this number. `len(found)` would not have moved if the sweep had
    # stopped reading sixty sites out of seventy, because it counts DISTINCT
    # keys -- so the floor is on the sites visited.
    assert sites >= 60, f"only {sites} write sites of `crs_decisions` seen in the source"

    # A key of ours has to be DECLARED, with the sentence saying why it is not a
    # synonym. The prefix rule above cannot ask that: `x-mapsmith:measurement_crs`
    # passes it, and `measurement_crs` is one of the two synonyms that started
    # all of this. Whether a name means what `source_crs` means is not a
    # mechanical question, so the ratchet does the only thing available -- it
    # makes whoever adds a key write the answer down.
    from mapsmith.provenance import CRS_EXTENSIONS

    undeclared = {
        key: where
        for key, where in found.items()
        if key.startswith("x-mapsmith:") and key not in CRS_EXTENSIONS
    }
    assert not undeclared, (
        f"these `crs_decisions` keys are ours and undeclared: {undeclared}. Add "
        "each to `provenance.CRS_EXTENSIONS` with the sentence that says why it is "
        "not a synonym of a key section 3.7 already recommends -- that sentence is "
        "the whole point, and a prefix does not supply it."
    )

    offenders = {
        key: where
        for key, where in found.items()
        if key not in fixed and not _EXTENSION_KEY.fullmatch(key)
    }
    assert not offenders, (
        f"these `crs_decisions` keys are neither recommended by section 3.7 of the "
        f"spec nor a MapSmith extension `x-mapsmith:<name>`: {offenders}. If the key "
        "means what a recommended one means, use the recommended one -- a synonym "
        "makes the record unreadable to a consumer holding the specification. If it "
        "is genuinely ours, prefix it, so that a reader holding the manifest and not "
        "the specification can tell which is which (D-077)."
    )

    # A ratchet, not an allowlist: an entry is a blind spot, not a thing to
    # check, and the three here are blind for reasons that were verified
    # rather than assumed. `alignment_decisions` builds the object for the
    # operations that bring a secondary input to one CRS, and its own keys
    # are pinned by `test_alignment_decisions_writes_only_conforming_keys`
    # below -- which exercises BOTH its branches, where the conformance
    # sweep only reaches the one where nothing moved. `grid.manifest_decisions` returns keys this sweep cannot
    # read and the conformance sweep over real records does. `redact_secrets`
    # cannot introduce a key at all: on a dict it rebuilds `{k: ...}` for the
    # keys it was given, so it re-emits whatever reached it and nothing else.
    # A third such function turns this red, so whoever adds it decides which
    # sweep covers it instead of discovering later that neither did.
    assert merged_from <= {
        "manifest_decisions",
        "redact_secrets",
        "alignment_decisions",
    }, (
        f"a dict is merged into `crs_decisions` from {sorted(merged_from)}, whose keys "
        "this sweep cannot read. Either write them out, or confirm the conformance "
        "sweep reaches every branch of it and add it here."
    )


def _crs_by_a_second_route(output_path: str):
    """The CRS of a written dataset, read properly rather than probed.

    `verify.probe_crs` -- which is what fills `output.crs` -- answers from
    metadata only and never raises, both of which are right for a producer and
    wrong for a check on that producer. This opens the file: rasterio for a
    raster, geopandas for everything it can read. It returns None when it
    cannot read the file at all, and a caller that finds None where the record
    claimed a CRS has learnt something either way.

    The CRS comes back as the OBJECT, not as a label. Comparing labels would
    turn this into a test of how two libraries spell the same system, and
    geopandas spells it as the whole PROJJSON document: `verify.same_crs` is
    the comparison that means what it says.
    """
    lower = str(output_path).lower()
    try:
        if lower.endswith((".tif", ".tiff")):
            import rasterio

            with rasterio.open(output_path) as dataset:
                return dataset.crs or None
        frame = gpd.read_parquet(output_path) if lower.endswith(".parquet") else gpd.read_file(
            output_path
        )
    except Exception:  # noqa: BLE001 -- an unreadable output is the caller's finding
        return None
    return frame.crs


def _spec_fixtures(tmp_path):
    """One real call per writing operation, for the conformance sweep.

    Real calls on real files: a hand-built record would validate the test's
    idea of a manifest rather than MapSmith's.
    """
    import geopandas as gpd
    from shapely.geometry import LineString, Point, Polygon

    from mapsmith.engines import vector

    crs = "EPSG:32632"
    square = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    other = Polygon([(50, 50), (150, 50), (150, 150), (50, 150)])
    layer = tmp_path / "a.parquet"
    gpd.GeoDataFrame({"k": ["x"], "v": [1]}, geometry=[square], crs=crs).to_parquet(layer)
    second = tmp_path / "b.parquet"
    gpd.GeoDataFrame({"j": [2]}, geometry=[other], crs=crs).to_parquet(second)
    # The same polygon in ANOTHER CRS, for the one two-layer call here that
    # reprojects its second input. Until 2026-09-24 every pair in this sweep
    # shared a CRS, so `x-mapsmith:inputs_reprojected` was declared, documented
    # on the vocabulary page, and produced by none of the fifty-eight records --
    # the `conformita-manifest` review measured 0 of 58. It is the other thing
    # `alignment_decisions` writes, and that function changed on 2026-09-23.
    elsewhere = tmp_path / "b_geographic.parquet"
    gpd.GeoDataFrame({"j": [2]}, geometry=[other], crs=crs).to_crs(
        "EPSG:4326"
    ).to_parquet(elsewhere)
    # One fixture on a GEOGRAPHIC datum, and NAD27 rather than WGS 84 on
    # purpose. Every other layer here is already projected, so until 2026-09-07
    # not one of the fifty-eight records this sweep collects had ever taken the
    # branch that reprojects and comes back -- which means `x-mapsmith:round_trip`
    # shipped, was declared, was documented, and was read by nothing. NAD27
    # crosses a datum in both directions (`estimate_utm_crs()` answers with a
    # WGS 84 zone whatever the input datum is), so the record here carries two
    # real transformations rather than two free relabellings.
    # A ring that crosses itself, so `measure_area` repairs it with `make_valid`
    # BEFORE measuring and records that under `repairs`. Until 2026-09-09 not one
    # of the fifty-eight records this sweep collects carried a `repairs` entry at
    # all, so every rule about their shape was checked against nothing -- the
    # vocabulary page's claim to list the names that appear only there included.
    # The planar area of a self-intersecting ring is the signed shoelace, which
    # matches no region and comes back without complaint: that is the defect the
    # repair exists for, and why it has to be visible in the record.
    self_crossing = tmp_path / "bowtie_area.parquet"
    gpd.GeoDataFrame(
        {"k": ["x"]},
        geometry=[Polygon([(0, 0), (100, 100), (100, 0), (0, 100)])],
        crs=crs,
    ).to_parquet(self_crossing)

    # EPSG:4806, Monte Mario with the Rome meridian: the pair section 3.7 of the
    # specification uses as its headline ballpark, and the one branch of
    # `datum.default_operation` no fixture reached. PROJ's own choice for
    # 4806 -> 4326 applies no datum shift, and a three-parameter Helmert exists
    # -- so the record carries `x-mapsmith:chosen_by` and `better_available_m`,
    # which is what makes the ratchet on that object able to fail at all.
    rome = tmp_path / "rome.parquet"
    gpd.GeoDataFrame(
        {"k": ["x"]},
        geometry=[Polygon([(-3.0, 41.9), (-2.9, 41.9), (-2.9, 42.0), (-3.0, 42.0)])],
        crs="EPSG:4806",
    ).to_parquet(rome)
    geographic = tmp_path / "nad27.parquet"
    gpd.GeoDataFrame(
        {"k": ["x"]},
        geometry=[Polygon([(-93.1, 34.5), (-93.0, 34.5), (-93.0, 34.6), (-93.1, 34.6)])],
        crs="EPSG:4267",
    ).to_parquet(geographic)
    points = tmp_path / "p.parquet"
    gpd.GeoDataFrame(
        {"n": [1, 2]}, geometry=[Point(10, 10), Point(90, 90)], crs=crs
    ).to_parquet(points)
    quad = tmp_path / "quad.parquet"
    gpd.GeoDataFrame(
        {"n": [1, 2, 3, 4], "v": [7.0, 7.0, 7.0, 7.0]},
        geometry=[Point(0, 0), Point(100, 0), Point(0, 100), Point(100, 100)],
        crs=crs,
    ).to_parquet(quad)

    # A small connected network and a strip of touching areas: everything the
    # network and statistics operations need, built once here rather than in
    # each lambda.
    streets = tmp_path / "streets.parquet"
    gpd.GeoDataFrame(
        {"id": [0, 1, 2]},
        geometry=[
            LineString([(0, 0), (100, 0)]),
            LineString([(100, 0), (200, 0)]),
            LineString([(100, 0), (100, 100)]),
        ],
        crs=crs,
    ).to_parquet(streets)
    # The same streets in another projected CRS: an operation that reads a
    # raster under a line in a different CRS records a transformation, and the
    # sweep has to see that record, not only the one where nothing moved.
    streets_elsewhere = tmp_path / "streets_3857.parquet"
    gpd.read_parquet(streets).to_crs("EPSG:3857").to_parquet(streets_elsewhere)
    areas = tmp_path / "areas.parquet"
    gpd.GeoDataFrame(
        {"cases": [1.0, 1.0, 5.0, 1.0], "pop": [100.0, 200.0, 300.0, 400.0]},
        geometry=[
            Polygon([(i * 10, 0), (i * 10 + 10, 0), (i * 10 + 10, 10), (i * 10, 10)])
            for i in range(4)
        ],
        crs=crs,
    ).to_parquet(areas)
    crowd = tmp_path / "crowd.parquet"
    gpd.GeoDataFrame(
        {"weight": [1.0, 5.0, 2.0, 4.0]},
        geometry=[Point(x, 0) for x in (0, 10, 20, 30)],
        crs=crs,
    ).to_parquet(crowd)

    # For the linework operations: a line a few centimetres off its reference,
    # a pair that cross in a plus sign, and two control points describing a
    # quarter turn about the origin followed by a shift.
    nearly = tmp_path / "nearly.parquet"
    gpd.GeoDataFrame(
        {"id": [0]}, geometry=[LineString([(0, 0.03), (100, 0.03)])], crs=crs
    ).to_parquet(nearly)
    crossing = tmp_path / "crossing.parquet"
    gpd.GeoDataFrame(
        {"id": [0]}, geometry=[LineString([(50, -50), (50, 50)])], crs=crs
    ).to_parquet(crossing)
    baseline = tmp_path / "baseline.parquet"
    gpd.GeoDataFrame(
        {"id": [0]}, geometry=[LineString([(0, 0), (100, 0)])], crs=crs
    ).to_parquet(baseline)
    control = tmp_path / "control.parquet"
    gpd.GeoDataFrame(
        {"source_x": [0.0, 10.0], "source_y": [0.0, 0.0]},
        geometry=[Point(100, 200), Point(100, 210)],
        crs=crs,
    ).to_parquet(control)

    # A container with two layers, which nothing else here needs: extract_layer
    # has nothing to extract without one. Written with the GPKG driver because
    # single-dataset formats cannot hold two layers at all — which is the
    # refusal the operation exists to resolve.
    container = tmp_path / "container.gpkg"
    gpd.GeoDataFrame({"k": ["x"], "v": [1]}, geometry=[square], crs=crs).to_file(
        container, layer="parcels", driver="GPKG"
    )
    gpd.GeoDataFrame(
        {"id": [0]}, geometry=[LineString([(0, 0), (100, 0)])], crs=crs
    ).to_file(container, layer="roads", driver="GPKG")

    def out(name: str) -> str:
        return str(tmp_path / name)

    from mapsmith.engines import linework, network, spatial_stats, whitebox_engine

    fixtures = {
        "network_shortest_path": lambda: network.network_shortest_path(
            str(streets), out("route.parquet"), 0, 0, 200, 0, tolerance=0.01
        ),
        "service_area": lambda: network.service_area(
            str(streets), out("reach.parquet"), 0, 0, budget=150.0, tolerance=0.01
        ),
        "hot_spots": lambda: spatial_stats.hot_spots(
            str(areas), out("gi.parquet"), value_field="cases", weights="contiguity"
        ),
        "smooth_rates": lambda: spatial_stats.smooth_rates(
            str(areas), out("eb.parquet"), count_field="cases", population_field="pop"
        ),
        "aggregate_to_threshold": lambda: spatial_stats.aggregate_to_threshold(
            str(areas), out("merged.parquet"), count_field="cases", minimum=2
        ),
        "thin_points": lambda: spatial_stats.thin_points(
            str(crowd), out("thin.parquet"), min_distance=15.0
        ),
        "cluster_points_by_distance": lambda: spatial_stats.cluster_points_by_distance(
            str(crowd), out("clusters.parquet"), max_distance=15.0
        ),
        "snap_layer": lambda: linework.snap_layer(
            str(nearly), str(baseline), out("snapped.parquet"), tolerance=0.05
        ),
        "points_along_lines": lambda: linework.points_along_lines(
            str(baseline), out("chainage.parquet"), spacing=20.0
        ),
        "line_intersections": lambda: linework.line_intersections(
            str(baseline), str(crossing), out("nodes.parquet")
        ),
        "transform_by_control_points": lambda: linework.transform_by_control_points(
            str(baseline), str(control), out("placed.parquet"), target_crs=crs
        ),
        "contour_lines": lambda: whitebox_engine.contour_lines(
            _ramp(tmp_path), out("contours.parquet"), interval=3.0
        ),
        "least_cost_path": lambda: network.least_cost_path(
            _uniform_cost(tmp_path),
            _one_point(tmp_path, "lcp_start", 0.5, 9.5),
            _one_point(tmp_path, "lcp_end", 9.5, 9.5),
            out("cheapest.parquet"),
        ),
        "buffer_layer": lambda: vector.buffer(str(layer), 10.0, out("buf.parquet")),
        "clip_layer": lambda: vector.clip(str(layer), str(elsewhere), out("clip.parquet")),
        "overlay_layers": lambda: vector.overlay(
            str(layer), str(second), out("ov.parquet")
        ),
        "dissolve_layer": lambda: vector.dissolve(str(layer), out("dis.parquet"), by="k"),
        "nearest_join": lambda: vector.nearest_join(
            str(points), str(layer), out("near.parquet")
        ),
        "explode_layer": lambda: vector.explode(str(layer), out("exp.parquet")),
        # On the self-crossing ring, so this sweep sees a `repairs` entry.
        "measure_area": lambda: vector.measure_area(
            str(self_crossing), out("area.parquet")
        ),
        "merge_layers": lambda: vector.merge(
            [str(layer), str(second)], out("merge.parquet")
        ),
        "simplify_layer": lambda: vector.simplify(str(layer), 1.0, out("simp.parquet")),
        # On the geographic fixture, so this sweep sees `x-mapsmith:round_trip`.
        "centroid_layer": lambda: vector.centroid(str(geographic), out("cent.parquet")),
        # `streets` and not `layer`: the single-polygon layer kept 1 of 1, so the
        # conformance sweep validated the manifest of a filter that filtered
        # nothing — output bytes identical to input, no `SUBSET` note, no
        # `feature_count_bounded` with anything to bound. Here two of three
        # survive, so the interesting branches are the ones checked.
        "select_features": lambda: vector.select_features(
            str(streets),
            out("selected.parquet"),
            by="field_in",
            field="id",
            values=[0, 1],
        ),
        "extract_layer": lambda: vector.extract_layer(
            str(container), "roads", out("extracted.parquet")
        ),
        "convert_format": lambda: vector.convert(str(layer), out("conv.gpkg")),
        # From the Rome meridian, so this sweep sees a ballpark transformation
        # and the keys only that branch writes.
        "reproject_layer": lambda: vector.reproject(
            str(rome), "EPSG:4326", out("rep.parquet")
        ),
        "spatial_join": lambda: vector.spatial_join(
            str(points), str(layer), out("sj.parquet")
        ),
    }

    # --- the tier-A operations, whose fixtures are the traps' own -----------
    table = tmp_path / "table.csv"
    table.write_text("k,v\nx,10\n", encoding="utf-8")
    keyed = tmp_path / "keyed.parquet"
    gpd.GeoDataFrame({"k": ["x"]}, geometry=[square], crs=crs).to_parquet(keyed)
    weighted = tmp_path / "weighted.parquet"
    gpd.GeoDataFrame(
        {"value": [20.0, 1.0], "weight": [1000, 99000]},
        geometry=[square, other],
        crs=crs,
    ).to_parquet(weighted)
    dms = tmp_path / "dms.csv"
    dms.write_text("id,lat,lon\n1,41.89,12.49\n", encoding="utf-8")
    climbing = tmp_path / "climbing.parquet"
    gpd.GeoDataFrame(
        {"i": [1]}, geometry=[LineString([(0, 0, 0), (400, 0, 300)])], crs=crs
    ).to_parquet(climbing)

    fixtures.update({
        "join_table": lambda: vector.join_table(
            str(keyed), str(table), out("joined.parquet"), on="k"
        ),
        "measure_length": lambda: vector.measure_length(
            str(climbing), out("length.parquet"), method="3d"
        ),
        "aggregate_weighted": lambda: vector.aggregate_weighted(
            str(weighted), out("agg.parquet"),
            value_column="value", weight_column="weight",
        ),
        "parse_coordinates": lambda: vector.parse_coordinates(
            str(dms), out("parsed.parquet"),
            latitude_columns="lat", longitude_columns="lon",
        ),
        "point_on_surface": lambda: vector.point_on_surface(
            str(layer), out("pos.parquet")
        ),
        "hull_layer": lambda: vector.hull(str(layer), out("hull.parquet")),
        "validate_geometry": lambda: vector.validate_geometry(
            str(layer), out("valid.parquet")
        ),
        "count_in_polygons": lambda: vector.count_in_polygons(
            str(points), str(layer), out("counts.parquet")
        ),
        "summarize_points_in_polygons": lambda: vector.summarize_points_in_polygons(
            str(points), str(layer), out("point_summary.parquet"), field="n"
        ),
        # Four points, because two collinear ones give two cells and no corner.
        "voronoi_polygons": lambda: vector.voronoi_polygons(
            str(quad), out("vor.parquet")
        ),
    })

    try:
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin

        from mapsmith.engines import raster
    except ImportError:
        return fixtures

    grid = tmp_path / "grid.tif"
    with rasterio.open(
        grid, "w", driver="GTiff", height=4, width=4, count=2, dtype="int16",
        crs=crs, transform=from_origin(0, 100, 25, 25), nodata=-9999,
    ) as ds:
        ds.write(np.arange(16, dtype="int16").reshape(4, 4), 1)
        ds.write(np.arange(16, 32, dtype="int16").reshape(4, 4), 2)
    # Weights on exactly that grid, for the weighted zonal statistics.
    grid_weights = tmp_path / "grid_weights.tif"
    with rasterio.open(
        grid_weights, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs=crs, transform=from_origin(0, 100, 25, 25), nodata=-1.0,
    ) as ds:
        ds.write(np.arange(1, 17, dtype="float32").reshape(4, 4), 1)

    # The raster twin of the Rome-meridian layer above, and it exercises the
    # OTHER branch: `reproject_raster` hands the pair to rasterio, which reaches
    # for PROJ itself, so `datum.default_operation` reports what the engine will
    # get rather than choosing -- and that is the branch writing
    # `x-mapsmith:chosen_by`. Nothing in this sweep reached it before.
    rome_grid = tmp_path / "rome.tif"
    with rasterio.open(
        rome_grid, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32",
        crs="EPSG:4806", transform=from_origin(-3.0, 42.0, 0.01, 0.01), nodata=-9999.0,
    ) as ds:
        ds.write(np.arange(16, dtype="float32").reshape(4, 4), 1)

    # An AGREEING `.aux.xml` beside the raster, so that at least one record in
    # this sweep carries a non-empty `environment`. Until 2026-09-06 not one of
    # the fifty-eight did: the field that answers the first of the two silent
    # error classes -- the configuration nobody named -- had its shape covered
    # by nothing, and a guard written for its keys passed with the keys wrong.
    # Agreeing rather than contradicting on purpose: a disagreement is refused
    # outright by twelve operations (D-059), so it would test the refusal
    # instead of the record.
    (grid.parent / f"{grid.name}.aux.xml").write_text(
        "<PAMDataset><SRS>EPSG:32632</SRS></PAMDataset>", encoding="utf-8"
    )
    query = (
        f"SELECT * FROM read_parquet('{str(layer).replace(chr(92), '/')}')"
    )
    from mapsmith.engines import duckdb_engine

    fixtures["run_sql"] = lambda: duckdb_engine.run_sql(query, out("sql.parquet"))

    fixtures.update({
        "resample_raster": lambda: raster.resample(
            str(grid), out("res.tif"), 50, "nearest"
        ),
        "clip_raster": lambda: raster.clip_raster(
            str(grid), str(layer), out("clipr.tif")
        ),
        "reclassify_raster": lambda: raster.reclassify(
            str(grid), out("rc.tif"), ["0:8:1", "8:40:2"]
        ),
        "band_math": lambda: raster.band_math(str(grid), out("bm.tif"), "b2 - b1"),
        # The WEIGHTED form: it adds an input and a check to the record, so it
        # is the one worth sweeping; the unweighted path shares everything else.
        "zonal_statistics": lambda: raster.zonal_statistics(
            str(grid), str(layer), out("zs.parquet"), stats=["mean", "weighted_mean"],
            weights_path=str(grid_weights),
        ),
        "reproject_raster": lambda: raster.reproject_raster(
            str(rome_grid), out("repr.tif"), "EPSG:4326", "nearest"
        ),
        "extract_band": lambda: raster.extract_band(str(grid), out("band2.tif"), 2),
    })

    try:
        from mapsmith.engines import sampling, whitebox_engine
    except ImportError:
        return fixtures

    # A tilted plane with a single low corner: enough terrain for the
    # derivatives and the hydrology to have something to route.
    rows, cols = 24, 24
    yy, xx = np.mgrid[0:rows, 0:cols]
    surface = (100.0 + xx * 2.0 + yy * 1.0).astype("float32")
    dem = tmp_path / "dem.tif"
    with rasterio.open(
        dem, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
        crs=crs, transform=from_origin(0, rows * 10.0, 10, 10), nodata=-9999.0,
    ) as ds:
        ds.write(surface, 1)
    pour = tmp_path / "pour.parquet"
    gpd.GeoDataFrame(
        {"id": [1]}, geometry=[Point(5.0, 5.0)], crs=crs
    ).to_parquet(pour)
    mask = tmp_path / "mask.tif"
    features = np.zeros((rows, cols), dtype="float32")
    features[rows // 2, cols // 2] = 1.0
    with rasterio.open(
        mask, "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
        crs=crs, transform=from_origin(0, rows * 10.0, 10, 10), nodata=-9999.0,
    ) as ds:
        ds.write(features, 1)
    fixtures.update({
        "hillshade": lambda: whitebox_engine.hillshade(str(dem), out("hs.tif")),
        "slope": lambda: whitebox_engine.slope(str(dem), out("slope.tif")),
        "aspect": lambda: whitebox_engine.aspect(str(dem), out("aspect.tif")),
        "flow_accumulation": lambda: whitebox_engine.flow_accumulation(
            str(dem), out("facc.tif")
        ),
        "watershed": lambda: whitebox_engine.watershed(
            str(dem), str(pour), out("ws.tif")
        ),
        "focal_statistics": lambda: whitebox_engine.focal_statistics(
            str(dem), out("focal.tif"), statistic="mean", window=3
        ),
        "extract_streams": lambda: whitebox_engine.extract_streams(
            whitebox_engine.flow_accumulation(str(dem), out("facc_for_streams.tif"))
            and out("facc_for_streams.tif"),
            out("streams.tif"),
            threshold=5.0,
        ),
        "curvature": lambda: whitebox_engine.curvature(
            str(dem), out("curv.tif"), kind="profile"
        ),
        "flow_direction": lambda: whitebox_engine.flow_direction(
            str(dem), out("d8.tif"), method="d8"
        ),
        # A mask, not the DEM: euclidean_distance measures from the NON-ZERO
        # cells, and every cell of the DEM is non-zero, so it would be all zeros.
        "euclidean_distance": lambda: whitebox_engine.euclidean_distance(
            str(mask), out("dist.tif")
        ),
        "idw_interpolation": lambda: whitebox_engine.idw_interpolation(
            str(quad), out("idw.tif"), field_name="v", cell_size=10.0
        ),
        "viewshed": lambda: whitebox_engine.viewshed(
            str(dem), str(pour), out("seen.tif"), station_height=2.0
        ),
        "sample_raster_at_points": lambda: sampling.sample_raster_at_points(
            str(dem), str(points), out("sampled.parquet"), "bilinear"
        ),
        # With the gradient: it adds parameters and a check to the record. The
        # line in another CRS than the DEM, so the record carries source_crs,
        # target_crs and a transformation the output did not take.
        "elevation_profile": lambda: sampling.elevation_profile(
            str(dem), str(streets_elsewhere), out("profile.parquet"), spacing=25.0,
            grade_base_length=50.0, grade_threshold_percent=5.0,
        ),
    })
    return fixtures



def _ramp(tmp_path) -> str:
    """A planar DEM: z = column index, 10 m cells. Contours land on cell centres."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    path = tmp_path / "ramp.tif"
    if not path.exists():
        values = np.tile(np.arange(12, dtype="float32"), (12, 1))
        with rasterio.open(
            path, "w", driver="GTiff", height=12, width=12, count=1,
            dtype="float32", crs="EPSG:32632",
            transform=from_origin(1000.0, 5000.0, 10.0, 10.0),
        ) as dst:
            dst.write(values, 1)
    return str(path)


def _uniform_cost(tmp_path) -> str:
    """Every cell costs 1, so the cheapest route is the straight one."""
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    path = tmp_path / "cost.tif"
    if not path.exists():
        with rasterio.open(
            path, "w", driver="GTiff", height=10, width=10, count=1,
            dtype="float32", crs="EPSG:32632",
            transform=from_origin(0, 10, 1, 1),
        ) as dst:
            dst.write(np.ones((10, 10), dtype="float32"), 1)
    return str(path)


def _one_point(tmp_path, name: str, x: float, y: float) -> str:
    import geopandas as gpd
    from shapely.geometry import Point

    path = tmp_path / f"{name}.parquet"
    if not path.exists():
        gpd.GeoDataFrame(
            {"id": [1]}, geometry=[Point(x, y)], crs="EPSG:32632"
        ).to_parquet(path)
    return str(path)


def test_a_crash_writes_a_manifest_the_published_validator_accepts(tmp_path):
    """Four call sites passed an empty precondition list, so an engine crash
    wrote `verification: []` — which the specification rejects, in its own
    words because a record with no checks is "a log entry wearing a manifest's
    clothes".

    Two of the four were operations added in 0.4.0: the module that arrived in
    this release did not inherit the pattern. The conformance sweep could not
    see it because it exercises only the paths that succeed.
    """
    import json
    from pathlib import Path

    from mapsmith.provenance import ProvenanceRecord

    out = tmp_path / "out.parquet"
    record = ProvenanceRecord(
        operation="run_sql",
        parameters={"query": "SELECT 1"},
        inputs=[],
        engine={"name": "duckdb", "version": "1.5.5"},
    )
    with pytest.raises(RuntimeError), verify.audit_on_failure(record, str(out), []):
        raise RuntimeError("the engine blew up")

    manifest = json.loads(
        Path(f"{out}.provenance.json").read_text(encoding="utf-8")
    )
    assert manifest["verification"], "a crash wrote a record with no checks"
    assert manifest["verification"][0]["passed"] is False

    # BOTH implementations, via the helper this file already has. The first
    # version of this test used only the vendored validator — the lenient one of
    # the two — which is the thing `_spec_problems`'s own docstring forbids, and
    # a `pipeline: null` divergence between them was live at the time.
    assert _spec_problems(manifest) == [], _spec_problems(manifest)


def test_an_operation_that_verifies_nothing_raises_and_still_writes_the_record(tmp_path):
    """The success-path half of the same rule, and it used to be the other half.

    Until 2026-09-05 this test was called `..._raises_rather_than_writing` and
    asserted only the raise. That was deliberate — a record with no checks is
    "a log entry wearing a manifest's clothes", so the branch refused to write
    one — and it broke the requirement on the other side: the dataset is
    already on disk when `audited` runs, and §4 says a conforming producer
    emits a record for **every dataset it writes**. Raising left an orphan.

    Both hold when the absence is recorded as a failed check, which is what
    `audit_on_failure` does for a crash. So: the caller still gets its
    VerificationError, the orphan is gone, and the record that appears is
    conforming to both implementations — checked here, because a record
    written to satisfy the specification that the specification rejects would
    be worse than no record at all.
    """
    from mapsmith.provenance import ProvenanceRecord

    record = ProvenanceRecord(
        operation="pretend_operation",
        parameters={},
        inputs=[],
        engine={"name": "test", "version": "0"},
    )
    out = tmp_path / "out.parquet"
    out.write_bytes(b"")
    with pytest.raises(verify.VerificationError, match="no verification at all") as raised:
        verify.audited(
            record,
            str(out),
            operation="pretend_operation",
            checks_fn=list,
        )

    # The SENTENCE, not just the raise. `enforce` builds its message from the
    # failed check names, and every name that is not an input precondition fell
    # into the branch that says "output failed deterministic verification" —
    # false here, and false in the direction that matters: an agent reading
    # "output failed" retries or repairs the DATA, when the defect is in the
    # operation and a second run produces the same nothing.
    message = str(raised.value)
    assert "verified nothing about its output" in message
    assert "output failed" not in message

    written = out.with_name(out.name + ".provenance.json")
    assert written.exists(), "the dataset is on disk and its record is not"
    manifest = json.loads(written.read_text(encoding="utf-8"))
    assert [c["name"] for c in manifest["verification"]] == [
        "x-mapsmith:verification_present"
    ]
    assert manifest["verification"][0]["passed"] is False
    assert _spec_problems(manifest) == [], _spec_problems(manifest)


def _writers_by_shape() -> tuple[dict[str, str], dict[str, str]]:
    """Every dataset writer in the engines, split by how it reaches the manifest.

    Derived from the source rather than listed, because a list is worth exactly
    what somebody remembered to put in it: the point of this pair of tests is
    the writer nobody adds to a list.
    """
    import ast
    import pathlib

    import mapsmith.engines

    audited: dict[str, str] = {}
    inline: dict[str, str] = {}
    root = pathlib.Path(mapsmith.engines.__file__).parent
    for module in sorted(root.glob("*.py")):
        text = module.read_text(encoding="utf-8")
        tree = ast.parse(text)
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.get_source_segment(text, node) or ""
            where = f"{module.name}:{node.name}"
            if "verify.audited(" in body:
                audited[where] = body
            elif ".write_for(" in body:
                # `.write_for(` and not the whole `.finish().write_for(output_path)`
                # line: keying on the literal meant a writer whose output
                # parameter happened to be named differently would be invisible
                # to both guards below — it would not fail, it would disappear,
                # which is the defect these guards exist to close, one level up.
                inline[where] = body
    return audited, inline


def test_no_writer_reaches_the_manifest_from_outside_the_engines():
    """The other half of the same worry: a writer in a module nobody scans.

    `_writers_by_shape` reads `engines/`, because that is where dataset writers
    live. That is a true statement about today and an assumption about tomorrow,
    so it is asserted rather than assumed: `write_for` may be called from the
    engines, from the module that defines it, and from the two helpers in
    `verify` that wrap the sequence. Anywhere else is a writer that neither
    guard can see.
    """
    import pathlib

    import mapsmith

    root = pathlib.Path(mapsmith.__file__).parent
    allowed = {"provenance.py", "verify.py"}
    stray = [
        str(module.relative_to(root))
        for module in sorted(root.rglob("*.py"))
        if module.parent.name != "engines"
        and module.name not in allowed
        and ".write_for(" in module.read_text(encoding="utf-8")
    ]
    assert not stray, (
        f"these modules write a manifest and live outside engines/, so neither "
        f"writer guard scans them: {stray}. Either move the writer, or widen "
        "`_writers_by_shape` — do not widen this allow-list without doing one."
    )


def test_every_writer_enforces_after_writing_the_manifest():
    """Manifest first, enforce second — and *enforce* is the half that can vanish.

    `mapsmith/CLAUDE.md` used to say that writers go through `verify.audited`
    "so the audit-trail-first invariant cannot be bypassed". Seventeen of the
    fifty-seven writers did not go through it, so the sentence was false on a
    public page, and one of the seventeen — `run_sql` — wrote its manifest and
    then never called `verify.enforce` at all. Its two checks are both
    non-critical, so nothing was wrong with the output; what was wrong is that a
    critical check added there later would have been recorded and not applied,
    which is the shape of defect this file exists to catch.
    """
    audited, inline = _writers_by_shape()
    assert audited, "no writer reaches the manifest through verify.audited"
    missing = sorted(
        where for where, body in inline.items() if "verify.enforce(" not in body
    )
    assert not missing, (
        "these writers build the manifest by hand and never enforce, so a "
        f"critical check would be recorded and ignored: {missing}"
    )


def test_the_number_of_hand_written_writers_only_goes_down():
    """A ratchet, not a pin.

    Open-coding the sequence is a migration in progress, not a second sanctioned
    shape (see the roadmap item). A new writer must use `verify.audited`, so
    this number may fall and must never rise — and when it falls, lower it here.
    """
    _, inline = _writers_by_shape()
    assert len(inline) <= 17, (
        f"{len(inline)} writers now build the manifest by hand, up from 17. A new "
        "writer goes through verify.audited: " + ", ".join(sorted(inline))
    )


def test_a_crash_manifest_that_cannot_be_written_says_so_on_the_exception(tmp_path):
    """The MUST that was protected by `suppress(Exception)`, which protects nothing.

    Section 3.1 of the manifest specification says a manifest MUST be written
    even when verification fails. `audit_on_failure` wrapped its write in
    `with suppress(Exception)`, so the audit trail this helper exists to save
    could itself vanish with nothing said anywhere — the contents of the crash
    record were made honest on 2026-09-02 while its existence stayed
    best-effort.

    Two behaviours are asserted, in the order that matters:

    1. Hashing the output is the only part of the write that reads a file the
       crashed engine may still hold, so when that raises the manifest is
       written WITHOUT `output` rather than not at all. A record with no
       `output` is valid and merely cannot be checked against bytes; a record
       that does not exist cannot be checked against anything.
    2. If even that fails, the loss is attached to the exception the caller
       already receives. Silence is the only outcome that is not allowed.
    """
    from mapsmith.provenance import ProvenanceRecord

    record = ProvenanceRecord(
        operation="pretend_operation",
        parameters={},
        inputs=[],
        engine={"name": "test", "version": "0"},
    )
    output = tmp_path / "held.parquet"
    output.write_bytes(b"some bytes")
    passed = verify.Check("input_crs_present", True, "EPSG:4326")

    def unreadable(_path):
        raise PermissionError("the engine still holds this file open")

    import mapsmith.provenance as prov

    original = prov.sha256_of
    prov.sha256_of = unreadable
    try:
        with (
            pytest.raises(RuntimeError, match="the engine died"),
            verify.audit_on_failure(record, str(output), [passed]),
        ):
            raise RuntimeError("the engine died")
    finally:
        prov.sha256_of = original

    written = tmp_path / "held.parquet.provenance.json"
    assert written.exists(), (
        "the output could not be hashed and the whole manifest was dropped — "
        "this is the MUST that suppress(Exception) used to hide"
    )
    manifest = json.loads(written.read_text(encoding="utf-8"))
    assert "output" not in manifest, "the digest was supposed to be the part dropped"
    names = [c["name"] for c in manifest["verification"]]
    assert "x-mapsmith:operation_completed" in names
    assert "input_crs_present" in names

    # 2. When nothing can be written, the caller is told on the exception it
    #    already has, rather than being left to discover the gap later.
    second = tmp_path / "gone" / "out.parquet"  # parent does not exist
    record2 = ProvenanceRecord(
        operation="pretend_operation",
        parameters={},
        inputs=[],
        engine={"name": "test", "version": "0"},
    )
    with (
        pytest.raises(RuntimeError) as raised,
        verify.audit_on_failure(record2, str(second), [passed]),
    ):
        raise RuntimeError("the engine died again")
    notes = " ".join(getattr(raised.value, "__notes__", []))
    assert "could not write the crash manifest" in notes, (
        "the manifest could not be written and nothing said so: "
        f"notes were {getattr(raised.value, '__notes__', [])!r}"
    )
    assert "no audit trail on disk" in notes


def test_a_crash_after_passing_preconditions_still_records_the_failure(tmp_path):
    """The `or` that made a crashed run look like a successful one.

    `audit_on_failure` recorded its failure check only when the precondition
    list was empty — `list(preconditions) or [...]`. Every operation that checks
    its inputs first passes a non-empty list, which is about 59 paths counting
    the ones that reach it through `verify.audited`, and on those an engine
    crash wrote a manifest containing nothing but the checks that had already
    passed. Conforming, and unreadable in the one way that matters: it reads
    like a success.

    The point of the test is the combination — a passing precondition AND a
    crash — because each half alone was already fine.
    """
    from mapsmith.provenance import ProvenanceRecord

    record = ProvenanceRecord(
        operation="pretend_operation",
        parameters={},
        inputs=[],
        engine={"name": "test", "version": "0"},
    )
    output = tmp_path / "out.parquet"
    output.write_bytes(b"")
    passed = verify.Check("input_crs_present", True, "EPSG:4326")

    with (
        pytest.raises(RuntimeError, match="the engine died"),
        verify.audit_on_failure(record, str(output), [passed]),
    ):
        raise RuntimeError("the engine died")

    manifest = json.loads(
        (tmp_path / "out.parquet.provenance.json").read_text(encoding="utf-8")
    )
    names = [c["name"] for c in manifest["verification"]]
    assert "input_crs_present" in names, "the precondition was dropped"
    assert "x-mapsmith:operation_completed" in names, (
        "the run crashed and the manifest says every check passed — this is the "
        "record reading like a success"
    )
    failed = [c for c in manifest["verification"] if not c["passed"]]
    assert len(failed) == 1 and failed[0]["name"] == "x-mapsmith:operation_completed"
    # And it does not claim the passing checks say anything about the result.
    assert "BEFORE that point" in failed[0]["detail"]


def test_alignment_decisions_writes_only_conforming_keys():
    """The keys of the one helper both sweeps have to take on trust.

    `alignment_decisions` is a function, so the AST sweep records it as a blind
    spot rather than reading through it, and the conformance sweep only reaches
    its quiet branch — the fixtures hand every operation inputs that already
    share a CRS, so nothing is ever reprojected in them. Between the two, the
    branch that emits the most keys is seen by neither.

    So it is pinned here, on both branches, against the same predicate the
    other two use. Not a list of expected keys: whatever it emits has to be a
    key section 3.7 recommends or a MapSmith extension, and a key added
    tomorrow is judged by the rule rather than by whether somebody remembered
    to add it to an assertion.
    """
    from mapsmith.provenance import alignment_decisions

    fixed = _spec_crs_keys()
    cases = {
        "nothing moved": alignment_decisions("EPSG:32632", "already aligned"),
        "one moved": alignment_decisions(
            "EPSG:32632", "the mask was aligned", [("mask_path", "EPSG:4267")]
        ),
        "several moved": alignment_decisions(
            "EPSG:32632",
            "two layers were aligned",
            [("input_2", "EPSG:4326"), ("input_3", "EPSG:4267")],
        ),
    }
    for label, decisions in cases.items():
        offenders = [
            key
            for key in decisions
            if key not in fixed and not _EXTENSION_KEY.fullmatch(key)
        ]
        assert not offenders, f"{label}: {offenders}"

    # And the substance, because conforming keys with nothing in them would
    # pass the paragraph above. One input moved: the transformation goes in the
    # specification's own key. Several: there is no single transformation, so
    # each entry carries its own and the top-level key is absent rather than
    # holding one of them and implying it covers both.
    one = cases["one moved"]
    assert isinstance(one["transformation"]["is_ballpark"], bool)
    assert one[INPUTS_REPROJECTED] == [{"argument": "mask_path", "from": "EPSG:4267"}]

    several = cases["several moved"]
    assert "transformation" not in several
    assert [entry["argument"] for entry in several[INPUTS_REPROJECTED]] == [
        "input_2",
        "input_3",
    ]
    assert all(
        isinstance(entry["transformation"]["is_ballpark"], bool)
        for entry in several[INPUTS_REPROJECTED]
    )

    assert INPUTS_REPROJECTED not in cases["nothing moved"]


def test_every_reprojected_input_names_a_real_argument():
    """A wrong argument name in the record is worse than no name at all.

    `INPUTS_REPROJECTED` exists so a reader knows WHICH input was moved. On
    2026-09-06 `watershed` recorded `points_path` and the operation's argument
    is `pour_points_path` -- the local variable's name, written down instead of
    the caller's. A reader looking for `points_path` in their own call finds
    nothing and concludes the record is about some other run.

    **Read from the source, and the first version of this test was not.** It
    ran every operation and inspected the records, which sounds stronger and is
    weaker: the fixtures hand every operation inputs that already share a CRS,
    so no reprojection branch is ever taken and there was nothing to inspect.
    Restoring the wrong name left it green. That is the guard-that-cannot-fail
    again, written by the person who spent the day removing them -- and it is
    why the sabotage runs before the test is believed.
    """
    import ast
    from pathlib import Path

    import mapsmith
    from mapsmith import catalog
    from mapsmith.plans.registry import BINDINGS

    # The names a caller can actually pass, per engine function. The catalogue
    # is keyed by operation name and the engine function may be called something
    # else (`buffer` implements `buffer_layer`), so the binding is what joins
    # them -- the same join `test_path_containment` makes.
    parameters = {
        entry["name"]: {
            parameter["name"] if isinstance(parameter, dict) else str(parameter)
            for parameter in entry.get("parameters", [])
        }
        for entry in catalog.OPERATIONS
    }
    # The binding carries the caller-facing names too, and they are the
    # authority: `input_args` is what the plan validator checks and what an
    # agent writes. Joined to the engine function by the operation the function
    # NAMES ITSELF -- `ProvenanceRecord(operation="clip_layer")` -- because the
    # binding's `loader` is a wrapper, not the engine function, and matching on
    # `__name__` joined nothing at all.
    allowed: dict[str, set[str]] = {}
    for operation, binding in BINDINGS.items():
        allowed[operation] = (
            set(parameters.get(operation, ()))
            | set(getattr(binding, "input_args", ()) or ())
            | set(getattr(binding, "list_input_args", ()) or ())
        )

    root = Path(mapsmith.__file__).parent
    named: list[tuple[str, str, str]] = []
    for module in sorted(root.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef):
                continue
            declares = [
                keyword.value.value
                for call in ast.walk(function)
                if isinstance(call, ast.Call)
                and getattr(call.func, "id", None) == "ProvenanceRecord"
                for keyword in call.keywords
                if keyword.arg == "operation"
                and isinstance(keyword.value, ast.Constant)
            ]
            uses_helper = any(
                isinstance(call, ast.Call)
                and (
                    call.func.attr if isinstance(call.func, ast.Attribute)
                    else getattr(call.func, "id", None)
                )
                == "alignment_decisions"
                for call in ast.walk(function)
            )
            if not uses_helper:
                continue
            # Every two-tuple with a string literal first, anywhere in a function
            # that calls the helper. Reading only the third positional argument
            # found nothing: at the real call sites `moved` is a conditional
            # expression, a comprehension or a variable built earlier, and a
            # sweep that only understands a list literal understands none of the
            # twelve.
            for node in ast.walk(function):
                if not isinstance(node, ast.Tuple) or len(node.elts) != 2:
                    continue
                first = node.elts[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    for operation in declares:
                        named.append((module.name, operation, first.value))

    assert len(named) >= 8, (
        f"only {len(named)} argument names read from the source: the sweep is not "
        "finding the call sites any more"
    )
    wrong = [
        f"{module}:{operation} names {argument!r}"
        for module, operation, argument in named
        if argument not in allowed.get(operation, set())
    ]
    assert not wrong, (
        f"these name an input that is not an argument of their operation: {wrong}. "
        "The point of the key is that a reader can find the argument in their own "
        "call; a local variable's name sends them looking for something that is "
        "not there."
    )


def test_every_declared_extension_is_actually_written_somewhere():
    """The other half of the registry, asked where it can be answered.

    The AST sweep cannot ask it: three of the six keys are written inside
    `alignment_decisions` and `manifest_decisions`, which it records as blind
    spots by design rather than reading through. Comparing the registry against
    what that sweep sees therefore called three live keys stale -- the check was
    wrong, not the code.

    So the question is asked of the source as a whole: a declared key that no
    line writes is a name nobody emits, and a registry of those is a list that
    grows and never shrinks. The reason each key exists is in the registry; this
    only asks that the key still does.
    """
    # The registry's OWN declaration is cut out of the text first, and without
    # that this test cannot fail: declaring a key is what puts it in the source,
    # so every entry would find itself. Fourth guard-that-cannot-fail written
    # today, and the sabotage found it in seconds (D-079).
    import ast
    from pathlib import Path

    import mapsmith
    from mapsmith.provenance import CRS_EXTENSIONS

    root = Path(mapsmith.__file__).parent
    home = root / "provenance.py"
    lines = home.read_text(encoding="utf-8").splitlines(keepends=True)
    for node in ast.parse("".join(lines)).body:
        targets = getattr(node, "targets", []) or [getattr(node, "target", None)]
        if any(getattr(t, "id", None) == "CRS_EXTENSIONS" for t in targets if t):
            del lines[node.lineno - 1 : node.end_lineno]
            break
    else:  # pragma: no cover - the registry moved and this test is now blind
        raise AssertionError("CRS_EXTENSIONS is no longer a module-level assignment")

    source = "".join(lines) + chr(10).join(
        module.read_text(encoding="utf-8")
        for module in sorted(root.rglob("*.py"))
        if module != home
    )
    unwritten = [
        key
        for key, name in (
            (key, key.removeprefix("x-mapsmith:")) for key in CRS_EXTENSIONS
        )
        if key not in source and name not in source
    ]
    assert not unwritten, (
        f"these are declared in CRS_EXTENSIONS and written by no line: {unwritten}. "
        "Remove them — a registry of names nobody emits is a list that only grows, "
        "and the next reader believes it."
    )
    assert len(CRS_EXTENSIONS) >= 5, (
        f"only {len(CRS_EXTENSIONS)} extensions declared, which cannot be right"
    )
    thin = [key for key, why in CRS_EXTENSIONS.items() if len(why) < 80]
    assert not thin, (
        f"these are declared with no real reason: {thin}. The sentence is the point "
        "of the registry: it is what a prefix cannot supply."
    )


def test_the_published_vocabulary_is_what_the_source_says_today():
    """The page of names, and the two derivations of them that must agree.

    A vocabulary a consumer has to read the engines to learn is half a
    vocabulary, so `docs/manifest-vocabulary.md` lists it — generated, because
    a hand-written list of sixty names is worth what whoever last remembered to
    update it was worth.

    The assertion that earns its place is the second one. There are now two
    readings of the same set: the generator's, which lists, and the sweep
    above, which polices. Two copies of one rule is how a rule quietly becomes
    two rules — and this project has watched exactly that happen to a manifest
    validator and its schema, which had drifted on every recommended field. So
    the two are compared, and a name either derivation finds alone is a
    failure.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "benchmarks"))
    import manifest_vocabulary as vocabulary

    published = (root / "docs" / "manifest-vocabulary.md").read_text(encoding="utf-8")
    assert published == vocabulary.page(), (
        "docs/manifest-vocabulary.md is not what the source says now. Regenerate "
        "with `python benchmarks/manifest_vocabulary.py --write` and read the diff: "
        "a name that appeared or vanished is a change to what a consumer can "
        "branch on."
    )

    # The two derivations, compared. `_check_names_in_source` is the policing
    # one — it refuses names it cannot read rather than skipping them, so it is
    # the stricter of the two and the generator must not see more than it does.
    listed = set(vocabulary.check_names())
    policed, _ = _check_names_in_source()
    policed = set(policed)
    assert listed == policed, (
        "the generator and the vocabulary guard disagree about which check names "
        f"exist. Only the generator: {sorted(listed - policed)}. Only the guard: "
        f"{sorted(policed - listed)}. One rule, two readings, and they have "
        "started to drift."
    )


#: Writing operations whose output legitimately declares no CRS. Empty, and
#: measured: all 58 write a georeferenced dataset. A table of statistics with no
#: geometry would belong here -- declared, with the reason, rather than lowering
#: a threshold until it passes.
NO_OUTPUT_CRS: set[str] = set()

#: Operations that write their dataset OUTSIDE `audit_on_failure`, with the
#: number of uncovered write sites in each. **Empty**, and it stays a ratchet
#: rather than an assertion of zero because the useful question is not "is it
#: zero today" but "did a new one appear". It was eighteen sites in nine
#: operations when this was measured on 2026-09-07, and zero by the end of the
#: same day: the eight that only needed a `with`, then the ten whose write had
#: to move down into the net. See
#: `test_no_new_operation_writes_a_dataset_without_a_net`.
WRITES_WITHOUT_AN_AUDIT: dict[tuple[str, str], int] = {}


def _writes_outside_the_net() -> tuple[dict[tuple[str, str], int], int]:
    """Where a writing operation writes its dataset with no audit around it.

    Invariant 2 is *provenance on every writer*, and `audit_on_failure` is what
    makes it survive an exception: the manifest is written with the failure
    recorded instead of being lost with the traceback. A write outside that
    block has the opposite property. Measured on 2026-09-07 by making `_write`
    leave 516 bytes and raise: **the partial dataset stayed on disk and no
    manifest was written at all** -- the data landing where the manifest is not,
    which is the same shape as the trailing-dot defect of 2026-09-02 with a
    different cause.

    Returns the uncovered sites per (module, function), and the number of
    covered ones -- which is the anti-vacuity number. Asserting on the uncovered
    count alone would pass the day this sweep stops reading the source at all.
    """
    import ast
    from pathlib import Path

    package = Path(verify.__file__).parent
    writers = {"_write", "to_parquet", "to_file"}

    def holds(block: ast.With, node: ast.AST) -> bool:
        last = max(getattr(x, "lineno", block.lineno) for x in ast.walk(block))
        return block.lineno <= node.lineno <= last

    uncovered: dict[tuple[str, str], int] = {}
    covered = 0
    for module in sorted(package.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = [c for c in ast.walk(fn) if isinstance(c, ast.Call)]
            # A writing operation is one that goes through `verify.audited`.
            if not any("audited" in ast.unparse(c.func) for c in calls):
                continue
            nets = [
                w for w in ast.walk(fn)
                if isinstance(w, ast.With)
                and any("audit_on_failure" in ast.unparse(i.context_expr) for i in w.items)
            ]
            for call in calls:
                name = getattr(call.func, "attr", getattr(call.func, "id", None))
                if name not in writers:
                    continue
                if any(holds(w, call) for w in nets):
                    covered += 1
                else:
                    key = (module.relative_to(package).as_posix(), fn.name)
                    uncovered[key] = uncovered.get(key, 0) + 1
    return uncovered, covered


def test_no_new_operation_writes_a_dataset_without_a_net():
    """A ratchet on invariant 2: the list above may shrink, never grow.

    The list is empty, and the test is still worth its runtime for the other two
    assertions: a NEW uncovered write fails it, and so does the derivation
    quietly stopping. The eighteen sites it was written for were closed the same
    day -- eight by wrapping the write where it stood, ten by moving the write
    down to just before the verification that reads it, which was safe because
    nothing those records hold depends on the write and nothing between the two
    positions touches the file.
    """
    uncovered, covered = _writes_outside_the_net()

    # ANTI-VACUITY, and it is on what the sweep must SEE rather than on what it
    # must find: if the derivation breaks, `uncovered` goes empty and every
    # assertion below passes. `covered` going to zero is the tell.
    assert covered >= 30, (
        f"the sweep found only {covered} writes INSIDE an audit block, and there "
        "were 40 when this floor was set. It has stopped reading the source, and "
        "an empty list of offenders below would then mean nothing -- which is the "
        "whole failure mode this floor exists for."
    )

    new = {
        where: count
        for where, count in uncovered.items()
        if count > WRITES_WITHOUT_AN_AUDIT.get(where, 0)
    }
    assert not new, (
        f"these operations write a dataset with no `audit_on_failure` around it: "
        f"{new}. If the write raises after touching the file, the dataset is on "
        "disk and the manifest is not -- invariant 2, measured. Wrap the write, "
        "moving the ProvenanceRecord above it if it is built after."
    )

    fixed = {
        where: WRITES_WITHOUT_AN_AUDIT[where]
        for where in WRITES_WITHOUT_AN_AUDIT
        if uncovered.get(where, 0) < WRITES_WITHOUT_AN_AUDIT[where]
    }
    assert not fixed, (
        f"these are covered now, and the ratchet still lists them: {fixed}. "
        "Lower the numbers in WRITES_WITHOUT_AN_AUDIT -- a ratchet that is not "
        "tightened is a list of things somebody once meant to do."
    )


def test_the_version_the_writers_declare_is_the_one_the_vendored_schema_carries():
    """The one place `SPEC_VERSION` can be checked without the spec repository.

    `provenance.SPEC_VERSION` is a hand-typed string, and until 2026-09-07 there
    was nothing on this side of the fence to compare it against: the vendored
    schema accepts any `1.x.y` by design, so it said nothing about which draft
    it was, and the only check on the version compared the code with the
    CHANGELOG -- two files in the same repository, which drift together.

    The specification's schema now declares its own version in `x-spec-version`,
    a keyword every JSON Schema validator ignores. That makes this comparison
    possible in CI, with no sibling checkout: re-vendoring the schema and
    forgetting to move the string now fails here, which is the mistake this is
    for.
    """
    import json
    from pathlib import Path

    from mapsmith import provenance

    schema = json.loads(
        (Path(__file__).parent / "data" / "manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    declared = schema.get("x-spec-version")
    assert declared, (
        "the vendored schema carries no `x-spec-version`. Either it was vendored "
        "from a copy older than 1.0.0-draft.3, or the keyword was dropped in the "
        "specification -- and in both cases nothing on this side can tell which "
        "draft the fixtures are checking against."
    )
    assert provenance.SPEC_VERSION == declared, (
        f"the writers declare spec_version {provenance.SPEC_VERSION!r} and the "
        f"vendored schema is {declared!r}. Whichever moved, the records this "
        "suite validates are being checked against a different draft than they "
        "claim to target."
    )


def test_the_vendored_schema_and_validator_are_the_published_ones():
    """Skipped without the sibling checkout, and that is why it is not the only one.

    A test that can only run on a developer's disk is not a guard in CI, so the
    version tie above does the work that has to happen on every push. This one
    catches the other half: a vendored copy edited here instead of upstream, or
    an upstream change never brought across. Bodies are compared with line
    endings normalised, because those are decided by whichever checkout wrote
    the file and not by either project.
    """
    from pathlib import Path

    # The sibling path was written as parents[3] first, which resolved to the
    # drive root and would have made this test skip in silence for ever; and
    # even at parents[2] it skipped in CI, which has no sibling checkout, until
    # 2026-10-05. `spec_checkout` resolves both and fails where CI requires it.
    from conftest import spec_checkout

    spec_repo = spec_checkout()

    here = Path(__file__).parent / "data"
    def body_after_the_docstring(path: Path) -> list[str]:
        """Everything below the module docstring, normalised for line endings.

        The vendored validator's docstring is deliberately NOT the published
        one: it says it is a copy, where it came from, and that drift is a
        finding rather than something to merge. Comparing whole files fails on
        the single difference that is supposed to be there, and the usual repair
        for a test like that is to delete it.
        """
        import ast

        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        first = tree.body[0] if tree.body else None
        is_docstring = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )
        start = first.end_lineno if is_docstring else 0
        return source.splitlines()[start:]

    schema_here = here / "manifest-v1.schema.json"
    schema_there = spec_repo / "schema" / "manifest-v1.schema.json"
    assert schema_there.is_file(), f"{schema_there} is missing from the spec checkout"
    assert schema_here.read_text(encoding="utf-8").splitlines() == schema_there.read_text(
        encoding="utf-8"
    ).splitlines(), (
        "the vendored schema differs from the published one. Copy the published "
        "one across rather than editing the copy: this suite validates against "
        "the vendored file, so an edit here makes the tests agree with "
        "themselves and with nothing else."
    )

    validator_here = here / "manifest_spec_validator.py"
    validator_there = spec_repo / "validator" / "validate.py"
    assert validator_there.is_file(), f"{validator_there} is missing from the spec checkout"
    assert body_after_the_docstring(validator_here) == body_after_the_docstring(
        validator_there
    ), (
        "the vendored validator differs from the published one BELOW its "
        "docstring. Copy the published body across: the header here is ours and "
        "says so, everything under it is theirs."
    )


def test_two_chained_operations_link_by_the_output_digest(tmp_path, monkeypatch):
    """Section 6 of the specification says multi-step lineage needs no new
    field: the second record's `inputs[].sha256` is the first record's
    `output.sha256`, so a consumer holding only the final file can walk back.

    Nothing checked that with real bytes until 2026-09-13. It matters here more
    than in the specification repository, because MapSmith is where the claim
    meets formats that a reader can modify while opening them -- a GeoPackage is
    a SQLite database, and a driver that touched it on read would break the link
    while every individual record stayed true.
    """
    import hashlib
    import json

    import geopandas as gpd
    from shapely.geometry import Point

    from mapsmith.engines import vector

    monkeypatch.setenv("MAPSMITH_WORKSPACE", str(tmp_path))
    source = tmp_path / "points.gpkg"
    gpd.GeoDataFrame(
        {"id": [1, 2]}, geometry=[Point(0, 0), Point(100, 100)], crs="EPSG:32633"
    ).to_file(source, driver="GPKG")

    buffered = tmp_path / "buffered.gpkg"
    centroids = tmp_path / "centroids.gpkg"
    vector.buffer(str(source), 10.0, str(buffered))
    vector.centroid(str(buffered), str(centroids))

    upstream = json.loads(
        (tmp_path / "buffered.gpkg.provenance.json").read_text(encoding="utf-8")
    )
    downstream = json.loads(
        (tmp_path / "centroids.gpkg.provenance.json").read_text(encoding="utf-8")
    )

    # Anti-vacuity on what the check must SEE. Without it this passes when the
    # upstream record has no `output` at all -- which is a valid record, and
    # exactly the state in which the chain silently stops working.
    digest = (upstream.get("output") or {}).get("sha256")
    assert digest, (
        "the upstream manifest carries no output digest, so there is no link to "
        "check and section 6's claim is untestable here"
    )
    assert digest == hashlib.sha256(buffered.read_bytes()).hexdigest(), (
        "the recorded output digest is not the digest of the bytes on disk: "
        "something wrote or touched the file after the manifest was written"
    )
    assert digest in [i["sha256"] for i in downstream["inputs"]], (
        "the second operation read the first operation's output and recorded a "
        "different digest for it, so the chain does not resolve. Either the "
        "reader modified the file on open, or the two ends hash different bytes."
    )


def test_every_extension_name_the_source_emits_is_on_the_published_page():
    """`docs/manifest-vocabulary.md` says it lists the names MapSmith adds to a
    manifest. Until 2026-09-13 it listed the names in three containers, and the
    page could not tell the difference: it derives a section per container from
    a list of containers, so a key added to a fourth was documented nowhere and
    nothing was red. `engine.x-mapsmith:geometry_library` and
    `repairs[].x-mapsmith:round` had been shipping in that gap.

    This sweep does not know about containers. It reads every string constant in
    the package that IS an extension name -- the whole string, so prose and
    comments mentioning a name are not mistaken for one being emitted -- and
    requires the page to carry it.

    The comparison is on a word boundary, and that is not fussiness: checking
    for `x-mapsmith:round` as a plain substring finds `x-mapsmith:round_trip`
    and reports a missing name as present. That false negative happened while
    this test was being written.
    """
    import ast
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    package = root / "src" / "mapsmith"
    shape = re.compile(r"^x-mapsmith:[a-z0-9_]+$")

    emitted: dict[str, str] = {}
    for module in sorted(package.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and shape.match(node.value)
            ):
                emitted.setdefault(node.value, module.name)

    # Anti-vacuity on what the sweep must SEE, not on what it must find. These
    # three live in three different containers, so a change that narrows the
    # sweep to one of them fails here instead of quietly checking less.
    # The `crs_decisions` anchor was `x-mapsmith:round_trip` until 2026-09-23,
    # when that key entered the specification as `round_trip` (draft.6, D-091)
    # and stopped being ours to prefix. Its replacement is one every raster
    # manifest with a registration carries, so the anchor names a key that is
    # really emitted and not one that is merely declared.
    for expected in (
        "x-mapsmith:geometry_library",     # engine
        "x-mapsmith:round",                # repairs[]
        "x-mapsmith:raster_registration",  # crs_decisions
    ):
        assert expected in emitted, (
            f"the sweep no longer reads {expected} out of the source, so whatever "
            f"it reports about the page proves less than it claims"
        )

    page = (root / "docs" / "manifest-vocabulary.md").read_text(encoding="utf-8")
    undocumented = sorted(
        f"{name} ({module})"
        for name, module in emitted.items()
        if not re.search(re.escape(name) + r"(?![a-z0-9_])", page)
    )
    assert not undocumented, (
        f"these extension names are emitted and appear nowhere on the published "
        f"vocabulary page: {undocumented}. A consumer branching on one has "
        f"nothing to look it up in, which is the whole reason the page exists. "
        f"Add the container to CONTAINER_EXTENSIONS in provenance.py -- with the "
        f"sentence saying why the key is not a synonym -- and regenerate."
    )
