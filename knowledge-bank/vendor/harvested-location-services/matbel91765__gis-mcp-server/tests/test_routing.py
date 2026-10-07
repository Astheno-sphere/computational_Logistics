"""Tests for routing tools."""

from unittest.mock import AsyncMock, patch

import pytest

from locusync.tools.routing import (
    _destination_point,
    _generate_sample_points,
    _normalize_profile,
    calculate_isochrone,
    calculate_route,
)


class TestNormalizeProfile:
    """Tests for profile normalization."""

    def test_driving_profiles(self):
        """Test driving profile aliases."""
        assert _normalize_profile("driving") == "car"
        assert _normalize_profile("car") == "car"
        assert _normalize_profile("DRIVING") == "car"

    def test_walking_profiles(self):
        """Test walking profile aliases."""
        assert _normalize_profile("walking") == "foot"
        assert _normalize_profile("foot") == "foot"
        assert _normalize_profile("pedestrian") == "foot"

    def test_cycling_profiles(self):
        """Test cycling profile aliases."""
        assert _normalize_profile("cycling") == "bike"
        assert _normalize_profile("bike") == "bike"
        assert _normalize_profile("bicycle") == "bike"

    def test_invalid_profile(self):
        """Test invalid profile returns None."""
        assert _normalize_profile("invalid") is None
        assert _normalize_profile("airplane") is None


class TestDestinationPoint:
    """Tests for destination point calculation."""

    def test_destination_north(self):
        """Test destination point going north."""
        lat, lon = _destination_point(0, 0, 111.32, 0)  # ~1 degree north
        assert abs(lat - 1.0) < 0.1  # Should be approximately 1 degree north
        assert abs(lon) < 0.1  # Longitude should stay near 0

    def test_destination_east(self):
        """Test destination point going east."""
        lat, lon = _destination_point(0, 0, 111.32, 90)  # ~1 degree east at equator
        assert abs(lat) < 0.1  # Latitude should stay near 0
        assert abs(lon - 1.0) < 0.1  # Should be approximately 1 degree east

    def test_destination_south(self):
        """Test destination point going south."""
        lat, lon = _destination_point(0, 0, 111.32, 180)  # ~1 degree south
        assert abs(lat + 1.0) < 0.1  # Should be approximately 1 degree south

    def test_destination_zero_distance(self):
        """Test with zero distance."""
        lat, lon = _destination_point(48.8566, 2.3522, 0, 45)
        assert abs(lat - 48.8566) < 0.0001
        assert abs(lon - 2.3522) < 0.0001


class TestGenerateSamplePoints:
    """Tests for sample point generation."""

    def test_generates_correct_count(self):
        """Test that correct number of points is generated."""
        points = _generate_sample_points(48.8566, 2.3522, 10, num_rings=3, points_per_ring=8)
        assert len(points) == 3 * 8  # 24 points

    def test_generates_tuples(self):
        """Test that points are (lon, lat) tuples."""
        points = _generate_sample_points(48.8566, 2.3522, 10, num_rings=2, points_per_ring=4)
        for point in points:
            assert isinstance(point, tuple)
            assert len(point) == 2
            lon, lat = point
            assert isinstance(lon, float)
            assert isinstance(lat, float)

    def test_points_within_distance(self):
        """Test that all points are within expected distance."""
        center_lat, center_lon = 48.8566, 2.3522
        max_distance_km = 5
        points = _generate_sample_points(center_lat, center_lon, max_distance_km, num_rings=3, points_per_ring=8)

        # All points should be within reasonable bounds
        for lon, lat in points:
            # Rough check - points should be within ~0.1 degrees for 5km
            assert abs(lat - center_lat) < 0.2
            assert abs(lon - center_lon) < 0.2


