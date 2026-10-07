"""Reading a surface where somebody stands, walks, or looks.

Three operations that all come down to the same question — what does the raster
say at this place — and differ in what "this place" means: a set of points, a
line walked at a fixed step, or the sight line between two positions.

They exist because the discovery benchmark asked for them in the words of people
who had the problem: *"my total station elevations along the centerline are
consistently two tenths higher than the city's surface"*, *"elevation at every 20
metres along the centreline so I can plot the profile"*, *"line of sight check,
this site to that site, is the ridge blocking it"*. Both independent labellers
marked all three `none`: the catalogue could not serve them.

The recurring hazard here is the silent null. A point outside the raster, or on a
nodata cell, samples to nothing — and a table with nulls in it looks exactly like
a table without them until somebody averages it. So every operation in this
module counts what it could not read and puts that count in the manifest as a
check, not a footnote.
"""

from __future__ import annotations

import bisect
import math
from itertools import pairwise
from typing import Any

import geopandas as gpd

from .. import readers, verify
from ..provenance import InputRecord, ProvenanceRecord, alignment_decisions

#: How a value is read between cell centres.
#:
#: `nearest` is the value of the cell the position falls in — right for class
#: codes, land cover, anything where an average of 3 and 5 is not a 4.
#: `bilinear` interpolates the four surrounding cell centres, which is right for
#: a continuous surface and is what a survey comparison needs: a total station
#: shot does not land on a cell centre, and snapping it to one introduces up to
#: half a cell of horizontal error before the vertical difference is computed.
SAMPLING_METHODS = ("nearest", "bilinear")

#: Metres per unit, for the heights a DEM stores. A gradient divides a rise by
#: a length, and the two come from different files: the length from the line's
#: CRS, the rise from the raster's values, which almost never declare a unit.
#: A State Plane line in US survey feet over a DEM in metres gives a grade 3.28
#: times too steep, plausible on every point, with nothing to show for it.
HEIGHT_UNITS = {"metre": 1.0, "foot": 0.3048, "US survey foot": 1200 / 3937}

#: Mean Earth radius, metres (IUGG). Used only for the curvature drop in
#: `line_of_sight`, where the alternative is silently pretending the planet is
#: flat.
EARTH_RADIUS_M = 6_371_008.8

#: Standard atmospheric refraction coefficient. Light bends downward, so a
#: target is visible slightly further than geometry alone would allow; 0.13 is
#: the value the surveying literature uses for ordinary daytime conditions and
#: the one every GIS viewshed implementation defaults to.
REFRACTION_COEFFICIENT = 0.13


def _require_rasterio():
    try:
        import rasterio
    except ImportError as exc:  # pragma: no cover - exercised by the extra guard
        raise ImportError(
            "This operation needs rasterio: pip install mapsmith[raster]"
        ) from exc
    return rasterio


def _engine_info() -> dict[str, str]:
    rasterio = _require_rasterio()
    return {"name": "rasterio", "version": rasterio.__version__}


def _read_at(dataset: Any, band: int, xs, ys, method: str) -> list[float | None]:
    """Values at map coordinates, or None where there is nothing to read.

    Written here rather than taken from `dataset.sample` because that helper
    returns the nodata VALUE rather than a null, and a nodata value of -9999
    averaged into a profile is the silent error this module exists to avoid.
    """
    import numpy as np

    from .. import grid

    array = dataset.read(band, masked=True)
    # `array.mask` is the scalar `np.ma.nomask` when nothing is masked, and
    # indexing a scalar raises — so a raster with no nodata cells at all would
    # crash the reader that exists to handle nodata. `getmaskarray` always
    # returns a full boolean array.
    mask = np.ma.getmaskarray(array)
    inverse = ~dataset.transform
    # Where the values sit inside their cells: the centre, under either
    # registration, because GDAL has already shifted a point-registered file's
    # geotransform so its cells are centred on the samples. This said 0.0 for a
    # Point file until 2026-09-25, which put every profile along a Copernicus
    # or USGS DEM half a cell north-west of the samples (D-096).
    shift = grid.offset(dataset)
    height, width = array.shape
    out: list[float | None] = []

    for x, y in zip(xs, ys, strict=True):
        column, row = inverse * (x, y)
        if method == "nearest":
            # The cell the position falls in: its sample is the nearest one.
            r, c = grid.sample_index(dataset, x, y)
            if not (0 <= r < height and 0 <= c < width) or mask[r, c]:
                out.append(None)
                continue
            out.append(float(array[r, c]))
            continue

        # Bilinear over the four surrounding SAMPLES: the centres of GDAL's
        # cells, at (column - 0.5, row - 0.5) in array space, for either
        # registration. The offset is the part that is easy to drop, and
        # dropping it shifts every value by half a pixel.
        #
        # Two different "outside" here, and conflating them was a bug. A
        # position outside the raster's EXTENT has no value and returns None.
        # A position inside the extent but within the outer half-cell has a
        # value and an incomplete stencil: its outer neighbours do not exist.
        # Refusing those would make the whole boundary ring of every raster
        # unreadable — a sight line to a target near the edge came back "outside
        # the raster" — so the stencil is clamped to the edge cell, which is what
        # GDAL does and what "the surface continues to the edge of the data"
        # means. Nodata inside the stencil still yields None: that is missing
        # data, not a boundary.
        if not (0 <= column < width and 0 <= row < height):
            out.append(None)
            continue
        cx, cy = column - shift, row - shift
        c0, r0 = math.floor(cx), math.floor(cy)
        fx, fy = cx - c0, cy - r0
        corners = []
        for dr, dc, weight in (
            (0, 0, (1 - fx) * (1 - fy)),
            (0, 1, fx * (1 - fy)),
            (1, 0, (1 - fx) * fy),
            (1, 1, fx * fy),
        ):
            if weight == 0.0:
                # A corner with no weight contributes nothing, so whether it is
                # nodata is not this sample's problem. Checking the mask first
                # threw away exact values: a point sitting on a cell centre has
                # three corners at weight zero, and one of them being nodata
                # returned None for a position whose value was right there — the
                # opposite of the loss this module exists to prevent, and it
                # inflated the very counter the check reads.
                continue
            r = min(max(r0 + dr, 0), height - 1)
            c = min(max(c0 + dc, 0), width - 1)
            if mask[r, c]:
                corners = []
                break
            corners.append(weight * float(array[r, c]))
        out.append(float(np.sum(corners)) if corners else None)

    return out


