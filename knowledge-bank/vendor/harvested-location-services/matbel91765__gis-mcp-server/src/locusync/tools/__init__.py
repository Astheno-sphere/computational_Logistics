"""GIS MCP Tools - Comprehensive geospatial operations."""

# Elevation tools
from locusync.tools.elevation import get_elevation, get_elevation_profile

# File I/O tools
from locusync.tools.files import (
    clip_features,
    dissolve_features,
    merge_features,
    overlay_features,
    read_geo_file,
    spatial_join,
    write_geo_file,
)

# Geocoding tools
from locusync.tools.geocoding import geocode_address, reverse_geocode_coords

# Geometry tools (Shapely + PyProj)
from locusync.tools.geometry import (
    calculate_area,
    calculate_buffer,
    calculate_distance,
    calculate_length,
    get_centroid,
    get_convex_hull,
    get_crs_info,
    get_envelope,
    get_utm_zone,
    perform_spatial_query,
    simplify_geometry,
    transform_coordinates,
    validate_geometry,
)

# Raster tools
from locusync.tools.raster import (
    calculate_hillshade,
    calculate_ndvi,
    calculate_slope,
    raster_calculator,
    read_raster,
    reproject_raster,
    zonal_statistics,
)

# Routing tools
from locusync.tools.routing import calculate_isochrone, calculate_route

# Spatial statistics tools
from locusync.tools.statistics import (
    calculate_getis_ord,
    calculate_local_moran,
    calculate_moran_i,
    create_spatial_weights,
)

# Visualization tools
from locusync.tools.visualization import (
    create_choropleth_map,
    create_static_map,
    create_web_map,
)

__all__ = [
    # Geocoding
    "geocode_address",
    "reverse_geocode_coords",
    # Geometry (basic)
    "calculate_buffer",
    "calculate_distance",
    "perform_spatial_query",
    "transform_coordinates",
    # Geometry (advanced Shapely)
    "get_centroid",
    "simplify_geometry",
    "get_convex_hull",
    "get_envelope",
    "validate_geometry",
    "calculate_area",
    "calculate_length",
    # PyProj
    "get_utm_zone",
    "get_crs_info",
    # Routing
    "calculate_route",
    "calculate_isochrone",
    # Files (basic)
    "read_geo_file",
    "write_geo_file",
    # Files (GeoPandas operations)
    "spatial_join",
    "clip_features",
    "dissolve_features",
    "overlay_features",
    "merge_features",
    # Elevation
    "get_elevation",
    "get_elevation_profile",
    # Raster
    "read_raster",
    "calculate_ndvi",
    "calculate_hillshade",
    "calculate_slope",
    "zonal_statistics",
    "reproject_raster",
    "raster_calculator",
    # Visualization
    "create_static_map",
    "create_web_map",
    "create_choropleth_map",
    # Statistics
    "calculate_moran_i",
    "calculate_local_moran",
    "calculate_getis_ord",
    "create_spatial_weights",
]
