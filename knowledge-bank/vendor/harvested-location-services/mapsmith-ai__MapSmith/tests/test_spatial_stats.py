"""Four statistics, each with an answer worked out on paper before it ran.

Gi* has a closed form small enough to evaluate by hand; empirical Bayes has an
exact fixed point when every rate is equal; the aggregation and the thinning are
both deterministic greedy walks whose outcome can be traced step by step. Every
expected value below was derived that way and then compared, not read off a run
and pasted back in.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import LineString, Point, box

from mapsmith.engines import spatial_stats


def _manifest(output: Path) -> dict:
    return json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))


def _named(output: Path) -> dict:
    return {c["name"]: c for c in _manifest(output)["verification"]}


def _squares(counts, tmp_path: Path, name: str, extra: dict | None = None) -> Path:
    """A west-to-east strip of touching 100 m squares."""
    path = tmp_path / f"{name}.gpkg"
    data = {"n": list(counts)}
    data.update(extra or {})
    gpd.GeoDataFrame(
        data,
        geometry=[box(i * 100, 0, (i + 1) * 100, 100) for i in range(len(counts))],
        crs="EPSG:32632",
    ).to_file(path, layer="a", driver="GPKG")
    return path


# ------------------------------------------------------------------- Gi*

def test_gi_star_matches_the_value_worked_out_by_hand(tmp_path):
    """Four features in two pairs, values 4, 0, 0, 0.

    mean = 1, sum of squares = 16, variance = 16/4 - 1 = 3, S = sqrt(3). The
    band pairs 0 with 1 and 2 with 3, so every neighbourhood is two features
    including self: sum of weights = 2, sum of squared weights = 2, and the
    denominator is S * sqrt((4*2 - 4)/3) = sqrt(3) * sqrt(4/3) = 2.

    Features 0 and 1: (4 + 0) - 1*2 = 2, over 2 -> z = +1 exactly.
    Features 2 and 3: (0 + 0) - 1*2 = -2, over 2 -> z = -1 exactly.

    Paired rather than isolated because a layer where every feature is alone is
    refused now: Gi* over a neighbourhood of one is the value's own z-score and
    measures no clustering, which is a different statistic under this one's name.
    """
    path = tmp_path / "four.gpkg"
    gpd.GeoDataFrame(
        {"v": [4.0, 0.0, 0.0, 0.0]},
        geometry=[Point(0, 0), Point(10, 0), Point(2000, 0), Point(2010, 0)],
        crs="EPSG:32632",
    ).to_file(path, layer="p", driver="GPKG")

    out = tmp_path / "gi.parquet"
    spatial_stats.hot_spots(
        str(path), str(out), value_field="v", weights="distance_band",
        distance_band=50.0,
    )
    got = gpd.read_parquet(out)
    assert got["gi_z"].tolist() == pytest.approx([1.0, 1.0, -1.0, -1.0])
    assert got["neighbours"].tolist() == [1, 1, 1, 1]


def test_a_layer_where_every_feature_is_alone_is_refused(tmp_path):
    """Not a warning: a different statistic wearing this one's name.

    With no neighbours, Gi* reduces to the z-score of the value against the
    global distribution — it measures no clustering at all. A few islands are
    data; half the layer is an analysis that did not happen, and the map would
    be published under the word "hot spots".
    """
    path = tmp_path / "alone.gpkg"
    gpd.GeoDataFrame(
        {"v": [4.0, 0.0, 0.0, 0.0]},
        geometry=[Point(0, 0), Point(1000, 0), Point(2000, 0), Point(3000, 0)],
        crs="EPSG:32632",
    ).to_file(path, layer="p", driver="GPKG")

    from mapsmith.verify import VerificationError

    with pytest.raises(VerificationError, match="isolated"):
        spatial_stats.hot_spots(
            str(path), str(tmp_path / "x.parquet"), value_field="v",
            weights="distance_band", distance_band=10.0,
        )


def test_boundaries_that_overlap_by_a_millimetre_are_still_neighbours(tmp_path):
    """`touches` is false for polygons that overlap, and real ones do.

    A strip of five areas overlapping by 1 mm came back with zero neighbours
    each — Gi* silently became a z-score, with a non-critical note as the only
    trace. Same class of defect as the network tolerance, which this module was
    treating as a warning.
    """
    path = tmp_path / "sloppy.gpkg"
    gpd.GeoDataFrame(
        {"n": [1.0, 2.0, 3.0, 4.0, 5.0]},
        geometry=[
            box(i * 100 - 0.001, 0, (i + 1) * 100 + 0.001, 100) for i in range(5)
        ],
        crs="EPSG:32632",
    ).to_file(path, layer="a", driver="GPKG")

    out = tmp_path / "sloppy.parquet"
    result = spatial_stats.hot_spots(
        str(path), str(out), value_field="n", weights="contiguity"
    )
    assert result["isolated"] == 0, "a 1 mm overlap disconnected the whole layer"
    assert gpd.read_parquet(out)["neighbours"].tolist() == [1, 2, 2, 2, 1]


def test_a_neighbourhood_that_is_the_whole_layer_scores_zero(tmp_path):
    """Not a special case — the formula says so, and it is worth pinning.

    When every feature is a neighbour of every other, the sum of weights is n
    and the sum of squared weights is n, so `n*n - n*n` is zero: there is
    nothing to compare the neighbourhood against. A z of 0 is the answer; a
    division that raises, or a spurious extreme, would not be.
    """
    path = tmp_path / "close.gpkg"
    gpd.GeoDataFrame(
        {"v": [4.0, 0.0, 0.0, 0.0]},
        geometry=[Point(0, 0), Point(1, 0), Point(2, 0), Point(3, 0)],
        crs="EPSG:32632",
    ).to_file(path, layer="p", driver="GPKG")

    out = tmp_path / "all.parquet"
    spatial_stats.hot_spots(
        str(path), str(out), value_field="v", weights="distance_band",
        distance_band=1000.0,
    )
    assert gpd.read_parquet(out)["gi_z"].tolist() == [0.0, 0.0, 0.0, 0.0]


def test_identical_values_produce_no_hot_spots_anywhere(tmp_path):
    path = _squares([5, 5, 5, 5, 5], tmp_path, "flat")
    out = tmp_path / "flat.parquet"
    result = spatial_stats.hot_spots(
        str(path), str(out), value_field="n", weights="contiguity"
    )
    assert result["significant"] == 0
    assert set(gpd.read_parquet(out)["hot_or_cold"]) == {"not significant"}


def test_the_multiple_testing_correction_removes_findings_and_says_how_many(tmp_path):
    """The number that gets published, and the number before the correction.

    A clustered high tail produces several individually significant features; the
    false-discovery-rate step-up keeps fewer. If it ever kept MORE, the step-up
    is implemented backwards and the map would carry more false clusters than no
    correction at all — which is what the check in the manifest is for.
    """
    counts = [1, 1, 1, 1, 1, 1, 1, 1, 40, 40]
    path = _squares(counts, tmp_path, "tail")
    out = tmp_path / "tail.parquet"
    result = spatial_stats.hot_spots(
        str(path), str(out), value_field="n", weights="contiguity"
    )
    assert result["significant"] <= result["significant_before_correction"]
    assert _named(out)["x-mapsmith:the_correction_only_removes_findings"]["passed"]
    manifest = _manifest(out)
    assert manifest["parameters"]["multiple_testing"].startswith("Benjamini-Hochberg")


def test_an_isolated_feature_is_reported_rather_than_scored_in_silence(tmp_path):
    path = tmp_path / "island.gpkg"
    gpd.GeoDataFrame(
        {"n": [1.0, 2.0, 3.0]},
        geometry=[
            box(0, 0, 100, 100),
            box(100, 0, 200, 100),
            box(9000, 9000, 9100, 9100),
        ],
        crs="EPSG:32632",
    ).to_file(path, layer="a", driver="GPKG")

    out = tmp_path / "island.parquet"
    result = spatial_stats.hot_spots(
        str(path), str(out), value_field="n", weights="contiguity"
    )
    assert result["isolated"] == 1
    check = _named(out)["x-mapsmith:every_feature_has_a_neighbour"]
    assert check["passed"] is False and check["critical"] is False
    assert any("no neighbours at all" in note for note in _manifest(out)["notes"])


def test_a_distance_band_in_degrees_is_refused(tmp_path):
    path = tmp_path / "geo.gpkg"
    gpd.GeoDataFrame(
        {"n": [1.0, 2.0, 3.0]},
        geometry=[Point(11, 45), Point(11.01, 45), Point(11.02, 45)],
        crs="EPSG:4326",
    ).to_file(path, layer="p", driver="GPKG")
    with pytest.raises(ValueError, match="DEGREES"):
        spatial_stats.hot_spots(
            str(path), str(tmp_path / "x.parquet"), value_field="n",
            weights="distance_band", distance_band=1000.0,
        )


def test_a_missing_value_is_refused_rather_than_read_as_zero(tmp_path):
    path = _squares([1.0, None, 3.0], tmp_path, "gappy")
    with pytest.raises(ValueError, match="missing value is not a zero"):
        spatial_stats.hot_spots(
            str(path), str(tmp_path / "x.parquet"), value_field="n",
            weights="contiguity",
        )


# --------------------------------------------------------- empirical Bayes

def test_equal_rates_shrink_to_themselves_exactly(tmp_path):
    """The fixed point. Every area has the same rate, so there is nothing for the
    estimator to borrow and the smoothed rate must equal the raw one — to the
    last bit, not approximately."""
    path = _squares([1, 2, 3], tmp_path, "same", {"pop": [100, 200, 300]})
    out = tmp_path / "same.parquet"
    result = spatial_stats.smooth_rates(
        str(path), str(out), count_field="n", population_field="pop"
    )
    got = gpd.read_parquet(out)
    assert got["raw_rate"].tolist() == pytest.approx([1000.0, 1000.0, 1000.0])
    assert got["smoothed_rate"].tolist() == pytest.approx([1000.0, 1000.0, 1000.0])
    assert result["global_rate"] == pytest.approx(1000.0)
    assert result["fully_shrunk"] is True
    assert any("no larger than sampling noise" in n for n in _manifest(out)["notes"])


def test_a_tiny_denominator_is_pulled_toward_the_global_rate_and_a_large_one_is_not(
    tmp_path
):
    """The whole point: one case in a village of 120 is 833 per 100,000 and the
    map of raw rates is a map of which districts are small.

    Village and city both have one case. The village's estimate must move far
    toward the global rate and the city's must barely move, and the shrinkage
    column has to make that visible rather than leaving the reader to guess
    which numbers are evidence.
    """
    path = _squares(
        [1, 1, 50, 60], tmp_path, "denominators",
        {"pop": [120, 500_000, 400_000, 500_000]},
    )
    out = tmp_path / "eb.parquet"
    spatial_stats.smooth_rates(
        str(path), str(out), count_field="n", population_field="pop"
    )
    got = gpd.read_parquet(out)
    village, city = got.iloc[0], got.iloc[1]

    assert village["raw_rate"] == pytest.approx(1 / 120 * 100_000)
    assert village["shrinkage"] < 0.05, (
        "a village of 120 carries almost no information about its own risk and "
        "must be shrunk hard"
    )
    assert city["shrinkage"] > village["shrinkage"] * 10
    assert village["smoothed_rate"] < village["raw_rate"] / 4, (
        "the 833-per-100,000 spike survived the smoothing"
    )
    assert _named(out)[
        "x-mapsmith:every_estimate_lies_between_its_rate_and_the_global_one"
    ]["passed"]


def test_a_zero_population_is_refused_with_somewhere_to_go(tmp_path):
    path = _squares([1, 2], tmp_path, "empty", {"pop": [0, 100]})
    with pytest.raises(ValueError, match="aggregate_to_threshold"):
        spatial_stats.smooth_rates(
            str(path), str(tmp_path / "x.parquet"), count_field="n",
            population_field="pop",
        )


# ----------------------------------------------------- disclosure control

def test_the_greedy_merge_follows_the_rule_step_by_step(tmp_path):
    """Counts [1, 1, 5, 1, 1] with a minimum of 2, traced by hand.

    The smallest under the minimum is index 0 (tie at 1, broken by order); its
    only neighbour is 1, so they merge to 2. Then index 3, whose neighbours are
    2 (five) and 4 (one): the smaller is 4, so they merge to 2. Nothing is left
    under the minimum. Three groups: 2, 5, 2 — and the total is still 9.
    """
    path = _squares([1, 1, 5, 1, 1], tmp_path, "strip")
    out = tmp_path / "merged.parquet"
    result = spatial_stats.aggregate_to_threshold(
        str(path), str(out), count_field="n", minimum=2
    )
    got = gpd.read_parquet(out)
    assert result["groups"] == 3
    assert got["n"].tolist() == pytest.approx([2.0, 5.0, 2.0])
    assert got["source_indices"].tolist() == ["0,1", "2", "3,4"]
    assert got["members"].tolist() == [2, 1, 2]

    checks = _named(out)
    assert checks["x-mapsmith:no_group_is_below_the_minimum"]["passed"]
    assert checks["x-mapsmith:the_total_count_is_unchanged"]["passed"]
    assert checks["x-mapsmith:every_input_area_is_in_exactly_one_group"]["passed"]


def test_the_same_input_merges_the_same_way_every_time(tmp_path):
    """A disclosure decision that changes between runs cannot be defended."""
    path = _squares([1, 1, 1, 1, 1, 1], tmp_path, "ties")
    first, second = tmp_path / "a.parquet", tmp_path / "b.parquet"
    for out in (first, second):
        spatial_stats.aggregate_to_threshold(
            str(path), str(out), count_field="n", minimum=3
        )
    assert (
        gpd.read_parquet(first)["source_indices"].tolist()
        == gpd.read_parquet(second)["source_indices"].tolist()
    )


def test_an_island_below_the_threshold_is_refused_not_published(tmp_path):
    """The failure this operation exists to prevent, in its purest form: one
    area that cannot be merged and would otherwise be emitted below the
    threshold, quietly, among a page of compliant ones."""
    path = tmp_path / "island.gpkg"
    gpd.GeoDataFrame(
        {"n": [5.0, 5.0, 1.0]},
        geometry=[
            box(0, 0, 100, 100),
            box(100, 0, 200, 100),
            box(9000, 9000, 9100, 9100),
        ],
        crs="EPSG:32632",
    ).to_file(path, layer="a", driver="GPKG")

    with pytest.raises(ValueError, match="no neighbour to merge into"):
        spatial_stats.aggregate_to_threshold(
            str(path), str(tmp_path / "x.parquet"), count_field="n", minimum=3
        )


# ---------------------------------------------------------------- thinning

def test_thinning_keeps_the_first_of_each_crowded_group(tmp_path):
    """Points at 0, 10, 20, 30 with a minimum of 15, traced by hand.

    Keep 0. The point at 10 is 10 away: drop. The point at 20 is 20 from the
    last kept: keep. The point at 30 is 10 from that: drop. Two survive.
    """
    path = tmp_path / "row.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a", "b", "c", "d"]},
        geometry=[Point(x, 0) for x in (0, 10, 20, 30)],
        crs="EPSG:32632",
    ).to_file(path, layer="p", driver="GPKG")

    out = tmp_path / "thin.parquet"
    result = spatial_stats.thin_points(str(path), str(out), min_distance=15.0)
    assert gpd.read_parquet(out)["name"].tolist() == ["a", "c"]
    assert result["kept"] == 2 and result["removed"] == 2
    assert _named(out)[
        "x-mapsmith:no_two_kept_points_are_closer_than_the_minimum"
    ]["passed"]


def test_a_priority_field_keeps_the_capital_and_drops_the_hamlets(tmp_path):
    """Without it, thinning a label layer keeps whichever town came first in the
    file — which is how a map ends up naming three hamlets and no city.

    Same four positions, but the point at x=10 has the largest population. It is
    considered first and kept; 0 and 20 are within 15 of it and go; 30 is 20
    away from it and survives.
    """
    path = tmp_path / "towns.gpkg"
    gpd.GeoDataFrame(
        {"name": ["a", "capital", "c", "d"], "pop": [10, 900_000, 20, 30]},
        geometry=[Point(x, 0) for x in (0, 10, 20, 30)],
        crs="EPSG:32632",
    ).to_file(path, layer="p", driver="GPKG")

    out = tmp_path / "labels.parquet"
    spatial_stats.thin_points(
        str(path), str(out), min_distance=15.0, priority_field="pop"
    )
    assert gpd.read_parquet(out)["name"].tolist() == ["capital", "d"]


def test_thinning_says_in_the_manifest_that_it_removed_data(tmp_path):
    path = tmp_path / "many.gpkg"
    gpd.GeoDataFrame(
        {"id": list(range(20))},
        geometry=[Point(x, 0) for x in range(20)],
        crs="EPSG:32632",
    ).to_file(path, layer="p", driver="GPKG")

    out = tmp_path / "few.parquet"
    result = spatial_stats.thin_points(str(path), str(out), min_distance=5.0)
    notes = _manifest(out)["notes"]
    assert any("were removed" in note and "for drawing" in note for note in notes), (
        "a layer that has had points removed must say so, or a total computed "
        "from it is wrong in a way nobody can see"
    )
    assert _manifest(out)["parameters"]["removes_data"] is True
    assert result["kept"] == 4  # 0, 5, 10, 15


def test_a_thinning_distance_in_degrees_is_refused(tmp_path):
    path = tmp_path / "geo.gpkg"
    gpd.GeoDataFrame(
        {"id": [1, 2]}, geometry=[Point(11, 45), Point(11.01, 45)], crs="EPSG:4326"
    ).to_file(path, layer="p", driver="GPKG")
    with pytest.raises(ValueError, match="DEGREES"):
        spatial_stats.thin_points(
            str(path), str(tmp_path / "x.parquet"), min_distance=500.0
        )


def test_the_total_check_is_emitted_only_when_it_has_something_to_check(tmp_path):
    """A check that cannot fail is a tick in the manifest saying nothing.

    `the_population_weighted_total_is_preserved` used to read
    `math.isclose(...) or between > 0`, so in the ordinary case the predicate was
    true without measuring anything: on the conformance fixture the weighted
    total was 7.9175 against an input of 8.0 and the check was green. That is the
    `shape_matches_resolution` defect, found the day after closing it.

    Full shrinkage IS an identity, so the check is emitted there and nowhere
    else, and its name says which case it is about.
    """
    equal = _squares([1, 2, 3], tmp_path, "equal", {"pop": [100, 200, 300]})
    out = tmp_path / "equal.parquet"
    result = spatial_stats.smooth_rates(
        str(equal), str(out), count_field="n", population_field="pop"
    )
    assert result["fully_shrunk"] is True
    check = _named(out)["x-mapsmith:full_shrinkage_reconstructs_the_total"]
    assert check["passed"] is True
    assert "against an input total of 6" in check["detail"]

    spread = _squares(
        [1, 1, 50, 60], tmp_path, "spread",
        {"pop": [120, 500_000, 400_000, 500_000]},
    )
    partial = tmp_path / "spread.parquet"
    spatial_stats.smooth_rates(
        str(spread), str(partial), count_field="n", population_field="pop"
    )
    assert "x-mapsmith:full_shrinkage_reconstructs_the_total" not in _named(partial), (
        "the check is present under partial shrinkage, where the identity does "
        "not hold and there is nothing for it to verify"
    )


def test_a_detail_never_states_the_opposite_of_what_passed_says(tmp_path):
    """Three checks used to carry the failure sentence on a passing result.

    A reader opening the manifest of a disclosure-control run found a green tick
    next to "the merged counts do not add up to the input's total". The detail is
    prose the spec asks for to carry the diagnosis; contradicting `passed` is
    worse than leaving it empty.
    """
    path = _squares([1, 1, 5, 1, 1], tmp_path, "detail")
    out = tmp_path / "detail.parquet"
    spatial_stats.aggregate_to_threshold(
        str(path), str(out), count_field="n", minimum=2
    )
    for check in _manifest(out)["verification"]:
        if not check["passed"]:
            continue
        wording = check["detail"].lower()
        assert not any(
            phrase in wording
            for phrase in ("do not", "does not", "is missing", "fell outside")
        ), (
            f"{check['name']} passed and its detail reads like a failure: "
            f"{check['detail']!r}"
        )


def _row(tmp_path, xs, crs="EPSG:32632", name="row.gpkg"):
    path = tmp_path / name
    gpd.GeoDataFrame(
        {"name": [f"p{i}" for i in range(len(xs))]},
        geometry=[Point(x, 0) for x in xs],
        crs=crs,
    ).to_file(path, layer="p", driver="GPKG")
    return path


def test_clustering_chains_where_thinning_drops(tmp_path):
    """Points at 0, 400, 800 and 5000, 5300 with a 500 m link, traced by hand.

    0-400 and 400-800 are links, so 0 and 800 share a cluster although they are
    800 apart; 5000-5300 is a link; 800-5000 is not. Two clusters, of three and
    two. Thinning the same points at 500 keeps 0, 800 and 5000 -- three -- which
    is the difference the operation exists for.
    """
    path = _row(tmp_path, [0, 400, 800, 5000, 5300])
    out = tmp_path / "groups.parquet"
    result = spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    written = gpd.read_parquet(out)
    assert written["cluster_id"].tolist() == [1, 1, 1, 2, 2]
    assert written["cluster_size"].tolist() == [3, 3, 3, 2, 2]
    assert (result["clusters"], result["singletons"], result["largest_cluster"]) == (2, 0, 3)
    assert len(written) == 5, "clustering removes nothing"
    assert _named(out)["x-mapsmith:clusters_are_the_chains_of_the_written_points"]["passed"]
    thinned = spatial_stats.thin_points(str(path), str(tmp_path / "t.parquet"), min_distance=500.0)
    assert thinned["kept"] == 3


def test_a_distance_joining_too_many_pairs_is_refused_before_anything_is_written(
    tmp_path, monkeypatch
):
    """Ten points all within the distance are 45 pairs; a limit of 10 refuses them.

    The pairs grow with the square of the points when the distance is large, and
    the distance is the agent's argument (0.8.0 audit: 6,000 points at 1e9 took
    two minutes and 2.3 GB). The limit is the operator's, not the tool's.
    """
    monkeypatch.setenv("MAPSMITH_MAX_SAMPLES", "10")
    path = _row(tmp_path, [10 * i for i in range(10)])
    out = tmp_path / "g.parquet"
    with pytest.raises(ValueError, match="MAPSMITH_MAX_SAMPLES"):
        spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=1e9)
    assert not out.exists()
    assert not Path(str(out) + ".provenance.json").exists()


def test_the_pairs_are_the_same_across_block_boundaries(tmp_path, monkeypatch):
    """The query runs in blocks; blocks of three must find the chain test's links."""
    monkeypatch.setattr(spatial_stats, "_PAIR_BLOCK", 3)
    path = _row(tmp_path, [0, 400, 800, 5000, 5300])
    out = tmp_path / "groups.parquet"
    spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    written = gpd.read_parquet(out)
    assert written["cluster_id"].tolist() == [1, 1, 1, 2, 2]
    assert written["cluster_size"].tolist() == [3, 3, 3, 2, 2]


