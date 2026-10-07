"""The four operations that answer instead of writing, on fixtures with known answers.

Every expected value here is computable by hand and written in the test as the
arithmetic that produces it, not as a number copied from a run. A checkerboard
on a rook lattice has Moran's I of exactly -1; a 3x3 grid of points in a 200 m
box has R of exactly 3. Either the implementation returns those or it is wrong,
which is the only kind of test worth having on a statistic.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
from shapely.geometry import LineString, MultiLineString, Point, Polygon

from mapsmith.engines import summaries


def square(x: float, y: float, size: float = 1.0) -> Polygon:
    return Polygon(
        [(x, y), (x + size, y), (x + size, y + size), (x, y + size), (x, y)]
    )


@pytest.fixture
def parcels(tmp_path):
    """Four parcels with areas 10, 20, 30 and one missing, in two districts.

    Sum 60, mean 20, median 20, range 20, and the sample standard deviation of
    (10, 20, 30) is exactly 10.
    """
    gdf = gpd.GeoDataFrame(
        {
            "area": [10.0, 20.0, 30.0, None],
            "district": ["north", "north", "south", "south"],
        },
        geometry=[square(0, 0), square(2, 0), square(4, 0), square(6, 0)],
        crs="EPSG:32632",
    )
    path = tmp_path / "parcels.parquet"
    gdf.to_parquet(path)
    return str(path)


def test_the_statistics_are_the_arithmetic(parcels):
    answer = summaries.summarize_field(parcels, "area")
    overall = answer["overall"]
    assert overall["count"] == 3
    assert overall["sum"] == 60.0
    assert overall["mean"] == 20.0
    assert overall["median"] == 20.0
    assert overall["min"] == 10.0 and overall["max"] == 30.0
    assert overall["range"] == 20.0
    assert overall["stdev"] == pytest.approx(10.0)


def test_a_missing_value_is_excluded_and_counted(parcels):
    """The difference between a mean and a wrong mean.

    Four features, three values. Every statistic is over the three, and the
    answer has to say so where somebody reading it will see it — a total of 60
    presented as a total over four parcels is a lie nothing raises.
    """
    answer = summaries.summarize_field(parcels, "area")
    assert answer["features"] == 4
    assert answer["features_with_a_value"] == 3
    assert answer["features_with_no_value"] == 1
    assert "3" in answer["note"] and "4" in answer["note"]


def test_grouping_reports_one_row_per_group_in_a_stable_order(parcels):
    answer = summaries.summarize_field(parcels, "area", group_by="district")
    assert [group["district"] for group in answer["groups"]] == ["north", "south"]
    north, south = answer["groups"]
    assert north["sum"] == 30.0 and north["count"] == 2
    # South has one parcel with a value (30) and one without.
    assert south["sum"] == 30.0 and south["count"] == 1


def test_a_text_column_is_refused_rather_than_summed(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"kind": ["road", "path"]},
        geometry=[Point(0, 0), Point(1, 1)],
        crs="EPSG:32632",
    )
    path = tmp_path / "t.parquet"
    gdf.to_parquet(path)
    with pytest.raises(ValueError, match="not numbers"):
        summaries.summarize_field(str(path), "kind")


def test_an_unknown_statistic_names_the_ones_that_exist(parcels):
    with pytest.raises(ValueError, match="average"):
        summaries.summarize_field(parcels, "area", statistics=["average"])


@pytest.fixture
def strip(tmp_path):
    """Four unit squares in a ROW, values +1, -1, +1, -1.

    A row rather than a 2x2 block, and the difference is the whole point of the
    fixture. In a row each square touches only its neighbours in the line:
        pairs 0-1, 1-2, 2-3, so W = 6 ordered pairs
        Σ w·z_i·z_j = 2·[(+1)(-1) + (-1)(+1) + (+1)(-1)] = -6
        Σ z² = 4,  n = 4
        I = (n/W)·(Σwzz/Σz²) = (4/6)·(-6/4) = -1
    Exactly -1: perfect negative autocorrelation, the checkerboard case.
    E[I] = -1/(n-1) = -1/3.
    """
    gdf = gpd.GeoDataFrame(
        {"value": [1.0, -1.0, 1.0, -1.0]},
        geometry=[square(0, 0), square(1, 0), square(2, 0), square(3, 0)],
        crs="EPSG:32632",
    )
    path = tmp_path / "strip.parquet"
    gdf.to_parquet(path)
    return str(path)


def test_a_perfect_checkerboard_has_a_morans_i_of_exactly_minus_one(strip):
    answer = summaries.spatial_autocorrelation(strip, "value")
    assert answer["morans_i"] == pytest.approx(-1.0)
    assert answer["expected_i"] == pytest.approx(-1 / 3)
    assert answer["neighbour_pairs"] == 6
    assert answer["isolated_features"] == 0
    assert "dispersed" in answer["verdict"] or "no pattern" in answer["verdict"]


def test_contiguity_here_is_queen_and_the_number_shows_it(tmp_path):
    """Corner contact counts as neighbourhood, and it changes the answer.

    Four squares in a 2x2 block with values +1/-1 on the diagonal. Under ROOK
    contiguity (shared edges only) every cell would have two opposite
    neighbours and I would be -1. Under QUEEN (edges and corners) all four are
    mutually adjacent, the two same-sign diagonal pairs enter the sum, and:
        W = 12 ordered pairs,  Σ w·z_i·z_j = 2·(-1-1+1+1-1-1) = -4
        I = (4/12)·(-4/4) = -1/3
    This project's weights use `intersects`, which is queen, and it is a
    deliberate choice made in `spatial_stats` because real administrative
    boundaries overlap by millimetres and `touches` returns false for those.
    The test exists so that changing it cannot be silent: the same map would
    answer -1 instead of -1/3, and nothing else would look different.
    """
    gdf = gpd.GeoDataFrame(
        {"value": [1.0, -1.0, -1.0, 1.0]},
        geometry=[square(0, 0), square(1, 0), square(0, 1), square(1, 1)],
        crs="EPSG:32632",
    )
    path = tmp_path / "block.parquet"
    gdf.to_parquet(path)
    answer = summaries.spatial_autocorrelation(str(path), "value")
    assert answer["neighbour_pairs"] == 12, "corner contact is no longer a neighbour"
    assert answer["morans_i"] == pytest.approx(-1 / 3)


def test_identical_values_are_refused_rather_than_reported_as_zero(tmp_path):
    """Moran's I is undefined without variation, and zero is a different claim.

    Zero means "no spatial pattern", which is a finding. Undefined means the
    question cannot be asked of this data. Returning the first for the second
    is the silent error this project is about.
    """
    gdf = gpd.GeoDataFrame(
        {"value": [5.0, 5.0, 5.0, 5.0]},
        geometry=[square(0, 0), square(1, 0), square(0, 1), square(1, 1)],
        crs="EPSG:32632",
    )
    path = tmp_path / "flat.parquet"
    gdf.to_parquet(path)
    with pytest.raises(ValueError, match="undefined"):
        summaries.spatial_autocorrelation(str(path), "value")


def test_a_neighbourhood_that_found_almost_nothing_is_refused(tmp_path):
    """Four squares far apart: contiguity finds no neighbours at all.

    Answering would report a number computed over nothing. `hot_spots` treats
    this as a critical check on its output; here there is no output to attach a
    check to, so it is an error.
    """
    gdf = gpd.GeoDataFrame(
        {"value": [1.0, 2.0, 3.0, 4.0]},
        geometry=[square(0, 0), square(100, 0), square(0, 100), square(100, 100)],
        crs="EPSG:32632",
    )
    path = tmp_path / "far.parquet"
    gdf.to_parquet(path)
    with pytest.raises(ValueError, match="no neighbours"):
        summaries.spatial_autocorrelation(str(path), "value")


@pytest.fixture
def lattice(tmp_path):
    """A 3x3 grid of points 100 m apart, inside a 200 m x 200 m boundary.

    Every point has a nearest neighbour at exactly 100 m, so the observed mean
    is 100. With the boundary as the study area:
        density = 9 / 40000, expected = 0.5/sqrt(density) = 0.5·200/3 = 33.333…
        R = 100 / 33.333… = 3 exactly
    """
    points = [Point(x * 100, y * 100) for y in range(3) for x in range(3)]
    gdf = gpd.GeoDataFrame({"id": range(9)}, geometry=points, crs="EPSG:32632")
    path = tmp_path / "grid.parquet"
    gdf.to_parquet(path)

    area = gpd.GeoDataFrame(
        {"id": [1]}, geometry=[square(0, 0, 200)], crs="EPSG:32632"
    )
    area_path = tmp_path / "area.parquet"
    area.to_parquet(area_path)
    return str(path), str(area_path)


def test_a_regular_grid_in_a_known_box_gives_r_of_exactly_three(lattice):
    points, area = lattice
    answer = summaries.nearest_neighbour_index(points, area_path=area)
    assert answer["observed_mean_distance"] == pytest.approx(100.0)
    assert answer["expected_mean_distance"] == pytest.approx(200 / 6, abs=1e-3)
    assert answer["r"] == pytest.approx(3.0, abs=1e-4)
    assert answer["study_area"] == pytest.approx(40000.0)
    assert answer["verdict"] == "evenly spread"


def test_the_study_area_changes_the_answer_and_the_answer_says_which_was_used(lattice):
    """The property the docstring is built around, asserted.

    The same nine points give a different R against their own hull (200x200 is
    the hull here, so this pair happens to agree) — what must never differ is
    that the answer names the area it used. A run whose R cannot be traced to an
    area is not reproducible by anybody.
    """
    points, area = lattice
    with_boundary = summaries.nearest_neighbour_index(points, area_path=area)
    with_hull = summaries.nearest_neighbour_index(points)
    assert area in with_boundary["study_area_from"]
    assert "convex hull" in with_hull["study_area_from"]
    assert with_boundary["study_area"] == pytest.approx(with_hull["study_area"])


def test_a_geographic_crs_is_refused_because_degrees_are_not_a_length(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"id": [1, 2, 3]},
        geometry=[Point(9.0, 45.0), Point(9.1, 45.0), Point(9.0, 45.1)],
        crs="EPSG:4326",
    )
    path = tmp_path / "deg.parquet"
    gdf.to_parquet(path)
    with pytest.raises(ValueError, match="geographic CRS"):
        summaries.nearest_neighbour_index(str(path))


def test_coincident_points_are_counted_because_they_drag_r_down(tmp_path):
    points = [Point(0, 0), Point(0, 0), Point(100, 0), Point(0, 100)]
    gdf = gpd.GeoDataFrame({"id": range(4)}, geometry=points, crs="EPSG:32632")
    path = tmp_path / "dup.parquet"
    gdf.to_parquet(path)
    answer = summaries.nearest_neighbour_index(str(path))
    assert answer["coincident_points"] == 2
    assert "duplicated" in answer["note"].lower()


@pytest.fixture
def two_versions(tmp_path):
    first = gpd.GeoDataFrame(
        {"id": ["a", "b", "c"], "owner": ["x", "y", "z"]},
        geometry=[square(0, 0), square(2, 0), square(4, 0)],
        crs="EPSG:32632",
    )
    second = gpd.GeoDataFrame(
        # 'a' unchanged, 'b' moved, 'c' removed, 'd' added, and 'b' also edited
        {"id": ["a", "b", "d"], "owner": ["x", "changed", "w"]},
        geometry=[square(0, 0), square(2.5, 0), square(6, 0)],
        crs="EPSG:32632",
    )
    a, b = tmp_path / "a.parquet", tmp_path / "b.parquet"
    first.to_parquet(a)
    second.to_parquet(b)
    return str(a), str(b)


def test_the_diff_counts_what_a_person_would_count(two_versions):
    a, b = two_versions
    answer = summaries.compare_layers(a, b, key_field="id")
    assert answer["added"] == 1 and answer["added_keys"] == ["d"]
    assert answer["removed"] == 1 and answer["removed_keys"] == ["c"]
    assert answer["matched"] == 2
    assert answer["geometry_changed"] == 1 and answer["geometry_changed_keys"] == ["b"]
    assert answer["attributes_changed"] == 1
    assert answer["largest_move"] == pytest.approx(0.0, abs=1e-9) or (
        answer["largest_move"] > 0
    )
    assert answer["identical"] is False


def test_without_a_key_it_refuses_to_guess_which_feature_became_which(two_versions):
    a, b = two_versions
    answer = summaries.compare_layers(a, b)
    assert answer["compared_by"] == "counts, columns and extent only"
    assert "key_field" in answer["note"]
    assert "added" not in answer


def test_a_repeated_key_is_refused_rather_than_paired_arbitrarily(tmp_path):
    gdf = gpd.GeoDataFrame(
        {"id": ["a", "a"]},
        geometry=[square(0, 0), square(2, 0)],
        crs="EPSG:32632",
    )
    path = tmp_path / "dupkey.parquet"
    gdf.to_parquet(path)
    with pytest.raises(ValueError, match="repeated"):
        summaries.compare_layers(str(path), str(path), key_field="id")


def test_two_copies_of_the_same_layer_are_identical(two_versions):
    a, _ = two_versions
    answer = summaries.compare_layers(a, a, key_field="id")
    assert answer["identical"] is True
    assert answer["geometry_changed"] == 0 and answer["attributes_changed"] == 0


def test_a_layer_with_a_null_attribute_is_identical_to_a_copy_of_itself(tmp_path):
    """`NaN != NaN` made the diff report a file as changed against itself.

    The operation's whole question is "is this different from what we had", and
    every row holding a null in a compared column came back edited. Two rows
    that both record nothing about a column agree about it — IEEE 754 is right
    about floats and wrong about this question.
    """
    gdf = gpd.GeoDataFrame(
        {"id": ["a", "b"], "owner": ["Rossi", None]},
        geometry=[square(0, 0), square(2, 0)],
        crs="EPSG:32632",
    )
    path = tmp_path / "with_a_null.parquet"
    gdf.to_parquet(path)

    answer = summaries.compare_layers(str(path), str(path), key_field="id")
    assert answer["attributes_changed"] == 0, answer["attributes_changed_keys"]
    assert answer["identical"] is True


def test_a_larger_tolerance_can_only_find_fewer_changes(tmp_path):
    """The tolerance was inverted: loosening it made the comparison stricter.

    `tolerance` is a distance the caller is willing to ignore, so raising it
    cannot turn an unchanged feature into a changed one. The first version
        switched from `equals` to `equals_exact` as soon as a tolerance was
    given, so these two squares — the same shape, one carrying an extra
    collinear vertex — came back unchanged at 0 and changed at 5.
    """
    plain = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    with_extra_vertex = Polygon([(0, 0), (5, 0), (10, 0), (10, 10), (0, 10)])
    left = tmp_path / "plain.parquet"
    right = tmp_path / "extra.parquet"
    gpd.GeoDataFrame({"id": ["a"]}, geometry=[plain], crs="EPSG:32632").to_parquet(left)
    gpd.GeoDataFrame({"id": ["a"]}, geometry=[with_extra_vertex], crs="EPSG:32632").to_parquet(right)

    changed = {
        tolerance: summaries.compare_layers(
            str(left), str(right), key_field="id", tolerance=tolerance
        )["geometry_changed"]
        for tolerance in (0.0, 5.0)
    }
    assert changed[5.0] <= changed[0.0], (
        f"a tolerance of 5 found {changed[5.0]} changes where 0 found "
        f"{changed[0.0]}: the tolerance is inverted"
    )


def test_a_null_geometry_is_compared_rather_than_crashed_on(tmp_path):
    """Null geometries are ordinary in GeoPackage and GeoParquet, and the guard
    protected only the distance call before asking a None for `.equals` — a raw
    AttributeError where every other operation here answers with a sentence."""
    gdf = gpd.GeoDataFrame(
        {"id": ["a", "b"]},
        geometry=[square(0, 0), None],
        crs="EPSG:32632",
    )
    path = tmp_path / "with_a_null_geometry.parquet"
    gdf.to_parquet(path)

    answer = summaries.compare_layers(str(path), str(path), key_field="id")
    assert answer["identical"] is True
    assert answer["geometry_changed"] == 0


def test_a_geometry_that_appears_only_on_one_side_counts_as_changed(tmp_path):
    """The counterpart of the test above: treating two nulls as equal must not
    make a null and a real geometry equal as well."""
    present = gpd.GeoDataFrame(
        {"id": ["a"]}, geometry=[square(0, 0)], crs="EPSG:32632"
    )
    absent = gpd.GeoDataFrame({"id": ["a"]}, geometry=[None], crs="EPSG:32632")
    left = tmp_path / "present.parquet"
    right = tmp_path / "absent.parquet"
    present.to_parquet(left)
    absent.to_parquet(right)

    answer = summaries.compare_layers(str(left), str(right), key_field="id")
    assert answer["geometry_changed"] == 1
    assert answer["identical"] is False


def test_a_stretch_missing_from_the_middle_is_a_change(tmp_path):
    """The regression the Hausdorff fix introduced, and the reason for the gate.

    GEOS's `hausdorff_distance` is the DISCRETE one: vertices of each geometry
    against the other. A line and the same line with a stretch missing in the
    middle share every vertex, so the distance is 0.0 — and gating the
    comparison on it unconditionally made zero tolerance weaker than "exact
    geometric equality", which is what the docstring promises. A road that lost
    two metres came back identical.

    Zero tolerance now means `equals` and nothing else.
    """
    whole = LineString([(0, 0), (10, 0)])
    with_a_gap = MultiLineString([[(0, 0), (4, 0)], [(6, 0), (10, 0)]])
    assert whole.hausdorff_distance(with_a_gap) == 0.0, (
        "if GEOS ever makes this the continuous Hausdorff distance, the reason "
        "for the gate below has changed and this test should say so"
    )

    before = tmp_path / "before.parquet"
    after = tmp_path / "after.parquet"
    gpd.GeoDataFrame({"id": ["r1"]}, geometry=[whole], crs="EPSG:32632").to_parquet(before)
    gpd.GeoDataFrame({"id": ["r1"]}, geometry=[with_a_gap], crs="EPSG:32632").to_parquet(after)

    answer = summaries.compare_layers(str(before), str(after), key_field="id")
    assert answer["geometry_changed"] == 1
    assert answer["identical"] is False


def test_the_reported_move_is_the_boundary_deviation_and_has_a_known_value(
    two_versions,
):
    """`largest_move` had one test and it could not fail.

    It asserted `x == approx(0.0) or x > 0`, which is a tautology for any
    non-negative float — so the correction that changed what this number MEANS
    shipped with no coverage of its observable effect. The fixture moves
    `square(2, 0)` to `square(2.5, 0)`, whose boundary deviation is exactly 0.5.
    """
    a, b = two_versions
    answer = summaries.compare_layers(a, b, key_field="id")
    assert answer["largest_move"] == pytest.approx(0.5), (
        "the fixture's only moved feature is displaced by exactly 0.5, so this "
        "number is checkable rather than merely non-negative"
    )


def test_a_list_valued_attribute_does_not_crash_the_comparison(tmp_path):
    """`pd.isna` on a list returns an array, and `if a or b` on an array raises.

    List columns are ordinary in GeoParquet, and the plain `!=` this replaced
    handled them. Introduced by the null-handling fix and caught by review.
    """
    frame = gpd.GeoDataFrame(
        {"id": ["a", "b"], "codes": [[1, 2], [3]]},
        geometry=[square(0, 0), square(2, 0)],
        crs="EPSG:32632",
    )
    path = tmp_path / "lists.parquet"
    frame.to_parquet(path)

    answer = summaries.compare_layers(str(path), str(path), key_field="id")
    assert answer["identical"] is True
    assert answer["attributes_changed"] == 0
