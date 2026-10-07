"""Raster zonal statistics on the exactextract engine.

exactextract computes exact fractional pixel coverage (no all-in/all-out pixel
approximation) with bounded memory — 10-100x faster than rasterstats-class
implementations. Optional extra: ``pip install mapsmith[raster]``.

CRS discipline: zones are reprojected to the raster CRS before extraction
(mismatched CRS is the single most common silent error in GIS analysis), and
the decision is recorded in the provenance manifest. Output stays in the
raster CRS.
"""

from __future__ import annotations

import ast
import contextlib
import re
from typing import Any

import geopandas as gpd
import pandas as pd

from .. import datum, grid, readers, verify
from ..provenance import InputRecord, ProvenanceRecord, alignment_decisions, posix_path

VALID_STATS = {
    "count",
    "sum",
    "mean",
    "median",
    "min",
    "max",
    "stdev",
    "variance",
    "majority",
    "minority",
    "variety",
}

#: Statistics that need `weights_path`. Measured on exactextract 0.3.0 before
#: this was written: weighted_mean over a closed-form grid is exactly
#: sum(x*w)/sum(w), and ONE nodata weight inside a zone turns every weighted
#: statistic of that zone into NaN -- so MapSmith passes `default_weight=0`
#: (a cell with no weight does not count) and says which zones lost cells.
WEIGHTED_STATS = {
    "weighted_mean",
    "weighted_sum",
    "weighted_stdev",
    "weighted_variance",
    "weighted_frac",
}


def _require():
    try:
        import exactextract
        import rasterio
    except ImportError as exc:
        raise ImportError(
            "zonal_statistics requires the raster extra: pip install mapsmith[raster]"
        ) from exc
    return exactextract, rasterio


def _engine_info() -> dict[str, str]:
    from importlib.metadata import version

    return {"name": "exactextract", "version": version("exactextract")}


def _require_rasterio():
    try:
        import rasterio
    except ImportError as exc:
        raise ImportError(
            "raster inspection requires the raster extra: pip install mapsmith[raster]"
        ) from exc
    return rasterio


def describe(path: str) -> dict[str, Any]:
    """CRS, grid, bands, nodata and per-band statistics of a raster (read-only).

    Statistics are computed on the masked read, so nodata cells are excluded
    from min/max/mean and counted separately — most silent raster errors start
    with metadata nobody looked at, and nodata treated as elevation is the
    canonical one.
    """
    rasterio = _require_rasterio()
    with rasterio.open(path) as ds:
        bands = []
        for index in range(1, ds.count + 1):
            data = ds.read(index, masked=True)
            valid = int(data.count())
            bands.append({
                "band": index,
                "dtype": ds.dtypes[index - 1],
                "nodata": ds.nodatavals[index - 1],
                "valid_cells": valid,
                "nodata_cells": int(data.size - valid),
                "min": float(data.min()) if valid else None,
                "max": float(data.max()) if valid else None,
                "mean": float(data.mean()) if valid else None,
            })
        left, bottom, right, top = ds.bounds
        return {
            "path": str(path),
            "kind": "raster",
            "crs": str(ds.crs) if ds.crs else None,
            "width": ds.width,
            "height": ds.height,
            "band_count": ds.count,
            "resolution": {"x": abs(float(ds.res[0])), "y": abs(float(ds.res[1]))},
            "extent": {
                "minx": float(left),
                "miny": float(bottom),
                "maxx": float(right),
                "maxy": float(top),
            },
            "bands": bands,
            # Which georeferencing produced the numbers above, when the file is
            # not the only thing claiming to georeference itself. Describe is
            # the operation whose whole job is to say what a file IS, so a
            # second georeferencing is exactly the kind of thing it has to
            # mention — and it writes no manifest, so there is nowhere else it
            # could. Absent when there is only one source, because a key that
            # appears on every raster is a key nobody reads.
            **({"georeferencing": source} if (source := grid.georeferencing_source(path)) else {}),
        }


def zonal_statistics(
    raster_path: str,
    zones_path: str,
    output_path: str,
    stats: list[str] | None = None,
    weights_path: str | None = None,
) -> dict[str, Any]:
    """Statistics of a raster within each vector zone, one column per statistic.

    A multi-band raster gives one column per band and statistic, named by
    exactextract: `band_1_mean`, and with weights `band_1_weight_weighted_mean`.
    With `weights_path`, the weighted statistics too: the mean heat of a zone
    weighted by the population living in each cell, which is a different
    number from the plain mean whenever people are not spread evenly -- and
    used to take three operations and a division.
    """
    exactextract, rasterio = _require()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(raster_path, "zonal_statistics")
    if weights_path:
        grid.refuse_ambiguous_georeferencing(weights_path, "zonal_statistics")
    ops = stats or (
        ["count", "mean", "weighted_mean"] if weights_path else ["count", "mean", "min", "max"]
    )
    unknown = [s for s in ops if s not in VALID_STATS | WEIGHTED_STATS]
    if unknown:
        raise ValueError(
            f"Unknown statistics {unknown}. Valid: {sorted(VALID_STATS)}, and with "
            f"weights_path {sorted(WEIGHTED_STATS)} (note: 'stdev', not 'std')"
        )
    weighted = [s for s in ops if s in WEIGHTED_STATS]
    if weighted and not weights_path:
        raise ValueError(
            f"{weighted} need weights_path: a single-band raster of weights on the "
            "same grid as the values (same CRS and cells)."
        )
    if weights_path and not weighted:
        raise ValueError(
            "weights_path was given and no weighted statistic was asked for, so the "
            f"weights would change nothing. Add one of {sorted(WEIGHTED_STATS)} to "
            "stats, or leave weights_path out."
        )

    zones = readers.read_vector(zones_path)
    if zones.crs is None:
        raise ValueError(readers.no_crs_message(
            zones, f"{zones_path} has no CRS — cannot align zones to the raster."
        ))
    # Lines as zones ran without a word and returned a `count` equal to their
    # length; points raised a raw error from the engine (geometry inventory,
    # 2026-09-29). A zone is an area.
    from .vector import require_polygons

    require_polygons(zones, zones_path, "zones")

    with contextlib.ExitStack() as stack:
        ds = stack.enter_context(rasterio.open(raster_path))
        weights_ds = (
            stack.enter_context(rasterio.open(weights_path)) if weights_path else None
        )
        if weights_ds is not None:
            _refuse_unaligned_weights(ds, weights_ds, raster_path, weights_path)
        raster_crs = ds.crs
        parameters: dict[str, Any] = {"stats": ops, "bands": ds.count}
        if weights_ds is not None:
            # By name as well as by position in `inputs`: an auditor should not
            # have to know that the third input is the one that weighs.
            parameters["weights_path"] = posix_path(weights_path)
            parameters["weight_of_a_cell_with_no_weight"] = 0.0
        record = ProvenanceRecord(
            operation="zonal_statistics",
            parameters=parameters,
            inputs=[
                InputRecord.from_path(
                    raster_path, crs=verify.crs_label(raster_crs), argument="raster_path"
                ),
                InputRecord.from_path(
                    zones_path, crs=verify.crs_label(zones.crs), argument="zones_path"
                ),
                *(
                    [InputRecord.from_path(
                        weights_path, crs=verify.crs_label(weights_ds.crs), argument="weights_path"
                    )]
                    if weights_ds is not None
                    else []
                ),
            ],
            engine=_engine_info(),
        )
        aligned = raster_crs is not None and not verify.same_crs(zones.crs, raster_crs)
        record.crs_decisions.update(
            alignment_decisions(
                raster_crs,
                "zones brought to the raster CRS for exact pixel alignment; the "
                "output is kept in the raster CRS"
                if aligned
                else "zones and raster share the same CRS",
                [("zones_path", zones.crs)] if aligned else [],
            )
        )
        if aligned:
            zones = zones.to_crs(raster_crs)
        # exactextract takes the cell footprint from GDAL's geotransform, which
        # already centres each cell on its sample for a point-registered file
        # (RFC 33). Until 2026-09-25 the zones were moved half a cell here for a
        # Point raster, on the premise that the footprint came from the raw tie
        # point: it put every zone half a cell off (D-096). The registration is
        # recorded, because it says what a value represents.
        record.crs_decisions.update(grid.manifest_decisions(ds))
        if weights_ds is not None:
            _refuse_negative_weights(exactextract, weights_ds, zones, weights_path)
        if weights_ds is None:
            stats_df = exactextract.exact_extract(ds, zones, ops, output="pandas")
            weight_checks: list[verify.Check] = []
        else:
            # `op(default_weight=0)`: a cell with a value and no weight is left
            # out of the weighted statistics instead of turning the whole zone
            # into NaN. No alias: the column is already named `weighted_mean`
            # (measured), and an alias gave every band of a multi-band raster
            # the same name -- "Operation name is not unique", found by the
            # conformance sweep, whose grid has two bands.
            asked_ops = [f"{s}(default_weight=0)" if s in WEIGHTED_STATS else s for s in ops]
            stats_df = exactextract.exact_extract(
                ds, zones, asked_ops, weights=weights_ds, output="pandas"
            )
            record.notes.append(
                "a cell with a value and no weight counts with weight 0: it is left out "
                "of the weighted statistics and kept in the unweighted ones"
            )
            weight_checks = [
                _every_valued_cell_has_a_weight(exactextract, ds, weights_ds, zones)
            ]

    out = gpd.GeoDataFrame(
        pd.concat(
            [zones.reset_index(drop=True), stats_df.reset_index(drop=True)], axis=1
        ),
        geometry=zones.geometry.name,
        crs=zones.crs,
    )
    pre = verify.verify_loaded_inputs("zonal_statistics", zones_path=zones)
    with verify.audit_on_failure(record, output_path, pre):
        if str(output_path).endswith(".parquet"):
            out.to_parquet(output_path)
        else:
            out.to_file(output_path)

    # the zone geometries are carried through verbatim, so an invalid input
    # yields an invalid output: mechanical repair applies here
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="zonal_statistics",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=zones.crs,
                expect_count=len(zones),
            ),
            *weight_checks,
        ],
    )
    return {
        "output": str(output_path),
        "feature_count": len(out),
        "statistics": ops,
        "provenance": manifest,
        "verified": True,
        **extras,
    }


