"""Closed-form tests for the spheroid axis-order advisory in run_sql (D-039).

The reference square spans 0.0008 degrees of longitude by 0.0006 of latitude at
41.9 north. Its ground area is 4424.01 m² — agreed by pyproj's geodesic, a UTM
33N planar measurement (4425.54) and the local metric by hand (4419.85), three
methods that share no code. DuckDB's ST_Area_Spheroid, handed the same polygon
in the order every file format stores it, answers 5774.08: 31% out, no error,
no warning, and a perfectly ordinary parcel either way.

The advisory probes the installed build rather than trusting a version number,
because DuckDB has announced that this default changes: warning in 1.5, error
in 2.0, flipped in 2.1. When a build reads coordinates the way files store
them, these tests will show the advisory disappearing — which is correct
behaviour, not a regression, and the last test says so.
"""

from __future__ import annotations

import pytest

from mapsmith.engines import duckdb_engine

REFERENCE = (
    "POLYGON((12.4 41.9, 12.4008 41.9, 12.4008 41.9006, 12.4 41.9006, 12.4 41.9))"
)
TRUTH_M2 = 4424.01


def _build_reads_latitude_first() -> bool:
    """What this DuckDB build actually does, asked rather than assumed."""
    con = duckdb_engine._connect()
    as_stored = con.sql(
        f"SELECT ST_Area_Spheroid(ST_GeomFromText('{REFERENCE}'))"
    ).fetchone()[0]
    return abs(as_stored - TRUTH_M2) > abs(as_stored - 5774.08)


def test_the_reference_square_is_what_three_other_methods_say_it_is():
    """The probe's truth is not this file's opinion: it is checked against an
    independent geodesic implementation before anything else is asserted."""
    geod = pytest.importorskip("pyproj").Geod(ellps="WGS84")
    lons = [12.4, 12.4008, 12.4008, 12.4]
    lats = [41.9, 41.9, 41.9006, 41.9006]
    assert abs(geod.polygon_area_perimeter(lons, lats)[0]) == pytest.approx(
        TRUTH_M2, abs=0.01
    )


def test_a_spheroid_query_comes_back_with_the_measurement_that_contradicts_it():
    if not _build_reads_latitude_first():
        pytest.skip("this DuckDB build already reads longitude first")
    result = duckdb_engine.run_sql(
        f"SELECT ST_Area_Spheroid(ST_GeomFromText('{REFERENCE}')) AS area"
    )
    # The query still runs and still returns its number: this is an advisory,
    # not a refusal — run_sql is the door for arbitrary SQL.
    assert result["rows"][0][0] == pytest.approx(5774.08, abs=0.01)
    warnings = result["warnings"]
    assert [w["check"] for w in warnings] == ["x-mapsmith:spheroid_axis_order"]
    detail = warnings[0]["detail"]
    assert "4424.01" in detail and "5774.08" in detail and "31%" in detail
    assert "ST_FlipCoordinates" in warnings[0]["hint"]


def test_an_ordinary_query_says_nothing():
    """A check that fires on queries it has no business in trains the caller to
    ignore it."""
    assert "warnings" not in duckdb_engine.run_sql("SELECT 1 AS x")
    assert "warnings" not in duckdb_engine.run_sql(
        f"SELECT ST_Area(ST_GeomFromText('{REFERENCE}')) AS planar"
    )


def test_the_advisory_survives_into_the_manifest(tmp_path):
    if not _build_reads_latitude_first():
        pytest.skip("this DuckDB build already reads longitude first")
    import json
    from pathlib import Path

    out = tmp_path / "areas.parquet"
    result = duckdb_engine.run_sql(
        f"SELECT ST_Area_Spheroid(ST_GeomFromText('{REFERENCE}')) AS area",
        str(out),
    )
    # Two advisories here: a tabular result carries no georeference, which is
    # legitimate and already flagged. The axis one must be among them.
    assert "x-mapsmith:spheroid_axis_order" in [w["check"] for w in result["warnings"]]
    manifest = json.loads(Path(result["provenance"]).read_text(encoding="utf-8"))
    failed = [c["name"] for c in manifest["verification"] if not c["passed"]]
    assert "x-mapsmith:spheroid_axis_order" in failed
    # Non-critical: the operation completed and the file exists.
    entry = next(c for c in manifest["verification"] if c["name"] == "x-mapsmith:spheroid_axis_order")
    assert entry["critical"] is False
    assert out.exists()


def test_the_check_is_a_probe_not_a_version_string():
    """The day DuckDB flips its default, this advisory must stop firing on its
    own. Guarding that means asserting the mechanism, not the outcome: the
    verdict comes from running the reference square through the build."""
    import inspect

    source = inspect.getsource(duckdb_engine._axis_order_check)
    assert "ST_Area_Spheroid" in source and "ST_FlipCoordinates" in source
    # Version numbers may appear in the prose explaining why; they must not be
    # what the verdict is computed from.
    code = "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )
    assert "__version__" not in code
    assert "duckdb.__version__" not in source
