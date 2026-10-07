# GIS MCP Server Test Suite

This directory contains comprehensive tests for the GIS MCP Server, verifying the functionality of all major libraries.

## Test Structure

The test suite is organized by library:

- `test_shapely_functions.py` - Tests for Shapely geometric operations (29 functions)
- `test_pyproj_functions.py` - Tests for PyProj coordinate transformations (13 functions)
- `test_geopandas_functions.py` - Tests for GeoPandas vector operations (13 functions)
- `test_rasterio_functions.py` - Tests for Rasterio raster operations (20 functions)
- `test_pysal_functions.py` - Tests for PySAL spatial analysis (18 functions)

## Running Tests

### Run all tests:

```bash
pytest tests/
```

### Run tests for a specific library:

```bash
pytest tests/test_shapely_functions.py
pytest tests/test_pyproj_functions.py
pytest tests/test_geopandas_functions.py
pytest tests/test_rasterio_functions.py
pytest tests/test_pysal_functions.py
```

### Run with coverage:

```bash
pytest tests/ --cov=src/gis_mcp --cov-report=html
```

### Run specific test class:

```bash
pytest tests/test_shapely_functions.py::TestBasicGeometricOperations
```

### Run specific test:

```bash
pytest tests/test_shapely_functions.py::TestBasicGeometricOperations::test_buffer
```

## Test Coverage

The test suite aims to verify:

1. **Functionality**: All functions execute without errors
2. **Return Values**: Functions return expected data structures
3. **Edge Cases**: Functions handle edge cases appropriately
4. **Error Handling**: Functions handle errors gracefully

## Before Pushing Code

**Important**: Always run tests before pushing code to ensure all functionality works correctly:

```bash
# Run all tests
pytest tests/

# Or run with verbose output to see detailed results
pytest tests/ -v
```

This helps catch any issues early and ensures code quality.

## Adding New Tests

When adding new functions to the GIS MCP Server:

1. Add tests to the appropriate test file
2. Follow the existing test structure and naming conventions
3. Ensure tests cover both success and error cases
4. Use fixtures from `conftest.py` when possible
5. Run tests locally before submitting PRs