def _refuse_unaligned_weights(ds: Any, weights: Any, raster_path: str, weights_path: str) -> None:
    """Weights on exactly the value raster's grid, or a refusal saying how to get there.

    exactextract accepts a weights grid of another resolution and repeats each
    coarse cell whole in every fine cell it covers -- right for a density, and
    a weighted_sum inflated k-by-k times for a count -- and it never compares
    the two coordinate systems. Each of those is a plausible wrong number, so
    the grids must be the same one, and aligning them is the caller's step.

    The grid comparison is relative to the cell. `almost_equals` defaults to an
    ABSOLUTE 1e-5, and the 0.6.2 review measured it accepting a weights grid of
    1.8e-5 degree cells beside values at 9e-6: two grids, one answer.
    """
    problems = []
    if weights.count != 1:
        problems.append(f"it has {weights.count} bands and a weights raster needs one")
    if weights.crs is None:
        problems.append("it declares no CRS")
    elif not verify.same_crs(weights.crs, ds.crs):
        problems.append(
            f"it is in {verify.crs_label(weights.crs)} and the values in "
            f"{verify.crs_label(ds.crs)}"
        )
    cell = min(abs(ds.transform.a), abs(ds.transform.e)) or 1.0
    if (weights.height, weights.width) != (ds.height, ds.width) or not weights.transform.almost_equals(
        ds.transform, precision=cell * 1e-6
    ):
        problems.append(
            f"its grid is {weights.height}x{weights.width} at {tuple(weights.transform)[:6]}, "
            f"the values' {ds.height}x{ds.width} at {tuple(ds.transform)[:6]}"
        )
    # Not the registration: on the same geotransform a Point and an Area raster
    # have their samples in the same places, because GDAL has already folded
    # the difference into the transform (D-096). Refusing that pair refused two
    # grids that line up.
    if problems:
        raise ValueError(
            f"Refusing weights {weights_path} for {raster_path}: " + "; ".join(problems) + ". "
            "Weights must sit on the same grid as the values. Bring them there first -- "
            "reproject_raster or resample_raster onto the value raster's grid, choosing "
            "the resampling for what the weights are (a density averages, a count sums)."
        )


def _refuse_negative_weights(exactextract: Any, weights: Any, zones: Any, weights_path: str) -> None:
    """A negative weight inside a zone makes a weighted mean meaningless.

    Asked of exactextract, per zone, rather than of the whole band in memory:
    it streams by window, it treats a NaN as nodata -- the first version read
    the band with numpy, where one NaN made the minimum NaN, `nan < 0` was
    false, and a -5 weight went through to a plausible wrong mean (measured by
    the 0.6.2 review) -- and a negative weight outside every zone changes no
    number, so it is no reason to refuse.
    """
    import numpy as np

    lowest = np.asarray(
        exactextract.exact_extract(weights, zones, ["min"], output="pandas")["min"], dtype=float
    )
    negative = [int(i) for i in np.flatnonzero(lowest < 0)]
    if negative:
        raise ValueError(
            f"Refusing weights {weights_path}: rows {negative[:10]} of the zones layer (from 0) "
            "contain negative weights "
            f"(smallest {float(np.nanmin(lowest)):g}), and a negative weight makes a weighted "
            "mean meaningless. Clip or rescale the weights first."
        )


def _every_valued_cell_has_a_weight(exactextract: Any, ds: Any, weights: Any, zones: Any) -> Any:
    """Name the zones where a cell had a value and no weight.

    Those cells count with weight 0, which is the only choice that leaves a
    number: exactextract's own default turns the zone's weighted statistics
    into NaN. So the answer is still defensible -- and the record says where
    it rests on fewer cells than the unweighted one.

    That same default is the detector: `weighted_sum(default_weight=nan)` is
    NaN exactly in the zones where a cell has a value and no weight (measured),
    with exactextract's own reading of nodata and NaN on BOTH rasters and by
    window. The first version built the mask with numpy, which did not see a
    NaN as nodata: it passed a zone that had lost a cell and failed one that
    had not (both measured by the 0.6.2 review), and held the grid in memory
    five times over. On a multi-band raster a zone counts if any band lost one.
    """
    import numpy as np

    probe = exactextract.exact_extract(
        ds, zones, ["weighted_sum(default_weight=nan)"], weights=weights, output="pandas"
    )
    lost = np.isnan(probe.to_numpy(dtype=float)).any(axis=1)
    affected = [int(i) for i in np.flatnonzero(lost)]
    return verify.Check(
        "x-mapsmith:every_valued_cell_has_a_weight",
        not affected,
        f"{len(affected)} of {len(zones)} zones have cells with a value and no weight, "
        f"left out of the weighted statistics: rows {affected[:10]} of the zones layer, "
        "counted from 0"
        + (" and more" if len(affected) > 10 else "")
        if affected
        else "every cell with a value inside a zone also has a weight",
        critical=False,
        hint=None
        if not affected
        else "The weighted statistics of those zones rest on fewer cells than the "
        "unweighted ones. If a missing weight means zero (nobody lives there), the "
        "number is right; if it means unknown, fill the weights before trusting it.",
    )