def _unreadable_check(values: list[float | None], total: int) -> verify.Check:
    """A null is data, and it has to be counted somewhere a reader will look.

    Not critical: sampling outside the raster is a legitimate thing to do on
    purpose, and refusing it would make the operation useless for exactly the
    case it is best at — comparing a survey against a surface that does not
    cover all of it. But a table with silent nulls averages to a number nobody
    can defend, so the count travels with the result.
    """
    missing = sum(1 for v in values if v is None)
    return verify.Check(
        "x-mapsmith:every_position_had_a_value",
        missing == 0,
        f"{missing} of {total} positions fell outside the raster or on nodata",
        critical=False,
    )


def sample_raster_at_points(
    raster_path: str,
    points_path: str,
    output_path: str,
    method: str,
    band: int = 1,
    column_name: str = "value",
) -> dict[str, Any]:
    """The raster's value at each point, with the ones it could not read counted.

    `method` has no default because the two are right for different data and the
    wrong one fails quietly: `bilinear` on land-cover codes invents classes that
    do not exist, and `nearest` on a survey comparison snaps each shot to a cell
    centre, adding up to half a cell of horizontal error to a vertical
    difference somebody is about to call a datum offset.

    Points that fall outside the raster, or on a nodata cell, come back with a
    null in `column_name` rather than the nodata value — and the count of them
    is a check in the manifest.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). After the extra guard,
    # never before it: a caller without `[raster]` has to hear about the
    # missing extra, not about a sidecar.
    from .. import grid

    grid.refuse_ambiguous_georeferencing(raster_path, "sample_raster_at_points")
    if method not in SAMPLING_METHODS:
        raise ValueError(
            f"method must be one of {list(SAMPLING_METHODS)}, got {method!r}. "
            "'nearest' for class codes, 'bilinear' for a continuous surface."
        )

    points = readers.read_vector(points_path)
    if points.crs is None:
        raise ValueError(
            readers.no_crs_message(
                points, f"{points_path} has no CRS, so its points cannot be placed "
                "on the raster."
            )
        )
    readers.refuse_missing_geometry(
        points, points_path,
        "A point with no position has no cell to read, and a null value for it would "
        "read like a point that fell outside the raster.",
    )
    kinds = set(points.geom_type.dropna().unique())
    if not kinds <= {"Point", "MultiPoint"}:
        raise ValueError(
            f"sample_raster_at_points needs a point layer; {points_path} holds "
            f"{sorted(kinds)}. For polygons use zonal_statistics, which weights "
            "partial pixels instead of reading one."
        )
    if column_name in points.columns:
        raise ValueError(
            f"the layer already has a column called {column_name!r}; pass a "
            "different column_name rather than overwriting it silently."
        )

    with rasterio.open(raster_path) as dataset:
        if band < 1 or band > dataset.count:
            raise ValueError(
                f"band {band} does not exist: {raster_path} has {dataset.count}. "
                "Bands are 1-based."
            )
        raster_crs = dataset.crs
        if raster_crs is None:
            raise ValueError(
                f"{raster_path} declares no CRS, so points cannot be placed on it. "
                "Assign one first."
            )
        record = ProvenanceRecord(
            operation="sample_raster_at_points",
            parameters={"method": method, "band": band, "column_name": column_name},
            inputs=[
                InputRecord.from_path(
                    raster_path, crs=verify.crs_label(raster_crs), argument="raster_path"
                ),
                InputRecord.from_path(
                    points_path, crs=verify.crs_label(points.crs), argument="points_path"
                ),
            ],
            engine=_engine_info(),
        )
        aligned = not verify.same_crs(points.crs, raster_crs)
        record.crs_decisions = alignment_decisions(
            raster_crs,
            "points brought to the raster's CRS so each one lands on the cell it "
            "actually falls in; the output keeps that CRS"
            if aligned
            else "points and raster share the same CRS",
            [("points_path", points.crs)] if aligned else [],
        )
        if aligned:
            points = points.to_crs(raster_crs)
        centroids = points.geometry.representative_point()
        values = _read_at(dataset, band, centroids.x, centroids.y, method)

    out = points.copy()
    out[column_name] = values
    # `audited` below covers the checks; this covers the write before it, which
    # left a dataset with no record when it raised (measured 2026-09-25). The
    # preconditions are computed BEFORE the write: as an argument to `audited`
    # they ran after it and outside both nets.
    pre = verify.verify_loaded_inputs("sample_raster_at_points", points_path=points)
    with verify.audit_on_failure(record, output_path, pre):
        _write_vector(out, output_path)

    read = sum(1 for v in values if v is not None)
    manifest, extras = verify.audited(
        record,
        output_path,
        operation="sample_raster_at_points",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(points.crs),
                expect_count=len(points),
            ),
            _unreadable_check(values, len(points)),
        ],
    )
    return {
        "output": str(output_path),
        "points": len(points),
        "sampled": read,
        "unreadable": len(points) - read,
        "column": column_name,
        "method": method,
        "provenance": str(manifest),
        **extras,
    }


def _write_vector(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    if str(output_path).endswith(".parquet"):
        gdf.to_parquet(output_path)
    else:
        gdf.to_file(output_path)


def elevation_profile(
    raster_path: str,
    line_path: str,
    output_path: str,
    spacing: float,
    method: str = "bilinear",
    band: int = 1,
    grade_base_length: float | None = None,
    grade_threshold_percent: float | None = None,
    grade_height_unit: str | None = None,
) -> dict[str, Any]:
    """One point every `spacing` along each line, and one at its far end,
    carrying the surface value.

    `spacing` is a length in the LINE's linear unit, so a geographic line is
    refused: 20 of a degree is not 20 metres, and the profile would come back
    with a distance axis that means nothing — plausibly, at a plausible-looking
    scale. The DEM may be in any CRS; only the sample points go there.

    Output is a point layer with `distance` (along the line, from its start),
    `value`, and `point_index`, ordered. Lines are handled one at a time and
    `line_index` says which one a point came from, so a network of centrelines
    profiles in a single call without the segments running together.

    With `grade_base_length`, the gradient ALONG the line: each point carries
    `grade_percent`, the rise over the window of that length starting there,
    and the result gives, per line, the steepest window, the total ascent and
    descent, and the stretches above `grade_threshold_percent`. Three things
    the caller would otherwise get wrong, all stated rather than defaulted:
    this is not `slope`, which is the steepest direction of the ground and not
    the track's (a line crossing a hillside obliquely climbs far less); the
    window SLIDES by `spacing`, which answers "the steepest of ANY stretch",
    where sampling every base length answers only a fixed-offset version of it;
    and the base length has no default, because 2.5% over 10 m and over 100 m
    are different questions on rough ground.

    The heights are assumed to be in metres only when the line's unit is the
    metre; otherwise `grade_height_unit` is required, because the rise and the
    run come from two files and only one of them states its unit. A grade is
    positive where the line climbs in the direction it was digitised. A window
    that runs over a gap between the parts of a multi-part line, or over a point
    the raster could not answer for, carries no grade.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). After the extra guard,
    # never before it: a caller without `[raster]` has to hear about the
    # missing extra, not about a sidecar.
    from .. import grid

    grid.refuse_ambiguous_georeferencing(raster_path, "elevation_profile")
    # `not (x > 0)` rather than `x <= 0`: NaN fails every comparison, so the
    # second form let it through, and infinity is refused beside it.
    if not (spacing > 0) or math.isinf(spacing):
        raise ValueError(f"spacing must be a positive finite length, got {spacing}")
    window = _grade_window(spacing, grade_base_length, grade_threshold_percent)
    if method not in SAMPLING_METHODS:
        raise ValueError(f"method must be one of {list(SAMPLING_METHODS)}, got {method!r}")

    lines = readers.read_vector(line_path)
    if lines.crs is None:
        raise ValueError(
            readers.no_crs_message(
                lines, f"{line_path} has no CRS, so a spacing in its units means nothing."
            )
        )
    kinds = set(lines.geom_type.dropna().unique())
    if not kinds <= {"LineString", "MultiLineString"}:
        raise ValueError(
            f"elevation_profile needs a line layer; {line_path} holds {sorted(kinds)}."
        )
    if lines.crs.is_geographic:
        raise ValueError(
            f"{line_path} is in a geographic CRS, so a spacing of {spacing} would be "
            f"{spacing} degrees — about {spacing * 111_000:,.0f} m of latitude, and a "
            "different distance at every longitude. Reproject to a projected CRS "
            "first, or the distance axis of the profile is meaningless."
        )
    from .. import limits

    limits.refuse_too_many_samples(
        (g.length for g in lines.geometry if g is not None and not g.is_empty),
        spacing, "elevation_profile",
    )
    scale, unit, heights_assumed = (
        _height_scale(lines.crs, grade_height_unit) if window else (1.0, "", False)
    )

    with rasterio.open(raster_path) as dataset:
        raster_crs = dataset.crs
        if raster_crs is None:
            raise ValueError(f"{raster_path} declares no CRS.")
        if band < 1 or band > dataset.count:
            raise ValueError(
                f"band {band} does not exist: {raster_path} has {dataset.count}."
            )
        parameters: dict[str, Any] = {"spacing": spacing, "method": method, "band": band}
        if window:
            parameters["grade_base_length"] = grade_base_length
            parameters["grade_window_steps"] = window
            if grade_threshold_percent is not None:
                parameters["grade_threshold_percent"] = grade_threshold_percent
            if grade_height_unit is not None:
                parameters["grade_height_unit"] = grade_height_unit
        record = ProvenanceRecord(
            operation="elevation_profile",
            parameters=parameters,
            inputs=[
                InputRecord.from_path(
                    raster_path, crs=verify.crs_label(raster_crs), argument="raster_path"
                ),
                InputRecord.from_path(
                    line_path, crs=verify.crs_label(lines.crs), argument="line_path"
                ),
            ],
            engine=_engine_info(),
        )
        working = lines
        aligned = not verify.same_crs(lines.crs, raster_crs)
        # Positions along the line are measured in the LINE's CRS, which is
        # projected (a geographic one is refused above), and only the points
        # are brought to the raster's CRS to be read. Until 2026-09-25 the
        # whole line was reprojected first and the spacing measured after:
        # with a DEM in degrees, `spacing=100` meant 100 degrees, and a 1000 m
        # line came back as ONE point, with nothing in the result to say so.
        record.crs_decisions = alignment_decisions(
            lines.crs,
            "distances along the line are measured in the line's own projected CRS; "
            "the sample points are brought to the raster's CRS only to read the values"
            if aligned
            else "line and raster share the same CRS",
        )
        if aligned:
            # Nothing of the caller's was reprojected for the result: the output
            # is written in the line's CRS, where the distances were measured.
            # What the operation transformed is the sample points, to the
            # raster's CRS, to read a value there -- which is exactly what the
            # specification's `source_crs` / `target_crs` / `transformation`
            # describe ("the coordinate system they were put into, when the
            # operation transformed them"); `output.crs` says where the result
            # is. Until 2026-09-25 this was `inputs_reprojected` naming the
            # line's own CRS, whose definition says the output never was in the
            # CRS it names. Not an extension key either: one here would be a
            # second name for `target_crs`.
            from .. import datum

            record.crs_decisions["source_crs"] = verify.crs_label(lines.crs)
            record.crs_decisions["target_crs"] = verify.crs_label(raster_crs)
            record.crs_decisions["transformation"] = datum.default_operation(
                lines.crs, raster_crs
            )

        rows = _profile_positions(working, spacing)
        read_x, read_y = [r["x"] for r in rows], [r["y"] for r in rows]
        if aligned and rows:
            from shapely.geometry import Point as _Point

            moved = gpd.GeoSeries(
                [_Point(x, y) for x, y in zip(read_x, read_y)], crs=lines.crs
            ).to_crs(raster_crs)
            read_x, read_y = list(moved.x), list(moved.y)
        values = _read_at(dataset, band, read_x, read_y, method)

    from shapely.geometry import Point

    columns: dict[str, Any] = {
        "line_index": [r["line_index"] for r in rows],
        "point_index": [r["point_index"] for r in rows],
        "distance": [r["distance"] for r in rows],
        "value": values,
    }
    grades: list[float | None] = []
    summary: list[dict[str, Any]] = []
    if window:
        grades = _grades(rows, values, window, grade_base_length, scale)
        columns["run_index"] = [r["run"] for r in rows]
        columns["grade_percent"] = [float("nan") if g is None else g for g in grades]
        summary = _grade_summary(rows, values, grades, grade_base_length, grade_threshold_percent)
        heights = unit if heights_assumed else grade_height_unit
        record.notes.append(
            f"grade_percent is the rise of the surface over a window of {grade_base_length} "
            f"{unit} along the line, starting at each point, divided by that length. The "
            f"raster's values are taken as heights in {heights}"
            + (
                " -- ASSUMED, because the line is in metres and the raster declares no "
                "unit for its values; pass grade_height_unit if they are not metres."
                if heights_assumed
                else ", as the caller stated."
            )
            + " A point carries no grade where its window runs past the end of its run "
            "(run_index: the connected pieces of a multi-part line), or over a point the "
            "raster could not answer for. total_ascent and total_descent are in the "
            "raster's height unit and skip the steps that touch such a point."
        )
    out = gpd.GeoDataFrame(
        columns,
        geometry=[Point(r["x"], r["y"]) for r in rows],
        crs=working.crs,
    )
    lengths_by_line = {
        i: float(g.length) for i, g in enumerate(working.geometry) if g is not None and not g.is_empty
    }
    regular = _stepping_is_regular(rows, spacing, lengths_by_line)
    pre = verify.verify_loaded_inputs("elevation_profile", line_path=working)
    with verify.audit_on_failure(record, output_path, pre):
        _write_vector(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="elevation_profile",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(working.crs),
                expect_count=len(rows),
            ),
            # Derived from the OUTPUT, not from the formula that produced it.
            # The first version compared `len(rows)` against
            # `floor(L/S) + 1` — the same expression the generator uses, written
            # twice — so it could not fail. What is checked now is a property of
            # the points on disk: each line starts at zero, the step between
            # consecutive points is the spacing, and the last one is the last
            # whole step that fits.
            verify.Check(
                "x-mapsmith:each_profile_starts_at_zero_and_steps_by_the_spacing",
                regular,
                _stepping_detail(rows, spacing, regular),
            ),
            _unreadable_check(values, len(rows)),
            *([_grades_follow_the_written_profile(output_path, window, grade_base_length, scale)]
              if window else []),
        ],
    )
    lengths = working.geometry.length
    result = {
        "output": str(output_path),
        "lines": len(working),
        "points": len(rows),
        "spacing": spacing,
        "total_length": float(lengths.sum()),
        "sampled": sum(1 for v in values if v is not None),
        "provenance": str(manifest),
        **extras,
    }
    if window:
        result["grade"] = summary
        result["grade_units"] = {
            "base_length": unit,
            "heights": unit if heights_assumed else grade_height_unit,
            "heights_assumed": heights_assumed,
        }
    return result


