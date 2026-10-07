"""Questions whose answer is a number, not a layer.

Of sixty-one catalog operations, three produced an `answer` and none of them
took a vector layer. That is not a gap in coverage, it is a gap in *shape*: a
caller holding parcels and asking how much land there is had nothing to be
offered, because every operation that computes it writes the number into a
column and hands back a dataset. The discovery layer found this the hard way —
a search declaring `input_kind="vector", produces="answer"` left zero candidates
and came back as a choice between nothing.

So these four read and write nothing. No output path, no manifest, no
provenance record: there is no artefact to carry one, and inventing a file to
have something to attach a manifest to would be worse than the gap. What travels
instead is inside the answer — every statistic says what it was computed OVER,
because a mean over a column with nulls in it and a mean over the rows that had
values are different numbers with the same name.

Two of them are statistics with a literature and a trap each:

* **Moran's I** is the global companion of the local Gi* in `spatial_stats`.
  Same neighbourhoods, same reason to care about how they were built — a
  contiguity that finds no neighbours turns the statistic into noise.
* **The nearest-neighbour index** is not a property of the points. R is a ratio
  against what random points in *an area* would do, and the area is a choice the
  caller makes. Take the points' own bounding box and a clustered pattern
  reports itself as more clustered than it is, because the box shrank around it.
  This one refuses to hide that: the area is either given or it is the convex
  hull, and the answer says which and how big.
"""

from __future__ import annotations

import math
from typing import Any

import geopandas as gpd
import numpy as np

from .. import datum, readers, verify
from .network import _unit
from .spatial_stats import WEIGHT_SCHEMES, _normal_tail, _prepare, _weights

#: What `summarize_field` knows how to compute. Median is here and mode is not:
#: a mode over floats is a question about binning, and answering it silently
#: would be picking the bins for somebody.
STATISTICS = ("count", "sum", "mean", "median", "min", "max", "stdev", "range")


def _describe(values: np.ndarray) -> dict[str, float | int]:
    """The statistics of one group of values, all of them, computed once."""
    n = int(values.size)
    if n == 0:
        return {"count": 0}
    out: dict[str, float | int] = {
        "count": n,
        "sum": float(values.sum()),
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "min": float(values.min()),
        "max": float(values.max()),
        "range": float(values.max() - values.min()),
    }
    # Sample standard deviation (n-1), which is what a caller means by "the
    # spread of these values" when the features are a sample of something. With
    # one feature it is undefined rather than zero, and saying zero would claim
    # a certainty nobody has.
    out["stdev"] = float(values.std(ddof=1)) if n > 1 else None
    return out


