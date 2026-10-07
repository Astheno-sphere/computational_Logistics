"""DuckDB spatial engine: SQL, filters, aggregations, point-in-polygon joins.

Benchmarks (2025-26): DuckDB's SPATIAL_JOIN operator does point-in-polygon at
~2M rows/sec on a laptop. The spatial extension is NOT bundled in the wheel:
we install it on first use (needs network once per environment).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from .. import sql_policy, verify, workspace
from ..provenance import InputRecord, ProvenanceRecord

_PREVIEW_ROWS = 50


def _engine_info() -> dict[str, str]:
    return {"name": "duckdb", "version": duckdb.__version__}


def _sql_dir(path: Path) -> str:
    """Directory path as a DuckDB SQL string literal: forward slashes (GDAL and
    DuckDB normalize to them) and a trailing separator, because
    allowed_directories matches by PREFIX — without it 'C:/ws' would also
    admit 'C:/ws-evil'."""
    return (str(path).replace("\\", "/").rstrip("/") + "/").replace("'", "''")


def _connect() -> duckdb.DuckDBPyConnection:
    """A DuckDB connection with the spatial extension; sandboxed when
    MAPSMITH_WORKSPACE is set.

    SQL text can name any file, out of reach of the textual path jail at the
    tool boundary — so the confinement happens in the engine itself. Order is
    load-bearing (each step would be refused after the next one):
    extensions first, then the filesystem whitelist, then external access off
    (which is what ACTIVATES the whitelist: allowed_directories are the
    exceptions to it), configuration lock last. ST_Read is covered too: the
    spatial extension routes GDAL I/O through DuckDB's filesystem, and its
    /vsi* and DRIVER:https:// escapes are refused once external access is off.
    allowed_directories cannot go in the connect() config dict (VARCHAR[]
    options crash there — duckdb#17128); SET statements are the supported way.
    """
    # These apply in EVERY mode. Unconfined *file access* without a workspace is
    # a deliberate, documented choice; unconfined *code execution* is not, and
    # DuckDB's defaults allow the escalation: with autoload and community
    # extensions on, one statement can install `shellfs` (which runs a shell
    # command for a filename ending in '|') or autoload httpfs and exfiltrate
    # results in a URL. SQL written by an LLM from whatever reached its context
    # is untrusted SQL, so DuckDB's own hardening guidance applies.
    con = duckdb.connect(
        config={
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
            "allow_community_extensions": "false",  # self-locking by design
            "memory_limit": os.environ.get("MAPSMITH_DUCKDB_MEMORY", "4GB"),
        }
    )
    try:
        con.install_extension("spatial")
    except duckdb.Error:
        pass  # already installed in this environment, or offline with a cached copy
    con.load_extension("spatial")

    ws = workspace.root()
    tmp_limit = os.environ.get("MAPSMITH_DUCKDB_TEMP_LIMIT", "8GB").replace("'", "''")
    if ws is not None:
        con.execute(f"SET allowed_directories = ['{_sql_dir(ws)}']")
        con.execute(f"SET temp_directory = '{_sql_dir(ws)}.duckdb_tmp'")
        con.execute("SET enable_external_access = false")
    else:
        # No workspace means unconfined FILE access (documented). It must not
        # also mean network egress. `sql_policy` now refuses an explicit LOAD as
        # well, so this is the second layer rather than the only one — and it is
        # the layer that still holds for an extension a person allowed by name
        # in MAPSMITH_ALLOW_EXTENSIONS. enable_external_access=false would take
        # local files with it, so disabling the remote filesystems keeps local
        # access intact and
        # closes the exfiltration channel (verified: read_csv of a URL raises
        # PermissionException while a local read still works).
        con.execute("SET disabled_filesystems = 'HTTPFileSystem,S3FileSystem'")
        # ...and unconfined disk is not part of the deal either: without a
        # limit a spill fills the volume.
        con.execute(f"SET temp_directory = '{_sql_dir(Path(tempfile.gettempdir()))}mapsmith'")
    con.execute(f"SET max_temp_directory_size = '{tmp_limit}'")
    # Secrets: persistent ones are written to ~/.duckdb/stored_secrets, i.e.
    # OUTSIDE any workspace and beyond the life of the session. Under a
    # workspace `enable_external_access = false` already refuses that write
    # (verified), but unconfined mode would allow it, and a credential
    # surviving on disk is not something a tool call should be able to decide.
    # allow_unredacted_secrets is already false by default; stating it makes it
    # policy once the configuration is locked below.
    con.execute("SET allow_persistent_secrets = false")
    con.execute("SET allow_unredacted_secrets = false")
    # Locking is what makes the extension settings above a policy rather than a
    # default: without it, one multi-statement call re-enables autoload and
    # then INSTALL/LOAD of a signed extension (httpfs) opens a network egress
    # path. So it applies in EVERY mode, not just under a workspace.
    con.execute("SET lock_configuration = true")
    return con


# `geoparquet_version 'BOTH'` writes Parquet's native GEOMETRY/GEOGRAPHY logical
# types (what GeoParquet 2.0 requires, CRS included as PROJJSON) *and* the 1.x
# `geo` metadata key, so one file satisfies both readers — verified by reading it
# back with GeoPandas, which only understands the 1.x layer.
#
# Stated explicitly rather than left to the engine, because the default moved:
# DuckDB 1.4 wrote the native types by default and 1.5 went back to 1.x, which
# meant the installed engine version, not MapSmith, was choosing the canonical
# output format of a provenance product.
_COPY_OPTIONS = "FORMAT parquet, geoparquet_version 'BOTH'"


def _quote(path: str) -> str:
    return str(path).replace("'", "''")


def _rel(path: str) -> str:
    """SQL relation for a dataset file: GeoParquet natively, other formats via GDAL."""
    if str(path).lower().endswith(".parquet"):
        return f"read_parquet('{_quote(path)}')"
    return f"ST_Read('{_quote(path)}')"


# The spheroid functions take their coordinates in an order the SQL text does
# not state, and every file format stores the other one. Listed by name rather
# than matched loosely: a false positive here would train a caller to ignore
# the check, which is worse than not having it.
_SPHEROID_FUNCTIONS = (
    "st_area_spheroid",
    "st_perimeter_spheroid",
    "st_distance_spheroid",
    "st_length_spheroid",
)
# A square whose sides are 0.0008 degrees of longitude by 0.0006 of latitude at
# 41.9 north. Its ground area is ~4424 m2 by three independent methods (pyproj
# geodesic, a UTM 33N planar measurement, and the local metric by hand), so the
# probe can tell which axis order a build assumes by comparing against a number
# nobody in this file computed.
_PROBE_LONLAT = (
    "POLYGON((12.4 41.9, 12.4008 41.9, 12.4008 41.9006, 12.4 41.9006, 12.4 41.9))"
)
_PROBE_TRUTH_M2 = 4424.01


def _mentions_spheroid_function(query: str) -> list[str]:
    lowered = sql_policy.strip_comments(query).lower()
    return [name for name in _SPHEROID_FUNCTIONS if name in lowered]


def _axis_order_check(con: Any, used: list[str]) -> verify.Check | None:
    """Ask the installed build which axis order its spheroid functions assume.

    Measured at run time, not assumed from a version number: DuckDB has
    announced that `geometry_always_xy` warns in 1.5, errors in 2.0 and flips
    to true in 2.1, so a hardcoded verdict would be wrong twice — once now if
    the build is patched, once later when the default changes. When the build
    reads coordinates the way files store them, this returns None and the
    caller sees nothing, which is the correct amount of noise.
    """
    try:
        as_stored = con.sql(
            f"SELECT ST_Area_Spheroid(ST_GeomFromText('{_PROBE_LONLAT}'))"
        ).fetchone()[0]
        flipped = con.sql(
            "SELECT ST_Area_Spheroid(ST_FlipCoordinates("
            f"ST_GeomFromText('{_PROBE_LONLAT}')))"
        ).fetchone()[0]
    except Exception:  # noqa: BLE001 — the probe must never break the caller's query
        return None
    if as_stored is None or flipped is None:
        return None
    stored_is_right = abs(as_stored - _PROBE_TRUTH_M2) < abs(flipped - _PROBE_TRUTH_M2)
    if stored_is_right:
        return None
    error = abs(as_stored - _PROBE_TRUTH_M2) / _PROBE_TRUTH_M2 * 100
    return verify.Check(
        "x-mapsmith:spheroid_axis_order",
        False,
        f"{', '.join(used)} read coordinates as (latitude, longitude) in this "
        f"build: on a reference square whose ground area is {_PROBE_TRUTH_M2} m2 "
        f"they answer {as_stored:.2f} ({error:.0f}% out), and {flipped:.2f} with "
        "the axes swapped",
        critical=False,
        hint=(
            "Every file format stores longitude first, and these functions read "
            "latitude first, so a geometry read from a file and passed straight "
            "in comes back wrong by a plausible margin — no error, no warning. "
            "Wrap the geometry in ST_FlipCoordinates(), or measure in a projected "
            "CRS with ST_Area(ST_Transform(...)). MapSmith's own measure_area "
            "does the second. This check disappears on its own when the engine "
            "changes its default, because it probes the build rather than "
            "trusting a version number."
        ),
    )


def run_sql(query: str, output_path: str | None = None) -> dict[str, Any]:
    """Run spatial SQL. With output_path, materialize the result as GeoParquet."""
    # SQL text is out of reach of the path guard at the tool boundary, and GDAL
    # brings its own HTTP client: without this the remote opt-in (#21) would be
    # decorative for exactly the statement that can reach the network.
    workspace.refuse_remote_in_sql(query)
    # A credential in agent-written SQL would be recorded verbatim in a manifest
    # meant to be shared; refusing the statement beats redacting its text, which
    # an audit escaped four ways in minutes (#18, see sql_policy).
    sql_policy.refuse_credentials_in_sql(query)
    # An INSTALL fetches a native binary over HTTPS and runs it in this process.
    # It was allowed by default, and an audit used it to make this tool return
    # the host's real cloud credentials — while SECURITY.md said in the same
    # artifact that what stayed unconfined was file access "and nothing else".
    # Either the extension is already loaded, or a person names it in
    # MAPSMITH_ALLOW_EXTENSIONS, which lives outside the agent's reach.
    sql_policy.refuse_extension_loading_in_sql(query)
    con = _connect()
    record = ProvenanceRecord(
        operation="run_sql",
        parameters={"query": query},
        inputs=[],
        engine=_engine_info(),
    )
    if output_path:
        # The same net as `spatial_join` below. Without it a COPY or a check that
        # raised left the result on disk and nothing beside it (measured 2026-09-25).
        with verify.audit_on_failure(record, output_path, []):
            con.sql(f"COPY ({query}) TO '{_quote(output_path)}' ({_COPY_OPTIONS})")
            count = con.sql(
                f"SELECT count(*) FROM read_parquet('{_quote(output_path)}')"
            ).fetchone()[0]
            # SQL is opaque to static analysis: the cheapest honest check is whether
            # the materialized result carries georeference metadata (non-critical —
            # a purely tabular result is legitimate).
            out_crs = verify.probe_crs(output_path)
            checks = [
                verify.Check(
                    "crs_present",
                    out_crs != verify.UNKNOWN_CRS,
                    out_crs if out_crs != verify.UNKNOWN_CRS else
                    "no geo metadata (non-spatial result?)",
                    critical=False,
                )
            ]
            used = _mentions_spheroid_function(query)
            if used and (axis := _axis_order_check(con, used)):
                checks.append(axis)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        # Both checks above are non-critical, so this raises nothing today. It
        # is here because the alternative is a writer whose critical failures
        # are recorded and not enforced, and the day someone adds a critical
        # check to this function nobody would notice that it does not bite.
        # Sixteen of the seventeen writers that open-code the sequence already
        # end it this way; this was the seventeenth.
        verify.enforce(checks, "run_sql")
        result = {
            "output": str(output_path),
            "row_count": int(count),
            "provenance": str(manifest),
        }
        if advisories := verify.advisories(checks):
            result["warnings"] = advisories
        return result
    result = con.sql(query)
    rows = result.fetchmany(_PREVIEW_ROWS)
    # No output file means no manifest, and a preview query is exactly where a
    # caller is deciding whether to trust a number: the advisory has to reach
    # them here too, or it only exists when it is least needed.
    advisories: list[dict[str, Any]] = []
    used = _mentions_spheroid_function(query)
    if used and (axis := _axis_order_check(con, used)):
        advisories = verify.advisories([axis])
    return {
        **({"warnings": advisories} if advisories else {}),
        "columns": [d[0] for d in result.description],
        "rows": [[repr(v) if isinstance(v, (bytes, bytearray)) else v for v in r] for r in rows],
        "truncated_at": _PREVIEW_ROWS,
    }


def _write_empty_geoparquet(output_path: str, crs: str) -> None:
    """Rewrite a zero-row COPY output as a valid, empty GeoParquet."""
    import geopandas as gpd
    import pandas as pd

    table = pd.read_parquet(output_path)
    columns = [c for c in table.columns if c != "geometry"]
    empty = gpd.GeoDataFrame(
        {c: pd.Series(dtype=table[c].dtype) for c in columns},
        geometry=gpd.GeoSeries([], dtype="geometry"),
        crs=None if crs == verify.UNKNOWN_CRS else crs,
    )
    empty.to_parquet(output_path)


def spatial_join(
    left_path: str, right_path: str, output_path: str, predicate: str = "intersects"
) -> dict[str, Any]:
    """Attribute join by spatial predicate. GeoParquet-native fast path."""
    predicates = {"intersects": "ST_Intersects", "within": "ST_Within", "contains": "ST_Contains"}
    if predicate not in predicates:
        raise ValueError(f"predicate must be one of {sorted(predicates)}, got {predicate!r}")
    con = _connect()
    left_crs = verify.probe_crs(left_path)
    record = ProvenanceRecord(
        operation="spatial_join",
        parameters={"predicate": predicate, "engine": "duckdb"},
        inputs=[
            InputRecord.from_path(left_path, crs=left_crs, argument="left_path"),
            InputRecord.from_path(
                right_path, crs=verify.probe_crs(right_path), argument="right_path"
            ),
        ],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": left_crs,
        "reason": "DuckDB fast path joins in the shared input CRS "
        "(the router only takes this path when both inputs already match)",
    }
    fn = predicates[predicate]
    query = f"""
        SELECT l.*, r.* EXCLUDE (geometry)
        FROM {_rel(left_path)} AS l
        JOIN {_rel(right_path)} AS r
          ON {fn}(l.geometry, r.geometry)
    """
    with verify.audit_on_failure(record, output_path, []):
        con.sql(f"COPY ({query}) TO '{_quote(output_path)}' ({_COPY_OPTIONS})")
        count = con.sql(
            f"SELECT count(*) FROM read_parquet('{_quote(output_path)}')"
        ).fetchone()[0]
        # only worth asking when the result is empty: a non-empty join already
        # proves both inputs were populated, and counting via SQL (never a
        # GeoPandas read) keeps the fast path fast
        inputs_populated = count > 0 or all(
            con.sql(f"SELECT count(*) FROM {_rel(path)}").fetchone()[0] > 0
            for path in (left_path, right_path)
        )
    if count == 0:
        # DuckDB's COPY writes no "geo" metadata for a zero-row result, which
        # leaves an output that is not a GeoParquet at all: a downstream plan
        # step reading it would fail on a file we reported as written. An empty
        # result is a legitimate answer, so it has to be a legitimate file —
        # rewritten here with the analysis CRS and the joined schema.
        _write_empty_geoparquet(output_path, left_crs)

    # through audited() like every other writer: reading the output used to
    # raise before the manifest was written, losing the audit trail for exactly
    # the case the checks exist to explain
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="spatial_join",
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=left_crs if left_crs != verify.UNKNOWN_CRS else None,
            on_empty="warn" if inputs_populated else "ignore",
        ),
        repair=False,  # the join's geometry comes straight from the inputs
    )
    return {
        "output": str(output_path),
        "feature_count": int(count),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def supports_inputs(*paths: str) -> bool:
    """The DuckDB fast path expects GeoParquet inputs with a 'geometry' column."""
    return all(Path(p).suffix.lower() == ".parquet" for p in paths)
