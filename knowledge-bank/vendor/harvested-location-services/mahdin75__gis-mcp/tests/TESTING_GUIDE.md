# Testing Guide for GIS MCP Server

## Issue: FunctionTool is not callable

The tests are currently failing because FastMCP wraps functions with `@tool()` decorator, which creates `FunctionTool` objects that are not directly callable.

## Solution: Use FastMCP Client Pattern

According to the [FastMCP testing documentation](https://mcpcat.io/guides/writing-unit-tests-mcp-servers/), tests should use the `Client` class to call tools through the MCP protocol.

## Pattern to Follow

### Before (doesn't work):

```python
from gis_mcp import shapely_functions

def test_buffer():
    result = shapely_functions.buffer(point.wkt, distance=10.0)  # ❌ TypeError
```

### After (correct pattern):

```python
import pytest
import json
from fastmcp import Client
from gis_mcp.mcp import gis_mcp

@pytest.mark.asyncio
async def test_buffer():
    point = Point(0, 0)
    async with Client(gis_mcp) as client:
        result = await client.call_tool("buffer", {
            "geometry": point.wkt,
            "distance": 10.0
        })
        result_data = json.loads(result[0].text)
        assert result_data["status"] == "success"
```

## Helper Function

A helper function is available in `test_helpers.py`:

```python
from tests.test_helpers import call_tool

@pytest.mark.asyncio
async def test_buffer():
    point = Point(0, 0)
    result = await call_tool("buffer", geometry=point.wkt, distance=10.0)
    assert result["status"] == "success"
```

## Converting Existing Tests

1. Add `@pytest.mark.asyncio` decorator to test functions
2. Make test functions `async`
3. Replace direct function calls with `Client` pattern or use `call_tool` helper
4. Parse JSON result: `json.loads(result[0].text)`

## Rasterio CRS Fix

For rasterio tests, use `rasterio.crs.CRS.from_epsg(4326)` instead of `'EPSG:4326'`:

```python
import rasterio.crs

with rasterio.open(
    test_file,
    'w',
    crs=rasterio.crs.CRS.from_epsg(4326),  # ✅ Correct
    # ... other params
) as dst:
    dst.write(data)
```

## Next Steps

All test files need to be updated to use the async Client pattern. This is a systematic refactoring that should be done file by file.
