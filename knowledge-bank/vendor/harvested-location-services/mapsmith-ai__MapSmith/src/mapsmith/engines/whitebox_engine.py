"""Terrain and hydrology on the Whitebox Workflows engine (Whitebox Next Gen).

whitebox_workflows 2.x is the PyO3 successor of WhiteboxTools: rasters stay
in memory (no CLI round-trips) and every tool wrapped here lives in the open
tier (MIT/Apache-2.0 dual license — verified against the upstream taxonomy).
Optional extra: ``pip install mapsmith[whitebox]``.

API notes pinned by runtime verification (2.0.6): category tool calls accept
keyword arguments only; CRS is read via ``Raster.crs_epsg()``/``crs_wkt()``
(``metadata().epsg_code`` is not populated); hillshade output is scaled
0-32767; nodata passes through ``to_numpy`` as the raw nodata value.

Raster verification lives here rather than in ``verify.py`` because reading
the output back requires this engine; the checks land in the provenance
manifest before any error is raised, like every other MapSmith writer.
"""

from __future__ import annotations

import math
import tempfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any

import numpy as np
from pyproj import CRS

from .. import grid, readers, verify, workspace
from ..provenance import InputRecord, ProvenanceRecord, alignment_decisions

HILLSHADE_MAX = 32767  # upstream scales hillshade to 0-32767 (basic_terrain_tools.rs)


def _require():
    try:
        import whitebox_workflows as wb
    except ImportError as exc:
        raise ImportError(
            "terrain/hydrology operations require the whitebox extra: "
            "pip install mapsmith[whitebox]"
        ) from exc
    return wb


def _engine_info() -> dict[str, str]:
    from importlib.metadata import version

    return {"name": "whitebox-workflows", "version": version("whitebox-workflows")}


def _needs_plain_copy(path: str) -> str | None:
    """Why this GeoTIFF must be rewritten before whitebox may read it, or None.

    whitebox_workflows 2.x never undoes the TIFF predictor (tag 317), so
    ``read_raster`` hands back the *undifferenced* values and everything
    computed from them is wrong. The mechanism is unambiguous — for
    predictor=2 the rows come back as the horizontal differences themselves:

        row as whitebox returns it : [100,   7,   7,   7,   7,   7]
        row as GDAL decodes it     : [100, 107, 114, 121, 128, 135]
        cumsum(whitebox row) == GDAL row  ->  exactly True, on a STRIPED file

    The condition on that last line matters, and leaving it implicit misleads
    the next reader: the horizontal predictor differences within each strip or
    *tile*, so on a tiled GeoTIFF the series restarts at every tile boundary
    and a cumulative sum across the full row stops agreeing after the first
    tile column. Measured on ``examples/fixtures/mount_st_helens_dem.tif``
    (tiled 256, DEFLATE, predictor=2): columns 0-255 match, column 256 is the
    first mismatch, 50.8% of pixels differ — while the same cumulative sum
    *reset at each tile boundary* reproduces the truth exactly. Anyone checking
    with a COG, which is tiled by definition, would otherwise see the identity
    fail and conclude the bug is not there.

    The bug itself does not care about tiling: it happens at any block size,
    and on this tiled fixture whitebox reads elevations of -63..2531 m where
    the truth is 652..2534 m. predictor=3 (the floating-point predictor) yields
    garbage and NaNs the same way. Compression is NOT the trigger: DEFLATE, LZW
    and PACKBITS all read correctly without a predictor. The damage is silent —
    CRS, shape and value range all stay plausible, and a hillshade still looks
    like terrain while differing from the truth on 99% of pixels — so no
    postcondition can catch it.

    PREDICTOR=2 is the standard recommendation for integer rasters, so this
    is a normal encoding rather than an exotic one.

    Reported upstream: https://github.com/jblindsay/whitebox_next_gen/issues/32
    Drop this workaround once a release fixes it — the read-level test in
    tests/test_whitebox_encoding.py fails when that happens, on purpose.
    """
    try:
        import rasterio
    except ImportError:  # rasterio ships with the whitebox extra; be defensive
        return None
    from .. import grid

    try:
        with rasterio.open(path) as ds:
            predictor = ds.tags(ns="IMAGE_STRUCTURE").get("PREDICTOR")
            south_up = ds.transform.e > 0
            point = grid.registration(ds) == "point"
    except Exception:  # noqa: BLE001 — unreadable here means whitebox will complain
        return None
    reasons = []
    if predictor in ("2", "3"):
        reasons.append(f"stored with TIFF predictor {predictor}")

    # Second reason, measured on 2026-08-30 by Argleton trap 026. A GeoTIFF may
    # store its rows south to north — a POSITIVE fifth element of the
    # geotransform — which is legal, and which NetCDF, GRIB and HDF conversions
    # produce as a matter of course because those formats index latitude
    # upwards. whitebox_workflows 2.0.6 cannot express it and does not say so:
    # it discards the georeferencing entirely and reads the grid as unit cells
    # at the origin.
    #
    #     north-up file:  west=500000.0  resolution_x=10.0
    #     south-up file:  west=0.0       resolution_x=1.0
    #
    # The elevations, the shape and the CRS all survive. Only the size of a cell
    # is gone, and a slope is a rise over a run: on the trap's plane, 45 degrees
    # where the truth is 5.71, with every postcondition green.
    if south_up:
        reasons.append("stored south-up (a positive north-south pixel size)")

    # Third reason, measured on 2026-09-25 on the Copernicus DEM. A
    # point-registered GeoTIFF stores its tie point AT the first sample, and
    # GDAL shifts it half a cell to keep its geotransform area-oriented (RFC 33).
    # whitebox reads the raw tie point as the corner of the first cell, so it
    # places every cell half a cell south-east of the sample:
    #
    #     Copernicus clip:  GDAL corner 10.799861  whitebox corner 10.8
    #
    # `_same_grid_as_gdal` caught it and refused, which kept the numbers right
    # and every point-registered DEM out of every terrain operation -- the
    # Copernicus DEM, the most used global one, included. The copy declares
    # area on GDAL's own geotransform, which puts each cell's centre on the
    # sample, and the output gets the input's registration back (D-096).
    if point:
        reasons.append("point-registered (AREA_OR_POINT=Point)")
    return " and ".join(reasons) or None


def _plain_copy(path: str, into: Path) -> str:
    """A copy with byte-identical values and no predictor.

    Compression is kept (whitebox decodes it correctly on its own); only the
    predictor is dropped, so the copy stays roughly the size of the original.
    """
    import rasterio
    from affine import Affine

    with rasterio.open(path) as src:
        profile = src.profile
        data = src.read(1)
        transform = src.transform
        height = src.height

    profile.pop("predictor", None)
    # GTiff whatever the input was: the copy is named `.tif` and the engine reads
    # it as one. An input in another format would otherwise be recreated with
    # its own driver under a GeoTIFF name.
    profile["driver"] = "GTiff"
    if transform.e > 0:
        # Flip the rows and rewrite the transform to match, so the copy is the
        # same ground read the ordinary way round. Row r of the flipped array is
        # row (height - 1 - r) of the original, and the new origin is the north
        # edge: f + height*e. Checked by arithmetic rather than by eye — the
        # y-centre of every cell comes out identical under both transforms.
        data = data[::-1]
        profile["transform"] = Affine(
            transform.a,
            transform.b,
            transform.c,
            transform.d,
            -transform.e,
            transform.f + height * transform.e,
        )

    plain = into / f"{Path(path).stem}.no-predictor.tif"
    with rasterio.open(plain, "w", **profile, predictor=1) as dst:
        dst.write(data, 1)
        # Declared area on purpose, and on GDAL's geotransform, whatever the
        # original declares. GDAL already centres its cell on a point sample,
        # so an area copy with the same transform puts every cell centre on
        # the sample -- in the raw tie point too, which is what whitebox reads.
        # Copying the Point tag, as this did until 2026-09-25, handed whitebox
        # a tie point it reads half a cell off.
    return str(plain)


