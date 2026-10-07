"""Vector operations on the permissive GeoPandas/Shapely stack.

Design rules:
- Metric operations on geographic CRS are never silent: we estimate a UTM CRS,
  record the decision in provenance, and reproject back.
- Every writer emits a provenance manifest next to the output.
"""

from __future__ import annotations

import itertools
import math
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import shapely

from .. import antimeridian, datum, readers, stacks, verify
from .. import catalog as _catalog
from ..provenance import (
    InputRecord,
    ProvenanceRecord,
    alignment_decisions,
    record_round_trip,
)


def _engine_info() -> dict[str, str]:
    return {"name": "geopandas", "version": gpd.__version__}


_read = readers.read_vector


def _write(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    """Write GeoParquet natively (canonical format), other formats via GDAL."""
    if str(output_path).lower().endswith(".parquet"):
        gdf.to_parquet(output_path)
    else:
        gdf.to_file(output_path)


def describe(path: str) -> dict[str, Any]:
    layers = readers.ambiguous_layers(path)
    if layers:
        # Inspection is the one place a multi-layer container is NOT refused:
        # describing every layer is exactly what lets the caller choose one,
        # which is what every other operation now requires (#29).
        import pyogrio

        described = []
        for name in layers:
            info = pyogrio.read_info(path, layer=name)
            described.append({
                "layer": name,
                "feature_count": int(info.get("features") or -1),
                "geometry_type": info.get("geometry_type"),
                "crs": str(info["crs"]) if info.get("crs") else None,
            })
        return {
            "path": str(path),
            "kind": "vector-container",
            "layer_count": len(described),
            "layers": described,
            "hint": (
                "this container holds more than one layer, and operations need a "
                "single-layer dataset: extract the one you mean first — "
                "run_operation(operation='extract_layer', arguments={'input_path': "
                "..., 'layer': ..., 'output_path': ...}). The layer names are "
                "listed above."
            ),
        }
    gdf = _read(path)
    return {
        "path": str(path),
        "kind": "vector",
        "crs": verify.crs_label(gdf.crs) if gdf.crs else None,
        "feature_count": len(gdf),
        "geometry_types": sorted(gdf.geom_type.dropna().unique().tolist()),
        "fields": {c: str(t) for c, t in gdf.dtypes.items() if c != gdf.geometry.name},
        # Through `antimeridian`, because a bounding box of (-180, ..., 180, ...)
        # is arithmetically right and is the wrong answer to the question
        # anybody asked. On ordinary data this is the same dict it always was.
        "extent": antimeridian.describe_extent(gdf),
    }


def buffer(input_path: str, distance_meters: float, output_path: str) -> dict[str, Any]:
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf,
            f"{input_path} has no CRS. Refusing to buffer without knowing the units — "
            "assign a CRS first (see reproject_layer).",
        ))
    # Which stack runs this, decided before any geometry is touched (D-056).
    # In open source mode nothing changes from before: it is the default and it
    # needs no licence.
    routing = stacks.route("buffer_layer")
    record = ProvenanceRecord(
        operation="buffer_layer",
        parameters={"distance_meters": distance_meters},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    if routing.get("note"):
        # A substitution is recorded. A product that sells provenance and swaps
        # engines quietly is selling the opposite.
        record.notes.append(routing["note"])
    pre = verify.verify_loaded_inputs("buffer_layer", input_path=gdf)
    original_crs = gdf.crs
    on_a_geographic_crs = bool(original_crs.is_geographic)
    if on_a_geographic_crs:
        analysis_crs = antimeridian.estimate_utm_crs(gdf)
        open_source_decision = alignment_decisions(
            analysis_crs,
            "estimated UTM zone for metric buffering on a geographic CRS",
        )
        buffered = gdf.to_crs(analysis_crs)
        buffered["geometry"] = buffered.geometry.buffer(distance_meters)
        buffered = buffered.to_crs(original_crs)
    else:
        open_source_decision = alignment_decisions(
            original_crs,
            "input CRS is already projected; distance interpreted in its units",
        )
        buffered = gdf.copy()
        buffered["geometry"] = buffered.geometry.buffer(distance_meters)
    # NOT assigned yet. The Esri branch below discards `buffered` and, in the
    # first version, left this standing: the manifest named an analysis CRS the
    # run never used and a reason that did not apply, on numbers a different
    # engine produced. A CRS decision is a record of what happened, so it is
    # written by whichever branch actually happens.
    record.crs_decisions = open_source_decision
    if on_a_geographic_crs:
        # AFTER the way back, which on this branch already happened above: see
        # `record_round_trip`. It goes here rather than beside the `to_crs`
        # because `record.crs_decisions` is assigned by whichever branch really
        # ran, and the Esri branch below discards `buffered` without travelling.
        record_round_trip(record, analysis_crs, original_crs)

    if routing["stack"] == "esri":
        # The backend computes; verification and the manifest stay MapSmith's.
        # That is the point: the engine changes, the guarantees do not — and the
        # record says which engine actually made the numbers.
        from . import esri as esri_engine

        # The unit is decided HERE, by the code that knows the CRS, because the
        # two stacks read the same number differently. Buffer's PLANAR method
        # converts a linear unit into the CRS's unit, so "100 Meters" on a CRS
        # in US survey feet buffers by 328.08 feet while the open source branch
        # buffers by 100. On a geographic CRS the open source branch reprojects
        # to UTM and buffers metres, so metres is what Esri must be told —
        # "Unknown" there would mean 100 DEGREES.
        outcome = esri_engine.run(
            "buffer_layer",
            gdf,
            {
                "distance_meters": distance_meters,
                "distance_unit": "Meters" if on_a_geographic_crs else "Unknown",
            },
        )
        if outcome["status"] == "ok":
            produced = outcome["frame"]
            # The SCHEMA delta, computed on this output rather than quoted from
            # an earlier measurement: the two engines agree on geometry and not
            # on columns, and on a dissolve one of them drops every attribute.
            # A note saying only "the fingerprints matched" would be reassuring
            # and false.
            added = sorted(set(produced.columns) - set(buffered.columns))
            dropped = sorted(set(buffered.columns) - set(produced.columns))
            record.engine = esri_engine.engine_info()
            # What actually happened, replacing the open source branch's plan.
            record.crs_decisions = (
                {
                    # NOT `analysis_crs`. Naming one and then saying none was
                    # chosen is a record that contradicts itself, and a machine
                    # reading the key gets EPSG:4326 as the analysis CRS of a
                    # geodesic computation. The key is omitted; a separate one
                    # says what happened instead -- prefixed, because it is ours
                    # and its neighbours in this object are the specification's.
                    "x-mapsmith:computed_in": verify.crs_label(original_crs),
                    "reason": "buffered in the input's own geographic CRS by the "
                    "requested stack, which interprets a distance in metres "
                    "geodesically there rather than reprojecting — so there was no "
                    "analysis CRS to choose and the key is absent rather than "
                    "filled in with the input's",
                }
                if on_a_geographic_crs
                else {
                    "analysis_crs": verify.crs_label(original_crs),
                    "reason": "input CRS is already projected; the distance was "
                    "passed to the Esri stack in the CRS's own unit so that both "
                    "stacks read the same number the same way",
                }
            )
            record.notes.append(
                "requested stack 'esri': these numbers were produced by that "
                "stack, not by MapSmith's own engines. The geometry the two "
                "produce agrees; the schema does not, and that difference is "
                f"here rather than in a footnote — columns added: {added or 'none'}; "
                f"columns not carried through: {dropped or 'none'}. Anything "
                "downstream that reads a column has to know which engine wrote it."
            )
            buffered = produced
        else:
            # Refusal or failure: fall back, and say why. Never in silence.
            record.notes.append(
                stacks.fallback_note(
                    "buffer_layer",
                    stacks.NOT_IN_THIS_LICENCE
                    if outcome["status"] == "not_in_this_licence"
                    else "the requested stack could not run it",
                    outcome.get("detail", "")[:160],
                )
            )
    # MapSmith's writer always writes, whichever engine computed: the canonical
    # format stays canonical and verification runs over a file we produced.
    # Inside the net since 2026-09-07: measured, a `_write` that touched the file
    # and then raised left 516 bytes on disk and no manifest at all.
    with verify.audit_on_failure(record, output_path, pre):
        _write(buffered, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="buffer_layer",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=original_crs,
            expect_count=len(gdf),
            expect_geometry={"Polygon", "MultiPolygon"},
            # a buffer of a non-empty layer cannot be empty: that is a bug
            on_empty="fail" if len(gdf) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(buffered),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def clip(input_path: str, mask_path: str, output_path: str) -> dict[str, Any]:
    gdf = _read(input_path)
    mask = _read(mask_path)
    _refuse_naive_antimeridian(gdf, input_path)
    _refuse_naive_antimeridian(mask, mask_path)
    record = ProvenanceRecord(
        operation="clip_layer",
        parameters={},
        inputs=[
            InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs), argument="input_path"),
            InputRecord.from_path(mask_path, crs=verify.crs_label(mask.crs), argument="mask_path"),
        ],
        engine=_engine_info(),
    )
    # the CRS gate comes first: aligning CRS is what would raise a raw pyproj
    # error on a CRS-less input, before our own check could explain it
    pre = verify.verify_loaded_inputs("clip_layer", input_path=gdf, mask_path=mask)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "clip_layer")
    aligned = gdf.crs != mask.crs
    record.crs_decisions = alignment_decisions(
        gdf.crs,
        "the mask is brought to the input layer's CRS before clipping"
        if aligned
        else "the mask is already in the input layer's CRS; nothing was reprojected",
        [("mask_path", mask.crs)] if aligned else [],
    )
    if aligned:
        mask = mask.to_crs(gdf.crs)
    # extents can only be compared once both layers share a CRS
    pre += verify.verify_input_pairs("clip_layer", input_path=gdf, mask_path=mask)
    with verify.audit_on_failure(record, output_path, pre):
        clipped = gpd.clip(gdf, mask)
        _write(clipped, output_path)
    mask_bounds = tuple(float(v) for v in mask.total_bounds)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="clip_layer",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            max_count=len(gdf),
            within_bounds=mask_bounds,
            bounds_margin=1e-6,
            # an empty clip is legitimate (extents can overlap while geometries
            # miss), so warn loudly instead of failing a valid analysis
            on_empty="warn" if len(gdf) and len(mask) else "ignore",
        ),
        # gpd.clip goes through GEOS overlay, which always returns valid
        # geometry: there is nothing here for make_valid to fix
        repair=False,
    )
    return {
        "output": str(output_path),
        "feature_count": len(clipped),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def _datum_transformation(source_crs, target_crs) -> tuple[Any, dict[str, Any]]:
    """The transformation to use here, and the record of which one it is.

    Thin on purpose. The reasoning, the measurements and the ballpark fallback
    live in `mapsmith.datum`, because this was the only place in the codebase
    that answered Argleton trap 021 and the raster side needed the same answer
    without importing the vector engine. Vector callers *choose* their
    transformation, so this is `best_operation`; an engine that picks its own
    must use `datum.default_operation` instead, or the manifest describes an
    operation that never ran.
    """
    from .. import datum

    return datum.best_operation(source_crs, target_crs)


def _transformed(geometry, transformer):
    """Apply a chosen transformer to one geometry.

    `to_crs` cannot be used here: it picks its own transformation, which is the
    thing being avoided. `shapely.ops.transform` applies the one we selected.
    """
    from shapely.ops import transform as shapely_transform

    if geometry is None or geometry.is_empty:
        return geometry
    return shapely_transform(transformer.transform, geometry)

def reproject(input_path: str, target_crs: str, output_path: str) -> dict[str, Any]:
    gdf = _read(input_path)
    record = ProvenanceRecord(
        operation="reproject_layer",
        parameters={"target_crs": target_crs},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("reproject_layer", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "reproject_layer")

    from pyproj import CRS as _CRS

    target = _CRS.from_user_input(target_crs)
    transformer, shift = _datum_transformation(gdf.crs, target)
    # The field section 3.7 of the manifest spec calls "where this format earns
    # its keep", and which this operation left empty until 2026-08-27 -- the one
    # operation whose entire purpose IS a decision about the CRS.
    # Split in two, on 2026-09-23, for the reason `record_round_trip` exists.
    # What is true before anything moves goes here; what only becomes true once
    # the coordinates have actually moved goes after the transform. Until then
    # all of it was written up front, so a `_transformed` that raised left a
    # manifest saying `target_crs: EPSG:4326` and a seven-metre transformation
    # beside coordinates that had not gone anywhere -- and section 3.7 defines
    # `target_crs` as "the coordinate system they WERE PUT INTO".
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(target),
        "reason": (
            "the caller asked for this CRS; the datum transformation was chosen by "
            "stated accuracy and the choice is recorded beside it"
        ),
        "source_crs": verify.crs_label(gdf.crs),
    }
    with verify.audit_on_failure(record, output_path, pre):
        reprojected = gdf.set_geometry(
            gdf.geometry.apply(lambda g: _transformed(g, transformer))
        ).set_crs(target, allow_override=True)
        # The coordinates are there now, so the record may say where they went
        # and by which operation. The notes are the same claim in prose and move
        # with it: both say what WAS applied.
        record.crs_decisions["target_crs"] = verify.crs_label(target)
        record.crs_decisions["transformation"] = shift
        if shift.get("x-mapsmith:default_was_ballpark"):
            record.notes.append(
                "the transformation this library selects by default for this pair is a "
                "ballpark one, which applies no datum shift at all; a published operation "
                f"with a stated accuracy of {shift['accuracy_m']} m was used instead"
            )
        if shift["is_ballpark"]:
            record.notes.append(
                "no datum transformation is available for this pair, so the coordinates "
                "were carried across as if the two datums coincided (PROJ calls this a "
                "ballpark transformation). The result is not shifted; how far it is from "
                "the true position depends on the datums and can be tens of metres."
            )
        _write(reprojected, output_path)
    # reprojection carries geometry through verbatim, so an invalid input gives
    # an invalid output: this is where mechanical repair actually earns its keep
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="reproject_layer",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=target_crs,
                expect_count=len(gdf),
                on_empty="fail" if len(gdf) else "ignore",
            ),
            verify.Check(
                # Not critical: a ballpark is legitimate when the caller knows
                # the two datums coincide. What is not legitimate is not saying
                # so, and `crs_matches` passing while the coordinates never moved
                # is exactly how this went unnoticed.
                "x-mapsmith:datum_shift_applied",
                not shift["is_ballpark"],
                (
                    f"{shift['pipeline'] or 'transformation'} — stated accuracy "
                    f"{shift['accuracy_m']} m"
                    if not shift["is_ballpark"]
                    else "ballpark: no datum transformation was available, so the "
                    "coordinates were carried across unshifted"
                ),
                critical=False,
                hint=None if not shift["is_ballpark"] else (
                    "The output CRS is the one you asked for and the coordinates "
                    "were not moved. If the two datums are not equivalent, the "
                    "result is off by the datum shift — tens of metres is typical."
                ),
            ),
        ],
    )
    return {
        "output": str(output_path),
        "crs": verify.crs_label(reprojected.crs),
        "transformation": shift,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


OVERLAY_HOWS = {"intersection", "union", "identity", "symmetric_difference", "difference"}
DISSOLVE_AGGFUNCS = {"first", "last", "sum", "mean", "median", "min", "max", "count"}


def overlay(
    input_path: str, overlay_path: str, output_path: str, how: str = "intersection"
) -> dict[str, Any]:
    if how not in OVERLAY_HOWS:
        raise ValueError(f"how must be one of {sorted(OVERLAY_HOWS)}, got {how!r}")
    left = _read(input_path)
    right = _read(overlay_path)
    _refuse_naive_antimeridian(left, input_path)
    _refuse_naive_antimeridian(right, overlay_path)
    record = ProvenanceRecord(
        operation="overlay_layers",
        parameters={"how": how, "keep_geom_type": True},
        inputs=[
            InputRecord.from_path(
                input_path, crs=verify.crs_label(left.crs), argument="input_path"
            ),
            InputRecord.from_path(
                overlay_path, crs=verify.crs_label(right.crs), argument="overlay_path"
            ),
        ],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("overlay_layers", input_path=left, overlay_path=right)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "overlay_layers")
    aligned = left.crs != right.crs
    record.crs_decisions = alignment_decisions(
        left.crs,
        "the overlay layer is brought to the input CRS before overlaying"
        if aligned
        else "both layers are already in this CRS; nothing was reprojected",
        [("overlay_path", right.crs)] if aligned else [],
    )
    if aligned:
        right = right.to_crs(left.crs)
    else:
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(left.crs),
            "reason": "both layers share the same CRS; no reprojection needed",
        }
    # Two polygons that merely TOUCH intersect in a line, and a corner contact
    # in a point. keep_geom_type=True drops those lower-dimension pieces — a
    # semantic choice a reader of the result cannot see, so it is stated here
    # and in the manifest rather than made silently.
    record.notes.append(
        "keep_geom_type=true: overlay pieces of lower dimension than the inputs "
        "(shared edges, corner contacts) are dropped from the result"
    )
    pre += verify.verify_input_pairs("overlay_layers", input_path=left, overlay_path=right)
    with verify.audit_on_failure(record, output_path, pre):
        combined = gpd.overlay(left, right, how=how, keep_geom_type=True)
        _write(combined, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="overlay_layers",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=left.crs,
            # An empty intersection or difference is legitimate but suspicious,
            # exactly like an empty clip: it comes back flagged, never silent.
            on_empty="warn" if len(left) and len(right) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "how": how,
        "feature_count": len(combined),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def dissolve(
    input_path: str, output_path: str, by: str | None = None, aggfunc: str = "first"
) -> dict[str, Any]:
    if aggfunc not in DISSOLVE_AGGFUNCS:
        raise ValueError(
            f"aggfunc must be one of {sorted(DISSOLVE_AGGFUNCS)}, got {aggfunc!r}. "
            "The aggregation is recorded in the provenance manifest: a sum reported "
            "where a mean was meant is a plausible wrong number nobody can see."
        )
    gdf = _read(input_path)
    if by is not None and by not in gdf.columns:
        columns = [c for c in gdf.columns if c != gdf.geometry.name]
        raise ValueError(
            f"column {by!r} does not exist in {input_path}. Available columns: {columns}"
        )
    record = ProvenanceRecord(
        operation="dissolve_layer",
        parameters={"by": by, "aggfunc": aggfunc},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("dissolve_layer", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "dissolve_layer")
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "dissolve is a topological union; computed in the layer's native CRS",
    }
    # The group count is knowable BEFORE the engine runs: one output feature
    # per distinct non-null key (or exactly one with no key). Declaring it here
    # turns the row count into a closed-form postcondition instead of a report.
    if by is None:
        expected = 1 if len(gdf) else 0
    else:
        expected = int(gdf[by].nunique())
        dropped = int(gdf[by].isna().sum())
        if dropped:
            record.notes.append(
                f"{dropped} features have a null {by!r} key and are dropped by the "
                "grouping (geopandas dissolve default) — they are not merged into "
                "any group"
            )
    with verify.audit_on_failure(record, output_path, pre):
        merged = gdf.dissolve(by=by, aggfunc=aggfunc, as_index=False)
        _write(merged, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="dissolve_layer",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            expect_count=expected,
            on_empty="ignore" if not len(gdf) else "warn",
        ),
    )
    return {
        "output": str(output_path),
        "by": by,
        "aggfunc": aggfunc,
        "feature_count": len(merged),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def nearest_join(
    left_path: str,
    right_path: str,
    output_path: str,
    max_distance_meters: float | None = None,
    distance_column: str = "nearest_distance_m",
) -> dict[str, Any]:
    if max_distance_meters is not None and max_distance_meters <= 0:
        raise ValueError(f"max_distance_meters must be positive, got {max_distance_meters}")
    left = _read(left_path)
    right = _read(right_path)
    _refuse_naive_antimeridian(left, left_path)
    _refuse_naive_antimeridian(right, right_path)
    record = ProvenanceRecord(
        operation="nearest_join",
        parameters={
            "max_distance_meters": max_distance_meters,
            "distance_column": distance_column,
        },
        inputs=[
            InputRecord.from_path(left_path, crs=verify.crs_label(left.crs), argument="left_path"),
            InputRecord.from_path(
                right_path, crs=verify.crs_label(right.crs), argument="right_path"
            ),
        ],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("nearest_join", left_path=left, right_path=right)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "nearest_join")

    original_crs = left.crs
    moved_right = [] if verify.same_crs(right.crs, left.crs) else [("right_path", right.crs)]
    if moved_right:
        right = right.to_crs(left.crs)
    if original_crs.is_geographic:
        # The distance column is in METERS, always: nearest-in-degrees is the
        # classic silent killer of this operation (a degree of longitude is not
        # a degree of latitude, and neither is a metre).
        analysis_crs = antimeridian.estimate_utm_crs(left)
        record.crs_decisions = {
            **alignment_decisions(
                analysis_crs,
                "estimated UTM zone for metric nearest-distance on a geographic CRS",
                moved_right,
                # The right layer went to the LEFT layer's CRS, not to the UTM
                # zone: both are taken out to UTM together on the next line.
                moved_to=original_crs,
            ),
        }
        left_m, right_m = left.to_crs(analysis_crs), right.to_crs(analysis_crs)
    else:
        record.crs_decisions = alignment_decisions(
            original_crs,
            "nearest distances measured in the input layers' own projected CRS"
            if not moved_right
            else "the right layer is brought to the left layer's CRS, and the "
            "distances are measured there",
            moved_right,
        )
        left_m, right_m = left, right
    pre += verify.verify_input_pairs("nearest_join", left_path=left_m, right_path=right_m)
    with verify.audit_on_failure(record, output_path, pre):
        joined = gpd.sjoin_nearest(
            left_m, right_m, max_distance=max_distance_meters, distance_col=distance_column
        )
        joined = joined.drop(columns=[c for c in ("index_right",) if c in joined.columns])
        if original_crs.is_geographic:
            joined = joined.to_crs(original_crs)
            # AFTER the way back, never before: see `record_round_trip`.
            record_round_trip(record, analysis_crs, original_crs)
        _write(joined, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="nearest_join",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=original_crs,
            # max_distance can legitimately empty the result; it comes back
            # flagged rather than silent, like every suspicious emptiness.
            on_empty="warn" if len(left) and len(right) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(joined),
        "distance_column": distance_column,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def explode(input_path: str, output_path: str) -> dict[str, Any]:
    gdf = _read(input_path)
    record = ProvenanceRecord(
        operation="explode_layer",
        parameters={},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("explode_layer", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "explode_layer")
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "explode changes structure, not coordinates; computed in the native CRS",
    }
    # The output size is knowable before the engine runs: one feature per
    # part. Declaring it turns the count into a closed-form postcondition.
    expected = int(
        gdf.geometry.apply(
            lambda g: len(g.geoms) if hasattr(g, "geoms") else 1
        ).sum()
    )
    with verify.audit_on_failure(record, output_path, pre):
        parts = gdf.explode(index_parts=False, ignore_index=True)
        _write(parts, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="explode_layer",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            expect_count=expected,
            on_empty="ignore" if not len(gdf) else "warn",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(parts),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


# Dimension class per geometry type: merging polygons with more polygons is
# routine; merging polygons with points is almost always a mistake upstream.
_GEOMETRY_CLASS = {
    "Point": "point",
    "MultiPoint": "point",
    "LineString": "line",
    "MultiLineString": "line",
    "LinearRing": "line",
    "Polygon": "polygon",
    "MultiPolygon": "polygon",
    "GeometryCollection": "collection",
}


def merge(input_paths: list[str], output_path: str) -> dict[str, Any]:
    if len(input_paths) < 2:
        raise ValueError(
            f"merge_layers needs at least two input layers, got {len(input_paths)}"
        )
    frames = [_read(p) for p in input_paths]
    record = ProvenanceRecord(
        operation="merge_layers",
        parameters={"layer_count": len(frames)},
        # `input_1`, `input_2`...: the names the input checks below use, so a
        # consumer can join `verification[].argument` to `inputs[].argument`.
        inputs=[
            InputRecord.from_path(path, crs=verify.crs_label(frame.crs), argument=f"input_{i}")
            for i, (path, frame) in enumerate(zip(input_paths, frames, strict=True), start=1)
        ],
        engine=_engine_info(),
    )
    named = {f"input_{i}": frame for i, frame in enumerate(frames, start=1)}
    pre = verify.verify_loaded_inputs("merge_layers", **named)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "merge_layers")
    target = frames[0].crs
    # Named and paired with the CRS each one was in, not counted: 'three of
    # five were reprojected' does not tell a reader WHICH three, and with
    # several source CRSs there is no single transformation to report -- so
    # each entry carries its own.
    moved = [
        (f"input_{i}", frame.crs)
        for i, frame in enumerate(frames, start=1)
        if not verify.same_crs(frame.crs, target)
    ]
    record.crs_decisions = alignment_decisions(
        target,
        f"{len(moved)} of {len(frames)} layers are brought to the first "
        "layer's CRS before merging"
        if moved
        else "all layers share the first layer's CRS; nothing was reprojected",
        moved,
    )
    if moved:
        frames = [
            frame if verify.same_crs(frame.crs, target) else frame.to_crs(target)
            for frame in frames
        ]
    # A column missing from one input becomes nulls in its rows — data that
    # looks measured and is actually absent. The manifest names those columns.
    per_layer = [set(frame.columns) - {frame.geometry.name} for frame in frames]
    partial = sorted(set.union(*per_layer) - set.intersection(*per_layer))
    if partial:
        record.notes.append(
            "columns present in only some inputs are null-filled in the rows of "
            f"the others: {partial}"
        )
    classes = sorted({
        _GEOMETRY_CLASS.get(t, "other")
        for frame in frames
        for t in frame.geom_type.dropna().unique()
    })
    if len(classes) > 1:
        record.notes.append(
            f"the merged layer mixes geometry classes {classes}: many formats and "
            "operations reject mixed layers — merge like with like unless this is "
            "deliberate"
        )
    geometry_name = frames[0].geometry.name
    frames = [
        frame if frame.geometry.name == geometry_name
        else frame.rename_geometry(geometry_name)
        for frame in frames
    ]
    # One output row per input row: the count is knowable before the engine runs.
    expected = sum(len(frame) for frame in frames)
    with verify.audit_on_failure(record, output_path, pre):
        merged = pd.concat(frames, ignore_index=True)
        _write(merged, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="merge_layers",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=target,
            expect_count=expected,
            on_empty="fail" if expected else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "layer_count": len(input_paths),
        "feature_count": len(merged),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def simplify(input_path: str, tolerance_meters: float, output_path: str) -> dict[str, Any]:
    if tolerance_meters <= 0:
        raise ValueError(f"tolerance_meters must be positive, got {tolerance_meters}")
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf,
            f"{input_path} has no CRS. Refusing to simplify without knowing the "
            "units — assign a CRS first (see reproject_layer).",
        ))
    record = ProvenanceRecord(
        operation="simplify_layer",
        parameters={"tolerance_meters": tolerance_meters, "preserve_topology": True},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("simplify_layer", input_path=gdf)
    original_crs = gdf.crs
    # An empty layer has nothing to estimate a UTM zone from (estimate_utm_crs
    # raises a raw pyproj error), and nothing to simplify: it passes through in
    # its own CRS with the reason recorded, instead of crashing without a manifest.
    if original_crs.is_geographic and len(gdf):
        analysis_crs = antimeridian.estimate_utm_crs(gdf)
        record.crs_decisions = alignment_decisions(
            analysis_crs,
            "estimated UTM zone for metric simplification on a geographic CRS",
        )
        work = gdf.to_crs(analysis_crs)
        restore = True
    else:
        record.crs_decisions = alignment_decisions(
            original_crs,
            "empty input layer: no UTM zone to estimate, nothing to simplify"
            if original_crs.is_geographic
            else "input CRS is already projected; tolerance interpreted in its units",
        )
        work = gdf.copy()
        restore = False
    vertices_before = int(shapely.get_num_coordinates(work.geometry.values).sum())
    area_before = float(work.geometry.area.sum())
    length_before = float(work.geometry.length.sum())
    with verify.audit_on_failure(record, output_path, pre):
        work[work.geometry.name] = work.geometry.simplify(
            tolerance_meters, preserve_topology=True
        )
        vertices_after = int(shapely.get_num_coordinates(work.geometry.values).sum())
        # Simplification moves boundaries: the drift is measured and recorded,
        # never assumed away. Zero drift is a statement too.
        if area_before > 0:
            area_after = float(work.geometry.area.sum())
            drift = (area_after - area_before) / area_before * 100
            record.notes.append(
                f"total area {area_before:.6g} -> {area_after:.6g} square CRS units "
                f"({drift:+.4f}%) in the analysis CRS"
            )
        if length_before > 0:
            length_after = float(work.geometry.length.sum())
            drift = (length_after - length_before) / length_before * 100
            record.notes.append(
                f"total length {length_before:.6g} -> {length_after:.6g} CRS units "
                f"({drift:+.4f}%) in the analysis CRS"
            )
        record.notes.append(
            f"vertices {vertices_before} -> {vertices_after} "
            f"(tolerance {tolerance_meters} in analysis-CRS units)"
        )
        if restore:
            work = work.to_crs(original_crs)
            # AFTER the way back, never before: see `record_round_trip`.
            record_round_trip(record, analysis_crs, original_crs)
        _write(work, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="simplify_layer",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=original_crs,
            expect_count=len(gdf),
            on_empty="fail" if len(gdf) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(work),
        "vertices_before": vertices_before,
        "vertices_after": vertices_after,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def centroid(input_path: str, output_path: str) -> dict[str, Any]:
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf,
            f"{input_path} has no CRS. Refusing to compute centroids without knowing "
            "the units — assign a CRS first (see reproject_layer).",
        ))
    record = ProvenanceRecord(
        operation="centroid_layer",
        parameters={},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("centroid_layer", input_path=gdf)
    original_crs = gdf.crs
    # Same guard as simplify: estimate_utm_crs on an empty layer raises a raw
    # pyproj error before any manifest exists, and there is nothing to measure.
    if original_crs.is_geographic and len(gdf):
        # A planar centroid of degree coordinates lands in the wrong place —
        # quietly, and by more the farther from the equator the data sits.
        analysis_crs = antimeridian.estimate_utm_crs(gdf)
        record.crs_decisions = alignment_decisions(
            analysis_crs,
            "estimated UTM zone for planar centroids on a geographic CRS",
        )
        work = gdf.to_crs(analysis_crs)
        restore = True
    else:
        record.crs_decisions = alignment_decisions(
            original_crs,
            "empty input layer: no UTM zone to estimate, nothing to measure"
            if original_crs.is_geographic
            else "centroids computed in the layer's native projected CRS",
        )
        work = gdf.copy()
        restore = False
    record.notes.append(
        "the geometric centroid of a concave or multi-part feature can fall outside "
        "the feature itself; a point guaranteed inside is a different operation "
        "(representative point), not a tighter centroid"
    )
    with verify.audit_on_failure(record, output_path, pre):
        work[work.geometry.name] = work.geometry.centroid
        if restore:
            work = work.to_crs(original_crs)
            # AFTER the way back, never before: see `record_round_trip`.
            record_round_trip(record, analysis_crs, original_crs)
        _write(work, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="centroid_layer",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=original_crs,
            expect_count=len(gdf),
            expect_geometry={"Point"},
            on_empty="fail" if len(gdf) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(work),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


CONVERT_FORMATS = {".parquet": "GeoParquet", ".gpkg": "GeoPackage", ".geojson": "GeoJSON"}


def convert(input_path: str, output_path: str) -> dict[str, Any]:
    suffix = Path(str(output_path)).suffix.lower()
    if suffix == ".shp":
        raise ValueError(
            "refusing to write a shapefile: field names are truncated to 10 characters "
            "and dtypes are coerced, silently — a conversion that quietly renames "
            "columns is a silent error. Write GeoPackage (.gpkg) instead; if a legacy "
            "tool truly needs a shapefile, export from the GeoPackage in that tool, "
            "where the renaming is visible."
        )
    if suffix not in CONVERT_FORMATS:
        raise ValueError(
            f"output format {suffix!r} is not supported: use one of "
            f"{sorted(CONVERT_FORMATS)}"
        )
    gdf = _read(input_path)
    # RFC 7946 prescribes WGS84 lon-lat, which the authorities spell two ways:
    # OGC:CRS84 (the GeoParquet default) and EPSG:4326 (whose formal axis order
    # GeoDataFrames ignore anyway). Both are the same coordinates here.
    wgs84 = gdf.crs is not None and any(
        verify.same_crs(gdf.crs, crs) for crs in ("EPSG:4326", "OGC:CRS84")
    )
    if suffix == ".geojson" and gdf.crs is not None and not wgs84:
        raise ValueError(
            f"GeoJSON (RFC 7946) is WGS84 by definition and this layer is in "
            f"{verify.crs_label(gdf.crs)}: writing it would produce a file whose CRS "
            "some readers honour and others ignore. Reproject to EPSG:4326 first "
            "(reproject_layer), or convert to .gpkg/.parquet, which carry any CRS."
        )
    record = ProvenanceRecord(
        operation="convert_format",
        parameters={"target_format": CONVERT_FORMATS[suffix]},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("convert_format", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "convert_format")
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "no CRS change: format conversion does not transform coordinates",
    }
    with verify.audit_on_failure(record, output_path, pre):
        _write(gdf, output_path)
    # Geometry is carried through verbatim, so an invalid input gives an invalid
    # output: as in reproject, this is where mechanical repair earns its keep,
    # and every repair lands in the manifest and the result.
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="convert_format",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            expect_count=len(gdf),
            on_empty="ignore",
        ),
    )
    return {
        "output": str(output_path),
        "format": CONVERT_FORMATS[suffix],
        "feature_count": len(gdf),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


AREA_METHODS = {"planar", "geodesic"}

# Above this relative gap between the planar and the geodesic area, the map
# plane is not telling the truth about the ground and the result says so. A
# conformal projection (Web Mercator at 42 degrees: 1.80) blows straight past
# it; a transverse Mercator zone used as intended (1.0003) stays under.
_DISTORTION_TOLERANCE = 0.01


def _geodesic_areas(gdf: gpd.GeoDataFrame) -> tuple[list[float], dict[str, Any] | None]:
    """Ground area per feature, on the ellipsoid the layer's own CRS names.

    Rings are measured one at a time and holes are subtracted explicitly.
    `Geod.geometry_area_perimeter` returns a signed value whose sign depends on
    ring orientation, so wrapping the whole geometry in `abs()` — which is what
    this function used to do — turns a courtyard into extra land: a parcel of
    10000 m2 with a 1600 m2 courtyard came back as 11609 instead of 8407, the
    two rings added rather than subtracted.

    Found by Argleton's trap 011, built the day after this function shipped,
    for exactly this class of error. The planar path never had the bug, because
    Shapely's `.area` already accounts for interiors — which is why the two
    disagreed by 38% and the distortion check was the thing that noticed.
    """
    from pyproj import Geod
    from shapely.geometry import MultiPolygon, Polygon

    # Measure on the ellipsoid the COORDINATES are on, which after the line
    # below is WGS 84 — not the source CRS's ellipsoid. Taking `gdf.crs.ellipsoid`
    # and then reprojecting measured NAD27 or OSGB36 coordinates that had already
    # become WGS 84 ones, and named the source's ellipsoid in `analysis_crs`. The
    # magnitude is tens of parts per million, so this is a labelling defect more
    # than a numeric one — but `analysis_crs` saying "Clarke 1866 (ellipsoidal)"
    # about a WGS 84 computation is precisely the kind of statement a manifest
    # exists to make true. `.ellipsoid` can also be None on an engineering CRS,
    # which raised an AttributeError instead of saying anything.
    moved = not verify.same_crs(gdf.crs, "EPSG:4326")
    shift = datum.default_operation(gdf.crs, "EPSG:4326") if moved else None
    lonlat = gdf.to_crs("EPSG:4326") if moved else gdf
    ellipsoid = lonlat.crs.ellipsoid
    if ellipsoid is None:  # pragma: no cover - WGS 84 always names one
        raise ValueError(
            f"{gdf.crs} names no ellipsoid, so a ground area cannot be computed on "
            "one. Use method='planar' if a map-plane area is what you want."
        )
    geod = Geod(a=ellipsoid.semi_major_metre, rf=ellipsoid.inverse_flattening)

    def ring_area(ring) -> float:
        lons, lats = ring.coords.xy
        return abs(geod.polygon_area_perimeter(list(lons), list(lats))[0])

    def polygon_area(polygon: Polygon) -> float:
        return ring_area(polygon.exterior) - sum(
            ring_area(interior) for interior in polygon.interiors
        )

    areas: list[float] = []
    for geom in lonlat.geometry:
        if geom is None or geom.is_empty:
            areas.append(0.0)
        elif isinstance(geom, Polygon):
            areas.append(polygon_area(geom))
        elif isinstance(geom, MultiPolygon):
            areas.append(sum(polygon_area(part) for part in geom.geoms))
        else:
            # Points and lines enclose no area; the caller's own check refuses
            # them before this runs, and returning 0 keeps that the only place
            # the refusal lives.
            areas.append(0.0)
    return areas, shift


def measure_area(
    input_path: str,
    output_path: str,
    method: str = "geodesic",
    area_column: str = "area_m2",
) -> dict[str, Any]:
    if method not in AREA_METHODS:
        raise ValueError(f"method must be one of {sorted(AREA_METHODS)}, got {method!r}")
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf,
            f"{input_path} has no CRS. Refusing to measure an area without knowing "
            "the units — assign a CRS first (see reproject_layer).",
        ))
    if method == "planar" and gdf.crs.is_geographic:
        raise ValueError(
            f"{input_path} is in a geographic CRS ({verify.crs_label(gdf.crs)}), so a "
            "planar area would be in square degrees — a number that is not an area of "
            "anything. Use method='geodesic' for ground area, or reproject to a "
            "projected CRS first (reproject_layer)."
        )
    record = ProvenanceRecord(
        operation="measure_area",
        parameters={"method": method, "area_column": area_column},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("measure_area", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "measure_area")

    # Repair BEFORE measuring, not after: the planar area of a self-intersecting
    # ring is the signed shoelace — a number that matches no region and raises
    # nothing. Measuring first and repairing the output would keep the wrong
    # number. Every repair is recorded, because a silent repair trades one
    # silence for another.
    invalid = int((~gdf.geometry.is_valid).sum())
    input_repairs: list[dict[str, Any]] = []
    if invalid:
        from shapely.validation import make_valid

        gdf = gdf.copy()
        gdf[gdf.geometry.name] = gdf.geometry.apply(make_valid)
        # Recorded as a repair, not as a note: `repairs` is where the rest of
        # the system — and anyone reading the manifest — looks to find out
        # whether MapSmith rewrote the caller's geometry.
        # The keys follow 1.0.0-draft.5, which fixed the shape of a repairs
        # entry: `check`, `action`, `error` and `resolved` are the
        # specification's, `x-mapsmith:round` is ours and carries the prefix
        # because the container is not. `"operation": "measure_area"` used to
        # be here and is gone -- the manifest's root already says which
        # operation this is, and section 6 says a manifest describes one.
        input_repairs = [{
            "x-mapsmith:round": 1,
            "check": "x-mapsmith:input_geometry_valid",
            "action": f"make_valid applied to {invalid} input geometries BEFORE "
            "measuring: the planar area of a self-intersecting ring is the signed "
            "shoelace, which matches no region and is returned without complaint",
            "error": None,
            "resolved": True,
        }]
        record.add_repairs(input_repairs)

    geodesic, geodesic_shift = _geodesic_areas(gdf)
    if method == "planar":
        # The unit comes from the CRS, exactly once, and is not assumed to be
        # the metre: a layer in US survey feet is 0.0929 m2 per square foot.
        factor = gdf.crs.axis_info[0].unit_conversion_factor
        areas = [float(a) * factor**2 for a in gdf.geometry.area]
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(gdf.crs),
            "reason": "planar area in the layer's own CRS, converted to square metres "
            f"with its declared linear unit ({gdf.crs.axis_info[0].unit_name}, "
            f"factor {factor!r})",
        }
    else:
        areas = geodesic
        record.crs_decisions = {
            # The ellipsoid the measurement actually ran on, which is WGS 84's:
            # the coordinates are moved there first. Naming the source CRS's
            # ellipsoid here described a computation that did not happen.
            "analysis_crs": "WGS 84 (ellipsoidal)",
            "reason": "ground area computed on the WGS 84 ellipsoid, which is where "
            "the coordinates are put first; no map plane is involved, so no "
            "projection distortion enters",
            # Putting them there crosses a datum on anything but WGS 84, and
            # the measurement is made AFTER that move.
            **({"transformation": geodesic_shift} if geodesic_shift else {}),
        }
    planar_total = float(sum(areas)) if method == "planar" else None
    geodesic_total = float(sum(geodesic))
    total = float(sum(areas))

    distortion: float | None = None
    if method == "planar" and geodesic_total > 0:
        distortion = planar_total / geodesic_total
        record.notes.append(
            f"planar total {planar_total:.6g} m2 against the ellipsoidal ground area "
            f"{geodesic_total:.6g} m2: ratio {distortion:.6f}"
        )

    with verify.audit_on_failure(record, output_path, pre):
        measured = gdf.copy()
        measured[area_column] = areas
        _write(measured, output_path)

    def checks() -> list[verify.Check]:
        result = verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            expect_count=len(gdf),
            on_empty="fail" if len(gdf) else "ignore",
        )
        # More than one KIND of feature is a different statement from "some of
        # them have no area", which is what `area_is_measurable` below reports —
        # and that one passes as soon as a single polygon is present, with the
        # count buried in its detail. A total over a mixed layer is a total over
        # two questions, so it gets a check that fails.
        result.append(_mixed_geometry_check(gdf, "measure_area", "area"))
        polygonal = int(
            gdf.geom_type.isin(["Polygon", "MultiPolygon", "GeometryCollection"]).sum()
        )
        result.append(
            verify.Check(
                "x-mapsmith:area_is_measurable",
                polygonal > 0 or not len(gdf),
                f"{polygonal}/{len(gdf)} features have polygonal geometry",
                critical=False,
                hint=None if polygonal or not len(gdf) else
                "Points and lines enclose no area, so every value is 0. That is "
                "arithmetically right and probably not the question: check whether "
                "the layer you meant is the polygon one.",
            )
        )
        if distortion is not None:
            off = abs(distortion - 1.0)
            result.append(
                verify.Check(
                    # Prefixed: the core of section 3.6 has no name for "the
                    # map plane reports the ground area", and inventing an
                    # unprefixed one is what makes two records incomparable.
                    "x-mapsmith:planar_area_matches_ground",
                    off <= _DISTORTION_TOLERANCE,
                    f"planar/ellipsoidal area ratio {distortion:.6f}",
                    critical=False,
                    hint=None if off <= _DISTORTION_TOLERANCE else
                    f"This CRS's plane reports {distortion:.4f}x the ground area at "
                    "this location — it is not equal-area here. The planar number is "
                    "arithmetically exact and answers a question about the map, not "
                    "about the land. For ground area use method='geodesic' "
                    f"({geodesic_total:.6g} m2).",
                )
            )
        return result

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="measure_area",
        preconditions=pre,
        checks_fn=checks,
        # geometry was already repaired before measuring; repairing the output
        # again would change what the recorded numbers describe
        repair=False,
    )
    result = {
        "output": str(output_path),
        "method": method,
        "area_column": area_column,
        "total_area_m2": total,
        "feature_count": len(gdf),
        "ground_area_m2": geodesic_total,
        "provenance": manifest,
        "verified": True,
        **extras,
    }
    if input_repairs:
        # audited() reports only the repairs it performed itself (none here:
        # repair=False), so the pre-measurement one is added in the same shape.
        result["repairs"] = [
            {k: entry[k] for k in ("check", "action", "resolved")}
            for entry in input_repairs
        ]
    return result