def _height_scale(line_crs: Any, height_unit: str | None) -> tuple[float, str, bool]:
    """(heights to line units factor, the line's unit, whether heights were assumed).

    Assumed only in the one case where assuming is ordinary: a line in metres,
    over a DEM whose values are, as nearly every DEM's are, metres. Anywhere
    else the caller says, because the 3.28 in a feet-over-metres grade is a
    number nobody would notice.
    """
    axis = line_crs.axis_info[0] if line_crs.axis_info else None
    unit = axis.unit_name if axis else "unit"
    if height_unit is None:
        if unit != "metre":
            raise ValueError(
                f"the line is in {unit!r} and the raster's values state no unit, so a "
                f"grade needs grade_height_unit, one of {list(HEIGHT_UNITS)}: heights in "
                f"metres over a run in feet come out 3.28 times too steep."
            )
        return 1.0, unit, True
    if height_unit not in HEIGHT_UNITS:
        raise ValueError(
            f"grade_height_unit must be one of {list(HEIGHT_UNITS)}, got {height_unit!r}"
        )
    return HEIGHT_UNITS[height_unit] / axis.unit_conversion_factor, unit, False


def _grade_window(spacing: float, base: float | None, threshold: float | None) -> int:
    """How many steps of `spacing` make one gradient window, or 0 for no gradient.

    A whole number, or refused: "the steepest of any 100 m stretch" computed
    over windows of 105 m is a different question answered with the same words.
    """
    if base is None:
        if threshold is not None:
            raise ValueError(
                "grade_threshold_percent needs grade_base_length: a gradient is a rise "
                "over a length, and that length is the caller's to choose."
            )
        return 0
    if not (base > 0) or math.isinf(base):
        raise ValueError(f"grade_base_length must be a positive finite length, got {base}")
    if threshold is not None and not math.isfinite(threshold):
        # Measured in the 0.7.0 audit: `abs(g) <= nan` is always false, so a NaN
        # threshold marked the whole line as one stretch above it -- and wrote
        # `NaN` into the manifest, which is not JSON a strict parser accepts.
        raise ValueError(f"grade_threshold_percent must be a finite number, got {threshold}")
    if threshold is not None and threshold < 0:
        raise ValueError(
            f"grade_threshold_percent must not be negative, got {threshold}: it is compared "
            "with the size of the grade, climbing or falling, so a negative one would mark "
            "every window of every line."
        )
    steps = base / spacing
    whole = round(steps)
    if whole < 1 or abs(steps - whole) > 1e-9 * max(1.0, steps):
        raise ValueError(
            f"grade_base_length {base} is not a whole number of spacing steps ({spacing}): "
            f"the window would not be {base} long. Use a spacing that divides it, such as "
            f"{base / 10:g} for ten points per window."
        )
    return whole