def _plain_copy_note(reason: str) -> str:
    return (
        f"input GeoTIFF is {reason}; the engine was given a copy with identical "
        "values, north-up, without a TIFF predictor and declared area-registered "
        "on GDAL's own geotransform, because whitebox_workflows 2.x mishandles "
        "each of those (see _needs_plain_copy for the measurements)"
    )


def _write(wbe: Any, raster: Any, output_path: str, source: str, record: Any) -> None:
    """Write an engine output, give it back the input's registration, and say so.

    The engine was handed an area copy of a point-registered input, so it
    writes area. On the same geotransform the positions are the same either
    way (D-096), but the tag says what a value represents, and an output that
    quietly stopped saying "sample at a point" is the silent change `preserve`
    exists to prevent. Retagging in place keeps the geotransform: measured,
    GDAL shifts the stored tie point and reads back the same transform.

    The record gets the registration in `crs_decisions`, as the raster writers
    in `raster.py` already did, and a note when the output's bytes were changed
    after the engine wrote them. Until the 2026-09-25 review neither was there:
    MapSmith modified an output the manifest attributed to the engine alone.
    """
    import rasterio

    from .. import grid

    wbe.write_raster(raster, str(output_path))
    with rasterio.open(source) as src:
        record.crs_decisions.update(grid.manifest_decisions(src))
        point = grid.registration(src) == "point"
    if point:
        with rasterio.open(output_path, "r+") as dst:
            grid.preserve("point", dst)
        record.notes.append(
            "the input declares AREA_OR_POINT=Point, so after the engine wrote this "
            "output MapSmith tagged it Point in place; the geotransform is unchanged. "
            "Read through GDAL, positions are exact. The terrain engine itself reads a "
            "Point file's stored tie point as a cell corner, so opening this output "
            "with it directly puts every cell half a cell south-east -- MapSmith hands "
            "it an area copy instead."
        )


def _same_grid_as_gdal(dem: Any, source: str, declared_as: str) -> None:
    """Refuse when the engine's idea of the grid is not GDAL's.

    This is the check that would have caught Argleton trap 026 without the trap.
    whitebox builds its own raster model from the file and, on a south-up grid,
    silently built a different one — unit cells at the origin — while keeping
    the CRS, the shape and the values. Nothing downstream could tell: a slope
    computed on it is a plausible number, the output carries a correct-looking
    EPSG code, and every postcondition passes.

    The known cause is handled before this point by rewriting the input
    (`_needs_plain_copy`). What remains here is the general guard: any future
    divergence between the two readings stops the operation instead of
    producing a number nobody can question.
    """
    import rasterio

    meta = dem.metadata()
    with rasterio.open(source) as ds:
        expected = (abs(ds.transform.a), abs(ds.transform.e))
        west, north = ds.transform.c, ds.transform.f
    actual = (float(meta.resolution_x), float(meta.resolution_y))
    if not all(
        math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
        for a, b in zip(actual, expected, strict=True)
    ) or not (
        math.isclose(float(meta.west), west, rel_tol=1e-9, abs_tol=1e-6)
        and math.isclose(float(meta.north), north, rel_tol=1e-9, abs_tol=1e-6)
    ):
        raise ValueError(
            f"the terrain engine read {declared_as} as a grid of "
            f"{actual[0]} x {actual[1]} cells with its north-west corner at "
            f"({meta.west}, {meta.north}), where the file says "
            f"{expected[0]} x {expected[1]} at ({west}, {north}). Every number "
            "computed from it would be wrong by the ratio of those cell sizes, "
            "and the output would carry the file's own CRS on top of it, so "
            "nothing downstream could tell. This is refused rather than "
            "reported: MapSmith has no way to know which of the two readings "
            "the engine will use for the parts it does not expose."
        )


@contextmanager
def _read_dem(wbe: Any, dem_path: str):
    """Yield (raster, crs, is_geographic, disclosure note) for a DEM.

    A context manager because whitebox reads lazily: when the predictor
    defect (see :func:`_needs_plain_copy`) forces us to hand the engine a
    converted copy, that copy has to stay on disk until the operation ends.
    Rasters without a CRS are rejected — terrain analysis on unknown units is
    meaningless.
    """
    with ExitStack() as stack:
        reason = _needs_plain_copy(dem_path)
        if reason:
            ws = workspace.root()
            tmp = stack.enter_context(
                tempfile.TemporaryDirectory(dir=str(ws) if ws else None)
            )
            source, note = _plain_copy(dem_path, Path(tmp)), _plain_copy_note(reason)
        else:
            source, note = str(dem_path), None
        dem = wbe.read_raster(source)
        _same_grid_as_gdal(dem, source, dem_path)
        epsg = dem.crs_epsg()
        wkt = dem.crs_wkt()
        if not epsg and not wkt:
            raise ValueError(
                f"{dem_path} has no CRS — terrain analysis needs one to be meaningful. "
                "Assign the correct CRS to the source raster first."
            )
        crs_obj = CRS.from_epsg(epsg) if epsg else CRS.from_wkt(str(wkt))
        yield dem, (f"EPSG:{epsg}" if epsg else str(wkt)), crs_obj.is_geographic, note


def _raster_checks(
    wbe: Any,
    output_path: str,
    *,
    expect_epsg: int,
    expect_shape: tuple[int, int],
    value_range: tuple[float, float] | None = None,
) -> list[verify.Check]:
    """Deterministic postconditions on a raster output, read back from disk."""
    out = wbe.read_raster(str(output_path))
    out_wkt = out.crs_wkt()
    if out.crs_epsg():
        crs_detail = f"EPSG:{out.crs_epsg()}"
    elif out_wkt:
        crs_detail = f"WKT: {str(out_wkt)[:60]}"
    else:
        crs_detail = "output has no CRS"
    checks = [
        verify.Check(
            "crs_present",
            bool(out.crs_epsg() or out_wkt),
            crs_detail,
        )
    ]
    if expect_epsg:
        checks.append(
            verify.Check(
                "crs_matches",
                out.crs_epsg() == expect_epsg,
                f"expected EPSG:{expect_epsg}, got EPSG:{out.crs_epsg()}",
            )
        )
    meta = out.metadata()
    shape = (meta.rows, meta.columns)
    checks.append(
        verify.Check(
            "shape_preserved",
            shape == expect_shape,
            f"expected {expect_shape}, got {shape}",
        )
    )
    arr = out.to_numpy(dtype="float64")
    # NaN is a common float nodata: NaN != NaN, so an equality mask alone would
    # let nodata cells leak into the range check as NaN min/max.
    if math.isnan(meta.nodata):
        valid = arr[~np.isnan(arr)]
    else:
        valid = arr[(arr != meta.nodata) & ~np.isnan(arr)]
    checks.append(
        verify.Check(
            "result_not_empty",
            valid.size > 0,
            f"{valid.size}/{arr.size} valid cells",
        )
    )
    if value_range is not None and valid.size:
        lo, hi = value_range
        vmin, vmax = float(valid.min()), float(valid.max())
        checks.append(
            verify.Check(
                "values_in_expected_range",
                lo <= vmin and vmax <= hi,
                f"valid cells in [{vmin:.4g}, {vmax:.4g}], expected [{lo:.4g}, {hi:.4g}]",
            )
        )
    return checks


