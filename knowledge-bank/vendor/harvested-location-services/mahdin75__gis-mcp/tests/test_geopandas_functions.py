"""Tests for GeoPandas functions."""
import pytest
import sys
import os
import json
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point, Polygon
from fastmcp import Client

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gis_mcp.mcp import gis_mcp
from tests.test_helpers import get_result_data


class TestIOOperations:
    """Test I/O operations."""
    
    @pytest.mark.asyncio
    async def test_read_file_gpd(self, sample_geodataframe):
        """Test reading a geospatial file."""
        _, file_path = sample_geodataframe
        async with Client(gis_mcp) as client:
            result = await client.call_tool("read_file_gpd", {"file_path": file_path})
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "columns" in result_data
            assert "num_rows" in result_data
            assert "crs" in result_data
            assert result_data["num_rows"] == 3
    
    @pytest.mark.asyncio
    async def test_write_file_gpd(self, sample_geodataframe, temp_dir):
        """Test writing a geospatial file."""
        _, input_path = sample_geodataframe
        output_path = os.path.join(temp_dir, "output.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("write_file_gpd", {
                "gdf_path": input_path,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert os.path.exists(output_path)


class TestJoinAndMergeOperations:
    """Test join and merge operations."""
    
    @pytest.mark.asyncio
    async def test_append_gpd(self, sample_geodataframe, temp_dir):
        """Test appending GeoDataFrames."""
        _, file1 = sample_geodataframe
        # Create second file
        gdf2 = gpd.GeoDataFrame(
            {'id': [4, 5], 'name': ['D', 'E'], 'value': [40, 50]},
            geometry=[Point(3, 3), Point(4, 4)],
            crs='EPSG:4326'
        )
        file2 = os.path.join(temp_dir, "test2.shp")
        gdf2.to_file(file2)
        
        output_path = os.path.join(temp_dir, "appended.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("append_gpd", {
                "shapefile1_path": file1,
                "shapefile2_path": file2,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert os.path.exists(output_path)
    
    @pytest.mark.asyncio
    async def test_merge_gpd(self, sample_geodataframe, temp_dir):
        """Test merging GeoDataFrames."""
        _, file1 = sample_geodataframe
        # Create second file with matching id
        gdf2 = gpd.GeoDataFrame(
            {'id': [1, 2], 'extra': ['X', 'Y']},
            geometry=[Point(0, 0), Point(1, 1)],
            crs='EPSG:4326'
        )
        file2 = os.path.join(temp_dir, "test2.shp")
        gdf2.to_file(file2)
        
        output_path = os.path.join(temp_dir, "merged.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("merge_gpd", {
                "shapefile1_path": file1,
                "shapefile2_path": file2,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert os.path.exists(output_path)
    
    @pytest.mark.asyncio
    async def test_overlay_gpd(self, sample_polygon_geodataframe, temp_dir):
        """Test spatial overlay operation."""
        _, file1 = sample_polygon_geodataframe
        # Create second polygon file
        gdf2 = gpd.GeoDataFrame(
            {'id': [1]},
            geometry=[Polygon([(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)])],
            crs='EPSG:4326'
        )
        file2 = os.path.join(temp_dir, "overlay.shp")
        gdf2.to_file(file2)
        
        output_path = os.path.join(temp_dir, "overlay_result.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("overlay_gpd", {
                "gdf1_path": file1,
                "gdf2_path": file2,
                "how": "intersection",
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_dissolve_gpd(self, sample_polygon_geodataframe, temp_dir):
        """Test dissolve operation."""
        _, file_path = sample_polygon_geodataframe
        output_path = os.path.join(temp_dir, "dissolved.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("dissolve_gpd", {
                "gdf_path": file_path,
                "by": "name",
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_explode_gpd(self, sample_polygon_geodataframe, temp_dir):
        """Test explode operation."""
        _, file_path = sample_polygon_geodataframe
        output_path = os.path.join(temp_dir, "exploded.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("explode_gpd", {
                "gdf_path": file_path,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"


class TestSpatialOperations:
    """Test spatial operations."""
    
    @pytest.mark.asyncio
    async def test_clip_vector(self, sample_geodataframe, sample_polygon_geodataframe, temp_dir):
        """Test vector clipping."""
        _, points_file = sample_geodataframe
        _, clip_file = sample_polygon_geodataframe
        output_path = os.path.join(temp_dir, "clipped.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("clip_vector", {
                "gdf_path": points_file,
                "clip_path": clip_file,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_sjoin_gpd(self, sample_geodataframe, sample_polygon_geodataframe, temp_dir):
        """Test spatial join."""
        _, points_file = sample_geodataframe
        _, polygons_file = sample_polygon_geodataframe
        output_path = os.path.join(temp_dir, "sjoined.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("sjoin_gpd", {
                "left_path": points_file,
                "right_path": polygons_file,
                "how": "inner",
                "predicate": "intersects",
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_sjoin_nearest_gpd(self, sample_geodataframe, temp_dir):
        """Test nearest neighbor spatial join."""
        _, file1 = sample_geodataframe
        # Create second file
        gdf2 = gpd.GeoDataFrame(
            {'id': [10, 11], 'name': ['Target1', 'Target2']},
            geometry=[Point(0.5, 0.5), Point(1.5, 1.5)],
            crs='EPSG:4326'
        )
        file2 = os.path.join(temp_dir, "targets.shp")
        gdf2.to_file(file2)
        
        output_path = os.path.join(temp_dir, "nearest.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("sjoin_nearest_gpd", {
                "left_path": file1,
                "right_path": file2,
                "how": "left",
                "max_distance": 100000,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_point_in_polygon(self, sample_geodataframe, sample_polygon_geodataframe, temp_dir):
        """Test point in polygon operation."""
        _, points_file = sample_geodataframe
        _, polygons_file = sample_polygon_geodataframe
        output_path = os.path.join(temp_dir, "point_in_poly.shp")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("point_in_polygon", {
                "points_path": points_file,
                "polygons_path": polygons_file,
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
