"""Deterministic output verification — MapSmith's core promise.

Every operation's output is checked against explicit pre/postconditions
(CRS discipline, geometry validity, count and extent invariants). Results are
recorded in the provenance manifest; critical failures raise instead of
silently returning wrong data. External deterministic signals beat LLM
self-critique — so none of this involves a model.
"""

from __future__ import annotations

import itertools
import os
from contextlib import contextmanager, suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import readers


class VerificationError(RuntimeError):
    """An output failed a critical deterministic check. The manifest still records it."""


UNKNOWN_CRS = "unknown"

# The check that says "this operation verified nothing". It is a constant
# because `audited` emits it and `enforce` recognises it: two distant points
# that have to keep agreeing, which makes it a contract rather than a repeated
# string. Prefixed, because section 3.6 closed the core name vocabulary.
VERIFICATION_ABSENT = "x-mapsmith:verification_present"


def probe_crs(path: str) -> str:
    """CRS of an existing dataset from metadata only (no data scan, never raises).

    GeoParquet via the pyarrow ``geo`` schema metadata (missing/null crs means
    OGC:CRS84 per spec), rasters via rasterio when installed, everything else
    via pyogrio. Returns ``"unknown"`` whenever the CRS cannot be determined.
    """
    lower = str(path).lower()
    try:
        if lower.endswith(".parquet"):
            return _probe_geoparquet_crs(str(path))
        if lower.endswith((".tif", ".tiff")):
            try:
                import rasterio
            except ImportError:
                return UNKNOWN_CRS
            with rasterio.open(path) as ds:
                return str(ds.crs) if ds.crs else UNKNOWN_CRS
        from . import readers

        if readers.ambiguous_layers(str(path)):
            # A container with no chosen layer has no single CRS to report.
            # Reporting the first layer's would have the dispatcher and the
            # plan validator inspect a layer no operation will read (#29).
            return UNKNOWN_CRS
        import pyogrio

        crs = pyogrio.read_info(str(path)).get("crs")
        return str(crs) if crs else UNKNOWN_CRS
    except Exception:  # noqa: BLE001 — probing must never break the caller
        return UNKNOWN_CRS


def as_crs(value: Any) -> Any | None:
    """A pyproj CRS for whatever we were handed, or None when it is not one.

    Callers pass pyproj CRSs, rasterio CRSs, authority strings and — the bug
    this exists to stop — MapSmith's own display labels. Normalising once means
    a comparison never silently degrades to string equality between two things
    that were never the same kind.
    """
    if value is None:
        return None
    from pyproj import CRS

    if isinstance(value, CRS):
        return value
    with suppress(Exception):
        return CRS.from_user_input(value)
    return None


def same_crs(left: Any, right: Any) -> bool:
    """Do these two describe the same coordinate system?

    Compares the coordinate systems, not their labels. Comparing labels was how
    a display string ended up on the expected side of ``crs_matches``, where
    ``CRS.equals`` quietly returns False for anything it cannot parse — so a
    correct output in a CRS with no EPSG code failed a CRITICAL check.
    """
    a, b = as_crs(left), as_crs(right)
    if a is not None and b is not None:
        return bool(a.equals(b))
    return crs_label(left) == crs_label(right)


