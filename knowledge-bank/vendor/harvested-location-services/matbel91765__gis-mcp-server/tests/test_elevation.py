"""Tests for elevation tools.

Note: These tests mock the Open-Elevation API requests.
"""

from unittest.mock import AsyncMock, patch

import pytest

from locusync.tools.elevation import get_elevation, get_elevation_profile


class TestGetElevation:
    """Tests for the get_elevation tool."""

    @pytest.mark.asyncio
    async def test_get_elevation_invalid_lat(self):
        """Test get_elevation with invalid latitude."""
        result = await get_elevation(100, 2.3522)

        assert result["success"] is False
        assert "latitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_elevation_invalid_lon(self):
        """Test get_elevation with invalid longitude."""
        result = await get_elevation(48.8566, 200)

        assert result["success"] is False
        assert "longitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_elevation_response_structure(self):
        """Test that get_elevation returns correct structure (mocked)."""
        mock_response = {
            "results": [
                {
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "elevation": 35.5
                }
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await get_elevation(48.8566, 2.3522)

            assert result["success"] is True
            assert result["data"]["elevation_meters"] == 35.5
            assert result["data"]["location"]["lat"] == 48.8566
            assert result["data"]["location"]["lon"] == 2.3522
            assert result["metadata"]["source"] == "open-elevation"
            assert "SRTM" in result["metadata"]["dataset"]

    @pytest.mark.asyncio
    async def test_get_elevation_no_results(self):
        """Test get_elevation when no results found (mocked)."""
        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = {"results": []}

            result = await get_elevation(0, 0)

            assert result["success"] is False
            assert "no elevation data" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_elevation_null_elevation(self):
        """Test get_elevation when elevation is null (mocked)."""
        mock_response = {
            "results": [
                {
                    "latitude": 0,
                    "longitude": 0,
                    "elevation": None
                }
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await get_elevation(0, 0)

            assert result["success"] is False
            assert "not available" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_elevation_boundary_values(self):
        """Test get_elevation with valid boundary coordinates."""
        mock_response = {
            "results": [
                {
                    "latitude": 90,
                    "longitude": 180,
                    "elevation": 100.0
                }
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await get_elevation(90, 180)

            assert result["success"] is True
            assert result["data"]["elevation_meters"] == 100.0


class TestGetElevationProfile:
    """Tests for the get_elevation_profile tool."""

    @pytest.mark.asyncio
    async def test_elevation_profile_empty_coordinates(self):
        """Test elevation profile with empty coordinates."""
        result = await get_elevation_profile([])

        assert result["success"] is False
        assert "at least 2" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_elevation_profile_single_coordinate(self):
        """Test elevation profile with single coordinate."""
        result = await get_elevation_profile([[2.3522, 48.8566]])

        assert result["success"] is False
        assert "at least 2" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_elevation_profile_too_many_coordinates(self):
        """Test elevation profile with too many coordinates."""
        coords = [[i, i] for i in range(101)]
        result = await get_elevation_profile(coords)

        assert result["success"] is False
        assert "maximum 100" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_elevation_profile_invalid_coordinate_format(self):
        """Test elevation profile with invalid coordinate format."""
        result = await get_elevation_profile([[2.3522, 48.8566, 100], [2.4, 48.9]])

        assert result["success"] is False
        assert "must be [lon, lat]" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_elevation_profile_invalid_lat(self):
        """Test elevation profile with invalid latitude."""
        result = await get_elevation_profile([[2.3522, 100], [2.4, 48.9]])

        assert result["success"] is False
        assert "invalid coordinates" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_elevation_profile_invalid_lon(self):
        """Test elevation profile with invalid longitude."""
        result = await get_elevation_profile([[200, 48.8566], [2.4, 48.9]])

        assert result["success"] is False
        assert "invalid coordinates" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_elevation_profile_response_structure(self):
        """Test that elevation profile returns correct structure (mocked)."""
        mock_response = {
            "results": [
                {"latitude": 48.8566, "longitude": 2.3522, "elevation": 35.5},
                {"latitude": 48.8606, "longitude": 2.3376, "elevation": 40.2},
                {"latitude": 48.8584, "longitude": 2.2945, "elevation": 30.0}
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            coords = [[2.3522, 48.8566], [2.3376, 48.8606], [2.2945, 48.8584]]
            result = await get_elevation_profile(coords)

            assert result["success"] is True
            assert result["data"]["total_points"] == 3
            assert len(result["data"]["profile"]) == 3

            # Check first point
            profile = result["data"]["profile"]
            assert profile[0]["index"] == 0
            assert profile[0]["elevation_meters"] == 35.5
            assert profile[0]["location"]["lat"] == 48.8566
            assert profile[0]["location"]["lon"] == 2.3522

            # Check statistics
            stats = result["data"]["statistics"]
            assert stats["min_elevation_meters"] == 30.0
            assert stats["max_elevation_meters"] == 40.2
            assert stats["elevation_gain_meters"] == 10.2
            assert stats["avg_elevation_meters"] == pytest.approx(35.23, 0.01)

            # Check metadata
            assert result["metadata"]["source"] == "open-elevation"
            assert "SRTM" in result["metadata"]["dataset"]

    @pytest.mark.asyncio
    async def test_elevation_profile_with_null_values(self):
        """Test elevation profile when some elevations are null (mocked)."""
        mock_response = {
            "results": [
                {"latitude": 48.8566, "longitude": 2.3522, "elevation": 35.5},
                {"latitude": 48.8606, "longitude": 2.3376, "elevation": None},
                {"latitude": 48.8584, "longitude": 2.2945, "elevation": 30.0}
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            coords = [[2.3522, 48.8566], [2.3376, 48.8606], [2.2945, 48.8584]]
            result = await get_elevation_profile(coords)

            assert result["success"] is True
            assert result["data"]["total_points"] == 3

            # Check that null is preserved
            profile = result["data"]["profile"]
            assert profile[1]["elevation_meters"] is None

            # Check statistics only include non-null values
            stats = result["data"]["statistics"]
            assert stats["min_elevation_meters"] == 30.0
            assert stats["max_elevation_meters"] == 35.5

    @pytest.mark.asyncio
    async def test_elevation_profile_all_null_values(self):
        """Test elevation profile when all elevations are null (mocked)."""
        mock_response = {
            "results": [
                {"latitude": 48.8566, "longitude": 2.3522, "elevation": None},
                {"latitude": 48.8606, "longitude": 2.3376, "elevation": None}
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            coords = [[2.3522, 48.8566], [2.3376, 48.8606]]
            result = await get_elevation_profile(coords)

            assert result["success"] is True
            assert result["data"]["total_points"] == 2
            assert result["data"]["statistics"] is None

    @pytest.mark.asyncio
    async def test_elevation_profile_minimum_coordinates(self):
        """Test elevation profile with exactly 2 coordinates (minimum)."""
        mock_response = {
            "results": [
                {"latitude": 48.8566, "longitude": 2.3522, "elevation": 35.5},
                {"latitude": 48.8606, "longitude": 2.3376, "elevation": 40.2}
            ]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            coords = [[2.3522, 48.8566], [2.3376, 48.8606]]
            result = await get_elevation_profile(coords)

            assert result["success"] is True
            assert result["data"]["total_points"] == 2


class TestValidation:
    """Tests for coordinate validation in elevation tools."""

    @pytest.mark.asyncio
    async def test_lat_boundary_min(self):
        """Test latitude at minimum boundary."""
        mock_response = {
            "results": [{"latitude": -90, "longitude": 0, "elevation": 0}]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await get_elevation(-90, 0)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_lat_boundary_max(self):
        """Test latitude at maximum boundary."""
        mock_response = {
            "results": [{"latitude": 90, "longitude": 0, "elevation": 0}]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await get_elevation(90, 0)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_lon_boundary_min(self):
        """Test longitude at minimum boundary."""
        mock_response = {
            "results": [{"latitude": 0, "longitude": -180, "elevation": 0}]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await get_elevation(0, -180)
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_lon_boundary_max(self):
        """Test longitude at maximum boundary."""
        mock_response = {
            "results": [{"latitude": 0, "longitude": 180, "elevation": 0}]
        }

        with patch("locusync.tools.elevation._open_elevation_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await get_elevation(0, 180)
            assert result["success"] is True