def hillshade(
    dem_path: str,
    output_path: str,
    azimuth: float = 315.0,
    altitude: float = 30.0,
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Shaded relief from a DEM (values scaled 0-32767, nodata preserved)."""
    wb = _require()
    if not 0.0 <= azimuth <= 360.0:
        raise ValueError(f"azimuth must be in [0, 360] degrees, got {azimuth}")
    if not 0.0 <= altitude <= 90.0:
        raise ValueError(f"altitude must be in [0, 90] degrees, got {altitude}")

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, dem_path) as (dem, crs, geographic, input_note):
        record = ProvenanceRecord(
            operation="hillshade",
            parameters={"azimuth": azimuth, "altitude": altitude, "z_factor": z_factor},
            inputs=[InputRecord.from_path(dem_path, crs=crs)],
            engine=_engine_info(),
        )
        record.crs_decisions = {
            "analysis_crs": crs,
            "reason": (
                "DEM is in a geographic CRS (degree cells vs meter elevations): shading "
                "is computed on native cells and relief may be exaggerated — reproject "
                "to a projected CRS or tune z_factor for metrically faithful shading"
                if geographic
                else "hillshade computed in the DEM's native projected CRS; "
                "no reprojection needed"
            ),
        }
        result = wbe.terrain.general.hillshade(
            input=dem, azimuth=azimuth, altitude=altitude, z_factor=z_factor
        )
        # From the first byte of the output to the last check, a failure must leave a
        # record beside whatever landed (invariant 2). Measured on 2026-09-25: a check
        # that raised after this write left the raster on disk and no manifest, and so
        # did ten other writers in this module. The same net is on each of them.
        with verify.audit_on_failure(record, output_path, []):
            _write(wbe, result, output_path, dem_path, record)

            meta = dem.metadata()
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=dem.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                value_range=(0, HILLSHADE_MAX),
            )
        if input_note:
            record.notes.append(input_note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "hillshade")
        return {
            "output": str(output_path),
            "azimuth": azimuth,
            "altitude": altitude,
            "provenance": str(manifest),
            "verified": True,
        }


SLOPE_UNITS = {"degrees", "percent", "radians"}


def slope(
    dem_path: str,
    output_path: str,
    units: str = "degrees",
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Slope gradient from a DEM (Zevenbergen-Thorne; degrees, percent or radians).

    Geographic-CRS DEMs are refused: with degree cells and meter elevations the
    gradient is wrong everywhere while looking plausible — the caller must
    reproject first. Edge behaviour, measured on 2.0.6: the outermost TWO cell
    rings are approximated (clamped windows), values from the third ring inward
    are exact on an ideal plane.
    """
    if units not in SLOPE_UNITS:
        raise ValueError(f"units must be one of {sorted(SLOPE_UNITS)}, got '{units}'")
    bounds = {
        "degrees": (0.0, 90.0),
        "radians": (0.0, math.pi / 2),
        "percent": None,  # tan of the angle: unbounded near vertical
    }[units]
    return _derivative(
        "slope",
        dem_path,
        output_path,
        parameters={"units": units, "z_factor": z_factor},
        call=lambda wbe, dem: wbe.terrain.derivatives.slope(
            input=dem, units=units, z_factor=z_factor
        ),
        value_range=bounds,
    )


def aspect(
    dem_path: str,
    output_path: str,
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Aspect from a DEM: azimuth of the downslope direction, degrees, 0 = north.

    Convention pinned by measurement on 2.0.6: a plane rising eastward yields
    270 (the downslope faces west). Flat cells are encoded as -1, NOT as
    nodata — a consumer averaging aspect over an area that contains flats gets
    a plausible wrong number unless it masks the -1 first, which is why the
    value is stated here and in the tool docs. Geographic-CRS DEMs are refused
    (see slope).
    """
    return _derivative(
        "aspect",
        dem_path,
        output_path,
        parameters={"z_factor": z_factor},
        call=lambda wbe, dem: wbe.terrain.derivatives.aspect(input=dem, z_factor=z_factor),
        value_range=(-1.0, 360.0),  # -1 is the flat-cell marker, by upstream design
    )


def _derivative(
    operation: str,
    dem_path: str,
    output_path: str,
    *,
    parameters: dict[str, Any],
    call: Any,
    value_range: tuple[float, float] | None,
    extra_checks: Any = None,
) -> dict[str, Any]:
    """Shared body of the local terrain derivatives (slope, aspect, curvature, flow direction).

    `extra_checks` receives the written output path and returns more checks. It
    exists for `flow_direction`, whose codes are a fixed SET rather than a range:
    a value of 3 in a D8 pointer is not out of bounds, it is not a direction at
    all, and a range check would pass it.
    """
    wb = _require()
    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, dem_path) as (dem, crs, geographic, input_note):
        if geographic:
            raise ValueError(
                f"{operation} on a geographic CRS mixes degree cells with meter "
                "elevations and returns plausible but wrong values everywhere. "
                "Reproject the DEM to a projected CRS first (e.g. its UTM zone)."
            )
        record = ProvenanceRecord(
            operation=operation,
            parameters=parameters,
            inputs=[InputRecord.from_path(dem_path, crs=crs)],
            engine=_engine_info(),
        )
        record.crs_decisions = {
            "analysis_crs": crs,
            "reason": (
                f"{operation} computed in the DEM's native projected CRS; geographic-CRS "
                "DEMs are refused because horizontal units (degrees) would not match "
                "vertical units (meters)"
            ),
        }
        result = call(wbe, dem)
        with verify.audit_on_failure(record, output_path, []):
            _write(wbe, result, output_path, dem_path, record)

            meta = dem.metadata()
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=dem.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                value_range=value_range,
            )
            if extra_checks is not None:
                checks.extend(extra_checks(output_path))
        if input_note:
            record.notes.append(input_note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, operation)
        return {
            "output": str(output_path),
            **parameters,
            "provenance": str(manifest),
            "verified": True,
        }


def flow_accumulation(
    dem_path: str,
    output_path: str,
    out_type: str = "cells",
    log_transform: bool = False,
) -> dict[str, Any]:
    """D8 flow accumulation from a DEM (depressions filled first, decision recorded)."""
    wb = _require()
    valid_types = {"cells", "sca"}
    if out_type not in valid_types:
        raise ValueError(f"out_type must be one of {sorted(valid_types)}, got '{out_type}'")

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, dem_path) as (dem, crs, geographic, input_note):
        if out_type == "sca" and geographic:
            raise ValueError(
                "specific catchment area needs a projected CRS (it divides by cell width, "
                "which is degrees here). Reproject the DEM to a projected CRS first "
                "(e.g. a UTM zone via reproject workflows), or use out_type='cells'."
            )
        record = ProvenanceRecord(
            operation="flow_accumulation",
            parameters={
                "method": "d8",
                "out_type": out_type,
                "log_transform": log_transform,
                "preprocessing": "fill_depressions",
            },
            inputs=[InputRecord.from_path(dem_path, crs=crs)],
            engine=_engine_info(),
        )
        record.crs_decisions = {
            "analysis_crs": crs,
            "reason": (
                "cell-count accumulation is independent of cell units; computed in the "
                "DEM's native geographic CRS"
                if geographic
                else "flow routing computed in the DEM's native projected CRS; "
                "no reprojection needed"
            ),
        }
        filled = wbe.hydrology.depressions_storage.fill_depressions(dem=dem)
        pointer = wbe.hydrology.flow_routing.d8_pointer(dem=filled)
        accum = wbe.hydrology.flow_routing.d8_flow_accum(
            input=pointer, out_type=out_type, log_transform=log_transform, input_is_pointer=True
        )
        with verify.audit_on_failure(record, output_path, []):
            _write(wbe, accum, output_path, dem_path, record)

            meta = dem.metadata()
            cells = meta.rows * meta.columns
            # 'cells' accumulation counts each cell itself, so valid values live in [1, n_cells]
            # (or their natural log when log-transformed).
            bounds = (1.0, float(cells)) if out_type == "cells" else None
            if bounds and log_transform:
                bounds = (0.0, math.log(cells))
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=dem.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                value_range=bounds,
            )
        if input_note:
            record.notes.append(input_note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "flow_accumulation")
        return {
            "output": str(output_path),
            "method": "d8",
            "out_type": out_type,
            "provenance": str(manifest),
            "verified": True,
        }


def watershed(
    dem_path: str,
    pour_points_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Watershed of each pour point (1-based IDs in feature order; nodata elsewhere)."""
    wb = _require()
    points = readers.read_vector(pour_points_path)
    if points.crs is None:
        raise ValueError(readers.no_crs_message(
            points, f"{pour_points_path} has no CRS — cannot place pour points on the DEM."
        ))
    geom_types = set(points.geom_type.dropna().unique())
    if not geom_types.issubset({"Point"}):
        raise ValueError(f"pour points must be Point geometries, got {sorted(geom_types)}")

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, dem_path) as (dem, crs, _geographic, input_note):  # topology is unit-free
        record = ProvenanceRecord(
            operation="watershed",
            parameters={"method": "d8", "preprocessing": "fill_depressions", "n_pour_points": len(points)},
            inputs=[
                InputRecord.from_path(dem_path, crs=crs, argument="dem_path"),
                InputRecord.from_path(
                    pour_points_path, crs=verify.crs_label(points.crs), argument="pour_points_path"
                ),
            ],
            engine=_engine_info(),
        )
        # Compare the coordinate systems, not their spellings: `str(crs)` is
        # PROJJSON for any GeoParquet input, so this was true even when the
        # points were already on the DEM's grid — and the manifest then recorded
        # a reprojection that never happened.
        aligned = not verify.same_crs(points.crs, crs)
        record.crs_decisions = alignment_decisions(
            crs,
            "pour points brought to the DEM CRS to align with the flow grid"
            if aligned
            else "pour points and DEM share the same CRS",
            [("pour_points_path", points.crs)] if aligned else [],
        )
        if aligned:
            points = points.to_crs(crs)

        filled = wbe.hydrology.depressions_storage.fill_depressions(dem=dem)
        pointer = wbe.hydrology.flow_routing.d8_pointer(dem=filled)
        # whitebox reads vectors as shapefiles: hand it the (possibly reprojected)
        # points through a temporary shapefile so any GeoPandas-readable input works.
        # Under a workspace even scratch data must not leave it (data governance).
        with verify.audit_on_failure(record, output_path, []):
            ws = workspace.root()
            with tempfile.TemporaryDirectory(dir=str(ws) if ws else None) as tmp:
                shp = Path(tmp) / "pour_points.shp"
                points.to_file(shp)
                vec = wbe.read_vector(str(shp))
                basins = wbe.hydrology.watersheds_basins.watershed(d8_pointer=pointer, pour_pts=vec)
                _write(wbe, basins, output_path, dem_path, record)

            meta = dem.metadata()
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=dem.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                value_range=(1.0, float(len(points))),
            )
        if input_note:
            record.notes.append(input_note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "watershed")
        return {
            "output": str(output_path),
            "n_pour_points": len(points),
            "provenance": str(manifest),
            "verified": True,
        }