def crs_label(crs: Any) -> str:
    """Short, stable label for a CRS: 'EPSG:32632' rather than 2.5 KB of PROJJSON.

    `str(crs)` returns the EPSG string for a CRS read from a GeoPackage but the
    full PROJJSON document for one read from GeoParquet — the canonical format
    — so manifests and check details grew a JSON blob per field depending on
    the input format alone.

    Presentation only, with one hard rule: **a label never collapses two
    different coordinate systems into one string, and never borrows the
    sentinel for a CRS that does not exist.** Both happen without trying.
    pyproj names an authority-less PROJJSON document ``unknown``, which is the
    literal value of :data:`UNKNOWN_CRS`; and two unrelated custom projections
    routinely share a name (``Custom LAEA``, ``WGS_1984_Albers``). Labels are
    compared as well as printed — ``dispatch`` decides on them whether two
    layers need aligning — so a collision is a wrong number, not an ugly
    manifest. Hence the digest, appended whenever no authority can vouch for
    the name.

    The digest identifies a CRS *within one PROJ build*: it is taken over
    WKT2:2019, whose text PROJ can change between releases as ``proj.db``
    grows. It is a tie-breaker, not an identifier to compare across machines —
    for that, compare the CRSs themselves with :func:`same_crs`.
    """
    if crs is None:
        return UNKNOWN_CRS
    parsed = as_crs(crs)
    if parsed is None:
        return str(crs)
    epsg = parsed.to_epsg()
    if epsg:
        return f"EPSG:{epsg}"
    authority = parsed.to_authority()
    if authority:
        return ":".join(authority)
    import hashlib

    digest = hashlib.sha256(parsed.to_wkt(version="WKT2_2019").encode()).hexdigest()[:12]
    name = (parsed.name or "").strip()
    if name and name.lower() != UNKNOWN_CRS:
        return f"{name} (sha256:{digest})"
    return f"unnamed CRS (sha256:{digest})"


NATIVE_GEO_TYPES = readers.NATIVE_GEO_TYPES
native_geometry_column = readers.native_geometry_column


def native_crs_declaration(path: str, declaration: str) -> str:
    """Label form of :func:`mapsmith.readers.native_crs` — for manifests only.

    Resolution and presentation are two different questions (#28): use
    ``readers.native_crs`` when you need the CRS to read a file with, and this
    when you need a string to record. Feeding this value back in as if it were
    a CRS is what dropped a declared CRS whose name happened to be ``unknown``.
    """
    crs, _reason = readers.native_crs(path, declaration)
    return crs_label(crs) if crs is not None else UNKNOWN_CRS


def _probe_geoparquet_crs(path: str) -> str:
    import json

    import pyarrow.parquet as pq

    metadata = pq.read_schema(path).metadata or {}
    geo = metadata.get(b"geo")
    if not geo:
        # No `geo` key does not mean no geometry: GeoParquet 2.0 stores it in
        # Parquet's own logical types and makes the key optional.
        native = native_geometry_column(path)
        return native_crs_declaration(path, native[1]) if native else UNKNOWN_CRS
    geo_meta = json.loads(geo)
    column = geo_meta.get("primary_column", "geometry")
    spec = geo_meta.get("columns", {}).get(column, {})
    # The GeoParquet spec distinguishes two cases that must NOT be conflated:
    # the "crs" field being ABSENT means OGC:CRS84, while an explicit null
    # means "undefined or unknown". GeoPandas writes null for crs=None and
    # reads it back as None, so treating null as CRS84 would have MapSmith
    # invent a coordinate system and record it in the manifest as fact — the
    # worst possible failure for a provenance product, and it defeated the
    # CRS precondition in the canonical format.
    if "crs" not in spec:
        crs = "OGC:CRS84"
    elif spec["crs"] is None:
        return UNKNOWN_CRS
    else:
        crs = spec["crs"]
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    try:
        return crs_label(CRS.from_user_input(crs))
    except (CRSError, ValueError):
        # A `geo` key stating a CRS PROJ cannot read is not a CRS we know.
        return UNKNOWN_CRS


@dataclass
class Check:
    """One deterministic verification result.

    ``name`` is a stable code an agent can branch on; ``hint`` says what to do
    about a failure. Benchmarks put the bulk of GIS-agent failures at execution
    time (wrong parameters, outputs that exist but are meaningless), so a check
    that only reports *that* something is wrong wastes the diagnosis it already
    has.
    """

    name: str
    passed: bool
    detail: str
    critical: bool = True
    hint: str | None = None
    # which argument the check is about: without it two inputs produce two
    # identically named entries that a consumer indexing by name would collapse
    argument: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