def summarize_field(
    input_path: str,
    field: str,
    group_by: str | None = None,
    statistics: list[str] | None = None,
) -> dict[str, Any]:
    """Descriptive statistics of one attribute, optionally per group. Writes nothing.

    The commonest question asked of a GIS layer — how much, how many, what is
    the biggest — and the one that had no operation. Geometry is not touched:
    this is arithmetic over an attribute, so it works on a layer whose CRS is
    missing, which no metric operation may do.

    Rows with no value in `field` are excluded and **counted separately**. That
    is the whole difference between a mean and a wrong mean: a total over 900 of
    1000 parcels is a true number about 900 parcels, and reported as if it were
    about 1000 it is a lie nothing raises.
    """
    wanted = list(statistics) if statistics else list(STATISTICS)
    unknown = [name for name in wanted if name not in STATISTICS]
    if unknown:
        raise ValueError(
            f"unknown statistic(s) {unknown}. Available: {list(STATISTICS)}"
        )

    gdf = readers.read_vector(input_path)
    for column in (field, group_by):
        if column is not None and column not in gdf.columns:
            raise ValueError(
                f"{input_path} has no column {column!r}. Columns: "
                f"{sorted(c for c in gdf.columns if c != gdf.geometry.name)}"
            )

    series = gdf[field]
    numeric = series.map(lambda v: isinstance(v, int | float) and not isinstance(v, bool))
    if not numeric[series.notna()].all():
        raise ValueError(
            f"column {field!r} holds values that are not numbers, so a sum or a mean "
            "of it would be meaningless. Summarise a numeric column, or count rows "
            "per category with group_by."
        )

    missing = int(series.isna().sum())
    present = series.notna()
    answer: dict[str, Any] = {
        "field": field,
        "features": len(gdf),
        "features_with_a_value": int(present.sum()),
        "features_with_no_value": missing,
    }
    values = series[present].to_numpy(dtype=float)
    overall = _describe(values)
    answer["overall"] = {name: overall.get(name) for name in wanted}

    if group_by is not None:
        groups = []
        # Sorted by the group key so that two runs of the same data answer in
        # the same order: an answer whose row order depends on a hash table is
        # reproducible only by accident.
        for key in sorted(gdf[group_by].dropna().unique(), key=str):
            rows = gdf[(gdf[group_by] == key) & present]
            described = _describe(rows[field].to_numpy(dtype=float))
            groups.append(
                {group_by: key if isinstance(key, str) else key.item()
                 if hasattr(key, "item") else key,
                 **{name: described.get(name) for name in wanted}}
            )
        answer["group_by"] = group_by
        answer["groups"] = groups
        answer["groups_found"] = len(groups)
        ungrouped = int(gdf[group_by].isna().sum())
        if ungrouped:
            answer["features_with_no_group"] = ungrouped

    if missing:
        answer["note"] = (
            f"{missing} of {len(gdf)} feature(s) have no value in {field!r} and were "
            f"excluded. Every statistic above is over the {int(present.sum())} that do."
        )
    return answer


def spatial_autocorrelation(
    input_path: str,
    value_field: str,
    weights: str = "contiguity",
    distance_band: float | None = None,
) -> dict[str, Any]:
    """Global Moran's I: is this pattern clustered, random, or checkerboarded?

    The one-number companion to `hot_spots`. Gi* says *where* the clusters are
    and assumes there are some; this says whether the map as a whole holds a
    pattern at all, which is the question to ask first — a hot-spot map of noise
    still has hot spots on it, about five in a hundred at the usual threshold.

    I runs from about -1 (neighbours are opposites, a checkerboard) through 0
    (no pattern) to about +1 (neighbours are alike). The expected value under no
    pattern is not zero but -1/(n-1), which matters at small n and is reported.
    Significance is the normality-assumption z-score, exact for the weights
    given; it says the pattern is unlikely to be noise, never that it is causal.

    The neighbourhood is the statistic. Contiguity uses shared boundaries, a
    distance band uses a radius in the layer's own unit, and features with no
    neighbours contribute nothing at all — so their count is in the answer, and
    a majority of them is refused rather than reported.
    """
    if weights not in WEIGHT_SCHEMES:
        raise ValueError(f"weights must be one of {list(WEIGHT_SCHEMES)}, got {weights!r}")

    gdf = _prepare(input_path, "spatial_autocorrelation", value_field)
    n = len(gdf)
    if n < 3:
        raise ValueError(
            f"Moran's I needs at least 3 features to mean anything; {input_path} has {n}."
        )

    values = gdf[value_field].to_numpy(dtype=float)
    deviations = values - values.mean()
    denominator = float((deviations**2).sum())
    if denominator == 0:
        raise ValueError(
            f"every feature has the same value in {value_field!r}, so there is no "
            "variation for a spatial pattern to be in. Moran's I is undefined here, "
            "not zero."
        )

    neighbourhoods = _weights(gdf, weights, distance_band)
    isolated = sum(1 for row in neighbourhoods if not row)
    if isolated > n // 2:
        raise ValueError(
            f"{isolated} of {n} feature(s) have no neighbours under weights="
            f"{weights!r}, so most of the layer contributes nothing to the "
            "statistic and what comes back would not be a measure of this map. "
            + (
                "Widen distance_band."
                if weights == "distance_band"
                else "Check for boundaries that fall short or overlap by a sliver."
            )
        )

    # Binary weights, symmetric by construction, so S1 and S2 have their simple
    # forms. Written out rather than taken from a library because the whole
    # point of this project is that a number can be followed to its arithmetic.
    total_weight = float(sum(len(row) for row in neighbourhoods))
    cross = 0.0
    for i, row in enumerate(neighbourhoods):
        for j in row:
            cross += deviations[i] * deviations[j]
    moran = (n / total_weight) * (cross / denominator) if total_weight else float("nan")
    expected = -1.0 / (n - 1)

    degree = np.array([len(row) for row in neighbourhoods], dtype=float)
    s1 = 2.0 * total_weight  # ½·Σ(w_ij + w_ji)² with binary symmetric weights
    s2 = float((4.0 * degree**2).sum())  # Σ(row sum + column sum)²
    w2 = total_weight**2
    variance = (
        (n * n * s1 - n * s2 + 3 * w2) / (w2 * (n * n - 1)) - expected**2
        if total_weight
        else float("nan")
    )
    z = (moran - expected) / math.sqrt(variance) if variance > 0 else float("nan")
    p = _normal_tail(z) if variance > 0 else float("nan")

    if math.isnan(z):
        verdict = "undecided"
    elif p >= 0.05:
        verdict = "no pattern distinguishable from random"
    elif moran > expected:
        verdict = "clustered: neighbours resemble each other"
    else:
        verdict = "dispersed: neighbours are unalike, like a checkerboard"

    return {
        "morans_i": round(moran, 6),
        "expected_i": round(expected, 6),
        "variance": None if math.isnan(variance) else round(variance, 9),
        "z_score": None if math.isnan(z) else round(z, 4),
        "p_value": None if math.isnan(p) else round(p, 6),
        "verdict": verdict,
        "features": n,
        "value_field": value_field,
        "weights": weights,
        "distance_band": distance_band if weights == "distance_band" else None,
        "neighbour_pairs": int(total_weight),
        "isolated_features": isolated,
        "crs": verify.crs_label(gdf.crs),
        "note": (
            "significance here is the normality-assumption z-score, which is exact "
            "for these weights and says the pattern is unlikely under randomness — "
            "it says nothing about why"
        ),
    }


