"""Tests for Shapely functions."""
import pytest
import sys
import json
from pathlib import Path
from shapely.geometry import Point, Polygon, LineString
from shapely import wkt
from fastmcp import Client

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gis_mcp.mcp import gis_mcp
from tests.test_helpers import get_result_data


class TestBasicGeometricOperations:
    """Test basic geometric operations."""
    
    @pytest.mark.asyncio
    async def test_buffer(self):
        """Test buffer operation."""
        point = Point(0, 0)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("buffer", {
                "geometry": point.wkt,
                "distance": 10.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
            buffered = wkt.loads(result_data["geometry"])
            assert buffered.area > 0
    
    @pytest.mark.asyncio
    async def test_intersection(self):
        """Test intersection operation."""
        poly1 = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        poly2 = Polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("intersection", {
                "geometry1": poly1.wkt,
                "geometry2": poly2.wkt
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_union(self):
        """Test union operation."""
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = Polygon([(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("union", {
                "geometry1": poly1.wkt,
                "geometry2": poly2.wkt
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_difference(self):
        """Test difference operation."""
        poly1 = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        poly2 = Polygon([(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("difference", {
                "geometry1": poly1.wkt,
                "geometry2": poly2.wkt
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_symmetric_difference(self):
        """Test symmetric difference operation."""
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = Polygon([(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("symmetric_difference", {
                "geometry1": poly1.wkt,
                "geometry2": poly2.wkt
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data


class TestGeometricProperties:
    """Test geometric property operations."""
    
    @pytest.mark.asyncio
    async def test_convex_hull(self):
        """Test convex hull calculation."""
        poly = Polygon([(0, 0), (1, 0.5), (2, 0), (1.5, 1), (0.5, 1), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("convex_hull", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_envelope(self):
        """Test envelope calculation."""
        poly = Polygon([(0, 0), (2, 0), (2, 3), (0, 3), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("envelope", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_minimum_rotated_rectangle(self):
        """Test minimum rotated rectangle."""
        poly = Polygon([(0, 0), (1, 0.5), (2, 0), (1.5, 1), (0.5, 1), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("minimum_rotated_rectangle", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_get_centroid(self):
        """Test centroid calculation."""
        poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_centroid", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
            centroid = wkt.loads(result_data["geometry"])
            assert isinstance(centroid, Point)
    
    @pytest.mark.asyncio
    async def test_get_bounds(self):
        """Test bounds calculation."""
        poly = Polygon([(0, 0), (2, 0), (2, 3), (0, 3), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_bounds", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "bounds" in result_data
            assert len(result_data["bounds"]) == 4
            assert result_data["bounds"] == [0.0, 0.0, 2.0, 3.0]
    
    @pytest.mark.asyncio
    async def test_get_coordinates(self):
        """Test coordinate extraction."""
        point = Point(1, 2)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_coordinates", {"geometry": point.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "coordinates" in result_data
    
    @pytest.mark.asyncio
    async def test_get_geometry_type(self):
        """Test geometry type retrieval."""
        point = Point(0, 0)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_geometry_type", {"geometry": point.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert result_data["type"] == "Point"


class TestTransformations:
    """Test geometric transformations."""
    
    @pytest.mark.asyncio
    async def test_rotate_geometry(self):
        """Test geometry rotation."""
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("rotate_geometry", {"geometry": poly.wkt, "angle": 45.0})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_scale_geometry(self):
        """Test geometry scaling."""
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("scale_geometry", {"geometry": poly.wkt, "xfact": 2.0, "yfact": 2.0})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_translate_geometry(self):
        """Test geometry translation."""
        point = Point(0, 0)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("translate_geometry", {"geometry": point.wkt, "xoff": 5.0, "yoff": 10.0})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
            translated = wkt.loads(result_data["geometry"])
            assert translated.x == 5.0
            assert translated.y == 10.0


class TestAdvancedOperations:
    """Test advanced geometric operations."""
    
    @pytest.mark.asyncio
    async def test_triangulate_geometry(self):
        """Test triangulation."""
        poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("triangulate_geometry", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometries" in result_data
            assert isinstance(result_data["geometries"], list)
            assert len(result_data["geometries"]) > 0
    
    @pytest.mark.asyncio
    async def test_voronoi(self):
        """Test Voronoi diagram creation."""
        points = [Point(0, 0), Point(1, 1), Point(2, 0)]
        points_wkt = "MULTIPOINT ((0 0), (1 1), (2 0))"
        async with Client(gis_mcp) as client:
            result = await client.call_tool("voronoi", {"geometry": points_wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_unary_union_geometries(self):
        """Test unary union of multiple geometries."""
        geoms = [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]).wkt,
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)]).wkt
        ]
        async with Client(gis_mcp) as client:
            result = await client.call_tool("unary_union_geometries", {"geometries": geoms})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data


class TestMeasurements:
    """Test measurement operations."""
    
    @pytest.mark.asyncio
    async def test_get_length(self):
        """Test length calculation."""
        line = LineString([(0, 0), (3, 4)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_length", {"geometry": line.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "length" in result_data
            assert result_data["length"] > 0
    
    @pytest.mark.asyncio
    async def test_get_area(self):
        """Test area calculation."""
        poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("get_area", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "area" in result_data
            assert result_data["area"] == 4.0


class TestValidationAndUtilities:
    """Test validation and utility operations."""
    
    @pytest.mark.asyncio
    async def test_is_valid(self):
        """Test geometry validation."""
        poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("is_valid", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "is_valid" in result_data
            assert result_data["is_valid"] is True
    
    @pytest.mark.asyncio
    async def test_make_valid(self):
        """Test making invalid geometry valid."""
        # Create a potentially invalid geometry
        poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("make_valid", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_simplify(self):
        """Test geometry simplification."""
        line = LineString([(0, 0), (0.5, 0.1), (1, 0), (1.5, 0.1), (2, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("simplify", {"geometry": line.wkt, "tolerance": 0.2})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_snap_geometry(self):
        """Test geometry snapping."""
        point = Point(0.1, 0.1)
        target = Point(0, 0)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("snap_geometry", {
                "geometry1": point.wkt,
                "geometry2": target.wkt,
                "tolerance": 0.2
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_nearest_point_on_geometry(self):
        """Test finding nearest point on geometry."""
        point = Point(5, 5)
        line = LineString([(0, 0), (10, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("nearest_point_on_geometry", {
                "geometry1": point.wkt,
                "geometry2": line.wkt
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "nearest_point" in result_data
    
    @pytest.mark.asyncio
    async def test_normalize_geometry(self):
        """Test geometry normalization."""
        poly = Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)])
        async with Client(gis_mcp) as client:
            result = await client.call_tool("normalize_geometry", {"geometry": poly.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
    
    @pytest.mark.asyncio
    async def test_geometry_to_geojson(self):
        """Test geometry to GeoJSON conversion."""
        point = Point(1, 2)
        async with Client(gis_mcp) as client:
            result = await client.call_tool("geometry_to_geojson", {"geometry": point.wkt})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geojson" in result_data
    
    @pytest.mark.asyncio
    async def test_geojson_to_geometry(self):
        """Test GeoJSON to geometry conversion."""
        geojson = {"type": "Point", "coordinates": [1, 2]}
        async with Client(gis_mcp) as client:
            result = await client.call_tool("geojson_to_geometry", {"geojson": geojson})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "geometry" in result_data
            geom = wkt.loads(result_data["geometry"])
            assert isinstance(geom, Point)