MAX_REPAIR_ROUNDS = 2


_gpkg_layers = readers.gpkg_layers
_read_vector = readers.read_vector_or_table


def verify_loaded_inputs(operation: str, **frames: Any) -> list[Check]:
    """Per-input preconditions on frames the engine has ALREADY read.

    A missing CRS is refused here: metric maths on unknown units produces
    numbers that look fine and mean nothing. An empty input is reported but
    allowed — it is legitimate, just rarely intended.

    Pairwise checks live in :func:`verify_input_pairs` because callers need
    these *before* aligning coordinate systems and those *after*.
    """
    checks: list[Check] = []
    for arg, gdf in frames.items():
        if gdf is None:
            continue
        has_crs = gdf.crs is not None
        # When the reader knows *why* there is no CRS, say so: "no CRS" about a
        # file whose schema visibly carries a `crs` field is true of the frame
        # and false of the file, and the agent cannot act on the difference
        # without being told which one it is looking at (#28).
        reason = None if has_crs else readers.crs_reason(gdf)
        checks.append(
            Check(
                "input_crs_present",
                has_crs,
                f"'{arg}': {crs_label(gdf.crs) if has_crs else reason or 'no CRS'}",
                argument=arg,
                hint=None if has_crs else
                f"'{arg}' has no coordinate reference system MapSmith can use, so "
                f"{operation} cannot know what its numbers mean. "
                + (f"{reason[0].upper() + reason[1:]} " if reason else "")
                + "Assign the correct CRS to the source dataset (reproject_layer "
                "cannot invent one).",
            )
        )
        empty = len(gdf) == 0
        checks.append(
            Check(
                "input_not_empty",
                not empty,
                f"'{arg}': {len(gdf)} features",
                critical=False,
                argument=arg,
                hint=(
                    f"'{arg}' has no features, so {operation} can only produce an "
                    "empty result. Check the dataset, or the step that produced it."
                ) if empty else None,
            )
        )
    return checks


def verify_input_pairs(operation: str, **frames: Any) -> list[Check]:
    """Pairwise preconditions: can these inputs possibly interact at all?

    Every pair is checked, not just the first two: a check that silently
    ignored a third input would claim more than it verified.
    """
    checks: list[Check] = []
    usable = {
        arg: gdf
        for arg, gdf in frames.items()
        if gdf is not None and gdf.crs is not None and len(gdf)
    }
    for (a_arg, a_gdf), (b_arg, b_gdf) in itertools.combinations(usable.items(), 2):
        pair = f"{a_arg}+{b_arg}"
        if not a_gdf.crs.equals(b_gdf.crs):
            # comparing extents across coordinate systems is meaningless; say so
            # instead of returning a check that verified nothing
            checks.append(
                Check(
                    # A core name since spec 1.0.0-draft.3. It was
                    # `x-mapsmith:inputs_comparable` for one day, with a comment
                    # arguing it belonged in the core: "the inputs share a
                    # coordinate system" is a precondition any producer comparing
                    # two layers performs, and the core already carried two of
                    # that family. Left outside, every producer names it
                    # differently, which is section 3.6's own argument. The
                    # promotion tightened the spec, so it waited for the version
                    # bump instead of happening quietly.
                    "inputs_share_crs",
                    False,
                    f"'{a_arg}' is {crs_label(a_gdf.crs)} and "
                    f"'{b_arg}' is {crs_label(b_gdf.crs)}",
                    critical=False,
                    argument=pair,
                    hint=f"'{a_arg}' and '{b_arg}' are in different coordinate "
                    f"systems, so their extents cannot be compared before "
                    f"{operation} aligns them.",
                )
            )
            continue
        a = tuple(float(v) for v in a_gdf.total_bounds)
        b = tuple(float(v) for v in b_gdf.total_bounds)
        disjoint = a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]
        checks.append(
            Check(
                "inputs_may_intersect",
                not disjoint,
                f"'{a_arg}' bounds {[round(v, 4) for v in a]} vs "
                f"'{b_arg}' bounds {[round(v, 4) for v in b]}",
                critical=False,
                argument=pair,
                hint=(
                    f"The extents of '{a_arg}' and '{b_arg}' do not overlap, so "
                    f"{operation} will produce an empty result. They probably "
                    "cover different areas, or one of them is mis-georeferenced."
                ) if disjoint else None,
            )
        )
    return checks