def _spans_the_base(span: float, base: float) -> bool:
    return abs(span - base) <= 1e-6 * base


def _grades(
    rows: list[dict[str, Any]],
    values: list[float | None],
    window: int,
    base: float,
    scale: float,
) -> list[float | None]:
    """The rise over the window starting at each point, as a percentage of the base.

    None where the window runs past the end of its run, where it would end on
    the line's far end (a shorter last step, so the window is not `base` long),
    or where ANY point inside it is one the raster could not answer for: a
    gradient over a gap is not a gradient, and neither is one over the gap
    between two parts of a multi-part line that do not touch.
    """
    missing = [0]
    for value in values:
        missing.append(missing[-1] + (value is None))
    grades: list[float | None] = [None] * len(rows)
    for start in range(len(rows)):
        end = start + window
        if end >= len(rows):
            continue
        first, last = rows[start], rows[end]
        if (last["line_index"], last["run"]) != (first["line_index"], first["run"]):
            continue
        if not _spans_the_base(last["distance"] - first["distance"], base):
            continue
        if missing[end + 1] - missing[start]:
            continue
        grades[start] = (values[end] - values[start]) * scale / base * 100.0
    return grades


def _grade_summary(
    rows: list[dict[str, Any]],
    values: list[float | None],
    grades: list[float | None],
    base: float,
    threshold: float | None,
) -> list[dict[str, Any]]:
    """Per line: the steepest window, total ascent and descent, stretches above threshold.

    `steepest_grade_percent` is the grade of largest size and keeps its sign, so
    -3.1 is the steepest and it falls; on a tie the first window wins. A stretch
    is one direction of travel: a climb and the descent after it are two
    stretches, even where the windows around the crest overlap.
    """
    by_line: dict[int, list[int]] = {}
    for position, row in enumerate(rows):
        by_line.setdefault(row["line_index"], []).append(position)
    summary = []
    for line_index, positions in by_line.items():
        known = [p for p in positions if grades[p] is not None]
        steepest = max(known, key=lambda p: abs(grades[p])) if known else None
        ascent = descent = 0.0
        for a, b in pairwise(positions):
            if rows[a]["run"] != rows[b]["run"]:
                continue
            if values[a] is not None and values[b] is not None:
                step = values[b] - values[a]
                ascent += max(step, 0.0)
                descent += max(-step, 0.0)
        entry: dict[str, Any] = {
            "line_index": line_index,
            "steepest_grade_percent": None if steepest is None else grades[steepest],
            "steepest_window_starts_at": None if steepest is None else rows[steepest]["distance"],
            "total_ascent": ascent,
            "total_descent": descent,
            "unreadable_points": sum(1 for p in positions if values[p] is None),
            "runs": len({rows[p]["run"] for p in positions}),
        }
        if threshold is not None:
            stretches: list[dict[str, Any]] = []
            last_run = None
            for p in known:
                if abs(grades[p]) <= threshold:
                    continue
                start, end = rows[p]["distance"], rows[p]["distance"] + base
                direction = "up" if grades[p] > 0 else "down"
                if (
                    stretches
                    and last_run == rows[p]["run"]
                    and stretches[-1]["direction"] == direction
                    and start <= stretches[-1]["to"]
                ):
                    stretches[-1]["to"] = max(stretches[-1]["to"], end)
                else:
                    stretches.append({"from": start, "to": end, "direction": direction})
                last_run = rows[p]["run"]
            entry["stretches_above_threshold"] = stretches
        summary.append(entry)
    return summary


