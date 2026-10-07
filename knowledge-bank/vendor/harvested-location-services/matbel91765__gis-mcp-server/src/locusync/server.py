"""LocuSync Server - Main entry point."""

import logging
from typing import Annotated, Any, Literal, cast

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from pydantic import Field

from locusync.config import get_config
from locusync.metrics import metrics, render_prometheus

# Import all tool implementations
from locusync.tools.elevation import get_elevation, get_elevation_profile
from locusync.tools.files import (
    clip_features as _clip_features,
)
from locusync.tools.files import (
    dissolve_features as _dissolve_features,
)
from locusync.tools.files import (
    merge_features as _merge_features,
)
from locusync.tools.files import (
    overlay_features as _overlay_features,
)
from locusync.tools.files import (
    read_geo_file,
    write_geo_file,
)
from locusync.tools.files import (
    spatial_join as _spatial_join,
)
from locusync.tools.geocoding import (
    batch_geocode as _batch_geocode,
)
from locusync.tools.geocoding import (
    batch_reverse_geocode as _batch_reverse_geocode,
)
from locusync.tools.geocoding import (
    geocode_address,
    reverse_geocode_coords,
)
from locusync.tools.geometry import (
    calculate_area as _calculate_area,
)
from locusync.tools.geometry import (
    calculate_buffer,
    calculate_distance,
    perform_spatial_query,
    transform_coordinates,
)
from locusync.tools.geometry import (
    calculate_length as _calculate_length,
)
from locusync.tools.geometry import (
    get_centroid as _get_centroid,
)
from locusync.tools.geometry import (
    get_convex_hull as _get_convex_hull,
)
from locusync.tools.geometry import (
    get_crs_info as _get_crs_info,
)
from locusync.tools.geometry import (
    get_envelope as _get_envelope,
)
from locusync.tools.geometry import (
    get_utm_zone as _get_utm_zone,
)
from locusync.tools.geometry import (
    simplify_geometry as _simplify_geometry,
)
from locusync.tools.geometry import (
    validate_geometry as _validate_geometry,
)
from locusync.tools.postgis import list_spatial_tables, run_spatial_query
from locusync.tools.raster import (
    calculate_hillshade as _calculate_hillshade,
)
from locusync.tools.raster import (
    calculate_ndvi as _calculate_ndvi,
)
from locusync.tools.raster import (
    calculate_slope as _calculate_slope,
)
from locusync.tools.raster import (
    raster_calculator as _raster_calculator,
)
from locusync.tools.raster import (
    read_raster as _read_raster,
)
from locusync.tools.raster import (
    reproject_raster as _reproject_raster,
)
from locusync.tools.raster import (
    zonal_statistics as _zonal_statistics,
)
from locusync.tools.routing import (
    calculate_distance_matrix,
    calculate_isochrone,
    calculate_route,
)
from locusync.tools.statistics import (
    calculate_getis_ord as _calculate_getis_ord,
)
from locusync.tools.statistics import (
    calculate_local_moran as _calculate_local_moran,
)
from locusync.tools.statistics import (
    calculate_moran_i as _calculate_moran_i,
)
from locusync.tools.statistics import (
    create_spatial_weights as _create_spatial_weights,
)
from locusync.tools.visualization import (
    create_choropleth_map as _create_choropleth_map,
)
from locusync.tools.visualization import (
    create_static_map as _create_static_map,
)
from locusync.tools.visualization import (
    create_web_map as _create_web_map,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("LocuSync Server")


# =============================================================================
# OBSERVABILITY
# =============================================================================

class MetricsMiddleware(Middleware):  # type: ignore[misc]
    """Record call count, errors and latency for every tool invocation."""

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        import time

        name = getattr(getattr(context, "message", None), "name", "unknown")
        start = time.perf_counter()
        is_error = False
        try:
            result = await call_next(context)
            if getattr(result, "isError", False):
                is_error = True
            return result
        except Exception:
            is_error = True
            raise
        finally:
            metrics.record(name, time.perf_counter() - start, is_error=is_error)


mcp.add_middleware(MetricsMiddleware())

@mcp.custom_route("/metrics", methods=["GET"])
async def metrics_endpoint(request: Any) -> Any:
    """Prometheus scrape endpoint (HTTP transport). Unauthenticated by design."""
    from starlette.responses import PlainTextResponse

    return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4")


@mcp.tool()
async def health() -> dict[str, Any]:
    """Return server health: per-tool metrics and cache statistics."""
    from locusync.cache import get_cache

    cache = get_cache()
    return {
        "success": True,
        "data": {
            "status": "ok",
            "metrics": metrics.snapshot(),
            "cache": cache.stats() if cache is not None else {"enabled": False},
        },
        "metadata": {"source": "locusync"},
        "error": None,
    }


# =============================================================================
# GEOCODING TOOLS
# =============================================================================

@mcp.tool()
async def geocode(
    address: Annotated[str, Field(description="Address to geocode")]
) -> dict[str, Any]:
    """Convert an address to geographic coordinates (latitude/longitude)."""
    return await geocode_address(address)


@mcp.tool()
async def reverse_geocode(
    lat: Annotated[float, Field(description="Latitude (-90 to 90)")],
    lon: Annotated[float, Field(description="Longitude (-180 to 180)")]
) -> dict[str, Any]:
    """Convert coordinates to an address (reverse geocoding)."""
    return await reverse_geocode_coords(lat, lon)


@mcp.tool()
async def batch_geocode(
    addresses: Annotated[list[str], Field(description="Addresses to geocode (max 25)")]
) -> dict[str, Any]:
    """Geocode many addresses at once (deduplicated, rate-limited)."""
    return await _batch_geocode(addresses)


@mcp.tool()
async def batch_reverse_geocode(
    coordinates: Annotated[
        list[list[float]], Field(description="[lat, lon] pairs to reverse geocode (max 25)")
    ]
) -> dict[str, Any]:
    """Reverse geocode many [lat, lon] pairs at once (deduplicated, rate-limited)."""
    return await _batch_reverse_geocode(coordinates)


# =============================================================================
# GEOMETRY TOOLS (Basic)
# =============================================================================

@mcp.tool()
async def distance(
    lat1: Annotated[float, Field(description="Latitude of first point")],
    lon1: Annotated[float, Field(description="Longitude of first point")],
    lat2: Annotated[float, Field(description="Latitude of second point")],
    lon2: Annotated[float, Field(description="Longitude of second point")],
    method: Annotated[str, Field(description="Method: 'haversine' or 'geodesic'")] = "geodesic"
) -> dict[str, Any]:
    """Calculate the distance between two geographic points."""
    return await calculate_distance(lat1, lon1, lat2, lon2, method)


@mcp.tool()
async def buffer(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")],
    distance_meters: Annotated[float, Field(description="Buffer distance in meters")],
    resolution: Annotated[int, Field(description="Segments for curved edges")] = 16
) -> dict[str, Any]:
    """Create a buffer zone around a geometry."""
    return await calculate_buffer(geometry, distance_meters, resolution)


@mcp.tool()
async def spatial_query(
    geometry1: Annotated[dict[str, Any], Field(description="First GeoJSON geometry")],
    geometry2: Annotated[dict[str, Any], Field(description="Second GeoJSON geometry")],
    operation: Annotated[str, Field(description="Spatial operation to perform")]
) -> dict[str, Any]:
    """Perform spatial operations between two geometries."""
    return await perform_spatial_query(geometry1, geometry2, operation)


@mcp.tool()
async def transform_crs(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry to transform")],
    source_crs: Annotated[str, Field(description="Source CRS (e.g., 'EPSG:4326')")],
    target_crs: Annotated[str, Field(description="Target CRS (e.g., 'EPSG:3857')")]
) -> dict[str, Any]:
    """Transform coordinates between coordinate reference systems."""
    return await transform_coordinates(geometry, source_crs, target_crs)


# =============================================================================
# GEOMETRY TOOLS (Advanced Shapely)
# =============================================================================

@mcp.tool()
async def centroid(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")]
) -> dict[str, Any]:
    """Get the centroid (center point) of a geometry."""
    return await _get_centroid(geometry)


@mcp.tool()
async def simplify(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")],
    tolerance: Annotated[float, Field(description="Simplification tolerance")],
    preserve_topology: Annotated[bool, Field(description="Preserve topology")] = True
) -> dict[str, Any]:
    """Simplify a geometry using Douglas-Peucker algorithm."""
    return await _simplify_geometry(geometry, tolerance, preserve_topology)


@mcp.tool()
async def convex_hull(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")]
) -> dict[str, Any]:
    """Get the convex hull of a geometry."""
    return await _get_convex_hull(geometry)


@mcp.tool()
async def envelope(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")]
) -> dict[str, Any]:
    """Get the bounding box (envelope) of a geometry."""
    return await _get_envelope(geometry)


@mcp.tool()
async def validate(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")]
) -> dict[str, Any]:
    """Validate a geometry and fix it if invalid."""
    return await _validate_geometry(geometry)


@mcp.tool()
async def area(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON Polygon or MultiPolygon")]
) -> dict[str, Any]:
    """Calculate the area of a polygon geometry in multiple units."""
    return await _calculate_area(geometry)


@mcp.tool()
async def length(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry")]
) -> dict[str, Any]:
    """Calculate the length/perimeter of a geometry."""
    return await _calculate_length(geometry)


# =============================================================================
# PYPROJ TOOLS
# =============================================================================

@mcp.tool()
async def utm_zone(
    lat: Annotated[float, Field(description="Latitude")],
    lon: Annotated[float, Field(description="Longitude")]
) -> dict[str, Any]:
    """Get the UTM zone for a given coordinate."""
    return await _get_utm_zone(lat, lon)


@mcp.tool()
async def crs_info(
    crs_code: Annotated[str, Field(description="CRS identifier (e.g., 'EPSG:4326')")]
) -> dict[str, Any]:
    """Get detailed information about a coordinate reference system."""
    return await _get_crs_info(crs_code)


# =============================================================================
# ROUTING TOOLS
# =============================================================================

@mcp.tool()
async def route(
    start_lat: Annotated[float, Field(description="Start point latitude")],
    start_lon: Annotated[float, Field(description="Start point longitude")],
    end_lat: Annotated[float, Field(description="End point latitude")],
    end_lon: Annotated[float, Field(description="End point longitude")],
    profile: Annotated[str, Field(description="Profile: driving/walking/cycling")] = "driving"
) -> dict[str, Any]:
    """Calculate a route between two points."""
    return await calculate_route(start_lat, start_lon, end_lat, end_lon, profile)


@mcp.tool()
async def isochrone(
    lat: Annotated[float, Field(description="Center point latitude")],
    lon: Annotated[float, Field(description="Center point longitude")],
    time_minutes: Annotated[int, Field(description="Travel time in minutes")],
    profile: Annotated[str, Field(description="Profile: driving/walking/cycling")] = "driving"
) -> dict[str, Any]:
    """Calculate an isochrone (area reachable within a time limit)."""
    return await calculate_isochrone(lat, lon, time_minutes, profile)


@mcp.tool()
async def distance_matrix(
    points: Annotated[
        list[list[float]], Field(description="[lat, lon] pairs, 2 to 25 points")
    ],
    profile: Annotated[str, Field(description="Profile: driving/walking/cycling")] = "driving"
) -> dict[str, Any]:
    """Compute a full duration+distance matrix between points (OSRM table)."""
    return await calculate_distance_matrix(points, profile)


# =============================================================================
# ELEVATION TOOLS
# =============================================================================

@mcp.tool()
async def elevation(
    lat: Annotated[float, Field(description="Latitude")],
    lon: Annotated[float, Field(description="Longitude")]
) -> dict[str, Any]:
    """Get elevation for a single point (meters above sea level)."""
    return await get_elevation(lat, lon)


@mcp.tool()
async def elevation_profile(
    geometry: Annotated[dict[str, Any], Field(description="GeoJSON LineString geometry")],
    samples: Annotated[int, Field(description="Number of sample points")] = 100
) -> dict[str, Any]:
    """Get elevation profile along a line."""
    coordinates = geometry.get("coordinates", [])
    return await get_elevation_profile(coordinates)


# =============================================================================
# FILE I/O TOOLS
# =============================================================================

@mcp.tool()
async def read_file(
    file_path: Annotated[str, Field(description="Path to geospatial file")],
    layer: Annotated[str | None, Field(description="Layer name")] = None,
    limit: Annotated[int | None, Field(description="Max features to return")] = None
) -> dict[str, Any]:
    """Read a geospatial file (GeoJSON, Shapefile, GeoPackage, etc.)."""
    return await read_geo_file(file_path, layer, limit)


@mcp.tool()
async def write_file(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    file_path: Annotated[str, Field(description="Output file path")],
    driver: Annotated[str, Field(description="Format: GeoJSON/Shapefile/GPKG")] = "GeoJSON"
) -> dict[str, Any]:
    """Write features to a geospatial file."""
    return await write_geo_file(features, file_path, driver)


# =============================================================================
# GEOPANDAS TOOLS
# =============================================================================

@mcp.tool()
async def spatial_join(
    left_features: Annotated[dict[str, Any], Field(description="Left GeoJSON FeatureCollection")],
    right_features: Annotated[dict[str, Any], Field(description="Right GeoJSON FeatureCollection")],
    how: Annotated[str, Field(description="Join type: inner/left/right")] = "inner",
    predicate: Annotated[str, Field(description="Spatial predicate")] = "intersects"
) -> dict[str, Any]:
    """Perform a spatial join between two feature collections."""
    return await _spatial_join(left_features, right_features, how, predicate)


@mcp.tool()
async def clip(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection to clip")],
    clip_geometry: Annotated[dict[str, Any], Field(description="GeoJSON geometry to clip by")]
) -> dict[str, Any]:
    """Clip features to a boundary geometry."""
    return await _clip_features(features, clip_geometry)


@mcp.tool()
async def dissolve(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    by: Annotated[str | None, Field(description="Field to dissolve by")] = None,
    aggfunc: Annotated[str, Field(description="Aggregation: first/last/sum/mean")] = "first"
) -> dict[str, Any]:
    """Dissolve features, optionally by a property."""
    return await _dissolve_features(features, by, aggfunc)


@mcp.tool()
async def overlay(
    features1: Annotated[dict[str, Any], Field(description="First GeoJSON FeatureCollection")],
    features2: Annotated[dict[str, Any], Field(description="Second GeoJSON FeatureCollection")],
    how: Annotated[str, Field(description="Overlay operation")] = "intersection"
) -> dict[str, Any]:
    """Perform overlay operation between two feature collections."""
    return await _overlay_features(features1, features2, how)


@mcp.tool()
async def merge(
    feature_collections: Annotated[
        list[dict[str, Any]], Field(description="GeoJSON FeatureCollections")
    ]
) -> dict[str, Any]:
    """Merge multiple feature collections into one."""
    return await _merge_features(feature_collections)


# =============================================================================
# RASTER TOOLS
# =============================================================================

@mcp.tool()
async def read_raster(
    file_path: Annotated[str, Field(description="Path to raster file")],
    band: Annotated[int | None, Field(description="Band number (1-indexed)")] = None
) -> dict[str, Any]:
    """Read a raster file and return metadata and statistics."""
    return await _read_raster(file_path, band)


@mcp.tool()
async def ndvi(
    red_band_path: Annotated[str, Field(description="Path to red band raster")],
    nir_band_path: Annotated[str, Field(description="Path to NIR band raster")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None
) -> dict[str, Any]:
    """Calculate NDVI (Normalized Difference Vegetation Index)."""
    return await _calculate_ndvi(red_band_path, nir_band_path, output_path)


@mcp.tool()
async def hillshade(
    dem_path: Annotated[str, Field(description="Path to DEM raster")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None,
    azimuth: Annotated[float, Field(description="Sun azimuth (degrees)")] = 315,
    altitude: Annotated[float, Field(description="Sun altitude (degrees)")] = 45
) -> dict[str, Any]:
    """Calculate hillshade from a Digital Elevation Model."""
    return await _calculate_hillshade(dem_path, output_path, azimuth, altitude)


@mcp.tool()
async def slope(
    dem_path: Annotated[str, Field(description="Path to DEM raster")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None,
    units: Annotated[str, Field(description="Output units: degrees/percent")] = "degrees"
) -> dict[str, Any]:
    """Calculate slope from a Digital Elevation Model."""
    return await _calculate_slope(dem_path, output_path, units)


@mcp.tool()
async def zonal_stats(
    raster_path: Annotated[str, Field(description="Path to raster file")],
    zones_path: Annotated[str, Field(description="Path to vector zones file")],
    band: Annotated[int, Field(description="Band number")] = 1
) -> dict[str, Any]:
    """Calculate zonal statistics for a raster using vector zones."""
    return await _zonal_statistics(raster_path, zones_path, band)


@mcp.tool()
async def reproject_raster(
    input_path: Annotated[str, Field(description="Input raster path")],
    output_path: Annotated[str, Field(description="Output raster path")],
    target_crs: Annotated[str, Field(description="Target CRS (e.g., 'EPSG:4326')")],
    resampling: Annotated[str, Field(description="Resampling: nearest/bilinear/cubic")] = "nearest"
) -> dict[str, Any]:
    """Reproject a raster to a different CRS."""
    return await _reproject_raster(input_path, output_path, target_crs, resampling)


@mcp.tool()
async def raster_calc(
    expression: Annotated[str, Field(description="Math expression (e.g., 'A + B')")],
    rasters: Annotated[dict[str, str], Field(description="Variable to file path mapping")],
    output_path: Annotated[str, Field(description="Output file path")]
) -> dict[str, Any]:
    """Perform raster algebra using a mathematical expression."""
    return await _raster_calculator(expression, rasters, output_path)


# =============================================================================
# VISUALIZATION TOOLS
# =============================================================================

@mcp.tool()
async def static_map(
    features: Annotated[dict[str, Any], Field(description="GeoJSON features")],
    output_path: Annotated[str | None, Field(description="Output file path")] = None,
    title: Annotated[str | None, Field(description="Map title")] = None
) -> dict[str, Any]:
    """Create a static map image from GeoJSON features (requires matplotlib)."""
    return await _create_static_map(features, output_path, title)


@mcp.tool()
async def web_map(
    features: Annotated[dict[str, Any], Field(description="GeoJSON features")],
    output_path: Annotated[str | None, Field(description="Output HTML file path")] = None,
    title: Annotated[str | None, Field(description="Map title")] = None,
    basemap: Annotated[str, Field(description="Basemap provider")] = "OpenStreetMap"
) -> dict[str, Any]:
    """Create an interactive web map (requires folium)."""
    return await _create_web_map(features, output_path, title=title, basemap=basemap)


@mcp.tool()
async def choropleth_map(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Property field for coloring")],
    output_path: Annotated[str | None, Field(description="Output HTML file path")] = None,
    title: Annotated[str | None, Field(description="Map title")] = None
) -> dict[str, Any]:
    """Create a choropleth (thematic) map based on a property value."""
    return await _create_choropleth_map(features, value_field, output_path, title=title)


# =============================================================================
# SPATIAL STATISTICS TOOLS
# =============================================================================

@mcp.tool()
async def moran_i(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Numeric property field")],
    weight_type: Annotated[str, Field(description="Weight type: queen/rook/knn")] = "queen"
) -> dict[str, Any]:
    """Calculate Global Moran's I for spatial autocorrelation (requires libpysal)."""
    return await _calculate_moran_i(features, value_field, weight_type)


@mcp.tool()
async def local_moran(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Numeric property field")],
    weight_type: Annotated[str, Field(description="Weight type: queen/rook/knn")] = "queen"
) -> dict[str, Any]:
    """Calculate Local Moran's I (LISA) for cluster detection."""
    return await _calculate_local_moran(features, value_field, weight_type)


@mcp.tool()
async def hotspot_analysis(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    value_field: Annotated[str, Field(description="Numeric property field")],
    weight_type: Annotated[str, Field(description="Weight type: distance/queen")] = "distance"
) -> dict[str, Any]:
    """Perform Getis-Ord Gi* hot spot analysis."""
    return await _calculate_getis_ord(features, value_field, weight_type)


@mcp.tool()
async def spatial_weights(
    features: Annotated[dict[str, Any], Field(description="GeoJSON FeatureCollection")],
    weight_type: Annotated[str, Field(description="Type: queen/rook/knn/distance")] = "queen",
    k: Annotated[int, Field(description="Number of neighbors for KNN")] = 5
) -> dict[str, Any]:
    """Create and analyze a spatial weights matrix."""
    return await _create_spatial_weights(features, weight_type, k)


# =============================================================================
# POSTGIS TOOLS
# =============================================================================

@mcp.tool()
async def postgis_query(
    sql: Annotated[str, Field(description="Read-only SELECT/WITH spatial SQL query")],
    limit: Annotated[int, Field(description="Max rows to return (capped at 10000)")] = 1000,
) -> dict[str, Any]:
    """Run a read-only spatial SQL query against PostGIS.

    Wrap geometry columns in ST_AsGeoJSON(geom) to get GeoJSON back. Requires
    POSTGIS_DSN to be configured and the '.[postgis]' extra installed.
    """
    return await run_spatial_query(sql, limit)


@mcp.tool()
async def postgis_tables() -> dict[str, Any]:
    """List spatial tables registered in the PostGIS geometry_columns view."""
    return await list_spatial_tables()


def main() -> None:
    """Run the MCP server.

    Transport is selected via ``LOCUSYNC_TRANSPORT`` (stdio by default for local
    Claude Desktop use; ``http``/``sse`` for networked deployment).
    """
    config = get_config()
    server_cfg = config.server

    logger.info("Starting LocuSync Server (transport=%s)...", server_cfg.transport)
    logger.info(f"Nominatim URL: {config.nominatim.base_url}")
    logger.info(f"OSRM URL: {config.osrm.base_url}")
    logger.info("Tools: Geocoding, Geometry, Routing, Files, Raster, Visualization, Statistics")

    transport = server_cfg.transport
    if transport == "stdio":
        mcp.run()
        return

    if transport not in ("http", "sse"):
        raise ValueError(
            f"Unsupported transport '{transport}'. Use 'stdio', 'http' or 'sse'."
        )

    # Defense-in-depth bearer auth for networked transports (on top of any
    # reverse-proxy auth). Enabled only when a token is provided.
    if server_cfg.auth_token:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

        mcp.auth = StaticTokenVerifier(
            tokens={server_cfg.auth_token: {"client_id": "locusync", "scopes": []}}
        )
        logger.info("Bearer-token authentication enabled")
    else:
        logger.warning(
            "No LOCUSYNC_AUTH_TOKEN set — relying on the upstream proxy for auth"
        )

    mcp.run(
        transport=cast(Literal["http", "sse"], transport),
        host=server_cfg.host,
        port=server_cfg.port,
    )


if __name__ == "__main__":
    main()
