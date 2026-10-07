"""A bounding box that spans the planet for data two degrees wide.

The Fijian survey zone in Argleton's trap 025 has a bounding box of
`(-180, -17.5, 180, -16.5)`, and every number in it is arithmetically correct.
It is also the wrong answer to the question anybody asked. These tests pin both
halves: the plain box still comes out unchanged, and the sentence that makes it
readable comes out with it.

The cases that matter are the ones where the arithmetic alone gets it wrong —
a rectangle covering the world has the same wrapped span as a zone split at the
seam — so most of what follows is about *not* claiming a crossing.
"""

from __future__ import annotations

import geopandas as gpd
import pytest
import shapely

from mapsmith import antimeridian

# Two degrees of longitude either side of the seam: the survey zone the trap is
# built from, split at the antimeridian as RFC 7946 3.1.9 prescribes.
FIJI_WEST = shapely.box(179.0, -17.5, 180.0, -16.5)
FIJI_EAST = shapely.box(-180.0, -17.5, -179.0, -16.5)


def _layer(*geometries, crs="EPSG:4326"):
    return gpd.GeoDataFrame(geometry=list(geometries), crs=crs)


def test_the_plain_box_is_always_reported_unchanged():
    """Whatever else is said, the coordinates' own answer stays available.

    Something downstream may be relying on `minx/maxx`, and quietly replacing
    them with the wrapped form would be a second silent error rather than a fix
    for the first.
    """
    extent = antimeridian.describe_extent(_layer(FIJI_WEST, FIJI_EAST))
    assert extent["minx"] == -180.0
    assert extent["maxx"] == 180.0
    assert extent["miny"] == -17.5
    assert extent["maxy"] == -16.5


def test_a_zone_split_at_the_seam_is_named_as_crossing():
    extent = antimeridian.describe_extent(_layer(FIJI_WEST, FIJI_EAST))
    assert extent["crosses_antimeridian"] is True
    # 179 -> -179 the short way round is two degrees, not 358.
    assert extent["true_extent"]["width_degrees"] == pytest.approx(2.0)


def test_the_true_extent_is_in_the_form_rfc_7946_defines():
    """RFC 7946 5.2: for a crossing box the western value is the GREATER one.

    This is the whole reason the module exists — 3.1.9 splits the geometry so
    that no planar library can ever compute this form, and 5.2 defines it as the
    signal. Nothing bridges the two automatically.
    """
    true_extent = antimeridian.describe_extent(_layer(FIJI_WEST, FIJI_EAST))["true_extent"]
    assert true_extent["minx"] == pytest.approx(179.0)
    assert true_extent["maxx"] == pytest.approx(-179.0)
    assert true_extent["minx"] > true_extent["maxx"]
    # Latitude is not involved: it has no seam.
    assert true_extent["miny"] == -17.5
    assert true_extent["maxy"] == -16.5


def test_the_note_says_what_filtering_by_the_plain_box_would_select():
    note = antimeridian.describe_extent(_layer(FIJI_WEST, FIJI_EAST))["note"]
    assert "360" in note
    assert "RFC 7946" in note
    # The consequence, not just the diagnosis: the failure is a query returning
    # the whole latitude band, and a reader who is told only "this crosses the
    # antimeridian" has to work that out for themselves.
    assert "anywhere on Earth" in note


def test_one_rectangle_covering_the_world_is_not_a_crossing():
    """The case that makes this more than four lines of arithmetic.

    A global rectangle has exactly two longitudes in it, -180 and 180, and they
    wrap onto the same value. Its wrapped span is therefore 0, which is smaller
    than any real crossing's — by coordinates alone it is the *most* convincing
    crossing there is. Only the geometry can tell the two apart.
    """
    extent = antimeridian.describe_extent(_layer(shapely.box(-180.0, -60.0, 180.0, 60.0)))
    assert "crosses_antimeridian" not in extent
    assert extent["minx"] == -180.0
    assert extent["maxx"] == 180.0


def test_two_hemispheres_that_meet_at_greenwich_are_not_a_crossing():
    """Genuinely global data assembled from two halves.

    The pieces reach the seam from both sides, exactly like the Fiji zone, and
    the difference is only in which gap is empty.
    """
    world = _layer(
        shapely.box(-180.0, -60.0, 0.0, 60.0),
        shapely.box(0.0, -60.0, 180.0, 60.0),
    )
    assert "crosses_antimeridian" not in antimeridian.describe_extent(world)


def test_data_straddling_greenwich_says_nothing():
    """The other meridian is not a seam, and the wrapped span is the larger one."""
    straddling = _layer(shapely.box(-5.0, 40.0, 5.0, 50.0))
    extent = antimeridian.describe_extent(straddling)
    assert "crosses_antimeridian" not in extent
    assert extent["minx"] == -5.0


def test_ordinary_regional_data_says_nothing():
    extent = antimeridian.describe_extent(_layer(shapely.box(6.0, 36.0, 19.0, 47.0)))
    assert set(extent) == {"minx", "miny", "maxx", "maxy"}