def _grades_follow_the_written_profile(
    output_path: str, window: int, base: float, scale: float
) -> Any:
    """Recompute every grade from the distances and values ON DISK and compare.

    A check of the number, not of the run: it reads the written profile, rebuilds
    each window from the points that are there, and fails if a stored grade is
    not the rise over the distance those points actually span -- or if a grade
    is missing where the written points say a window fits, which is the half
    that a comparison of stored values alone cannot see. The count goes in the
    detail, so that "every grade agrees" over zero grades reads as what it is.
    """
    written = readers.read_vector(output_path)

    def absent(value: Any) -> bool:
        return value is None or (isinstance(value, float) and math.isnan(value))

    compared = mismatches = 0
    for _, part in written.groupby("line_index", sort=False):
        part = part.sort_values("point_index")
        distances, heights, stored, runs = (
            part["distance"].tolist(), part["value"].tolist(),
            part["grade_percent"].tolist(), part["run_index"].tolist(),
        )
        for i, grade in enumerate(stored):
            j = i + window
            fits = (
                j < len(distances)
                and runs[i] == runs[j]
                and _spans_the_base(distances[j] - distances[i], base)
                and not any(absent(h) for h in heights[i:j + 1])
            )
            if not fits:
                mismatches += not absent(grade)
                continue
            compared += 1
            expected = (heights[j] - heights[i]) * scale / base * 100.0
            if absent(grade) or not math.isclose(grade, expected, rel_tol=1e-9, abs_tol=1e-12):
                mismatches += 1
    return verify.Check(
        "x-mapsmith:grades_follow_the_written_profile",
        mismatches == 0,
        f"{compared} grade(s) recomputed from the written profile, all agree"
        + ("; no window fits on any readable run" if compared == 0 else "")
        if mismatches == 0
        else f"{mismatches} grade(s) disagree with the written profile ({compared} expected)",
    )