def spatial_join(
    left_path: str, right_path: str, output_path: str, predicate: str = "intersects"
) -> dict[str, Any]:
    allowed = {"intersects", "within", "contains"}
    if predicate not in allowed:
        raise ValueError(f"predicate must be one of {sorted(allowed)}, got {predicate!r}")
    left = _read(left_path)
    right = _read(right_path)
    _refuse_naive_antimeridian(left, left_path)
    _refuse_naive_antimeridian(right, right_path)
    record = ProvenanceRecord(
        operation="spatial_join",
        parameters={"predicate": predicate},
        inputs=[
            InputRecord.from_path(left_path, crs=verify.crs_label(left.crs), argument="left_path"),
            InputRecord.from_path(
                right_path, crs=verify.crs_label(right.crs), argument="right_path"
            ),
        ],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("spatial_join", left_path=left, right_path=right)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "spatial_join")
    aligned = left.crs != right.crs
    record.crs_decisions = alignment_decisions(
        left.crs,
        "the right layer is brought to the left layer's CRS before joining"
        if aligned
        else "both layers are already in this CRS; nothing was reprojected",
        [("right_path", right.crs)] if aligned else [],
    )
    if aligned:
        right = right.to_crs(left.crs)
    pre += verify.verify_input_pairs("spatial_join", left_path=left, right_path=right)
    with verify.audit_on_failure(record, output_path, pre):
        joined = gpd.sjoin(left, right, predicate=predicate, how="inner")
        joined = joined.drop(columns=[c for c in ("index_right",) if c in joined.columns])
        _write(joined, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="spatial_join",
        preconditions=pre,
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=left.crs,
            on_empty="warn" if len(left) and len(right) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(joined),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


JOIN_KINDS = {"inner", "left"}


def join_table(
    input_path: str,
    table_path: str,
    output_path: str,
    on: str,
    how: str = "left",
) -> dict[str, Any]:
    """Join a CSV table onto a layer by a key column, keys read as text.

    Two things go wrong in this operation and neither raises anything, so both
    are handled here rather than left to the caller.

    **Keys are read as text, always.** A CSV reader that infers types turns the
    identifier ``001`` into the integer ``1``, which matches nothing: rows drop
    out of an inner join with no error, and the total they carried disappears.
    Leading zeros are the norm in national identifier schemes — ISTAT, FIPS,
    INSEE, postcodes — so the safe reading is the one that preserves them.

    **Cardinality is measured, not assumed.** If the table has more than one row
    per key, the join multiplies features, and any sum over the result counts
    the duplicated ones twice. The row counts before and after are compared and
    the fan-out is reported: a join that changed the feature count is a fact the
    caller has to know before aggregating.
    """
    import pandas as pd

    if how not in JOIN_KINDS:
        raise ValueError(f"how must be one of {sorted(JOIN_KINDS)}, got {how!r}")
    gdf = _read(input_path)
    if on not in gdf.columns:
        columns = [c for c in gdf.columns if c != gdf.geometry.name]
        raise ValueError(
            f"key column {on!r} is not in {input_path}. Available: {columns}"
        )
    # dtype=str on the key alone: the other columns keep their natural types,
    # because turning a population into a string would trade one silent defect
    # for another.
    table = pd.read_csv(table_path, dtype={on: str})
    if on not in table.columns:
        raise ValueError(
            f"key column {on!r} is not in {table_path}. Available: {list(table.columns)}"
        )

    record = ProvenanceRecord(
        operation="join_table",
        parameters={"on": on, "how": how, "key_dtype": "str"},
        inputs=[
            InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs), argument="input_path"),
            InputRecord.from_path(table_path, argument="table_path"),
        ],
        engine={"name": "pandas", "version": pd.__version__},
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "an attribute join changes columns, not geometry or CRS",
    }
    pre = verify.verify_loaded_inputs("join_table", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "join_table")

    gdf = gdf.copy()
    gdf[on] = gdf[on].astype(str)
    duplicated_keys = int(table[on].duplicated().sum())
    unmatched = int((~gdf[on].isin(set(table[on]))).sum())

    with verify.audit_on_failure(record, output_path, pre):
        joined = gdf.merge(table, on=on, how=how)
        _write(joined, output_path)

        # Still inside the net: everything between the write and `audited` is, so a
        # note or a check that raises here cannot leave the output without a record.
        if duplicated_keys:
            record.notes.append(
                f"{duplicated_keys} duplicate key(s) in the table: the join produced "
                f"{len(joined)} features from {len(gdf)}, so any sum over the result "
                "counts the multiplied features more than once — aggregate the table "
                "before joining if that is not what you want"
            )
        if unmatched:
            record.notes.append(
                f"{unmatched} feature(s) matched no row in the table"
                + (
                    " and were dropped by the inner join"
                    if how == "inner"
                    else " and carry null attributes"
                )
            )

        checks: list[verify.Check] = [
            verify.Check(
                # `feature_count_exact` and not an extension: the predicate here is
                # word for word the core definition in section 3.6 of the spec --
                # the output's feature count equals a count derived before the
                # operation ran -- and §3.6 says a producer performing a core check
                # MUST use the core name. `validate_geometry` in this same file
                # already emits `feature_count_exact` for the identical comparison,
                # so calling it something else here answered "does this system check
                # that the count was preserved?" with yes for one operation and no
                # for the other. The fan-out diagnosis lives in `hint`, which is
                # where a name cannot carry it anyway.
                "feature_count_exact",
                len(joined) == len(gdf),
                f"{len(gdf)} features in, {len(joined)} out",
                critical=False,
                hint=None
                if len(joined) == len(gdf)
                else (
                    "The table has more than one row per key, so features were "
                    "duplicated. Summing an area or a population over this result "
                    "counts the duplicated features once per row — the classic "
                    "fan-out. Aggregate the table first, or count distinct."
                ),
            ),
            verify.Check(
                "x-mapsmith:every_feature_matched",
                unmatched == 0,
                f"{unmatched} of {len(gdf)} features matched nothing",
                critical=False,
                hint=None
                if unmatched == 0
                else (
                    "Keys were compared as text, so this is a real mismatch rather "
                    "than a type problem. Check for whitespace, case, or codes that "
                    "exist on one side only."
                ),
            ),
        ]
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="join_table",
        preconditions=pre,
        checks_fn=lambda: checks
        + verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            on_empty="warn" if len(gdf) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(joined),
        "input_feature_count": len(gdf),
        "unmatched_features": unmatched,
        "duplicate_keys": duplicated_keys,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


