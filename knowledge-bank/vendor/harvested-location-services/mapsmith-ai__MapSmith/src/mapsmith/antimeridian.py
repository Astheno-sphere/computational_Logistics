"""What a bounding box means when the data crosses the 180th meridian.

A survey zone two degrees wide in Fijian waters has a bounding box of
`(-180, -17.5, 180, -16.5)` — a band right around the planet — and every part of
that is arithmetically correct. The minimum longitude in the file really is
-180 and the maximum really is 180.

It is correct and it is the wrong answer to the question anybody asked, which is
the shape of failure this whole project exists to name. So an extent is reported
with the sentence that makes it readable rather than left to be misread.

## Why the two halves of the standard do not compose

RFC 7946 §3.1.9 says a geometry crossing the antimeridian **should** be split
into two parts at it, with every coordinate inside [-180, 180]. §5.2 then defines
a bounding box whose western value exceeds its eastern one as the one that
crosses.

A geometry split correctly per the first has parts that reach -180 and +180, so
the bounds *computed* from its coordinates come out as the ordinary
(west < east) form spanning the planet — never the §5.2 form. Nothing in a
planar geometry library computes anything else: shapely, GEOS and PostGIS all
work in a plane where longitude is an ordinary number, and the inverted-bbox
convention has no representation there.

Both halves are right and they do not meet. This module is the bridge: it
notices the case and reports the §5.2 form alongside the plain one.

## The rule

Two spans are computed from the per-feature bounds:

* **plain** — `max(x) - min(x)`, what every library reports.
* **wrapped** — the same over `x mod 360`, which puts the two sides of the
  antimeridian next to each other.

A layer crosses when three things hold together:

1. the wrapped span is **smaller** than the plain one — the data reads as
   narrower when the seam is treated as continuous;
2. the wrapped span is **under 180°** — the data occupies less than half the
   world going the short way round. This is what separates a zone at the seam
   from data that is simply spread everywhere: points at -179, -90, 0, 90 and
   179 also wrap to a narrower span, and calling that a crossing would be
   noise on a global dataset;
3. **the geometry does not reach into the gap.** One rectangle covering the
   world has exactly two longitudes in it, -180 and 180, which wrap onto the
   same value — so its wrapped span is 0 and by arithmetic alone it is the most
   convincing crossing there is. The difference is not in the coordinates, it is
   in what lies between them, so a meridian is drawn through the middle of the
   apparent empty band and the layer is asked whether anything is there.

There is deliberately **no threshold on the plain span**. An earlier version
required it to exceed 350° before looking any further, which sounds like a cheap
guard and is a blindfold: it only ever fires on data split exactly at ±180, the
well-formed case. Buoys at 170°E and 140°W span 310° and were reported in
silence. The negative cases are held by the three rules above and need no help
from a threshold — verified by measurement, not by argument.
"""

from __future__ import annotations

from typing import Any

#: A crossing layer occupies less than half the world going the short way. At
#: exactly 180° the two readings are the same width and neither is truer, so the
#: plain one wins — it is the one every other tool will also report.
HALF_THE_WORLD = 180.0


def _spans(values: Any) -> tuple[float, float, float, float]:
    """(plain span, wrapped minimum, wrapped maximum, wrapped span).

    Vectorised on purpose: this runs inside `describe_dataset`, which is meant
    to be the cheap call somebody makes before deciding anything.
    """
    import numpy as np

    xs = np.asarray(values, dtype="float64")
    wrapped = np.mod(xs, 360.0)
    wrapped_min, wrapped_max = float(wrapped.min()), float(wrapped.max())
    return (
        float(xs.max()) - float(xs.min()),
        wrapped_min,
        wrapped_max,
        wrapped_max - wrapped_min,
    )


#: The axis directions of the two horizontal axes. A third axis — height — is
#: `up` or `down`, and its unit says nothing about how longitude is measured.
_HORIZONTAL = {"east", "west", "north", "south"}


def _is_in_degrees(crs: Any) -> bool:
    """Geographic is not enough: EPSG:4807 is geographic in **grads**.

    Wrapping at 360 and talking about the 180th meridian would both be wrong
    there, and it is the same class of mistake `measure_area` exists to avoid —
    reading the unit from the CRS instead of assuming it.

    Only the **horizontal** axes are asked. Requiring every axis to be in
    degrees switched the whole module off on EPSG:4979 — WGS 84 3D, which is
    what a great deal of GNSS and LiDAR data declares — because its third axis
    is ellipsoidal height in metres. The result was the silent false negative
    this module exists to prevent: a Fijian survey zone came back with the plain
    world-spanning bounding box, no `crosses_antimeridian`, no note, nothing
    anywhere to say a question had been skipped.
    """
    try:
        if not crs.is_geographic:
            return False
        horizontal = [
            axis
            for axis in crs.axis_info
            if str(axis.direction).lower() in _HORIZONTAL
        ]
        if not horizontal:
            return False
        return all(axis.unit_name == "degree" for axis in horizontal)
    except AttributeError:  # pragma: no cover — a CRS without axis metadata
        return False


