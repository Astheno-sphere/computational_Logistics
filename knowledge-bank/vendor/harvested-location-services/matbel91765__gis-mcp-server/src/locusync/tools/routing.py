"""Routing tools for GIS MCP Server."""

import logging
import math
from typing import Any, cast

import aiohttp

from locusync.cache import cached
from locusync.config import get_config
from locusync.http import get_session
from locusync.utils import (
    format_distance,
    format_duration,
    make_error_response,
    make_success_response,
    retry_async,
    validate_coordinates,
)

logger = logging.getLogger(__name__)


PROFILE_MAP = {
    "driving": "car",
    "car": "car",
    "walking": "foot",
    "foot": "foot",
    "pedestrian": "foot",
    "cycling": "bike",
    "bike": "bike",
    "bicycle": "bike",
}


def _normalize_profile(profile: str) -> str | None:
    """Normalize routing profile name to OSRM format.

    Args:
        profile: User-provided profile name.

    Returns:
        Normalized profile name or None if invalid.
    """
    return PROFILE_MAP.get(profile.lower())


async def _osrm_request(
    service: str,
    coordinates: list[tuple[float, float]],
    profile: str = "car",
    **params: Any
) -> dict[str, Any]:
    """Make a request to OSRM API.

    Args:
        service: OSRM service (route, table, nearest, etc.).
        coordinates: List of (lon, lat) tuples.
        profile: Routing profile.
        **params: Additional query parameters.

    Returns:
        JSON response from OSRM.
    """
    config = get_config()

    # Build coordinates string: lon,lat;lon,lat
    coords_str = ";".join(f"{lon},{lat}" for lon, lat in coordinates)

    url = f"{config.osrm.base_url}/{service}/v1/{profile}/{coords_str}"

    session = await get_session()
    async with session.get(
        url,
        params=params,
        timeout=aiohttp.ClientTimeout(total=config.osrm.timeout)
    ) as response:
        response.raise_for_status()
        return cast(dict[str, Any], await response.json())


