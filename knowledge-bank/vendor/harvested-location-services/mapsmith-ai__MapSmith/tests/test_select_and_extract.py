"""Keeping the features a question is about, and pulling one layer out.

Both operations exist because MapSmith was already telling callers to do them.
The mixed-geometry check says *select the features the question is about*; the
multi-layer refusal says *extract the layer you mean into its own dataset*. Both
then handed over a `run_sql` incantation, which is a strange answer to "keep the
lines".

Counts here are small and deliberate — five features, three of them lines — so
every expected number is countable by eye rather than computed by the same code
under test.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
import shapely

from mapsmith.engines import vector

# Three lines, one polygon, one point: five features, and a mixed layer is the
# case the whole operation was named for.
MIXED = gpd.GeoDataFrame(
    {
        "kind": ["pipe", "pipe", "pipe", "plot", "valve"],
        "diameter_mm": [100, 200, 300, None, 50],
    },
    geometry=[
        shapely.LineString([(0, 0), (0, 100)]),
        shapely.LineString([(0, 0), (100, 0)]),
        shapely.MultiLineString([[(0, 0), (0, 50)], [(0, 60), (0, 100)]]),
        shapely.box(0, 0, 100, 100),
        shapely.Point(50, 50),
    ],
    crs="EPSG:32632",
)


@pytest.fixture
def mixed_path(tmp_path):
    path = tmp_path / "survey.parquet"
    MIXED.to_parquet(path)
    return str(path)


def _read(path):
    return gpd.read_parquet(path)


def test_selecting_a_geometry_family_keeps_its_multi_variant(tmp_path, mixed_path):
    """Three line features, one of them a MultiLineString.

    Somebody asking for the pipes means all three: a MultiLineString is
    line-shaped, and dropping it because of its type name would be a silent
    undercount of exactly the kind this project measures in other people.
    """
    out = tmp_path / "lines.parquet"
    result = vector.select_features(mixed_path, str(out), by="geometry_type", value="line")

    assert result["features_before"] == 5
    assert result["features_kept"] == 3
    assert result["features_removed"] == 2
    assert sorted(_read(out)["kind"]) == ["pipe", "pipe", "pipe"]


def test_the_surviving_geometry_is_untouched(tmp_path, mixed_path):
    """A filter removes rows; it must not move a coordinate.

    Length is the check that would notice a reprojection sneaking in, and it is
    closed-form here: 100 + 100 + (50 + 40) = 290 metres of pipe.
    """
    out = tmp_path / "lines.parquet"
    vector.select_features(mixed_path, str(out), by="geometry_type", value="line")

    kept = _read(out)
    assert kept.crs == MIXED.crs
    assert kept.length.sum() == pytest.approx(290.0)


def test_selecting_an_exact_geometry_type_is_narrower_than_its_family(tmp_path, mixed_path):
    out = tmp_path / "single.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="geometry_type", value="LineString"
    )
    assert result["features_kept"] == 2  # the MultiLineString is excluded by name


def test_field_equals(tmp_path, mixed_path):
    out = tmp_path / "plots.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_equals", field="kind", value="plot"
    )
    assert result["features_kept"] == 1
    assert result["criterion"] == "kind == 'plot'"


def test_field_in(tmp_path, mixed_path):
    out = tmp_path / "two.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_in", field="kind", values=["plot", "valve"]
    )
    assert result["features_kept"] == 2


def test_field_between_is_inclusive_at_both_ends(tmp_path, mixed_path):
    """100 and 200 are both kept; 300 and 50 are not, and the None never is.

    Inclusive bounds are a choice, so they are pinned: half-open would silently
    drop the pipe at 200 for anybody who read the parameter name and assumed.
    """
    out = tmp_path / "band.parquet"
    result = vector.select_features(
        mixed_path,
        str(out),
        by="field_between",
        field="diameter_mm",
        minimum=100,
        maximum=200,
    )
    assert result["features_kept"] == 2
    assert sorted(_read(out)["diameter_mm"]) == [100, 200]


def test_an_open_ended_range_is_allowed(tmp_path, mixed_path):
    out = tmp_path / "big.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_between", field="diameter_mm", minimum=200
    )
    assert result["features_kept"] == 2  # 200 and 300; the None is not a number


def test_matching_nothing_is_answered_not_refused(tmp_path, mixed_path):
    """An empty selection is a legitimate answer to a filter.

    It is also what a typo looks like, so it is *said*: a non-critical check in
    the manifest, with the hint that names the two possibilities. Refusing would
    be worse — the caller would learn nothing about which of the two happened.
    """
    out = tmp_path / "none.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_equals", field="kind", value="Pipe"
    )
    assert result["features_kept"] == 0

    # `result_not_empty`, the core name — not an x-mapsmith one. The spec says
    # a producer that checks a property the core names must use the core name,
    # and this file had an extension name for it until a review caught it.
    warnings = [w["check"] for w in result.get("warnings", [])]
    assert "result_not_empty" in warnings
    empty = next(w for w in result["warnings"] if w["check"] == "result_not_empty")
    # And the hint has to be the one for a FILTER: the default sentence talks
    # about extents and coordinate systems, which have nothing to do with a
    # value that matched nothing.
    assert "misspelled value" in empty["hint"]


def test_the_manifest_says_the_output_is_a_subset(tmp_path, mixed_path):
    """The number that matters downstream is what was removed.

    A total computed from this output is a total of the survivors, and the
    manifest is where somebody auditing the chain finds that out.
    """
    import json
    import pathlib

    out = tmp_path / "lines.parquet"
    result = vector.select_features(mixed_path, str(out), by="geometry_type", value="line")

    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert manifest["parameters"]["features_before"] == 5
    assert any("SUBSET" in note for note in manifest["notes"])

    # The arguments the engine ran with, one key each. `criterion` reads well
    # and stays, but it cannot be the only record: re-running from an English
    # sentence with a Python repr inside is what the spec faults other formats
    # for. `features_kept` is deliberately NOT here — it is an outcome, and
    # outcomes live in the verification and the notes.
    assert manifest["parameters"]["by"] == "geometry_type"
    assert manifest["parameters"]["value"] == "line"
    assert "features_kept" not in manifest["parameters"]

    # And the count that matters is checked against the FILE.
    counted = next(
        c for c in manifest["verification"] if c["name"] == "feature_count_exact"
    )
    assert counted["passed"]


def test_an_unknown_field_is_refused_with_the_real_columns(tmp_path, mixed_path):
    out = tmp_path / "x.parquet"
    with pytest.raises(ValueError, match="diameter_mm"):
        vector.select_features(
            mixed_path, str(out), by="field_equals", field="diametro", value=1
        )


def test_an_unknown_mode_is_refused(tmp_path, mixed_path):
    out = tmp_path / "x.parquet"
    with pytest.raises(ValueError, match="field_between"):
        vector.select_features(mixed_path, str(out), by="where", value="kind = 'pipe'")


def test_an_unknown_geometry_name_names_what_the_layer_holds(tmp_path, mixed_path):
    out = tmp_path / "x.parquet"
    with pytest.raises(ValueError, match="Polygon"):
        vector.select_features(mixed_path, str(out), by="geometry_type", value="Curve")


def test_selection_removes_the_silent_addition_measure_length_can_only_warn_about(
    tmp_path, mixed_path
):
    """The point of the operation, end to end, on Argleton trap 027's defect.

    `measure_length` does not refuse a mixed layer, deliberately: measuring one
    is a legitimate request and MapSmith cannot know which features the question
    was about. It warns, and the warning names a remedy. This test executes the
    remedy and measures what it is worth.

    The layer holds 290 m of pipe and a 100 x 100 m plot whose boundary is 400 m
    long. Shapely answers `length` on a polygon with its perimeter — true, and
    the answer to a question nobody asked — so the mixed total carries the
    fence line in silence. Selecting first removes it, and the difference is
    the perimeter to within the geodesic correction.
    """
    mixed = vector.measure_length(mixed_path, str(tmp_path / "mixed.parquet"))
    warnings = [w["check"] for w in mixed.get("warnings", [])]
    assert "x-mapsmith:one_geometry_type_in_the_layer" in warnings

    lines = tmp_path / "lines.parquet"
    vector.select_features(mixed_path, str(lines), by="geometry_type", value="line")
    honest = vector.measure_length(str(lines), str(tmp_path / "lengths.parquet"))

    # Nothing left to warn about, and the number dropped by the plot's boundary.
    assert "x-mapsmith:one_geometry_type_in_the_layer" not in [
        w["check"] for w in honest.get("warnings", [])
    ]
    assert honest["feature_count"] == 3
    assert mixed["total_length_m"] - honest["total_length_m"] == pytest.approx(400.0, rel=0.01)
    # The pipe measured on the ellipsoid, next to its 290 m on the map plane.
    assert honest["total_length_m"] == pytest.approx(290.0, rel=0.01)


# --------------------------------------------------------------- extract_layer

ROADS = gpd.GeoDataFrame(
    {"name": ["a", "b"]},
    geometry=[shapely.LineString([(0, 0), (10, 0)]), shapely.LineString([(0, 5), (10, 5)])],
    crs="EPSG:32632",
)
PARCELS = gpd.GeoDataFrame(
    {"ref": ["p1", "p2", "p3"]},
    geometry=[shapely.box(i, 0, i + 1, 1) for i in range(3)],
    crs="EPSG:32632",
)


@pytest.fixture
def container(tmp_path):
    path = tmp_path / "city.gpkg"
    ROADS.to_file(path, layer="roads", driver="GPKG")
    PARCELS.to_file(path, layer="parcels", driver="GPKG")
    return str(path)


def test_a_multi_layer_container_is_still_refused_by_everything_else(container, tmp_path):
    """The refusal this operation exists to resolve has to still be there.

    If it ever stops firing, `extract_layer` becomes optional and the first
    layer silently becomes the answer again — which is issue #29 returning.
    """
    # Anchored on the refusal's own words: "(?i)layer" matched almost any error
    # that happened to name a layer, including ones raised for other reasons.
    with pytest.raises(ValueError, match="no layer was chosen"):
        vector.centroid(container, str(tmp_path / "c.parquet"))


def test_extracting_a_layer_copies_it_whole(container, tmp_path):
    out = tmp_path / "parcels.parquet"
    result = vector.extract_layer(container, "parcels", str(out))

    assert result["features"] == 3
    assert result["layers_in_container"] == ["parcels", "roads"]
    assert sorted(_read(out)["ref"]) == ["p1", "p2", "p3"]


def test_the_extracted_layer_keeps_its_crs_and_geometry(container, tmp_path):
    out = tmp_path / "roads.parquet"
    vector.extract_layer(container, "roads", str(out))

    roads = _read(out)
    assert roads.crs == ROADS.crs
    assert roads.length.sum() == pytest.approx(20.0)  # two 10 m roads


def test_the_manifest_records_which_layer_of_which_container(container, tmp_path):
    """Naming the layer is the entire reason the operation exists.

    A manifest that said only "read city.gpkg" would answer the question issue
    #29 was about — which data produced these numbers — with a shrug.
    """
    import json
    import pathlib

    out = tmp_path / "roads.parquet"
    result = vector.extract_layer(container, "roads", str(out))
    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))

    # The field the FORMAT defines for this, not only MapSmith's own key. An
    # auditor holding a five-layer container and this record has to be able to
    # tell which layer produced the numbers, and `inputs[].layer` is where the
    # schema says to look. This test asserted only `parameters` until a review
    # pointed out that it consecrated the private spelling and missed the
    # standard one — which was null.
    assert manifest["inputs"][0]["layer"] == "roads"
    assert manifest["parameters"]["layer"] == "roads"
    assert manifest["parameters"]["layers_in_container"] == ["parcels", "roads"]
    assert manifest["parameters"]["container_layer_count"] == 2
    assert any("parcels" in note for note in manifest["notes"])


def test_an_unknown_layer_lists_the_real_ones(container, tmp_path):
    with pytest.raises(ValueError, match="parcels"):
        vector.extract_layer(container, "Roads", str(tmp_path / "x.parquet"))


def test_a_geoparquet_is_refused_before_ogr_is_consulted(tmp_path, mixed_path):
    """And refused for the right reason, on every machine.

    A GeoParquet has no layers to choose between. Whether GDAL can even *list*
    one depends on whether the build has the Arrow driver, so asking OGR first
    made this call behave differently on a conda install than on a wheel
    install — the shape of #28, in the module written to prevent it.
    """
    with pytest.raises(ValueError, match="GeoParquet"):
        vector.extract_layer(mixed_path, "survey", str(tmp_path / "x.parquet"))


def test_extraction_then_analysis_is_the_route_out_of_the_refusal(container, tmp_path):
    """End to end, the same shape as the select test above.

    The refusal is not a dead end: extract the layer that was meant, and the
    operation that refused now runs on data whose provenance names its source
    layer.
    """
    roads = tmp_path / "roads.parquet"
    vector.extract_layer(container, "roads", str(roads))
    centroids = vector.centroid(str(roads), str(tmp_path / "centroids.parquet"))
    assert centroids["feature_count"] == 2


def test_a_numeric_filter_sent_as_text_still_matches(tmp_path, mixed_path):
    """The wire contract carries lists as strings, and columns hold numbers.

    `plans.models.ArgValue` allows str, bool, int and float as scalars and
    strings only inside a list, so a plan filtering a numeric column arrives
    with "200". Compared as text it matches nothing, the output is empty, and an
    empty output reads as a finding. The conversion is what stops that, so it is
    pinned on both the scalar and the list form.
    """
    out = tmp_path / "one.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_equals", field="diameter_mm", value="200"
    )
    assert result["features_kept"] == 1

    out = tmp_path / "two.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_in", field="diameter_mm", values=["100", "300"]
    )
    assert result["features_kept"] == 2

    out = tmp_path / "range.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_between", field="diameter_mm", minimum="200"
    )
    assert result["features_kept"] == 2


def test_text_that_is_not_a_number_is_refused_rather_than_matching_nothing(
    tmp_path, mixed_path
):
    """'high' against an integer column is a question with no answer.

    Falling back to a string comparison would return an empty dataset, which is
    indistinguishable from "no pipe is that wide" — the caller would read a
    finding where there was a mistake.
    """
    with pytest.raises(ValueError, match="reads as an answer"):
        vector.select_features(
            mixed_path,
            str(tmp_path / "x.parquet"),
            by="field_equals",
            field="diameter_mm",
            value="high",
        )


def test_a_text_column_of_numeric_looking_values_is_not_converted(tmp_path):
    """Conversion applies to numeric columns only, and this is the case that
    proves it.

    The earlier version of this test filtered a text column on `'valve'` — a
    value no conversion would ever have been attempted on — so it would have
    passed with the guard removed. The postcode its own docstring described is
    the real case: `'00100'` must stay a string, because becoming 100 would make
    the conversion cause the silent mismatch it exists to prevent.
    """
    layer = gpd.GeoDataFrame(
        {"postcode": ["00100", "00185", "20121"]},
        geometry=[shapely.Point(i, 0) for i in range(3)],
        crs="EPSG:32632",
    )
    path = tmp_path / "addresses.parquet"
    layer.to_parquet(path)

    out = tmp_path / "centre.parquet"
    result = vector.select_features(
        str(path), str(out), by="field_equals", field="postcode", value="00100"
    )
    assert result["features_kept"] == 1
    assert _read(out)["postcode"].iloc[0] == "00100"


def test_the_conversion_is_declared_in_the_manifest(tmp_path, mixed_path):
    """A coercion changes what was compared, so it is said.

    `_as_column_type` promised this in its docstring before it was true: the
    conversion appeared only sideways, inside the Python repr of the criterion
    sentence. Either the promise goes or the note does.
    """
    import json
    import pathlib

    out = tmp_path / "one.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_equals", field="diameter_mm", value="200"
    )
    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert any("converted to the column's type" in n for n in manifest["notes"])
    assert any("'200' read as 200" in n for n in manifest["notes"])
    # And the parameter records the value USED, not the one typed: the spec asks
    # for the parameters the engine ran with.
    assert manifest["parameters"]["value"] == 200


def test_no_conversion_means_no_note_about_one(tmp_path, mixed_path):
    """The quiet case stays quiet. A manifest that mentions a conversion on
    every run teaches its reader to skip the line."""
    import json
    import pathlib

    out = tmp_path / "kind.parquet"
    result = vector.select_features(
        mixed_path, str(out), by="field_equals", field="kind", value="pipe"
    )
    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert not any("converted" in n for n in manifest["notes"])


def test_selecting_everything_does_not_claim_a_subset(tmp_path, mixed_path):
    """Nothing removed is not a subset, and saying so is noise."""
    import json
    import pathlib

    # Every `kind` value, so nothing is dropped. A numeric range would not do:
    # the plot has no diameter, and a null is never in a range.
    out = tmp_path / "all.parquet"
    result = vector.select_features(
        mixed_path,
        str(out),
        by="field_in",
        field="kind",
        values=["pipe", "plot", "valve"],
    )
    assert result["features_kept"] == 5
    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert not any("SUBSET" in n for n in manifest["notes"])


def test_a_filter_cannot_grow_the_layer_and_the_file_is_what_says_so(tmp_path, mixed_path):
    """`feature_count_bounded`, computed by reading the output.

    The first version of this asked the same question under an x-mapsmith name
    from two numbers already in memory — `kept <= before` where `kept` came from
    a boolean mask on the frame `before` was measured on. A tautology, recorded
    in an audit trail as though something had been checked.
    """
    import json
    import pathlib

    out = tmp_path / "lines.parquet"
    result = vector.select_features(mixed_path, str(out), by="geometry_type", value="line")
    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))

    names = [c["name"] for c in manifest["verification"]]
    assert "feature_count_bounded" in names
    # Named individually rather than banning the prefix: `no_geometry_is_empty`
    # is an extension on purpose, for a property the core does NOT name. The
    # rule is one core name per core property, not "no extensions".
    retired = {"x-mapsmith:a_filter_only_removes", "x-mapsmith:the_selection_matched_something"}
    assert not retired & set(names), (
        "these are properties the spec names in its core set, so they must carry "
        "the core names: an extension name for a core property is how two "
        "conforming records stop being comparable"
    )


# --- The refusals. On an operation whose whole claim is "no silently wrong
# --- answers", these matter more than the happy paths: each one is a case that
# --- used to produce an empty dataset with a complete manifest, which reads as
# --- a finding rather than a mistake.


@pytest.fixture
def big_ids(tmp_path):
    """Identifiers past 2^53, where float stops being able to count."""
    layer = gpd.GeoDataFrame(
        {"osm_id": [9007199254740992, 9007199254740993, 9007199254740994]},
        geometry=[shapely.Point(i, 0) for i in range(3)],
        crs="EPSG:32632",
    )
    path = tmp_path / "osm.parquet"
    layer.to_parquet(path)
    return str(path)


def test_a_big_integer_filter_keeps_the_row_that_was_asked_for(tmp_path, big_ids):
    """The worst defect this operation had, and it was not an empty result.

    `float("9007199254740993")` is 9007199254740992.0 — the conversion went
    through float, so the filter came back with **the row next to** the one
    asked for: one feature kept, every check green, and a manifest naming a
    number the caller never typed. OSM ids, BIGINT keys and cadastral
    references all live past 2^53.
    """
    import json
    import pathlib

    out = tmp_path / "one.parquet"
    result = vector.select_features(
        big_ids, str(out), by="field_equals", field="osm_id", value="9007199254740993"
    )
    assert result["features_kept"] == 1
    assert _read(out)["osm_id"].iloc[0] == 9007199254740993

    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert manifest["parameters"]["value"] == 9007199254740993


def test_nan_is_refused_because_it_would_match_nothing_forever(tmp_path, mixed_path):
    """`float("nan")` raises nothing, and nan equals nothing — including itself.

    So `field == nan` is an empty output with a full manifest. Somebody typing
    "nan" means "the rows with no value", which is a different question this
    operation does not answer, and answering it with an empty dataset is worse
    than saying so.
    """
    with pytest.raises(ValueError, match="IS NULL"):
        vector.select_features(
            mixed_path,
            str(tmp_path / "x.parquet"),
            by="field_equals",
            field="diameter_mm",
            value="nan",
        )


def test_infinity_is_refused_with_the_thing_that_was_probably_meant(tmp_path, mixed_path):
    with pytest.raises(ValueError, match="no upper bound"):
        vector.select_features(
            mixed_path,
            str(tmp_path / "x.parquet"),
            by="field_between",
            field="diameter_mm",
            maximum="inf",
        )


def test_field_equals_without_a_value_is_refused(tmp_path, mixed_path):
    """A comparison against null is false for every row.

    The other three modes each refuse their empty argument; this one did not,
    and the diagnosis the caller got instead — `result_not_empty`, hinting at a
    misspelled value — sent them looking for a typo that was not there.
    """
    with pytest.raises(ValueError, match="by='field_equals' needs a value"):
        vector.select_features(
            mixed_path, str(tmp_path / "x.parquet"), by="field_equals", field="kind"
        )


def test_a_range_with_its_bounds_the_wrong_way_round_is_refused(tmp_path, mixed_path):
    """Empty by construction, and the criterion in the manifest would have read
    like a legitimate range."""
    with pytest.raises(ValueError, match="above"):
        vector.select_features(
            mixed_path,
            str(tmp_path / "x.parquet"),
            by="field_between",
            field="diameter_mm",
            minimum=300,
            maximum=100,
        )


def test_a_range_on_a_text_column_gets_a_mapsmith_message_and_not_a_pandas_one(
    tmp_path, mixed_path
):
    """pandas raises `Invalid comparison between dtype=str and int` from inside
    the mask, before anything can write a manifest. The caller gets a library
    error where MapSmith should have said which modes work on this column."""
    with pytest.raises(ValueError, match="can be ordered"):
        vector.select_features(
            mixed_path,
            str(tmp_path / "x.parquet"),
            by="field_between",
            field="kind",
            minimum=1,
            maximum=2,
        )


def test_a_geometry_collection_is_named_rather_than_dropped_in_silence(tmp_path):
    """The undercount this operation's own docstring argues against, applied to
    the case that is easier to miss.

    A GeometryCollection holding a polygon is a polygon to everybody except
    `geom_type`, which answers "GeometryCollection" — so it falls outside every
    family and a family selection drops it. Keeping the Multi variants and
    dropping this one silently would be exactly the half-applied care the
    docstring criticises in other systems.
    """
    layer = gpd.GeoDataFrame(
        {"n": [1, 2, 3]},
        geometry=[
            shapely.box(0, 0, 1, 1),
            shapely.GeometryCollection([shapely.box(2, 0, 3, 1)]),
            None,
        ],
        crs="EPSG:32632",
    )
    path = tmp_path / "mixed_bag.parquet"
    layer.to_parquet(path)

    result = vector.select_features(
        str(path), str(tmp_path / "polys.parquet"), by="geometry_type", value="polygon"
    )
    assert result["features_kept"] == 1

    considered = next(
        w for w in result["warnings"]
        if w["check"] == "x-mapsmith:every_feature_was_considered"
    )
    assert "GeometryCollection" in considered["detail"]
    assert "null geometry" in considered["detail"]
    assert "explode" in considered["hint"]


def test_an_attribute_filter_is_not_accused_of_dropping_geometry_types(
    tmp_path, mixed_path
):
    """The check belongs to family selection only. An attribute filter keeps
    whatever geometry the matching rows carry, so raising the question there
    would be a warning nobody can act on."""
    result = vector.select_features(
        mixed_path,
        str(tmp_path / "one.parquet"),
        by="field_equals",
        field="kind",
        value="plot",
    )
    considered = next(
        c for c in _checks(result) if c == "x-mapsmith:every_feature_was_considered"
    )
    assert considered  # present and passing, not a warning
    assert not [
        w for w in result.get("warnings", [])
        if w["check"] == "x-mapsmith:every_feature_was_considered"
    ]


def _checks(result):
    import json
    import pathlib

    manifest = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    return [c["name"] for c in manifest["verification"]]


def test_an_input_without_a_crs_is_refused_and_the_manifest_survives(tmp_path):
    """Invariants 3 and 4 together, on both writers.

    Invariant 4: an input with no CRS is refused. Invariant 3: the manifest is
    written BEFORE the error is raised, so the audit trail outlives the failure
    — a diagnosis nobody can read is the same as no diagnosis.
    """
    import json
    import pathlib

    from mapsmith.verify import VerificationError

    homeless = gpd.GeoDataFrame(
        {"kind": ["a"]}, geometry=[shapely.box(0, 0, 1, 1)], crs=None
    )
    path = tmp_path / "no_crs.parquet"
    homeless.to_parquet(path)

    out = tmp_path / "selected.parquet"
    with pytest.raises(VerificationError):
        vector.select_features(str(path), str(out), by="geometry_type", value="polygon")

    manifest = pathlib.Path(f"{out}.provenance.json")
    assert manifest.exists(), (
        "the manifest has to be on disk before the error is raised: an operation "
        "that refuses without leaving its reasoning behind teaches nobody anything"
    )
    record = json.loads(manifest.read_text(encoding="utf-8"))
    failed = [c for c in record["verification"] if not c["passed"]]
    assert any(c["name"] == "input_crs_present" for c in failed)