LENGTH_METHODS = {"planar", "geodesic", "3d"}


def _mixed_geometry_check(gdf: Any, operation: str, quantity: str) -> Any:
    """A layer holding more than one geometry type, said out loud.

    A GeoPackage layer may declare its type as GEOMETRY and hold whatever it
    likes; GeoJSON never restricted it either. Only the shapefile enforced one
    type per file, which is why this arrives exactly when data is converted out
    of shapefiles and the split the old format imposed is merged away.

    The consequence is not an error and cannot be one. Shapely answers `length`
    on a polygon with its perimeter, which is a real quantity and the right
    answer to a question nobody asked; it answers `area` on a line with zero,
    which is also true. So a total over a mixed layer is a total of two
    different things, every individual row is still correct, and a spot check of
    the data confirms the data.

    Measured by Argleton trap 027 on 2026-08-30: five pipe runs and one
    treatment plant in one layer, and the total length came back 3000 m where
    the pipe is 2000 — the plant's fence line, added in silence.

    Not critical. Measuring a mixed layer is a legitimate thing to ask for and
    MapSmith cannot know which features the question was about. What it can do
    is refuse to let the answer arrive without the sentence.
    """
    kinds = sorted({str(k) for k in gdf.geom_type.dropna().unique()})
    families = {k.replace("Multi", "") for k in kinds}
    return verify.Check(
        "x-mapsmith:one_geometry_type_in_the_layer",
        len(families) <= 1,
        f"the layer holds {kinds}, so this {quantity} is a total over more than "
        "one kind of feature",
        critical=False,
        hint=f"a polygon's length is its perimeter and a line's area is zero, so "
        f"{operation} over a mixed layer adds quantities that answer different "
        "questions. Every individual row is still right, which is why a spot "
        "check will not show it. Keep the features the question is about first: "
        "run_operation(operation='select_features', arguments={'by': "
        "'geometry_type', 'value': 'line'|'polygon'|'point', ...}).",
    )