FOCAL_STATISTICS = {
    "mean": "mean_filter",
    "median": "median_filter",
    "maximum": "maximum_filter",
    "minimum": "minimum_filter",
    "range": "range_filter",
    "standard_deviation": "standard_deviation_filter",
    "majority": "majority_filter",
    "diversity": "diversity_filter",
    "total": "total_filter",
}


def focal_statistics(
    input_path: str,
    output_path: str,
    statistic: str,
    window: int,
) -> dict[str, Any]:
    """A moving-window statistic over a raster, with the window size required.

    Whitebox's filters default to an 11 x 11 window. On a 1 m DEM that is a
    5.5 m radius, so a "local" statistic quietly stops being local — and the
    result is a perfectly ordinary-looking smoothed surface. The window is
    therefore a required argument here, and must be odd: an even window has no
    centre cell, so the output is offset by half a cell from its input, which
    is a shift nothing downstream can see.

    For class codes use `majority` or `diversity`; `mean` on a land-cover map
    invents codes, the same way an interpolating resample does.
    """
    wb = _require()
    if statistic not in FOCAL_STATISTICS:
        raise ValueError(
            f"statistic must be one of {sorted(FOCAL_STATISTICS)}, got {statistic!r}"
        )
    if window < 3 or window % 2 == 0:
        raise ValueError(
            f"window must be an odd number of cells, at least 3, got {window}. "
            "An even window has no centre cell and shifts the result by half a "
            "cell against its input."
        )
    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, input_path) as (raster, crs, _geographic, input_note):
        record = ProvenanceRecord(
            operation="focal_statistics",
            parameters={"statistic": statistic, "window": window, "shape": "square"},
            inputs=[InputRecord.from_path(input_path, crs=crs)],
            engine=_engine_info(),
        )
        record.crs_decisions = {
            "analysis_crs": crs,
            "reason": "a moving window is measured in CELLS, not in ground units: "
            "the same window covers a different distance on a different grid, and "
            "no reprojection would change that",
        }
        record.notes.append(
            f"window {window}x{window} cells; at this raster's resolution that is "
            f"{window} cells across, and the statistic is not comparable with one "
            "computed at another resolution"
        )
        if statistic in ("mean", "median", "total", "standard_deviation", "range"):
            record.notes.append(
                f"'{statistic}' derives values that need not exist in the input: "
                "correct for a continuous surface, wrong for class codes, where "
                "'majority' or 'diversity' are the ones that keep the alphabet"
            )
        # `wbe.remote_sensing`, not `wbe.raster`: the typed stub files them
        # under raster and the runtime does not have them there. Third time
        # a Whitebox tool is not where its documentation says (after
        # terrain.general vs terrain.derivatives), so this path was found by
        # introspecting the installed package.
        method = getattr(wbe.remote_sensing, FOCAL_STATISTICS[statistic])
        result = method(input=raster, filter_size_x=window, filter_size_y=window)
        with verify.audit_on_failure(record, output_path, []):
            _write(wbe, result, output_path, input_path, record)

            meta = raster.metadata()
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=raster.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                value_range=None,
            )
        if input_note:
            record.notes.append(input_note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "focal_statistics")
        return {
            "output": str(output_path),
            "statistic": statistic,
            "window": window,
            "provenance": str(manifest),
            "verified": True,
        }


def extract_streams(
    flow_accumulation_path: str,
    output_path: str,
    threshold: float,
    zero_background: bool = False,
) -> dict[str, Any]:
    """The stream network implied by a flow-accumulation grid and a threshold.

    The threshold is required, and the manifest records which UNIT it is in,
    because that is where this operation goes wrong: `d8_flow_accum` produces
    either a cell count or a specific contributing area depending on its
    `out_type`, the two differ by orders of magnitude, and a threshold tuned for
    one applied to the other gives a stream network that is well formed, drawn
    on the map, and wrong. There is no defensible default for the threshold
    either — the literature says so plainly — so the caller states it and the
    record keeps it.
    """
    wb = _require()
    if threshold <= 0:
        raise ValueError(
            f"threshold must be positive, got {threshold}. With 0 every cell that "
            "drains anything becomes a stream, which is the whole DEM."
        )
    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, flow_accumulation_path) as (accumulation, crs, _geographic, note):
        record = ProvenanceRecord(
            operation="extract_streams",
            parameters={
                "threshold": threshold,
                "zero_background": zero_background,
                "threshold_unit": "whatever unit the input flow accumulation is in",
            },
            inputs=[InputRecord.from_path(flow_accumulation_path, crs=crs)],
            engine=_engine_info(),
        )
        record.crs_decisions = {
            "analysis_crs": crs,
            "reason": "thresholding an existing grid changes values, not geometry",
        }
        record.notes.append(
            "the threshold is compared against the input's own values: if that grid "
            "came from d8_flow_accum with out_type='cells' the unit is a cell count, "
            "and with 'sca' it is a specific contributing area — the two differ by "
            "orders of magnitude and produce different networks from the same number"
        )
        # `wbe.streams.extract_streams`, measured: the stub nests it under a
        # `network_extraction` sub-namespace that does not exist at runtime.
        result = wbe.streams.extract_streams(
            flow_accumulation=accumulation,
            threshold=threshold,
            zero_background=zero_background,
        )
        with verify.audit_on_failure(record, output_path, []):
            _write(wbe, result, output_path, flow_accumulation_path, record)

            meta = accumulation.metadata()
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=accumulation.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                value_range=None,
            )
        if note:
            record.notes.append(note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "extract_streams")
        return {
            "output": str(output_path),
            "threshold": threshold,
            "zero_background": zero_background,
            "provenance": str(manifest),
            "verified": True,
        }