# Resampling methods that AVERAGE their neighbours. On a categorical raster
# these invent class codes that were never in the data, which is the whole
# reason this operation refuses to have a default.
# Measured against the installed rasterio, not assumed: read() accepts nine of
# the fifteen Resampling members and raises ResamplingAlgorithmError for
# min/max/med/q1/q3/sum, which are warp-only. rasterio has three different
# valid sets (read, warp, overviews) and the intersection is what matters here.
INTERPOLATING_RESAMPLING = {
    "bilinear", "cubic", "cubic_spline", "lanczos", "average", "rms", "gauss",
}
# These pick an existing value instead of deriving one, so a class code
# survives them. On the read path that is exactly two methods.
CATEGORICAL_RESAMPLING = {"nearest", "mode"}
WARP_ONLY_RESAMPLING = {"min", "max", "med", "q1", "q3", "sum"}
# Beyond this many distinct values a raster is treated as continuous and the
# new-code check is skipped: the point is to catch class codes, not elevations.
_CATEGORICAL_MAX_CLASSES = 64


def resample(
    input_path: str,
    output_path: str,
    resolution: float,
    resampling: str,
) -> dict[str, Any]:
    """Resample a raster to a target cell size. The method is REQUIRED, by design.

    Every raster library defaults to nearest neighbour, and the caller who
    wanted a smooth surface silently gets a blocky one; the caller who reaches
    for bilinear on land-cover codes silently gets classes that do not exist.
    Neither failure raises anything, so the choice is the caller's to state.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "resample_raster")
    import math

    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject as warp

    if resolution <= 0:
        raise ValueError(f"resolution must be positive, got {resolution}")
    valid = INTERPOLATING_RESAMPLING | CATEGORICAL_RESAMPLING
    if resampling not in valid:
        warp_only = (
            f" '{resampling}' exists in rasterio's Resampling enum but is valid only "
            "for warping, not for the read path this operation uses."
            if resampling in WARP_ONLY_RESAMPLING
            else ""
        )
        raise ValueError(
            f"resampling must be one of {sorted(valid)}, got {resampling!r}.{warp_only} "
            "There is no default on purpose: interpolating methods (bilinear, cubic, "
            "average) derive values between the ones present, which is right for a "
            "continuous surface and wrong for class codes — use nearest or mode there."
        )
    method = getattr(Resampling, resampling)

    with rasterio.open(input_path) as src:
        if src.crs is None:
            raise ValueError(
                f"{input_path} declares no CRS, so a resolution in its units cannot be "
                "interpreted. Assign a CRS first."
            )
        left, bottom, right, top = src.bounds
        # THE CELL SIZE IS THE REQUEST, and the extent gives way to it.
        #
        # Until 0.3.0 this kept the extent and derived the cell size from it —
        # `round(extent / resolution)` cells across the same ground — so asking
        # for 30 m on a 100 m extent delivered 33.333 m, the manifest recorded
        # `"resolution": 30.0`, and a check named `shape_matches_resolution`
        # passed because it compared the shape on disk to the shape we had
        # computed rather than to the resolution in its own name. An 11% cell
        # error is a 23% area error for anyone multiplying by cell size, which
        # is the ordinary downstream use. Well-formed, confidently reported and
        # wrong: the exact failure this project measures in other systems.
        #
        # So the grid is anchored at the top-left corner with cells of exactly
        # `resolution`, and the extent grows outward to the next whole cell —
        # what `gdalwarp -tr` does, and what a caller means by "resample to 30 m".
        # `ceil` with a tolerance, so an extent that already divides evenly does
        # not gain a phantom column to floating-point noise.
        width = max(1, math.ceil((right - left) / resolution - _GRID_EPSILON))
        height = max(1, math.ceil((top - bottom) / resolution - _GRID_EPSILON))
        target_transform = from_origin(left, top, resolution, resolution)
        source_values, categorical = _distinct_values(src)
        record = ProvenanceRecord(
            operation="resample_raster",
            parameters={
                "resolution": resolution,
                "resampling": resampling,
                "target_shape": [height, width],
            },
            inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(src.crs))],
            engine={"name": "rasterio", "version": rasterio.__version__},
        )
        grown = (
            left + width * resolution > right + _GRID_EPSILON
            or top - height * resolution < bottom - _GRID_EPSILON
        )
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(src.crs),
            "reason": "resampling changes the grid, not the coordinate system; "
            "the target resolution is read in the raster's own CRS units",
        }
        if grown:
            record.notes.append(
                f"the extent does not divide evenly by {resolution}, so the output "
                f"covers slightly more ground than the input: the cell size is the "
                f"request and the grid grew outward to the next whole cell, rather "
                f"than the cell size bending to fit the extent"
            )
        profile = src.profile.copy()
        profile.update(width=width, height=height, transform=target_transform)
        # The source's tiling describes the source's grid: carried onto a
        # smaller output GDAL complains and drops it. Let the driver choose.
        for key in ("blockxsize", "blockysize", "tiled"):
            profile.pop(key, None)

        # Measured on 2026-09-25: a warp that raised on the second band left a raster
        # on disk and no manifest -- the defect fixed in `reproject_raster` two days
        # earlier, in its twin. The write and the reading-back of the output are both
        # inside the net, here and in every writer in this module.
        with (
            verify.audit_on_failure(record, output_path, []),
            rasterio.open(output_path, "w", **profile) as dst,
        ):
            grid.preserve(src, dst)
            for band in range(1, src.count + 1):
                warp(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dst, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=target_transform,
                    dst_crs=src.crs,
                    resampling=method,
                )

    checks: list[verify.Check] = []
    with verify.audit_on_failure(record, output_path, []), rasterio.open(output_path) as out:
        checks.append(
            verify.Check(
                "x-mapsmith:shape_matches_resolution",
                (out.height, out.width) == (height, width),
                f"expected {height}x{width}, got {out.height}x{out.width}",
            )
        )
        checks.append(_cell_size_check(out, resolution))
        checks.append(
            verify.Check(
                "crs_matches",
                verify.same_crs(out.crs, record.inputs[0].crs),
                f"{verify.crs_label(out.crs)}",
            )
        )
        result_values, _ = _distinct_values(out)

    # The check that looks at the VALUES, not at whether the run finished: an
    # interpolating method on a categorical raster produces codes that were
    # never in the input, and nothing else in the stack will say so.
    invented: list[float] = []
    if categorical and resampling in INTERPOLATING_RESAMPLING and result_values is not None:
        invented = sorted(result_values - source_values)
        checks.append(
            verify.Check(
                "x-mapsmith:no_invented_class_codes",
                not invented,
                f"{resampling} introduced codes absent from the input: {invented}"
                if invented
                else "output codes are a subset of the input codes",
                critical=False,
                hint=(
                    "This raster looks categorical (integer, few distinct values) and was "
                    f"resampled with '{resampling}', which averages neighbours. The codes "
                    f"{invented} exist in the result and not in the source: if they mean "
                    "something in your legend, every downstream count and area for those "
                    "classes is fabricated. Use nearest or mode for class codes."
                )
                if invented
                else None,
            )
        )

    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "resample_raster")
    result = {
        "output": str(output_path),
        "resolution": resolution,
        "resampling": resampling,
        "shape": [height, width],
        "provenance": str(manifest),
        "verified": True,
    }
    hinted = verify.advisories(checks)
    if hinted:
        result["warnings"] = hinted
    if invented:
        result["invented_values"] = invented
    return result


#: A grid whose extent already divides evenly by the requested cell size must
#: not gain a phantom row to floating-point noise, and one that misses by a
#: micron must not lose a real one. Relative, because extents run from metres to
#: millions of metres.
_GRID_EPSILON = 1e-9


def _datum_shift_check(shift: dict[str, Any]) -> Any:
    """Say whether a datum shift was actually applied, in the manifest.

    `crs_matches` passes whether or not one was: the output really is in the CRS
    that was asked for. Those two facts together are Argleton trap 021, which
    this repository measures in other people's software and, until 2026-09-03,
    reproduced on its own raster side.
    """
    if not shift["is_ballpark"]:
        return verify.Check(
            "x-mapsmith:datum_shift_applied",
            True,
            f"{shift['pipeline'] or 'transformation'} - stated accuracy "
            f"{shift['accuracy_m']} m",
            critical=False,
        )
    better = shift.get("better_available_m")
    return verify.Check(
        "x-mapsmith:datum_shift_applied",
        # Not critical: a ballpark is legitimate when the caller knows the two
        # datums coincide. Refusing would break those callers; saying nothing
        # is what this fixes.
        False,
        "PROJ applied no datum shift between these two CRSs",
        critical=False,
        hint=(
            "The coordinates were carried across as if the two datums coincided, so "
            "the result can be tens of metres from the true position while every "
            "other check passes. "
            + (
                f"A published operation with a stated accuracy of {better} m exists "
                "for this pair but its grid is not installed here: install it "
                "(`projinfo -s <source> -t <target>` names the file) and run again."
                if better is not None
                else "PROJ has no published operation for this pair at all, so this "
                "is the best that can be done - treat the result as unshifted."
            )
        ),
    )


def _cell_size_check(dataset: Any, requested: float) -> Any:
    """Assert the delivered cell size IS the requested one.

    The check this sits beside compares the shape on disk to the shape we
    computed, which is a real check of a different thing — and its name,
    `shape_matches_resolution`, promised this one. For half a release it passed
    on rasters whose cells were 11% larger than the caller asked for. A check
    whose name asserts a property it does not test is worse than no check: it
    is a green tick in the manifest saying the number is right.
    """
    x = abs(dataset.transform.a)
    y = abs(dataset.transform.e)
    tolerance = requested * 1e-6
    return verify.Check(
        "x-mapsmith:cell_size_is_what_was_asked",
        abs(x - requested) <= tolerance and abs(y - requested) <= tolerance,
        f"asked for {requested}, delivered {x} x {y}",
    )


def _distinct_values(dataset: Any) -> tuple[set[float] | None, bool]:
    """The distinct values of band 1, and whether the raster looks categorical.

    Categorical here means integer dtype with few distinct values — a heuristic,
    stated as such: it decides whether to RUN a non-critical check, never
    whether to alter data.
    """
    import numpy as np

    if not np.issubdtype(np.dtype(dataset.dtypes[0]), np.integer):
        return None, False
    band = dataset.read(1, masked=True)
    values = {float(v) for v in np.unique(band.compressed())}
    return (values, True) if len(values) <= _CATEGORICAL_MAX_CLASSES else (values, False)


def clip_raster(
    raster_path: str,
    mask_path: str,
    output_path: str,
    all_touched: bool = False,
) -> dict[str, Any]:
    """Clip a raster to the area of a vector mask, with the CRS handled openly.

    ``rasterio.mask`` never looks at a CRS — its documentation states the
    precondition and the code does not enforce it. Three things then happen,
    and only the first is loud: disjoint bounds raise or warn; bounds that
    overlap *numerically* while the CRS differ (metres against US survey feet,
    UTM 32N against 33N) clip a plausible wrong piece of the raster in total
    silence; degrees against metres usually yields an all-nodata output with a
    warning nobody reads. So the mask is reprojected here, deliberately, and
    the decision is recorded.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(raster_path, "clip_raster")
    from rasterio.mask import mask as rio_mask

    frame = readers.read_vector(mask_path)
    with rasterio.open(raster_path) as src:
        if src.crs is None:
            raise ValueError(
                f"{raster_path} declares no CRS, so a vector mask cannot be placed "
                "on it. Assign a CRS first."
            )
        record = ProvenanceRecord(
            operation="clip_raster",
            parameters={"all_touched": all_touched},
            inputs=[
                InputRecord.from_path(
                    raster_path, crs=verify.crs_label(src.crs), argument="raster_path"
                ),
                InputRecord.from_path(
                    mask_path, crs=verify.crs_label(frame.crs), argument="mask_path"
                ),
            ],
            engine={"name": "rasterio", "version": rasterio.__version__},
        )
        pre = verify.verify_loaded_inputs("clip_raster", mask_path=frame)
        if verify.has_critical_failure(pre):
            record.add_verification(pre).finish().write_for(output_path)
            verify.enforce(pre, "clip_raster")
        aligned = not verify.same_crs(frame.crs, src.crs)
        record.crs_decisions = alignment_decisions(
            src.crs,
            "the mask is brought to the raster CRS before clipping; rasterio.mask "
            "does not check CRS and would have clipped the wrong area without "
            "saying so"
            if aligned
            else "mask and raster already share a CRS; nothing was reprojected",
            [("mask_path", frame.crs)] if aligned else [],
        )
        if aligned:
            frame = frame.to_crs(src.crs)
        # nodata: rasterio.mask falls back to 0 when the raster declares none,
        # and 0 is a valid elevation, reflectance and temperature. Refuse to
        # let that be implicit.
        nodata = src.nodata
        if nodata is None:
            record.notes.append(
                "the source raster declares no nodata value, so the area outside the "
                "mask is filled with 0 — a legal value in most bands. Consider "
                "declaring nodata on the source before clipping"
            )
        with verify.audit_on_failure(record, output_path, pre):
            data, transform = rio_mask(
                src, list(frame.geometry), crop=True, all_touched=all_touched
            )
            profile = src.profile.copy()
            profile.update(
                height=data.shape[1], width=data.shape[2], transform=transform
            )
            for key in ("blockxsize", "blockysize", "tiled"):
                profile.pop(key, None)
            with rasterio.open(output_path, "w", **profile) as dst:
                grid.preserve(src, dst)
                dst.write(data)
        source_shape = (src.height, src.width)

    checks: list[verify.Check] = []
    with verify.audit_on_failure(record, output_path, pre), rasterio.open(output_path) as out:
        checks.append(
            verify.Check(
                "crs_matches",
                verify.same_crs(out.crs, record.inputs[0].crs),
                verify.crs_label(out.crs),
            )
        )
        # A clip can only shrink the grid. Growing means the mask was placed
        # somewhere the raster is not, which is the CRS failure this operation
        # exists to prevent.
        checks.append(
            verify.Check(
                "x-mapsmith:not_larger_than_source",
                out.height <= source_shape[0] and out.width <= source_shape[1],
                f"{out.height}x{out.width} from {source_shape[0]}x{source_shape[1]}",
            )
        )
        band = out.read(1, masked=True)
        valid = int(band.count())
        checks.append(
            verify.Check(
                "result_not_empty",
                valid > 0,
                f"{valid} cells with data",
                critical=False,
                hint=None
                if valid
                else "The clip produced a raster with no data at all. The mask and the "
                "raster overlap in extent but not where the data is — or the mask "
                "covers only nodata cells. Check the two extents before trusting it.",
            )
        )
        result_shape = [out.height, out.width]

    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "clip_raster")
    result = {
        "output": str(output_path),
        "shape": result_shape,
        "valid_cells": valid,
        "provenance": str(manifest),
        "verified": True,
    }
    advisories = verify.advisories(checks)
    if advisories:
        result["warnings"] = advisories
    return result


