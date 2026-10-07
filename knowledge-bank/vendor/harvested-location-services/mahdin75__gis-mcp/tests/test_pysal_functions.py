"""Tests for PySAL functions."""
import pytest
import sys
import os
from pathlib import Path
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from gis_mcp.mcp import gis_mcp
from fastmcp import Client
import json
from tests.test_helpers import get_result_data


@pytest.fixture
def sample_shapefile_with_data(temp_dir):
    """Create a sample shapefile with data for PySAL testing."""
    # Create a grid of points with values
    points = []
    values = []
    ids = []
    for i in range(5):
        for j in range(5):
            points.append(Point(i, j))
            values.append(i * 5 + j)  # Unique values
            ids.append(i * 5 + j)
    
    gdf = gpd.GeoDataFrame(
        {
            'id': ids,
            'LAND_USE': values,
            'VALUE': [v * 10 for v in values]
        },
        geometry=points,
        crs='EPSG:4326'
    )
    test_file = os.path.join(temp_dir, 'test_data.shp')
    gdf.to_file(test_file)
    return gdf, test_file


class TestSpatialAutocorrelation:
    """Test spatial autocorrelation functions."""
    
    @pytest.mark.asyncio
    async def test_morans_i(self, sample_shapefile_with_data):
        """Test Moran's I global autocorrelation."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("morans_i", {
                "shapefile_path": file_path,
                "dependent_var": "LAND_USE",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
            assert "morans_i" in result_data["result"]
    
    @pytest.mark.asyncio
    async def test_gearys_c(self, sample_shapefile_with_data):
        """Test Geary's C global autocorrelation."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("gearys_c", {
                "shapefile_path": file_path,
                "dependent_var": "LAND_USE",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
            assert "gearys_c" in result_data["result"]
    
    @pytest.mark.asyncio
    async def test_gamma_statistic(self, sample_shapefile_with_data):
        """Test Gamma statistic."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("gamma_statistic", {
                "shapefile_path": file_path,
                "dependent_var": "LAND_USE",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
    
    @pytest.mark.asyncio
    async def test_getis_ord_g(self, sample_shapefile_with_data):
        """Test Getis-Ord G global statistic."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("getis_ord_g", {
                "shapefile_path": file_path,
                "dependent_var": "LAND_USE",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
            assert "getis_ord_g" in result_data["result"]


