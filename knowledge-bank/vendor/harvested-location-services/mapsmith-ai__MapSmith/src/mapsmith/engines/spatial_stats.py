"""Four operations for the moment somebody is about to publish a map of noise.

They come from the discovery benchmark, in the words of the people who had the
problem: *"the high-count villages seem grouped but I'm not sure what I'm
seeing"*, *"the district-level tuberculosis rates are jumping wildly from 0 to
800 per 100,000 just because [the denominators are tiny]"*, *"the ethics
committee is breathing down my neck about patient confidentiality"*, *"over a
million dots, so the map completely freezes"*. Both independent labellers marked
all four `none`.

What they have in common is that the naive answer is not an error, it is a
picture. A choropleth of raw rates over small populations maps population size;
a hot-spot map without a multiple-testing correction finds clusters in random
data; publishing a count of two identifies a person. None of that raises
anything, which is why these belong in a product about verifiable results rather
than in a notebook.

No new dependency. `math.erfc` gives the normal tail exactly, the weights matrices
here are small by construction, and a package whose tie-breaking we did not
control would make two runs of the same data disagree.
"""

from __future__ import annotations

import math
from typing import Any

import geopandas as gpd

from .. import readers, verify
from ..provenance import InputRecord, ProvenanceRecord

#: How neighbours are defined. `contiguity` is shared-boundary adjacency, which
#: is what administrative areas mean by neighbour; `distance_band` is everything
#: within a radius, which is what point data means by it.
WEIGHT_SCHEMES = ("contiguity", "distance_band")

#: Benjamini–Hochberg, because at 0.05 over 300 districts about fifteen come back
#: significant from noise alone — and they will be somewhere, so they will look
#: like a pattern.
DEFAULT_ALPHA = 0.05


def _engine_info() -> dict[str, str]:
    """The engine is this module. Gi*, Benjamini-Hochberg and the empirical-Bayes
    estimator are arithmetic written here; shapely only builds the neighbourhoods,
    so it belongs in a field of its own rather than in the version string, where
    a reader would conclude the statistics came from it."""
    import shapely

    from .. import __version__

    return {
        "name": "mapsmith-stats",
        "version": __version__,
        "x-mapsmith:geometry_library": f"shapely {shapely.__version__}",
    }


