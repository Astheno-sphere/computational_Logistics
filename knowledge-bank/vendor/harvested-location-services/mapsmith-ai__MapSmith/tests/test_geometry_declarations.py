"""Every geometry declaration in the catalogue matches what the operation does.

`applicability.geometry` hides an operation from a caller holding another
family, so a declaration narrower than the code is the dangerous direction: the
operation vanishes, silently, for exactly the caller it could have served. The
behaviour tested here is therefore the refusal. For every argument that takes
only some families, each family it does not take must be refused with a message
about geometry; and the families the rows below accept, per operation, must be
the declared ones -- so a declaration added without a row here fails, and so
does a row that drifted from the catalogue.
"""

from __future__ import annotations

import re

import geopandas as gpd
import pytest
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from mapsmith import catalog

CRS = "EPSG:32632"
FAMILIES = ("point", "line", "polygon")
GEOMETRY_WORDS = re.compile(
    r"\b(points?|lines?|polygons?|geometr\w*|linestring|multipoint|areas?|areal)\b",
    re.IGNORECASE,
)


#: Each family in its single and its multipart form. A declaration is about the
#: family, and a refusal that caught LineString and let MultiLineString through
#: would be a declaration narrower than the code for half the data in the wild.
SHAPES = {
    "point": [Point(10, 10), Point(60, 60), Point(90, 20)],
    "line": [LineString([(0, 0), (100, 100)]), LineString([(0, 100), (100, 0)])],
    "polygon": [Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])],
    "multipoint": [MultiPoint([(10, 10), (20, 20)]), MultiPoint([(60, 60), (90, 20)])],
    "multiline": [MultiLineString([[(0, 0), (50, 50)], [(50, 50), (100, 100)]])],
    "multipolygon": [MultiPolygon([
        Polygon([(0, 0), (40, 0), (40, 40), (0, 40)]),
        Polygon([(60, 60), (100, 60), (100, 100), (60, 100)]),
    ])],
}
FORMS = {
    "point": ("point", "multipoint"),
    "line": ("line", "multiline"),
    "polygon": ("polygon", "multipolygon"),
}


@pytest.fixture
def layers(tmp_path):
    # Neutral names on purpose. They were `point.gpkg`, `line.gpkg`, and a
    # refusal that quotes its path -- most do -- then contained a geometry word
    # whatever it said, so the message half of the check below could not fail
    # (found by review, 2026-09-29; D-079).
    out = {}
    for index, (form, geoms) in enumerate(SHAPES.items()):
        path = tmp_path / f"layer_{index}.gpkg"
        gpd.GeoDataFrame({"v": list(range(1, len(geoms) + 1))}, geometry=geoms, crs=CRS).to_file(
            path, layer="data", driver="GPKG"
        )
        out[form] = str(path)
    return out