def _usable(lines: gpd.GeoDataFrame) -> list[Any]:
    return [g for g in lines.geometry if g is not None and not g.is_empty]


def _stepping_is_regular(
    rows: list[dict[str, Any]], spacing: float, lengths: dict[int, float]
) -> bool:
    """Every line starts at 0, advances by exactly `spacing`, and ends at its length.

    The last step may be shorter than the spacing -- it is the remainder that
    reaches the far end -- and never longer.
    """
    by_line: dict[int, list[float]] = {}
    for row in rows:
        by_line.setdefault(row["line_index"], []).append(row["distance"])
    for line_index, distances in by_line.items():
        if distances[0] != 0.0:
            return False
        length = lengths[line_index]
        if len(distances) > 1 and not math.isclose(distances[-1], length, rel_tol=1e-9):
            return False
        for previous, current in pairwise(distances[:-1]):
            if not math.isclose(current - previous, spacing, rel_tol=1e-9):
                return False
        if len(distances) > 1 and distances[-1] - distances[-2] > spacing * (1 + 1e-9):
            return False
    return True


def _stepping_detail(rows: list[dict[str, Any]], spacing: float, regular: bool) -> str:
    lines = len({row["line_index"] for row in rows})
    return f"{len(rows)} point(s) over {lines} line(s) at a step of {spacing}, " + (
        "the last step reaching each line's far end"
        if regular
        else "and some line does not start at 0, step by the spacing, or reach its far end"
    )


