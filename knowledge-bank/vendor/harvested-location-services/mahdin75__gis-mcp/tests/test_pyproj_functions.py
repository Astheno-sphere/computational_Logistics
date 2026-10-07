"""Tests for PyProj functions."""
import pytest
import sys
import json
from pathlib import Path
from shapely.geometry import Point, Polygon
from shapely import wkt
from fastmcp import Client

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gis_mcp.mcp import gis_mcp
from tests.test_helpers import get_result_data


class TestCoordinateTransformations:
    """Test coordinate transformation operations."""
    
    @pytest.mark.asyncio
    async def test_transform_coordinates(self):
        """Test coordinate transformation."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("transform_coordinates", {
                "coordinates": [0, 0],
                "source_crs": "EPSG:4326",
                "target_crs": "EPSG:3857"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "coordinates" in result_data
            assert len(result_data["coordinates"]) == 2
            assert isinstance(result_data["coordinates"][0], float)
            assert isinstance(result_data["coordinates"][1], float)
    
    @pytest.mark.asyncio
    async def test_project_geometry(self):
        """Test geometry projection."""
        point = Point(0, 0)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("project_geometry", {
                "geometry": point.wkt,
                "source_crs": "EPSG:4326",
                "target_crs": "EPSG:3857"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
            assert result_data["source_crs"] == "EPSG:4326"
            assert result_data["target_crs"] == "EPSG:3857"


class TestCRSInformation:
    """Test CRS information operations."""
    
    @pytest.mark.asyncio
    async def test_get_crs_info(self):
        """Test getting CRS information."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_crs_info", {"crs": "EPSG:4326"})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "name" in result_data
            assert "type" in result_data
            assert "is_geographic" in result_data
            assert result_data["is_geographic"] is True
    
    @pytest.mark.asyncio
    async def test_get_available_crs(self):
        """Test getting available CRS list."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_available_crs", {})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "crs_list" in result_data
            assert isinstance(result_data["crs_list"], list)
            assert len(result_data["crs_list"]) > 0
    
    @pytest.mark.asyncio
    async def test_get_utm_zone(self):
        """Test getting UTM zone."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_utm_zone", {"coordinates": [-120, 40]})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "zone" in result_data
            assert isinstance(result_data["zone"], int)
            assert 1 <= result_data["zone"] <= 60
    
    @pytest.mark.asyncio
    async def test_get_utm_crs(self):
        """Test getting UTM CRS."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_utm_crs", {"coordinates": [-120, 40]})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "crs" in result_data
            assert "EPSG" in result_data["crs"]
    
    @pytest.mark.asyncio
    async def test_get_geocentric_crs(self):
        """Test getting geocentric CRS."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_geocentric_crs", {"coordinates": [0, 0]})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "crs" in result_data


class TestGeodeticCalculations:
    """Test geodetic calculation operations."""
    
    @pytest.mark.asyncio
    async def test_get_geod_info(self):
        """Test getting geodetic information."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_geod_info", {"ellps": "WGS84"})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "ellipsoid" in result_data
            assert "a" in result_data  # semi-major axis
            assert "b" in result_data  # semi-minor axis
    
    @pytest.mark.asyncio
    async def test_calculate_geodetic_distance(self):
        """Test geodetic distance calculation."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("calculate_geodetic_distance", {
                "point1": [0, 0],
                "point2": [1, 1],
                "ellps": "WGS84"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "distance" in result_data
            assert result_data["distance"] > 0
            assert "unit" in result_data
    
    @pytest.mark.asyncio
    async def test_calculate_geodetic_point(self):
        """Test calculating point at distance and azimuth."""
        async with Client(gis_mcp) as client:
            result = await client.call_tool("calculate_geodetic_point", {
                "start_point": [0, 0],
                "azimuth": 45.0,
                "distance": 100000.0,  # 100 km
                "ellps": "WGS84"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "point" in result_data
            assert len(result_data["point"]) == 2
    
    @pytest.mark.asyncio
    async def test_calculate_geodetic_area(self):
        """Test geodetic area calculation."""
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("calculate_geodetic_area", {
                "geometry": poly.wkt,
                "ellps": "WGS84"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "area" in result_data
            assert result_data["area"] > 0
            assert "unit" in result_data
