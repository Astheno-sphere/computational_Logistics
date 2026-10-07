"""Sea polygons from OSM coastline ways, which keep land on the left and sea on the right."""
import numpy as np
from shapely.geometry import MultiLineString, Point, box
from shapely.ops import linemerge, polygonize, unary_union


def sea_polygons(coast, bounds, probe=4.0):
    """coast: GeoDataFrame of natural=coastline in a metric CRS (lines, plus closed rings that OSMnx
    turned into island polygons). bounds: (x0, y0, x1, y1) of the area to fill.
    Returns (sea geometry, bounds actually filled)."""
    frame = box(*bounds)
    lines = [p for g in coast.geometry if g.geom_type in ("LineString", "MultiLineString")
             for p in (g.geoms if g.geom_type == "MultiLineString" else [g])]
    islands = [g for g in coast.geometry if g.geom_type in ("Polygon", "MultiPolygon")]
    # join ways end to start; directed, because direction is what says which side is sea
    merged = linemerge(MultiLineString(lines), directed=True) if lines else None
    # an extract cut on a lat/lon box ends its coastline on a curved edge: shrink the metric frame
    # until every loose coastline end lies outside it, so the coast splits the frame cleanly
    parts = [] if merged is None else (list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged])
    ends = [Point(p.coords[k]) for p in parts if not p.is_closed for k in (0, -1)]
    inside = [e.distance(frame.exterior) for e in ends if frame.contains(e)]
    if inside:
        frame = box(*frame.buffer(-(max(inside) + 1.0), join_style=2).bounds)
    # node the uncut lines with the frame edge (clipping first leaves endpoints a hair off the edge)
    noded = unary_union([frame.boundary] + ([merged] if merged else []))
    faces = [f for f in polygonize(noded) if frame.contains(f.representative_point())]
    # vote: a point just right of each coastline segment is sea, just left is land
    votes = np.zeros(len(faces))
    for ln in parts:
        xy = np.asarray(ln.coords)
        for (xa, ya), (xb, yb) in zip(xy[:-1], xy[1:]):
            dx, dy = xb - xa, yb - ya
            n = np.hypot(dx, dy)
            if n == 0:
                continue
            mx, my, ox_, oy_ = (xa + xb) / 2, (ya + yb) / 2, dy / n * probe, -dx / n * probe
            for p, w in ((Point(mx + ox_, my + oy_), 1), (Point(mx - ox_, my - oy_), -1)):
                for i, f in enumerate(faces):
                    if f.contains(p):
                        votes[i] += w
                        break
    sea = [f for f, v in zip(faces, votes) if v > 0]
    out = unary_union(sea) if sea else frame.buffer(0).difference(frame)
    for isl in islands:
        out = out.difference(isl)
    return out, frame.bounds