def test_a_link_exactly_at_the_distance_joins(tmp_path):
    path = _row(tmp_path, [0, 500, 1001])
    out = tmp_path / "g.parquet"
    result = spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    assert gpd.read_parquet(out)["cluster_id"].tolist() == [1, 1, 2]
    assert result["singletons"] == 1


def test_cluster_ids_follow_the_order_of_first_features(tmp_path):
    # The lone far point comes first in the file, so its cluster is number 1.
    path = _row(tmp_path, [9000, 0, 100])
    out = tmp_path / "g.parquet"
    spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=150.0)
    assert gpd.read_parquet(out)["cluster_id"].tolist() == [1, 2, 2]


def test_clustering_refuses_degrees_and_non_points(tmp_path):
    geographic = _row(tmp_path, [0, 0.001], crs="EPSG:4326", name="geo.gpkg")
    with pytest.raises(ValueError, match="DEGREES"):
        spatial_stats.cluster_points_by_distance(
            str(geographic), str(tmp_path / "x.parquet"), max_distance=500.0
        )
    lines = tmp_path / "lines.gpkg"
    gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 1)])], crs="EPSG:32632"
    ).to_file(lines, layer="l", driver="GPKG")
    with pytest.raises(ValueError, match="point layer"):
        spatial_stats.cluster_points_by_distance(
            str(lines), str(tmp_path / "y.parquet"), max_distance=500.0
        )


