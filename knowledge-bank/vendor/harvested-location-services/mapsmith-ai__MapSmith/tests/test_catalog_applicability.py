"""Every catalog entry declares what it applies to.

The applicability block exists so that a future deterministic filter can
narrow the catalog to the operations that are *meaningful* for the data in
hand (vector vs raster, projected CRS required) before any ranking runs — and
so that the choice is recordable in a manifest. Declared per entry at
writing time, because retrofitting sixty entries later is how schemas rot.
"""

from __future__ import annotations

import pytest

from mapsmith import catalog

# "none" is not an empty list: it says the operation takes no dataset at all
# (describe_crs answers about a CRS, geodetic_distance about two coordinates).
# The distinction matters to the filter — an operation that needs no data is
# applicable whatever data you hold, while an empty list would read as "applies
# to nothing" and quietly drop it from every result.
ALLOWED_INPUTS = {"vector", "raster", "dataset", "plan", "none"}


@pytest.mark.parametrize("op", catalog.OPERATIONS, ids=lambda op: op["name"])
def test_every_entry_declares_its_applicability(op):
    block = op.get("applicability")
    assert block, f"{op['name']} has no applicability block"
    # `geometry` is optional, and its absence is a statement: any geometry.
    assert set(block) - {"geometry"} == {"inputs", "requires_projected_crs", "dataset_inputs"}
    if "geometry" in block:
        families = block["geometry"]
        assert families and len(set(families)) == len(families), "a non-empty set"
        assert set(families) <= set(catalog.GEOMETRY_FAMILIES)
        assert {"vector", "dataset"} & set(block["inputs"]), (
            "a geometry declaration on an entry that takes no vector input filters nothing"
        )
    assert block["inputs"], "inputs must not be empty"
    assert set(block["inputs"]) <= ALLOWED_INPUTS
    assert isinstance(block["requires_projected_crs"], bool)
    # How many datasets the caller is holding. An exact set rather than a subset
    # on purpose: a facet the filter does not read narrows nothing and lies in
    # the schema, and a facet the schema does not know about is one the entries
    # can start disagreeing about.
    arity = block["dataset_inputs"]
    # `None` means variable or not expressible as a count — a list of inputs, or
    # inputs named inside a query string — and such an entry survives every
    # declared arity instead of being dropped from all of them.
    assert arity is None or (isinstance(arity, int) and arity >= 0)


def test_the_projected_crs_requirement_matches_the_engines_that_refuse():
    """The operations that refuse a geographic CRS at the engine level, and only
    those, must declare it — or the filter offers an operation that will raise.

    The list is written out rather than derived from the source, because deriving
    it from the source is what went wrong once: grepping for "geographic" near a
    `raise` reported five more operations than actually refuse, since the word
    also appears in notes and warnings. The executable version of this check
    lives in test_whitebox_geographic_refusal.py, which runs each one on a
    geographic DEM and compares the outcome with this declaration.
    """
    demanding = {
        op["name"] for op in catalog.OPERATIONS
        if op["applicability"]["requires_projected_crs"]
    }
    assert demanding == {
        "slope",
        "aspect",
        "curvature",
        "flow_direction",
        "euclidean_distance",
        # Added 2026-08-29 with the ten operations that came out of the discovery
        # benchmark. Each refuses a geographic CRS for the same reason: a length
        # the caller names — a sample spacing, a sight-line run, a station height
        # against a cell size, a minimum spacing between labels — is not a length
        # in degrees, and the answer would be plausible and wrong rather than
        # absent. `test_whitebox_geographic_refusal` executes the whitebox one;
        # the others have their own refusal tests.
        "elevation_profile",
        "line_of_sight",
        "viewshed",
        # Added 2026-08-30 with the second ten. Same rule, same reason: each of
        # these takes a length from the caller — a snapping tolerance, a spacing
        # along a line, a contour interval against a cell size, the area a
        # nearest-neighbour ratio is measured against, the ground distance that
        # weights a cost — and a length in degrees is not a length.
        "snap_layer",
        "points_along_lines",
        "contour_lines",
        "least_cost_path",
        "nearest_neighbour_index",
        "thin_points",
        # A link length, like thinning's spacing: in degrees it is not a length.
        "cluster_points_by_distance",
        # Added 2026-08-29, and the reason belongs here rather than in a commit:
        # it declared False and did not refuse, so the executable check in
        # test_whitebox_geographic_refusal saw the two statements agree and
        # passed — while the operation weighted every sample by a distance in
        # degrees. Consistency between a declaration and a behaviour says
        # nothing about whether either is right, which is why this list is
        # written by hand and reviewed rather than derived.
        "idw_interpolation",
    }