def verify_vector_output(
    output_path: str,
    *,
    expect_crs: str | None = None,
    expect_count: int | None = None,
    max_count: int | None = None,
    expect_geometry: set[str] | None = None,
    within_bounds: tuple[float, float, float, float] | None = None,
    bounds_margin: float = 1e-6,
    on_empty: str = "ignore",
    empty_hint: str | None = None,
) -> list[Check]:
    """Run postcondition checks on a vector output. Returns all checks (pass and fail)."""
    if on_empty not in ("ignore", "warn", "fail"):
        raise ValueError(f"on_empty must be ignore/warn/fail, got {on_empty!r}")
    checks: list[Check] = []
    gdf = _read_vector(output_path)

    if on_empty != "ignore":
        checks.append(
            Check(
                "result_not_empty",
                len(gdf) > 0,
                f"{len(gdf)} features",
                # "fail" where emptiness is provably a bug (a buffer of a
                # non-empty layer cannot be empty); "warn" where it is
                # legitimate but suspicious (a clip whose geometries genuinely
                # miss each other) — silently passing it off as success is what
                # we refuse to do either way.
                critical=on_empty == "fail",
                # The default hint is written for a spatial operation, where
                # emptiness means the geometries missed each other. A filter
                # is empty for a different reason — a value that matches
                # nothing — so an operation may replace the sentence. It may
                # not replace the NAME: one property, one core name (3.6).
                hint=None if len(gdf) else empty_hint or
                "The operation ran but matched nothing. A file exists and is valid, "
                "so downstream steps would silently work on an empty layer: check the "
                "inputs' extents and coordinate systems before trusting this result.",
            )
        )

    checks.append(
        Check(
            "crs_present",
            gdf.crs is not None,
            crs_label(gdf.crs) if gdf.crs else "output has no CRS",
        )
    )
    if expect_crs is not None and gdf.crs is not None:
        checks.append(
            Check(
                "crs_matches",
                same_crs(gdf.crs, expect_crs),
                f"expected {crs_label(expect_crs)}, got {crs_label(gdf.crs)}",
            )
        )

    if len(gdf) > 0:
        invalid = int((~gdf.geometry.is_valid).sum())
        checks.append(
            Check(
                "geometry_valid",
                invalid == 0,
                f"{invalid}/{len(gdf)} invalid geometries" if invalid else "all valid",
            )
        )
        empty = int(gdf.geometry.is_empty.sum())
        checks.append(
            Check(
                # NOT `result_not_empty`, which is a core name meaning "the output
                # has at least one feature". This is a different property — none
                # of those features is an empty geometry — and section 3.6 of the
                # spec says a core name MUST NOT be used for anything else. The
                # two were emitted together, both with `argument: null`, on
                # nineteen operations: a consumer indexing by name collapsed them.
                "x-mapsmith:no_geometry_is_empty",
                empty == 0,
                f"{empty}/{len(gdf)} empty geometries" if empty else "none empty",
                critical=False,
                hint=(
                    "Every feature kept its row but lost its geometry — the classic "
                    "sign of a distance with the wrong sign or magnitude (a negative "
                    "buffer larger than the features erodes them away). Check the "
                    "parameter and the CRS units."
                ) if empty == len(gdf) else None,
            )
        )

    if expect_count is not None:
        checks.append(
            Check(
                "feature_count_exact",
                len(gdf) == expect_count,
                f"expected {expect_count}, got {len(gdf)}",
            )
        )
    if max_count is not None:
        checks.append(
            Check(
                "feature_count_bounded",
                len(gdf) <= max_count,
                f"expected <= {max_count}, got {len(gdf)}",
            )
        )

    if expect_geometry is not None and len(gdf) > 0:
        found = set(gdf.geom_type.dropna().unique())
        checks.append(
            Check(
                "geometry_types",
                found.issubset(expect_geometry),
                f"expected subset of {sorted(expect_geometry)}, got {sorted(found)}",
            )
        )

    if within_bounds is not None and len(gdf) > 0:
        minx, miny, maxx, maxy = gdf.total_bounds
        exp = within_bounds
        m = bounds_margin
        inside = (
            minx >= exp[0] - m and miny >= exp[1] - m and maxx <= exp[2] + m and maxy <= exp[3] + m
        )
        checks.append(
            Check(
                "extent_within_expected",
                bool(inside),
                f"output bounds {[round(v, 6) for v in (minx, miny, maxx, maxy)]} "
                f"vs expected {[round(v, 6) for v in exp]} (margin {m})",
                critical=False,
            )
        )

    return checks