def reclassify(
    input_path: str,
    output_path: str,
    intervals: list[str],
) -> dict[str, Any]:
    """Reclassify raster values into new codes, with the ranges stated as text.

    Each interval is ``"low:high:new"``, half-open — ``low <= value < high`` —
    so ``["0:100:1", "100:200:2"]`` maps everything under 100 to 1 and
    everything from 100 up to (not including) 200 to 2. Half-open is the only
    convention that tiles the number line without overlap, and the off-by-one
    at the boundary is the classic silent error of this operation: a cell of
    exactly 100 belongs to the second class, and this docstring is the contract.

    Ranges are checked for overlap before anything runs, and cells that fall in
    no interval become nodata and are counted in the manifest — the alternative,
    leaving them at their original value, mixes old codes with new ones in the
    same band and is unreadable afterwards.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "reclassify_raster")
    import numpy as np

    parsed: list[tuple[float, float, float]] = []
    for entry in intervals:
        parts = str(entry).split(":")
        if len(parts) != 3:
            raise ValueError(
                f"interval {entry!r} must be 'low:high:new', e.g. '0:100:1' "
                "(low inclusive, high exclusive)"
            )
        try:
            low, high, new = (float(p) for p in parts)
        except ValueError as exc:
            raise ValueError(f"interval {entry!r} has a non-numeric bound") from exc
        if not low < high:
            raise ValueError(f"interval {entry!r}: low must be less than high")
        parsed.append((low, high, new))
    for i, (low_a, high_a, _) in enumerate(parsed):
        for low_b, high_b, _ in parsed[i + 1:]:
            if low_a < high_b and low_b < high_a:
                raise ValueError(
                    f"intervals [{low_a}, {high_a}) and [{low_b}, {high_b}) overlap: "
                    "a value in both would take whichever class was listed first, "
                    "which is a coin toss the caller should not have to know about"
                )

    with rasterio.open(input_path) as src:
        # Taken while the input is open: a closed dataset used to answer
        # "area" without raising, and this writer shipped it.
        source_registration = grid.registration(src)
        record = ProvenanceRecord(
            operation="reclassify_raster",
            parameters={
                "intervals": [f"{low}:{high}:{new}" for low, high, new in parsed],
                "bounds": "low inclusive, high exclusive",
            },
            inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(src.crs))],
            engine={"name": "rasterio", "version": rasterio.__version__},
        )
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(src.crs),
            "reason": "reclassification changes values, not geometry or CRS",
        }
        band = src.read(1, masked=True)
        nodata_out = -9999.0
        # Plain arrays on purpose: comparisons on a masked array return masked
        # booleans, and indexing with those does not mean what it looks like.
        # The validity mask is carried separately and applied explicitly.
        valid = ~np.ma.getmaskarray(band)
        values = np.ma.getdata(band).astype("float64")
        result_band = np.full(band.shape, nodata_out, dtype="float32")
        assigned = np.zeros(band.shape, dtype=bool)
        for low, high, new in parsed:
            selected = valid & (values >= low) & (values < high)
            result_band[selected] = new
            assigned |= selected
        unmapped = int(np.sum(valid & ~assigned))
        profile = src.profile.copy()
        profile.update(dtype="float32", nodata=nodata_out, count=1)
        for key in ("blockxsize", "blockysize", "tiled"):
            profile.pop(key, None)
        source_shape = (src.height, src.width)

    if unmapped:
        record.notes.append(
            f"{unmapped} cells fell outside every interval and became nodata "
            f"({nodata_out}); they are not left at their original values, which "
            "would mix old codes with new ones in one band"
        )
    with verify.audit_on_failure(record, output_path, []):
        with rasterio.open(output_path, "w", **profile) as dst:
            grid.preserve(source_registration, dst)
            dst.write(result_band, 1)

        checks: list[verify.Check] = []
        with rasterio.open(output_path) as out:
            checks.append(
                verify.Check(
                    "shape_preserved",
                    (out.height, out.width) == source_shape,
                    f"{out.height}x{out.width}",
                )
            )
            checks.append(
                verify.Check(
                    "crs_matches",
                    verify.same_crs(out.crs, record.inputs[0].crs),
                    verify.crs_label(out.crs),
                )
            )
            written = out.read(1, masked=True)
            produced = {float(v) for v in np.unique(written.compressed())}
            declared = {new for _, _, new in parsed}
            # Closed form: every value in the output must be one of the codes the
            # caller asked for. Anything else means the mapping did not do what the
            # intervals say, and a reclassified raster nobody can trust is worse
            # than one that failed.
            checks.append(
                verify.Check(
                    "x-mapsmith:values_are_declared_codes",
                    produced <= declared,
                    f"unexpected codes {sorted(produced - declared)}"
                    if produced - declared
                    else f"all values in {sorted(declared)}",
                )
            )
            result_shape = [out.height, out.width]

    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "reclassify_raster")
    return {
        "output": str(output_path),
        "shape": result_shape,
        "unmapped_cells": unmapped,
        "codes": sorted(declared),
        "provenance": str(manifest),
        "verified": True,
    }


# Only these names, and only these operators, reach the evaluator. Band
# references are b1..bN; everything else is rejected before anything is read.
_BAND_REFERENCE = re.compile(r"\bb([1-9][0-9]?)\b")
_ALLOWED_EXPRESSION = re.compile(r"^[b0-9+\-*/(). ]+$")

#: A band squared or cubed is ordinary; an exponent larger than this is not an
#: index, and the two together bound what constant folding can cost.
_MAX_EXPONENT = 8
_MAX_POWERS = 4


def _refuse_unevaluable_expression(expression: str) -> None:
    """Parse the expression and refuse anything that is not band arithmetic.

    The character whitelist is not enough and never was. `b1*0+9**9**9**9`
    matches it, references a band, and then asks CPython for an integer power
    that exhausts the host's memory before any raster is read — one call, one
    machine. The sandbox (`{"__builtins__": {}}`) is about *what* can be
    reached; this is about *how much work* an accepted expression can be.

    So the exponent of `**` has to be a plain number, small, and there can only
    be a few of them. That is what separates `(b1 - b2) ** 2` from a tower:
    `9**9**9**9` is right-associative, so its outer exponent is another
    expression rather than a constant, and it is refused on that.

    Parsing rather than pattern-matching, for the reason the SQL policy learned
    in 0.4.0: finding structure in a string is what a parser is for.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as bad:
        raise ValueError(
            f"expression {expression!r} is not valid arithmetic: {bad.msg}"
        ) from bad

    powers = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Expression | ast.Load):
            continue
        if isinstance(node, ast.Add | ast.Sub | ast.Mult | ast.Div | ast.Pow):
            continue
        if isinstance(node, ast.UAdd | ast.USub):
            continue
        if isinstance(node, ast.UnaryOp):
            continue
        if isinstance(node, ast.Name) and _BAND_REFERENCE.fullmatch(node.id):
            continue
        # `not bool` because `True` is an `int` in Python, and `b1 * True` is
        # not arithmetic anybody meant to write.
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int | float)
            and not isinstance(node.value, bool)
        ):
            continue
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, ast.Pow):
                continue
            powers += 1
            exponent = node.right
            legal = (
                isinstance(exponent, ast.Constant)
                and isinstance(exponent.value, int | float)
                and not isinstance(exponent.value, bool)
                and 0 <= exponent.value <= _MAX_EXPONENT
            )
            if not legal:
                raise ValueError(
                    f"expression {expression!r} raises to a power that is not a "
                    f"plain number between 0 and {_MAX_EXPONENT}. An index that "
                    "squares a band is ordinary; an exponent that is itself an "
                    "expression is how `9**9**9**9` exhausts the machine before "
                    "a single pixel is read."
                )
            continue
        raise ValueError(
            f"expression {expression!r} contains {type(node).__name__}, which is "
            "not band arithmetic. Only band references (b1, b2, …), numbers, "
            "+ - * / ** and parentheses are evaluated."
        )

    if powers > _MAX_POWERS:
        raise ValueError(
            f"expression {expression!r} uses {powers} exponentiations and at most "
            f"{_MAX_POWERS} are allowed. Chained small powers multiply into a "
            "large one, so the cap is on the count as well as on each exponent."
        )


