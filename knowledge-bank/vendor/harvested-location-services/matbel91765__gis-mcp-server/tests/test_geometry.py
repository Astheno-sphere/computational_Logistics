"""Tests for geometry tools."""

import pytest

from locusync.tools.geometry import (
    calculate_buffer,
    calculate_distance,
    perform_spatial_query,
    transform_coordinates,
)


class TestDistance:
    """Tests for the distance tool."""

    @pytest.mark.asyncio
    async def test_geodesic_distance_paris_london(self):
        """Test geodesic distance between Paris and London."""
        result = await calculate_distance(
            lat1=48.8566, lon1=2.3522,  # Paris
            lat2=51.5074, lon2=-0.1278,  # London
            method="geodesic"
        )

        assert result["success"] is True
        assert result["error"] is None

        distance_km = result["data"]["distance"]["kilometers"]
        # Paris-London is approximately 343 km
        assert 340 < distance_km < 350

    @pytest.mark.asyncio
    async def test_haversine_distance_paris_london(self):
        """Test haversine distance between Paris and London."""
        result = await calculate_distance(
            lat1=48.8566, lon1=2.3522,
            lat2=51.5074, lon2=-0.1278,
            method="haversine"
        )

        assert result["success"] is True
        distance_km = result["data"]["distance"]["kilometers"]
        # Haversine should be close to geodesic
        assert 340 < distance_km < 350

    @pytest.mark.asyncio
    async def test_distance_same_point(self):
        """Test distance when both points are the same."""
        result = await calculate_distance(
            lat1=48.8566, lon1=2.3522,
            lat2=48.8566, lon2=2.3522,
            method="geodesic"
        )

        assert result["success"] is True
        assert result["data"]["distance"]["meters"] < 1

    @pytest.mark.asyncio
    async def test_invalid_coordinates(self):
        """Test with invalid coordinates."""
        result = await calculate_distance(
            lat1=100, lon1=2.3522,  # Invalid latitude
            lat2=51.5074, lon2=-0.1278,
            method="geodesic"
        )

        assert result["success"] is False
        assert "latitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_method(self):
        """Test with invalid method."""
        result = await calculate_distance(
            lat1=48.8566, lon1=2.3522,
            lat2=51.5074, lon2=-0.1278,
            method="invalid"
        )

        assert result["success"] is False
        assert "invalid" in result["error"].lower()


class TestBuffer:
    """Tests for the buffer tool."""

    @pytest.mark.asyncio
    async def test_point_buffer(self):
        """Test buffer around a point."""
        geometry = {
            "type": "Point",
            "coordinates": [2.3522, 48.8566]  # Paris
        }

        result = await calculate_buffer(geometry, 1000)  # 1km buffer

        assert result["success"] is True
        assert result["data"]["geometry"]["type"] == "Polygon"
        # Area of 1km circle should be ~3.14 km²
        assert 3.0 < result["data"]["area_km2"] < 3.5

    @pytest.mark.asyncio
    async def test_linestring_buffer(self):
        """Test buffer around a linestring."""
        geometry = {
            "type": "LineString",
            "coordinates": [
                [2.3522, 48.8566],
                [2.3622, 48.8666]
            ]
        }

        result = await calculate_buffer(geometry, 500)  # 500m buffer

        assert result["success"] is True
        assert result["data"]["geometry"]["type"] == "Polygon"

    @pytest.mark.asyncio
    async def test_buffer_invalid_distance(self):
        """Test buffer with invalid distance."""
        geometry = {"type": "Point", "coordinates": [2.3522, 48.8566]}

        result = await calculate_buffer(geometry, -100)

        assert result["success"] is False
        assert "positive" in result["error"].lower()


class TestSpatialQuery:
    """Tests for spatial query tool."""

    @pytest.mark.asyncio
    async def test_intersection(self):
        """Test intersection of two overlapping polygons."""
        polygon1 = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]
        }
        polygon2 = {
            "type": "Polygon",
            "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]
        }

        result = await perform_spatial_query(polygon1, polygon2, "intersection")

        assert result["success"] is True
        assert result["data"]["geometry"] is not None
        assert result["data"]["is_empty"] is False

    @pytest.mark.asyncio
    async def test_contains(self):
        """Test contains predicate."""
        outer = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]
        }
        inner = {
            "type": "Point",
            "coordinates": [5, 5]
        }

        result = await perform_spatial_query(outer, inner, "contains")

        assert result["success"] is True
        assert result["data"]["result"] is True

    @pytest.mark.asyncio
    async def test_union(self):
        """Test union of two polygons."""
        polygon1 = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]
        }
        polygon2 = {
            "type": "Polygon",
            "coordinates": [[[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]]]
        }

        result = await perform_spatial_query(polygon1, polygon2, "union")

        assert result["success"] is True
        assert result["data"]["geometry"] is not None

    @pytest.mark.asyncio
    async def test_invalid_operation(self):
        """Test with invalid operation."""
        polygon = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
        }

        result = await perform_spatial_query(polygon, polygon, "invalid_op")

        assert result["success"] is False
        assert "invalid" in result["error"].lower()


class TestTransformCRS:
    """Tests for CRS transformation tool."""

    @pytest.mark.asyncio
    async def test_wgs84_to_web_mercator(self):
        """Test transformation from WGS84 to Web Mercator."""
        geometry = {
            "type": "Point",
            "coordinates": [0, 0]  # Equator/Prime meridian intersection
        }

        result = await transform_coordinates(
            geometry,
            source_crs="EPSG:4326",
            target_crs="EPSG:3857"
        )

        assert result["success"] is True
        # At origin, Web Mercator should also be near 0,0
        coords = result["data"]["geometry"]["coordinates"]
        assert abs(coords[0]) < 1
        assert abs(coords[1]) < 1

    @pytest.mark.asyncio
    async def test_roundtrip_transformation(self):
        """Test that roundtrip transformation preserves coordinates."""
        original_coords = [2.3522, 48.8566]  # Paris
        geometry = {
            "type": "Point",
            "coordinates": original_coords
        }

        # Transform to Web Mercator
        result1 = await transform_coordinates(
            geometry,
            source_crs="EPSG:4326",
            target_crs="EPSG:3857"
        )

        assert result1["success"] is True

        # Transform back to WGS84
        result2 = await transform_coordinates(
            result1["data"]["geometry"],
            source_crs="EPSG:3857",
            target_crs="EPSG:4326"
        )

        assert result2["success"] is True

        # Check coordinates are preserved (within floating point precision)
        final_coords = result2["data"]["geometry"]["coordinates"]
        assert abs(final_coords[0] - original_coords[0]) < 0.0001
        assert abs(final_coords[1] - original_coords[1]) < 0.0001

    @pytest.mark.asyncio
    async def test_invalid_source_crs(self):
        """Test with invalid source CRS."""
        geometry = {"type": "Point", "coordinates": [0, 0]}

        result = await transform_coordinates(
            geometry,
            source_crs="INVALID",
            target_crs="EPSG:3857"
        )

        assert result["success"] is False
        assert "source" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_target_crs(self):
        """Test with invalid target CRS."""
        geometry = {"type": "Point", "coordinates": [0, 0]}

        result = await transform_coordinates(
            geometry,
            source_crs="EPSG:4326",
            target_crs="NOT_A_CRS"
        )

        assert result["success"] is False
        assert "target" in result["error"].lower()