def test_clustering_an_empty_layer_writes_a_record_instead_of_crashing(tmp_path):
    """`thin_points` treats an empty layer as a result; this used to raise a
    TypeError from shapely, which cannot infer the dtype of an empty list."""
    path = _row(tmp_path, [])
    out = tmp_path / "g.parquet"
    result = spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    assert (result["points"], result["clusters"], result["largest_cluster"]) == (0, 0, 0)
    assert _named(out)["x-mapsmith:clusters_are_the_chains_of_the_written_points"]["passed"]


def test_clustering_refuses_to_overwrite_an_input_column(tmp_path):
    # The record says `removes_data: false`; replacing a column would falsify it.
    path = tmp_path / "pre.gpkg"
    gpd.GeoDataFrame(
        {"cluster_id": ["A", "B"]}, geometry=[Point(0, 0), Point(10, 0)], crs="EPSG:32632"
    ).to_file(path, layer="p", driver="GPKG")
    out = tmp_path / "g.parquet"
    with pytest.raises(ValueError, match="would overwrite"):
        spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    assert not out.exists()


def test_the_cluster_check_fails_on_a_file_whose_ids_are_wrong(tmp_path):
    """The check re-reads the output: a guard that re-read the pairs the
    union-find had just merged could not fail. This one can, in both directions."""
    path = _row(tmp_path, [0, 400, 5000])
    out = tmp_path / "g.parquet"
    spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    frame = gpd.read_parquet(out)
    split = frame.copy()
    split.loc[1, "cluster_id"] = 3  # two linked points in different clusters
    split.to_parquet(tmp_path / "split.parquet")
    assert not spatial_stats._clusters_match_the_written_points(
        str(tmp_path / "split.parquet"), 500.0
    ).passed
    merged = frame.copy()
    merged["cluster_id"] = 1  # the far point joined a cluster no chain reaches
    merged.to_parquet(tmp_path / "merged.parquet")
    assert not spatial_stats._clusters_match_the_written_points(
        str(tmp_path / "merged.parquet"), 500.0
    ).passed


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0.0, -5.0])
def test_clustering_and_thinning_refuse_a_distance_that_is_not_a_positive_number(tmp_path, bad):
    # NaN compares false with everything, so `NaN <= 0` let it through and every
    # point came back a cluster of one (found by the geo review).
    path = _row(tmp_path, [0, 100])
    with pytest.raises(ValueError, match="positive number"):
        spatial_stats.cluster_points_by_distance(str(path), str(tmp_path / "c.parquet"), bad)
    with pytest.raises(ValueError, match="positive number"):
        spatial_stats.thin_points(str(path), str(tmp_path / "t.parquet"), min_distance=bad)


