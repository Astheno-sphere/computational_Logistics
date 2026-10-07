"""Elevation and terrain data tools for GIS MCP Server."""

import logging
from typing import Any, cast

import aiohttp

from locusync.cache import cached
from locusync.config import get_config
from locusync.http import get_session
from locusync.utils import (
    make_error_response,
    make_success_response,
    retry_async,
    validate_coordinates,
)

logger = logging.getLogger(__name__)


async def _open_elevation_request(locations: list[dict[str, float]]) -> dict[str, Any]:
    """Make a request to the Open-Elevation API.

    Args:
        locations: List of location dicts with 'latitude' and 'longitude' keys.

    Returns:
        API response as dictionary.

    Raises:
        aiohttp.ClientError: On network errors.
        TimeoutError: On timeout.
    """
    config = get_config()
    url = f"{config.open_elevation.base_url}/api/v1/lookup"

    session = await get_session()
    try:
        async with session.post(
            url,
            json={"locations": locations},
            timeout=aiohttp.ClientTimeout(total=config.open_elevation.timeout)
        ) as response:
            response.raise_for_status()
            return cast(dict[str, Any], await response.json())
    except aiohttp.ClientError as e:
        logger.error(f"Open-Elevation API request failed: {e}")
        raise
    except TimeoutError as e:
        logger.error(f"Open-Elevation API request timed out: {e}")
        raise


@cached("elevation", key_args=("lat", "lon"))
async def get_elevation(lat: float, lon: float) -> dict[str, Any]:
    """Get elevation for a single point.

    Args:
        lat: Latitude of the point.
        lon: Longitude of the point.

    Returns:
        GIS response with elevation data in meters.
    """
    # Validate coordinates
    is_valid, error = validate_coordinates(lat, lon)
    if not is_valid:
        return make_error_response(f"Invalid coordinates: {error}")

    try:
        # Make request to Open-Elevation API
        locations = [{"latitude": lat, "longitude": lon}]

        async def do_request() -> dict[str, Any]:
            return await _open_elevation_request(locations)

        response = await retry_async(do_request)

        if "results" not in response or not response["results"]:
            return make_error_response("No elevation data returned from API")

        result = response["results"][0]
        elevation = result.get("elevation")

        if elevation is None:
            return make_error_response("Elevation data not available for this location")

        data = {
            "elevation_meters": round(elevation, 2),
            "location": {
                "lat": lat,
                "lon": lon
            }
        }

        metadata = {
            "source": "open-elevation",
            "dataset": "SRTM (Shuttle Radar Topography Mission)",
        }

        return make_success_response(data, metadata)

    except (aiohttp.ClientError, TimeoutError) as e:
        logger.exception(f"Error getting elevation: {e}")
        return make_error_response(f"Failed to get elevation data: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting elevation: {e}")
        return make_error_response(f"Elevation lookup failed: {str(e)}")


async def get_elevation_profile(coordinates: list[list[float]]) -> dict[str, Any]:
    """Get elevations along a path defined by coordinates.

    Args:
        coordinates: List of [lon, lat] pairs defining the path.

    Returns:
        GIS response with elevation profile data.
    """
    if not coordinates or len(coordinates) < 2:
        return make_error_response(
            "At least 2 coordinate pairs are required for an elevation profile"
        )

    if len(coordinates) > 100:
        return make_error_response(
            "Maximum 100 coordinate pairs allowed for elevation profile"
        )

    # Validate all coordinates
    for i, coord in enumerate(coordinates):
        if len(coord) != 2:
            return make_error_response(
                f"Coordinate at index {i} must be [lon, lat] pair"
            )

        lon, lat = coord
        is_valid, error = validate_coordinates(lat, lon)
        if not is_valid:
            return make_error_response(
                f"Invalid coordinates at index {i}: {error}"
            )

    try:
        # Convert to Open-Elevation API format
        locations = [
            {"latitude": lat, "longitude": lon}
            for lon, lat in coordinates
        ]

        # Make request to Open-Elevation API
        async def do_request() -> dict[str, Any]:
            return await _open_elevation_request(locations)

        response = await retry_async(do_request)

        if "results" not in response or not response["results"]:
            return make_error_response("No elevation data returned from API")

        # Process results
        profile = []
        elevations = []

        for i, result in enumerate(response["results"]):
            elevation = result.get("elevation")

            if elevation is None:
                logger.warning(f"No elevation data for point {i}")
                elevation = None
            else:
                elevation = round(elevation, 2)
                elevations.append(elevation)

            lon, lat = coordinates[i]
            profile.append({
                "index": i,
                "location": {"lat": lat, "lon": lon},
                "elevation_meters": elevation
            })

        # Calculate statistics
        stats = None
        if elevations:
            stats = {
                "min_elevation_meters": round(min(elevations), 2),
                "max_elevation_meters": round(max(elevations), 2),
                "elevation_gain_meters": round(max(elevations) - min(elevations), 2),
                "avg_elevation_meters": round(sum(elevations) / len(elevations), 2),
            }

        data = {
            "profile": profile,
            "statistics": stats,
            "total_points": len(profile),
        }

        metadata = {
            "source": "open-elevation",
            "dataset": "SRTM (Shuttle Radar Topography Mission)",
        }

        return make_success_response(data, metadata)

    except (aiohttp.ClientError, TimeoutError) as e:
        logger.exception(f"Error getting elevation profile: {e}")
        return make_error_response(f"Failed to get elevation profile: {str(e)}")
    except Exception as e:
        logger.exception(f"Unexpected error getting elevation profile: {e}")
        return make_error_response(f"Elevation profile lookup failed: {str(e)}")
