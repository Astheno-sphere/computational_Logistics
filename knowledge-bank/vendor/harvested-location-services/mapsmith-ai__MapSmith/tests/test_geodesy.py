"""describe_crs and geodetic_distance against numbers that are not opinions.

The expectations here are definitions, not measurements: a degree of longitude
on the equator is the semi-major axis times pi/180 by construction, and the US
survey foot is 1200/3937 metres by statute. If one of these ever fails, PROJ
has changed under us and every length in the project is worth re-checking.
"""

import math

import pytest

from mapsmith.engines import geodesy

# ---------------------------------------------------------- describe_crs


@pytest.mark.parametrize(
    ("crs", "kind", "axis_order", "unit"),
    [
        ("EPSG:4326", "geographic", "lat,lon", "degree"),
        (4326, "geographic", "lat,lon", "degree"),  # the bare code, too
        ("EPSG:32632", "projected", "lon,lat", "metre"),
        ("EPSG:2263", "projected", "lon,lat", "US survey foot"),
        ("EPSG:3857", "projected", "lon,lat", "metre"),
        ("EPSG:4806", "geographic", "lat,lon", "degree"),
    ],
)
def test_describe_crs_reports_kind_axis_order_and_unit(crs, kind, axis_order, unit):
    described = geodesy.describe_crs(crs)
    assert described["kind"] == kind
    assert described["axis_order"] == axis_order
    assert described["unit"] == unit


def test_the_us_survey_foot_is_not_the_international_foot():
    """1200/3937 exactly, and the difference is 2 cm per kilometre.

    This is the number behind the trap `measure_area` was written for: a length
    in EPSG:2263 read as if it were in international feet is wrong by a factor
    that no validity check catches.
    """
    factor = geodesy.describe_crs("EPSG:2263")["unit_to_metre"]
    assert factor == pytest.approx(1200.0 / 3937.0, abs=1e-15)
    assert factor != 0.3048
    per_kilometre = (factor / 0.3048 - 1.0) * 1000.0
    assert per_kilometre == pytest.approx(0.002, abs=1e-4)


def test_describe_crs_reads_a_non_greenwich_prime_meridian():
    """EPSG:4806 measures longitude from Rome, which is the whole reason a
    coordinate can be plausible and 12 degrees out."""
    described = geodesy.describe_crs("EPSG:4806")
    assert described["prime_meridian"] == "Rome"
    assert described["ellipsoid"]["name"] == "International 1924"
    assert described["ellipsoid"]["semi_major_metre"] == pytest.approx(6378388.0)
    assert described["ellipsoid"]["inverse_flattening"] == pytest.approx(297.0)


def test_describe_crs_reports_the_area_of_use_and_the_projection_method():
    described = geodesy.describe_crs("EPSG:3857")
    assert described["projection_method"] == "Popular Visualisation Pseudo Mercator"
    _, south, _, north = described["area_of_use"]["bounds"]
    # Web Mercator stops short of the poles by construction, and a point outside
    # that band still gets coordinates.
    assert north == pytest.approx(85.06, abs=0.01)
    assert south == pytest.approx(-85.06, abs=0.01)


def test_describe_crs_refuses_something_that_is_not_a_crs():
    with pytest.raises(ValueError, match="not a CRS pyproj can read"):
        geodesy.describe_crs("EPSG:999999")


def test_describe_crs_accepts_a_proj_string_and_wkt():
    from_proj = geodesy.describe_crs("+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs")
    assert from_proj["kind"] == "projected"
    assert from_proj["unit"] == "metre"
    wkt = geodesy.describe_crs("EPSG:32632")
    assert from_proj["projection_method"] == wkt["projection_method"]


# ------------------------------------------------------ geodetic_distance


def test_a_degree_of_longitude_on_the_equator_is_the_semi_major_arc():
    """a * pi/180, by the definition of the ellipsoid. Not an approximation."""
    result = geodesy.geodetic_distance(0, 0, 1, 0)
    assert result["distance_metres"] == pytest.approx(6378137.0 * math.pi / 180, abs=1e-6)
    assert result["forward_azimuth_degrees"] == pytest.approx(90.0)


def test_equator_to_pole_is_the_wgs84_quarter_meridian():
    result = geodesy.geodetic_distance(0, 0, 0, 90)
    assert result["distance_metres"] == pytest.approx(10001965.729312724, abs=1e-6)
    assert result["forward_azimuth_degrees"] == pytest.approx(0.0)


def test_the_same_point_is_zero_and_not_an_epsilon():
    result = geodesy.geodetic_distance(12.4964, 41.9028, 12.4964, 41.9028)
    assert result["distance_metres"] == 0.0


def test_a_degree_of_longitude_shrinks_with_latitude():
    """The fact that makes a planar distance in a geographic CRS meaningless:
    the same one-degree step is 111 km at the equator and 83 km in Rome."""
    equator = geodesy.geodetic_distance(12.0, 0.0, 13.0, 0.0)["distance_metres"]
    rome = geodesy.geodetic_distance(12.0, 41.86, 13.0, 41.86)["distance_metres"]
    assert rome < equator
    assert rome / equator == pytest.approx(math.cos(math.radians(41.86)), abs=0.002)


def test_the_ellipsoid_changes_the_answer_which_is_why_it_is_a_fixed_list():
    """New York to Paris differs by 269 m between WGS84 and International 1924.
    A free-text field that silently fell back to WGS84 would move a legacy
    number by that much with nothing to show for it."""
    wgs84 = geodesy.geodetic_distance(-74.0, 40.7, 2.35, 48.85)["distance_metres"]
    intl = geodesy.geodetic_distance(-74.0, 40.7, 2.35, 48.85, ellipsoid="intl")[
        "distance_metres"
    ]
    assert wgs84 != intl
    assert abs(wgs84 - intl) == pytest.approx(269.1, abs=0.5)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"from_lon": 0, "from_lat": 100, "to_lon": 0, "to_lat": 0}, "not a latitude"),
        ({"from_lon": 0, "from_lat": 0, "to_lon": 0, "to_lat": -91}, "not a latitude"),
        ({"from_lon": 200, "from_lat": 0, "to_lon": 0, "to_lat": 0}, r"outside \[-180"),
        (
            {"from_lon": 0, "from_lat": 0, "to_lon": 1, "to_lat": 0, "ellipsoid": "wgs84"},
            "ellipsoid must be one of",
        ),
    ],
)
def test_geodetic_distance_refuses_what_is_not_a_coordinate(kwargs, message):
    with pytest.raises(ValueError, match=message):
        geodesy.geodetic_distance(**kwargs)


def test_the_result_carries_the_ellipsoid_it_used():
    """A distance without its ellipsoid is not reproducible, and the two are
    hundreds of metres apart over an ocean."""
    result = geodesy.geodetic_distance(0, 0, 1, 0, ellipsoid="clrk66")
    assert result["ellipsoid"] == "clrk66"
    assert result["semi_major_metre"] == pytest.approx(6378206.4)
    assert "no projection involved" in result["method"]