def _run_starts(geometry: Any) -> list[float]:
    """Distances along `geometry` at which a new connected run begins.

    Shapely measures a MultiLineString as one line with its parts laid end to
    end in stored order, so a distance keeps counting across a gap between two
    parts that do not touch -- and a gradient window laid over that gap
    compares two heights a kilometre apart as if they were fifty metres apart.
    Measured before this existed: two parallel level tracks on a 2% plane came
    back with a 40% stretch, and every check passed.
    """
    if geometry.geom_type != "MultiLineString":
        return []
    parts = [p for p in geometry.geoms if not p.is_empty]
    tolerance = 1e-9 * max(1.0, geometry.length)
    starts: list[float] = []
    travelled = 0.0
    for previous, current in pairwise(parts):
        travelled += previous.length
        (x0, y0), (x1, y1) = previous.coords[-1][:2], current.coords[0][:2]
        if math.hypot(x1 - x0, y1 - y0) > tolerance:
            starts.append(travelled)
    return starts


def _profile_positions(lines: gpd.GeoDataFrame, spacing: float) -> list[dict[str, Any]]:
    """Positions along each line at a fixed step, and one at the far end.

    Until 2026-09-25 this docstring said "both ends included" and the code
    stopped at the last whole step: 15 m at a step of 4 ended at 12, and the
    test named for including the far end asserted that it did not. A profile
    that silently stops short of the summit is the worst kind of nearly-right.
    """
    rows: list[dict[str, Any]] = []
    for line_index, geometry in enumerate(lines.geometry):
        # `network._build` guards these and this did not: a null geometry died on
        # `'NoneType' object has no attribute 'length'`, and an empty LineString
        # was counted as one point and then died in `interpolate`. Skipped rather
        # than refused, because a layer with a few empty rows is ordinary — and
        # counted, because a profile missing a line should not look complete.
        if geometry is None or geometry.is_empty:
            continue
        length = geometry.length
        steps = math.floor(length / spacing)
        distances = [point_index * spacing for point_index in range(steps + 1)]
        if length - distances[-1] > 1e-9 * max(1.0, length):
            distances.append(length)
        starts = _run_starts(geometry)
        for point_index, distance in enumerate(distances):
            position = geometry.interpolate(distance)
            rows.append(
                {
                    "line_index": line_index,
                    "point_index": point_index,
                    "distance": float(distance),
                    # A point exactly at a gap is the end of the earlier part,
                    # which is where Shapely's `interpolate` puts it.
                    "run": bisect.bisect_left(starts, distance),
                    "x": position.x,
                    "y": position.y,
                }
            )
    return rows


