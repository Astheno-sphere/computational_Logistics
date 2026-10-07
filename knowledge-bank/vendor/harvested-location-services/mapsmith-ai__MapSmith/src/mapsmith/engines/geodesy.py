"""Read-only answers about coordinate systems and distances on the ellipsoid.

Neither operation here writes a dataset, so neither emits a manifest: there is
no output whose lineage could be questioned later, and a provenance file beside
nothing would be a claim about nothing.

Both exist because of the same recurring failure. Most wrong numbers in agent
GIS are not wrong arithmetic; they are right arithmetic in the wrong units, in
the wrong axis order, or across a projection whose distortion nobody looked up.
`describe_crs` answers "what am I actually holding" before an operation, and
`geodetic_distance` answers "how far apart are these two places" without
choosing a projection at all -- which is the only way to answer it that a
projection cannot spoil.
"""

from __future__ import annotations

from typing import Any

from pyproj import CRS, Geod
from pyproj.exceptions import CRSError

# The ellipsoids a caller is plausibly asked to reproduce a legacy number on.
# Named rather than free-form so a typo is refused instead of silently falling
# back to WGS84, which would change the answer by hundreds of metres over long
# lines while still looking like a distance.
ELLIPSOIDS = {
    "WGS84": "WGS84",
    "GRS80": "GRS80",
    "WGS72": "WGS72",
    "intl": "intl",  # International 1924 / Hayford: Monte Mario and much of Europe
    "clrk66": "clrk66",  # Clarke 1866: NAD27
    "airy": "airy",  # Airy 1830: OSGB36
    "bessel": "bessel",
}


def describe_crs(crs: str | int) -> dict[str, Any]:
    """Everything about a CRS that changes the meaning of a number computed in it.

    Accepts anything pyproj accepts: `"EPSG:4326"`, `4326`, a PROJ string, a WKT.

    The four fields worth reading before anything else, because each one turns a
    plausible number into a wrong one on its own:

    - `axis_order` -- `"lat,lon"` or `"lon,lat"`. EPSG:4326 declares LATITUDE
      first, most software and every GeoJSON file put longitude first, and
      swapping them puts Rome in the Indian Ocean or, worse, somewhere merely
      implausible. This reports what the CRS actually declares, not the habit.
    - `unit` and `unit_to_metre` -- a length or area computed in EPSG:2263 comes
      out in US survey feet, and 0.3048006096012192 is not 0.3048: over a state
      plane that difference is metres, and it is the reason `measure_area` reads
      the unit from the CRS instead of assuming.
    - `kind` -- geographic or projected. A distance or an area computed in a
      geographic CRS is in degrees, which is not a length at any latitude.
    - `area_of_use` -- outside it, a projected CRS still returns numbers, and a
      datum transformation may silently fall back to a ballpark one.

    `is_deprecated` is reported too: superseded EPSG codes keep working, and keep
    giving the answer their superseded definition implies.
    """
    try:
        parsed = CRS.from_user_input(crs)
    except CRSError as error:
        raise ValueError(
            f"{crs!r} is not a CRS pyproj can read: {error}. Accepted forms include "
            "'EPSG:4326', the bare code 4326, a PROJ string, or WKT."
        ) from error

    axes = [
        {
            "name": axis.name,
            "abbrev": axis.abbrev,
            "direction": axis.direction,
            "unit": axis.unit_name,
            "unit_to_metre": axis.unit_conversion_factor,
        }
        for axis in parsed.axis_info
    ]
    horizontal = [a for a in axes if a["direction"] in ("north", "south", "east", "west")]
    if len(horizontal) >= 2:
        first = horizontal[0]["direction"]
        axis_order = "lat,lon" if first in ("north", "south") else "lon,lat"
    else:
        axis_order = None

    unit = horizontal[0]["unit"] if horizontal else None
    factor = horizontal[0]["unit_to_metre"] if horizontal else None
    if horizontal and len({a["unit"] for a in horizontal}) > 1:
        # Mixed horizontal units are legal and pathological; naming one would be
        # a lie, so the field says so instead.
        unit = "mixed: " + ", ".join(a["unit"] for a in horizontal)
        factor = None

    ellipsoid = parsed.ellipsoid
    datum = parsed.datum
    extent = parsed.area_of_use
    authority = parsed.to_authority()
    operation = parsed.coordinate_operation

    return {
        "input": str(crs),
        "name": parsed.name,
        "authority": f"{authority[0]}:{authority[1]}" if authority else None,
        "kind": "geographic"
        if parsed.is_geographic
        else "projected"
        if parsed.is_projected
        else "compound"
        if parsed.is_compound
        else "other",
        "axis_order": axis_order,
        "axes": axes,
        "unit": unit,
        "unit_to_metre": factor,
        "is_geographic": parsed.is_geographic,
        "is_projected": parsed.is_projected,
        "is_deprecated": bool(getattr(parsed, "is_deprecated", False)),
        "datum": datum.name if datum else None,
        "ellipsoid": {
            "name": ellipsoid.name,
            "semi_major_metre": ellipsoid.semi_major_metre,
            "inverse_flattening": ellipsoid.inverse_flattening,
        }
        if ellipsoid
        else None,
        "prime_meridian": parsed.prime_meridian.name if parsed.prime_meridian else None,
        "projection_method": operation.method_name if operation else None,
        "area_of_use": {"name": extent.name, "bounds": list(extent.bounds)}
        if extent
        else None,
        "epsg": parsed.to_epsg(),
    }