# The sixteen curvature tools whitebox-workflows exposes, of which these six are
# the ones with an established meaning in terrain analysis. Verified against the
# installed package rather than the documentation (D-048).
#
# Call them through the CATEGORY path with keyword arguments, never through the
# flat `wbe.<tool>(...)` name -- and not because the flat form is deprecated: on
# this build it is disabled for SOME tools and works for others. `wbe.slope(dem)`
# runs; `wbe.d8_pointer(dem)` raises "Flat WbEnvironment tool methods are
# disabled in this build"; `dir(wbe)` lists both identically. A per-tool
# inconsistency cannot be learned once and reapplied, so the rule here is the
# category path everywhere, which worked for every tool measured. The category
# form also refuses positional arguments, hence `input=` (`points=` for IDW).
#
# One operation with a `kind`, not six tools: two tools that both apply to a DEM
# and return different numbers for the same question are exactly what invariant 6
# is about.
CURVATURE_KINDS = {
    "profile": "profile_curvature",
    "plan": "plan_curvature",
    "tangential": "tangential_curvature",
    "mean": "mean_curvature",
    "gaussian": "gaussian_curvature",
    "total": "total_curvature",
}

# D8 and Rho8 encode directions as powers of two; a value outside the set is not
# a direction. Dinf and Fd8 write continuous aspect-like values instead, so the
# set check does not apply to them.
FLOW_DIRECTION_METHODS = {"d8": "d8_pointer", "rho8": "rho8_pointer",
                          "dinf": "dinf_pointer", "fd8": "fd8_pointer"}
_POINTER_CODES = {0.0, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0}

# The two direction tables a pointer raster can hold, named after what they ARE
# rather than after who uses them -- which is also the more useful name, since a
# consumer needs the table and not the brand.
#
# Both were MEASURED on whitebox-workflows 2.0.6, one direction at a time: a 5x5
# grid at 200 with the centre at 100 and exactly one neighbour at 0, so the code
# the centre receives names that neighbour and nothing else.
#
# `northeast_first` is what the engine writes by default, and it is also what
# whitebox documents for its own default: `d8_pointer.rs` carries the grid
#
#     | 64 | 128 | 1  |      northwest 64   north 128   northeast 1
#     | 32 |  0  | 2  |      west      32       .       east      2
#     | 16 |  8  | 4  |      southwest 16   south   8   southeast 4
#
# and calls it "a clockwise, base-2 numeric index convention". `east_first` is
# the table most desktop GIS software uses, and the engine's alternate mode
# reproduces it exactly as that software documents it.
#
# Until 2026-09-22 these lines said the opposite: that the manual documented
# east=1, northeast=2, north=4, counter-clockwise from east, and that the
# mismatch was a defect in whitebox's documentation of its own default. That
# table belongs to nobody -- not to whitebox, not to ESRI -- and the paragraph
# opened with "Both were MEASURED", which was true of the engine's table and
# asserted of the manual's. A measurement and an assertion sewn into one
# sentence, where the verb of the first covers the second, in a public file
# accusing an upstream project of a defect it does not have.
#
# The reason for writing the whole table into the manifest is stronger than the
# claim it replaces. Both conventions are clockwise and use the SAME set of
# codes -- the powers of two from 1 to 128 -- one position apart. So reading a
# pointer under the wrong table leaves every cell on a legal direction and
# rotates the entire drainage network by 45 degrees, uniformly, in one turn.
# Nothing raises, no set check can see it, and a rotated network still looks
# like a drainage network. The name of a table cannot be checked against the
# file; the table can.
POINTER_ENCODINGS = {
    "northeast_first": {
        "northeast": 1, "east": 2, "southeast": 4, "south": 8,
        "southwest": 16, "west": 32, "northwest": 64, "north": 128,
    },
    "east_first": {
        "east": 1, "southeast": 2, "south": 4, "southwest": 8,
        "west": 16, "northwest": 32, "north": 64, "northeast": 128,
    },
}


def curvature(
    dem_path: str,
    output_path: str,
    kind: str,
    z_factor: float = 1.0,
) -> dict[str, Any]:
    """Surface curvature from a DEM. The kind is REQUIRED: they mean different things.

    `profile` is curvature along the slope (where flow accelerates), `plan` is
    curvature across it (where flow converges), and they answer opposite
    questions about the same cell — a hillslope can be convex in profile and
    concave in plan at once. `mean`, `gaussian`, `total` and `tangential` are
    the standard invariants. There is no default because a caller who wanted
    convergence and got acceleration receives a plausible raster of the wrong
    quantity, with no way to tell.

    Geographic-CRS DEMs are refused, for the same reason as `slope`: degree cells
    with metre elevations make the second derivative wrong everywhere.
    """
    if kind not in CURVATURE_KINDS:
        raise ValueError(
            f"kind must be one of {sorted(CURVATURE_KINDS)}, got {kind!r}. There is no "
            "default: profile curvature is along the slope and plan curvature is across "
            "it, and they answer opposite questions about the same cell."
        )
    tool = CURVATURE_KINDS[kind]
    return _derivative(
        "curvature",
        dem_path,
        output_path,
        parameters={"kind": kind, "z_factor": z_factor, "tool": tool},
        call=lambda wbe, dem: getattr(wbe.terrain.derivatives, tool)(
            input=dem, z_factor=z_factor
        ),
        # Curvature is a second derivative in units of 1/length: unbounded, and
        # a range check would either pass everything or reject real terrain.
        value_range=None,
    )


def flow_direction(
    dem_path: str,
    output_path: str,
    method: str = "d8",
    encoding: str = "northeast_first",
) -> dict[str, Any]:
    """Flow direction from a DEM, as a pointer raster with its direction table.

    `d8` sends all of a cell's water to its steepest neighbour and `dinf`
    splits it between two, which is the difference between a drainage network
    that looks like a line and one that looks like a fan. `rho8` is D8 with a
    stochastic tie-break; `fd8` spreads over all downslope neighbours.

    A pointer raster is a grid of small integers whose MEANING lives outside the
    file, and the two conventions in use disagree on every direction: in
    `northeast_first` (this engine's default) 1 is northeast, in `east_first`
    (what most desktop GIS software writes) 1 is east. Read a raster with the
    wrong table and every cell points somewhere else -- the network stays
    connected, stays plausible, and drains the wrong way. Nothing in a GeoTIFF
    says which table it holds, so the manifest carries the whole table, by
    direction name, for the encoding actually used: a consumer never has to know
    which engine wrote the file, and never has to trust a manual. This engine's
    own manual documents its default table backwards (see POINTER_ENCODINGS).

    `dinf` and `fd8` do not use the table at all, so for those it is not
    recorded and `encoding` is refused rather than ignored.
    """
    if method not in FLOW_DIRECTION_METHODS:
        raise ValueError(
            f"method must be one of {sorted(FLOW_DIRECTION_METHODS)}, got {method!r}"
        )
    if encoding not in POINTER_ENCODINGS:
        raise ValueError(
            f"encoding must be one of {sorted(POINTER_ENCODINGS)}, got {encoding!r}"
        )
    tool = FLOW_DIRECTION_METHODS[method]
    coded = method in ("d8", "rho8")
    if encoding != "northeast_first" and not coded:
        raise ValueError(
            f"encoding={encoding!r} is meaningless for method={method!r}: {method} writes "
            "continuous aspect-like values, not direction codes, so there is no table to "
            "choose. Use method='d8' or 'rho8', or leave the default encoding."
        )

    def codes_are_directions(written: str) -> list[verify.Check]:
        if not coded:
            return []
        wb = _require()
        wbe = wb.WbEnvironment()
        wbe.verbose = False
        out = wbe.read_raster(str(written))
        meta = out.metadata()
        arr = out.to_numpy(dtype="float64")
        if math.isnan(meta.nodata):
            valid = arr[~np.isnan(arr)]
        else:
            valid = arr[(arr != meta.nodata) & ~np.isnan(arr)]
        seen = {float(v) for v in np.unique(valid)}
        stray = sorted(seen - _POINTER_CODES)
        return [
            verify.Check(
                # A range check would pass a 3: it is between 0 and 128 and it is
                # not a direction. The valid codes are a SET.
                "values_in_expected_range",
                not stray,
                f"codes {sorted(seen)} are powers of two" if not stray
                else f"{stray} are not D8 direction codes",
            )
        ]

    parameters: dict[str, Any] = {"method": method, "tool": tool}
    if coded:
        # The table itself, not its name. The two conventions share the same set
        # of codes one position apart, so the name is the only thing that tells
        # them apart and the name is not in the raster: a consumer that guesses
        # wrong reads a network rotated 45 degrees with every cell on a legal
        # direction. See POINTER_ENCODINGS.
        parameters["encoding"] = encoding
        parameters["direction_codes"] = dict(POINTER_ENCODINGS[encoding])

    def run_tool(wbe, dem):
        tool_fn = getattr(wbe.hydrology.flow_routing, tool)
        if coded:
            # The engine's own flag name is its vendor's; the value is what matters.
            return tool_fn(input=dem, esri_pntr=(encoding == "east_first"))
        return tool_fn(input=dem)

    return _derivative(
        "flow_direction",
        dem_path,
        output_path,
        parameters=parameters,
        call=run_tool,
        value_range=None,
        extra_checks=codes_are_directions,
    )


