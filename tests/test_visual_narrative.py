import geopandas as gpd
import pytest
from shapely.geometry import LineString, Polygon

import coast


def coastline(*geoms):
    return gpd.GeoDataFrame(geometry=list(geoms))


def test_sea_is_right_of_the_coastline():
    # coast runs west -> east at y = 40: land on the left (north), sea on the right (south)
    sea, _ = coast.sea_polygons(coastline(LineString([(-10, 40), (110, 40)])), (0, 0, 100, 100))
    assert sea.area == pytest.approx(100 * 40)
    assert sea.contains(gpd.points_from_xy([50], [10])[0])


def test_reversed_coastline_flips_the_sea():
    sea, _ = coast.sea_polygons(coastline(LineString([(110, 40), (-10, 40)])), (0, 0, 100, 100))
    assert sea.area == pytest.approx(100 * 60)


def test_island_is_cut_out_of_the_sea():
    island = Polygon([(40, 10), (60, 10), (60, 20), (40, 20)])
    sea, _ = coast.sea_polygons(coastline(LineString([(-10, 40), (110, 40)]), island), (0, 0, 100, 100))
    assert sea.area == pytest.approx(100 * 40 - 200)


def test_loose_end_inside_the_frame_shrinks_it():
    # an extract cut on a lat/lon box can end its coastline just inside a metric frame
    sea, bounds = coast.sea_polygons(coastline(LineString([(-10, 40), (97, 40)])), (0, 0, 100, 100))
    assert bounds[2] < 97 and bounds[0] > 0
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    assert sea.area == pytest.approx(width * (40 - bounds[1]))