def estimate_utm_crs(gdf: Any) -> Any:
    """`GeoDataFrame.estimate_utm_crs`, for data that straddles the 180th meridian.

    GeoPandas centres its estimate on the mean of `minx` and `maxx`. For a
    layer in degrees that crosses the antimeridian -- split there as RFC 7946
    prescribes -- those are about -180 and 180, the mean is about 0, and the zone
    it picks is on the opposite side of the planet. Measured on 2026-09-24: two
    points at 175E and 175W came back with EPSG:32630, centred on 3W. (GeoPandas
    handles the crossing only when the input is projected; the geographic branch
    takes the plain mean.)

    Not every operation is hurt by that: PROJ's transverse Mercator holds up far
    from its central meridian, and a 1 km buffer measured the same in the far
    zone as in the right one. `nearest_join` was, because polygons touching
    +/-180 projected into a zone 180 degrees away come out invalid. So this is
    the right zone rather than a rescue, and it changes nothing for data that
    does not cross: those go straight to GeoPandas.
    """
    extent = describe_extent(gdf)
    if not extent.get("crosses_antimeridian"):
        try:
            return gdf.estimate_utm_crs()
        except RuntimeError as exc:
            # Only GeoPandas' own "no zone" answer. pyproj's errors subclass
            # RuntimeError too, and relabelling them "no UTM zone covers..."
            # would replace the real diagnosis with a plausible one.
            if "Unable to determine UTM CRS" not in str(exc):
                raise
            bounds = gdf.total_bounds
            raise RuntimeError(
                _no_utm_zone(
                    (bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0
                )
            ) from exc

    from pyproj import CRS
    from pyproj.aoi import AreaOfInterest
    from pyproj.database import query_utm_crs_info

    true = extent["true_extent"]
    # West is GREATER than east here (RFC 7946 5.2), so the centre is found by
    # carrying the eastern edge past 180 and folding the mean back.
    centre = (true["minx"] + true["maxx"] + 360.0) / 2.0
    centre = ((centre + 180.0) % 360.0) - 180.0
    latitude = (true["miny"] + true["maxy"]) / 2.0
    found = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(centre, latitude, centre, latitude),
    )
    if not found:
        raise RuntimeError(_no_utm_zone(centre, latitude))
    return CRS.from_epsg(found[0].code)


def _no_utm_zone(longitude: float, latitude: float) -> str:
    """Why no UTM zone came back, and what to use instead.

    It said "data centred on the antimeridian" whatever the data, which was
    false for a layer centred anywhere else, and it offered no way out. The
    realistic cause is latitude: UTM is defined between 80S and 84N.
    """
    polar = latitude > 84.0 or latitude < -80.0
    return (
        f"no UTM zone covers the centre of this data ({longitude:.3f}, {latitude:.3f})"
        + (
            ": UTM is defined only between 80S and 84N. Reproject to a polar CRS "
            "first -- UPS (EPSG:32661 north, EPSG:32761 south), or a polar "
            "stereographic such as EPSG:3413 (Arctic) or EPSG:3031 (Antarctic) -- "
            "and run the operation on that."
            if polar
            else ". Reproject the layer to a projected CRS suited to its extent and "
            "run the operation on that."
        )
    )