def test_points_either_side_of_the_seam_are_named():
    """Points have no interior, so the probe cannot intersect them.

    Worth its own test: a layer of Aleutian stations is the realistic form of
    this problem, and a geometry probe that only works on polygons would pass
    every other test here.
    """
    aleutians = _layer(
        shapely.Point(179.6, 51.9),
        shapely.Point(-179.4, 51.8),
        shapely.Point(179.9, 52.0),
    )
    extent = antimeridian.describe_extent(aleutians)
    assert extent["crosses_antimeridian"] is True
    assert extent["true_extent"]["width_degrees"] == pytest.approx(1.0)


def test_a_projected_crs_is_never_asked_the_question():
    """A projected CRS has no antimeridian inside it.

    Its eastings can span 360 units for reasons that have nothing to do with
    longitude, and a note about the 180th meridian on a UTM layer would be a
    false alarm dressed as expertise.
    """
    utm = _layer(shapely.box(500_000.0, 4_500_000.0, 500_360.0, 4_500_100.0), crs="EPSG:32632")
    assert "crosses_antimeridian" not in antimeridian.describe_extent(utm)


def test_a_layer_without_a_crs_is_not_second_guessed():
    """Without a CRS, numbers near 180 are just numbers."""
    unknown = _layer(FIJI_WEST, FIJI_EAST, crs=None)
    assert "crosses_antimeridian" not in antimeridian.describe_extent(unknown)


def test_an_empty_layer_does_not_raise():
    assert "crosses_antimeridian" not in antimeridian.describe_extent(_layer(crs="EPSG:4326"))


def test_a_single_unsplit_geometry_is_reported_plainly():
    """RFC 7946 says this should not exist; it exists.

    A ring whose longitudes run 179 to 181 — coordinates outside [-180, 180],
    which plenty of producers emit — already has narrow bounds, and nothing
    about them misleads. So it is reported plainly and that is the right answer.

    This test was called `..._is_caught` while asserting the opposite, and it
    passed through the old span threshold without the module doing anything —
    it would have passed against `return plain_extent`. Renamed to what it
    checks, and paired with the case below, which is the one that does work.
    """
    unsplit = _layer(shapely.box(179.0, -17.5, 181.0, -16.5))
    extent = antimeridian.describe_extent(unsplit)
    assert "crosses_antimeridian" not in extent
    assert extent["maxx"] == 181.0


def test_data_that_crosses_without_touching_the_seam_is_named():
    """The case the old threshold could not see, and the common one.

    Pacific buoys at 170°E and 140°W span 310° of longitude — under the 350°
    the module used to require before looking — so they were reported as a band
    round the planet, in silence. Nothing about that data is malformed: it is
    simply not split exactly at ±180, which most real data is not. AIS tracks,
    Aleutian stations and WCPFC fishing areas all have this shape.
    """
    buoys = _layer(shapely.Point(170.0, 0.0), shapely.Point(-140.0, 0.0))
    extent = antimeridian.describe_extent(buoys)
    assert extent["crosses_antimeridian"] is True
    assert extent["true_extent"]["width_degrees"] == pytest.approx(50.0)
    assert extent["true_extent"]["minx"] == pytest.approx(170.0)
    assert extent["true_extent"]["maxx"] == pytest.approx(-140.0)


def test_data_spread_over_more_than_half_the_world_is_not_a_crossing():
    """Points at -179, -90, 0, 90 and 179 do wrap to a narrower span — 270°
    against 358° — and calling that a crossing would be noise.

    This is what the 180° rule is for, and why it is not an arbitrary constant:
    below it the data occupies less than half the world going the short way, so
    one reading is genuinely the narrow one. At 270° neither is.
    """
    scattered = _layer(*[shapely.Point(x, 0.0) for x in (-179, -90, 0, 90, 179)])
    assert "crosses_antimeridian" not in antimeridian.describe_extent(scattered)


def test_a_geographic_crs_measured_in_grads_is_left_alone():
    """`is_geographic` is not enough: EPSG:4807 is geographic in **grads**.

    Wrapping those at 360 and talking about the 180th meridian would both be
    wrong, and it is the class of mistake `measure_area` exists to avoid —
    read the unit from the CRS instead of assuming it.
    """
    grads = _layer(
        shapely.box(179.0, -17.5, 180.0, -16.5),
        shapely.box(-180.0, -17.5, -179.0, -16.5),
        crs="EPSG:4807",
    )
    assert "crosses_antimeridian" not in antimeridian.describe_extent(grads)


def test_a_null_geometry_does_not_poison_the_bounds():
    """NaN bounds propagate through min and max without a word."""
    with_null = gpd.GeoDataFrame(
        geometry=[FIJI_WEST, None, FIJI_EAST], crs="EPSG:4326"
    )
    extent = antimeridian.describe_extent(with_null)
    assert extent["crosses_antimeridian"] is True
    assert extent["true_extent"]["width_degrees"] == pytest.approx(2.0)