class TestCalculateRoute:
    """Tests for route calculation."""

    @pytest.mark.asyncio
    async def test_invalid_start_coordinates(self):
        """Test with invalid start coordinates."""
        result = await calculate_route(
            start_lat=100,  # Invalid
            start_lon=2.3522,
            end_lat=48.8606,
            end_lon=2.3376
        )
        assert result["success"] is False
        assert "start" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_end_coordinates(self):
        """Test with invalid end coordinates."""
        result = await calculate_route(
            start_lat=48.8566,
            start_lon=2.3522,
            end_lat=48.8606,
            end_lon=200  # Invalid
        )
        assert result["success"] is False
        assert "end" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_profile(self):
        """Test with invalid routing profile."""
        result = await calculate_route(
            start_lat=48.8566,
            start_lon=2.3522,
            end_lat=48.8606,
            end_lon=2.3376,
            profile="airplane"
        )
        assert result["success"] is False
        assert "profile" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_route_success_mocked(self):
        """Test successful route calculation (mocked)."""
        mock_response = {
            "code": "Ok",
            "routes": [{
                "distance": 5432.1,
                "duration": 842.5,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[2.3522, 48.8566], [2.3376, 48.8606]]
                },
                "legs": [{
                    "steps": [{
                        "maneuver": {"instruction": "Head north"},
                        "distance": 100,
                        "duration": 20,
                        "name": "Rue de Test",
                        "mode": "driving"
                    }]
                }]
            }]
        }

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await calculate_route(
                start_lat=48.8566,
                start_lon=2.3522,
                end_lat=48.8606,
                end_lon=2.3376,
                profile="driving"
            )

            assert result["success"] is True
            assert "distance" in result["data"]
            assert "duration" in result["data"]
            assert "geometry" in result["data"]
            assert "steps" in result["data"]
            assert result["metadata"]["source"] == "osrm"

    @pytest.mark.asyncio
    async def test_route_no_routes_found(self):
        """Test when no routes are found."""
        mock_response = {
            "code": "Ok",
            "routes": []
        }

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await calculate_route(
                start_lat=48.8566,
                start_lon=2.3522,
                end_lat=48.8606,
                end_lon=2.3376
            )

            assert result["success"] is False
            assert "no route" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_route_api_error(self):
        """Test when OSRM returns an error."""
        mock_response = {
            "code": "NoRoute",
            "message": "No route found"
        }

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await calculate_route(
                start_lat=48.8566,
                start_lon=2.3522,
                end_lat=48.8606,
                end_lon=2.3376
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_route_network_error(self):
        """Test network error handling."""
        import aiohttp

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.side_effect = aiohttp.ClientError("Connection failed")

            result = await calculate_route(
                start_lat=48.8566,
                start_lon=2.3522,
                end_lat=48.8606,
                end_lon=2.3376
            )

            assert result["success"] is False
            assert "network" in result["error"].lower()


class TestCalculateIsochrone:
    """Tests for isochrone calculation."""

    @pytest.mark.asyncio
    async def test_invalid_center_coordinates(self):
        """Test with invalid center coordinates."""
        result = await calculate_isochrone(
            lat=100,  # Invalid
            lon=2.3522,
            time_minutes=15
        )
        assert result["success"] is False
        assert "center" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_time_too_low(self):
        """Test with time less than 1 minute."""
        result = await calculate_isochrone(
            lat=48.8566,
            lon=2.3522,
            time_minutes=0
        )
        assert result["success"] is False
        assert "time" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_time_too_high(self):
        """Test with time greater than 120 minutes."""
        result = await calculate_isochrone(
            lat=48.8566,
            lon=2.3522,
            time_minutes=121
        )
        assert result["success"] is False
        assert "time" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_profile(self):
        """Test with invalid profile."""
        result = await calculate_isochrone(
            lat=48.8566,
            lon=2.3522,
            time_minutes=15,
            profile="helicopter"
        )
        assert result["success"] is False
        assert "profile" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_isochrone_success_mocked(self):
        """Test successful isochrone calculation (mocked)."""
        # Generate durations - center point + sample points
        # Most points reachable, some not
        durations = [[0] + [300 + i * 10 for i in range(128)]]  # All reachable within 15 min (900s)

        mock_response = {
            "code": "Ok",
            "durations": durations
        }

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await calculate_isochrone(
                lat=48.8566,
                lon=2.3522,
                time_minutes=15,
                profile="driving"
            )

            assert result["success"] is True
            assert "geometry" in result["data"]
            assert result["data"]["time_minutes"] == 15
            assert result["metadata"]["source"] == "osrm"

    @pytest.mark.asyncio
    async def test_isochrone_not_enough_points(self):
        """Test when not enough reachable points."""
        # Only 2 points reachable (need at least 3)
        durations = [[0] + [None] * 126 + [100, 200]]  # Most points unreachable

        mock_response = {
            "code": "Ok",
            "durations": durations
        }

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await calculate_isochrone(
                lat=48.8566,
                lon=2.3522,
                time_minutes=1,  # Very short time
                profile="driving"
            )

            assert result["success"] is False
            assert "not enough" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_isochrone_api_error(self):
        """Test when OSRM returns an error."""
        mock_response = {
            "code": "InvalidQuery",
            "message": "Invalid coordinates"
        }

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await calculate_isochrone(
                lat=48.8566,
                lon=2.3522,
                time_minutes=15
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_isochrone_network_error(self):
        """Test network error handling."""
        import aiohttp

        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.side_effect = aiohttp.ClientError("Connection failed")

            result = await calculate_isochrone(
                lat=48.8566,
                lon=2.3522,
                time_minutes=15
            )

            assert result["success"] is False
            assert "network" in result["error"].lower()