def naive_crossings(gdf: Any) -> list[int]:
    """Polygons drawn across the 180th meridian as one ring, which the plane inverts.

    A zone from 170°E to 170°W written as a single ring --
    `(170, -5), (-170, -5), (-170, 5), (170, 5)` -- is, to shapely and every other
    planar library, the band from 170°W to 170°E: the rest of the planet. Measured
    on 2026-09-24 with `count_in_polygons` over two points, one at 175°E inside the
    real zone and one at 0°: the first was dropped, the second counted, and the
    total was 1 -- the same as the truth. So no number in the output betrays it.
    Split at 180 the way RFC 7946 §3.1.9 prescribes, the same zone is right.

    The signature is an edge that jumps more than half the world in longitude
    between two consecutive vertices. A real edge that long, drawn straight in a
    geographic CRS, is not a thing anybody means; the crossing artefact is exactly
    that. Returns the positions of the offending features, so a caller can refuse
    with their indices. Degrees only, for the reason `_is_in_degrees` gives.

    **An edge that runs from -180 to 180 is not one.** The first version flagged
    it, and so refused the rectangle covering the world, a latitude band round
    the whole planet, a polar cap -- and Antarctica in the Natural Earth
    countries file, found by the pre-release review of 0.6.0 before it shipped:
    "points per country" would have been refused. Those edges run along the edge
    of the plane, where the planar reading is the one meant. The artefact always
    has at least one end strictly inside (-180, 180), so that is the test.

    Vectorised: it runs on every input of six operations, and the loop it
    replaces took 29 s on 200 000 polygons and 12 s on as many points, which
    have no ring at all.
    """
    import numpy as np

    rings = _ring_longitudes(gdf)
    if rings is None:
        return []
    x, coord_ring, ring_part, part_feature, areal = rings
    # An edge running along the edge of the plane is not the artefact, and the
    # plane ends at -180/180 or, for a layer written in 0..360, at 0/360. Both
    # pairs are exempt whatever the layer's convention: the rectangle covering
    # the world written as box(0, -90, 360, 90) was refused on 2026-09-25 as
    # Antarctica had been, and a first fix that picked ONE pair per layer from
    # its maximum refused the world beside a polygon overshooting 180 by 1e-7.
    seams = np.asarray(_ALL_SEAMS)
    on_seam = np.abs(x[:, None] - seams[None, :]).min(axis=1) <= _SEAM_TOLERANCE
    jump = (
        (coord_ring[1:] == coord_ring[:-1])
        & (np.abs(np.diff(x)) > HALF_THE_WORLD)
        & ~(on_seam[1:] & on_seam[:-1])
    )
    if not jump.any():
        return []
    bad_rings = np.unique(coord_ring[1:][jump])
    return sorted({int(p) for p in areal[part_feature[ring_part[bad_rings]]]})


def layer_seam(gdf: Any) -> tuple[float, float]:
    """The seam a naive ring in this layer crosses, read from the same vertices.

    The refusal message used to decide the convention from `total_bounds`,
    which covers every geometry in the layer, while the detector reads polygon
    rings only: a point at 200 degrees beside a ring drawn 170 -> -170 made the
    message send its author to 0/360, the one meridian that ring does not cross.
    """
    rings = _ring_longitudes(gdf)
    return seam_longitudes(rings[0] if rings is not None else [])


def _ring_longitudes(gdf: Any):
    """The longitudes of every polygon ring vertex, with the indices back to features.

    `None` when there is nothing to look at: no CRS in degrees, no polygon, or
    fewer than two vertices.
    """
    import numpy as np
    import shapely

    if gdf.crs is None or not _is_in_degrees(gdf.crs) or not len(gdf):
        return None
    geometries = np.asarray(gdf.geometry.array, dtype=object)
    areal = np.flatnonzero(
        np.isin(
            shapely.get_type_id(geometries),
            (shapely.GeometryType.POLYGON, shapely.GeometryType.MULTIPOLYGON),
        )
    )
    if not areal.size:
        return None
    parts, part_feature = shapely.get_parts(geometries[areal], return_index=True)
    rings, ring_part = shapely.get_rings(parts, return_index=True)
    coords, coord_ring = shapely.get_coordinates(rings, return_index=True)
    if len(coords) < 2:
        return None
    return coords[:, 0], coord_ring, ring_part, part_feature, areal


#: How close to +/-180 a longitude must be to count as lying on the seam. Far
#: below any survey precision, far above the round trip of a float through a
#: file format.
_SEAM_TOLERANCE = 1e-9

#: Both places a plane of longitudes can end.
_ALL_SEAMS = (-180.0, 180.0, 0.0, 360.0)


def seam_longitudes(longitudes: Any) -> tuple[float, float]:
    """The two longitudes where a layer's plane ends: (-180, 180), or (0, 360).

    A layer is taken to be written in 0..360 when it has NO negative longitude
    and some longitude beyond 180. Beyond 180 alone was the first rule, and one
    vertex overshooting 180 by 1e-7 -- ordinary noise after a reprojection --
    moved the seam of a whole -180..180 layer. For a 0..360 layer the seam a
    single ring can be drawn across naively is the prime meridian.
    """
    import numpy as np

    values = np.asarray(longitudes, dtype="float64")
    values = values[np.isfinite(values)]
    if (
        values.size
        and float(values.min()) >= -_SEAM_TOLERANCE
        and float(values.max()) > 180.0 + _SEAM_TOLERANCE
    ):
        return (0.0, 360.0)
    return (-180.0, 180.0)


