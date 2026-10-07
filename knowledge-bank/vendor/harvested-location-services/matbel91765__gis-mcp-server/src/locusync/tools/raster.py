"""Raster processing tools for GIS MCP Server.

All file paths are sandboxed via ``safe_path`` (no access outside the workspace)
and every rasterio/numpy computation runs in a worker thread so it never blocks
the asyncio event loop.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import numpy as np

from locusync.security import PathSecurityError, safe_path
from locusync.utils import make_error_response, make_success_response

logger = logging.getLogger(__name__)

# Check if rasterio is available
try:
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import calculate_default_transform, reproject
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False
    logger.warning("Rasterio not available. Raster tools will be disabled.")


def _check_rasterio() -> dict[str, Any] | None:
    """Check if rasterio is available."""
    if not RASTERIO_AVAILABLE:
        return make_error_response(
            "Rasterio is not installed. Install with: pip install rasterio"
        )
    return None


def _resolve(path: str, *, must_exist: bool) -> Path:
    """Resolve a path inside the sandbox, raising PathSecurityError on escape."""
    return safe_path(path, must_exist=must_exist)


async def read_raster(
    file_path: str,
    band: int | None = None,
    window: dict[str, int] | None = None
) -> dict[str, Any]:
    """Read a raster file and return metadata and statistics.

    Args:
        file_path: Path to the raster file.
        band: Specific band to read (1-indexed). If None, reads all bands.
        window: Optional window dict with col_off, row_off, width, height.

    Returns:
        GIS response with raster metadata and statistics.
    """
    error = _check_rasterio()
    if error is not None:
        return error

    try:
        path = _resolve(file_path, must_exist=True)
    except PathSecurityError as e:
        return make_error_response(str(e))

    def _work() -> dict[str, Any]:
        try:
            with rasterio.open(str(path)) as src:
                metadata = {
                    "driver": src.driver,
                    "dtype": str(src.dtypes[0]),
                    "width": src.width,
                    "height": src.height,
                    "count": src.count,
                    "crs": str(src.crs) if src.crs else None,
                    "bounds": {
                        "left": src.bounds.left,
                        "bottom": src.bounds.bottom,
                        "right": src.bounds.right,
                        "top": src.bounds.top,
                    },
                    "transform": list(src.transform)[:6],
                    "nodata": src.nodata,
                }

                if band:
                    if band < 1 or band > src.count:
                        return make_error_response(
                            f"Band {band} out of range (1-{src.count})"
                        )
                    data = src.read(band, window=window)
                    bands_stats = [_compute_band_stats(data, src.nodata, band)]
                else:
                    bands_stats = []
                    for b in range(1, src.count + 1):
                        data = src.read(b, window=window)
                        bands_stats.append(_compute_band_stats(data, src.nodata, b))

                result = {
                    "file": path.name,
                    "metadata": metadata,
                    "statistics": bands_stats,
                }
                return make_success_response(result, {"file_path": str(path)})
        except Exception as e:
            logger.exception(f"Error reading raster: {e}")
            return make_error_response(f"Failed to read raster: {str(e)}")

    return await asyncio.to_thread(_work)


def _compute_band_stats(
    data: np.ndarray[Any, Any], nodata: float | None, band_num: int
) -> dict[str, Any]:
    """Compute statistics for a raster band."""
    valid_data = data[data != nodata] if nodata is not None else data.flatten()

    if len(valid_data) == 0:
        return {"band": band_num, "all_nodata": True}

    return {
        "band": band_num,
        "min": float(np.min(valid_data)),
        "max": float(np.max(valid_data)),
        "mean": float(np.mean(valid_data)),
        "std": float(np.std(valid_data)),
        "median": float(np.median(valid_data)),
        "valid_pixels": int(len(valid_data)),
        "total_pixels": int(data.size),
    }


async def calculate_ndvi(
    red_band_path: str,
    nir_band_path: str,
    output_path: str | None = None,
    red_band: int = 1,
    nir_band: int = 1
) -> dict[str, Any]:
    """Calculate Normalized Difference Vegetation Index (NDVI).

    NDVI = (NIR - Red) / (NIR + Red)
    """
    error = _check_rasterio()
    if error is not None:
        return error

    try:
        red_path = _resolve(red_band_path, must_exist=True)
        nir_path = _resolve(nir_band_path, must_exist=True)
        out_path = _resolve(output_path, must_exist=False) if output_path else None
    except PathSecurityError as e:
        return make_error_response(str(e))

    def _work() -> dict[str, Any]:
        try:
            with rasterio.open(str(red_path)) as red_src, \
                 rasterio.open(str(nir_path)) as nir_src:
                if red_src.shape != nir_src.shape:
                    return make_error_response(
                        "Red and NIR bands must have the same dimensions"
                    )

                red = red_src.read(red_band).astype(np.float32)
                nir = nir_src.read(nir_band).astype(np.float32)

                denominator = nir + red
                ndvi = np.where(denominator != 0, (nir - red) / denominator, 0)
                ndvi = np.clip(ndvi, -1, 1)

                valid_ndvi = ndvi[~np.isnan(ndvi)]
                stats = {
                    "min": float(np.min(valid_ndvi)),
                    "max": float(np.max(valid_ndvi)),
                    "mean": float(np.mean(valid_ndvi)),
                    "std": float(np.std(valid_ndvi)),
                }

                size = ndvi.size
                vegetation_classes = {
                    "water_or_bare": float(np.sum(ndvi < 0) / size * 100),
                    "sparse_vegetation": float(np.sum((ndvi >= 0) & (ndvi < 0.2)) / size * 100),
                    "moderate_vegetation": float(
                        np.sum((ndvi >= 0.2) & (ndvi < 0.4)) / size * 100
                    ),
                    "dense_vegetation": float(np.sum(ndvi >= 0.4) / size * 100),
                }

                output_file = None
                if out_path is not None:
                    profile = red_src.profile.copy()
                    profile.update(dtype=rasterio.float32, count=1, nodata=-9999)
                    with rasterio.open(str(out_path), 'w', **profile) as dst:
                        dst.write(ndvi, 1)
                    output_file = str(out_path)

                data = {
                    "statistics": stats,
                    "vegetation_classes_percent": vegetation_classes,
                    "shape": list(ndvi.shape),
                }
                if output_file:
                    data["output_file"] = output_file

                return make_success_response(data, {
                    "red_band": str(red_path),
                    "nir_band": str(nir_path),
                })
        except Exception as e:
            logger.exception(f"Error calculating NDVI: {e}")
            return make_error_response(f"NDVI calculation failed: {str(e)}")

    return await asyncio.to_thread(_work)


async def calculate_hillshade(
    dem_path: str,
    output_path: str | None = None,
    azimuth: float = 315,
    altitude: float = 45,
    z_factor: float = 1.0
) -> dict[str, Any]:
    """Calculate hillshade from a Digital Elevation Model."""
    error = _check_rasterio()
    if error is not None:
        return error

    if not 0 <= azimuth <= 360:
        return make_error_response("Azimuth must be between 0 and 360 degrees")
    if not 0 <= altitude <= 90:
        return make_error_response("Altitude must be between 0 and 90 degrees")

    try:
        dem = _resolve(dem_path, must_exist=True)
        out_path = _resolve(output_path, must_exist=False) if output_path else None
    except PathSecurityError as e:
        return make_error_response(str(e))

    def _work() -> dict[str, Any]:
        try:
            with rasterio.open(str(dem)) as src:
                dem_arr = src.read(1).astype(np.float32)

                cell_size_x = src.transform[0]
                cell_size_y = abs(src.transform[4])
                cell_size = (cell_size_x + cell_size_y) / 2

                dy, dx = np.gradient(dem_arr * z_factor, cell_size)

                azimuth_rad = np.radians(360 - azimuth + 90)
                altitude_rad = np.radians(altitude)

                slope = np.arctan(np.sqrt(dx**2 + dy**2))
                aspect = np.arctan2(-dx, dy)

                hillshade = np.sin(altitude_rad) * np.cos(slope) + \
                    np.cos(altitude_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
                hillshade = ((hillshade + 1) / 2 * 255).astype(np.uint8)

                output_file = None
                if out_path is not None:
                    profile = src.profile.copy()
                    profile.update(dtype=rasterio.uint8, count=1, nodata=0)
                    with rasterio.open(str(out_path), 'w', **profile) as dst:
                        dst.write(hillshade, 1)
                    output_file = str(out_path)

                data = {
                    "shape": list(hillshade.shape),
                    "min_value": int(np.min(hillshade)),
                    "max_value": int(np.max(hillshade)),
                    "azimuth": azimuth,
                    "altitude": altitude,
                    "z_factor": z_factor,
                }
                if output_file:
                    data["output_file"] = output_file

                return make_success_response(data, {"dem_path": str(dem)})
        except Exception as e:
            logger.exception(f"Error calculating hillshade: {e}")
            return make_error_response(f"Hillshade calculation failed: {str(e)}")

    return await asyncio.to_thread(_work)


async def calculate_slope(
    dem_path: str,
    output_path: str | None = None,
    units: str = "degrees"
) -> dict[str, Any]:
    """Calculate slope from a Digital Elevation Model."""
    error = _check_rasterio()
    if error is not None:
        return error

    if units not in ("degrees", "percent"):
        return make_error_response("Units must be 'degrees' or 'percent'")

    try:
        dem = _resolve(dem_path, must_exist=True)
        out_path = _resolve(output_path, must_exist=False) if output_path else None
    except PathSecurityError as e:
        return make_error_response(str(e))

    def _work() -> dict[str, Any]:
        try:
            with rasterio.open(str(dem)) as src:
                dem_arr = src.read(1).astype(np.float32)

                cell_size_x = src.transform[0]
                cell_size_y = abs(src.transform[4])
                cell_size = (cell_size_x + cell_size_y) / 2

                dy, dx = np.gradient(dem_arr, cell_size)

                slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
                slope = np.degrees(slope_rad) if units == "degrees" else np.tan(slope_rad) * 100

                valid_slope = slope[~np.isnan(slope)]
                stats = {
                    "min": float(np.min(valid_slope)),
                    "max": float(np.max(valid_slope)),
                    "mean": float(np.mean(valid_slope)),
                    "std": float(np.std(valid_slope)),
                }

                if units == "degrees":
                    sz = slope.size
                    slope_classes = {
                        "flat (0-5°)": float(np.sum(slope < 5) / sz * 100),
                        "gentle (5-15°)": float(np.sum((slope >= 5) & (slope < 15)) / sz * 100),
                        "moderate (15-30°)": float(
                            np.sum((slope >= 15) & (slope < 30)) / sz * 100
                        ),
                        "steep (30-45°)": float(np.sum((slope >= 30) & (slope < 45)) / sz * 100),
                        "very steep (>45°)": float(np.sum(slope >= 45) / sz * 100),
                    }
                else:
                    slope_classes = None

                output_file = None
                if out_path is not None:
                    profile = src.profile.copy()
                    profile.update(dtype=rasterio.float32, count=1, nodata=-9999)
                    with rasterio.open(str(out_path), 'w', **profile) as dst:
                        dst.write(slope.astype(np.float32), 1)
                    output_file = str(out_path)

                data = {
                    "statistics": stats,
                    "units": units,
                    "shape": list(slope.shape),
                }
                if slope_classes:
                    data["slope_classes_percent"] = slope_classes
                if output_file:
                    data["output_file"] = output_file

                return make_success_response(data, {"dem_path": str(dem)})
        except Exception as e:
            logger.exception(f"Error calculating slope: {e}")
            return make_error_response(f"Slope calculation failed: {str(e)}")

    return await asyncio.to_thread(_work)


async def zonal_statistics(
    raster_path: str,
    zones_path: str,
    band: int = 1,
    stats: list[str] | None = None
) -> dict[str, Any]:
    """Calculate zonal statistics for a raster using vector zones."""
    error = _check_rasterio()
    if error is not None:
        return error

    try:
        import geopandas as gpd
        from rasterio.mask import mask
    except ImportError:
        return make_error_response(
            "GeoPandas required for zonal statistics. Install with: pip install geopandas"
        )

    try:
        rpath = _resolve(raster_path, must_exist=True)
        zpath = _resolve(zones_path, must_exist=True)
    except PathSecurityError as e:
        return make_error_response(str(e))

    requested_stats = stats if stats is not None else ["min", "max", "mean", "std", "sum", "count"]

    def _work() -> dict[str, Any]:
        try:
            zones_gdf = gpd.read_file(str(zpath))
            results = []

            with rasterio.open(str(rpath)) as src:
                if zones_gdf.crs and src.crs and zones_gdf.crs != src.crs:
                    zones_gdf = zones_gdf.to_crs(src.crs)

                for idx, row in zones_gdf.iterrows():
                    geom = [row.geometry.__geo_interface__]
                    try:
                        out_image, _ = mask(src, geom, crop=True, nodata=src.nodata)
                        data = out_image[band - 1]

                        if src.nodata is not None:
                            valid_data = data[data != src.nodata]
                        else:
                            valid_data = data.flatten()

                        zone_stats: dict[str, Any] = {"zone_id": idx}
                        if len(valid_data) > 0:
                            if "min" in requested_stats:
                                zone_stats["min"] = float(np.min(valid_data))
                            if "max" in requested_stats:
                                zone_stats["max"] = float(np.max(valid_data))
                            if "mean" in requested_stats:
                                zone_stats["mean"] = float(np.mean(valid_data))
                            if "std" in requested_stats:
                                zone_stats["std"] = float(np.std(valid_data))
                            if "sum" in requested_stats:
                                zone_stats["sum"] = float(np.sum(valid_data))
                            if "count" in requested_stats:
                                zone_stats["count"] = int(len(valid_data))
                            if "median" in requested_stats:
                                zone_stats["median"] = float(np.median(valid_data))
                        else:
                            zone_stats["no_data"] = True

                        results.append(zone_stats)
                    except Exception as zone_error:
                        results.append({"zone_id": idx, "error": str(zone_error)})

            data = {
                "zone_count": len(results),
                "statistics_computed": requested_stats,
                "zones": results,
            }
            return make_success_response(data, {
                "raster_path": str(rpath),
                "zones_path": str(zpath),
                "band": band,
            })
        except Exception as e:
            logger.exception(f"Error computing zonal statistics: {e}")
            return make_error_response(f"Zonal statistics failed: {str(e)}")

    return await asyncio.to_thread(_work)


async def reproject_raster(
    input_path: str,
    output_path: str,
    target_crs: str,
    resampling_method: str = "nearest"
) -> dict[str, Any]:
    """Reproject a raster to a different coordinate reference system."""
    error = _check_rasterio()
    if error is not None:
        return error

    resampling_methods = {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
        "cubic_spline": Resampling.cubic_spline,
        "lanczos": Resampling.lanczos,
        "average": Resampling.average,
        "mode": Resampling.mode,
    }

    if resampling_method not in resampling_methods:
        return make_error_response(
            f"Invalid resampling method. Valid options: {list(resampling_methods.keys())}"
        )

    try:
        in_path = _resolve(input_path, must_exist=True)
        out_path = _resolve(output_path, must_exist=False)
    except PathSecurityError as e:
        return make_error_response(str(e))

    def _work() -> dict[str, Any]:
        try:
            from rasterio.crs import CRS

            with rasterio.open(str(in_path)) as src:
                dst_crs = CRS.from_string(target_crs)
                transform, width, height = calculate_default_transform(
                    src.crs, dst_crs, src.width, src.height, *src.bounds
                )
                kwargs = src.meta.copy()
                kwargs.update({
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height,
                })
                source_crs = str(src.crs)
                orig_w, orig_h = src.width, src.height

                with rasterio.open(str(out_path), 'w', **kwargs) as dst:
                    for i in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, i),
                            destination=rasterio.band(dst, i),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=dst_crs,
                            resampling=resampling_methods[resampling_method],
                        )

            data = {
                "output_file": str(out_path),
                "source_crs": source_crs,
                "target_crs": target_crs,
                "original_size": {"width": orig_w, "height": orig_h},
                "new_size": {"width": width, "height": height},
                "resampling_method": resampling_method,
            }
            return make_success_response(data, {"input_path": str(in_path)})
        except Exception as e:
            logger.exception(f"Error reprojecting raster: {e}")
            return make_error_response(f"Reprojection failed: {str(e)}")

    return await asyncio.to_thread(_work)


async def raster_calculator(
    expression: str,
    rasters: dict[str, str],
    output_path: str,
    band: int = 1
) -> dict[str, Any]:
    """Perform raster algebra using a mathematical expression."""
    error = _check_rasterio()
    if error is not None:
        return error

    # Whitelist characters (no underscores/brackets → no dunder access in eval).
    allowed_chars = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-*/()., "
    )
    if not set(expression).issubset(allowed_chars):
        return make_error_response("Expression contains invalid characters")

    try:
        resolved = {var: _resolve(path, must_exist=True) for var, path in rasters.items()}
        out_path = _resolve(output_path, must_exist=False)
    except PathSecurityError as e:
        return make_error_response(str(e))

    def _work() -> dict[str, Any]:
        try:
            raster_data = {}
            profile = None
            for var, path in resolved.items():
                with rasterio.open(str(path)) as src:
                    raster_data[var] = src.read(band).astype(np.float32)
                    if profile is None:
                        profile = src.profile.copy()
                        profile.update(dtype=rasterio.float32, count=1)

            if profile is None:
                return make_error_response("No valid raster data found")

            result = eval(expression, {"__builtins__": {}, "np": np}, raster_data)

            nodata_value = profile.get("nodata")
            if nodata_value is None:
                nodata_value = -9999
            result = np.where(np.isfinite(result), result, nodata_value)

            with rasterio.open(str(out_path), 'w', **profile) as dst:
                dst.write(result.astype(np.float32), 1)

            valid_result = result[np.isfinite(result)]
            stats = {
                "min": float(np.min(valid_result)) if len(valid_result) > 0 else None,
                "max": float(np.max(valid_result)) if len(valid_result) > 0 else None,
                "mean": float(np.mean(valid_result)) if len(valid_result) > 0 else None,
            }

            data = {
                "output_file": str(out_path),
                "expression": expression,
                "input_rasters": {var: str(p) for var, p in resolved.items()},
                "statistics": stats,
                "shape": list(result.shape),
            }
            return make_success_response(data, {})
        except Exception as e:
            logger.exception(f"Error in raster calculation: {e}")
            return make_error_response(f"Raster calculation failed: {str(e)}")

    return await asyncio.to_thread(_work)