def test_clustering_refuses_multipart_points_empty_geometries_and_shapefiles(tmp_path):
    from shapely.geometry import MultiPoint

    multi = tmp_path / "multi.gpkg"
    gpd.GeoDataFrame(
        geometry=[MultiPoint([(0, 0), (100000, 0)]), Point(300, 0), Point(100300, 0)],
        crs="EPSG:32632",
    ).to_file(multi, layer="p", driver="GPKG")
    with pytest.raises(ValueError, match="explode_layer"):
        spatial_stats.cluster_points_by_distance(str(multi), str(tmp_path / "m.parquet"), 500.0)

    empty = tmp_path / "empty_geom.parquet"
    gpd.GeoDataFrame(geometry=[Point(0, 0), Point()], crs="EPSG:32632").to_parquet(empty)
    with pytest.raises(ValueError, match="empty"):
        spatial_stats.cluster_points_by_distance(str(empty), str(tmp_path / "e.parquet"), 500.0)

    with pytest.raises(ValueError, match="shapefile"):
        spatial_stats.cluster_points_by_distance(
            str(_row(tmp_path, [0, 1])), str(tmp_path / "out.shp"), 500.0
        )


def test_clustering_says_which_unit_the_distance_was_read_in(tmp_path):
    # EPSG:2263 is in US survey feet: 500 there is about 152 m, and the record,
    # the note and the result have to say so, or a caller thinking in metres
    # never learns that the link was a third of what they meant.
    path = _row(tmp_path, [0, 400], crs="EPSG:2263", name="feet.gpkg")
    out = tmp_path / "g.parquet"
    result = spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    assert "foot" in result["distance_unit"].lower()
    manifest = _manifest(out)
    assert "foot" in manifest["parameters"]["unit"].lower()
    assert any("foot" in note.lower() for note in manifest["notes"])