def nearest_neighbour_index(
    input_path: str,
    area_path: str | None = None,
) -> dict[str, Any]:
    """Clark-Evans R: are these points clustered, random, or evenly spread?

    R is the mean distance to the nearest other point divided by what that mean
    would be if the same number of points were scattered at random over the same
    area. Below 1 is clustered, 1 is random, above 1 is spread out, and about
    2.15 is a perfect lattice.

    **R is not a property of the points.** It is a ratio against an area, and
    the area is a decision. Take the points' own bounding box and a tight
    cluster in one corner of a county reports itself as barely clustered,
    because the box shrank to fit it. So `area_path` is the honest input — the
    boundary the points were sampled within — and without it the convex hull is
    used, which is stated in the answer along with the area itself. Two runs
    that disagree about R usually agree about the points and disagree about
    this.

    Needs a projected CRS: the distances and the area have to be in the same
    linear unit, and degrees are not a unit of length.
    """
    gdf = _prepare(input_path, "nearest_neighbour_index")
    if gdf.crs.is_geographic:
        raise ValueError(
            f"{input_path} is in a geographic CRS ({verify.crs_label(gdf.crs)}), so "
            "distances would be in degrees and the area in square degrees — the "
            "ratio would be a number with no meaning. Reproject to a projected CRS "
            "first (reproject_layer)."
        )
    points = gdf.geometry.representative_point()
    n = len(points)
    if n < 3:
        raise ValueError(
            f"the nearest-neighbour index needs at least 3 points; {input_path} has {n}."
        )

    if area_path is not None:
        boundary = readers.read_vector(area_path)
        if boundary.crs is None:
            raise ValueError(f"{area_path} has no CRS, so its area cannot be trusted.")
        # The study area comes out of THIS reprojection, density is n/area,
        # and R is a ratio against a distance derived from density -- so a
        # ballpark here does not decorate the answer, it moves the verdict
        # between clustered, random and evenly spread. This operation writes
        # no manifest, so the answer is where it has to be said.
        boundary_moved = not verify.same_crs(boundary.crs, gdf.crs)
        if boundary_moved:
            boundary_from = verify.crs_label(boundary.crs)
            transformation = datum.default_operation(boundary.crs, gdf.crs)
            boundary = boundary.to_crs(gdf.crs)
        area = float(boundary.geometry.area.sum())
        area_source = f"the area of {area_path}"
    else:
        hull = gpd.GeoSeries(points, crs=gdf.crs).union_all().convex_hull
        area = float(hull.area)
        area_source = (
            "the convex hull of the points themselves, because no boundary was given "
            "— this makes R a comparison against the area the points already occupy, "
            "which understates clustering"
        )
    if area <= 0:
        raise ValueError(
            "the study area came out as zero, so R cannot be computed. Points on a "
            "single line have no hull area: pass area_path with the boundary they "
            "were sampled within."
        )

    coordinates = np.array([[p.x, p.y] for p in points])
    # Full pairwise distances: n is small for this statistic in practice, and an
    # exact answer with an obvious implementation beats a tree that has to be
    # trusted. The diagonal is set to infinity so a point is never its own
    # nearest neighbour — the mistake that makes every R come out as zero.
    differences = coordinates[:, None, :] - coordinates[None, :, :]
    distances = np.sqrt((differences**2).sum(axis=2))
    np.fill_diagonal(distances, np.inf)
    nearest = distances.min(axis=1)
    coincident = int((nearest == 0).sum())

    observed = float(nearest.mean())
    density = n / area
    expected = 0.5 / math.sqrt(density)
    r = observed / expected
    standard_error = 0.26136 / math.sqrt(n * density)
    z = (observed - expected) / standard_error if standard_error > 0 else float("nan")
    p = float("nan") if math.isnan(z) else _normal_tail(z)

    if p >= 0.05:
        verdict = "indistinguishable from random"
    elif r < 1:
        verdict = "clustered"
    else:
        verdict = "evenly spread"

    answer = {
        "r": round(r, 4),
        "observed_mean_distance": round(observed, 4),
        "expected_mean_distance": round(expected, 4),
        "z_score": None if math.isnan(z) else round(z, 4),
        "p_value": None if math.isnan(p) else round(p, 6),
        "verdict": verdict,
        "points": n,
        "study_area": round(area, 4),
        "study_area_from": area_source,
        "unit": _unit(gdf.crs),
        "crs": verify.crs_label(gdf.crs),
    }
    if area_path is not None and boundary_moved:
        answer["boundary_reprojected"] = {
            "argument": "area_path",
            "from": boundary_from,
            "transformation": transformation,
        }
    if coincident:
        answer["coincident_points"] = coincident
        answer["note"] = (
            f"{coincident} point(s) sit exactly on another, giving a nearest-neighbour "
            "distance of zero. Duplicated records do this, and they drag R towards "
            "clustered whether or not the pattern is."
        )
    return answer


