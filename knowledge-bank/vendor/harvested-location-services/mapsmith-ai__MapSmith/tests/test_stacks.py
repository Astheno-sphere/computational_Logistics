"""Choosing a geoprocessing stack, and what happens when it cannot be used.

Most of these run on a machine with no ArcGIS Pro, which is deliberate: CI is
such a machine, and the path that matters most is the one where the preferred
stack is *absent*. A test suite that only exercised the happy path would leave
the fallback — the common case, since 924 of 2198 tools do not run on a Standard
licence — untested everywhere it runs.

The tests that need the real thing say so and skip.
"""

from __future__ import annotations

import json
import pathlib

import geopandas as gpd
import pytest
import shapely

from mapsmith import stacks
from mapsmith.engines import esri, vector

CRS = "EPSG:32632"
HAS_ESRI = stacks.installed()["esri"]["available"]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    """No inherited MAPSMITH_STACK: the default is part of what is tested."""
    monkeypatch.delenv("MAPSMITH_STACK", raising=False)


@pytest.fixture
def squares(tmp_path):
    """Two 100 m squares, 200 m apart. Area, perimeter and count by hand."""
    path = tmp_path / "squares.gpkg"
    gpd.GeoDataFrame(
        {"a_field_name_that_is_long": [1, 2]},
        geometry=[shapely.box(0, 0, 100, 100), shapely.box(300, 0, 400, 100)],
        crs=CRS,
    ).to_file(path, driver="GPKG")
    return str(path)


def test_the_default_needs_no_licence_and_no_environment():
    assert stacks.requested() == "opensource"
    assert stacks.DEFAULT_STACK == "opensource"


def test_a_misspelled_stack_is_refused_rather_than_ignored(monkeypatch):
    """`MAPSMITH_STACK=esry` must not quietly mean open source.

    Falling back to the default would give the caller results from an engine
    they did not ask for while believing they had asked for another — the quiet
    kind of wrong this project exists to refuse.
    """
    monkeypatch.setenv("MAPSMITH_STACK", "esry")
    with pytest.raises(ValueError, match="esry"):
        stacks.requested()


def test_open_source_is_always_available():
    """MapSmith's own engines ship with it, so this can never be false.

    It matters because the fallback target has to exist unconditionally: a
    fallback that could itself be unavailable is not a fallback.
    """
    assert stacks.installed()["opensource"]["available"] is True


def test_asking_for_esri_without_esri_says_so_at_the_start(monkeypatch):
    """The whole point of announcing the stack when a session opens.

    A caller who plans five steps around a stack this machine does not have
    should learn that before the first step, not at the first failure.
    """
    monkeypatch.setenv("MAPSMITH_STACK", "esri")
    monkeypatch.setattr(
        stacks, "installed",
        lambda: {"opensource": {"available": True, "qgis": True},
                 "esri": {"available": False}},
    )
    reported = stacks.describe()
    assert reported["requested"] == "esri"
    assert "warning" in reported
    assert "does not ship it" in reported["warning"]


def test_the_three_reasons_never_collapse_into_one():
    """D-056 point 4: they lead a reader to three different decisions.

    "No such tool" is permanent, "not in this licence" is a purchase, and
    "needs an online service" may be a choice the caller made on purpose. One
    word for all three would throw away the only part that is actionable.
    """
    reasons = {stacks.NO_SUCH_TOOL, stacks.NOT_IN_THIS_LICENCE,
               stacks.NEEDS_ONLINE_SERVICE}
    assert len(reasons) == 3
    sentences = {stacks.fallback_note("op", r) for r in reasons}
    assert len(sentences) == 3, "two reasons produce the same sentence"
    assert "not about the product" in stacks.fallback_note(
        "op", stacks.NOT_IN_THIS_LICENCE
    ), "a licence tier that lacks a tool is not a product that cannot do the thing"


def test_a_fallback_is_never_silent(monkeypatch, squares, tmp_path):
    """Requested Esri, got open source, and the record says which and why.

    This is the test that matters on every machine without ArcGIS Pro — which
    includes CI — and it is the invariant the whole feature rests on: a product
    that sells provenance and swaps engines quietly is selling the opposite.
    """
    monkeypatch.setenv("MAPSMITH_STACK", "esri")
    monkeypatch.setattr(
        esri, "available_for",
        lambda operation: (False, stacks.NO_SUCH_TOOL, "not installed here"),
    )
    out = tmp_path / "buffered.parquet"
    result = vector.buffer(squares, 10, str(out))

    record = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert record["engine"]["name"] == "geopandas"
    note = [n for n in record["notes"] if "esri" in n]
    assert note, "the record does not say that a different stack was requested"
    assert "not by the one that was asked for" in note[0]


def test_open_source_mode_records_no_fallback(monkeypatch, squares, tmp_path):
    """The quiet case stays quiet.

    A record that carried a stack sentence on every operation would teach its
    reader to skip the line, which is the same as not writing it.
    """
    monkeypatch.setenv("MAPSMITH_STACK", "opensource")
    out = tmp_path / "buffered.parquet"
    result = vector.buffer(squares, 10, str(out))
    record = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))
    assert not [n for n in record["notes"] if "stack" in n.lower()]


def test_the_bridge_format_is_never_a_shapefile():
    """A back door cannot use the format the front door refuses.

    ArcPy reads neither GeoParquet nor a plain GeoPackage path, so the Esri
    backend needs a bridge. The obvious one is a shapefile, and it silently
    truncates field names to ten characters — which is exactly why
    `convert_format` refuses to write one. Measured on 2026-08-30: a
    28-character field survives a GeoPackage bridge intact.
    """
    assert ".shp" not in esri.PROBE, (
        "the Esri probe writes a shapefile somewhere; field names over ten "
        "characters would be truncated without a word"
    )
    assert "GEOPACKAGE" in esri.PROBE