def test_the_cluster_check_fails_on_wrong_sizes(tmp_path):
    path = _row(tmp_path, [0, 400, 5000])
    out = tmp_path / "g.parquet"
    spatial_stats.cluster_points_by_distance(str(path), str(out), max_distance=500.0)
    frame = gpd.read_parquet(out)
    frame.loc[2, "cluster_size"] = 2
    frame.to_parquet(tmp_path / "sizes.parquet")
    assert not spatial_stats._clusters_match_the_written_points(
        str(tmp_path / "sizes.parquet"), 500.0
    ).passed


def test_hot_spots_with_a_band_joining_too_many_pairs_is_refused(tmp_path, monkeypatch):
    """Distance-band weights go through the same capped pair query as clustering.

    They were a double loop over every pair in Python, quadratic at any band
    (0.8.0 audit). Ten points within one band are 45 pairs; a limit of 10 refuses.
    """
    monkeypatch.setenv("MAPSMITH_MAX_SAMPLES", "10")
    path = tmp_path / "dense.gpkg"
    gpd.GeoDataFrame(
        {"v": [float(i) for i in range(10)]},
        geometry=[Point(i, 0) for i in range(10)],
        crs="EPSG:32632",
    ).to_file(path)
    with pytest.raises(ValueError, match="MAPSMITH_MAX_SAMPLES"):
        spatial_stats.hot_spots(
            str(path), str(tmp_path / "gi.parquet"), value_field="v",
            weights="distance_band", distance_band=1e9,
        )


@pytest.mark.parametrize("band", [float("nan"), float("inf"), 0.0, -1.0])
def test_hot_spots_refuses_a_band_that_is_not_a_finite_positive_number(tmp_path, band):
    path = tmp_path / "p.gpkg"
    gpd.GeoDataFrame({"v": [1.0, 2.0, 3.0]}, geometry=[Point(0, 0), Point(1, 0), Point(2, 0)],
                     crs="EPSG:32632").to_file(path)
    with pytest.raises(ValueError, match="positive, finite distance_band"):
        spatial_stats.hot_spots(
            str(path), str(tmp_path / "gi.parquet"), value_field="v",
            weights="distance_band", distance_band=band,
        )