def _repair_invalid_geometry(output_path: str) -> str:
    """make_valid() the output, replacing the original only once the new file
    is complete.

    Three things this must never do: write through the original (a failed write
    would destroy the user's data — GDAL truncates before it writes), assume
    the active geometry column is called "geometry" (engines and ogr2ogr
    routinely name it "geom"), and rewrite a container holding layers it did
    not read — replacing a multi-layer GeoPackage with a single-layer temp file
    would silently delete the rest of the user's project.
    """
    path = Path(output_path)
    suffix = path.suffix.lower()
    if suffix not in (".parquet", ".gpkg"):
        raise ValueError(
            f"'{suffix or path.name}' is not a single-file format: rewriting it "
            "cannot be made atomic, so the repair was skipped rather than risk "
            "the output. Convert to GeoParquet or fix the geometry upstream."
        )
    layers = _gpkg_layers(output_path) if suffix == ".gpkg" else []
    if layers is None:
        raise ValueError(
            f"the layers of {path.name} could not be listed, so rewriting it "
            "could drop layers this operation never read; repair skipped."
        )
    if len(layers) > 1:
        raise ValueError(
            f"{path.name} holds {len(layers)} layers ({', '.join(layers)}): "
            "repairing it would rewrite the whole container and drop the layers "
            "this operation did not write. Write the output to its own file "
            "(GeoParquet is the canonical format) or fix the geometry upstream."
        )
    gdf = _read_vector(output_path)
    column = gdf.geometry.name
    fixed = gdf.copy()
    fixed[column] = gdf.geometry.make_valid()
    tmp = path.with_name(f"{path.stem}.mapsmith-repair{path.suffix}")
    try:
        if suffix == ".parquet":
            fixed.to_parquet(tmp)
        else:
            fixed.to_file(tmp, layer=layers[0] if layers else path.stem, driver="GPKG")
        os.replace(tmp, output_path)  # the original survives any failure above
    finally:
        if tmp.exists():
            tmp.unlink()
    return f"make_valid() on geometry column '{column}', written atomically"


# Failed check -> deterministic repair. Only mechanical, engine-level fixes
# belong here: anything needing judgement (empty results, wrong CRS choice)
# must reach the agent as a hint instead of being silently "fixed".
_REPAIRS = {"geometry_valid": _repair_invalid_geometry}


