"""Tests for utility functions."""

from locusync.utils import (
    format_distance,
    format_duration,
    make_error_response,
    make_success_response,
    validate_coordinates,
)


class TestResponseHelpers:
    """Tests for response helper functions."""

    def test_success_response(self):
        """Test creating a success response."""
        data = {"key": "value"}
        metadata = {"source": "test"}

        result = make_success_response(data, metadata)

        assert result["success"] is True
        assert result["data"] == data
        assert result["metadata"] == metadata
        assert result["error"] is None

    def test_success_response_no_metadata(self):
        """Test success response without metadata."""
        data = {"key": "value"}

        result = make_success_response(data)

        assert result["success"] is True
        assert result["data"] == data
        assert result["metadata"] is None

    def test_error_response(self):
        """Test creating an error response."""
        error = "Something went wrong"
        metadata = {"code": 500}

        result = make_error_response(error, metadata)

        assert result["success"] is False
        assert result["data"] is None
        assert result["error"] == error
        assert result["metadata"] == metadata

    def test_error_response_no_metadata(self):
        """Test error response without metadata."""
        error = "Something went wrong"

        result = make_error_response(error)

        assert result["success"] is False
        assert result["error"] == error
        assert result["metadata"] is None


class TestValidateCoordinates:
    """Tests for coordinate validation."""

    def test_valid_coordinates(self):
        """Test with valid coordinates."""
        is_valid, error = validate_coordinates(48.8566, 2.3522)
        assert is_valid is True
        assert error is None

    def test_invalid_lat_too_high(self):
        """Test with latitude too high."""
        is_valid, error = validate_coordinates(91, 0)
        assert is_valid is False
        assert "latitude" in error.lower()

    def test_invalid_lat_too_low(self):
        """Test with latitude too low."""
        is_valid, error = validate_coordinates(-91, 0)
        assert is_valid is False
        assert "latitude" in error.lower()

    def test_invalid_lon_too_high(self):
        """Test with longitude too high."""
        is_valid, error = validate_coordinates(0, 181)
        assert is_valid is False
        assert "longitude" in error.lower()

    def test_invalid_lon_too_low(self):
        """Test with longitude too low."""
        is_valid, error = validate_coordinates(0, -181)
        assert is_valid is False
        assert "longitude" in error.lower()

    def test_boundary_values(self):
        """Test with boundary values."""
        # All these should be valid
        assert validate_coordinates(90, 180)[0] is True
        assert validate_coordinates(-90, -180)[0] is True
        assert validate_coordinates(0, 0)[0] is True


class TestFormatDistance:
    """Tests for distance formatting."""

    def test_format_distance_meters(self):
        """Test distance formatting."""
        result = format_distance(1609.344)  # 1 mile in meters

        assert result["meters"] == 1609.34
        assert result["kilometers"] == 1.609
        assert result["miles"] == 1.0
        assert "feet" in result

    def test_format_distance_zero(self):
        """Test formatting zero distance."""
        result = format_distance(0)

        assert result["meters"] == 0
        assert result["kilometers"] == 0
        assert result["miles"] == 0

    def test_format_distance_large(self):
        """Test formatting large distance."""
        result = format_distance(1_000_000)  # 1000 km

        assert result["kilometers"] == 1000


class TestFormatDuration:
    """Tests for duration formatting."""

    def test_format_duration_seconds(self):
        """Test duration formatting."""
        result = format_duration(3600)  # 1 hour

        assert result["seconds"] == 3600
        assert result["minutes"] == 60
        assert result["hours"] == 1

    def test_format_duration_zero(self):
        """Test formatting zero duration."""
        result = format_duration(0)

        assert result["seconds"] == 0
        assert result["minutes"] == 0
        assert result["hours"] == 0