def euclidean_distance(input_path: str, output_path: str) -> dict[str, Any]:
    """Distance from every cell to the nearest non-zero cell, in the CRS's units.

    The unit is the raster's own horizontal unit, which is why a geographic CRS
    is refused: a distance in degrees is not a distance, it varies with latitude,
    and it comes back as a number that looks like metres.

    Whitebox treats the NON-ZERO cells as the sources, so a mask where features
    are 1 and background is 0 behaves as expected. A mask whose background is
    nodata rather than 0 does not, and that is worth knowing before reading the
    output as a proximity surface.
    """
    wb = _require()
    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, input_path) as (source, crs, geographic, input_note):
        if geographic:
            raise ValueError(
                "euclidean_distance on a geographic CRS would measure in degrees, which "
                "is not a length: a degree of longitude is 111 km at the equator and "
                "83 km in Rome. Reproject to a projected CRS first."
            )
        record = ProvenanceRecord(
            operation="euclidean_distance",
            parameters={"source_cells": "non-zero"},
            inputs=[InputRecord.from_path(input_path, crs=crs)],
            engine=_engine_info(),
        )
        record.crs_decisions = {
            "analysis_crs": crs,
            "reason": "distance is measured in the raster's own projected units; a "
            "geographic CRS is refused because degrees are not a length",
        }
        meta = source.metadata()
        result = wbe.raster.distance_cost.euclidean_distance(input=source)
        with verify.audit_on_failure(record, output_path, []):
            _write(wbe, result, output_path, input_path, record)
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=source.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                # Both ends are closed form from the grid: a distance cannot be
                # negative, and nothing in the raster can be farther from a source
                # than the grid's own diagonal.
                value_range=(
                    0.0,
                    math.hypot(
                        meta.rows * abs(meta.resolution_y),
                        meta.columns * abs(meta.resolution_x),
                    ),
                ),
            )
        if input_note:
            record.notes.append(input_note)
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "euclidean_distance")
        return {
            "output": str(output_path),
            "units": "the raster's own horizontal units",
            "provenance": str(manifest),
            "verified": True,
        }


def viewshed(
    dem_path: str,
    stations_path: str,
    output_path: str,
    station_height: float,
) -> dict[str, Any]:
    """How many observing stations can see each cell.

    **The output is a COUNT, not a yes/no**, and that sentence is here because
    the tool's own documentation says the opposite. The Whitebox help for
    Viewshed states "The output image will be a Boolean raster, containing 1's
    and 0's"; measured on the installed 2.0.6 with two stations on flat ground,
    every cell comes back `2.0`. The classic Rust source settles it — it calls
    `output.increment(...)`, not `set_value`. A caller who trusted the manual
    and thresholded at `> 0` would be right by accident, and one who summed the
    raster expecting an area would be wrong by a factor of the station count.
    This is the second place where this library's prose describes the reverse of
    what its code does; the first was the D8 pointer table (see
    `POINTER_ENCODINGS`), and the lesson both times was to measure.

    `station_height` has no default even though the library defaults it to 2.0,
    because **the unit is the DEM's Z unit, not metres**: on a DEM in US survey
    feet, 2.0 is two feet, and an eye height of 0.6 m would be a silent error
    with a plausible-looking viewshed to show for it. There is no target height
    in this tool — only the observer is raised — so a radio mast at the far end
    is not modelled. Use `line_of_sight` for a two-ended check.

    A geographic CRS is refused: the height is in Z units while the cell size is
    in degrees, so the vertical and horizontal are on different scales and the
    horizon comes out at the wrong distance.
    """
    wb = _require()
    if station_height < 0:
        raise ValueError(f"station_height must be zero or positive, got {station_height}")

    stations = readers.read_vector(stations_path)
    if stations.crs is None:
        raise ValueError(
            readers.no_crs_message(
                stations, f"{stations_path} has no CRS — cannot place the observing "
                "stations on the DEM."
            )
        )
    kinds = set(stations.geom_type.dropna().unique())
    if not kinds.issubset({"Point"}):
        raise ValueError(
            f"observing stations must be Point geometries, got {sorted(kinds)}"
        )
    if stations.empty:
        raise ValueError(
            f"{stations_path} holds no stations, so there is nothing to see from. "
            "The output would be a grid of zeros, which is not the same answer as "
            "'nothing is visible'."
        )

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, dem_path) as (dem, crs, geographic, input_note):
        if geographic:
            raise ValueError(
                "viewshed on a geographic CRS would compare a station height in the "
                "DEM's Z unit against cell sizes in degrees, so the horizon lands at "
                "the wrong distance. Reproject the DEM to a projected CRS first."
            )
        record = ProvenanceRecord(
            operation="viewshed",
            parameters={
                "station_height": station_height,
                "height_unit": "the DEM's Z unit, not necessarily metres",
                "n_stations": len(stations),
                "output_meaning": "number of stations that can see the cell",
            },
            inputs=[
                InputRecord.from_path(dem_path, crs=crs, argument="dem_path"),
                InputRecord.from_path(
                    stations_path, crs=verify.crs_label(stations.crs), argument="stations_path"
                ),
            ],
            engine=_engine_info(),
        )
        aligned = not verify.same_crs(stations.crs, crs)
        record.crs_decisions = alignment_decisions(
            crs,
            "stations brought to the DEM CRS so each one stands on the cell it "
            "actually occupies"
            if aligned
            else "stations and DEM share the same CRS",
            [("stations_path", stations.crs)] if aligned else [],
        )
        if aligned:
            stations = stations.to_crs(crs)

        with verify.audit_on_failure(record, output_path, []):
            ws = workspace.root()
            with tempfile.TemporaryDirectory(dir=str(ws) if ws else None) as tmp:
                shp = Path(tmp) / "stations.shp"
                stations.to_file(shp)
                vec = wbe.read_vector(str(shp))
                seen = wbe.terrain.visibility.viewshed(
                    input=dem, stations=vec, height=station_height
                )
                _write(wbe, seen, output_path, dem_path, record)

            meta = dem.metadata()
            checks = _raster_checks(
                wbe,
                output_path,
                expect_epsg=dem.crs_epsg(),
                expect_shape=(meta.rows, meta.columns),
                # 0..n, because it counts. Written as the station count rather than
                # 1.0 precisely because the documentation says 1.0: if a future
                # version really does turn it into a boolean, this range still
                # passes and the note below stops being true — so there is also a
                # test that asserts the count semantics directly.
                value_range=(0.0, float(len(stations))),
            )
        if input_note:
            record.notes.append(input_note)
        record.notes.append(
            "each cell holds the NUMBER of stations that can see it, not a 0/1 flag: "
            "measured on whitebox-workflows 2.0.6, against its own documentation"
        )
        manifest = record.add_verification(checks).finish().write_for(output_path)
        verify.enforce(checks, "viewshed")
        return {
            "output": str(output_path),
            "stations": len(stations),
            "station_height": station_height,
            "shape": [meta.rows, meta.columns],
            "provenance": str(manifest),
            "verified": True,
        }


