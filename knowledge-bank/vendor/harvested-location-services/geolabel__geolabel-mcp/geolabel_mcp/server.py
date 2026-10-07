"""
GeoLabel MCP Server
===================
Turn GPS coordinates into AI-ready location context for Claude and any
MCP-compatible assistant. Wraps the GeoLabel API (geolabel.dev).

Configuration (environment variables):
    GEOLABEL_API_KEY   Your GeoLabel API key (required). Get one free at geolabel.dev.
    GEOLABEL_BASE_URL  Override the API base URL (optional).
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_API_KEY  = os.getenv("GEOLABEL_API_KEY", "")
_BASE_URL = os.getenv("GEOLABEL_BASE_URL", "https://api.geolabel.dev").rstrip("/")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="GeoLabel",
    instructions=(
        "GeoLabel converts GPS coordinates into a human-friendly place name, "
        "a stable category (gym, supermarket, restaurant, gas_station, pharmacy …), "
        "and real-time opening-hours status. "
        "Call get_location_label whenever the user shares coordinates or asks "
        "what is at a specific location. "
        "Use 'category' for decisions, 'label' for display, and the hours "
        "fields (is_open, closes_at, opens_at) to answer time-sensitive questions. "
        "If is_open is null the place has no hours data in OpenStreetMap — "
        "do not guess; tell the user hours are unavailable for that location."
    ),
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_location_label(lat: float, lng: float, radius: int = 100) -> dict:
    """
    Identify a place from GPS coordinates and return its label, category,
    and live opening-hours status.

    Use this whenever the user provides coordinates or asks what is at a
    location. The response gives Claude everything needed to answer
    location-aware questions — place name, type, whether it is open right
    now, and when it closes or next opens.

    Args:
        lat:    Latitude in decimal degrees (-90 to 90).
        lng:    Longitude in decimal degrees (-180 to 180).
        radius: Search radius in metres. Smaller values pin to the nearest
                place precisely; larger values cast a wider net.
                Default 100 m, maximum 500 m.

    Returns a dict with:
        place           Raw venue name from OpenStreetMap (may include branch
                        numbers or location suffixes). Prefer 'label' for display.
        label           Clean, user-friendly name — e.g. "Walmart", "Planet Fitness",
                        "Starbucks". Use this for display and speech.
        category        Stable place type for logic: "gym", "supermarket",
                        "restaurant", "fast_food", "gas_station", "pharmacy",
                        "hospital", "cafe", "retail", etc.
        distance_meters Distance in metres from the supplied coordinates to the
                        matched place centroid.
        is_open         true  → currently open.
                        false → currently closed.
                        null  → OpenStreetMap has no hours data for this place.
        opens_at        Next opening time as "HH:MM" (24-hour). Populated when
                        is_open is false so you know when it reopens.
                        null when open, or when hours are unknown.
        closes_at       Today's closing time as "HH:MM" (24-hour). Populated when
                        is_open is true — subtract current time to get minutes
                        remaining. null when closed or hours unknown.
        opening_hours   Raw OpenStreetMap opening_hours string, e.g.
                        "Mo-Fr 09:00-18:00; Sa 10:00-17:00". null if not set in OSM.
        cached          true if place data was served from the 10-minute in-memory
                        cache. Hours fields are always recalculated live against
                        the current time, even on cache hits.
    """
    if not _API_KEY:
        return {
            "error": (
                "GEOLABEL_API_KEY is not configured. "
                "Get a free API key at https://geolabel.dev and add it to your "
                "MCP server environment as GEOLABEL_API_KEY."
            )
        }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.get(
                f"{_BASE_URL}/label",
                headers={"X-API-Key": _API_KEY},
                params={"lat": lat, "lng": lng, "radius": radius},
            )
            r.raise_for_status()
            return r.json()

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                return {
                    "error": (
                        "Invalid API key. Verify GEOLABEL_API_KEY or "
                        "generate a new key at https://geolabel.dev."
                    )
                }
            if status == 429:
                return {
                    "error": (
                        "Rate limit reached. Upgrade your plan at "
                        "https://geolabel.dev for higher limits."
                    )
                }
            if status == 422:
                return {
                    "error": (
                        f"Invalid parameters: lat={lat}, lng={lng}, radius={radius}. "
                        "Latitude must be -90–90, longitude -180–180, radius 10–500."
                    )
                }
            if status == 502:
                return {
                    "error": (
                        "OpenStreetMap data is temporarily unavailable. "
                        "Try again in a moment."
                    )
                }
            return {"error": f"GeoLabel API returned HTTP {status}."}

        except httpx.TimeoutException:
            return {
                "error": (
                    "Request timed out after 15 s. "
                    "The service may be briefly slow — try again."
                )
            }

        except Exception as exc:  # noqa: BLE001
            return {"error": f"Unexpected error: {exc}"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