def band_math(input_path: str, output_path: str, expression: str) -> dict[str, Any]:
    """Evaluate an arithmetic expression over a raster's bands (NDVI and friends).

    Bands are referenced as ``b1``, ``b2``, … and the expression may use
    ``+ - * / ** ( )`` and numbers, nothing else — it is matched against a
    regular expression before anything is read, then evaluated over numpy
    arrays with no builtins in scope. ``**`` is allowed on purpose (an index
    that squares a band is ordinary); names, calls and attribute access are
    not.

    Three things are done that a hand-rolled version usually is not, each of
    which is a silent wrong answer waiting:

    * **Declared scale and offset are applied**, and the manifest says so. GDAL
      states that applying them is the caller's job and that ``RasterIO`` will
      not; an index computed on stored digital numbers is a plausible number
      that is not the one asked for.
    * **Arithmetic happens in float64.** Subtracting two ``uint16`` bands wraps
      around at zero — ``red - nir`` where red is larger comes back near 65535,
      silently — and the result of an index built on that is well formed and
      meaningless.
    * **The output is written as float32 with a declared nodata**, rather than
      inheriting the input's integer profile, which would round an index in
      [-1, 1] to zeros and ones on the way to disk.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "band_math")
    import numpy as np

    if not _ALLOWED_EXPRESSION.match(expression):
        raise ValueError(
            f"expression {expression!r} may only contain band references (b1, b2, …), "
            "numbers, the operators + - * / ** and parentheses. Names, function "
            "calls and attribute access are rejected before the file is opened."
        )
    _refuse_unevaluable_expression(expression)
    referenced = sorted({int(m) for m in _BAND_REFERENCE.findall(expression)})
    if not referenced:
        raise ValueError(
            f"expression {expression!r} references no band; write them as b1, b2, …"
        )

    with rasterio.open(input_path) as src:
        # Taken while the input is open: a closed dataset used to answer
        # "area" without raising, and this writer shipped it.
        source_registration = grid.registration(src)
        missing = [b for b in referenced if b > src.count]
        if missing:
            raise ValueError(
                f"expression references band(s) {missing} but {input_path} has "
                f"{src.count} band(s)"
            )
        record = ProvenanceRecord(
            operation="band_math",
            parameters={"expression": expression, "bands_used": referenced},
            inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(src.crs))],
            engine={"name": "rasterio", "version": rasterio.__version__},
        )
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(src.crs),
            "reason": "band arithmetic is per-cell; geometry and CRS are unchanged",
        }
        # float64 before any arithmetic: integer bands wrap around on subtraction.
        namespace: dict[str, Any] = {}
        applied: list[str] = []
        for band_index in referenced:
            data = src.read(band_index, masked=True).astype("float64")
            scale = src.scales[band_index - 1]
            offset = src.offsets[band_index - 1]
            if scale != 1.0 or offset != 0.0:
                data = data * scale + offset
                applied.append(f"b{band_index}: value * {scale} + {offset}")
            namespace[f"b{band_index}"] = data
        if applied:
            record.notes.append(
                "declared scale and offset applied before the expression — "
                + "; ".join(applied)
                + ". GDAL leaves this to the caller, so an index computed on the "
                "stored numbers would have been a plausible wrong answer"
            )
        else:
            record.notes.append(
                "no band declares a scale or offset: the stored values are the "
                "physical ones"
            )
        source_shape = (src.height, src.width)
        profile = src.profile.copy()

    with np.errstate(divide="ignore", invalid="ignore"):
        computed = eval(
            expression, {"__builtins__": {}}, namespace
        )
    computed = np.ma.masked_invalid(np.ma.asarray(computed))
    nodata_out = -9999.0
    profile.update(count=1, dtype="float32", nodata=nodata_out)
    for key in ("blockxsize", "blockysize", "tiled"):
        profile.pop(key, None)
    with verify.audit_on_failure(record, output_path, []):
        with rasterio.open(output_path, "w", **profile) as dst:
            grid.preserve(source_registration, dst)
            dst.write(computed.filled(nodata_out).astype("float32"), 1)

        checks: list[verify.Check] = []
        with rasterio.open(output_path) as out:
            checks.append(
                verify.Check(
                    "shape_preserved",
                    (out.height, out.width) == source_shape,
                    f"{out.height}x{out.width}",
                )
            )
            checks.append(
                verify.Check(
                    "x-mapsmith:written_as_float",
                    out.dtypes[0].startswith("float"),
                    out.dtypes[0],
                )
            )
            band = out.read(1, masked=True)
            valid = int(band.count())
            invalid = int(band.size - valid)
            checks.append(
                verify.Check(
                    "result_not_empty",
                    valid > 0,
                    f"{valid} of {band.size} cells carry a value",
                    critical=False,
                    hint=None
                    if valid
                    else "Every cell is nodata: the expression divided by zero or "
                    "operated on nodata everywhere. Check the bands' nodata values.",
                )
            )
            stats = (
                {"min": float(band.min()), "max": float(band.max()), "mean": float(band.mean())}
                if valid
                else {}
            )

    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "band_math")
    result = {
        "output": str(output_path),
        "expression": expression,
        "bands_used": referenced,
        "nodata_cells": invalid,
        "provenance": str(manifest),
        "verified": True,
        **stats,
    }
    if applied:
        result["scale_offset_applied"] = applied
    advisories = verify.advisories(checks)
    if advisories:
        result["warnings"] = advisories
    return result


def reproject_raster(
    input_path: str,
    output_path: str,
    target_crs: str,
    resampling: str,
    resolution: float | None = None,
) -> dict[str, Any]:
    """Reproject a raster to another CRS. The method is REQUIRED, by design.

    The same reason `resample_raster` has no default: warping resamples, and an
    interpolating method on class codes invents classes that were never in the
    file. Nothing raises, the output looks like land cover, and every area and
    count for the invented codes is fabricated.

    Reprojection also changes the grid — a warped raster has a new shape, a new
    transform and, at the edges, cells that were outside the source. That is why
    the shape is not checked against the input's: what is checked is that the
    output really is in the CRS that was asked for, and that an interpolating
    method did not put new codes into a categorical raster.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "reproject_raster")
    import math

    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds, from_origin
    from rasterio.warp import reproject as warp
    from rasterio.warp import transform_bounds

    valid = INTERPOLATING_RESAMPLING | CATEGORICAL_RESAMPLING | WARP_ONLY_RESAMPLING
    if resampling not in valid:
        raise ValueError(
            f"resampling must be one of {sorted(valid)}, got {resampling!r}. "
            "There is no default on purpose: interpolating methods (bilinear, cubic, "
            "average) derive values between the ones present, which is right for a "
            "continuous surface and wrong for class codes — use nearest or mode there."
        )
    method = getattr(Resampling, resampling)

    with rasterio.open(input_path) as src:
        if src.crs is None:
            raise ValueError(
                f"{input_path} declares no CRS, so it cannot be reprojected. Assign one "
                "first: a raster without a CRS has coordinates that mean nothing."
            )
        source_values, categorical = _distinct_values(src)
        # The target grid is computed here rather than by
        # `rasterio.warp.calculate_default_transform`, and the reason is worth
        # knowing: that helper builds an in-memory VRT dataset and opens it, and
        # this package disables the VRT driver at the GDAL level on purpose --
        # a `.vrt` is a local path whose contents name remote sources, which is
        # the hole the audit found INSIDE the fix for issue #21. So the helper
        # cannot run here, and computing the grid ourselves is the better answer
        # anyway: the shape is derived before the engine runs and then verified.
        #
        # The pixel count is preserved in each dimension and the cell size
        # follows from the reprojected extent, which is deterministic and
        # explainable. A caller who needs a specific cell size passes one.
        left, bottom, right, top = transform_bounds(
            src.crs, target_crs, *src.bounds, densify_pts=21
        )
        if resolution is not None:
            if resolution <= 0:
                raise ValueError(f"resolution must be positive, got {resolution}")
            # Same rule as `resample`, and for the same reason: a caller who
            # names a cell size gets that cell size, and the extent grows
            # outward to the next whole cell. Deriving the size from the extent
            # instead delivered 33.24 x 33.47 for a requested 30 — not even
            # square — under a manifest that recorded 30.
            width = max(1, math.ceil((right - left) / resolution - _GRID_EPSILON))
            height = max(1, math.ceil((top - bottom) / resolution - _GRID_EPSILON))
            transform = from_origin(left, top, resolution, resolution)
        else:
            # No cell size named: preserve the pixel count and let the size
            # follow from the reprojected extent, which is what the caller is
            # asking for when they say only "put this in that CRS".
            width, height = src.width, src.height
            transform = from_bounds(left, bottom, right, top, width, height)
        record = ProvenanceRecord(
            operation="reproject_raster",
            parameters={
                "target_crs": target_crs,
                "resampling": resampling,
                "resolution": resolution,
                "target_shape": [height, width],
            },
            inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(src.crs))],
            engine={"name": "rasterio", "version": rasterio.__version__},
        )
        # What PROJ will do between these two datums, reported and not chosen:
        # rasterio builds its own transformer inside `warp`, so recording the
        # BEST available operation here would describe one that never ran.
        shift = datum.default_operation(src.crs, target_crs)
        # What is true before any pixel moves. `target_crs` and `transformation`
        # are NOT here: they say where the pixels were put and by which
        # operation, and on 2026-09-23 the same shape was found and fixed in
        # `reproject_layer` -- claims written before the `with`, on a path where
        # the move happens inside it.
        record.crs_decisions = {
            "analysis_crs": str(target_crs),
            "reason": "the caller asked for this CRS; the grid was recomputed for it with "
            f"the '{resampling}' method, which the caller also chose",
            "source_crs": verify.crs_label(src.crs),
        }
        profile = src.profile.copy()
        profile.update(crs=target_crs, transform=transform, width=width, height=height)
        for key in ("blockxsize", "blockysize", "tiled"):
            profile.pop(key, None)
        # Measured on 2026-09-23: with a three-band input and a warp that raises
        # on the second band, this left a 19608-byte raster on disk and NO
        # manifest -- bands two and three zero-filled, a plausible-looking file
        # with no lineage beside it. Invariant 2 says a dataset without a
        # manifest did not come from here, and that one had.
        with verify.audit_on_failure(record, output_path, []):
            with rasterio.open(output_path, "w", **profile) as dst:
                grid.preserve(src, dst)
                for band in range(1, src.count + 1):
                    warp(
                        source=rasterio.band(src, band),
                        destination=rasterio.band(dst, band),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs=target_crs,
                        resampling=method,
                    )
            # The pixels are there now, so the record may say where they went.
            record.crs_decisions["target_crs"] = str(target_crs)
            record.crs_decisions["transformation"] = shift
            if shift["is_ballpark"]:
                better = shift.get("better_available_m")
                record.notes.append(
                    "no datum shift was applied between these two CRSs: PROJ selected a "
                    "ballpark operation, which carries the coordinates across as if the "
                    "two datums coincided. Every pixel is correct relative to its "
                    "neighbours and the whole grid can be tens of metres from the true "
                    "position. "
                    + (
                        f"A published operation with a stated accuracy of {better} m "
                        "exists for this pair but its grid is not installed here."
                        if better is not None
                        else "PROJ has no published operation for this pair at all."
                    )
                )

    checks: list[verify.Check] = []
    with verify.audit_on_failure(record, output_path, []), rasterio.open(output_path) as out:
        checks.append(
            verify.Check(
                "crs_matches",
                verify.same_crs(out.crs, target_crs),
                f"{verify.crs_label(out.crs)}",
            )
        )
        # Not critical: a ballpark is legitimate when the caller knows the two
        # datums coincide. What is not legitimate is not saying so -- and
        # `crs_matches` above passes either way, because the output really is
        # in the CRS that was asked for. That pair of facts IS Argleton trap
        # 021, and it was true of this operation until 2026-09-03.
        checks.append(_datum_shift_check(shift))
        checks.append(
            verify.Check(
                "result_not_empty",
                out.width > 0 and out.height > 0,
                f"{out.height}x{out.width}",
            )
        )
        if resolution is not None:
            checks.append(_cell_size_check(out, resolution))
        result_values, _ = _distinct_values(out)

    # Reprojection rotates the grid, so the output covers cells the source never
    # had, and warp fills them. With a declared nodata they are marked as
    # missing; WITHOUT one they are filled with 0 and are indistinguishable from
    # a real zero — a land-cover class 0, an elevation at sea level, a count of
    # none. Found by testing this operation rather than by reading about it: the
    # first run reported 0.0 as an invented class code, which it is not.
    fill = profile.get("nodata")
    checks.append(
        verify.Check(
            "x-mapsmith:fill_is_distinguishable",
            fill is not None,
            f"nodata is {fill}" if fill is not None
            else "the source declares no nodata, so cells outside its extent are 0",
            critical=False,
            hint=None if fill is not None else (
                "Reprojection rotates the grid, so the output has cells the source did "
                "not cover. With no nodata declared they are filled with 0, which no "
                "consumer can tell from a real 0 — a class code, a sea-level elevation, "
                "a count of none. Declare a nodata value on the source before "
                "reprojecting, or treat the border of this output as unknown."
            ),
        )
    )

    invented: list[float] = []
    if categorical and resampling in INTERPOLATING_RESAMPLING and result_values is not None:
        # The fill is not an invented class: it is the absence of one, and
        # counting it as invented would cry wolf on every reprojection.
        allowed = set(source_values) | {float(fill) if fill is not None else 0.0}
        invented = sorted(result_values - allowed)
        checks.append(
            verify.Check(
                "x-mapsmith:no_invented_class_codes",
                not invented,
                f"{resampling} introduced codes absent from the input: {invented}"
                if invented
                else "output codes are a subset of the input codes",
                critical=False,
                hint=(
                    "This raster looks categorical and was warped with "
                    f"'{resampling}', which averages neighbours. The codes {invented} "
                    "exist in the result and not in the source: every downstream count "
                    "and area for them is fabricated. Use nearest or mode for class codes."
                )
                if invented
                else None,
            )
        )

    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "reproject_raster")
    result = {
        "output": str(output_path),
        "crs": str(target_crs),
        "resampling": resampling,
        "shape": [height, width],
        "resolution": resolution,
        "provenance": str(manifest),
        "verified": True,
    }
    hinted = verify.advisories(checks)
    if hinted:
        result["warnings"] = hinted
    if invented:
        result["invented_values"] = invented
    return result