def _normal_tail(z: float) -> float:
    """Two-sided p for a standard normal deviate. Exact, via the error function."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def _benjamini_hochberg(p_values: list[float], alpha: float) -> list[bool]:
    """Which p-values survive an FDR correction at `alpha`.

    Step-up: sort ascending, find the largest k with p_(k) <= k/n * alpha, and
    reject everything up to it. Returns a mask in the ORIGINAL order.
    """
    n = len(p_values)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p_values[i])
    cutoff = -1
    for rank, index in enumerate(order, start=1):
        if p_values[index] <= rank / n * alpha:
            cutoff = rank
    keep = [False] * n
    for rank, index in enumerate(order, start=1):
        if rank <= cutoff:
            keep[index] = True
    return keep


def _weights(
    gdf: gpd.GeoDataFrame, scheme: str, distance_band: float | None
) -> list[list[int]]:
    """Neighbour lists, one per feature, excluding the feature itself."""
    if scheme == "contiguity":
        # `intersects`, not `touches`. `touches` is false for polygons that
        # OVERLAP, and real administrative boundaries overlap by millimetres all
        # the time — a strip of five areas with a 1 mm overlap came back with
        # zero neighbours each, which turns Gi* into a plain z-score of the value
        # against the global distribution. A different statistic, computed in
        # silence, with a non-critical note as the only trace. This is the same
        # class of defect that `network.tolerance` exists for, and it was being
        # treated as a warning here.
        index = gdf.sindex
        neighbours = []
        for position, geometry in enumerate(gdf.geometry):
            candidates = index.query(geometry, predicate="intersects")
            neighbours.append(sorted(int(c) for c in candidates if int(c) != position))
        return neighbours

    if distance_band is None or not (math.isfinite(distance_band) and distance_band > 0):
        raise ValueError(
            "weights='distance_band' needs a positive, finite distance_band: the radius "
            "within which two features count as neighbours."
        )
    # Through the same blocked, capped pair query as the clustering. This was a
    # double loop in Python: every feature measured against every other, so
    # quadratic at any band, and with a large band its neighbour lists alone
    # held n^2 entries (0.8.0 audit). Distance inclusive, as before.
    points = gdf.geometry.representative_point().to_numpy()
    neighbours: list[list[int]] = [[] for _ in range(len(points))]
    pairs = _pairs_within(points, distance_band)
    for a, b in zip(pairs[0].tolist(), pairs[1].tolist(), strict=True):
        neighbours[a].append(b)
        neighbours[b].append(a)
    return [sorted(row) for row in neighbours]


def _prepare(input_path: str, operation: str, *fields: str):
    gdf = readers.read_vector(input_path)
    if gdf.crs is None:
        raise ValueError(
            readers.no_crs_message(gdf, f"{input_path} has no CRS.")
        )
    for field in fields:
        if field is None:
            continue
        if field not in gdf.columns:
            raise ValueError(
                f"{input_path} has no column {field!r}. Columns: "
                f"{sorted(c for c in gdf.columns if c != gdf.geometry.name)}"
            )
        if gdf[field].isna().any():
            raise ValueError(
                f"{gdf[field].isna().sum()} row(s) have no value in {field!r}. A "
                f"missing value is not a zero, and {operation} would treat it as one."
            )
    return gdf


def _write(gdf: gpd.GeoDataFrame, output_path: str) -> None:
    if str(output_path).endswith(".parquet"):
        gdf.to_parquet(output_path)
    else:
        gdf.to_file(output_path)


def hot_spots(
    input_path: str,
    output_path: str,
    value_field: str,
    weights: str,
    distance_band: float | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Getis-Ord Gi*: where high values cluster with other high values.

    Answers *"the high-count villages seem grouped but I'm not sure what I'm
    seeing"* — and the reason it is a operation rather than a colour ramp is
    that the eye finds clusters in random data, and so does this statistic if
    you let it. **Every feature is a hypothesis test**, so over 300 districts at
    the conventional 0.05 about fifteen come back significant from noise alone,
    and they will be somewhere, and that somewhere will look like a pattern.

    So the output carries three things and the classification uses the third:
    `gi_z` (the standard deviate), `gi_p` (its two-sided p-value) and
    `significant` — which is a Benjamini-Hochberg false-discovery-rate decision
    at `alpha` across all features, not a per-feature threshold. `hot_or_cold`
    says which tail a significant feature is in. The uncorrected count is in the
    result and in the manifest so the difference is visible rather than implied.

    Gi* INCLUDES the feature itself, which is the starred variant and the one
    almost everybody means: a village that is high on its own but surrounded by
    lows is not a hot spot, and Gi without the star cannot say that.
    """
    if weights not in WEIGHT_SCHEMES:
        raise ValueError(
            f"weights must be one of {list(WEIGHT_SCHEMES)}, got {weights!r}. "
            "'contiguity' for administrative areas that share boundaries, "
            "'distance_band' for points or for areas that should reach further."
        )
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be between 0 and 1, got {alpha}")

    gdf = _prepare(input_path, "hot_spots", value_field)
    if weights == "distance_band" and gdf.crs.is_geographic:
        raise ValueError(
            f"{input_path} is in a geographic CRS, so a distance_band of "
            f"{distance_band} would be in DEGREES — a different ground distance at "
            "every latitude. Reproject first."
        )
    values = [float(v) for v in gdf[value_field]]
    n = len(values)
    if n < 3:
        raise ValueError(
            f"Gi* needs at least 3 features to have a distribution to compare "
            f"against; {input_path} has {n}."
        )

    neighbourhoods = _weights(gdf, weights, distance_band)
    mean = sum(values) / n
    variance = sum(v * v for v in values) / n - mean * mean
    spread = math.sqrt(max(variance, 0.0))

    z_scores: list[float | None] = []
    p_values: list[float] = []
    isolated = 0
    for position in range(n):
        # Gi* includes the feature itself: the neighbourhood is the neighbours
        # plus self, with binary weights.
        members = [*neighbourhoods[position], position]
        w_sum = float(len(members))
        w_squared_sum = float(len(members))
        if len(members) == 1:
            isolated += 1
        local_sum = sum(values[m] for m in members)
        denominator = spread * math.sqrt(
            max((n * w_squared_sum - w_sum * w_sum) / (n - 1), 0.0)
        )
        if denominator == 0:
            # Every value identical, or the neighbourhood is the whole layer:
            # there is no deviation to measure and a z of 0 is the honest answer,
            # not a division that raises somewhere downstream.
            z_scores.append(0.0)
            p_values.append(1.0)
            continue
        z = (local_sum - mean * w_sum) / denominator
        z_scores.append(z)
        p_values.append(_normal_tail(z))

    significant = _benjamini_hochberg(p_values, alpha)
    uncorrected = sum(1 for p in p_values if p <= alpha)

    out = gdf.copy()
    out["gi_z"] = z_scores
    out["gi_p"] = p_values
    out["significant"] = significant
    out["hot_or_cold"] = [
        ("hot" if (z or 0) > 0 else "cold") if flag else "not significant"
        for z, flag in zip(z_scores, significant, strict=True)
    ]
    out["neighbours"] = [len(row) for row in neighbourhoods]

    record = ProvenanceRecord(
        operation="hot_spots",
        parameters={
            "value_field": value_field,
            "weights": weights,
            # Only when it was used. Recorded unconditionally, it told a reader
            # of a contiguity run that the analysis used a radius it ignored.
            "distance_band": distance_band if weights == "distance_band" else None,
            "alpha": alpha,
            "statistic": "Getis-Ord Gi* (self included), binary weights",
            "multiple_testing": "Benjamini-Hochberg false discovery rate",
        },
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "the neighbourhood is built in the layer's own CRS; with a "
        "distance band that CRS's linear unit is the band's unit",
    }
    if isolated:
        record.notes.append(
            f"{isolated} feature(s) have no neighbours at all, so their Gi* is "
            "computed over themselves alone. That is a statement about the weights, "
            "not about the data: with contiguity it usually means an island or a "
            "sliver, with a distance band it means the band is too small."
        )

    # The write is INSIDE the net since 2026-09-07, and it moved down here
    # rather than the record moving up: nothing this record holds depends on
    # the write, and nothing between the two positions touches the file. A
    # write that raises after opening the file left the dataset on disk with
    # no manifest beside it -- measured, 516 bytes of a partial dataset.
    pre = verify.verify_loaded_inputs("hot_spots", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        _write(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="hot_spots",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(gdf.crs),
                expect_count=n,
            ),
            # The correction can only ever remove findings. If it added one, the
            # step-up is implemented backwards — which would publish MORE false
            # clusters than no correction at all.
            verify.Check(
                "x-mapsmith:the_correction_only_removes_findings",
                sum(significant) <= uncorrected,
                f"{sum(significant)} after correction, {uncorrected} before",
            ),
            verify.Check(
                "x-mapsmith:every_feature_has_a_neighbour",
                isolated == 0,
                f"{isolated} of {n} feature(s) have no neighbours",
                critical=False,
                hint="an isolated feature's Gi* is computed over itself alone; widen "
                "the distance band, or check for slivers if using contiguity",
            ),
            # A few islands are data. Half the layer with no neighbours is not a
            # property of the data, it is an analysis that did not happen: Gi*
            # over a neighbourhood of one is the z-score of the value against the
            # global distribution, which measures no clustering at all. Critical,
            # because the output would be a map of a different statistic under
            # this one's name.
            verify.Check(
                "x-mapsmith:the_weights_found_a_neighbourhood_to_work_with",
                isolated <= n // 2,
                f"{isolated} of {n} feature(s) are isolated, so for those Gi* is "
                "the value's own z-score and measures no clustering",
                hint="with contiguity, boundaries that overlap or fall short by a "
                "sliver produce this; with a distance band, the band is too small",
            ),
        ],
    )
    return {
        "output": str(output_path),
        "features": n,
        "significant": sum(significant),
        "significant_before_correction": uncorrected,
        "hot": sum(1 for row in out["hot_or_cold"] if row == "hot"),
        "cold": sum(1 for row in out["hot_or_cold"] if row == "cold"),
        "isolated": isolated,
        "provenance": str(manifest),
        **extras,
    }