class TestLocalStatistics:
    """Test local spatial statistics."""
    
    @pytest.mark.asyncio
    async def test_moran_local(self, sample_shapefile_with_data):
        """Test local Moran's I."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("moran_local", {
                "shapefile_path": file_path,
                "dependent_var": "LAND_USE",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
    
    @pytest.mark.asyncio
    async def test_getis_ord_g_local(self, sample_shapefile_with_data):
        """Test local Getis-Ord G*."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("getis_ord_g_local", {
                "shapefile_path": file_path,
                "dependent_var": "LAND_USE",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
    
    @pytest.mark.asyncio
    async def test_join_counts_local(self, sample_shapefile_with_data):
        """Test local join counts."""
        _, file_path = sample_shapefile_with_data
        # Create binary variable
        gdf = gpd.read_file(file_path)
        gdf['BINARY'] = (gdf['LAND_USE'] > 10).astype(int)
        file_path_binary = file_path.replace('.shp', '_binary.shp')
        gdf.to_file(file_path_binary)
        
        async with Client(gis_mcp) as client:
            result = await client.call_tool("join_counts_local", {
                "shapefile_path": file_path_binary,
                "dependent_var": "BINARY",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data


class TestGlobalStatistics:
    """Test global spatial statistics."""
    
    @pytest.mark.asyncio
    async def test_join_counts(self, sample_shapefile_with_data):
        """Test binary join counts."""
        _, file_path = sample_shapefile_with_data
        # Create binary variable
        gdf = gpd.read_file(file_path)
        gdf['BINARY'] = (gdf['LAND_USE'] > 10).astype(int)
        file_path_binary = file_path.replace('.shp', '_binary2.shp')
        gdf.to_file(file_path_binary)
        
        async with Client(gis_mcp) as client:
            result = await client.call_tool("join_counts", {
                "shapefile_path": file_path_binary,
                "dependent_var": "BINARY",
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
    
    @pytest.mark.asyncio
    async def test_adbscan(self, sample_shapefile_with_data):
        """Test adaptive DBSCAN clustering."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("adbscan", {
                "shapefile_path": file_path,
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0,
                "eps": 0.5,
                "min_samples": 3
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data


class TestSpatialWeights:
    """Test spatial weights creation."""
    
    @pytest.mark.asyncio
    async def test_weights_from_shapefile(self, sample_shapefile_with_data):
        """Test creating weights from shapefile."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("weights_from_shapefile", {
                "shapefile_path": file_path,
                "contiguity": "queen"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "weights_info" in result_data
    
    @pytest.mark.asyncio
    async def test_distance_band_weights(self, sample_shapefile_with_data):
        """Test distance band weights."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("distance_band_weights", {
                "data_path": file_path,
                "threshold": 2.0,
                "binary": True
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "weights_info" in result_data
    
    @pytest.mark.asyncio
    async def test_knn_weights(self, sample_shapefile_with_data):
        """Test K-nearest neighbors weights."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("knn_weights", {
                "data_path": file_path,
                "k": 4
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "weights_info" in result_data
    
    @pytest.mark.asyncio
    async def test_build_transform_and_save_weights(self, sample_shapefile_with_data, temp_dir):
        """Test building, transforming, and saving weights."""
        _, file_path = sample_shapefile_with_data
        output_path = os.path.join(temp_dir, "weights.gal")
        async with Client(gis_mcp) as client:
            result = await client.call_tool("build_transform_and_save_weights", {
                "data_path": file_path,
                "method": "queen",
                "output_path": output_path
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert os.path.exists(output_path)
    
    @pytest.mark.asyncio
    async def test_build_and_transform_weights(self, sample_shapefile_with_data):
        """Test building and transforming weights."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("build_and_transform_weights", {
                "data_path": file_path,
                "method": "queen"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "weights_info" in result_data


class TestSpatialRegression:
    """Test spatial regression functions."""
    
    @pytest.mark.asyncio
    async def test_ols_with_spatial_diagnostics_safe(self, sample_shapefile_with_data):
        """Test OLS regression with spatial diagnostics."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("ols_with_spatial_diagnostics_safe", {
                "data_path": file_path,
                "y_field": "VALUE",
                "x_fields": ["LAND_USE"]
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "regression_results" in result_data


class TestSpatialTemporalAnalysis:
    """Test spatial-temporal analysis functions."""
    
    @pytest.mark.asyncio
    async def test_spatial_markov(self, sample_shapefile_with_data):
        """Test spatial Markov analysis."""
        _, file_path = sample_shapefile_with_data
        # Create time series data
        gdf = gpd.read_file(file_path)
        gdf['TIME1'] = gdf['LAND_USE']
        gdf['TIME2'] = gdf['LAND_USE'] + 1
        gdf['TIME3'] = gdf['LAND_USE'] + 2
        file_path_ts = file_path.replace('.shp', '_ts.shp')
        gdf.to_file(file_path_ts)
        
        async with Client(gis_mcp) as client:
            result = await client.call_tool("spatial_markov", {
                "shapefile_path": file_path_ts,
                "value_columns": ["TIME1", "TIME2", "TIME3"],
                "target_crs": "EPSG:4326"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
    
    @pytest.mark.asyncio
    async def test_dynamic_lisa(self, sample_shapefile_with_data):
        """Test dynamic LISA analysis."""
        _, file_path = sample_shapefile_with_data
        # Create two time periods
        gdf = gpd.read_file(file_path)
        gdf['TIME0'] = gdf['LAND_USE']
        gdf['TIME1'] = gdf['LAND_USE'] + 1
        file_path_ts = file_path.replace('.shp', '_ts2.shp')
        gdf.to_file(file_path_ts)
        
        async with Client(gis_mcp) as client:
            result = await client.call_tool("dynamic_lisa", {
                "shapefile_path": file_path_ts,
                "value_columns": ["TIME0", "TIME1"],
                "target_crs": "EPSG:4326"
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data


class TestSpatialLagModel:
    """Test spatial lag model."""
    
    @pytest.mark.asyncio
    async def test_gm_lag(self, sample_shapefile_with_data):
        """Test GM_Lag spatial lag model."""
        _, file_path = sample_shapefile_with_data
        async with Client(gis_mcp) as client:
            result = await client.call_tool("gm_lag", {
                "shapefile_path": file_path,
                "y_col": "VALUE",
                "x_cols": ["LAND_USE"],
                "target_crs": "EPSG:4326",
                "distance_threshold": 2.0
            })
            result_data = get_result_data(result)
            assert result_data["status"] == "success"
            assert "result" in result_data
