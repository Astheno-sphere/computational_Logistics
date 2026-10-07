"""Tests for file I/O tools."""

import json
import os
import tempfile

import pytest

from locusync.tools.files import (
    _get_driver_for_path,
    read_geo_file,
    write_geo_file,
)


class TestGetDriverForPath:
    """Tests for driver detection."""

    def test_geojson_extension(self):
        """Test GeoJSON extension detection."""
        assert _get_driver_for_path("file.geojson") == "GeoJSON"
        assert _get_driver_for_path("file.json") == "GeoJSON"
        assert _get_driver_for_path("FILE.GEOJSON") == "GeoJSON"

    def test_shapefile_extension(self):
        """Test Shapefile extension detection."""
        assert _get_driver_for_path("file.shp") == "ESRI Shapefile"
        assert _get_driver_for_path("FILE.SHP") == "ESRI Shapefile"

    def test_geopackage_extension(self):
        """Test GeoPackage extension detection."""
        assert _get_driver_for_path("file.gpkg") == "GPKG"

    def test_unsupported_extension(self):
        """Test unsupported extension returns None."""
        assert _get_driver_for_path("file.txt") is None
        assert _get_driver_for_path("file.csv") is None
        assert _get_driver_for_path("file") is None


class TestReadGeoFile:
    """Tests for reading geospatial files."""

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        """Test reading a non-existent file inside the workspace."""
        missing = os.path.join(tempfile.gettempdir(), "locusync_does_not_exist.geojson")
        result = await read_geo_file(missing)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_unsupported_format(self):
        """Test reading unsupported format."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"not a geo file")
            temp_path = f.name

        try:
            result = await read_geo_file(temp_path)
            assert result["success"] is False
            assert "unsupported" in result["error"].lower()
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_read_valid_geojson(self):
        """Test reading a valid GeoJSON file."""
        geojson_content = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [2.3522, 48.8566]
                    },
                    "properties": {
                        "name": "Paris",
                        "population": 2161000
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-0.1278, 51.5074]
                    },
                    "properties": {
                        "name": "London",
                        "population": 8982000
                    }
                }
            ]
        }

        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
            json.dump(geojson_content, f)
            temp_path = f.name

        try:
            result = await read_geo_file(temp_path)
            assert result["success"] is True
            assert result["data"]["type"] == "FeatureCollection"
            assert result["data"]["feature_count"] == 2
            assert len(result["data"]["features"]) == 2
            assert result["metadata"]["driver"] == "GeoJSON"
            assert "geometry_types" in result["metadata"]
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_read_with_limit(self):
        """Test reading with feature limit."""
        geojson_content = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [i, i]},
                    "properties": {"id": i}
                }
                for i in range(10)
            ]
        }

        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
            json.dump(geojson_content, f)
            temp_path = f.name

        try:
            result = await read_geo_file(temp_path, limit=3)
            assert result["success"] is True
            assert result["data"]["feature_count"] == 3
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_read_empty_file(self):
        """Test reading file with no features."""
        geojson_content = {
            "type": "FeatureCollection",
            "features": []
        }

        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
            json.dump(geojson_content, f)
            temp_path = f.name

        try:
            result = await read_geo_file(temp_path)
            assert result["success"] is False
            assert "no features" in result["error"].lower()
        finally:
            os.unlink(temp_path)


class TestWriteGeoFile:
    """Tests for writing geospatial files."""

    @pytest.mark.asyncio
    async def test_invalid_driver(self):
        """Test with invalid driver."""
        features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {}
                }
            ]
        }

        result = await write_geo_file(features, "/tmp/test.geojson", driver="InvalidDriver")
        assert result["success"] is False
        assert "invalid" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_invalid_features_type(self):
        """Test with non-dict features."""
        result = await write_geo_file("not a dict", "/tmp/test.geojson")
        assert result["success"] is False
        assert "geojson" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_not_feature_collection(self):
        """Test with wrong GeoJSON type."""
        features = {
            "type": "Feature",  # Should be FeatureCollection
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {}
        }

        result = await write_geo_file(features, "/tmp/test.geojson")
        assert result["success"] is False
        assert "featurecollection" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_empty_features(self):
        """Test with empty feature collection."""
        features = {
            "type": "FeatureCollection",
            "features": []
        }

        result = await write_geo_file(features, "/tmp/test.geojson")
        assert result["success"] is False
        assert "no features" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_write_valid_geojson(self):
        """Test writing valid GeoJSON."""
        features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]},
                    "properties": {"name": "Paris"}
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-0.1278, 51.5074]},
                    "properties": {"name": "London"}
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.geojson")

            result = await write_geo_file(features, output_path, driver="GeoJSON")

            assert result["success"] is True
            assert result["data"]["feature_count"] == 2
            assert result["data"]["driver"] == "GeoJSON"
            assert os.path.exists(output_path)

            # Verify written content
            with open(output_path) as f:
                written = json.load(f)
                assert written["type"] == "FeatureCollection"
                assert len(written["features"]) == 2

    @pytest.mark.asyncio
    async def test_write_creates_parent_directory(self):
        """Test that write creates parent directories."""
        features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [0, 0]},
                    "properties": {}
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "subdir", "nested", "output.geojson")

            result = await write_geo_file(features, output_path)

            assert result["success"] is True
            assert os.path.exists(output_path)

    @pytest.mark.asyncio
    async def test_write_shapefile(self):
        """Test writing Shapefile."""
        features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]},
                    "properties": {"name": "Paris"}
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.shp")

            result = await write_geo_file(features, output_path, driver="ESRI Shapefile")

            assert result["success"] is True
            assert result["data"]["driver"] == "ESRI Shapefile"
            assert os.path.exists(output_path)

    @pytest.mark.asyncio
    async def test_write_geopackage(self):
        """Test writing GeoPackage."""
        features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]},
                    "properties": {"name": "Paris"}
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "output.gpkg")

            result = await write_geo_file(features, output_path, driver="GPKG")

            assert result["success"] is True
            assert result["data"]["driver"] == "GPKG"
            assert os.path.exists(output_path)


class TestRoundTrip:
    """Tests for read/write round-trip."""

    @pytest.mark.asyncio
    async def test_geojson_round_trip(self):
        """Test reading back written GeoJSON."""
        original_features = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]},
                    "properties": {"name": "Paris", "population": 2161000}
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
                    },
                    "properties": {"name": "Square"}
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "roundtrip.geojson")

            # Write
            write_result = await write_geo_file(original_features, output_path)
            assert write_result["success"] is True

            # Read back
            read_result = await read_geo_file(output_path)
            assert read_result["success"] is True
            assert read_result["data"]["feature_count"] == 2

            # Verify geometry types preserved
            geom_types = read_result["metadata"]["geometry_types"]
            assert "Point" in geom_types
            assert "Polygon" in geom_types
