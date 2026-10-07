"""File I/O tools for GIS MCP Server."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

import geopandas as gpd

from locusync.config import get_config
from locusync.security import PathSecurityError, get_workspace_root, safe_path
from locusync.utils import make_error_response, make_success_response

logger = logging.getLogger(__name__)

# Number of features kept inline as a preview when a result is offloaded to disk.
OFFLOAD_SAMPLE_SIZE = 10


async def _offload_large_features(data: dict[str, Any], kind: str) -> dict[str, Any]:
    """Write oversized FeatureCollections to the sandbox, return a handle + sample.

    Keeps the LLM response small: if ``data["features"]`` exceeds
    ``max_inline_features``, the full collection is written to
    ``<workspace>/results/<kind>_<uuid>.geojson`` and the inline payload is
    replaced by a short preview plus ``output_file``/``total_features``.
    """
    features = data.get("features")
    threshold = get_config().max_inline_features
    if not isinstance(features, list) or len(features) <= threshold:
        return data

    results_dir = get_workspace_root() / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / f"{kind}_{uuid4().hex}.geojson"
    fc = {"type": "FeatureCollection", "features": features}
    await asyncio.to_thread(out_path.write_text, json.dumps(fc))

    reduced = dict(data)
    reduced["features"] = features[:OFFLOAD_SAMPLE_SIZE]
    reduced["truncated"] = True
    reduced["total_features"] = len(features)
    reduced["sample_size"] = min(OFFLOAD_SAMPLE_SIZE, len(features))
    reduced["output_file"] = str(out_path)
    return reduced


def _check_feature_count(count: int) -> str | None:
    """Return an error message when a feature count exceeds the configured cap."""
    max_features = get_config().max_features
    if count > max_features:
        return (
            f"Too many features ({count}). Maximum allowed is {max_features}. "
            "Reduce the input or pre-filter the data."
        )
    return None


# Supported file extensions and their drivers
EXTENSION_DRIVERS = {
    ".geojson": "GeoJSON",
    ".json": "GeoJSON",
    ".shp": "ESRI Shapefile",
    ".gpkg": "GPKG",
    ".gdb": "OpenFileGDB",
    ".kml": "KML",
    ".gml": "GML",
}


def _get_driver_for_path(file_path: str) -> str | None:
    """Get the appropriate driver for a file path.

    Args:
        file_path: Path to the file.

    Returns:
        Driver name or None if unsupported.
    """
    ext = Path(file_path).suffix.lower()
    return EXTENSION_DRIVERS.get(ext)


async def read_geo_file(
    file_path: str,
    layer: str | None = None,
    limit: int | None = None
) -> dict[str, Any]:
    """Read a geospatial file and return its features.

    Args:
        file_path: Path to the file.
        layer: Layer name for multi-layer files.
        limit: Maximum number of features to return.

    Returns:
        GIS response with features as GeoJSON.
    """
    # Resolve inside the sandbox (blocks path traversal) and ensure it exists.
    try:
        path = safe_path(file_path, must_exist=True)
    except PathSecurityError as e:
        return make_error_response(str(e))

    # Check file size
    config = get_config()
    file_size_mb = path.stat().st_size / (1024 * 1024)
    if file_size_mb > config.max_file_size_mb:
        return make_error_response(
            f"File too large ({file_size_mb:.1f} MB). Maximum: {config.max_file_size_mb} MB"
        )

    # Check extension
    driver = _get_driver_for_path(file_path)
    if not driver:
        supported = ", ".join(EXTENSION_DRIVERS.keys())
        return make_error_response(
            f"Unsupported file format. Supported extensions: {supported}"
        )

    try:
        # Read with geopandas
        read_kwargs: dict[str, Any] = {}
        if layer:
            read_kwargs["layer"] = layer
        if limit:
            read_kwargs["rows"] = limit

        # Offload blocking I/O+parse off the event loop.
        gdf = await asyncio.to_thread(gpd.read_file, str(path), **read_kwargs)

        if gdf.empty:
            return make_error_response("File contains no features")

        # Guard against returning an unbounded number of features.
        if (count_error := _check_feature_count(len(gdf))) is not None:
            return make_error_response(count_error)

        # Convert to GeoJSON
        geojson = gdf.__geo_interface__

        # Get layer info for multi-layer files
        layers = None
        try:
            import fiona
            layers = fiona.listlayers(str(path))
        except Exception:
            pass

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(gdf),
        }

        # Add CRS info
        crs_info = None
        if gdf.crs:
            crs_info = {
                "epsg": gdf.crs.to_epsg(),
                "wkt": gdf.crs.to_wkt(),
                "proj4": gdf.crs.to_proj4() if hasattr(gdf.crs, "to_proj4") else None,
            }

        # Get column info
        columns = [
            {"name": col, "dtype": str(gdf[col].dtype)}
            for col in gdf.columns if col != "geometry"
        ]

        # Get geometry types
        geom_types = gdf.geometry.geom_type.unique().tolist()

        metadata = {
            "file_path": str(path.absolute()),
            "file_size_mb": round(file_size_mb, 2),
            "driver": driver,
            "crs": crs_info,
            "columns": columns,
            "geometry_types": geom_types,
            "layers": layers,
            "bounds": list(gdf.total_bounds) if not gdf.empty else None,
        }

        data = await _offload_large_features(data, "read")
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error reading file: {e}")
        return make_error_response(f"Failed to read file: {str(e)}")


async def write_geo_file(
    features: dict[str, Any],
    file_path: str,
    driver: str = "GeoJSON"
) -> dict[str, Any]:
    """Write features to a geospatial file.

    Args:
        features: GeoJSON FeatureCollection.
        file_path: Output file path.
        driver: Output format driver.

    Returns:
        GIS response with file info.
    """
    # Validate driver
    valid_drivers = {"GeoJSON", "ESRI Shapefile", "GPKG"}
    if driver not in valid_drivers:
        return make_error_response(
            f"Invalid driver '{driver}'. Valid options: {', '.join(valid_drivers)}"
        )

    # Validate features structure
    if not isinstance(features, dict):
        return make_error_response("Features must be a GeoJSON object")

    if features.get("type") != "FeatureCollection":
        return make_error_response("Features must be a FeatureCollection")

    feature_list = features.get("features", [])
    if not feature_list:
        return make_error_response("FeatureCollection contains no features")

    if (count_error := _check_feature_count(len(feature_list))) is not None:
        return make_error_response(count_error)

    # Resolve the output path inside the sandbox (blocks writing outside it).
    try:
        out_path = safe_path(file_path)
    except PathSecurityError as e:
        return make_error_response(str(e))

    try:
        # Create GeoDataFrame from GeoJSON
        gdf = gpd.GeoDataFrame.from_features(feature_list)

        # Set CRS if not present (default to WGS84)
        if gdf.crs is None:
            crs = features.get("crs", {}).get("properties", {}).get("name")
            if crs:
                gdf.set_crs(crs, inplace=True)
            else:
                gdf.set_crs("EPSG:4326", inplace=True)

        # Ensure parent directory exists
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file (offload blocking serialization off the event loop).
        await asyncio.to_thread(gdf.to_file, str(out_path), driver=driver)

        # Get file info
        file_size_mb = out_path.stat().st_size / (1024 * 1024)

        data = {
            "file_path": str(out_path),
            "feature_count": len(gdf),
            "driver": driver,
        }

        metadata = {
            "file_size_mb": round(file_size_mb, 4),
            "crs": str(gdf.crs) if gdf.crs else None,
            "geometry_types": gdf.geometry.geom_type.unique().tolist(),
            "columns": list(gdf.columns),
        }

        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error writing file: {e}")
        return make_error_response(f"Failed to write file: {str(e)}")


# =============================================================================
# GEOPANDAS OPERATIONS
# =============================================================================

async def spatial_join(
    left_features: dict[str, Any],
    right_features: dict[str, Any],
    how: str = "inner",
    predicate: str = "intersects"
) -> dict[str, Any]:
    """Perform a spatial join between two feature collections.

    Args:
        left_features: Left GeoJSON FeatureCollection.
        right_features: Right GeoJSON FeatureCollection.
        how: Join type ('inner', 'left', 'right').
        predicate: Spatial predicate ('intersects', 'contains', 'within').

    Returns:
        GIS response with joined features.
    """
    valid_how = {"inner", "left", "right"}
    if how not in valid_how:
        return make_error_response(f"Invalid 'how'. Use one of: {valid_how}")

    valid_predicates = {"intersects", "contains", "within", "crosses", "touches"}
    if predicate not in valid_predicates:
        return make_error_response(f"Invalid predicate. Use one of: {valid_predicates}")

    try:
        # Parse features
        left_gdf = gpd.GeoDataFrame.from_features(left_features.get("features", []))
        right_gdf = gpd.GeoDataFrame.from_features(right_features.get("features", []))

        if left_gdf.empty:
            return make_error_response("Left features are empty")
        if right_gdf.empty:
            return make_error_response("Right features are empty")

        # Set CRS if not present
        if left_gdf.crs is None:
            left_gdf = left_gdf.set_crs("EPSG:4326")
        if right_gdf.crs is None:
            right_gdf = right_gdf.set_crs("EPSG:4326")

        # Ensure same CRS
        if left_gdf.crs != right_gdf.crs:
            right_gdf = right_gdf.to_crs(left_gdf.crs)

        # Perform spatial join (CPU-heavy → run in a worker thread)
        result = await asyncio.to_thread(
            gpd.sjoin, left_gdf, right_gdf, how=how, predicate=predicate
        )

        # Convert to GeoJSON
        geojson = result.__geo_interface__

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(result),
        }

        metadata = {
            "how": how,
            "predicate": predicate,
            "left_count": len(left_gdf),
            "right_count": len(right_gdf),
            "result_count": len(result),
            "columns": list(result.columns),
        }

        data = await _offload_large_features(data, "join")
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error in spatial join: {e}")
        return make_error_response(f"Spatial join failed: {str(e)}")


async def clip_features(
    features: dict[str, Any],
    clip_geometry: dict[str, Any]
) -> dict[str, Any]:
    """Clip features to a boundary geometry.

    Args:
        features: GeoJSON FeatureCollection to clip.
        clip_geometry: GeoJSON geometry or FeatureCollection to clip by.

    Returns:
        GIS response with clipped features.
    """
    try:
        from shapely.geometry import shape

        # Parse features
        gdf = gpd.GeoDataFrame.from_features(features.get("features", []))

        if gdf.empty:
            return make_error_response("Features are empty")

        # Parse clip geometry
        if clip_geometry.get("type") == "FeatureCollection":
            clip_gdf = gpd.GeoDataFrame.from_features(clip_geometry.get("features", []))
            clip_geom = clip_gdf.union_all()
        elif clip_geometry.get("type") == "Feature":
            clip_geom = shape(clip_geometry.get("geometry"))
        else:
            clip_geom = shape(clip_geometry)

        # Set CRS
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

        # Clip (CPU-heavy → run in a worker thread)
        result = await asyncio.to_thread(gpd.clip, gdf, clip_geom)

        if result.empty:
            return make_error_response("Clip resulted in no features")

        # Convert to GeoJSON
        geojson = result.__geo_interface__

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(result),
        }

        metadata = {
            "original_count": len(gdf),
            "clipped_count": len(result),
            "bounds": list(result.total_bounds),
        }

        data = await _offload_large_features(data, "clip")
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error clipping features: {e}")
        return make_error_response(f"Clip failed: {str(e)}")


async def dissolve_features(
    features: dict[str, Any],
    by: str | None = None,
    aggfunc: str | dict[str, str] = "first"
) -> dict[str, Any]:
    """Dissolve features, optionally by a property.

    Args:
        features: GeoJSON FeatureCollection.
        by: Property name to dissolve by (None for all features).
        aggfunc: Aggregation function ('first', 'last', 'sum', 'mean', etc.).

    Returns:
        GIS response with dissolved features.
    """
    try:
        gdf = gpd.GeoDataFrame.from_features(features.get("features", []))

        if gdf.empty:
            return make_error_response("Features are empty")

        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")

        # Validate 'by' field
        if by and by not in gdf.columns:
            return make_error_response(
                f"Field '{by}' not found. Available: {list(gdf.columns)}"
            )

        # Dissolve (CPU-heavy → run in a worker thread)
        if by:
            result = await asyncio.to_thread(
                lambda: gdf.dissolve(by=by, aggfunc=aggfunc).reset_index()
            )
        else:
            # Dissolve all into one
            union = await asyncio.to_thread(gdf.union_all)
            result = gpd.GeoDataFrame(geometry=[union], crs=gdf.crs)

        # Convert to GeoJSON
        geojson = result.__geo_interface__

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(result),
        }

        metadata = {
            "original_count": len(gdf),
            "dissolved_count": len(result),
            "dissolved_by": by,
            "aggfunc": str(aggfunc),
        }

        data = await _offload_large_features(data, "dissolve")
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error dissolving features: {e}")
        return make_error_response(f"Dissolve failed: {str(e)}")


async def overlay_features(
    features1: dict[str, Any],
    features2: dict[str, Any],
    how: str = "intersection"
) -> dict[str, Any]:
    """Perform overlay operation between two feature collections.

    Args:
        features1: First GeoJSON FeatureCollection.
        features2: Second GeoJSON FeatureCollection.
        how: Overlay operation ('intersection', 'union', 'difference', 'symmetric_difference').

    Returns:
        GIS response with overlay result.
    """
    valid_how = {"intersection", "union", "difference", "symmetric_difference", "identity"}
    if how not in valid_how:
        return make_error_response(f"Invalid 'how'. Use one of: {valid_how}")

    try:
        gdf1 = gpd.GeoDataFrame.from_features(features1.get("features", []))
        gdf2 = gpd.GeoDataFrame.from_features(features2.get("features", []))

        if gdf1.empty:
            return make_error_response("First features are empty")
        if gdf2.empty:
            return make_error_response("Second features are empty")

        # Set CRS
        if gdf1.crs is None:
            gdf1 = gdf1.set_crs("EPSG:4326")
        if gdf2.crs is None:
            gdf2 = gdf2.set_crs("EPSG:4326")

        # Ensure same CRS
        if gdf1.crs != gdf2.crs:
            gdf2 = gdf2.to_crs(gdf1.crs)

        # Perform overlay (CPU-heavy → run in a worker thread)
        result = await asyncio.to_thread(gpd.overlay, gdf1, gdf2, how=how)

        if result.empty:
            return make_error_response(f"Overlay '{how}' resulted in no features")

        # Convert to GeoJSON
        geojson = result.__geo_interface__

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(result),
        }

        metadata = {
            "operation": how,
            "input1_count": len(gdf1),
            "input2_count": len(gdf2),
            "result_count": len(result),
            "columns": list(result.columns),
        }

        data = await _offload_large_features(data, "overlay")
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error in overlay: {e}")
        return make_error_response(f"Overlay failed: {str(e)}")


async def merge_features(
    feature_collections: list[dict[str, Any]]
) -> dict[str, Any]:
    """Merge multiple feature collections into one.

    Args:
        feature_collections: List of GeoJSON FeatureCollections.

    Returns:
        GIS response with merged features.
    """
    if not feature_collections:
        return make_error_response("No feature collections provided")

    if len(feature_collections) < 2:
        return make_error_response("At least 2 feature collections required for merge")

    try:
        gdfs = []
        for i, fc in enumerate(feature_collections):
            if fc.get("type") != "FeatureCollection":
                return make_error_response(f"Item {i} is not a FeatureCollection")
            gdf = gpd.GeoDataFrame.from_features(fc.get("features", []))
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
            gdfs.append(gdf)

        # Merge all to same CRS
        target_crs = gdfs[0].crs
        gdfs = [gdf.to_crs(target_crs) if gdf.crs != target_crs else gdf for gdf in gdfs]

        # Concatenate (CPU-heavy → run in a worker thread)
        import pandas as pd
        result = await asyncio.to_thread(
            lambda: gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=target_crs)
        )

        # Convert to GeoJSON
        geojson = result.__geo_interface__

        data = {
            "type": "FeatureCollection",
            "features": geojson.get("features", []),
            "feature_count": len(result),
        }

        metadata = {
            "input_counts": [len(gdf) for gdf in gdfs],
            "total_count": len(result),
            "columns": list(result.columns),
        }

        data = await _offload_large_features(data, "merge")
        return make_success_response(data, metadata)

    except Exception as e:
        logger.exception(f"Error merging features: {e}")
        return make_error_response(f"Merge failed: {str(e)}")
