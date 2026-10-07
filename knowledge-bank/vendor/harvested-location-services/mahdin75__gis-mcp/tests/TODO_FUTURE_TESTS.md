# TODO: Future Test Implementations

This document outlines test suites that should be implemented in the future to complete comprehensive testing coverage for the GIS MCP Server.

## Data Module Tests

### Administrative Boundaries Functions
- **File**: `tests/test_administrative_boundaries.py`
- **Functions to test**:
  - `download_boundaries` - Test downloading GADM administrative boundaries
    - Test with different regions
    - Test with different administrative levels
    - Test file saving functionality
    - Test error handling for invalid regions

### Climate Data Functions
- **File**: `tests/test_climate.py`
- **Functions to test**:
  - `download_climate_data` - Test downloading climate data (ERA5 or other CDS datasets)
    - Test with different datasets
    - Test date range specifications
    - Test area of interest (bbox) specifications
    - Test authentication and API key handling
    - Test error handling for invalid requests

### Ecology Data Functions
- **File**: `tests/test_ecology.py`
- **Functions to test**:
  - `get_species_info` - Test retrieving taxonomic information
    - Test with valid species names
    - Test with invalid species names
    - Test response structure validation
  - `download_species_occurrences` - Test downloading occurrence records
    - Test with different species
    - Test limit parameter
    - Test file saving functionality
    - Test error handling

### Movement Data Functions
- **File**: `tests/test_movement.py`
- **Functions to test**:
  - `download_street_network` - Test downloading street networks via OSMnx
    - Test with different place names
    - Test with different network types (drive, walk, bike, all)
    - Test custom filter functionality
    - Test GraphML file saving
    - Test error handling for invalid places
  - `calculate_shortest_path` - Test shortest path calculation
    - Test with valid origin/destination pairs
    - Test with invalid coordinates
    - Test path result validation

### Land Cover Data Functions
- **File**: `tests/test_land_cover.py`
- **Functions to test**:
  - `download_worldcover` - Test downloading ESA WorldCover
    - Test with different years
    - Test with bounding box
    - Test crop and reprojection options
    - Test file saving
  - `compute_s2_ndvi` - Test NDVI computation from Sentinel-2
    - Test with different date ranges
    - Test cloud cover filtering
    - Test bounding box and geometry specifications
    - Test crop and reprojection

### Satellite Imagery Functions
- **File**: `tests/test_satellite_imagery.py`
- **Functions to test**:
  - `download_satellite_imagery` - Test downloading and stacking bands from STAC
    - Test with different collections (Sentinel-2, Landsat)
    - Test with different band combinations
    - Test date range specifications
    - Test cloud cover filtering
    - Test crop and reprojection options
    - Test authentication for Planetary Computer

## Visualization Module Tests

### Static Map Functions
- **File**: `tests/test_map_tool.py`
- **Functions to test**:
  - `create_map` - Test static map generation
    - Test with different layer types (shapefiles, rasters, WKT, coordinates)
    - Test with multiple layers
    - Test different output formats (PNG, PDF, JPG)
    - Test styling options
    - Test legend and grid options
    - Test error handling for invalid inputs

### Interactive Web Map Functions
- **File**: `tests/test_web_map_tool.py`
- **Functions to test**:
  - `create_web_map` - Test interactive web map generation
    - Test with different layer types
    - Test with multiple layers
    - Test different basemap options
    - Test tooltip and popup functionality
    - Test legend and minimap options
    - Test HTML output validation

## Storage and Save Tool Tests

### Save Tool Functions
- **File**: `tests/test_save_tool.py`
- **Functions to test**:
  - Test file saving functionality
  - Test path resolution
  - Test storage configuration
  - Test error handling for invalid paths

## Integration Tests

### End-to-End Workflows
- **File**: `tests/test_integration.py`
- **Scenarios to test**:
  - Complete workflow: Download data → Process → Visualize
  - Multiple library interactions
  - Error propagation through workflows
  - Performance testing for large datasets

## Test Infrastructure Improvements

### Mock Data and Fixtures
- Create reusable fixtures for:
  - Sample administrative boundary data
  - Sample climate data responses
  - Sample satellite imagery
  - Sample street networks
  - Mock API responses for external services

### Test Utilities
- Create helper functions for:
  - Mocking external API calls
  - Creating test datasets
  - Validating output files
  - Comparing geometries

## Notes

- Many data module tests will require mocking external API calls to avoid:
  - Network dependencies
  - API key requirements
  - Rate limiting
  - Cost implications
  
- Consider using `pytest-mock` or `responses` library for API mocking

- Some tests may need to be marked as `@pytest.mark.slow` or `@pytest.mark.integration` if they:
  - Make actual network calls
  - Process large datasets
  - Take significant time to execute

- Consider adding test data files to a `tests/data/` directory for:
  - Sample shapefiles
  - Sample raster files
  - Sample GeoJSON files
  - Expected output files for comparison