def test_the_esri_binding_is_keyed_by_the_catalogue_name():
    """`buffer` and `buffer_layer` are not the same key.

    They were, once, and the effect was invisible: every call fell back with
    the reason "no such tool" while the tool was right there. A wrong key here
    does not fail loudly — it produces a plausible refusal.
    """
    from mapsmith import catalog

    names = {o["name"] for o in catalog.OPERATIONS}
    unknown = set(esri.TOOLS) - names
    assert not unknown, (
        f"these Esri bindings name no catalogue operation: {sorted(unknown)}"
    )


def test_the_qualified_tool_name_is_what_is_looked_up():
    """297 of 2198 installed tools share a bare name with another toolbox.

    Keying an inventory by the bare name collapses them without a word, and the
    scripting module addresses them qualified anyway.
    """
    for binding in esri.TOOLS.values():
        assert binding["toolbox"] and binding["tool"]


@pytest.mark.skipif(not HAS_ESRI, reason="ArcGIS Pro is not installed on this machine")
@pytest.mark.slow
def test_the_esri_stack_produces_the_same_geometry_and_a_different_schema(
    monkeypatch, squares, tmp_path
):
    """The real thing, end to end, and the finding is the difference.

    The two engines agree on the geometry — a 100 m square buffered by 10 m is
    14314 m², and both land within a few m² of it, the gap being how each
    approximates the arcs. They do NOT agree on the schema: ArcGIS adds
    `BUFF_DIST` and `ORIG_FID`. That difference has to be in the record,
    because anything downstream that reads a column needs to know which engine
    wrote it.
    """
    monkeypatch.setenv("MAPSMITH_STACK", "esri")
    out = tmp_path / "esri.parquet"
    result = vector.buffer(squares, 10, str(out))
    record = json.loads(pathlib.Path(result["provenance"]).read_text(encoding="utf-8"))

    assert record["engine"]["name"] == "ArcGIS Pro"
    written_layer = gpd.read_parquet(out)
    # Two squares of 100 m buffered by 10: 10000 + 4x1000 + pi x 100 each.
    assert written_layer.area.sum() == pytest.approx(28628.3, rel=0.001)
    assert "a_field_name_that_is_long" in written_layer.columns, (
        "the bridge truncated or dropped a field name"
    )

    # Found by what the note is FOR, not by the vendor's name. Naming the engine
    # is `engine.name`'s job, asserted above; the note's job is the schema delta,
    # and an assertion that looked for the name here would pass while the delta
    # was missing.
    note = [n for n in record["notes"] if "requested stack 'esri'" in n]
    assert note, "the record does not say a different stack was asked for"
    assert "BUFF_DIST" in note[0], (
        "the schema difference is not in the record: a downstream step reading "
        "columns would not know the engine changed them"
    )


def test_every_declared_esri_tool_is_actually_routed():
    """A table entry is a promise that requesting the stack reaches it.

    `TOOLS` declared three operations and `available_for` reported all three
    usable, while `stacks.route` was called from exactly one place. So with the
    Esri stack requested, `centroid_layer` and `dissolve_layer` ran on the open
    source stack and no manifest note recorded the substitution — the one thing
    `stacks.py` says never happens quietly, and on `dissolve` the vendor drops
    every attribute, so a pipeline that dissolves and then reads a column gets
    the column on one stack and nothing on the other.

    This reads the source rather than calling anything, which is a weaker kind
    of test — but the alternative needs ArcGIS Pro installed, and the failure it
    guards against is exactly a missing line of source.
    """
    from pathlib import Path

    from mapsmith.engines import esri

    source_root = Path(esri.__file__).resolve().parent
    routed = set()
    for module in sorted(source_root.glob("*.py")):
        text = module.read_text(encoding="utf-8")
        for name in esri.TOOLS:
            if f'stacks.route("{name}")' in text:
                routed.add(name)

    assert set(esri.TOOLS) == routed, (
        f"declared in TOOLS and never routed: {sorted(set(esri.TOOLS) - routed)}. "
        f"Requesting the Esri stack runs these on the open source one with no "
        f"note in the manifest. Either call stacks.route in the operation, or "
        f"move it to MEASURED_NOT_ROUTED."
    )


def test_the_two_stacks_are_told_the_same_distance_the_same_way():
    """`distance_meters` meant two different things on the two stacks.

    The open source branch buffers by that number in the CRS's own unit when the
    CRS is projected; ArcPy was handed `"<n> Meters"`, and Buffer's PLANAR
    method converts a linear unit into the CRS's unit. On EPSG:2263 (US survey
    feet) the same call produced 100 feet on one stack and 328.08 on the other,
    with the same sentence in the manifest and every check green.

    The unit is now decided by the code that knows the CRS: the layer's own unit
    when it is projected, metres when it is geographic — where the open source
    branch reprojects to UTM and buffers metres, and where "Unknown" would mean
    a hundred DEGREES.
    """
    from pathlib import Path

    from mapsmith.engines import esri, vector

    vector_source = Path(vector.__file__).read_text(encoding="utf-8")
    assert '"distance_unit": "Meters" if on_a_geographic_crs else "Unknown"' in (
        vector_source
    ), "the unit is no longer chosen from the CRS before the Esri call"

    probe = esri.PROBE
    assert 'request.get("distance_unit"' in probe, (
        "the probe no longer reads the unit from the request, so it is back to "
        "assuming one"
    )
    assert '"%s Meters"' not in probe, (
        "the probe hard-codes Meters again, which is wrong on every projected "
        "CRS whose unit is not the metre"
    )