def repair_and_reverify(
    output_path: str,
    checks: list[Check],
    *,
    operation: str,
    reverify,
    max_rounds: int = MAX_REPAIR_ROUNDS,
) -> tuple[list[Check], list[dict[str, Any]]]:
    """Apply deterministic repairs to failed checks, re-verifying after each.

    Returns the final checks and an audit of every attempt, which the caller
    records in the manifest — a repaired output must never look like one that
    was right the first time, and an attempt that did NOT work must not claim
    it did. Bounded by max_rounds so a repair that fails to converge stops
    loudly instead of looping.
    """
    attempts: list[dict[str, Any]] = []
    # a repair that raised will raise again on the same input: retrying it would
    # burn the budget without ever changing the outcome
    impossible: set[str] = set()
    for round_no in range(1, max_rounds + 1):
        repairable = [
            c
            for c in checks
            if not c.passed and c.critical and c.name in _REPAIRS
            and c.name not in impossible
        ]
        if not repairable:
            break
        this_round: list[dict[str, Any]] = []
        for check in repairable:
            try:
                action, error = _REPAIRS[check.name](output_path), None
            except Exception as exc:  # noqa: BLE001 — a failed repair is an audit entry
                action, error = None, f"{type(exc).__name__}: {exc}"
                impossible.add(check.name)
            entry = {
                # Four of these are the specification's since 1.0.0-draft.5,
                # which fixed the shape of a repairs entry: `check`, `action`,
                # `error`, `resolved`. `round` is ours and says so -- the format
                # has no concept of repair rounds -- and D-077 rule 3 puts the
                # prefix on it because the container is the specification's.
                #
                # `operation` used to be here and is gone. It duplicated the
                # manifest's own root `operation`, always and by construction:
                # every caller passes one literal to `ProvenanceRecord` and the
                # same one to `audited`. Section 6 of the specification says a
                # manifest describes ONE operation, so repeating it inside a
                # repair said nothing a reader did not already have -- the same
                # case as `mapsmith_version` (D-082), and removed for the same
                # reason rather than prefixed into permanence.
                "x-mapsmith:round": round_no,
                "check": check.name,
                "action": action,
                "error": error,
                "resolved": False,
            }
            attempts.append(entry)
            this_round.append(entry)
        try:
            checks = reverify()
        except Exception as exc:  # noqa: BLE001 — verification must not mask the audit
            for entry in this_round:
                entry["error"] = entry["error"] or (
                    f"re-verification failed: {type(exc).__name__}: {exc}"
                )
            break
        passed = {c.name: c.passed for c in checks}
        for entry in this_round:
            # resolved means "the check we targeted now passes" — not "the whole
            # output is clean", which would mislabel a repair that did work
            entry["resolved"] = bool(passed.get(entry["check"]))
    return checks, attempts


def has_critical_failure(checks: list[Check]) -> bool:
    """True when at least one critical check failed (i.e. enforce would raise)."""
    return any(not c.passed and c.critical for c in checks)