def measure_length(
    input_path: str,
    output_path: str,
    method: str = "geodesic",
    length_column: str = "length_m",
) -> dict[str, Any]:
    """Length per feature in metres, with the third dimension counted when asked.

    ``3d`` uses the Z the geometry carries: a pipe that climbs 300 m over 400 m
    of ground is 500 m of pipe, and every 2D length function in the stack
    answers 400 without mentioning it — in PostGIS the difference is the name of
    the function (``ST_Length`` against ``ST_3DLength``), in Shapely it is a
    property that quietly drops the coordinate.

    ``geodesic`` (the default) measures on the ellipsoid the CRS names; ``planar``
    measures in the CRS's own plane and converts to metres by its declared unit.
    When the layer has Z and a flat method was chosen, the result carries the 3D
    length alongside as a non-critical check, because the difference is exactly
    what nobody notices.
    """
    if method not in LENGTH_METHODS:
        raise ValueError(f"method must be one of {sorted(LENGTH_METHODS)}, got {method!r}")
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf, f"{input_path} has no CRS, so a length in metres has no meaning."
        ))
    record = ProvenanceRecord(
        operation="measure_length",
        parameters={"method": method, "length_column": length_column},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs("measure_length", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "measure_length")

    has_z = bool(shapely.has_z(gdf.geometry.values).any())
    if method == "3d":
        if not has_z:
            raise ValueError(
                f"{input_path} has no Z coordinates, so a 3D length would equal the "
                "2D one. Use method='planar' or 'geodesic' and say so, rather than "
                "reporting a 3D measurement that measured nothing of the sort."
            )
        lengths = [_length_3d(geom) for geom in gdf.geometry]
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(gdf.crs),
            "reason": "3D length in the layer's own projected CRS: horizontal and "
            "vertical units must match, which they do not on a geographic CRS",
        }
        if gdf.crs.is_geographic:
            raise ValueError(
                "a 3D length on a geographic CRS would add degrees to metres. "
                "Reproject to a projected CRS first (reproject_layer)."
            )
    elif method == "geodesic":
        lengths, geodesic_shift = _geodesic_lengths(gdf)
        record.crs_decisions = {
            # WGS 84's ellipsoid, because that is the one the coordinates are on
            # by the time the measurement runs -- see `_geodesic_lengths`. Naming
            # the source CRS here described a computation that did not happen, and
            # the sibling `measure_area` had already been corrected for it.
            "analysis_crs": "WGS 84 (ellipsoidal)",
            "reason": "measured on the WGS 84 ellipsoid, which is where the "
            "coordinates are put first; the map plane is not consulted, so no "
            "projection distortion enters",
            **({"transformation": geodesic_shift} if geodesic_shift else {}),
        }
    else:
        factor = 1.0 if gdf.crs.is_geographic else gdf.crs.axis_info[0].unit_conversion_factor
        if gdf.crs.is_geographic:
            raise ValueError(
                "a planar length on a geographic CRS would be in degrees. Use "
                "method='geodesic', or reproject first."
            )
        lengths = [float(geom.length) * factor for geom in gdf.geometry]
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(gdf.crs),
            "reason": f"planar length in the CRS plane, converted to metres by its "
            f"declared unit (factor {factor})",
        }

    measured = gdf.copy()
    measured[length_column] = lengths
    total = float(sum(lengths))
    with verify.audit_on_failure(record, output_path, pre):
        _write(measured, output_path)

        checks: list[verify.Check] = [
            _mixed_geometry_check(gdf, "measure_length", "length")
        ]
        if has_z and method != "3d":
            three_d = float(sum(_length_3d(geom) for geom in gdf.geometry))
            difference = abs(three_d - total) / three_d * 100 if three_d else 0.0
            checks.append(
                verify.Check(
                    "x-mapsmith:flat_length_on_3d_geometry",
                    difference < 0.01,
                    f"the layer carries Z: {method} gives {total:.3f} m, the 3D length "
                    f"is {three_d:.3f} m ({difference:.2f}% apart)",
                    critical=False,
                    hint=(
                        "The geometry has elevations and this measurement ignored them. "
                        "For anything that follows the ground — a pipe, a cable, a path "
                        "— use method='3d'. If the plan-view length is what you wanted, "
                        "this check is the record that you chose it."
                    )
                    if difference >= 0.01
                    else None,
                )
            )
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="measure_length",
        preconditions=pre,
        checks_fn=lambda: checks
        + verify.verify_vector_output(
            output_path, expect_crs=gdf.crs, expect_count=len(gdf), on_empty="ignore"
        ),
    )
    return {
        "output": str(output_path),
        "method": method,
        "total_length_m": total,
        "feature_count": len(measured),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def _length_3d(geom: Any) -> float:
    """Length of a geometry through space, using Z where it exists."""
    import math

    if geom is None or geom.is_empty:
        return 0.0
    if hasattr(geom, "geoms"):
        return sum(_length_3d(part) for part in geom.geoms)
    coords = list(geom.coords)
    total = 0.0
    for start, end in itertools.pairwise(coords):
        dx, dy = end[0] - start[0], end[1] - start[1]
        dz = (end[2] - start[2]) if len(start) > 2 and len(end) > 2 else 0.0
        total += math.sqrt(dx * dx + dy * dy + dz * dz)
    return total


def _geodesic_lengths(gdf: gpd.GeoDataFrame) -> tuple[list[float], dict[str, Any] | None]:
    """Length per feature on the ellipsoid the COORDINATES are on."""
    from pyproj import Geod

    # The same defect `_geodesic_areas` describes two hundred lines above,
    # left standing in the twin. It took `gdf.crs.ellipsoid` and then measured
    # coordinates that the next line had already turned into WGS 84 ones: on
    # NAD27 that is Clarke 1866 arithmetic on WGS 84 numbers, 2.61 m per
    # 100 km (26 ppm, measured 2026-09-06). Small as a number and wrong as a
    # statement, which is the half a manifest exists to get right.
    #
    # The lesson was written beside the fix in the other copy and the second
    # copy was never touched -- the shape #28 is about, and the reason
    # `readers.py` exists.
    moved = not verify.same_crs(gdf.crs, "EPSG:4326")
    shift = datum.default_operation(gdf.crs, "EPSG:4326") if moved else None
    lonlat = gdf.to_crs("EPSG:4326") if moved else gdf
    ellipsoid = lonlat.crs.ellipsoid
    geod = Geod(a=ellipsoid.semi_major_metre, rf=ellipsoid.inverse_flattening)
    return [
        float(geod.geometry_length(geom)) if geom is not None and not geom.is_empty else 0.0
        for geom in lonlat.geometry
    ], shift


def aggregate_weighted(
    input_path: str,
    output_path: str,
    value_column: str,
    weight_column: str,
    result_column: str = "weighted_value",
) -> dict[str, Any]:
    """A rate over a whole area: the ratio of totals, not the average of ratios.

    Averaging three unemployment rates treats a town of a thousand as equal to a
    city of a hundred thousand — 13.67% where the area's actual rate is 1.38%.
    The weighted value here is ``sum(value * weight) / sum(weight)``, which is
    what a rate means, and both totals are recorded so the number can be checked
    without the data.

    The unweighted mean is computed too and returned beside it: when the two
    differ materially, that difference is the whole finding, and hiding it would
    make this operation a black box that happens to be right.
    """
    import pandas as pd

    gdf = _read(input_path)
    for column in (value_column, weight_column):
        if column not in gdf.columns:
            available = [c for c in gdf.columns if c != gdf.geometry.name]
            raise ValueError(f"column {column!r} is not in {input_path}. Available: {available}")
    values = pd.to_numeric(gdf[value_column], errors="coerce")
    weights = pd.to_numeric(gdf[weight_column], errors="coerce")
    if weights.isna().any() or values.isna().any():
        raise ValueError(
            f"{value_column!r} and {weight_column!r} must both be numeric in every "
            "row: a weighted aggregate over missing values would silently weight "
            "them as zero"
        )
    total_weight = float(weights.sum())
    if total_weight == 0:
        raise ValueError(f"the weights in {weight_column!r} sum to zero")
    weighted = float((values * weights).sum() / total_weight)
    unweighted = float(values.mean())

    record = ProvenanceRecord(
        operation="aggregate_weighted",
        parameters={
            "value_column": value_column,
            "weight_column": weight_column,
            "result_column": result_column,
        },
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "an attribute aggregate; geometry is dissolved into one feature "
        "and coordinates are not transformed",
    }
    record.notes.append(
        f"weighted {weighted:.6g} = sum({value_column} * {weight_column}) / "
        f"sum({weight_column}) = {(values * weights).sum():.6g} / {total_weight:.6g}; "
        f"the unweighted mean of {value_column} is {unweighted:.6g}"
    )
    pre = verify.verify_loaded_inputs("aggregate_weighted", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        merged = gdf.dissolve(aggfunc="first", as_index=False)
        merged[result_column] = weighted
        merged[f"{weight_column}_total"] = total_weight
        _write(merged, output_path)

        difference = abs(weighted - unweighted)
        relative = difference / abs(weighted) * 100 if weighted else 0.0
        checks = [
            verify.Check(
                "x-mapsmith:weighting_changed_the_answer",
                relative < 1.0,
                f"weighted {weighted:.6g} against unweighted {unweighted:.6g} "
                f"({relative:.1f}% apart)",
                critical=False,
                hint=(
                    "The units being aggregated differ enough in weight that averaging "
                    "the values would have given a materially different answer. That is "
                    "not an error here — this operation weights — but it is the number "
                    "to quote if anyone compares this result with a plain mean."
                )
                if relative >= 1.0
                else None,
            )
        ]
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="aggregate_weighted",
        preconditions=pre,
        checks_fn=lambda: checks
        + verify.verify_vector_output(
            output_path, expect_crs=gdf.crs, expect_count=1, on_empty="fail"
        ),
    )
    return {
        "output": str(output_path),
        "weighted_value": weighted,
        "unweighted_mean": unweighted,
        "total_weight": total_weight,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def parse_coordinates(
    table_path: str,
    output_path: str,
    latitude_columns: str,
    longitude_columns: str,
    crs: str = "EPSG:4326",
) -> dict[str, Any]:
    """Build a point layer from a table of coordinates, DMS or decimal, stated.

    ``latitude_columns`` and ``longitude_columns`` name the columns that hold
    each coordinate, comma-separated: one column for decimal degrees, three for
    degrees/minutes/seconds, optionally a fourth for the hemisphere letter. The
    caller says which, because the file cannot: 41.5324 and 41°53'24" are both
    plausible latitudes for the same station and they are 40 km apart, so a
    reader that guesses will be wrong quietly.

    The conversion is 41 + 53/60 + 24/3600, recorded in the manifest with the
    column names it used. Values outside the valid range are refused rather
    than wrapped: a latitude of 91 is a parsing failure, not a place.
    """
    import pandas as pd

    def columns_of(spec: str, what: str) -> list[str]:
        names = [c.strip() for c in spec.split(",") if c.strip()]
        if len(names) not in (1, 3, 4):
            raise ValueError(
                f"{what} must name 1 column (decimal degrees), 3 (degrees, minutes, "
                f"seconds) or 4 (plus a hemisphere letter), got {len(names)}: {names}"
            )
        return names

    lat_cols = columns_of(latitude_columns, "latitude_columns")
    lon_cols = columns_of(longitude_columns, "longitude_columns")
    table = pd.read_csv(table_path)
    for name in lat_cols + lon_cols:
        if name not in table.columns:
            raise ValueError(
                f"column {name!r} is not in {table_path}. Available: {list(table.columns)}"
            )

    def to_degrees(row, names: list[str]) -> float:
        if len(names) == 1:
            return float(row[names[0]])
        degrees = abs(float(row[names[0]]))
        value = degrees + float(row[names[1]]) / 60 + float(row[names[2]]) / 3600
        sign = -1.0 if float(row[names[0]]) < 0 else 1.0
        if len(names) == 4:
            hemisphere = str(row[names[3]]).strip().upper()
            if hemisphere in ("S", "W"):
                sign = -1.0
            elif hemisphere not in ("N", "E"):
                raise ValueError(
                    f"hemisphere {row[names[3]]!r} is not one of N, S, E, W"
                )
        return sign * value

    latitudes = [to_degrees(row, lat_cols) for _, row in table.iterrows()]
    longitudes = [to_degrees(row, lon_cols) for _, row in table.iterrows()]
    for value, limit, what in ((latitudes, 90, "latitude"), (longitudes, 180, "longitude")):
        outside = [v for v in value if abs(v) > limit]
        if outside:
            raise ValueError(
                f"{what} values outside +/-{limit} after conversion: {outside[:3]}. "
                "That is a parsing failure rather than a place — check whether the "
                "columns really hold what the arguments say they do."
            )

    record = ProvenanceRecord(
        operation="parse_coordinates",
        parameters={
            "latitude_columns": lat_cols,
            "longitude_columns": lon_cols,
            "crs": crs,
            "interpretation": "decimal degrees" if len(lat_cols) == 1 else
            "degrees + minutes/60 + seconds/3600",
        },
        inputs=[InputRecord.from_path(table_path)],
        engine={"name": "pandas", "version": pd.__version__},
    )
    record.crs_decisions = {
        "analysis_crs": crs,
        "reason": f"coordinates read as {'decimal degrees' if len(lat_cols) == 1 else 'DMS'} "
        f"from the columns the caller named, and placed in {crs}",
    }
    points = gpd.GeoDataFrame(
        table.copy(),
        geometry=gpd.points_from_xy(longitudes, latitudes),
        crs=crs,
    )
    with verify.audit_on_failure(record, output_path, []):
        _write(points, output_path)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="parse_coordinates",
        preconditions=[],
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=crs,
            expect_count=len(table),
            expect_geometry={"Point"},
            on_empty="fail" if len(table) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(points),
        "latitude_range": [min(latitudes), max(latitudes)],
        "longitude_range": [min(longitudes), max(longitudes)],
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def point_on_surface(input_path: str, output_path: str) -> dict[str, Any]:
    """One point per feature, guaranteed to lie ON the feature.

    Different from :func:`centroid` and the difference is the whole reason this
    exists: the centroid of an L-shaped parcel, a crescent or a ring falls
    outside the shape, so locating a feature by its centroid can put it in the
    wrong district — with a district name as the answer, which carries no
    magnitude to sanity-check. Every output point is verified to be on its own
    input feature, which is a closed-form postcondition, not an opinion.
    """
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(
            gdf, f"{input_path} has no CRS."
        ))
    record = ProvenanceRecord(
        operation="point_on_surface",
        parameters={},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "a representative point is chosen inside the geometry; no "
        "reprojection is involved and none would change the answer",
    }
    pre = verify.verify_loaded_inputs("point_on_surface", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        points = gdf.copy()
        points[points.geometry.name] = gdf.geometry.representative_point()
        _write(points, output_path)

        inside = int(
            sum(
                point.intersects(polygon)
                for point, polygon in zip(points.geometry, gdf.geometry)
                if point is not None and polygon is not None
            )
        )
        checks = [
            verify.Check(
                "x-mapsmith:point_lies_on_its_feature",
                inside == len(gdf),
                f"{inside} of {len(gdf)} points lie on their own feature",
            )
        ]
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="point_on_surface",
        preconditions=pre,
        checks_fn=lambda: checks
        + verify.verify_vector_output(
            output_path,
            expect_crs=gdf.crs,
            expect_count=len(gdf),
            expect_geometry={"Point"},
            on_empty="fail" if len(gdf) else "ignore",
        ),
    )
    return {
        "output": str(output_path),
        "feature_count": len(points),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


HULL_KINDS = {"convex", "envelope", "oriented"}


def hull(input_path: str, output_path: str, kind: str = "convex") -> dict[str, Any]:
    """The convex hull, bounding box or minimum rotated rectangle of each feature.

    The three differ by how much they claim: an envelope is axis-aligned and can
    be several times the feature's area, an oriented rectangle follows it, a
    convex hull follows it more closely still. Which one was used goes in the
    manifest, because "the extent of the site" is a phrase that hides all three,
    and the ratio between the hull's area and the feature's is reported so the
    inflation is visible rather than implied.
    """
    if kind not in HULL_KINDS:
        raise ValueError(f"kind must be one of {sorted(HULL_KINDS)}, got {kind!r}")
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(gdf, f"{input_path} has no CRS."))
    record = ProvenanceRecord(
        operation="hull_layer",
        parameters={"kind": kind},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": f"the {kind} hull is computed in the layer's own CRS; a hull "
        "computed after reprojection is a different shape",
    }
    pre = verify.verify_loaded_inputs("hull_layer", input_path=gdf)
    original_area = float(gdf.geometry.area.sum())
    with verify.audit_on_failure(record, output_path, pre):
        hulled = gdf.copy()
        if kind == "convex":
            hulled[hulled.geometry.name] = gdf.geometry.convex_hull
        elif kind == "envelope":
            hulled[hulled.geometry.name] = gdf.geometry.envelope
        else:
            hulled[hulled.geometry.name] = gdf.geometry.minimum_rotated_rectangle()
        _write(hulled, output_path)
    hull_area = float(hulled.geometry.area.sum())
    if original_area > 0:
        record.notes.append(
            f"{kind} hull area {hull_area:.6g} against the features' own "
            f"{original_area:.6g} ({hull_area / original_area:.3f}x): the hull "
            "claims the difference, and any count or area over it includes ground "
            "the features do not occupy"
        )
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="hull_layer",
        preconditions=pre,
        checks_fn=lambda: [
            verify.Check(
                "x-mapsmith:hull_contains_its_feature",
                all(
                    h.buffer(1e-9).contains(g)
                    for h, g in zip(hulled.geometry, gdf.geometry)
                    if h is not None and g is not None and not g.is_empty
                ),
                "every hull contains the feature it was built from",
            )
        ]
        + verify.verify_vector_output(
            output_path, expect_crs=gdf.crs, expect_count=len(gdf), on_empty="ignore"
        ),
    )
    return {
        "output": str(output_path),
        "kind": kind,
        "feature_count": len(hulled),
        "hull_area": hull_area,
        "feature_area": original_area,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


VORONOI_BOUNDARIES = {"envelope", "convex_hull"}


def voronoi_polygons(
    input_path: str,
    output_path: str,
    boundary: str = "envelope",
    margin_fraction: float = 0.0,
) -> dict[str, Any]:
    """Thiessen polygons from a point layer, each carrying its own point's attributes.

    Two things about a Voronoi diagram are easy to get wrong and impossible to
    see afterwards, so both are handled here rather than left to the caller.

    First, the JOIN. Shapely returns the cells as a collection whose order is an
    implementation detail, not the input order: zip them with the points and
    every attribute lands on a neighbour's cell. The result is a map that is
    correct in shape, wrong in every value, and indistinguishable from the right
    one. This asks shapely for the ordered form AND then verifies the join
    geometrically -- each output cell must contain the point whose row it
    carries. A declaration that the order is right is not a check; containment
    is.

    Second, the BOUNDARY. The cells of the outermost points are infinite, so
    every real Voronoi layer is a clipped one, and the clip decides their areas.
    An area computed over these polygons is therefore partly a property of the
    boundary, not of the data: `boundary` says which one was used (the points'
    bounding box, or their convex hull), `margin_fraction` expands it, and both
    go in the manifest with a note saying the outer areas depend on them.
    """
    if boundary not in VORONOI_BOUNDARIES:
        raise ValueError(
            f"boundary must be one of {sorted(VORONOI_BOUNDARIES)}, got {boundary!r}"
        )
    if margin_fraction < 0:
        raise ValueError(f"margin_fraction cannot be negative, got {margin_fraction}")
    gdf = _read(input_path)
    if gdf.crs is None:
        raise ValueError(readers.no_crs_message(gdf, f"{input_path} has no CRS."))
    kinds = set(gdf.geom_type.dropna().unique())
    if kinds - {"Point"}:
        raise ValueError(
            f"voronoi_polygons needs a point layer; {input_path} holds {sorted(kinds)}. "
            "A Voronoi diagram is defined by points, and passing polygons would "
            "silently use their vertices, which is a different question."
        )
    points = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if len(points) < 2:
        raise ValueError(
            f"voronoi_polygons needs at least 2 distinct points, got {len(points)} "
            f"usable in {input_path}: with one point there is no boundary to draw."
        )
    # DISTINCT was in the message above and never checked, which is how a caller
    # got `GEOSException: Multiple input coordinates in cell at 0 0` — an
    # untranslated engine error, from an operation whose every other refusal
    # explains itself. Duplicate coordinates are ordinary in real point layers:
    # two sensors at one address, several readings snapped to the same GPS fix.
    # They are refused rather than de-duplicated because which of the duplicates
    # should own the cell is the caller's question, not ours: the attributes
    # differ even when the geometry does not.
    coordinates = [(geom.x, geom.y) for geom in points.geometry]
    if len(set(coordinates)) != len(coordinates):
        seen: set[tuple[float, float]] = set()
        repeated = sorted({c for c in coordinates if c in seen or seen.add(c)})
        raise ValueError(
            f"voronoi_polygons needs DISTINCT points and {input_path} repeats "
            f"{len(repeated)} coordinate(s), the first being {repeated[0]}. A "
            "Voronoi cell is the region closer to one point than to any other, "
            "which is undefined for two points in the same place — the engine "
            "raises 'Multiple input coordinates in cell'. Decide which row should "
            "own the cell (dissolve_layer on the coordinate, or drop the "
            "duplicates) rather than having that decided for you: the attributes "
            "usually differ even when the geometry does not."
        )

    record = ProvenanceRecord(
        operation="voronoi_polygons",
        parameters={"boundary": boundary, "margin_fraction": margin_fraction},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "the cells are built in the layer's own CRS; a Voronoi diagram "
        "computed after reprojection has different edges, because equidistance is "
        "a property of the plane it is measured in",
    }
    pre = verify.verify_loaded_inputs("voronoi_polygons", input_path=points)

    with verify.audit_on_failure(record, output_path, pre):
        minx, miny, maxx, maxy = points.total_bounds
        margin = margin_fraction * max(maxx - minx, maxy - miny)
        window = shapely.box(minx - margin, miny - margin, maxx + margin, maxy + margin)
        collection = shapely.MultiPoint(list(points.geometry))
        # ordered=True is what makes the positional join legal at all; without it
        # shapely is free to return the cells in any order.
        cells = shapely.voronoi_polygons(collection, extend_to=window, ordered=True)
        pieces = list(shapely.get_parts(cells))
        if boundary == "convex_hull":
            limit = shapely.convex_hull(collection)
            if margin:
                limit = limit.buffer(margin)
        else:
            limit = window
        # The positional join is legal because of `ordered=True` above; this is
        # the assertion that says so out loud. Slicing to `len(points)` would
        # have turned a short result into a pandas length error at the assignment
        # — before the `each_cell_holds_its_own_point` check that exists to catch
        # exactly this — so the count is compared first and named.
        if len(pieces) < len(points):
            raise ValueError(
                f"the engine returned {len(pieces)} cells for {len(points)} points, "
                "so the positional join between them is not valid. This should not "
                "happen with ordered=True; do not trust the output."
            )
        built = points.copy()
        built[built.geometry.name] = [
            shapely.intersection(cell, limit) for cell in pieces[: len(points)]
        ]
        _write(built, output_path)

    # Closed form: each cell must contain its own point. A wrong join produces
    # cells that are all valid polygons and all on the wrong row.
    own = sum(
        1
        for cell, point in zip(built.geometry, points.geometry)
        if cell is not None and not cell.is_empty and cell.covers(point)
    )
    outer_area = float(built.geometry.area.sum())
    record.notes.append(
        f"the outer cells are clipped to the points' {boundary}"
        + (f" expanded by {margin_fraction:g} of its larger side" if margin else "")
        + f"; total area {outer_area:.6g} is therefore partly a property of that "
        "boundary, not of the points"
    )
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="voronoi_polygons",
        preconditions=pre,
        checks_fn=lambda: [
            verify.Check(
                "x-mapsmith:each_cell_holds_its_own_point",
                own == len(points),
                f"{own}/{len(points)} cells contain the point whose attributes they "
                "carry",
                hint=(
                    "The cells and the rows are out of step, so every attribute is on "
                    "the wrong polygon. The output is geometrically valid and "
                    "semantically scrambled: do not use it."
                )
                if own != len(points)
                else None,
            )
        ]
        + verify.verify_vector_output(
            output_path, expect_crs=gdf.crs, expect_count=len(points)
        ),
    )
    return {
        "output": str(output_path),
        "boundary": boundary,
        "cell_count": len(built),
        "total_area": outer_area,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def validate_geometry(input_path: str, output_path: str) -> dict[str, Any]:
    """Report which geometries are invalid and why, repairing nothing.

    Every other operation here repairs what it can and records the repair. This
    one is the inspection step that comes first: it writes the layer back with a
    validity column and the GEOS reason per feature, so a caller can decide what
    to do about a self-intersection instead of discovering afterwards that
    something was rewritten. An invalid ring is not a crash — its area is the
    signed shoelace of a shape that means nothing — so knowing before measuring
    is the point.
    """
    from shapely.validation import explain_validity

    gdf = _read(input_path)
    record = ProvenanceRecord(
        operation="validate_geometry",
        parameters={},
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "validity is a property of the coordinates as stored; nothing is "
        "reprojected and nothing is repaired",
    }
    pre = verify.verify_loaded_inputs("validate_geometry", input_path=gdf)
    reasons = [
        "valid" if geom is None or geom.is_valid else explain_validity(geom)
        for geom in gdf.geometry
    ]
    invalid = sum(1 for r in reasons if r != "valid")
    checked = gdf.copy()
    checked["is_valid"] = [r == "valid" for r in reasons]
    checked["validity_reason"] = reasons
    with verify.audit_on_failure(record, output_path, pre):
        _write(checked, output_path)
        if invalid:
            record.notes.append(
                f"{invalid} of {len(gdf)} features are invalid; nothing was repaired "
                "here by design — the reasons are in the validity_reason column"
            )
        # The generic output checks are the wrong ones here: `geometry_valid` is
        # critical everywhere else, and this operation exists precisely to carry an
        # invalid geometry through to disk with its diagnosis attached. Failing on
        # that would make the inspection impossible to perform.
        output_checks = [
            verify.Check(
                "crs_present",
                _read_output_crs(output_path) is not None,
                verify.crs_label(gdf.crs),
            ),
            verify.Check(
                "feature_count_exact",
                len(checked) == len(gdf),
                f"{len(checked)} of {len(gdf)} features written",
            ),
            verify.Check(
                # This used to be `passed=True`, a constant -- a declaration wearing
                # a check's clothes, which raised the count of passing checks
                # without adding evidence. That is the defect this project measures
                # in other systems. The predicate now asserts what the operation
                # actually promises: every feature it calls invalid carries a reason
                # a reader can act on. It fails if GEOS ever returns an empty
                # explanation, which is the only way the promise could break.
                "x-mapsmith:invalid_geometry_explained",
                all(r.strip() for r in reasons),
                f"{invalid} of {len(gdf)} features invalid, every one with a reason "
                "in validity_reason; nothing was repaired",
            ),
        ]
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="validate_geometry",
        preconditions=pre,
        checks_fn=lambda: output_checks,
        # repairing here would defeat the operation
        repair=False,
    )
    return {
        "output": str(output_path),
        "feature_count": len(checked),
        "invalid_count": invalid,
        "reasons": sorted({r for r in reasons if r != "valid"}),
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def _refuse_naive_antimeridian(polygons: gpd.GeoDataFrame, polygons_path: str) -> None:
    """Refuse a polygon drawn across the 180th meridian as a single ring.

    The plane reads such a ring as its complement -- the rest of the planet.
    Measured on 2026-09-24 in five operations: `count_in_polygons` dropped the
    point inside the zone and counted one at 0 (a total equal to the truth),
    and `clip_layer`, `spatial_join` and `overlay_layers` each returned the
    feature on the far side of the world instead of the one inside. Not
    `measure_area`, whose geodesic area follows the edge the short way and is
    right. `nearest_join` returned an empty result. See
    `antimeridian.naive_crossings`. Refused rather than repaired: splitting the
    ring means deciding which side is meant, which is the caller's decision
    and the reason the file is ambiguous in the first place.
    """
    offending = antimeridian.naive_crossings(polygons)
    if offending:
        # Which seam, and so which advice: a layer written in 0..360 longitudes
        # ends at 0/360, and telling its author to split at 180 -- which it
        # did until 2026-09-25 -- sends them to the one meridian their ring
        # does not cross.
        _, high = antimeridian.layer_seam(polygons)
        seam = (
            "the 180th meridian"
            if high == 180.0
            else "the prime meridian (0/360: this layer is written in 0..360 longitudes)"
        )
        split = "180" if high == 180.0 else "0/360, or rewrite the layer in -180..180"
        raise ValueError(
            f"Refusing {polygons_path}: feature(s) {offending[:5]}"
            f"{' and more' if len(offending) > 5 else ''} cross {seam} "
            "as a single ring, which every planar library reads as the rest of the "
            "planet: whatever lies inside the zone is treated as outside it, and "
            "whatever lies on the far side of the world as inside. Split the ring at "
            f"{split} into two parts (RFC 7946 section 3.1.9), or use a projected CRS "
            "centred on the zone."
        )


#: How a point is placed in a polygon, and only these two. `contains` was the
#: third until 2026-09-24 and placed nothing, ever: `sjoin(points, polygons,
#: predicate)` evaluates `predicate(point, polygon)`, so it asked whether a POINT
#: contains a polygon -- false for any polygon with area. `count_in_polygons`
#: returned all zeros under it with `verified: True`, and one non-critical check
#: blamed the points for being "in no polygon". Even the intended reading, the
#: polygon containing the point, is exactly `within`: three names for two
#: behaviours, and the third broken. Found by the `geo-reviewer`.
COUNT_PREDICATES = {"intersects", "within"}


def require_polygons(frame, path: str, role: str) -> None:
    """Refuse a layer that should hold areas and does not.

    A line layer passed where polygons are expected is not an error anywhere
    downstream: points "fall in" a line when they lie on it, and a raster zone
    drawn along a line gets a count equal to its length. A plausible number
    from the wrong shape, with no warning -- so it is refused here, where the
    operation still knows what it expected (found by the geometry inventory,
    2026-09-29). A GeometryCollection whose parts are all polygons is a polygon,
    as `_uncovered_kinds` argues, and passes. Null and empty geometries are not
    judged here: this refuses the wrong shape, not the absence of one.
    """
    import numpy as np

    geoms = frame.geometry.to_numpy()
    present = geoms[~(shapely.is_missing(geoms) | shapely.is_empty(geoms))]
    # Vectorised: a loop over every geometry in Python was measurable on a
    # million-polygon layer (0.8.0 review). Only collections are broken apart.
    type_ids = shapely.get_type_id(present)
    collections = present[type_ids == 7]  # GeometryCollection
    if len(collections):
        type_ids = np.concatenate(
            [type_ids[type_ids != 7], shapely.get_type_id(shapely.get_parts(collections))]
        )
    names = {0: "Point", 1: "LineString", 2: "LinearRing", 3: "Polygon", 4: "MultiPoint",
             5: "MultiLineString", 6: "MultiPolygon", 7: "GeometryCollection"}
    kinds = {names.get(int(i), f"type {int(i)}") for i in np.unique(type_ids)}
    kinds -= {"Polygon", "MultiPolygon"}
    if kinds:
        raise ValueError(
            f"{path} holds {sorted(kinds)} geometries, and the {role} must be polygons: "
            "a line or a point encloses no area, so anything measured inside it would "
            "be a number about the wrong shape. Use a polygon layer."
        )


def count_in_polygons(
    points_path: str,
    polygons_path: str,
    output_path: str,
    predicate: str = "intersects",
    count_column: str = "point_count",
) -> dict[str, Any]:
    """Count points per polygon, with the boundary rule stated and its cost measured.

    ``intersects`` (the default) includes points on the boundary; ``within``
    excludes them. On a partition — districts that share edges — that is the
    difference between counting every point and dropping the ones on the seams,
    silently, because a join that returns fewer rows looks exactly like a join
    that had fewer to find. Both counts are computed: the total under the chosen
    predicate, and how many points fall in no polygon at all.
    """
    if predicate not in COUNT_PREDICATES:
        raise ValueError(
            f"predicate must be one of {sorted(COUNT_PREDICATES)}, got {predicate!r}"
        )
    points = _read(points_path)
    polygons = _read(polygons_path)
    require_polygons(polygons, polygons_path, "polygons")
    _refuse_naive_antimeridian(polygons, polygons_path)
    # Points only, and for the reason its sibling found first: a MultiPoint
    # straddling two polygons was counted in both, as two points, and a polygon
    # layer passed as the points was counted without a word. Measured on
    # 2026-09-24. Null and empty geometries are not refused -- they have no
    # position, which is a different fact from a wrong one, and they are
    # counted apart below.
    has_position = points.geometry.notna() & ~points.geometry.is_empty
    kinds = set(points.geometry[has_position].geom_type)
    if kinds - {"Point"}:
        raise ValueError(
            f"{points_path} holds {sorted(kinds - {'Point'})} geometries, and this "
            "operation counts points: a multi-part or areal feature can fall in "
            "several polygons at once and be counted in each. Explode multi-points "
            "into single points first (explode_layer)."
        )
    record = ProvenanceRecord(
        operation="count_in_polygons",
        parameters={"predicate": predicate, "count_column": count_column},
        inputs=[
            InputRecord.from_path(
                points_path, crs=verify.crs_label(points.crs), argument="points_path"
            ),
            InputRecord.from_path(
                polygons_path, crs=verify.crs_label(polygons.crs), argument="polygons_path"
            ),
        ],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs(
        "count_in_polygons", points_path=points, polygons_path=polygons
    )
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "count_in_polygons")
    original_points_crs = points.crs
    aligned = not verify.same_crs(original_points_crs, polygons.crs)
    if aligned:
        points = points.to_crs(polygons.crs)
    # After the move, and one call for both branches. This wrote the decision
    # before `to_crs` and then overwrote it by hand when nothing moved -- no
    # false record reached disk, because nothing is written between the two
    # lines, but it is the order six operations were fixed for on 2026-09-23.
    record.crs_decisions = alignment_decisions(
        polygons.crs,
        "the points are brought onto the polygons' CRS before counting"
        if aligned
        else "both layers share a CRS; nothing was reprojected",
        [("points_path", original_points_crs)] if aligned else [],
    )
    pre += verify.verify_input_pairs(
        "count_in_polygons", points_path=points, polygons_path=polygons
    )
    without_geometry = int((~has_position).sum())
    located = points.loc[has_position, [points.geometry.name]]
    with verify.audit_on_failure(record, output_path, pre):
        # Geometry only on both sides: the counts need nothing else, and the
        # join used to carry every column of both layers.
        joined = gpd.sjoin(
            located, polygons[[polygons.geometry.name]], predicate=predicate, how="inner"
        )
        counts = joined.groupby("index_right").size()
        result = polygons.copy()
        result[count_column] = [int(counts.get(i, 0)) for i in result.index]
        _write(result, output_path)

        matched = int(joined["index_right"].notna().sum())
        distinct_points = len(set(joined.index))
        # Over the points that HAVE a position. A null or empty geometry used to
        # land here as a point "in no polygon", and the hint sent the reader to
        # check the boundaries while the defect was in the points.
        unplaced = len(located) - distinct_points
        record.notes.append(
            f"{distinct_points} of {len(located)} located points fall in at least one "
            f"polygon under `{predicate}`; the counts sum to {matched}, which exceeds the "
            "number of points when polygons overlap or share edges"
            if matched != distinct_points
            else f"{distinct_points} of {len(located)} located points fall in a polygon "
            f"under `{predicate}`"
        )
        if without_geometry:
            record.notes.append(
                f"{without_geometry} of {len(points)} points have no geometry (null or "
                "empty), so they have no position and are in no count"
            )
        checks = [
            verify.Check(
                "x-mapsmith:every_point_placed",
                unplaced == 0,
                f"{unplaced} of {len(located)} located points fall in no polygon",
                critical=False,
                hint=None
                if unplaced == 0
                else (
                    f"Those points are outside every polygon under `{predicate}`. If the "
                    "polygons are meant to cover the whole study area, check the "
                    "boundaries: with `within`, a point exactly on a shared edge belongs "
                    "to neither side and disappears from the totals."
                ),
            )
        ]
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="count_in_polygons",
        preconditions=pre,
        checks_fn=lambda: checks
        + verify.verify_vector_output(
            output_path,
            expect_crs=polygons.crs,
            expect_count=len(polygons),
            on_empty="ignore",
        ),
    )
    return {
        "output": str(output_path),
        "predicate": predicate,
        "polygon_count": len(result),
        "points_placed": distinct_points,
        "points_unplaced": unplaced,
        "points_without_geometry": without_geometry,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def summarize_points_in_polygons(
    points_path: str,
    polygons_path: str,
    output_path: str,
    field: str,
    statistics: list[str] | None = None,
    predicate: str = "intersects",
) -> dict[str, Any]:
    """Statistics of one attribute of the points in each polygon: count_in_polygons' sibling.

    "Average pH by field block" was two operations -- a spatial join to stamp the
    block on every sample, then `summarize_field` grouped by it -- and a request
    that is two operations is, to somebody searching, an operation that does not
    exist. The arithmetic is `summarize_field`'s, so the vocabulary and the
    stdev rule are the same; the placement is `count_in_polygons'`, so the
    boundary rule is the same. Three decisions about the NUMBER, each recorded:

    * **A polygon with no points stays, with every statistic null.** The mean of
      nothing is not zero, and dropping the polygon makes the output look like
      coverage the samples never had.
    * **A point with no value is placed but not summarised.** `point_count` counts
      every point in the polygon and `<field>_count` the ones with a value, so a
      mean over three of five samples says so beside itself.
    * **The boundary rule is the caller's, and stated.** Under `intersects` a
      point on an edge two polygons share is counted in both; under `within`, in
      neither. Both are defensible and they give different totals, so the one
      used is in the record with how many points it double-counted or dropped.
    """
    from .summaries import STATISTICS, _describe

    if predicate not in COUNT_PREDICATES:
        raise ValueError(
            f"predicate must be one of {sorted(COUNT_PREDICATES)}, got {predicate!r}"
        )
    if statistics is not None and not statistics:
        raise ValueError(
            "statistics is an empty list, which asks for nothing. Leave it out for "
            f"the default (count, mean, min, max), or name some of {list(STATISTICS)}"
        )
    wanted = list(statistics) if statistics else ["count", "mean", "min", "max"]
    unknown = [name for name in wanted if name not in STATISTICS]
    if unknown:
        raise ValueError(f"unknown statistic(s) {unknown}. Available: {list(STATISTICS)}")
    if "count" not in wanted:
        # The count of summarised values is what makes every other statistic
        # readable: a mean without it cannot say how many values it is a mean of.
        wanted = ["count", *wanted]
    # Once each, in order: `["mean", "mean"]` made one column and a manifest
    # listing two, so two records of the same output differed by a duplicate.
    wanted = list(dict.fromkeys(wanted))

    points = _read(points_path)
    polygons = _read(polygons_path)
    _refuse_naive_antimeridian(polygons, polygons_path)
    if field not in points.columns or field == points.geometry.name:
        raise ValueError(
            f"{points_path} has no attribute {field!r}. Attributes: "
            f"{sorted(c for c in points.columns if c != points.geometry.name)}"
        )
    if field == "index_right":
        # The name the spatial join gives its own index column. Refused here
        # with a reason, instead of geopandas' message about a collision the
        # caller never chose.
        raise ValueError(
            "the attribute is called 'index_right', which the spatial join uses for "
            "its own column. Rename it first."
        )
    values = points[field]
    numeric = values.map(lambda v: isinstance(v, int | float) and not isinstance(v, bool))
    if not numeric[values.notna()].all():
        raise ValueError(
            f"attribute {field!r} holds values that are not numbers, so a sum or a mean "
            "of it would be meaningless. Summarise a numeric attribute, or count "
            "points per polygon with count_in_polygons."
        )
    require_polygons(polygons, polygons_path, "polygons")
    # Points only. A MultiPoint straddling two polygons carried its whole value
    # into both, and the note blamed overlap; a polygon layer passed as the
    # points was summarised without a word. Measured by the `geo-reviewer`.
    # Null and empty geometries are not refused -- they are counted and left
    # out, because they have no position rather than a wrong one.
    has_position = points.geometry.notna() & ~points.geometry.is_empty
    kinds = set(points.geometry[has_position].geom_type)
    if kinds - {"Point"}:
        raise ValueError(
            f"{points_path} holds {sorted(kinds - {'Point'})} geometries, and this "
            "operation places points: a multi-part or areal feature can fall in "
            "several polygons at once and carry its whole value into each. Explode "
            "multi-points into single points first (explode_layer), or summarise "
            "areas with an overlay."
        )
    new_columns = ["point_count", *(f"{field}_{name}" for name in wanted)]
    clashing = sorted(set(new_columns) & set(polygons.columns))
    if clashing:
        raise ValueError(
            f"the polygons already have column(s) {clashing}, which this operation "
            "would overwrite. Rename them first, so the output cannot silently "
            "replace a value that was in the input."
        )
    if str(output_path).lower().endswith(".shp"):
        # The Shapefile driver truncates names to ten characters, and here that
        # is not cosmetic: `population_count` came back as `population`, so a
        # count sat in a column that reads as the attribute it counts.
        too_long = [name for name in new_columns if len(name) > 10]
        if too_long:
            raise ValueError(
                f"a Shapefile cannot hold the column name(s) {too_long}: the driver cuts "
                "them to ten characters, and one of them would come back named like the "
                "attribute it summarises. Write GeoPackage or GeoParquet instead."
            )

    record = ProvenanceRecord(
        operation="summarize_points_in_polygons",
        parameters={"field": field, "statistics": wanted, "predicate": predicate},
        inputs=[
            InputRecord.from_path(
                points_path, crs=verify.crs_label(points.crs), argument="points_path"
            ),
            InputRecord.from_path(
                polygons_path, crs=verify.crs_label(polygons.crs), argument="polygons_path"
            ),
        ],
        engine=_engine_info(),
    )
    pre = verify.verify_loaded_inputs(
        "summarize_points_in_polygons", points_path=points, polygons_path=polygons
    )
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "summarize_points_in_polygons")
    original_points_crs = points.crs
    aligned = not verify.same_crs(original_points_crs, polygons.crs)
    if aligned:
        points = points.to_crs(polygons.crs)
    # Written after the move, not before it: on 2026-09-23 six operations were
    # found recording a reprojection before it happened.
    record.crs_decisions = alignment_decisions(
        polygons.crs,
        "the points are brought onto the polygons' CRS before they are placed"
        if aligned
        else "both layers share a CRS; nothing was reprojected",
        [("points_path", original_points_crs)] if aligned else [],
    )
    pre += verify.verify_input_pairs(
        "summarize_points_in_polygons", points_path=points, polygons_path=polygons
    )
    without_geometry = int((~has_position).sum())
    located = points.loc[has_position, [field, points.geometry.name]]

    with verify.audit_on_failure(record, output_path, pre):
        joined = gpd.sjoin(
            located, polygons[[polygons.geometry.name]], predicate=predicate, how="inner"
        )
        result = polygons.copy()
        placed_counts = joined.groupby("index_right").size()
        result["point_count"] = pd.Series(
            [int(placed_counts.get(i, 0)) for i in result.index],
            index=result.index, dtype="int64",
        )
        per_polygon = {
            index: _describe(group[field].dropna().to_numpy(dtype=float))
            for index, group in joined.groupby("index_right")
        }
        # Typed explicitly. A statistic that is null in every polygon -- stdev
        # over single samples, anything over an empty layer -- was written as
        # TEXT in GeoPackage and as a null type in GeoParquet, so the schema of
        # the output depended on the data and two runs of one flow disagreed.
        for name in wanted:
            column = [per_polygon.get(i, {"count": 0}).get(name) for i in result.index]
            if name == "count":
                result[f"{field}_{name}"] = pd.Series(
                    [int(v or 0) for v in column], index=result.index, dtype="int64"
                )
            else:
                result[f"{field}_{name}"] = pd.Series(
                    [float("nan") if v is None else float(v) for v in column],
                    index=result.index, dtype="float64",
                )
        _write(result, output_path)

        distinct = len(set(joined.index))
        unplaced = len(located) - distinct
        memberships = joined.index.value_counts()
        # Two different numbers, which the first version reported as one: how many
        # POINTS are counted in more than one polygon, and how many memberships
        # beyond one each. A point in three overlapping polygons is one point, and
        # the note said "1 of 1 points ...; 2 of them are counted in more than one".
        counted_twice = int((memberships > 1).sum())
        extra_memberships = len(joined) - distinct
        missing = int(points[field].isna().sum())
        # Of those, the ones that were PLACED -- only they are in a `point_count`.
        # The first version said all of them were, and a point with no value that
        # fell in no polygon is in no count at all: the `conformita-manifest`
        # review measured the note saying so beside a layer of zero polygons.
        missing_placed = int(points.loc[sorted(set(joined.index)), field].isna().sum())
        empty = int((result["point_count"] == 0).sum())
        record.notes.append(
            f"{distinct} of {len(located)} located points fall in a polygon under `{predicate}`"
            + (
                f"; {counted_twice} of them are counted in more than one polygon "
                f"({extra_memberships} extra memberships in all), because polygons overlap "
                "or a point sits on an edge they share"
                if counted_twice
                else ""
            )
        )
        if without_geometry:
            record.notes.append(
                f"{without_geometry} of {len(points)} points have no geometry (null or "
                "empty), so they have no position and are in no polygon and no statistic"
            )
        if missing_placed:
            record.notes.append(
                f"{missing_placed} of the {distinct} placed points have no value in "
                f"{field!r}: they are in `point_count` and in no statistic, so "
                f"`{field}_count` is smaller than `point_count` wherever one of them fell"
            )
        if missing - missing_placed:
            record.notes.append(
                f"{missing - missing_placed} more points with no value in {field!r} are "
                "not in any polygon, so they are in no count either"
            )
        if empty:
            record.notes.append(
                f"{empty} of {len(result)} polygons hold no point: they are kept, with "
                "`point_count` 0, the count of values 0 and every other statistic null, "
                "because the mean of no values is not zero"
            )
        checks = [
            verify.Check(
                "x-mapsmith:every_point_placed",
                unplaced == 0,
                f"{unplaced} of {len(located)} located points fall in no polygon",
                critical=False,
                hint=None if unplaced == 0 else (
                    f"Those points are outside every polygon under `{predicate}` and are "
                    "in no statistic. With `within`, a point exactly on a shared edge "
                    "belongs to neither side."
                ),
            ),
        ]

        def summary_intact() -> list[Any]:
            # A check on the NUMBER, read back from the file rather than trusted
            # from memory: the columns the manifest promises are there under their
            # declared names, the counts add up to the memberships the join found,
            # and no polygon summarises more values than it holds points.
            written = readers.read_vector_or_table(output_path)
            absent = [name for name in new_columns if name not in written.columns]
            problems = []
            if absent:
                problems.append(f"columns {absent} are not in the output")
            else:
                total = int(written["point_count"].sum())
                if total != len(joined):
                    problems.append(
                        f"point_count sums to {total}, the join found {len(joined)} memberships"
                    )
                if (written[f"{field}_count"] > written["point_count"]).any():
                    problems.append("some polygon summarises more values than it holds points")
            return [
                verify.Check(
                    "x-mapsmith:summary_columns_intact",
                    not problems,
                    "; ".join(problems) if problems else (
                        f"{len(new_columns)} columns present; point_count sums to "
                        f"{len(joined)}, and no {field}_count exceeds its point_count"
                    ),
                )
            ]

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="summarize_points_in_polygons",
        preconditions=pre,
        checks_fn=lambda: checks + summary_intact() + verify.verify_vector_output(
            output_path,
            expect_crs=polygons.crs,
            expect_count=len(polygons),
            on_empty="ignore",
        ),
    )
    return {
        "output": str(output_path),
        "field": field,
        "statistics": wanted,
        "predicate": predicate,
        "polygon_count": len(result),
        "polygons_without_points": empty,
        "points_placed": distinct,
        "points_unplaced": unplaced,
        "points_without_geometry": without_geometry,
        "points_counted_twice": counted_twice,
        "points_without_value": missing,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def _read_output_crs(path: str) -> Any:
    """The CRS of a dataset just written, for a check that must not re-validate it."""
    try:
        return readers.read_vector_or_table(path).crs
    except Exception:  # noqa: BLE001 — the check reports absence, it does not diagnose
        return None


#: What `select_features` can filter on, and nothing else. A general expression
#: language here would be `run_sql` with extra steps and a smaller vocabulary;
#: what is missing from the catalogue is the narrow, safe version of the two
#: questions MapSmith's own hints already tell callers to ask.
SELECT_BY = ("geometry_type", "field_equals", "field_in", "field_between")

#: The families a geometry type belongs to. `Multi` variants answer the same
#: question as their singular form — a MultiLineString is line-shaped — so
#: selecting "line" keeps both, which is what somebody asking for the pipes
#: means.
#: `LinearRing` is deliberately NOT in the line family: `linework` refuses it,
#: so selecting "line" and getting one back would produce a layer the very
#: operation this hint sends people to still rejects. It is reported by
#: `_uncovered_kinds` instead, which is the honest answer — we saw it and did
#: not take it.
GEOMETRY_FAMILIES = {
    family: set(kinds) for family, kinds in _catalog.GEOMETRY_FAMILIES.items()
}

#: Every type any family names. What a layer holds beyond this — a
#: GeometryCollection, a LinearRing, a null geometry — is dropped by a family
#: selection, and dropped silently unless something says so.
COVERED_KINDS = {kind for family in GEOMETRY_FAMILIES.values() for kind in family}


def _uncovered_kinds(gdf: Any) -> dict[str, int]:
    """Features a family selection cannot keep, counted by type.

    A GeometryCollection holding a polygon is a polygon to everybody except
    `geom_type`, which answers "GeometryCollection" and so falls outside every
    family. Dropping it is the silent undercount this operation's own docstring
    argues against when it explains why the Multi variants are kept — the same
    argument, applied to the case that is easier to miss. Null geometries go the
    same way: `geom_type` is None and `isin` is false.
    """
    counts: dict[str, int] = {}
    kinds = gdf.geom_type
    missing = int(kinds.isna().sum())
    if missing:
        counts["null geometry"] = missing
    for kind, count in kinds.dropna().value_counts().items():
        if str(kind) not in COVERED_KINDS:
            counts[str(kind)] = int(count)
    return counts


def _as_column_type(
    column: Any, value: Any, field: str
) -> tuple[Any, str | None]:
    """A filter value converted to the type of the column it is compared with,
    and a sentence saying so when it happened.

    The wire contract (`plans.models.ArgValue`) carries scalars as str, bool,
    int or float, and lists as strings only. So a filter on a numeric column
    receives "3" and compares it with 3, which matches nothing — and an empty
    output reads as a finding rather than as a type mismatch. Argleton has a
    family for exactly this shape.

    Conversion is attempted only when the types disagree, and the caller puts
    the returned sentence in the manifest — the second half of the tuple is
    there so that recording it is the easy path rather than a thing to
    remember. It REFUSES rather than falling back to a string comparison:
    "high" against an integer column is a question with no answer, and pretending
    otherwise produces the empty result this exists to prevent.
    """
    if value is None or not pd.api.types.is_numeric_dtype(column):
        return value, None
    if isinstance(value, bool) or not isinstance(value, str):
        return value, None

    text = value.strip()
    # `int` FIRST, and this is the whole reason the function is not one line.
    # `float("9007199254740993")` is 9007199254740992.0, so going through float
    # would hand back a filter for the row NEXT TO the one asked for — one
    # feature kept, every check green, and the manifest naming a number the
    # caller never typed. OSM ids, BIGINT keys and cadastral references all
    # live past 2^53.
    try:
        return int(text), _read_as(value, int(text), field)
    except ValueError:
        pass
    try:
        number = float(text)
    except ValueError:
        raise ValueError(
            f"{field} holds numbers and the filter value is {value!r}. Comparing "
            "them as text would match nothing and return an empty dataset, which "
            "reads as an answer. Pass a number."
        ) from None
    # `float()` accepts three strings that are not quantities. `nan` is the
    # dangerous one: it raises nothing and compares false against everything,
    # so `field == nan` is an empty output with a full manifest — and somebody
    # writing "nan" means "the rows with no value", which is a different
    # question this operation does not answer.
    if math.isnan(number):
        raise ValueError(
            f"{value!r} is not a value {field} can equal: a null is never equal to "
            "anything, including itself, so this filter would return an empty "
            "dataset and read as an answer. Missing values are not selectable with "
            "these four modes — use run_sql with IS NULL."
        )
    if math.isinf(number):
        raise ValueError(
            f"{value!r} is not a number {field} can hold. If the intent was 'no upper "
            "bound', leave `maximum` out instead."
        )
    if pd.api.types.is_integer_dtype(column) and not number.is_integer():
        raise ValueError(
            f"{field} holds whole numbers and the filter value is {value!r}. "
            "Comparing it would match nothing exactly, which returns an empty "
            "dataset that reads as an answer. Use field_between for a range."
        )
    number = int(number) if number.is_integer() else number
    return number, _read_as(value, number, field)


def _read_as(typed: Any, used: Any, field: str) -> str:
    return f"{typed!r} read as {used!r} for {field}"


def select_features(
    input_path: str,
    output_path: str,
    by: str,
    value: Any = None,
    field: str | None = None,
    values: list[Any] | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
) -> dict[str, Any]:
    """Keep the features a question is about, by geometry type or by attribute.

    MapSmith has been telling callers to do this for a while without offering
    it. The mixed-geometry check says *select the features the question is about
    — with run_sql, or by filtering the layer*; the line-only guard says
    *convert or select the line geometry first*. Both were pointing at an
    operation that did not exist, so the remedy was "write SQL" for something
    that is a filter.

    Four ways to ask, and deliberately no fifth:

    * ``by="geometry_type"`` with ``value="line"`` (or ``point``/``polygon``, or
      an exact type like ``"MultiPolygon"``). A family keeps its Multi variant
      too, because a MultiLineString is line-shaped and somebody asking for the
      pipes means both.
    * ``by="field_equals"`` with ``field`` and ``value``.
    * ``by="field_in"`` with ``field`` and ``values``.
    * ``by="field_between"`` with ``field`` and ``minimum``/``maximum``,
      inclusive at both ends.

    There is no expression language on purpose. That would be `run_sql` with
    extra steps and a smaller vocabulary, and it would need its own parser,
    its own injection story and its own way of going wrong. What was missing
    from the catalogue is the narrow version, which is also the one whose
    manifest can say exactly what it kept.

    **Selecting nothing is allowed and is reported, not refused.** An empty
    result is a legitimate answer to a filter — nothing matched — and the
    manifest carries a non-critical check saying so, because a zero that reads
    as a finding is the failure mode this suite has a whole family for.
    """
    if by not in SELECT_BY:
        raise ValueError(f"by must be one of {list(SELECT_BY)}, got {by!r}")

    gdf = _read(input_path)
    before = len(gdf)
    coercions: list[str] = []
    # Only a selection BY FAMILY can drop a type no family names; an
    # attribute filter keeps whatever geometry the matching rows carry.
    uncovered: dict[str, int] = {}

    if by == "geometry_type":
        if not isinstance(value, str):
            raise ValueError(
                "by='geometry_type' needs value: a family ('point', 'line', "
                "'polygon') or an exact type such as 'MultiPolygon'."
            )
        wanted = GEOMETRY_FAMILIES.get(value.lower())
        if wanted is None:
            present = sorted(gdf.geom_type.dropna().unique().tolist())
            if value not in present and value not in {
                t for family in GEOMETRY_FAMILIES.values() for t in family
            }:
                raise ValueError(
                    f"{value!r} is neither a geometry family "
                    f"({sorted(GEOMETRY_FAMILIES)}) nor a geometry type. This layer "
                    f"holds {present}."
                )
            wanted = {value}
        keep = gdf.geom_type.isin(sorted(wanted))
        description = f"geometry type in {sorted(wanted)}"
        uncovered = _uncovered_kinds(gdf)
    else:
        if not field:
            raise ValueError(f"by={by!r} needs a field name.")
        if field not in gdf.columns:
            raise ValueError(
                f"{input_path} has no column {field!r}. Columns: "
                f"{sorted(c for c in gdf.columns if c != gdf.geometry.name)}"
            )
        if by == "field_equals":
            if value is None:
                raise ValueError(
                    "by='field_equals' needs a value. Without one the comparison is "
                    "against null, which is false for every row: the output would be "
                    "an empty dataset with a complete manifest, and an empty dataset "
                    "reads as an answer."
                )
            value, said = _as_column_type(gdf[field], value, field)
            coercions += [said] if said else []
            keep = gdf[field] == value
            description = f"{field} == {value!r}"
        elif by == "field_in":
            if not values:
                raise ValueError("by='field_in' needs a non-empty `values` list.")
            converted = [_as_column_type(gdf[field], v, field) for v in values]
            values = [v for v, _ in converted]
            coercions += [said for _, said in converted if said]
            keep = gdf[field].isin(values)
            description = f"{field} in {values!r}"
        else:
            if minimum is None and maximum is None:
                raise ValueError(
                    "by='field_between' needs `minimum`, `maximum`, or both."
                )
            if not (
                pd.api.types.is_numeric_dtype(gdf[field])
                or pd.api.types.is_datetime64_any_dtype(gdf[field])
            ):
                raise ValueError(
                    f"field_between needs a field that can be ordered, and {field} "
                    f"holds {gdf[field].dtype}. Comparing it with a bound raises "
                    "inside pandas before MapSmith can write a manifest. Use "
                    "field_equals or field_in for this column."
                )
            minimum, said_min = _as_column_type(gdf[field], minimum, field)
            maximum, said_max = _as_column_type(gdf[field], maximum, field)
            coercions += [s for s in (said_min, said_max) if s]
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(
                    f"field_between was given minimum={minimum!r} above "
                    f"maximum={maximum!r}, so no value can satisfy it. The output "
                    "would be empty by construction, and the criterion written in "
                    "the manifest would read like a legitimate range."
                )
            keep = gdf[field].notna()
            if minimum is not None:
                keep &= gdf[field] >= minimum
            if maximum is not None:
                keep &= gdf[field] <= maximum
            description = (
                f"{field} between {minimum if minimum is not None else '-inf'} and "
                f"{maximum if maximum is not None else '+inf'}, inclusive"
            )

    out = gdf[keep].copy()
    kept = len(out)

    # The arguments the engine ran with, one key each. `criterion` is the same
    # thing in a sentence and stays because it reads well — but it cannot be the
    # only record: re-running from it would mean parsing English with a Python
    # repr inside, which is what the spec faults other formats for. The values
    # are the ones USED, after any coercion.
    arguments: dict[str, Any] = {"by": by, "criterion": description}
    if by == "geometry_type":
        arguments["value"] = value
    else:
        arguments["field"] = field
        if by == "field_equals":
            arguments["value"] = value
        elif by == "field_in":
            arguments["values"] = values
        else:
            arguments["minimum"], arguments["maximum"] = minimum, maximum
    # `features_before` is an observation of the input, like `source_band_count`
    # elsewhere. `features_kept` is an OUTCOME, and outcomes live in the
    # verification and in the notes, not among the parameters.
    arguments["features_before"] = before

    record = ProvenanceRecord(
        operation="select_features",
        parameters=arguments,
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "no CRS change: selecting rows does not touch coordinates",
    }
    if kept < before:
        record.notes.append(
            f"{before - kept} of {before} feature(s) were removed. This output is a "
            "SUBSET: any total computed from it is a total of what survived the "
            f"filter ({description}), not of the source."
        )
    if coercions:
        # Said out loud because it changes what was compared. A value arriving
        # as text against a numeric column is the ordinary case over the wire,
        # and silently comparing them as text would match nothing.
        record.notes.append(
            "filter value(s) converted to the column's type before comparing: "
            + "; ".join(coercions)
        )

    pre = verify.verify_loaded_inputs("select_features", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "select_features")
    with verify.audit_on_failure(record, output_path, pre):
        _write(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="select_features",
        preconditions=pre,
        # Both properties this operation needs are ones the spec already names,
        # so they use the core names and are computed FROM THE FILE. The first
        # version of this asked them under `x-mapsmith:` names and answered from
        # numbers already in memory — two checks that could not fail, one of
        # them critical, sitting in an audit trail as if they had.
        checks_fn=lambda: [
            *verify.verify_vector_output(
            output_path,
            expect_crs=verify.crs_label(gdf.crs),
            expect_count=kept,
            # A filter can only remove: more rows out than in means the
            # predicate was applied to the wrong frame, which is silent.
            max_count=before,
            # Nothing matched is a legitimate answer, and it is also what a
            # misspelled value looks like. Warn, and say which is which.
            on_empty="warn" if before else "ignore",
            empty_hint="an empty selection is a valid answer to a filter, and it is "
            f"also what a misspelled value or the wrong case looks like ({description}). "
            "describe_dataset lists the geometry types and the fields actually present.",
            ),
            # A family selection cannot keep what no family names, and dropping
            # it without a word is the undercount this operation was built to
            # prevent for the Multi variants. Not critical: the selection may be
            # exactly what was wanted. Said, so it cannot be assumed.
            verify.Check(
                "x-mapsmith:every_feature_was_considered",
                not uncovered,
                ", ".join(f"{count} {kind}" for kind, count in uncovered.items())
                if uncovered
                else "every feature belongs to a geometry family",
                critical=False,
                hint=None if not uncovered else
                "these features belong to no geometry family, so a selection by "
                "family drops them whatever family is asked for — a "
                "GeometryCollection holding a polygon is a polygon to everybody "
                "except its type name. Use explode first, or select by exact type.",
            ),
        ],
    )
    return {
        "output": str(output_path),
        "features_before": before,
        "features_kept": kept,
        "features_removed": before - kept,
        "criterion": description,
        "provenance": str(manifest),
        **extras,
    }


def extract_layer(input_path: str, layer: str, output_path: str) -> dict[str, Any]:
    """Take one layer out of a multi-layer container, into a dataset of its own.

    MapSmith refuses a container with more than one layer, because the format's
    default is the first layer and a manifest could not honestly say which data
    produced the numbers (issue #29, and Argleton trap 006 measured the old
    behaviour). The refusal has always told the caller what to do instead —
    *extract the layer you mean into its own dataset* — and then handed them a
    `run_sql` incantation, because there was no operation for it.

    This is that operation. It is the natural next step after
    `describe_dataset`, which lists a container's layers precisely so that one
    can be chosen.

    An unknown layer name is refused with the list of real ones rather than an
    empty result, because a typo and an empty layer are different problems and
    only one of them is the caller's data.

    A layer with no CRS is refused too, by the shared precondition, and that is
    worth knowing before it happens: it makes this a dead end for the one case
    somebody most wants it for — pulling a broken layer out of a container in
    order to fix it. The refusal is deliberate (invariant 4, and
    `convert_format` refuses the same input), but the way out today is `run_sql`
    rather than this operation. Recorded as a decision to take, not a gap to
    discover.
    """
    available = readers.gpkg_layers(input_path)
    # Both the refusals and the read itself live in `readers`, which is the one
    # place that decides how a vector dataset is opened. Writing them here would
    # be the seventh copy of that decision, and #28 was the first six.
    gdf = readers.read_named_layer(input_path, layer)

    record = ProvenanceRecord(
        operation="extract_layer",
        parameters={
            "layer": layer,
            "layers_in_container": sorted(available),
            "container_layer_count": len(available),
        },
        # `layer` on the INPUT record, which is the field the spec defines for
        # exactly this: an auditor holding a five-layer container and this
        # record has to be able to tell which layer produced the numbers.
        # Recording it only under `parameters` would be MapSmith answering in
        # its own vocabulary a question the format already asks.
        inputs=[
            InputRecord.from_path(
                input_path, crs=verify.crs_label(gdf.crs), layer=layer
            )
        ],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "no CRS change: the layer is copied out as it is stored",
    }
    record.notes.append(
        f"{layer!r} of {len(available)} layer(s) in the container "
        f"({', '.join(sorted(available))}). The others are untouched and are not in "
        "this output — which is the point: an operation downstream can now say "
        "which data produced its numbers."
    )

    pre = verify.verify_loaded_inputs("extract_layer", input_path=gdf)
    if verify.has_critical_failure(pre):
        record.add_verification(pre).finish().write_for(output_path)
        verify.enforce(pre, "extract_layer")
    with verify.audit_on_failure(record, output_path, pre):
        _write(gdf, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="extract_layer",
        preconditions=pre,
        # Extraction copies; it does not select, so the count in the file must
        # be the count in the container — which is what `expect_count` asks,
        # reading the output. There was an `x-mapsmith:the_layer_came_out_whole`
        # here that compared the input with a second read of the same input:
        # critical, unfailable, and its detail claimed a comparison it never
        # made. `feature_count_exact` was already doing the work.
        checks_fn=lambda: verify.verify_vector_output(
            output_path,
            expect_crs=verify.crs_label(gdf.crs),
            expect_count=len(gdf),
        ),
    )
    return {
        "output": str(output_path),
        "layer": layer,
        "features": len(gdf),
        "layers_in_container": sorted(available),
        "provenance": str(manifest),
        **extras,
    }