def _geometry(value: Any) -> Any:
    """The geometry, or None when the row has none — whatever "none" looks like.

    A missing geometry is `None` from a GeoPackage and `nan` (a float) from
    GeoParquet, and the first version of this check tested `is not None`, so the
    Parquet case reached `.distance` on a float and raised an AttributeError.
    Asking whether it is a geometry answers both.
    """
    from shapely.geometry.base import BaseGeometry

    return value if isinstance(value, BaseGeometry) and not value.is_empty else None


def _same_value(left: Any, right: Any) -> bool:
    """Whether two attribute values say the same thing, nulls included.

    `NaN != NaN` is what IEEE 754 requires and what pandas gives back, and it is
    the wrong answer to "did this attribute change": two rows that both record
    nothing about a column agree about it. Comparing a layer with a copy of
    itself reported every row holding a null as edited.
    """
    import pandas as pd

    def missing(value: Any) -> bool:
        # `pd.isna` on a list or an array returns an ARRAY, and `if a or b` on
        # one raises "the truth value of an array is ambiguous". List columns are
        # ordinary in GeoParquet, and the plain `!=` this replaced handled them —
        # so the null fix broke a case that worked. Anything list-shaped is
        # present by definition: it holds values.
        if value is None:
            return True
        if isinstance(value, str | bytes | list | tuple | set | dict):
            return False
        try:
            return bool(pd.isna(value))
        except (TypeError, ValueError):
            # An ndarray, or anything else pandas cannot reduce to one boolean.
            return False

    left_missing, right_missing = missing(left), missing(right)
    if left_missing or right_missing:
        return left_missing and right_missing
    try:
        return bool(left == right)
    except (TypeError, ValueError):
        # Two arrays compare elementwise; fall back to their representations
        # rather than raising inside a comparison that is meant to answer yes
        # or no.
        return repr(left) == repr(right)