def idw_interpolation(
    points_path: str,
    output_path: str,
    field_name: str,
    cell_size: float,
    weight: float = 2.0,
    radius: float = 0.0,
    min_points: int = 0,
) -> dict[str, Any]:
    """Inverse-distance-weighted surface from a point layer. The field is REQUIRED.

    `field_name` has no default here because of the library's default: whitebox
    interpolates FID when you do not say otherwise, which produces a smooth,
    plausible and perfectly meaningless surface of ROW NUMBERS. Nothing raises,
    the raster renders, and a caller who forgot the argument gets a map of the
    order the points happened to be stored in.

    `weight` is the distance exponent: 2 is the usual choice, and higher values
    make the surface flatter between points and peakier at them. It is recorded,
    because an IDW surface without its exponent cannot be reproduced.

    A geographic CRS is refused, for the same reason `euclidean_distance`
    refuses one and with more consequence: IDW weights every sample by its
    distance, and in degrees at 41 degrees north a degree of longitude covers
    0.75 of the ground a degree of latitude does. The weighting comes out
    anisotropic by a third, the surface is stretched east-west, and nothing in
    the output says so — it renders, it is smooth, and it is wrong in a way that
    looks like terrain. Until 0.3.0 this ran happily on EPSG:4326 and recorded
    "the cell size is read in that CRS's units" as though that settled it.
    """
    wb = _require()
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")
    if not field_name or not str(field_name).strip():
        raise ValueError(
            "field_name is required: whitebox interpolates FID by default, which "
            "produces a smooth and meaningless surface of row numbers, with no warning."
        )
    # Checked BEFORE the engine runs, and named as the INPUT's problem. The
    # output-side `crs_present` check does catch a CRS-less input, but only
    # afterwards, and its message sends the caller to look at the output — the
    # wrong artifact.
    layer = readers.read_vector(points_path)
    if layer.crs is None:
        raise ValueError(
            readers.no_crs_message(
                layer,
                f"{points_path} declares no CRS, so the distances IDW weights by "
                "mean nothing.",
            )
        )
    crs = layer.crs
    if crs.is_geographic:
        raise ValueError(
            "idw_interpolation on a geographic CRS would weight samples by a distance "
            "in degrees, which is not a distance: a degree of longitude is 111 km at "
            "the equator and 83 km in Rome, so the weighting comes out anisotropic by "
            "a third and the surface is stretched east-west with nothing to show for "
            "it. Reproject to a projected CRS first."
        )

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    # No `_needs_plain_copy` here, unlike the DEM path this was copied from: that
    # helper opens a path with rasterio looking for a TIFF predictor, which on a
    # vector layer raises and is swallowed, so the branch was permanently dead —
    # and had it ever fired it would have written a single-band GeoTIFF in place
    # of the point layer. Removed rather than guarded.
    points = wbe.read_vector(str(points_path))
    record = ProvenanceRecord(
        operation="idw_interpolation",
        parameters={
            "field_name": field_name,
            "cell_size": cell_size,
            "weight": weight,
            "radius": radius,
            "min_points": min_points,
        },
        inputs=[InputRecord.from_path(points_path, crs=verify.crs_label(crs))],
        engine=_engine_info(),
    )
    result = wbe.raster.general.idw_interpolation(
        points=points,
        field_name=field_name,
        weight=weight,
        radius=radius,
        min_points=min_points,
        cell_size=cell_size,
    )
    meta = result.metadata()
    epsg = result.crs_epsg()
    # Decided before the write, so a record written on failure carries it.
    record.crs_decisions = {
        "analysis_crs": f"EPSG:{epsg}" if epsg else verify.crs_label(crs),
        "reason": "the surface is built in the point layer's own CRS, which is "
        "projected — refused otherwise — so the cell size and the distance "
        "weighting are both in that CRS's linear unit",
    }
    with verify.audit_on_failure(record, output_path, []):
        wbe.write_raster(result, str(output_path))
        checks = _raster_checks(
            wbe,
            output_path,
            expect_epsg=epsg,
            expect_shape=(meta.rows, meta.columns),
            value_range=None,
        )
    manifest = record.add_verification(checks).finish().write_for(output_path)
    verify.enforce(checks, "idw_interpolation")
    return {
        "output": str(output_path),
        "field_name": field_name,
        "cell_size": cell_size,
        "weight": weight,
        "shape": [meta.rows, meta.columns],
        "provenance": str(manifest),
        "verified": True,
    }


#: Half a cell, and where it comes from. Whitebox places a contour vertex at the
#: WEST edge of the cell whose value it contours, not at the cell's centre —
#: measured on the installed 2.0.6 with a planar ramp `z = column index`, origin
#: (1000, 5000), cells of 10 m: the contour for height 3 came back at x = 1030
#: where the centre of the column holding 3 is x = 1035. Exactly half a cell, in
#: both axes, on every contour.
#:
#: Which one is right is not a matter of taste. The raster declares
#: `AREA_OR_POINT=Area`, so each value is a sample at its cell's centre, and the
#: isoline of a field sampled at centres passes through the centre of the cell
#: holding that value. On a 30 m DEM the difference is 15 m of horizontal
#: position on every contour — plausible, well-formed, and wrong, which is the
#: third time this library's behaviour has diverged from its description here
#: (see the TIFF predictor and the D8 pointer table).
CONTOUR_REGISTRATION_SHIFT = 0.5