@cached("route", key_args=("start_lat", "start_lon", "end_lat", "end_lon", "profile"))
async def calculate_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    profile: str = "driving"
) -> dict[str, Any]:
    """Calculate a route between two points.

    Args:
        start_lat: Start point latitude.
        start_lon: Start point longitude.
        end_lat: End point latitude.
        end_lon: End point longitude.
        profile: Routing profile (driving, walking, cycling).

    Returns:
        GIS response with route details.
    """
    # Validate coordinates
    for lat, lon, name in [(start_lat, start_lon, "start"), (end_lat, end_lon, "end")]:
        is_valid, error = validate_coordinates(lat, lon)
        if not is_valid:
            return make_error_response(f"Invalid {name} point: {error}")

    normalized_profile = _normalize_profile(profile)
    if not normalized_profile:
        return make_error_response(
            f"Invalid profile '{profile}'. Use 'driving', 'walking', or 'cycling'."
        )

    # OSRM demo server only supports driving
    # For walking/cycling, we'd need a different server
    osrm_profile = "driving" if normalized_profile == "car" else normalized_profile

    try:
        coordinates = [(start_lon, start_lat), (end_lon, end_lat)]

        async def do_request() -> dict[str, Any]:
            return await _osrm_request(
                "route",
                coordinates,
                profile=osrm_profile,
                overview="full",
                geometries="geojson",
                steps="true",
            )

        result = await retry_async(do_request, max_retries=3)

        if result.get("code") != "Ok":
            return make_error_response(
                f"Routing failed: {result.get('message', 'Unknown error')}",
                metadata={"osrm_code": result.get("code")}
            )

        routes = result.get("routes", [])
        if not routes:
            return make_error_response("No route found between the given points")

        route = routes[0]

        # Build route geometry as GeoJSON LineString
        geometry = route.get("geometry", {})

        # Extract turn-by-turn instructions
        steps = []
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                steps.append({
                    "instruction": step.get("maneuver", {}).get("instruction", ""),
                    "distance_m": step.get("distance", 0),
                    "duration_s": step.get("duration", 0),
                    "name": step.get("name", ""),
                    "mode": step.get("mode", ""),
                })

        data = {
            "distance": format_distance(route.get("distance", 0)),
            "duration": format_duration(route.get("duration", 0)),
            "geometry": geometry,
            "steps": steps,
            "start": {"lat": start_lat, "lon": start_lon},
            "end": {"lat": end_lat, "lon": end_lon},
        }

        metadata = {
            "source": "osrm",
            "profile": profile,
            "waypoints": len(coordinates),
        }

        return make_success_response(data, metadata)

    except aiohttp.ClientError as e:
        logger.error(f"Network error during routing: {e}")
        return make_error_response(
            f"Network error: Unable to reach routing service. {str(e)}",
            metadata={"source": "osrm"}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during routing: {e}")
        return make_error_response(
            f"Routing failed: {str(e)}",
            metadata={"source": "osrm"}
        )


MATRIX_MAX_POINTS = 25


@cached("distance_matrix", key_args=("points", "profile"))
async def calculate_distance_matrix(
    points: list[list[float]],
    profile: str = "driving"
) -> dict[str, Any]:
    """Compute a full duration+distance matrix between points (OSRM table service).

    Args:
        points: List of [lat, lon] pairs (2 to 25 points).
        profile: Routing profile (driving, walking, cycling).

    Returns:
        GIS response with durations (s) and distances (m) matrices.
    """
    if not isinstance(points, list) or len(points) < 2:
        return make_error_response("At least 2 points are required")
    if len(points) > MATRIX_MAX_POINTS:
        return make_error_response(
            f"Too many points ({len(points)}). Maximum is {MATRIX_MAX_POINTS}."
        )

    for i, pt in enumerate(points):
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return make_error_response(f"Point {i} must be a [lat, lon] pair")
        is_valid, error = validate_coordinates(pt[0], pt[1])
        if not is_valid:
            return make_error_response(f"Invalid point {i}: {error}")

    normalized_profile = _normalize_profile(profile)
    if not normalized_profile:
        return make_error_response(
            f"Invalid profile '{profile}'. Use 'driving', 'walking', or 'cycling'."
        )

    try:
        coordinates = [(lon, lat) for lat, lon in points]

        async def do_request() -> dict[str, Any]:
            return await _osrm_request(
                "table",
                coordinates,
                profile="driving",  # OSRM demo only serves the driving profile
                annotations="duration,distance",
            )

        result = await retry_async(do_request, max_retries=2)

        if result.get("code") != "Ok":
            return make_error_response(
                f"Distance matrix failed: {result.get('message', 'Unknown error')}",
                metadata={"osrm_code": result.get("code")},
            )

        data = {
            "durations_seconds": result.get("durations"),
            "distances_meters": result.get("distances"),
            "point_count": len(points),
        }
        metadata = {"source": "osrm", "profile": profile, "annotations": ["duration", "distance"]}
        return make_success_response(data, metadata)

    except aiohttp.ClientError as e:
        logger.error(f"Network error during distance matrix: {e}")
        return make_error_response(
            f"Network error: Unable to reach routing service. {str(e)}",
            metadata={"source": "osrm"},
        )
    except Exception as e:
        logger.exception(f"Unexpected error during distance matrix: {e}")
        return make_error_response(f"Distance matrix failed: {str(e)}", metadata={"source": "osrm"})


async def calculate_isochrone(
    lat: float,
    lon: float,
    time_minutes: int,
    profile: str = "driving"
) -> dict[str, Any]:
    """Calculate an isochrone (area reachable within time limit).

    This implementation uses OSRM's table service to sample reachable points
    and creates an approximate isochrone polygon. For production, consider
    using Valhalla which has native isochrone support.

    Args:
        lat: Center point latitude.
        lon: Center point longitude.
        time_minutes: Travel time limit in minutes.
        profile: Routing profile (driving, walking, cycling).

    Returns:
        GIS response with isochrone polygon.
    """
    is_valid, error = validate_coordinates(lat, lon)
    if not is_valid:
        return make_error_response(f"Invalid center point: {error}")

    if time_minutes < 1 or time_minutes > 120:
        return make_error_response("Time must be between 1 and 120 minutes")

    normalized_profile = _normalize_profile(profile)
    if not normalized_profile:
        return make_error_response(
            f"Invalid profile '{profile}'. Use 'driving', 'walking', or 'cycling'."
        )

    try:
        # Estimate max distance based on profile and time
        # These are rough estimates for generating sample points
        speed_kmh = {
            "car": 60,
            "foot": 5,
            "bike": 20,
        }
        max_distance_km = speed_kmh.get(normalized_profile, 60) * (time_minutes / 60) * 1.5

        # Generate sample points in a grid around the center
        sample_points = _generate_sample_points(
            lat, lon, max_distance_km, num_rings=8, points_per_ring=16
        )

        # Include center point
        coordinates = [(lon, lat)] + sample_points

        # OSRM demo server only supports driving
        osrm_profile = "driving"

        async def do_request() -> dict[str, Any]:
            return await _osrm_request(
                "table",
                coordinates,
                profile=osrm_profile,
                sources="0",  # Only from center point
            )

        result = await retry_async(do_request, max_retries=2)

        if result.get("code") != "Ok":
            return make_error_response(
                f"Isochrone calculation failed: {result.get('message', 'Unknown error')}",
                metadata={"osrm_code": result.get("code")}
            )

        # Get durations from center to all points
        durations = result.get("durations", [[]])[0]
        time_limit_seconds = time_minutes * 60

        # Filter reachable points
        reachable_points = []
        for i, duration in enumerate(durations[1:], 1):  # Skip center point
            if duration is not None and duration <= time_limit_seconds:
                point_lon, point_lat = coordinates[i]
                reachable_points.append((point_lon, point_lat))

        if len(reachable_points) < 3:
            return make_error_response(
                "Not enough reachable points to create isochrone polygon",
                metadata={"reachable_count": len(reachable_points)}
            )

        # Create convex hull of reachable points
        from shapely.geometry import MultiPoint, mapping

        points = MultiPoint(reachable_points)
        hull = points.convex_hull

        # If we have enough points, try concave hull for more accuracy
        if len(reachable_points) >= 10:
            try:
                from shapely import concave_hull
                hull = concave_hull(points, ratio=0.3)
            except Exception:
                pass  # Fall back to convex hull

        data = {
            "geometry": mapping(hull),
            "center": {"lat": lat, "lon": lon},
            "time_minutes": time_minutes,
            "reachable_points": len(reachable_points),
        }

        metadata = {
            "source": "osrm",
            "profile": profile,
            "method": "sampled_points",
            "sample_count": len(coordinates),
            "note": "Approximate isochrone. For production, use Valhalla.",
        }

        return make_success_response(data, metadata)

    except aiohttp.ClientError as e:
        logger.error(f"Network error during isochrone calculation: {e}")
        return make_error_response(
            f"Network error: Unable to reach routing service. {str(e)}",
            metadata={"source": "osrm"}
        )
    except Exception as e:
        logger.exception(f"Unexpected error during isochrone calculation: {e}")
        return make_error_response(
            f"Isochrone calculation failed: {str(e)}",
            metadata={"source": "osrm"}
        )


def _generate_sample_points(
    center_lat: float,
    center_lon: float,
    max_distance_km: float,
    num_rings: int = 6,
    points_per_ring: int = 12
) -> list[tuple[float, float]]:
    """Generate sample points in concentric rings around a center.

    Args:
        center_lat: Center latitude.
        center_lon: Center longitude.
        max_distance_km: Maximum distance from center.
        num_rings: Number of concentric rings.
        points_per_ring: Points per ring.

    Returns:
        List of (lon, lat) tuples.
    """
    points = []

    for ring in range(1, num_rings + 1):
        distance_km = (ring / num_rings) * max_distance_km

        for i in range(points_per_ring):
            bearing = (360 / points_per_ring) * i

            # Calculate destination point
            lat, lon = _destination_point(center_lat, center_lon, distance_km, bearing)
            points.append((lon, lat))

    return points


def _destination_point(
    lat: float,
    lon: float,
    distance_km: float,
    bearing: float
) -> tuple[float, float]:
    """Calculate destination point given distance and bearing.

    Args:
        lat: Starting latitude.
        lon: Starting longitude.
        distance_km: Distance in kilometers.
        bearing: Bearing in degrees.

    Returns:
        Tuple of (latitude, longitude).
    """
    earth_radius_km = 6371  # Earth's radius in km

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)

    d = distance_km / earth_radius_km

    dest_lat = math.asin(
        math.sin(lat_rad) * math.cos(d) +
        math.cos(lat_rad) * math.sin(d) * math.cos(bearing_rad)
    )

    dest_lon = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(d) * math.cos(lat_rad),
        math.cos(d) - math.sin(lat_rad) * math.sin(dest_lat)
    )

    return math.degrees(dest_lat), math.degrees(dest_lon)