def smooth_rates(
    input_path: str,
    output_path: str,
    count_field: str,
    population_field: str,
    per: float = 100_000.0,
) -> dict[str, Any]:
    """Empirical-Bayes rates: the small-denominator problem, handled explicitly.

    Answers *"the district-level tuberculosis rates are jumping wildly from 0 to
    800 per 100,000"*. They are jumping because of the denominators: one case in
    a village of 120 is 833 per 100,000 and zero cases is 0, and the map of raw
    rates is largely a map of which districts are small. Nothing about that
    raises — it produces a striking picture, which is worse.

    The estimator (Marshall 1991) shrinks each raw rate toward the global rate by
    an amount that depends on how much information the local denominator carries:
    a district of two million barely moves, one of 120 moves most of the way.
    Output carries `raw_rate`, `smoothed_rate` and `shrinkage` — the weight given
    to the local rate, between 0 and 1 — so the reader can see which numbers are
    mostly evidence and which are mostly the prior.

    **A smoothed rate is not a corrected count.** It is an estimate of the
    underlying risk, and it is the wrong number to use if the question is how
    many people were actually ill.
    """
    if per <= 0:
        raise ValueError(f"per must be positive, got {per}")
    gdf = _prepare(input_path, "smooth_rates", count_field, population_field)

    counts = [float(c) for c in gdf[count_field]]
    populations = [float(p) for p in gdf[population_field]]
    if any(p <= 0 for p in populations):
        bad = sum(1 for p in populations if p <= 0)
        raise ValueError(
            f"{bad} row(s) have a population of zero or less in "
            f"{population_field!r}. A rate needs a denominator; drop those areas or "
            "merge them into a neighbour first (aggregate_to_threshold does that)."
        )
    if any(c < 0 for c in counts):
        raise ValueError(f"{count_field!r} holds negative counts, which is not a count.")

    total_count = sum(counts)
    total_population = sum(populations)
    n = len(counts)
    global_rate = total_count / total_population
    raw = [c / p for c, p in zip(counts, populations, strict=True)]

    # Marshall's variance component, which can come out negative when the
    # between-area variation is smaller than sampling noise alone would produce.
    # Negative variance is not a number: it means "no signal here", and the
    # honest response is to shrink everything to the global rate rather than to
    # take a square root of it.
    weighted = sum(
        p * (r - global_rate) ** 2 for p, r in zip(populations, raw, strict=True)
    )
    between = weighted / total_population - global_rate / (total_population / n)
    between = max(between, 0.0)

    shrinkage = [
        (between / (between + global_rate / p)) if between > 0 else 0.0
        for p in populations
    ]
    smoothed = [
        w * r + (1 - w) * global_rate
        for w, r in zip(shrinkage, raw, strict=True)
    ]

    out = gdf.copy()
    out["raw_rate"] = [r * per for r in raw]
    out["smoothed_rate"] = [s * per for s in smoothed]
    out["shrinkage"] = shrinkage

    record = ProvenanceRecord(
        operation="smooth_rates",
        parameters={
            "count_field": count_field,
            "population_field": population_field,
            "per": per,
            "method": "empirical Bayes, Marshall (1991) global prior",
            "global_rate": global_rate * per,
            "between_area_variance": between,
        },
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "geometry is carried through unchanged; the estimator is "
        "aspatial and uses only counts and populations",
    }
    if between == 0.0:
        record.notes.append(
            "the between-area variance came out at or below zero, which means the "
            "variation between areas is no larger than sampling noise alone would "
            "produce. Every area is shrunk to the global rate: on this data the "
            "differences you can see are not evidence of differences in risk."
        )

    # The write is INSIDE the net since 2026-09-07, and it moved down here
    # rather than the record moving up: nothing this record holds depends on
    # the write, and nothing between the two positions touches the file. A
    # write that raises after opening the file left the dataset on disk with
    # no manifest beside it -- measured, 516 bytes of a partial dataset.
    pre = verify.verify_loaded_inputs("smooth_rates", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        _write(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="smooth_rates",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(gdf.crs),
                expect_count=n,
            ),
            # Closed form: shrinking toward a weighted mean cannot move an
            # estimate outside the range spanned by that mean and the raw rate.
            # A smoothed rate above every raw rate is not smoothing.
            verify.Check(
                "x-mapsmith:every_estimate_lies_between_its_rate_and_the_global_one",
                all(
                    min(r, global_rate) - 1e-12 <= s <= max(r, global_rate) + 1e-12
                    for r, s in zip(raw, smoothed, strict=True)
                ),
                f"worst deviation from the interval: "
                f"{max((max(min(r, global_rate) - s, s - max(r, global_rate), 0.0) for r, s in zip(raw, smoothed, strict=True)), default=0.0):.3g}",
            ),
            # Only when the estimator collapsed to the global rate, and the name
            # says so. It used to be `... or between > 0`, which in the ordinary
            # case made the predicate true without measuring anything: on the
            # conformance fixture the weighted total was 7.9175 against an input
            # of 8.0 and the check was green. That is the `shape_matches_resolution`
            # defect, found the day after closing it — a name asserting a property
            # the check does not test, with a tick in the manifest to say so.
            #
            # Full shrinkage IS an identity: every estimate equals the global rate,
            # so the population-weighted sum reconstructs the total exactly.
            # Partial shrinkage is not, and there is nothing here to check.
            *(
                [
                    verify.Check(
                        "x-mapsmith:full_shrinkage_reconstructs_the_total",
                        math.isclose(
                            sum(
                                s * p
                                for s, p in zip(smoothed, populations, strict=True)
                            ),
                            total_count,
                            rel_tol=1e-6,
                        ),
                        f"{sum(s * p for s, p in zip(smoothed, populations, strict=True)):.6g} "
                        f"against an input total of {total_count:.6g}",
                        critical=False,
                    )
                ]
                if between == 0.0
                else []
            ),
        ],
    )
    return {
        "output": str(output_path),
        "features": n,
        "global_rate": global_rate * per,
        "per": per,
        "mean_shrinkage": sum(shrinkage) / n,
        "fully_shrunk": between == 0.0,
        "provenance": str(manifest),
        **extras,
    }