def geodetic_distance(
    from_lon: float,
    from_lat: float,
    to_lon: float,
    to_lat: float,
    ellipsoid: str = "WGS84",
) -> dict[str, Any]:
    """Distance and azimuths between two lon/lat points, measured on the ellipsoid.

    This is the answer that no projection can spoil. A distance computed in a
    projected CRS is a distance on that projection's plane, and the two differ by
    a factor that grows with latitude -- at 42 degrees, Web Mercator is off by
    about 1.8x, and the number it returns is in metres and looks correct. Here
    there is no plane: Karney's algorithm measures along the ellipsoid, and the
    answer is accurate to nanometres for any pair of points on Earth.

    Coordinates are LONGITUDE FIRST, which is stated in the parameter names
    rather than in a comment because the swap is the single most common error in
    this signature and it produces a valid number for the wrong two places.
    Latitudes outside +-90 are refused for the same reason: pyproj would return
    a number for a latitude of 100, and there is no such place.

    Returns metres, plus the forward and back azimuths in degrees clockwise from
    north -- the forward azimuth is the bearing to walk at the start, not for the
    whole way: on a geodesic it changes continuously except along the equator and
    the meridians.
    """
    if ellipsoid not in ELLIPSOIDS:
        raise ValueError(
            f"ellipsoid must be one of {sorted(ELLIPSOIDS)}, got {ellipsoid!r}. "
            "It is not a free-form field: an unrecognised name silently falling back "
            "to WGS84 would move a legacy answer by hundreds of metres."
        )
    for label, value in (
        ("from_lat", from_lat),
        ("to_lat", to_lat),
    ):
        if not -90.0 <= float(value) <= 90.0:
            raise ValueError(
                f"{label}={value} is not a latitude. Coordinates here are longitude "
                "first: geodetic_distance(from_lon, from_lat, to_lon, to_lat)."
            )
    for label, value in (
        ("from_lon", from_lon),
        ("to_lon", to_lon),
    ):
        if not -180.0 <= float(value) <= 180.0:
            raise ValueError(
                f"{label}={value} is outside [-180, 180]. Coordinates here are "
                "longitude first: geodetic_distance(from_lon, from_lat, to_lon, to_lat)."
            )

    geod = Geod(ellps=ELLIPSOIDS[ellipsoid])
    forward, back, metres = geod.inv(from_lon, from_lat, to_lon, to_lat)
    return {
        "distance_metres": float(metres),
        "forward_azimuth_degrees": float(forward),
        "back_azimuth_degrees": float(back),
        "ellipsoid": ellipsoid,
        "semi_major_metre": geod.a,
        "flattening": geod.f,
        "from": [float(from_lon), float(from_lat)],
        "to": [float(to_lon), float(to_lat)],
        "method": "geodesic on the ellipsoid (Karney); no projection involved",
    }