def line_of_sight(
    raster_path: str,
    observer_x: float,
    observer_y: float,
    target_x: float,
    target_y: float,
    earth_curvature: bool,
    observer_height: float = 0.0,
    target_height: float = 0.0,
    samples: int | None = None,
    band: int = 1,
) -> dict[str, Any]:
    """Whether the terrain blocks the view, and where it first does.

    `earth_curvature` has no default, and that is deliberate. Over 5 km the
    planet drops about 1.7 m below the tangent plane and over 30 km about 62 m
    net of refraction, so a flat-Earth answer is right for a rooftop survey and
    badly wrong for a radio link — and there is no way to guess which one the
    caller has. Say it, and the manifest records what was assumed. When true,
    the standard refraction coefficient of 0.13 is applied with it, because
    curvature without refraction over-corrects.

    Answers rather than writes: the result is a verdict, the distance at which
    the ground first rises above the sight line, and how far below the terrain
    the line passes there. Use `elevation_profile` for the shape of the ground.

    **A profile with holes in it does not produce a verdict.** Samples that fall
    on nodata are counted in `unreadable_samples`, and above a twentieth of the
    line missing `visible` comes back `None` with `verdict_withheld` set. The
    first version skipped unreadable samples and said nothing: a 100 m ridge
    buried in a nodata gap returned `visible: True`. "Cannot say" is an answer a
    caller can act on; "yes" computed over the parts that happened to be there
    is not.
    """
    rasterio = _require_rasterio()
    # Two georeferencings and nobody chose: refuse rather than compute
    # from a file the caller did not name (D-059). After the extra guard,
    # never before it: a caller without `[raster]` has to hear about the
    # missing extra, not about a sidecar.
    from .. import grid

    grid.refuse_ambiguous_georeferencing(raster_path, "line_of_sight")
    with rasterio.open(raster_path) as dataset:
        crs = dataset.crs
        if crs is None:
            raise ValueError(f"{raster_path} declares no CRS.")
        if crs.is_geographic:
            raise ValueError(
                f"{raster_path} is in a geographic CRS, so the distance between the "
                "two positions would be in degrees and the sight line would compare "
                "a height in metres against a run in degrees. Reproject first."
            )
        if band < 1 or band > dataset.count:
            raise ValueError(
                f"band {band} does not exist: {raster_path} has {dataset.count}."
            )

        run = math.hypot(target_x - observer_x, target_y - observer_y)
        if run == 0:
            raise ValueError(
                "the observer and the target are at the same position, so there is "
                "no sight line to check."
            )
        # One sample per cell along the line by default: sampling coarser than
        # the data can step over the ridge that blocks the view, and a viewshed
        # that misses a ridge is the confident wrong answer this whole product
        # is about.
        cell = min(abs(dataset.transform.a), abs(dataset.transform.e))
        steps = samples if samples is not None else max(2, math.ceil(run / cell) + 1)
        if steps < 2:
            raise ValueError(f"samples must be at least 2, got {samples}")

        xs = [observer_x + (target_x - observer_x) * i / (steps - 1) for i in range(steps)]
        ys = [observer_y + (target_y - observer_y) * i / (steps - 1) for i in range(steps)]
        ground = _read_at(dataset, band, xs, ys, "bilinear")

    if ground[0] is None or ground[-1] is None:
        raise ValueError(
            "the observer or the target is outside the raster or on nodata, so "
            "there is no ground elevation to stand on."
        )

    observer_z = ground[0] + observer_height
    target_z = ground[-1] + target_height
    blocked_at: float | None = None
    clearance = math.inf
    unreadable = sum(1 for value in ground if value is None)
    for index in range(1, steps - 1):
        if ground[index] is None:
            continue
        distance = run * index / (steps - 1)
        drop = _curvature_drop(distance, run) if earth_curvature else 0.0
        sight_z = observer_z + (target_z - observer_z) * index / (steps - 1) - drop
        gap = sight_z - ground[index]
        clearance = min(clearance, gap)
        if gap < 0 and blocked_at is None:
            blocked_at = distance

    # A verdict computed over a profile with holes in it is not a verdict. This
    # module's docstring promises that every operation counts what it could not
    # read; this one is the only one that answers yes-or-no instead of returning
    # a table, so a silent null costs the most here — a 100 m ridge buried in a
    # nodata gap came back `visible: True` with nothing to show for it. Above a
    # twentieth of the line missing, the answer is None: "cannot say" is an
    # answer a caller can act on and "yes" is not.
    too_holey = unreadable > max(1, steps // 20)
    return {
        "visible": None if too_holey else blocked_at is None,
        "unreadable_samples": unreadable,
        "samples_read": steps - unreadable,
        "verdict_withheld": too_holey,
        "distance": run,
        "first_obstruction_at": blocked_at,
        "minimum_clearance": None if clearance is math.inf else clearance,
        "observer_elevation": observer_z,
        "target_elevation": target_z,
        "earth_curvature": earth_curvature,
        "refraction_coefficient": REFRACTION_COEFFICIENT if earth_curvature else None,
        "samples": steps,
        "crs": verify.crs_label(crs),
    }


def _curvature_drop(distance: float, total: float) -> float:
    """How far the Earth falls away under a chord, net of refraction.

    `d * (total - d) / (2R)` is the sagitta of the arc at distance `d` along a
    chord of length `total` — zero at both ends, greatest in the middle, which
    is what curvature actually does to a sight line. The refraction coefficient
    reduces it, because the atmosphere bends light back down.
    """
    return (
        (1 - REFRACTION_COEFFICIENT) * distance * (total - distance) / (2 * EARTH_RADIUS_M)
    )