def aggregate_to_threshold(
    input_path: str,
    output_path: str,
    count_field: str,
    minimum: float,
) -> dict[str, Any]:
    """Merge neighbouring areas until every one meets a minimum count.

    Answers the disclosure-control question — *"the ethics committee is
    breathing down my neck about patient confidentiality"* — where publishing a
    count of two in a village of ninety identifies a person, and suppressing it
    while publishing the neighbours and the total identifies them anyway.

    Deterministic and greedy: repeatedly take the area with the smallest count
    that is still under the minimum, and merge it into whichever neighbour has
    the smallest count, ties broken by feature order. That produces the same
    grouping every run, which matters more here than optimality: a disclosure
    decision that changes between runs cannot be defended to an ethics committee.

    **An area with no neighbours cannot be merged**, and the operation refuses
    rather than emitting it below the threshold — quietly publishing the one
    island that could not be fixed is exactly the failure this prevents.
    """
    if minimum <= 0:
        raise ValueError(f"minimum must be positive, got {minimum}")
    gdf = _prepare(input_path, "aggregate_to_threshold", count_field)
    n = len(gdf)
    if n == 0:
        raise ValueError(f"{input_path} is empty.")

    neighbourhoods = _weights(gdf, "contiguity", None)
    groups: list[set[int]] = [{i} for i in range(n)]
    totals: list[float] = [float(v) for v in gdf[count_field]]
    adjacency: list[set[int]] = [set(row) for row in neighbourhoods]
    alive = set(range(n))

    stranded: list[int] = []
    while True:
        below = sorted(
            (g for g in alive if totals[g] < minimum),
            key=lambda g: (totals[g], min(groups[g])),
        )
        below = [g for g in below if g not in stranded]
        if not below:
            break
        target = below[0]
        options = sorted(adjacency[target] & alive, key=lambda g: (totals[g], min(groups[g])))
        if not options:
            stranded.append(target)
            continue
        into = options[0]
        groups[into] |= groups[target]
        totals[into] += totals[target]
        adjacency[into] = (adjacency[into] | adjacency[target]) - {target, into}
        for other in adjacency[target]:
            if other in alive and other != into:
                adjacency[other].discard(target)
                adjacency[other].add(into)
        alive.discard(target)

    if stranded:
        names = sorted(min(groups[g]) for g in stranded)
        raise ValueError(
            f"{len(stranded)} area(s) are below the minimum of {minimum} and have no "
            f"neighbour to merge into (feature index {names[:5]}). Publishing them "
            "as they are would be the disclosure this operation exists to prevent, "
            "and dropping them silently would change the total. Decide explicitly: "
            "remove them from the input, or lower the minimum."
        )

    order = sorted(alive, key=lambda g: min(groups[g]))
    from shapely import union_all

    records = []
    for group in order:
        members = sorted(groups[group])
        records.append(
            {
                "geometry": union_all([gdf.geometry.iloc[m] for m in members]),
                count_field: totals[group],
                "members": len(members),
                "source_indices": ",".join(str(m) for m in members),
            }
        )
    out = gpd.GeoDataFrame(records, geometry="geometry", crs=gdf.crs)

    record = ProvenanceRecord(
        operation="aggregate_to_threshold",
        parameters={
            "count_field": count_field,
            "minimum": minimum,
            "rule": "greedy: smallest area under the minimum merges into its "
            "smallest neighbour, ties by feature order",
        },
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "areas are merged in their own CRS; adjacency is topological and "
        "unit-free",
    }

    # The write is INSIDE the net since 2026-09-07, and it moved down here
    # rather than the record moving up: nothing this record holds depends on
    # the write, and nothing between the two positions touches the file. A
    # write that raises after opening the file left the dataset on disk with
    # no manifest beside it -- measured, 516 bytes of a partial dataset.
    pre = verify.verify_loaded_inputs("aggregate_to_threshold", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        _write(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="aggregate_to_threshold",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(gdf.crs),
                expect_count=len(order),
                max_count=n,
            ),
            # The two closed-form guarantees a disclosure-control step has to
            # make: nothing is left under the threshold, and nothing was lost.
            verify.Check(
                "x-mapsmith:no_group_is_below_the_minimum",
                all(totals[g] >= minimum for g in order),
                f"{sum(1 for g in order if totals[g] < minimum)} group(s) still below "
                f"{minimum}",
            ),
            verify.Check(
                "x-mapsmith:the_total_count_is_unchanged",
                math.isclose(
                    sum(totals[g] for g in order),
                    sum(float(v) for v in gdf[count_field]),
                    rel_tol=1e-9,
                ),
                f"{sum(totals[g] for g in order):.6g} after merging against "
                f"{sum(float(v) for v in gdf[count_field]):.6g} in the input",
            ),
            verify.Check(
                "x-mapsmith:every_input_area_is_in_exactly_one_group",
                sorted(m for g in order for m in groups[g]) == list(range(n)),
                f"{len([m for g in order for m in groups[g]])} placements for "
                f"{n} input areas",
            ),
        ],
    )
    return {
        "output": str(output_path),
        "input_areas": n,
        "groups": len(order),
        "merged_away": n - len(order),
        "minimum": minimum,
        "smallest_group_count": min(totals[g] for g in order),
        "provenance": str(manifest),
        **extras,
    }


