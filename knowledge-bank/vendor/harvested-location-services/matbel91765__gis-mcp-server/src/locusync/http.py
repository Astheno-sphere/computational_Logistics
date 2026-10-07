"""Shared aiohttp session with connection pooling.

Creating a new ``aiohttp.ClientSession`` per request (the previous behaviour)
disables keep-alive and connection reuse. This module exposes a single lazily
created session, bound to the running event loop, reused across all outbound
HTTP calls (Nominatim, OSRM, elevation, ...).
"""

import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)

_session: aiohttp.ClientSession | None = None
_lock = asyncio.Lock()


async def get_session() -> aiohttp.ClientSession:
    """Return the shared session, creating it on first use."""
    global _session
    if _session is None or _session.closed:
        async with _lock:
            if _session is None or _session.closed:
                connector = aiohttp.TCPConnector(
                    limit=50,            # total concurrent connections
                    limit_per_host=10,
                    ttl_dns_cache=300,   # cache DNS resolutions for 5 min
                    enable_cleanup_closed=True,
                )
                _session = aiohttp.ClientSession(
                    connector=connector,
                    raise_for_status=False,
                )
                logger.debug("Created shared aiohttp session")
    return _session


async def close_session() -> None:
    """Close the shared session (call on shutdown)."""
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        logger.debug("Closed shared aiohttp session")
    _session = None