def extract_band(input_path: str, output_path: str, band: int) -> dict[str, Any]:
    """Write one band of a multi-band raster to a single-band raster.

    Bands are numbered from 1, as they are everywhere in GDAL and rasterio and
    nowhere in Python. Asking for band 0 or for a band past the end is refused
    rather than clamped: an off-by-one here produces a perfectly valid raster of
    the wrong quantity — near-infrared where red was meant — and nothing
    downstream can tell, which is the whole reason this refuses instead of
    guessing.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "extract_band")

    with rasterio.open(input_path) as src:
        # Taken while the input is open: a closed dataset used to answer
        # "area" without raising, and this writer shipped it.
        source_registration = grid.registration(src)
        if not 1 <= band <= src.count:
            raise ValueError(
                f"band must be between 1 and {src.count} for {input_path}, got {band}. "
                "Bands are 1-based: band 1 is the first. Reading the wrong band returns a "
                "valid raster of the wrong quantity, so this is refused rather than clamped."
            )
        record = ProvenanceRecord(
            operation="extract_band",
            parameters={"band": band, "source_band_count": src.count},
            inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(src.crs))],
            engine={"name": "rasterio", "version": rasterio.__version__},
        )
        record.crs_decisions = {
            "analysis_crs": verify.crs_label(src.crs),
            "reason": "extracting a band changes neither the grid nor the coordinate system",
        }
        data = src.read(band)
        profile = src.profile.copy()
        profile.update(count=1)
        descriptions = src.descriptions
        label = descriptions[band - 1] if descriptions else None
        if label:
            record.notes.append(f"band {band} is described in the source as {label!r}")
        checksum = src.checksum(band)

    with verify.audit_on_failure(record, output_path, []):
        with rasterio.open(output_path, "w", **profile) as dst:
            grid.preserve(source_registration, dst)
            dst.write(data, 1)
            if label:
                dst.set_band_description(1, label)

        with rasterio.open(output_path) as out:
            checks = [
                verify.Check(
                    "shape_preserved",
                    (out.height, out.width) == data.shape,
                    f"{out.height}x{out.width}",
                ),
                verify.Check(
                    "crs_matches",
                    verify.same_crs(out.crs, record.inputs[0].crs),
                    f"{verify.crs_label(out.crs)}",
                ),
                verify.Check(
                    # The band that landed is the band that was asked for, compared
                    # by the source's own checksum rather than by trusting the index
                    # we passed: an off-by-one is exactly what this operation exists
                    # not to make, so it is the one thing worth verifying.
                    "x-mapsmith:band_content_matches_source",
                    out.checksum(1) == checksum,
                    f"checksum {out.checksum(1)} against source band {band}'s {checksum}",
                ),
            ]

    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "extract_band")
    return {
        "output": str(output_path),
        "band": band,
        "description": label,
        "provenance": str(manifest),
        "verified": True,
    }


def band_statistics(input_path: str, band: int | None = None) -> dict[str, Any]:
    """Per-band statistics, computed over the valid cells only. Reads, writes nothing.

    Nodata is excluded, and how many cells that removed is part of the answer:
    a mean over a raster whose nodata is `-9999` and whose mask was ignored is
    the classic wrong number that looks like an elevation. The count of valid
    cells travels with every statistic so the caller can see what it is a mean
    OF.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "band_statistics")

    with rasterio.open(input_path) as src:
        if band is not None and not 1 <= band <= src.count:
            raise ValueError(
                f"band must be between 1 and {src.count} for {input_path}, got {band}"
            )
        wanted = [band] if band is not None else list(range(1, src.count + 1))
        bands = []
        for index in wanted:
            values = src.read(index, masked=True)
            valid = int(values.count())
            row: dict[str, Any] = {
                "band": index,
                "valid_cells": valid,
                "masked_cells": int(values.size - valid),
                "nodata": src.nodatavals[index - 1],
            }
            if valid:
                row.update(
                    min=float(values.min()),
                    max=float(values.max()),
                    mean=float(values.mean()),
                    std=float(values.std()),
                    sum=float(values.sum()),
                )
            else:
                # Every cell is nodata. Saying so is the answer; a mean of an
                # empty selection is not, and numpy would hand back a warning
                # and a nan that reads like a value.
                row["all_masked"] = True
            bands.append(row)
        return {
            "path": str(input_path),
            "crs": verify.crs_label(src.crs),
            "band_count": src.count,
            "shape": [src.height, src.width],
            "bands": bands,
        }