def describe_extent(gdf: Any) -> dict[str, Any]:
    """The extent of a layer, and what it means if it crosses the antimeridian.

    Always returns `minx/miny/maxx/maxy` — the plain bounding box, unchanged,
    because that is what the coordinates say and something downstream may be
    relying on it. When the data crosses, three more keys appear:
    `crosses_antimeridian`, `true_extent` in RFC 7946 §5.2 form (west greater
    than east), and `note`.

    Only degree-based geographic coordinate systems are considered. A projected
    CRS has no antimeridian in it — the seam is outside the projection's
    domain — and testing for one would produce a note on any dataset that
    happens to span 360 units of easting.
    """
    bounds = gdf.total_bounds
    extent = {
        "minx": float(bounds[0]),
        "miny": float(bounds[1]),
        "maxx": float(bounds[2]),
        "maxy": float(bounds[3]),
    }
    if gdf.crs is None or not len(gdf) or not _is_in_degrees(gdf.crs):
        return extent

    # Per-PART bounds rather than every vertex: for a geometry split at the seam
    # as §3.1.9 prescribes, the halves' own bounds carry the extremes, and this
    # is two numbers per part instead of two per vertex. Per part and not per
    # feature: one MultiPolygon split at 180 -- the form MapSmith's own
    # antimeridian refusal tells a caller to produce -- has feature bounds of
    # -180..180, which read as a layer spread over the whole world, and the UTM
    # zone estimated from that was the one centred on 3W (found by the 0.6.0
    # pre-release review). It cannot see a single unsplit geometry that itself
    # spans the seam -- that one has coordinates outside [-180, 180], its plain
    # bounds are already the narrow truth, and nothing about them misleads.
    import numpy as np
    import shapely

    parts = shapely.get_parts(np.asarray(gdf.geometry.array, dtype=object))
    per_part = shapely.bounds(parts)
    xs = per_part[:, [0, 2]].ravel()
    # A null geometry has NaN bounds, and NaN poisons min/max silently.
    xs = xs[np.isfinite(xs)]
    if not len(xs):
        return extent

    plain_span, wrapped_min, wrapped_max, wrapped_span = _spans(xs)
    if plain_span <= HALF_THE_WORLD:
        # The hypothesis only makes sense for data whose PLAIN extent is absurd.
        # A layer that wraps the seam looks like it covers nearly the whole
        # world; one that does not, does not — whatever the seam reading says.
        #
        # This line exists because the test below is a comparison of two floats
        # that differ by a round trip through +-360, and on data that does not
        # wrap they are the same number computed twice. Measured 2026-09-14 on a
        # river spanning 0.001 degrees at -122.19: plain 0.0010000000000047748,
        # wrapped 0.0009999999999763531, wrapped SMALLER by 2.8e-14 degrees --
        # about three nanometres on the ground. The comparison passed, the probe
        # meridian on the far side of the world naturally met nothing, and the
        # layer was announced as crossing the antimeridian, with a `true_extent`
        # identical to the ordinary one and a `width_degrees` equal to the plain
        # span. The verdict was decided by the last bits of a subtraction.
        #
        # An agent reads that note and stops trusting the bounding box of a
        # perfectly ordinary layer. Which way the noise falls is not a property
        # of the data, so any layer could get it.
        return extent
    if wrapped_span >= plain_span or wrapped_span >= HALF_THE_WORLD:
        # Either the seam buys nothing, or the data is spread over more than
        # half the world and neither reading is the narrow one.
        return extent

    # The probe: a meridian through the middle of the apparent empty band. Data
    # that really crosses the antimeridian does not reach it; a rectangle
    # covering the world does. This is the case arithmetic cannot decide.
    import shapely

    middle = ((wrapped_max + wrapped_min + 360.0) / 2.0) % 360.0
    probe_lon = middle if middle <= 180.0 else middle - 360.0
    probe = shapely.LineString(
        [(probe_lon, extent["miny"]), (probe_lon, extent["maxy"])]
    )
    if len(gdf.sindex.query(probe, predicate="intersects")):
        return extent

    west = wrapped_min if wrapped_min <= 180.0 else wrapped_min - 360.0
    east = wrapped_max if wrapped_max <= 180.0 else wrapped_max - 360.0
    extent.update(
        crosses_antimeridian=True,
        true_extent={
            "minx": round(west, 9),
            "miny": extent["miny"],
            "maxx": round(east, 9),
            "maxy": extent["maxy"],
            "width_degrees": round(wrapped_span, 9),
        },
        note=(
            f"the extent above spans {plain_span:.6g} degrees of longitude and the "
            f"data spans {wrapped_span:.6g}. Both are correct: the coordinates really "
            "do reach across the antimeridian, because the geometry is split there "
            "as RFC 7946 3.1.9 prescribes. `true_extent` is the same envelope in the "
            "form RFC 7946 5.2 defines for this case, with the western value GREATER "
            "than the eastern one. Filtering by the plain box — a coordinate slice, a "
            "tile request, a WHERE on min/max columns — selects everything at these "
            "latitudes anywhere on Earth."
        ),
    )
    return extent
