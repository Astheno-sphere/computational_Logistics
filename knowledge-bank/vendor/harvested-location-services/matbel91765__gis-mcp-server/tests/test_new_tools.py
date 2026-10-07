"""Tests for distance_matrix and batch_reverse_geocode."""

from unittest.mock import AsyncMock, patch

import pytest

from locusync.tools.geocoding import batch_reverse_geocode
from locusync.tools.routing import calculate_distance_matrix


class TestDistanceMatrix:
    @pytest.mark.asyncio
    async def test_requires_two_points(self):
        result = await calculate_distance_matrix([[48.85, 2.35]])
        assert result["success"] is False
        assert "at least 2" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_too_many_points(self):
        pts = [[0.0, float(i)] for i in range(26)]
        result = await calculate_distance_matrix(pts)
        assert result["success"] is False
        assert "too many" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_coordinate(self):
        result = await calculate_distance_matrix([[91.0, 0.0], [0.0, 0.0]])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_matrix_success(self):
        osrm = {
            "code": "Ok",
            "durations": [[0, 120], [130, 0]],
            "distances": [[0, 1000], [1100, 0]],
        }
        with patch("locusync.tools.routing._osrm_request", new_callable=AsyncMock) as mock:
            mock.return_value = osrm
            result = await calculate_distance_matrix([[48.85, 2.35], [48.86, 2.34]])
            assert result["success"] is True
            assert result["data"]["durations_seconds"][0][1] == 120
            assert result["data"]["distances_meters"][1][0] == 1100
            assert result["data"]["point_count"] == 2


class TestBatchReverseGeocode:
    @pytest.mark.asyncio
    async def test_empty(self):
        result = await batch_reverse_geocode([])
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_too_many(self):
        coords = [[0.0, float(i)] for i in range(26)]
        result = await batch_reverse_geocode(coords)
        assert result["success"] is False
        assert "too many" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_dedup(self):
        mock_response = {
            "display_name": "Paris, France",
            "type": "city",
            "class": "place",
            "address": {"city": "Paris", "country": "France"},
        }
        coords = [[48.8566, 2.3522], [48.8566, 2.3522]]
        with patch(
            "locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock
        ) as mock:
            mock.return_value = mock_response
            result = await batch_reverse_geocode(coords)
            assert result["success"] is True
            assert result["data"]["summary"]["total"] == 2
            assert result["data"]["summary"]["unique_geocoded"] == 1
            assert mock.call_count == 1