def thin_points(
    input_path: str,
    output_path: str,
    min_distance: float,
    priority_field: str | None = None,
    keep_highest: bool = True,
) -> dict[str, Any]:
    """Keep points no closer together than a distance, deterministically.

    Answers two different-sounding requests that are the same operation: *"over
    a million dots, so the map completely freezes"* and *"the city names are a
    total mess of overlapping text — drop the smaller towns"*. The second is why
    `priority_field` exists: without it thinning keeps whichever point came
    first in the file, which on a label layer means keeping hamlets and dropping
    capitals.

    Greedy and order-defined: points are considered in priority order (ties by
    feature index), and a point is kept when no already-kept point lies within
    `min_distance`. That is deterministic — the same input gives the same output
    — which random or grid-jittered thinning is not, and a map that changes
    between runs cannot carry a manifest.

    **This removes data.** It is a display operation: the output is for drawing,
    not for counting, and the manifest says how many were dropped so that a
    total computed from the thinned layer is obviously wrong rather than subtly
    so.
    """
    if not (math.isfinite(min_distance) and min_distance > 0):
        raise ValueError(f"min_distance must be a positive number, got {min_distance}")
    gdf = _prepare(input_path, "thin_points", priority_field)
    readers.refuse_missing_geometry(
        gdf, input_path,
        "A point with no position cannot be near anything, so there is no answer for "
        "whether it is kept.",
    )
    kinds = set(gdf.geom_type.dropna().unique())
    if not kinds <= {"Point", "MultiPoint"}:
        raise ValueError(
            f"thin_points needs a point layer; {input_path} holds {sorted(kinds)}."
        )
    if gdf.crs.is_geographic:
        raise ValueError(
            f"{input_path} is in a geographic CRS, so a min_distance of "
            f"{min_distance} would be in DEGREES — about "
            f"{min_distance * 111_000:,.0f} m of latitude and a different distance "
            "at every longitude. Reproject first."
        )

    points = list(gdf.geometry.representative_point())
    if priority_field is None:
        order = list(range(len(points)))
    else:
        order = sorted(
            range(len(points)),
            key=lambda i: (
                -float(gdf[priority_field].iloc[i])
                if keep_highest
                else float(gdf[priority_field].iloc[i]),
                i,
            ),
        )

    kept: list[int] = []
    kept_points: list[Any] = []
    for index in order:
        candidate = points[index]
        if all(candidate.distance(other) >= min_distance for other in kept_points):
            kept.append(index)
            kept_points.append(candidate)

    out = gdf.iloc[sorted(kept)].copy()

    # Once, into a name. Both arguments of a `Check` are evaluated eagerly, so
    # calling this in the predicate AND in the detail ran an O(k^2) sweep twice:
    # measured, 43.7 s of the 67 s that thinning 4,000 points took.
    separation = _minimum_separation(kept_points)

    record = ProvenanceRecord(
        operation="thin_points",
        parameters={
            "min_distance": min_distance,
            "priority_field": priority_field,
            "keep_highest": keep_highest if priority_field else None,
            "rule": "greedy in priority order, ties by feature index",
            "removes_data": True,
        },
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "spacing is measured in the layer's own CRS, whose unit the "
        "min_distance is read in",
    }
    record.notes.append(
        f"{len(gdf) - len(kept)} of {len(gdf)} points were removed. The output is "
        "for drawing: any total computed from it is a total of what survived "
        "thinning, not of the data."
    )

    # The write is INSIDE the net since 2026-09-07, and it moved down here
    # rather than the record moving up: nothing this record holds depends on
    # the write, and nothing between the two positions touches the file. A
    # write that raises after opening the file left the dataset on disk with
    # no manifest beside it -- measured, 516 bytes of a partial dataset.
    pre = verify.verify_loaded_inputs("thin_points", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        _write(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="thin_points",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(gdf.crs),
                expect_count=len(kept),
                max_count=len(gdf),
                on_empty="warn",
            ),
            # The property the operation is named for, checked on the output
            # rather than assumed from the loop that produced it.
            verify.Check(
                "x-mapsmith:no_two_kept_points_are_closer_than_the_minimum",
                separation >= min_distance - 1e-9,
                f"closest surviving pair is {separation:.6g} apart, minimum was "
                f"{min_distance}",
            ),
        ],
    )
    return {
        "output": str(output_path),
        "input_points": len(gdf),
        "kept": len(kept),
        "removed": len(gdf) - len(kept),
        "min_distance": min_distance,
        "provenance": str(manifest),
        **extras,
    }


