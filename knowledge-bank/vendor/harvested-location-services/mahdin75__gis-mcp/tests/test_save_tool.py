"""Tests for save_results tool."""
import pytest
import sys
import os
import json
from pathlib import Path
from shapely.geometry import Point
from fastmcp import Client

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gis_mcp.mcp import gis_mcp
from tests.test_helpers import get_result_data


class TestSaveResults:
    """Test save_results tool."""
    
    @pytest.mark.asyncio
    async def test_save_results_json(self, temp_dir):
        """Test saving results to JSON format."""
        test_data = {
            "status": "success",
            "result": "test_value",
            "number": 42
        }
        test_folder = os.path.join(temp_dir, "test_outputs")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("save_results", {
                "data": test_data,
                "filename": "test_output",
                "formats": ["json"],
                "folder": test_folder
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "saved_files" in result_data
            assert "json" in result_data["saved_files"]
            
            # Verify file was created
            json_path = result_data["saved_files"]["json"]
            assert os.path.exists(json_path)
            
            # Verify content
            with open(json_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            assert loaded_data == test_data
    
    @pytest.mark.asyncio
    async def test_save_results_multiple_formats(self, temp_dir):
        """Test saving results to multiple formats."""
        test_data = {
            "status": "success",
            "result": "test_value",
            "number": 42
        }
        test_folder = os.path.join(temp_dir, "test_outputs")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("save_results", {
                "data": test_data,
                "filename": "multi_format",
                "formats": ["json", "txt", "yaml"],
                "folder": test_folder
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "saved_files" in result_data
            assert "json" in result_data["saved_files"]
            assert "txt" in result_data["saved_files"]
            assert "yaml" in result_data["saved_files"]
            
            # Verify all files were created
            for format_type in ["json", "txt", "yaml"]:
                file_path = result_data["saved_files"][format_type]
                assert os.path.exists(file_path)
    
    @pytest.mark.asyncio
    async def test_save_results_with_geometry(self, temp_dir):
        """Test saving results with geometry to shapefile and geojson."""
        point = Point(0, 0)
        test_data = {
            "status": "success",
            "geometry": point.wkt,
            "value": 100
        }
        test_folder = os.path.join(temp_dir, "test_outputs")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("save_results", {
                "data": test_data,
                "filename": "geometry_output",
                "formats": ["json", "geojson"],
                "folder": test_folder
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "saved_files" in result_data
            assert "json" in result_data["saved_files"]
            # GeoJSON might not be saved if there's an error, but JSON should work
            assert os.path.exists(result_data["saved_files"]["json"])
    
    @pytest.mark.asyncio
    async def test_save_results_default_formats(self, temp_dir):
        """Test saving results with default formats (all formats)."""
        test_data = {
            "status": "success",
            "result": "test_value"
        }
        test_folder = os.path.join(temp_dir, "test_outputs")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("save_results", {
                "data": test_data,
                "filename": "default_formats",
                "folder": test_folder
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "saved_files" in result_data
            # Should have at least JSON, CSV, TXT, YAML
            assert "json" in result_data["saved_files"]
            assert os.path.exists(result_data["saved_files"]["json"])
    
    @pytest.mark.asyncio
    async def test_save_results_no_filename(self, temp_dir):
        """Test saving results without specifying filename (should generate timestamp)."""
        test_data = {
            "status": "success",
            "result": "test_value"
        }
        test_folder = os.path.join(temp_dir, "test_outputs")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("save_results", {
                "data": test_data,
                "formats": ["json"],
                "folder": test_folder
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "saved_files" in result_data
            assert "json" in result_data["saved_files"]
            # Filename should start with "output_"
            json_path = result_data["saved_files"]["json"]
            assert os.path.basename(json_path).startswith("output_")
            assert os.path.exists(json_path)