def test_describe_dataset_carries_the_finding(tmp_path):
    """End to end: the sentence has to reach whoever called describe_dataset.

    The module could be perfect and the defect would survive untouched if the
    describe path still returned the bare box.
    """
    from mapsmith.engines import dispatch

    path = tmp_path / "zone.parquet"
    _layer(FIJI_WEST, FIJI_EAST).to_parquet(path)

    extent = dispatch.describe_routed(str(path))["extent"]
    assert extent["crosses_antimeridian"] is True
    assert extent["true_extent"]["minx"] > extent["true_extent"]["maxx"]


def test_only_one_place_decides_what_a_crossing_extent_means():
    """The discipline that came out of issue #28, applied before it can break.

    The reason describe_dataset was wrong is not that the question is hard, it
    is that nobody owned it. A second copy of this rule somewhere else would be
    the same bug with a longer fuse, so the constant that encodes the judgement
    is allowed to appear in exactly one module.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "mapsmith"
    guilty = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*.py")
        if path.name != "antimeridian.py"
        and "HALF_THE_WORLD" in path.read_text(encoding="utf-8")
    ]
    assert not guilty, f"the antimeridian rule has a second copy in {guilty}"


def test_a_three_dimensional_geographic_crs_is_still_geographic(tmp_path):
    """EPSG:4979 switched the whole module off, silently.

    WGS 84 3D is what a great deal of GNSS and LiDAR data declares, and its
    third axis is ellipsoidal height in metres. The unit check asked *every*
    axis for degrees, so `_is_in_degrees` was False, detection never ran, and a
    Fijian survey zone came back with the plain world-spanning box and no note —
    the exact false negative this module exists to prevent, leaving no trace
    that a question had been skipped.

    Only the horizontal axes decide how longitude is measured.
    """
    for crs in ("EPSG:4326", "EPSG:4979"):
        gdf = gpd.GeoDataFrame(
            {"id": [1, 2]}, geometry=[FIJI_WEST, FIJI_EAST], crs=crs
        )
        described = antimeridian.describe_extent(gdf)
        assert described["crosses_antimeridian"] is True, (
            f"the crossing was not detected in {crs}"
        )
        assert described["true_extent"]["width_degrees"] == pytest.approx(2.0)


def test_a_crs_in_grads_is_still_refused_and_a_geocentric_one_too():
    """The counterpart: relaxing the axis check must not let non-degree CRSs in.

    EPSG:4807 is geographic in grads, where 180 is not the antimeridian at all,
    and EPSG:4936 is geocentric — three metre axes and no longitude to wrap.
    """
    from pyproj import CRS

    from mapsmith.antimeridian import _is_in_degrees

    assert _is_in_degrees(CRS.from_user_input("EPSG:4326")) is True
    assert _is_in_degrees(CRS.from_user_input("EPSG:4979")) is True
    assert _is_in_degrees(CRS.from_user_input("EPSG:4807")) is False
    assert _is_in_degrees(CRS.from_user_input("EPSG:4936")) is False
    assert _is_in_degrees(CRS.from_user_input("EPSG:32632")) is False


def test_an_ordinary_layer_is_not_announced_as_crossing_the_seam():
    """A tenth of a kilometre of river in Washington is not a wrapped dataset.

    The rule used to be "does reading across the seam give a narrower span",
    and on data that does not wrap those two spans are the same number computed
    twice -- once directly, once through a round trip via +-360. Measured on
    2026-09-14 against the demo fixture: plain 0.0010000000000047748, wrapped
    0.0009999999999763531. The wrapped reading won by 2.8e-14 degrees, about
    three nanometres on the ground, and the layer was published with
    `crosses_antimeridian: true`, a `true_extent` identical to the ordinary one,
    and a note telling the reader not to trust its bounding box.

    Which way that subtraction falls is not a property of the data, so the
    defect is not an edge case: any ordinary layer could draw it. The rule is
    now that the PLAIN extent has to be absurd first -- a wrapped dataset looks
    like it spans nearly the whole world, and this one spans a thousandth of a
    degree.
    """
    import geopandas as gpd
    from shapely.geometry import LineString

    river = gpd.GeoDataFrame(
        geometry=[LineString([(-122.1905, 46.197), (-122.1895, 46.206)])],
        crs="EPSG:4326",
    )
    extent = antimeridian.describe_extent(river)
    assert "crosses_antimeridian" not in extent, (
        "a 0.001-degree line in Washington is announced as crossing the antimeridian: "
        f"{extent}"
    )
    assert "note" not in extent
    # And the fix must not have bought that by blinding the detector: a layer
    # split at the seam the way RFC 7946 asks still has to be recognised.
    from shapely.geometry import box

    wrapped = gpd.GeoDataFrame(
        geometry=[box(179.0, -1.0, 180.0, 1.0), box(-180.0, -1.0, -179.0, 1.0)],
        crs="EPSG:4326",
    )
    crossing = antimeridian.describe_extent(wrapped)
    assert crossing.get("crosses_antimeridian") is True
    assert crossing["true_extent"]["width_degrees"] == pytest.approx(2.0)