def cluster_points_by_distance(
    input_path: str,
    output_path: str,
    max_distance: float,
) -> dict[str, Any]:
    """Group points that are chained together within a distance, and keep them all.

    Answers *"group everything within half a kilometre"*, which is not what
    `thin_points` does: thinning keeps one representative per crowd and drops
    the rest, so its count is close to the number of groups and not equal to it.
    Here two points belong to the same cluster when a chain of points joins
    them with every link at most `max_distance` long (single linkage: the
    connected components of the "within distance" graph). **Chains merge**: A
    and C are in one cluster when B lies within the distance of both, even if
    A and C are twice that apart. A biologist asking "how many groups" and a
    planner asking "which sites are within walking distance of each other" both
    mean this; the manifest says it in words so that nobody reads a cluster as
    a circle of radius `max_distance`.

    Deterministic: cluster ids are numbered in the order of each cluster's
    first feature in the file, so the same input gives the same ids. Nothing is
    removed; each point gains `cluster_id` and `cluster_size`.
    """
    # `not (> 0)` rather than `<= 0`: NaN compares false with everything, so
    # `NaN <= 0` let it through and every point came back a cluster of one.
    if not (math.isfinite(max_distance) and max_distance > 0):
        raise ValueError(f"max_distance must be a positive number, got {max_distance}")
    if str(output_path).lower().endswith(".shp"):
        raise ValueError(
            "refusing to write a shapefile: field names are truncated to 10 characters, "
            "so `cluster_size` would arrive as `cluster_si` with nothing saying so. "
            "Write GeoParquet (.parquet) or GeoPackage (.gpkg) instead."
        )
    import shapely

    gdf = _prepare(input_path, "cluster_points_by_distance")
    missing = gdf.geometry.isna() | gdf.geometry.is_empty
    if missing.any():
        raise ValueError(
            f"{input_path} has {int(missing.sum())} feature(s) with no or an empty "
            "geometry. A point with no position belongs to no cluster, and counting it "
            "as a cluster of one would change the answer; remove those features first."
        )
    kinds = set(gdf.geom_type.unique())
    if not kinds <= {"Point", "MultiPoint"}:
        raise ValueError(
            f"cluster_points_by_distance needs a point layer; {input_path} holds "
            f"{sorted(kinds)}."
        )
    # A MultiPoint's distance to another is between its NEAREST parts, so one
    # feature with parts 100 km apart would chain two groups that no link joins,
    # and `cluster_size` would count it as one point (found by the geo review).
    if (shapely.get_num_geometries(gdf.geometry.to_numpy()) > 1).any():
        raise ValueError(
            f"{input_path} has MultiPoint features with more than one part. Each part "
            "is a point to cluster; run explode_layer first so that each is a feature."
        )
    if gdf.crs.is_geographic:
        raise ValueError(
            f"{input_path} is in a geographic CRS, so a max_distance of "
            f"{max_distance} would be in DEGREES — about "
            f"{max_distance * 111_000:,.0f} m of latitude and a different distance "
            "at every longitude. Reproject first."
        )
    # The record says `removes_data: false`, and replacing an input column of
    # the same name would make that sentence false without a trace in it.
    clashing = sorted({"cluster_id", "cluster_size"} & set(gdf.columns))
    if clashing:
        raise ValueError(
            f"{input_path} already has column(s) {clashing}, which this operation "
            "would overwrite. Rename them first, so the output cannot silently "
            "replace a value that was in the input."
        )

    # An object array, not a list: shapely cannot infer the dtype of an empty
    # list and raised a TypeError on an empty layer, which `thin_points` and
    # `on_empty="warn"` below treat as a result rather than a crash.
    geometries = gdf.geometry.to_numpy()
    unit = _unit_of(gdf)
    pairs = _pairs_within(geometries, max_distance)

    # Union-find over the "within distance" pairs: the connected components are
    # the clusters. Roots are kept at the smallest index, which is what makes the
    # numbering below independent of the order the pairs come back in.
    parent = list(range(len(geometries)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in zip(pairs[0].tolist(), pairs[1].tolist(), strict=True):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots = [root(i) for i in range(len(geometries))]
    number = {r: n for n, r in enumerate(sorted(set(roots)), start=1)}
    ids = [number[r] for r in roots]
    sizes: dict[int, int] = {}
    for cid in ids:
        sizes[cid] = sizes.get(cid, 0) + 1

    out = gdf.copy()
    out["cluster_id"] = ids
    out["cluster_size"] = [sizes[cid] for cid in ids]
    clusters = len(sizes)
    singletons = sum(1 for n in sizes.values() if n == 1)
    largest = max(sizes.values(), default=0)

    record = ProvenanceRecord(
        operation="cluster_points_by_distance",
        parameters={
            "max_distance": max_distance,
            "unit": unit,
            "rule": "single linkage: connected components of the within-distance graph, "
            "distance inclusive",
            "cluster_numbering": "in the order of each cluster's first feature",
            "removes_data": False,
        },
        inputs=[InputRecord.from_path(input_path, crs=verify.crs_label(gdf.crs))],
        engine=_engine_info(),
    )
    record.crs_decisions = {
        "analysis_crs": verify.crs_label(gdf.crs),
        "reason": "distances are measured in the layer's own CRS, whose unit the "
        "max_distance is read in",
    }
    record.notes.append(
        f"{len(gdf)} points in {clusters} clusters ({singletons} of one point, largest "
        f"{largest}), linking points at most {max_distance} {unit} apart. Clusters "
        "chain: two points in one cluster can be much farther apart than that, because "
        "each link, not the cluster, is bounded."
    )

    pre = verify.verify_loaded_inputs("cluster_points_by_distance", input_path=gdf)
    with verify.audit_on_failure(record, output_path, pre):
        _write(out, output_path)

    manifest, extras = verify.audited(
        record,
        output_path,
        operation="cluster_points_by_distance",
        preconditions=pre,
        checks_fn=lambda: [
            *verify.verify_vector_output(
                output_path,
                expect_crs=verify.crs_label(gdf.crs),
                expect_count=len(gdf),
                on_empty="warn",
            ),
            _clusters_match_the_written_points(output_path, max_distance),
        ],
    )
    return {
        "output": str(output_path),
        "points": len(gdf),
        "clusters": clusters,
        "singletons": singletons,
        "largest_cluster": largest,
        "max_distance": max_distance,
        "distance_unit": unit,
        "provenance": str(manifest),
        **extras,
    }


def _unit_of(gdf: Any) -> str:
    """The linear unit `max_distance` is read in, as the CRS names it."""
    try:
        return gdf.crs.axis_info[0].unit_name
    except (AttributeError, IndexError):  # pragma: no cover - exotic CRS
        return "unit"


#: Points queried against the tree at a time. Small enough that one block of
#: ordered pairs stays in memory comfortably before it is halved.
_PAIR_BLOCK = 2048


def _pairs_within(geometries: Any, distance: float) -> Any:
    """Each unordered pair within the distance once: no self-pairs, no mirror.

    The tree answers every ordered pair and every point with itself, which on a
    dense layer doubled the pairs and added one per point for nothing: 3,000
    points all within the distance gave nine million (measured by the review).

    Queried in blocks, and refused past the operator's limit
    (`MAPSMITH_MAX_SAMPLES`, counted in pairs) before the next block is
    allocated. The number of pairs grows with the square of the points when the
    distance is large, and the distance is the agent's argument: the 0.8.0
    audit measured 6,000 points at a distance of 1e9 taking two minutes and
    2.3 GB, and a layer of a few tens of thousands exhausting memory.
    """
    import numpy as np
    from shapely import STRtree

    from .. import limits

    cap = limits.max_samples()
    tree = STRtree(geometries)
    blocks, total = [], 0
    for start in range(0, len(geometries), _PAIR_BLOCK):
        found = tree.query(
            geometries[start : start + _PAIR_BLOCK], predicate="dwithin", distance=distance
        )
        found[0] += start
        found = found[:, found[0] < found[1]]
        total += found.shape[1]
        if total > cap:
            raise ValueError(
                f"a distance of {distance} joins more than {cap:,} pairs of points in this "
                f"layer, over this server's limit (after {min(start + _PAIR_BLOCK, len(geometries)):,} "
                f"of {len(geometries):,} points). Use a smaller distance, or ask the operator "
                f"to raise {limits.MAX_SAMPLES_ENV}: it is a setting of the server, not an "
                "argument of the tool."
            )
        blocks.append(found)
    if not blocks:
        return np.empty((2, 0), dtype=np.intp)
    return np.concatenate(blocks, axis=1)


def _clusters_match_the_written_points(output_path: str, max_distance: float) -> Any:
    """Re-derive the clusters from the WRITTEN file, by another algorithm.

    A check that re-read the pairs the union-find had just merged could not
    fail (the guard that cannot fail, D-079). This one reads the output back,
    recomputes the within-distance pairs from the geometries on disk, and walks
    them breadth-first -- a different algorithm from the union-find that
    assigned the ids. It checks what the output promises: no pair within the
    distance straddles two clusters, no cluster holds points that no chain
    joins, every `cluster_size` is its cluster's count, and ids are numbered in
    the order of each cluster's first feature.
    """
    from collections import Counter, deque

    import numpy as np

    written = readers.read_vector(output_path)
    geometries = written.geometry.to_numpy()
    ids = np.asarray(written["cluster_id"], dtype=np.int64)
    sizes = np.asarray(written["cluster_size"], dtype=np.int64)
    pairs = _pairs_within(geometries, max_distance)
    straddling = int((ids[pairs[0]] != ids[pairs[1]]).sum())

    neighbours: dict[int, list[int]] = {i: [] for i in range(len(geometries))}
    for a, b in zip(pairs[0].tolist(), pairs[1].tolist(), strict=True):
        neighbours[a].append(b)
        neighbours[b].append(a)
    seen: set[int] = set()
    components = 0
    for start in range(len(geometries)):
        if start in seen:
            continue
        components += 1
        queue = deque([start])
        seen.add(start)
        while queue:
            for nxt in neighbours[queue.popleft()]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)

    counts = Counter(ids.tolist())
    wrong_sizes = sum(
        1 for cid, size in zip(ids.tolist(), sizes.tolist(), strict=True) if counts[cid] != size
    )
    first_seen = list(dict.fromkeys(ids.tolist()))
    in_order = first_seen == list(range(1, len(first_seen) + 1))
    labelled = len(counts)
    return verify.Check(
        "x-mapsmith:clusters_are_the_chains_of_the_written_points",
        straddling == 0 and components == labelled and wrong_sizes == 0 and in_order,
        f"re-read {len(geometries)} points: {components} chains within {max_distance}, "
        f"{labelled} cluster ids, {straddling} within-distance pairs across two ids, "
        f"{wrong_sizes} wrong cluster_size values, ids "
        f"{'numbered' if in_order else 'NOT numbered'} in the order of first features",
    )


def _minimum_separation(points: list[Any]) -> float:
    if len(points) < 2:
        return math.inf
    return min(
        points[i].distance(points[j])
        for i in range(len(points))
        for j in range(i + 1, len(points))
    )