@pytest.fixture
def raster(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    import numpy as np
    from rasterio.transform import from_origin

    path = tmp_path / "dem.tif"
    data = np.arange(100, dtype="float32").reshape(10, 10)
    with rasterio.open(
        path, "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
        crs=CRS, transform=from_origin(0, 100, 10, 10),
    ) as dst:
        dst.write(data, 1)
    return str(path)


def _whitebox():
    pytest.importorskip("whitebox_workflows")


# (operation, argument, families that argument accepts, call). `call` receives the
# layer to put in that argument, the other layers, the raster and an output path.
def _rows():
    from mapsmith.engines import linework, network, sampling, spatial_stats, vector, whitebox_engine
    from mapsmith.engines import raster as raster_ops

    return [
        ("thin_points", "input_path", {"point"},
         lambda lyr, L, r, out: spatial_stats.thin_points(lyr, out, min_distance=1.0)),
        ("cluster_points_by_distance", "input_path", {"point"},
         lambda lyr, L, r, out: spatial_stats.cluster_points_by_distance(lyr, out, 1.0)),
        ("voronoi_polygons", "input_path", {"point"},
         lambda lyr, L, r, out: vector.voronoi_polygons(lyr, out)),
        ("sample_raster_at_points", "points_path", {"point"},
         lambda lyr, L, r, out: sampling.sample_raster_at_points(r(), lyr, out, "nearest")),
        ("elevation_profile", "line_path", {"line"},
         lambda lyr, L, r, out: sampling.elevation_profile(r(), lyr, out, spacing=10.0)),
        ("viewshed", "stations_path", {"point"},
         lambda lyr, L, r, out: (_whitebox(),
                                 whitebox_engine.viewshed(r(), lyr, out, station_height=1.0))),
        ("watershed", "pour_points_path", {"point"},
         lambda lyr, L, r, out: (_whitebox(), whitebox_engine.watershed(r(), lyr, out))),
        ("network_shortest_path", "network_path", {"line"},
         lambda lyr, L, r, out: network.network_shortest_path(
             lyr, out, 0, 0, 100, 100, tolerance=5.0)),
        ("service_area", "network_path", {"line"},
         lambda lyr, L, r, out: network.service_area(lyr, out, 0, 0, budget=50.0, tolerance=5.0)),
        ("points_along_lines", "input_path", {"line"},
         lambda lyr, L, r, out: linework.points_along_lines(lyr, out, spacing=10.0)),
        ("line_intersections", "input_path", {"line"},
         lambda lyr, L, r, out: linework.line_intersections(lyr, None, out)),
        ("count_in_polygons", "points_path", {"point"},
         lambda lyr, L, r, out: vector.count_in_polygons(lyr, L["polygon"], out)),
        ("count_in_polygons", "polygons_path", {"polygon"},
         lambda lyr, L, r, out: vector.count_in_polygons(L["point"], lyr, out)),
        ("summarize_points_in_polygons", "points_path", {"point"},
         lambda lyr, L, r, out: vector.summarize_points_in_polygons(lyr, L["polygon"], out, "v")),
        ("summarize_points_in_polygons", "polygons_path", {"polygon"},
         lambda lyr, L, r, out: vector.summarize_points_in_polygons(L["point"], lyr, out, "v")),
        ("least_cost_path", "start_path", {"point"},
         lambda lyr, L, r, out: network.least_cost_path(r(), lyr, lyr, out)),
        ("zonal_statistics", "zones_path", {"polygon"},
         lambda lyr, L, r, out: raster_ops.zonal_statistics(r(), lyr, out, ["mean"])),
    ]


def test_every_declaration_has_rows_and_the_rows_are_the_declaration():
    declared = {
        op["name"]: set(op["applicability"]["geometry"])
        for op in catalog.OPERATIONS
        if op["applicability"].get("geometry")
    }
    assert declared, "no operation declares a geometry: the derivation is broken"
    covered: dict[str, set[str]] = {}
    for name, _argument, families, _call in _rows():
        covered.setdefault(name, set()).update(families)
    assert covered == declared, (
        "the catalogue's geometry declarations and the behaviour rows here differ: "
        f"declared only {sorted(set(declared) - set(covered))}, rows only "
        f"{sorted(set(covered) - set(declared))}, different sets "
        f"{sorted(n for n in set(declared) & set(covered) if declared[n] != covered[n])}"
    )


@pytest.mark.parametrize(
    ("name", "argument", "families", "call"),
    _rows(),
    ids=[f"{row[0]}-{row[1]}" for row in _rows()],
)
def test_each_family_an_argument_does_not_take_is_refused(
    name, argument, families, call, layers, raster, tmp_path
):
    for family in FAMILIES:
        if family in families:
            continue
        for form in FORMS[family]:
            with pytest.raises(ValueError) as refused:
                call(layers[form], layers, lambda: raster, str(tmp_path / f"out_{form}.parquet"))
            # The paths come out before the words are looked for: the test's
            # own directory is named after the test id, which names operations
            # like `count_in_polygons`.
            message = str(refused.value)
            for spelling in {str(tmp_path), tmp_path.as_posix()}:
                message = message.replace(spelling, "")
            assert GEOMETRY_WORDS.search(message), (
                f"{name} refused a {form} layer in {argument}, but not for its geometry: "
                f"{refused.value}"
            )


def test_the_message_check_can_fail(layers, tmp_path):
    """The check above, run on a refusal that says nothing about geometry.

    It passed on every message for as long as the fixture names carried the
    family, so it gets a test of its own that it can say no: the message every
    operation gives for a layer without a CRS, quoting a fixture path.
    """
    message = f"{layers['line']} has no CRS, so no distance in it means anything."
    for spelling in {str(tmp_path), tmp_path.as_posix()}:
        message = message.replace(spelling, "")
    assert not GEOMETRY_WORDS.search(message), message


def test_a_collection_of_polygons_is_still_a_polygon_zone(raster, tmp_path):
    """The refusal is about the shape, and a collection of polygons has that shape.

    `zonal_statistics` answered correctly for a GeometryCollection holding one
    polygon until the polygon refusal went in, and then refused it: the refusal
    read `geom_type`, which says "GeometryCollection" for a polygon. Found by
    review, 2026-09-29. The 5 x 5 block of the 10 x 10 ramp, as in the other
    closed-form zonal tests: 25 cells.
    """
    from shapely.geometry import GeometryCollection

    from mapsmith.engines import raster as raster_ops

    zones = tmp_path / "zones.gpkg"
    block = Polygon([(0, 100), (50, 100), (50, 50), (0, 50)])
    gpd.GeoDataFrame({"v": [1]}, geometry=[GeometryCollection([block])], crs=CRS).to_file(
        zones, driver="GPKG"
    )
    raster_ops.zonal_statistics(raster, str(zones), str(tmp_path / "out.parquet"), ["count"])
    assert gpd.read_parquet(tmp_path / "out.parquet")["count"].tolist() == [25.0]


@pytest.mark.parametrize(
    ("spelling", "family"),
    [("point", "point"), ("points", "point"), ("Point Z", "point"), ("3D Point", "point"),
     ("MultiPolygon", "polygon"), ("MultiPolygon25D", "polygon"), ("LineString M", "line"),
     ("polygons", "polygon")],
)
def test_the_spellings_drivers_use_are_understood(spelling, family):
    assert catalog.geometry_families(spelling) == {family}


def test_an_unknown_geometry_says_leaving_it_out_is_safe():
    with pytest.raises(ValueError, match="leave geometry out"):
        catalog.geometry_families("GeometryCollection")


@pytest.mark.parametrize(
    "operation", ["thin_points", "sample_raster_at_points", "points_along_lines", "line_intersections"]
)
def test_a_feature_with_no_geometry_is_refused_before_anything_is_written(
    operation, raster, tmp_path
):
    """Four operations crashed on a null geometry with a raw error.

    An AttributeError from `thin_points`, "cannot convert float NaN to integer"
    from the sampler, a failed sort of a set holding None from the two line
    operations (review, 2026-09-29). Now a refusal that counts them, and no
    output on disk.
    """
    from mapsmith.engines import linework, sampling, spatial_stats

    points = tmp_path / "with_null_points.gpkg"
    gpd.GeoDataFrame({"v": [1, 2]}, geometry=[Point(10, 10), None], crs=CRS).to_file(points)
    lines = tmp_path / "with_null_lines.gpkg"
    gpd.GeoDataFrame(
        {"v": [1, 2]}, geometry=[LineString([(0, 0), (100, 100)]), None], crs=CRS
    ).to_file(lines)
    out = tmp_path / "out.parquet"
    calls = {
        "thin_points": lambda: spatial_stats.thin_points(str(points), str(out), min_distance=1.0),
        "sample_raster_at_points": lambda: sampling.sample_raster_at_points(
            raster, str(points), str(out), "nearest"
        ),
        "points_along_lines": lambda: linework.points_along_lines(str(lines), str(out), 10.0),
        "line_intersections": lambda: linework.line_intersections(str(lines), None, str(out)),
    }
    with pytest.raises(ValueError, match=r"1 feature\(s\) with no or an empty geometry"):
        calls[operation]()
    assert not out.exists()