def compare_layers(
    input_path: str,
    other_path: str,
    key_field: str | None = None,
    tolerance: float = 0.0,
) -> dict[str, Any]:
    """What changed between two versions of the same layer. Writes nothing.

    The question asked of every new delivery — *is this actually different from
    what we had* — and the one usually answered by opening both in a viewer and
    squinting. Compares the things that make two layers the same layer: CRS,
    feature count, columns, extent, and, with `key_field`, what happened to each
    feature.

    Without a key it can only compare shapes in bulk, and it says so rather than
    guessing which feature became which: matching features by position is the
    kind of assumption that reports an entire layer as changed because somebody
    sorted it.

    `tolerance` is a distance in the CRS's own unit. Zero means exact geometric
    equality, which is the right default: a rewrite through a different library
    can move a vertex by a nanometre, and a comparison that hides that is not a
    comparison.
    """
    left = readers.read_vector(input_path)
    right = readers.read_vector(other_path)

    same_crs = verify.same_crs(left.crs, right.crs)
    aligned = not same_crs and right.crs is not None and left.crs is not None
    alignment = (
        datum.default_operation(right.crs, left.crs) if aligned else None
    )
    if aligned:
        right = right.to_crs(left.crs)

    left_columns = {c for c in left.columns if c != left.geometry.name}
    right_columns = {c for c in right.columns if c != right.geometry.name}

    answer: dict[str, Any] = {
        "same_crs": bool(same_crs),
        "crs": [verify.crs_label(left.crs), verify.crs_label(right.crs)],
        # `same_crs: false` says the two disagreed; this says what was done
        # about it. Every geometric difference below is measured after the
        # alignment, so a ballpark there is a difference this operation
        # would report as real. No manifest here: the answer is the record.
        **({"transformation": alignment} if alignment else {}),
        "features": [len(left), len(right)],
        "columns_only_in_first": sorted(left_columns - right_columns),
        "columns_only_in_second": sorted(right_columns - left_columns),
        "columns_in_both": sorted(left_columns & right_columns),
        "extent": [
            [round(v, 6) for v in left.total_bounds.tolist()] if len(left) else None,
            [round(v, 6) for v in right.total_bounds.tolist()] if len(right) else None,
        ],
        "tolerance": tolerance,
    }
    if not same_crs:
        answer["note_crs"] = (
            "the two layers declare different coordinate systems; the second was "
            "reprojected onto the first before comparing, so tiny geometric "
            "differences below are the reprojection, not the data"
        )

    if key_field is None:
        answer["compared_by"] = "counts, columns and extent only"
        answer["identical"] = bool(
            same_crs
            and len(left) == len(right)
            and left_columns == right_columns
            and answer["extent"][0] == answer["extent"][1]
        )
        answer["note"] = (
            "no key_field was given, so features were not matched to each other. "
            "Pass the column that identifies a feature to learn which ones were "
            "added, removed, moved or edited."
        )
        return answer

    for name, frame, path in (("first", left, input_path), ("second", right, other_path)):
        if key_field not in frame.columns:
            raise ValueError(f"the {name} layer ({path}) has no column {key_field!r}.")
        duplicates = int(frame[key_field].duplicated().sum())
        if duplicates:
            raise ValueError(
                f"{path} has {duplicates} repeated value(s) in {key_field!r}, so it "
                "does not identify a feature and the comparison would pair rows "
                "arbitrarily."
            )

    left_rows = {row[key_field]: row for _, row in left.iterrows()}
    right_rows = {row[key_field]: row for _, row in right.iterrows()}
    added = sorted(set(right_rows) - set(left_rows), key=str)
    removed = sorted(set(left_rows) - set(right_rows), key=str)
    shared = sorted(set(left_rows) & set(right_rows), key=str)

    moved, edited, moved_by = [], [], 0.0
    compare_columns = sorted((left_columns & right_columns) - {key_field})
    for key in shared:
        a, b = left_rows[key], right_rows[key]
        # Null geometries are ordinary in GeoPackage and GeoParquet, and the
        # first version of this loop guarded only the distance call before
        # asking a None for `.equals`, which is a raw AttributeError where every
        # other operation here answers with a sentence.
        left_geometry, right_geometry = _geometry(a.geometry), _geometry(b.geometry)
        if left_geometry is None or right_geometry is None:
            distance = 0.0
            differs = (left_geometry is None) != (right_geometry is None)
        else:
            # The Hausdorff distance, not the distance between the two shapes:
            # two overlapping polygons are zero apart however differently they
            # are shaped, so a reshaped parcel measured that way came back
            # unchanged. Hausdorff is the largest deviation between the two
            # boundaries, which is what "did this move, and by how much" means
            # for a feature that was edited rather than dragged.
            distance = left_geometry.hausdorff_distance(right_geometry)
            # `tolerance` is a deviation the caller is willing to ignore, so a
            # larger one can only ever find FEWER changes. The first version
            # switched from `equals` (topological) to `equals_exact`
            # (structural) as soon as a tolerance was given, so a caller
            # loosening the comparison to 5 m got a stricter one: two polygons
            # of identical shape differing by a collinear vertex came back
            # unchanged at 0 and changed at 5.
            # Zero tolerance means exact geometric equality and nothing else.
            # Gating on the distance unconditionally made zero WEAKER than the
            # docstring promises, because GEOS's Hausdorff distance is the
            # DISCRETE one — vertices of each against the other — so it is 0.0
            # for a line and the same line with a stretch missing in the middle:
            # every vertex still coincides. A road that lost two metres came
            # back identical. Second attempt at this fix; the first traded one
            # wrong answer for another.
            differs = not left_geometry.equals(right_geometry) and (
                tolerance == 0 or distance > tolerance
            )
        if differs:
            moved.append(key)
            moved_by = max(moved_by, float(distance))
        # `NaN != NaN` is True, so comparing a layer with a byte-identical copy
        # of itself reported every row holding a null as edited — the operation
        # whose whole question is "is this different from what we had" answering
        # yes about the same file. Two nulls are the same value here: neither
        # row says anything about that column.
        if any(
            not _same_value(a[column], b[column]) for column in compare_columns
        ):
            edited.append(key)

    answer.update(
        compared_by=f"matched on {key_field!r}",
        added=len(added),
        removed=len(removed),
        matched=len(shared),
        geometry_changed=len(moved),
        attributes_changed=len(edited),
        largest_move=round(moved_by, 6),
        added_keys=added[:50],
        removed_keys=removed[:50],
        geometry_changed_keys=moved[:50],
        attributes_changed_keys=edited[:50],
        identical=bool(
            same_crs and not added and not removed and not moved and not edited
        ),
    )
    if len(added) > 50 or len(removed) > 50 or len(moved) > 50 or len(edited) > 50:
        answer["keys_truncated"] = (
            "the *_keys lists stop at 50 entries; the counts above them are complete"
        )
    return answer