def result_extras(
    checks: list[Check], repairs: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Optional keys a writer adds to its result.

    Repairs are reported as loudly as warnings: MapSmith rewriting the user's
    geometry is exactly the kind of thing that must not live only in a file the
    agent has to go and read.
    """
    extras: dict[str, Any] = {}
    warnings = advisories(checks)
    if warnings:
        extras["warnings"] = warnings
    if repairs:
        extras["repairs"] = [
            {k: r[k] for k in ("check", "action", "resolved") if k in r} for r in repairs
        ]
    return extras


def advisories(checks: list[Check]) -> list[dict[str, Any]]:
    """Non-critical failed checks, for the tool result.

    A warning that only lands in the manifest is a warning the agent has to go
    looking for; returning it inline is what makes it actionable.
    """
    return [
        {"check": c.name, "detail": c.detail, "hint": c.hint}
        for c in checks
        if not c.passed and not c.critical
    ]


@contextmanager
def audit_on_failure(record: Any, output_path: str, preconditions: list[Check]):
    """Persist the preconditions if the operation itself raises.

    The diagnosis this module exists to produce ("these extents cannot
    overlap") is most valuable exactly when the engine blows up, so it must not
    be lost with the exception.

    The failure check is **always appended**, not used as a fallback when there
    are no preconditions. It was `list(preconditions) or [...]`, which fired only
    on the empty case — so on the ~59 paths that pass a non-empty `pre`, an
    engine crash wrote a manifest made of nothing but passing checks. Conforming
    (an absent `output` claims nothing) and exactly the shape §1 of the
    specification describes as the defect to remove: a record that reads like a
    success because the only things it recorded are the things that succeeded
    before the failure.

    The specification also requires `verification` to hold at least one check —
    a record with none is "a log entry wearing a manifest's clothes", in its own
    words — which the old form happened to satisfy for the empty case. Appending
    satisfies it for both.
    """
    try:
        yield
    except Exception as failure:
        recorded = [
            *preconditions,
            Check(
                # Prefixed: section 3.6 closed the core vocabulary, and a
                # producer-specific check has to say whose it is.
                "x-mapsmith:operation_completed",
                False,
                (
                    f"the operation raised {type(failure).__name__} and did not "
                    "finish. Any other check in this record ran BEFORE that point "
                    "and says nothing about the result; this record exists to say "
                    "the run happened and stopped. It makes no claim that the "
                    "output is CORRECT, and the output may be absent or partial "
                    "— any digest recorded beside it identifies whatever bytes "
                    "exist, which is a fact and not a verification"
                ),
                hint="read the error the operation raised; this record is the "
                "audit trail, not the diagnosis",
            )
        ]
        # A MUST protected by `suppress(Exception)` is not protected. This used
        # to swallow every failure of the write, so the case this whole helper
        # exists for — the audit trail surviving the crash — could itself vanish
        # with nothing said. The realistic ways it fails are hashing an output
        # the engine still holds open, a parameter that will not serialise (loud
        # on the success path, silent here), and a full disk.
        try:
            record.add_verification(recorded).finish()
        except Exception as lost:  # noqa: BLE001 - the original failure must win
            failure.add_note(
                f"MapSmith could not even assemble the crash manifest: "
                f"{type(lost).__name__}: {lost}"
            )
            raise failure from None
        try:
            record.write_for(output_path)
        except Exception:  # noqa: BLE001 - retried below, reported if that fails too
            try:
                # Drop the one field whose computation reads the output file.
                record.write_for(output_path, with_output_digest=False)
            except Exception as lost:  # noqa: BLE001 - the original failure must win
                # Never silent: the caller gets the engine's error with a note
                # saying the trail is missing, which is the difference between
                # "no manifest" and "no manifest and nobody knows".
                failure.add_note(
                    f"MapSmith could not write the crash manifest for "
                    f"{output_path}: {type(lost).__name__}: {lost}. "
                    f"There is no audit trail on disk for this failure."
                )
        raise


def verification_absent(operation: str) -> Check:
    """The check that stands in for a verification that never happened.

    One function because two distant places need the same words: `audited`,
    when an operation's checks come back empty, and `ProvenanceRecord.write_for`,
    for the seventeen writers that build their record by hand and never reach
    `audited` at all. Two copies of this text would drift, and the thing they
    would drift on is the sentence a reader gets instead of a verification.

    Prefixed, because §3.6 closed the core vocabulary and a check about this
    producer's own discipline has to say whose it is. Critical, because the
    point is that `enforce` raises on it wherever `enforce` is reached.
    """
    return Check(
        VERIFICATION_ABSENT,
        False,
        (
            f"{operation} produced no verification at all. This record exists "
            "because the specification requires one for every dataset written, "
            "and NO CHECK LOOKED AT THE OUTPUT: the digest beside it identifies "
            "the bytes that were written, and nothing was verified about them"
        ),
        hint=(
            "this is a defect in the operation, not in the data — an operation "
            f"that writes a dataset has to check something about it, and "
            f"{operation} checked nothing"
        ),
    )


def audited(
    record: Any,
    output_path: str,
    *,
    operation: str,
    preconditions: list[Check] | None = None,
    checks_fn,
    repair: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Verify, repair what is mechanically repairable, persist, then enforce.

    Returns the manifest path and the extra keys for the writer's result. The
    order — manifest first, enforce second — is the invariant this helper
    exists to make unmissable.
    """
    with audit_on_failure(record, output_path, preconditions or []):
        checks = checks_fn()
    repairs: list[dict[str, Any]] = []
    if repair:
        checks, repairs = repair_and_reverify(
            output_path, checks, operation=operation, reverify=checks_fn
        )
    all_checks = (preconditions or []) + checks
    if not all_checks:
        # Two requirements of the specification meet here, and until 2026-09-05
        # this branch satisfied one by breaking the other. The schema needs at
        # least one check, "because a manifest with no checks at all is a log
        # entry wearing a manifest's clothes" — so it raised rather than writing
        # an empty record. But §4 says a conforming producer "emits a conforming
        # record for every dataset it writes, including failed runs", and §3
        # makes it a MUST: "a manifest MUST be written even when verification
        # fails". The dataset is already on disk by the time this helper runs
        # — every caller writes it first — so raising left it there with no
        # record beside it, which is the one thing §4 forbids outright.
        #
        # Both hold if the absence is itself recorded as a failed check. That is
        # not a compromise, it is what the two constructs on either side of this
        # one already do: `audit_on_failure` appends a failing check when the
        # engine crashes, and the lines below write the manifest and only then
        # let `enforce` raise. The caller still gets a VerificationError; the
        # difference is that the orphan dataset now has a record saying why.
        all_checks = [verification_absent(operation)]
    record.add_verification(all_checks)
    if repairs:
        record.add_repairs(repairs)
    manifest = record.finish().write_for(output_path)
    enforce(all_checks, operation, repairs)
    return str(manifest), result_extras(all_checks, repairs)


def enforce(
    checks: list[Check], operation: str, repairs: list[dict[str, Any]] | None = None
) -> None:
    """Raise VerificationError if any critical check failed.

    When repairs were attempted, the message says so: an error about an output
    MapSmith itself rewrote must not read like an error about the original.
    """
    failed = [c for c in checks if not c.passed and c.critical]
    if failed:
        details = "; ".join(f"{c.name}: {c.detail}" for c in failed)
        hints = " ".join(c.hint for c in failed if c.hint)
        if [c.name for c in failed] == [VERIFICATION_ABSENT]:
            # NOT "the output failed": nothing looked at the output. The whole
            # point of that check is the difference between "we measured it and
            # it is wrong" and "we measured nothing", and the sentence has to
            # carry it — this message is read by an agent, and "output failed"
            # is the phrasing that makes a caller retry or repair the DATA when
            # the defect is in the operation and a second run produces the same
            # nothing. Same class as every other false statement this module
            # exists to prevent, one level up: a claim about a measurement that
            # did not happen.
            raise VerificationError(
                f"{operation} verified nothing about its output ({details}). "
                + (f"{hints} " if hints else "")
                + "The provenance manifest records exactly that, and nothing more."
            )
        repaired = ""
        if repairs:
            attempted = ", ".join(sorted({r["check"] for r in repairs}))
            repaired = (
                f"MapSmith already attempted deterministic repair of [{attempted}] "
                "on this output; this is what remained. "
            )
        subject = (
            "input preconditions"
            if all(c.name.startswith("input") for c in failed)
            else "output"
        )
        raise VerificationError(
            f"{operation} {'failed' if subject == 'input preconditions' else 'output failed'}"
            f" deterministic verification ({subject}) — {details}. "
            + (f"{hints} " if hints else "")
            + repaired
            + "The provenance manifest records the full check list."
        )