def test_the_filter_narrows_before_ranking_deterministically():
    """Closed-form: a geographic raster must never be offered slope or aspect,
    and must still be offered hillshade and zonal_statistics."""
    names = {op["name"] for op in catalog.applicable("raster", projected=False)}
    assert "slope" not in names and "aspect" not in names
    assert {"hillshade", "zonal_statistics", "describe_dataset"} <= names
    assert "buffer_layer" not in names  # vector-only does not apply to a raster

    projected_raster = {op["name"] for op in catalog.applicable("raster", projected=True)}
    assert {"slope", "aspect"} <= projected_raster

    vector_names = {op["name"] for op in catalog.applicable("vector")}
    assert {"buffer_layer", "overlay_layers", "dissolve_layer", "run_sql"} <= vector_names
    assert "hillshade" not in vector_names

    # An operation that needs no dataset is applicable to every kind, including a
    # geographic raster: describe_crs is precisely what you call to find out that
    # the raster is geographic.
    dataless = {"describe_crs", "geodetic_distance"}
    assert dataless <= names
    assert dataless <= projected_raster
    assert dataless <= vector_names

    with pytest.raises(ValueError, match="input_kind must be"):
        catalog.applicable("tabular")


def test_search_applies_the_filter_before_bm25():
    # Read through `entries`: with the facets declared, few enough operations
    # survive that the search hands over the set instead of ranking it, and a
    # test that indexed `hits[0]` would be asserting on the response envelope.
    hits = catalog.entries(catalog.search("slope in degrees", input_kind="raster",
                                          projected=False))
    assert hits and all(entry["name"] != "slope" for entry in hits)
    projected = catalog.entries(
        catalog.search("slope in degrees", input_kind="raster", projected=True)
    )
    assert projected and projected[0]["name"] == "slope"


def test_search_names_its_engine_and_refuses_an_unknown_one():
    """Every result says which engine ranked it: a score of 10.03 and one of
    0.38 are not comparable, and a caller reading both needs to know which
    scale it is on."""
    hits = catalog.search("area of a parcel", limit=3, engine="lexical")
    assert hits and all(entry["engine"] == "lexical" for entry in hits)
    # The default is `auto`, which prefers the embedding engine; the field must
    # say so rather than the caller having to know what the default is.
    #
    # A query the catalog can place, deliberately: "area of a parcel" ranks
    # `validate_geometry` first on BM25 — it did before `distinguishes` existed
    # too — so on the default engine the two rankers disagree and the search
    # returns `unsure` instead. That is the clarification path working, not a
    # regression, and it has no `engine` field to check.
    default = catalog.search("steepness of the terrain", limit=3)
    assert default and default[0].get("engine") in ("vector", "lexical")
    with pytest.raises(ValueError, match="engine must be one of"):
        catalog.search("area", engine="nonsense")


def test_auto_engine_always_answers_whatever_is_installed():
    """auto is the deployment switch: it must never fail for want of an extra.
    With the extra it ranks by vectors, without it by BM25 — either way the
    caller gets results and is told which."""
    hits = catalog.search("how big is this field really", limit=3, engine="auto")
    assert hits
    engines = {entry["engine"] for entry in hits}
    assert engines in ({"vector"}, {"lexical"}), engines


def test_the_vector_engine_also_narrows_before_it_ranks(vector_engine):
    """The applicability filter is not a property of BM25: it runs first for
    both engines, or the guarantee is only true of the default one."""
    answer = catalog.search(
        "slope in degrees", input_kind="raster", projected=False, engine="vector"
    )
    hits = catalog.entries(answer)
    assert hits and all(entry["name"] not in ("slope", "aspect") for entry in hits)
    # The engine is named once on the envelope when the answer is a choice, and
    # on every row when it is a ranking. Either way the caller can read it.
    assert answer[0].get("engine") == "vector" or all(
        entry["engine"] == "vector" for entry in hits
    )
    projected = catalog.entries(catalog.search(
        "steepness of the terrain", input_kind="raster", projected=True, engine="vector"
    ))
    assert {"slope", "aspect"} & {entry["name"] for entry in projected}


def test_every_operation_declares_a_workload_the_dispatcher_knows():
    """D-041: declaring is not routing, but a declaration the router cannot read
    is decoration. Every entry carries a workload, and every workload is a value
    of the enum the dispatcher switches on — so the day routing is extended, the
    catalog is already the input it needs."""
    from mapsmith.engines.dispatch import Workload

    valid = {w.value for w in Workload}
    for op in catalog.OPERATIONS:
        assert "workload" in op, f"{op['name']} declares no workload"
        assert op["workload"] in valid, (
            f"{op['name']} declares workload {op['workload']!r}, "
            f"which the dispatcher does not know: {sorted(valid)}"
        )


def test_a_raster_operation_is_never_filed_as_a_vector_workload():
    """Closed-form: the raster category and the raster workload must agree.
    A GeoTIFF operation filed as heavy_join is how a router eventually sends a
    grid to a spatial-join engine."""
    for op in catalog.OPERATIONS:
        if op["category"] == "raster" or op["applicability"]["inputs"] == ["raster"]:
            assert op["workload"] == "raster", (
                f"{op['name']} is a raster operation declared as {op['workload']!r}"
            )
