"""Tests for geocoding tools.

Note: These tests require network access to Nominatim.
For CI/CD, consider mocking the HTTP requests.
"""

from unittest.mock import AsyncMock, patch

import pytest

from locusync.config import Config, PeliasConfig
from locusync.tools.geocoding import batch_geocode, geocode_address, reverse_geocode_coords


def _create_pelias_config():
    """Create a mock config with Pelias configured."""
    config = Config()
    config.pelias = PeliasConfig(
        base_url="http://localhost:4000",
        api_key="test-key",
        timeout=10.0
    )
    return config


class TestGeocode:
    """Tests for the geocode tool."""

    @pytest.mark.asyncio
    async def test_geocode_empty_address(self):
        """Test geocoding with empty address."""
        result = await geocode_address("")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_geocode_whitespace_address(self):
        """Test geocoding with whitespace-only address."""
        result = await geocode_address("   ")

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_geocode_response_structure(self):
        """Test that geocode returns correct structure (mocked)."""
        mock_response = [{
            "lat": "48.8566",
            "lon": "2.3522",
            "display_name": "Paris, Île-de-France, France",
            "type": "city",
            "class": "place",
            "importance": 0.9,
            "osm_type": "relation",
            "osm_id": 7444,
            "boundingbox": ["48.815", "48.902", "2.224", "2.469"],
            "address": {
                "city": "Paris",
                "state": "Île-de-France",
                "country": "France"
            }
        }]

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await geocode_address("Paris")

            assert result["success"] is True
            assert result["data"]["lat"] == 48.8566
            assert result["data"]["lon"] == 2.3522
            assert "Paris" in result["data"]["display_name"]
            assert result["metadata"]["source"] == "nominatim"
            assert "confidence" in result["metadata"]

    @pytest.mark.asyncio
    async def test_geocode_no_results(self):
        """Test geocoding when no results found (mocked)."""
        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = []

            result = await geocode_address("xyznonexistentplace123")

            assert result["success"] is False
            assert "no results" in result["error"].lower()


class TestReverseGeocode:
    """Tests for the reverse geocode tool."""

    @pytest.mark.asyncio
    async def test_reverse_geocode_invalid_lat(self):
        """Test reverse geocoding with invalid latitude."""
        result = await reverse_geocode_coords(100, 2.3522)

        assert result["success"] is False
        assert "latitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reverse_geocode_invalid_lon(self):
        """Test reverse geocoding with invalid longitude."""
        result = await reverse_geocode_coords(48.8566, 200)

        assert result["success"] is False
        assert "longitude" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_reverse_geocode_response_structure(self):
        """Test that reverse geocode returns correct structure (mocked)."""
        mock_response = {
            "display_name": "Eiffel Tower, Paris, France",
            "type": "attraction",
            "class": "tourism",
            "osm_type": "way",
            "osm_id": 123456,
            "boundingbox": ["48.857", "48.859", "2.293", "2.296"],
            "address": {
                "tourism": "Eiffel Tower",
                "road": "Avenue Gustave Eiffel",
                "city": "Paris",
                "state": "Île-de-France",
                "postcode": "75007",
                "country": "France",
                "country_code": "fr"
            }
        }

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await reverse_geocode_coords(48.8584, 2.2945)

            assert result["success"] is True
            assert "Eiffel Tower" in result["data"]["display_name"]
            assert result["data"]["structured"]["city"] == "Paris"
            assert result["metadata"]["source"] == "nominatim"

    @pytest.mark.asyncio
    async def test_reverse_geocode_error_response(self):
        """Test reverse geocoding when API returns error (mocked)."""
        mock_response = {
            "error": "Unable to geocode"
        }

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response

            result = await reverse_geocode_coords(0, 0)  # Middle of ocean

            assert result["success"] is False


