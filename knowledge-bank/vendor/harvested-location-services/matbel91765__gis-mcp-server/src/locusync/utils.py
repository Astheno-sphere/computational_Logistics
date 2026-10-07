"""Utility functions for GIS MCP Server."""

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import aiohttp
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GISResponse(BaseModel):
    """Standard response format for all GIS tools."""

    success: bool
    data: dict[str, Any] | list[Any] | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None


def make_success_response(
    data: dict[str, Any] | list[Any],
    metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create a successful response."""
    return GISResponse(
        success=True,
        data=data,
        metadata=metadata,
        error=None
    ).model_dump()


def make_error_response(error: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create an error response."""
    return GISResponse(
        success=False,
        data=None,
        metadata=metadata,
        error=error
    ).model_dump()


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, min_interval: float = 1.0):
        """Initialize rate limiter.

        Args:
            min_interval: Minimum time between requests in seconds.
        """
        self.min_interval = min_interval
        self._last_request: float = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()


# Global rate limiters for different services
_nominatim_limiter = RateLimiter(min_interval=1.0)


def get_nominatim_limiter() -> RateLimiter:
    """Get the Nominatim rate limiter."""
    return _nominatim_limiter


T = TypeVar("T")


async def retry_async(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    backoff_factor: float = 1.5,
    **kwargs: Any
) -> Any:
    """Retry an async function with exponential backoff.

    Args:
        func: The async function to retry.
        *args: Positional arguments for the function.
        max_retries: Maximum number of retry attempts.
        backoff_factor: Multiplier for backoff delay.
        **kwargs: Keyword arguments for the function.

    Returns:
        The result of the function.

    Raises:
        The last exception if all retries fail.
    """
    last_exception: Exception | None = None
    delay = 1.0

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (TimeoutError, aiohttp.ClientError) as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")

    raise last_exception  # type: ignore


def validate_coordinates(lat: float, lon: float) -> tuple[bool, str | None]:
    """Validate latitude and longitude values.

    Args:
        lat: Latitude value.
        lon: Longitude value.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return False, "Coordinates must be numeric values"
    if lat < -90 or lat > 90:
        return False, f"Latitude must be between -90 and 90, got {lat}"
    if lon < -180 or lon > 180:
        return False, f"Longitude must be between -180 and 180, got {lon}"
    return True, None


def format_distance(meters: float) -> dict[str, float]:
    """Format distance in multiple units.

    Args:
        meters: Distance in meters.

    Returns:
        Dictionary with distance in various units.
    """
    return {
        "meters": round(meters, 2),
        "kilometers": round(meters / 1000, 3),
        "miles": round(meters / 1609.344, 3),
        "feet": round(meters * 3.28084, 2),
    }


def format_duration(seconds: float) -> dict[str, float]:
    """Format duration in multiple units.

    Args:
        seconds: Duration in seconds.

    Returns:
        Dictionary with duration in various units.
    """
    return {
        "seconds": round(seconds, 1),
        "minutes": round(seconds / 60, 2),
        "hours": round(seconds / 3600, 3),
    }