def contour_lines(
    dem_path: str,
    output_path: str,
    interval: float,
    base: float = 0.0,
    smoothing: int = 0,
) -> dict[str, Any]:
    """Isolines of a surface, at a fixed interval. Requires the [whitebox] extra.

    The oldest way of drawing terrain and still the one a person reads fastest.
    Each output line carries the elevation it traces, in the DEM's own Z unit.

    **Two defaults here are deliberately not the library's.**

    `smoothing=0` turns off a filter Whitebox applies by default at size 9. That
    filter moves vertices to make the line look better, and a contour that has
    been prettified no longer passes through the elevation it claims. Smoothing
    is available and it is recorded in the manifest when used, because a
    cartographic output and a measurement are different products and the reader
    is entitled to know which one this is.

    And the geometry is shifted half a cell east and south from what the library
    returns. That is a correction, not a preference: Whitebox places contour
    vertices on the west edge of a cell rather than at its centre, which puts
    every contour on a 30 m DEM 15 m from where the elevation it names actually
    occurs. The correction is verified rather than trusted — the DEM is sampled
    at the finished vertices and the elevation read back must equal the
    contour's own height. If a future version of the library changes its
    registration, that check fails loudly instead of silently double-correcting.

    A geographic CRS is refused: an interval is a height and the vertices are a
    position, and a contour computed on degrees comes back stretched by the
    latitude it happens to be at.
    """
    wb = _require()
    if interval <= 0:
        raise ValueError(f"interval must be positive, got {interval}")
    if smoothing < 0:
        raise ValueError(f"smoothing must be zero or positive, got {smoothing}")

    wbe = wb.WbEnvironment()
    wbe.verbose = False
    with _read_dem(wbe, dem_path) as (dem, crs, geographic, input_note):
        if geographic:
            raise ValueError(
                "contour_lines on a geographic CRS would place vertices in degrees "
                "while the interval is a height, so the contours come back stretched "
                "by the latitude. Reproject the DEM to a projected CRS first."
            )
        meta = dem.metadata()
        ws = workspace.root()
        # The scratch directory is opened BEFORE the call, and that is the
        # whole point of this shape. `contours_from_raster` is the one
        # file-based tool among the fifteen Whitebox tools MapSmith calls: it
        # writes its result and reads it back, and with no path given it
        # writes `contours_from_raster.{shp,shx,dbf,prj}` into
        # `WbEnvironment().working_directory`, which defaults to the PROCESS
        # working directory. With a workspace set and the server started
        # anywhere else, that is four files outside the jail SECURITY.md says
        # nothing may write outside of. Measured on 2026-09-06, and invisible
        # for weeks because `.gitignore` covers `*.shp`.
        #
        # `output_path=` and not `output=`: the shipped type stub declares
        # `output`, and passing it raises TypeError. The runtime signature is
        # the authority, read from `__text_signature__`. Fourth measured
        # divergence between this library's declaration and its behaviour,
        # after the TIFF predictor, the D8 table and contour registration.
        with tempfile.TemporaryDirectory(dir=str(ws) if ws else None) as tmp:
            written = Path(tmp) / "contours.shp"
            wbe.contours_from_raster(
                dem,
                contour_interval=float(interval),
                base_contour=float(base),
                smoothing_filter_size=int(smoothing),
                output_path=str(written),
            )
            # No `write_vector` afterwards: the tool has already written this
            # file, and writing it a second time is a second chance to differ.
            # Verified identical on 2026-09-06 -- same rows, same columns,
            # same geometries, same heights.
            # Through the one reader, even though this file is three lines old
            # and we wrote it ourselves. The rule is absolute on purpose: #28
            # was "open a vector file" existing as six copies of one decision,
            # and a seventh copy with a good excuse is still a seventh copy.
            lines = readers.read_vector(str(written))

    if lines.empty:
        raise ValueError(
            f"no contour crosses this DEM at an interval of {interval} from a base "
            f"of {base}. The surface spans less than one interval, or the base is "
            "outside its range."
        )

    # The engine returns the west/north EDGE of the cell it reads, so the
    # centre -- where the value is -- is half a cell south-east: +0.5. Always,
    # since 2026-09-25: a point-registered DEM reaches the engine as an area
    # copy on GDAL's geotransform (`_needs_plain_copy`), whose cell centres are
    # the samples. Until then this chose -0.5 for a Point DEM, on the premise
    # that GDAL leaves a PixelIsPoint geotransform alone; it does not (RFC 33),
    # and the branch was unreachable anyway, because `_read_dem` refused every
    # Point DEM before it (D-096). The check below reads the DEM back at the
    # vertices, so a wrong sign cannot pass in silence.
    import rasterio

    with rasterio.open(dem_path) as probe:
        placement = grid.registration(probe)
        registration_note = grid.describe(probe)
    shift_x = CONTOUR_REGISTRATION_SHIFT * float(meta.resolution_x)
    shift_y = -CONTOUR_REGISTRATION_SHIFT * float(meta.resolution_y)
    height_column = "HEIGHT" if "HEIGHT" in lines.columns else lines.columns[1]
    lines = lines.rename(columns={height_column: "elevation"})
    lines["geometry"] = lines.geometry.translate(xoff=shift_x, yoff=shift_y)
    lines = lines[["elevation", "geometry"]].set_crs(crs, allow_override=True)

    # The record exists BEFORE the write. It used to be built after it, so a
    # write that died halfway left contour lines on disk with nothing to write
    # beside them: the failure net needs a record to put in the manifest.
    record = ProvenanceRecord(
        operation="contour_lines",
        parameters={
            "interval": interval,
            "base": base,
            "smoothing_filter_size": smoothing,
            "z_unit": "the DEM's own Z unit, not necessarily metres",
            "registration_correction": (
                f"{shift_x:+g}, {shift_y:+g} — the engine places contour vertices "
                "on the west/north edge of a cell, half a cell from the centre where "
                f"the value it names sits (input registration: {placement})"
            ),
            **registration_note,
        },
        inputs=[InputRecord.from_path(dem_path, crs=crs)],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": crs,
        "reason": "contours are traced in the DEM's own grid, with no reprojection, "
        "so the vertices are in the DEM's coordinates",
    }
    if input_note:
        record.notes.append(input_note)
    if smoothing:
        record.notes.append(
            f"smoothing_filter_size={smoothing} was applied, so vertices have been "
            "moved to make the lines look better. These contours are a drawing, not "
            "a measurement: a vertex no longer sits exactly on the elevation it names."
        )

    with verify.audit_on_failure(record, output_path, []):
        _write_vector(lines, output_path)
        # The check that looks at the number: read the DEM back at the finished
        # vertices and compare with the elevation each line claims. This is what
        # `measure_area` does for area and what nothing did for terrain until now.
        sampled = _sample_along(dem_path, lines)
        worst = max((abs(value - height) for value, height in sampled), default=0.0)
    record.notes.append(
        f"the DEM read back at {len(sampled)} contour vertices differs from the "
        f"elevation each line claims by at most {worst:.6g} (Z unit)"
    )

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="contour_lines",
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=crs,
                expect_geometry={"LineString", "MultiLineString"},
                on_empty="fail",
            ),
            # Every contour's height must sit on the interval grid the caller
            # asked for. An engine that quietly rounds or offsets the series
            # produces a legible map of the wrong levels.
            verify.Check(
                "x-mapsmith:every_contour_sits_on_the_requested_interval",
                all(
                    abs(
                        (float(height) - base) / interval
                        - round((float(height) - base) / interval)
                    )
                    < 1e-6
                    for height in lines["elevation"]
                ),
                f"{len(lines)} contour(s) against base {base} step {interval}",
            ),
            # The one that catches the registration. Smoothing moves vertices on
            # purpose, so the tolerance opens when it is on — and the check stops
            # being critical, because then the line IS a drawing.
            verify.Check(
                "x-mapsmith:the_dem_at_a_contour_vertex_is_the_contour_height",
                worst <= (interval / 2 if smoothing else max(interval * 0.02, 1e-6)),
                f"largest disagreement {worst:.6g} over {len(sampled)} sampled "
                f"vertices, against an interval of {interval}",
                critical=not smoothing,
                hint="a disagreement of about half an interval means the engine's "
                "grid registration changed and the half-cell correction is now "
                "wrong; one of about a whole interval means the base is off by one",
            ),
        ],
    )
    return {
        "output": str(output_path),
        "contours": len(lines),
        "levels": sorted({float(h) for h in lines["elevation"]}),
        "interval": interval,
        "base": base,
        "smoothing_filter_size": smoothing,
        "vertices_checked": len(sampled),
        "largest_disagreement_with_the_dem": round(worst, 9),
        "provenance": str(manifest),
        **extras,
    }


def _write_vector(gdf: Any, output_path: str) -> None:
    if str(output_path).endswith(".parquet"):
        gdf.to_parquet(output_path)
    else:
        gdf.to_file(output_path)


def _sample_along(dem_path: str, lines: Any, limit: int = 400) -> list[tuple[float, float]]:
    """(elevation read from the DEM, elevation the contour claims) at its vertices.

    Bilinear, through the sampling engine's reader rather than rasterio's own
    `sample`, because that one hands back the nodata VALUE where there is no
    data and -9999 compared against a contour height would fail this check for
    the wrong reason. Capped: this is a spot check, and reading every vertex of
    a national DEM's contours to make a point is not worth the minutes.
    """
    import rasterio

    from .sampling import _read_at

    xs: list[float] = []
    ys: list[float] = []
    heights: list[float] = []
    for _, row in lines.iterrows():
        geometry = row.geometry
        parts = (
            [geometry] if geometry.geom_type == "LineString" else list(geometry.geoms)
        )
        for part in parts:
            for x, y, *_ in part.coords:
                xs.append(float(x))
                ys.append(float(y))
                heights.append(float(row["elevation"]))
    if len(xs) > limit:
        step = len(xs) // limit
        xs, ys, heights = xs[::step], ys[::step], heights[::step]

    with rasterio.open(dem_path) as src:
        values = _read_at(src, 1, xs, ys, "bilinear")
    return [
        (float(value), height)
        for value, height in zip(values, heights, strict=True)
        if value is not None
    ]