class TestValidation:
    """Tests for coordinate validation."""

    @pytest.mark.asyncio
    async def test_lat_boundary_min(self):
        """Test latitude at minimum boundary."""
        result = await reverse_geocode_coords(-90, 0)
        # Should not fail validation (may fail for other reasons)
        assert "latitude" not in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_lat_boundary_max(self):
        """Test latitude at maximum boundary."""
        result = await reverse_geocode_coords(90, 0)
        assert "latitude" not in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_lon_boundary_min(self):
        """Test longitude at minimum boundary."""
        result = await reverse_geocode_coords(0, -180)
        assert "longitude" not in (result.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_lon_boundary_max(self):
        """Test longitude at maximum boundary."""
        result = await reverse_geocode_coords(0, 180)
        assert "longitude" not in (result.get("error") or "").lower()


class TestBatchGeocode:
    """Tests for the batch_geocode function."""

    @pytest.mark.asyncio
    async def test_batch_geocode_empty_list(self):
        """Test batch geocoding with empty list."""
        result = await batch_geocode([])

        assert result["success"] is False
        assert "empty" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_batch_geocode_too_many_addresses(self):
        """Test batch geocoding beyond the batch limit is rejected."""
        addresses = [f"Address {i}" for i in range(26)]
        result = await batch_geocode(addresses)

        assert result["success"] is False
        assert "too many" in result["error"].lower()
        assert "25" in result["error"]

    @pytest.mark.asyncio
    async def test_batch_geocode_valid_addresses(self):
        """Test batch geocoding with valid addresses (mocked)."""
        addresses = ["Paris, France", "London, UK", "Berlin, Germany"]

        mock_responses = [
            [{
                "lat": "48.8566",
                "lon": "2.3522",
                "display_name": "Paris, Île-de-France, France",
                "type": "city",
                "class": "place",
                "importance": 0.9,
                "osm_type": "relation",
                "osm_id": 7444,
                "boundingbox": ["48.815", "48.902", "2.224", "2.469"],
                "address": {"city": "Paris", "country": "France"}
            }],
            [{
                "lat": "51.5074",
                "lon": "-0.1278",
                "display_name": "London, England, UK",
                "type": "city",
                "class": "place",
                "importance": 0.9,
                "osm_type": "relation",
                "osm_id": 65606,
                "boundingbox": ["51.38", "51.69", "-0.35", "0.14"],
                "address": {"city": "London", "country": "United Kingdom"}
            }],
            [{
                "lat": "52.5200",
                "lon": "13.4050",
                "display_name": "Berlin, Germany",
                "type": "city",
                "class": "place",
                "importance": 0.9,
                "osm_type": "relation",
                "osm_id": 62422,
                "boundingbox": ["52.33", "52.68", "13.08", "13.76"],
                "address": {"city": "Berlin", "country": "Germany"}
            }]
        ]

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_responses

            result = await batch_geocode(addresses)

            assert result["success"] is True
            assert result["data"]["summary"]["total"] == 3
            assert result["data"]["summary"]["successful"] == 3
            assert result["data"]["summary"]["failed"] == 0
            assert len(result["data"]["results"]) == 3

            # Check first result
            first_result = result["data"]["results"][0]
            assert first_result["index"] == 0
            assert first_result["address"] == "Paris, France"
            assert first_result["result"]["success"] is True
            assert first_result["result"]["data"]["lat"] == 48.8566

    @pytest.mark.asyncio
    async def test_batch_geocode_deduplicates(self):
        """Duplicate addresses are geocoded only once but returned per index."""
        addresses = ["Paris, France", "Paris, France", "paris, france  "]
        mock_response = [{
            "lat": "48.8566", "lon": "2.3522",
            "display_name": "Paris, France", "type": "city", "class": "place",
            "importance": 0.9,
        }]

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_response
            result = await batch_geocode(addresses)

            assert result["success"] is True
            assert result["data"]["summary"]["total"] == 3
            assert result["data"]["summary"]["successful"] == 3
            assert result["data"]["summary"]["unique_geocoded"] == 1
            # Only one upstream call despite three (equivalent) addresses.
            assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_geocode_partial_failures(self):
        """Test batch geocoding with some addresses failing (mocked)."""
        addresses = ["Paris, France", "InvalidAddress123XYZ", "Berlin, Germany"]

        mock_responses = [
            [{
                "lat": "48.8566",
                "lon": "2.3522",
                "display_name": "Paris, Île-de-France, France",
                "type": "city",
                "class": "place",
                "importance": 0.9,
                "osm_type": "relation",
                "osm_id": 7444,
                "boundingbox": ["48.815", "48.902", "2.224", "2.469"],
                "address": {"city": "Paris", "country": "France"}
            }],
            [],  # No results for invalid address
            [{
                "lat": "52.5200",
                "lon": "13.4050",
                "display_name": "Berlin, Germany",
                "type": "city",
                "class": "place",
                "importance": 0.9,
                "osm_type": "relation",
                "osm_id": 62422,
                "boundingbox": ["52.33", "52.68", "13.08", "13.76"],
                "address": {"city": "Berlin", "country": "Germany"}
            }]
        ]

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.side_effect = mock_responses

            result = await batch_geocode(addresses)

            assert result["success"] is True  # Overall success if at least one succeeded
            assert result["data"]["summary"]["total"] == 3
            assert result["data"]["summary"]["successful"] == 2
            assert result["data"]["summary"]["failed"] == 1

            # Check that the failed address has an error
            second_result = result["data"]["results"][1]
            assert second_result["index"] == 1
            assert second_result["address"] == "InvalidAddress123XYZ"
            assert second_result["result"]["success"] is False
            assert "no results" in second_result["result"]["error"].lower()

    @pytest.mark.asyncio
    async def test_batch_geocode_all_failures(self):
        """Test batch geocoding when all addresses fail (mocked)."""
        addresses = ["Invalid1", "Invalid2"]

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = []  # No results for any address

            result = await batch_geocode(addresses)

            assert result["success"] is False
            assert "all addresses failed" in result["error"].lower()
            assert result["metadata"]["batch_size"] == 2

    @pytest.mark.asyncio
    async def test_batch_geocode_not_a_list(self):
        """Test batch geocoding with invalid input type."""
        result = await batch_geocode("not a list")  # type: ignore

        assert result["success"] is False
        assert "list" in result["error"].lower()


class TestPeliasGeocode:
    """Tests for Pelias geocoding provider."""

    @pytest.mark.asyncio
    async def test_pelias_geocode_invalid_provider(self):
        """Test geocoding with invalid provider name."""
        result = await geocode_address("Paris", provider="invalid")

        assert result["success"] is False
        assert "invalid provider" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_pelias_geocode_not_configured(self):
        """Test Pelias geocoding when not configured (falls back to Nominatim)."""
        mock_nominatim_response = [{
            "lat": "48.8566",
            "lon": "2.3522",
            "display_name": "Paris, France",
            "type": "city",
            "class": "place",
            "importance": 0.9,
            "osm_type": "relation",
            "osm_id": 7444,
            "address": {"city": "Paris", "country": "France"}
        }]

        with patch("locusync.tools.geocoding._nominatim_request", new_callable=AsyncMock) as mock:
            mock.return_value = mock_nominatim_response

            result = await geocode_address("Paris", provider="pelias")

            assert result["success"] is True
            assert result["metadata"]["source"] == "nominatim"  # Fell back to Nominatim

    @pytest.mark.asyncio
    async def test_pelias_geocode_success(self):
        """Test successful Pelias geocoding (mocked)."""
        mock_pelias_response = {
            "geocoding": {"version": "0.2"},
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [2.3522, 48.8566]
                },
                "properties": {
                    "gid": "whosonfirst:locality:101751119",
                    "layer": "locality",
                    "source": "whosonfirst",
                    "name": "Paris",
                    "label": "Paris, Île-de-France, France",
                    "confidence": 0.9,
                    "country": "France",
                    "region": "Île-de-France",
                    "locality": "Paris"
                }
            }]
        }

        with patch("locusync.tools.geocoding.get_config") as mock_config:
            mock_config.return_value = _create_pelias_config()
            with patch("locusync.tools.geocoding._pelias_geocode", new_callable=AsyncMock) as mock:
                mock.return_value = mock_pelias_response

                result = await geocode_address("Paris", provider="pelias")

                assert result["success"] is True
                assert result["data"]["lat"] == 48.8566
                assert result["data"]["lon"] == 2.3522
                assert "Paris" in result["data"]["display_name"]
                assert result["metadata"]["source"] == "pelias"
                assert result["metadata"]["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_pelias_geocode_no_results(self):
        """Test Pelias geocoding with no results (mocked)."""
        mock_pelias_response = {
            "geocoding": {"version": "0.2"},
            "type": "FeatureCollection",
            "features": []
        }

        with patch("locusync.tools.geocoding.get_config") as mock_config:
            mock_config.return_value = _create_pelias_config()
            with patch("locusync.tools.geocoding._pelias_geocode", new_callable=AsyncMock) as mock:
                mock.return_value = mock_pelias_response

                result = await geocode_address("nonexistent123", provider="pelias")

                assert result["success"] is False
                assert "no results" in result["error"].lower()
                assert result["metadata"]["source"] == "pelias"

    @pytest.mark.asyncio
    async def test_pelias_reverse_geocode_success(self):
        """Test successful Pelias reverse geocoding (mocked)."""
        mock_pelias_response = {
            "geocoding": {"version": "0.2"},
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [2.2945, 48.8584]
                },
                "properties": {
                    "gid": "openstreetmap:venue:way/5013364",
                    "layer": "venue",
                    "source": "openstreetmap",
                    "name": "Eiffel Tower",
                    "label": "Eiffel Tower, Paris, France",
                    "street": "Avenue Gustave Eiffel",
                    "locality": "Paris",
                    "region": "Île-de-France",
                    "postalcode": "75007",
                    "country": "France"
                }
            }]
        }

        with patch("locusync.tools.geocoding.get_config") as mock_config:
            mock_config.return_value = _create_pelias_config()
            with patch("locusync.tools.geocoding._pelias_reverse", new_callable=AsyncMock) as mock:
                mock.return_value = mock_pelias_response

                result = await reverse_geocode_coords(48.8584, 2.2945, provider="pelias")

                assert result["success"] is True
                assert "Eiffel Tower" in result["data"]["display_name"]
                assert result["data"]["structured"]["city"] == "Paris"
                assert result["metadata"]["source"] == "pelias"

    @pytest.mark.asyncio
    async def test_pelias_reverse_geocode_no_results(self):
        """Test Pelias reverse geocoding with no results (mocked)."""
        mock_pelias_response = {
            "geocoding": {"version": "0.2"},
            "type": "FeatureCollection",
            "features": []
        }

        with patch("locusync.tools.geocoding.get_config") as mock_config:
            mock_config.return_value = _create_pelias_config()
            with patch("locusync.tools.geocoding._pelias_reverse", new_callable=AsyncMock) as mock:
                mock.return_value = mock_pelias_response

                result = await reverse_geocode_coords(0, 0, provider="pelias")

                assert result["success"] is False
                assert "no address found" in result["error"].lower()
                assert result["metadata"]["source"] == "pelias"

    @pytest.mark.asyncio
    async def test_pelias_reverse_geocode_invalid_provider(self):
        """Test reverse geocoding with invalid provider name."""
        result = await reverse_geocode_coords(48.8566, 2.3522, provider="invalid")

        assert result["success"] is False
        assert "invalid provider" in result["error"].lower()
