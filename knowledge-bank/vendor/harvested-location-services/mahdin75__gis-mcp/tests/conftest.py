"""Pytest configuration and shared fixtures."""
import pytest
import sys
import tempfile
import os
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Point, Polygon, LineString
import geopandas as gpd
from fastmcp import Client

# Add src to path for imports (for local testing without installation)
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import the MCP server instance
from gis_mcp.mcp import gis_mcp

@pytest.fixture
async def mcp_client():
    """Create an MCP client for testing tools."""
    async with Client(gis_mcp) as client:
        yield client


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_point():
    """Create a sample point geometry."""
    return Point(0, 0)


@pytest.fixture
def sample_polygon():
    """Create a sample polygon geometry."""
    return Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])


@pytest.fixture
def sample_linestring():
    """Create a sample linestring geometry."""
    return LineString([(0, 0), (1, 1), (2, 0)])


@pytest.fixture
def sample_geodataframe(temp_dir):
    """Create a sample GeoDataFrame for testing."""
    gdf = gpd.GeoDataFrame(
        {
            'id': [1, 2, 3],
            'name': ['A', 'B', 'C'],
            'value': [10, 20, 30]
        },
        geometry=[
            Point(0, 0),
            Point(1, 1),
            Point(2, 2)
        ],
        crs='EPSG:4326'
    )
    # Save to temporary file
    test_file = os.path.join(temp_dir, 'test.shp')
    gdf.to_file(test_file)
    return gdf, test_file


@pytest.fixture
def sample_raster(temp_dir):
    """Create a sample raster file for testing."""
    import rasterio
    from rasterio.transform import from_bounds
    
    # Create a simple 10x10 raster
    data = np.random.randint(0, 255, (1, 10, 10), dtype=np.uint8)
    transform = from_bounds(0, 0, 10, 10, 10, 10)
    
    test_file = os.path.join(temp_dir, 'test_raster.tif')
    # Use string CRS to avoid PROJ database conflicts
    with rasterio.open(
        test_file,
        'w',
        driver='GTiff',
        height=10,
        width=10,
        count=1,
        dtype=data.dtype,
        crs='EPSG:4326',  # Use string instead of CRS.from_epsg() to avoid PROJ conflicts
        transform=transform,
        nodata=0
    ) as dst:
        dst.write(data)
    
    return test_file


@pytest.fixture
def sample_polygon_geodataframe(temp_dir):
    """Create a sample polygon GeoDataFrame for testing."""
    gdf = gpd.GeoDataFrame(
        {
            'id': [1, 2],
            'name': ['Polygon1', 'Polygon2'],
            'value': [100, 200]
        },
        geometry=[
            Polygon([(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]),
            Polygon([(3, 3), (5, 3), (5, 5), (3, 5), (3, 3)])
        ],
        crs='EPSG:4326'
    )
    test_file = os.path.join(temp_dir, 'test_polygons.shp')
    gdf.to_file(test_file)
    return gdf, test_file