def locate_extreme_cell(
    input_path: str,
    which: str = "min",
    band: int = 1,
) -> dict[str, Any]:
    """Where the lowest or highest value of a raster is. Reads, writes nothing.

    The bottom of a hollow, the summit of a hill, the hottest cell of a
    difference grid. It answers with a coordinate rather than a value, which is
    the question no other operation here could be asked — and the gap that made
    MapSmith report `unsupported` twice on Argleton's `grid-registration`
    family, where the whole point is whether a system knows where its own cells
    are.

    **The position comes from `grid`**, which gives the same answer as
    `dataset.xy` under either registration: GDAL has already shifted the
    geotransform of a point-registered file so its cells are centred on the
    samples. Until 2026-09-25 this docstring said the opposite and the answer on
    every `AREA_OR_POINT=Point` raster was half a cell north-west of the sample
    -- 15 m on a 30 m DEM, the error it claimed to prevent (D-096).

    Nodata is excluded rather than competing: a nodata of -9999 wins every
    search for a minimum, and the answer would be the position of a hole.

    A tie is reported rather than broken silently. Two cells at the same extreme
    value is a fact about the data — a plateau, a flat pond, a saturated sensor
    — and picking the first in scan order and saying nothing turns it into a
    confident single answer.
    """
    if which not in ("min", "max"):
        raise ValueError(f"which must be 'min' or 'max', got {which!r}")
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). Returns the manifest
    # entry when there is nothing to refuse.
    grid.refuse_ambiguous_georeferencing(input_path, "locate_extreme_cell")

    import numpy as np


    with rasterio.open(input_path) as src:
        if not 1 <= band <= src.count:
            raise ValueError(
                f"band must be between 1 and {src.count} for {input_path}, got {band}"
            )
        if src.crs is None:
            raise ValueError(
                f"{input_path} has no CRS, so a position in it would be a pair of "
                "numbers with no ground meaning."
            )
        values = src.read(band, masked=True)
        if values.count() == 0:
            raise ValueError(
                f"every cell of band {band} in {input_path} is nodata, so there is "
                "no lowest or highest value to locate."
            )
        extreme = float(values.min() if which == "min" else values.max())
        hits = np.argwhere(np.ma.filled(values == extreme, False))
        row, column = (int(v) for v in hits[0])
        x, y = grid.sample_xy(src, row, column)
        registration = grid.describe(src)
        unit = None
        try:
            unit = src.crs.axis_info[0].unit_name
        except (AttributeError, IndexError):  # pragma: no cover - exotic CRS
            unit = "unit"

    answer = {
        "which": which,
        "value": extreme,
        "x": round(float(x), 6),
        "y": round(float(y), 6),
        "row": row,
        "column": column,
        "band": band,
        "valid_cells": int(values.count()),
        "nodata_cells": int(values.size - values.count()),
        "crs": verify.crs_label(src.crs),
        "unit": unit,
        **registration,
    }
    if len(hits) > 1:
        answer["tied_cells"] = len(hits)
        answer["note"] = (
            f"{len(hits)} cells hold the {which}imum value {extreme:g}; the first in "
            "scan order (top-left to bottom-right) is reported. A tie usually means a "
            "plateau, a flat surface, or a sensor at the end of its range, and any of "
            "those makes 'the position of the extreme' a question about a region "
            "rather than a cell."
        )
    return answer
