#!/usr/bin/env python3
"""GDAL/ogr2ogr OSM export (GeoJSON or GeoJSONL, e.g. from GeoLibre or QGIS) -> OSM XML.

ogr2ogr's OSM driver writes points, lines and multipolygons with the common tags as columns and the
rest packed into an `other_tags` hstore string. osm-network reads OSM XML, so this rebuilds it:
lines become ways, multipolygon outer rings become closed ways, and vertices with identical
coordinates become one node (that is how GDAL keeps the junctions ways shared in OSM).

    python gdal_osm_to_xml.py kristiansund.geojsonl data/osm/kristiansund.osm.bz2

Features entirely outside the export box (plus --pad degrees) are dropped, so long routes such as a
2,700 km coastal ferry do not stretch the extract; <bounds> is that box.
"""
import argparse
import bz2
import json
import re
from xml.sax.saxutils import quoteattr

KEEP_MARGIN_DEG = 0.005                   # ~500 m: keep ways that touch the export box
SKIP = {"osm_id", "osm_way_id", "other_tags", "z_order"}
HSTORE = re.compile(r'"((?:[^"\\]|\\.)*)"=>"((?:[^"\\]|\\.)*)"')


def tags_of(props):
    out = {k: str(v) for k, v in props.items() if v is not None and k not in SKIP}
    for k, v in HSTORE.findall(props.get("other_tags") or ""):
        out[k.replace('\\"', '"')] = v.replace('\\"', '"')
    return out


def read(path):
    with open(path, encoding="utf-8") as f:
        head = f.read(1).lstrip()
        f.seek(0)
        if head == "{" and '"FeatureCollection"' in f.read(2000):
            f.seek(0)
            yield from json.load(f)["features"]
            return
        f.seek(0)
        for line in f:
            line = line.strip().rstrip(",")
            if line.startswith("{"):
                yield json.loads(line)


def lines_of(geom):
    t, c = geom.get("type"), geom.get("coordinates")
    if c is None:                         # GeometryCollection: nothing osm-network uses
        return []
    if t == "LineString":
        return [c]
    if t == "MultiLineString":
        return c
    if t == "Polygon":
        return c[:1]                      # outer ring
    if t == "MultiPolygon":
        return [p[0] for p in c]
    return []


def convert(src, dst, pad=0.0):
    feats = [f for f in read(src) if f.get("geometry")]
    # The export box: Overpass returns whole ways (they stick out past it) but only the nodes inside
    # it, so the bulk of the point features marks it; trim the 0.1 % tails (distant ferry terminals).
    import numpy as np
    pts = np.array([f["geometry"]["coordinates"][:2] for f in feats if f["geometry"].get("type") == "Point"])
    if len(pts) < 100:                    # too few points: fall back to the road extent
        pts = np.array([p[:2] for f in feats if f["properties"].get("highway")
                        for ring in lines_of(f["geometry"]) for p in ring])
    if not len(pts):
        raise ValueError("no points or highway lines found: is this an ogr2ogr OSM export?")
    (w, s), (e, n) = np.percentile(pts, 0.1, axis=0) - pad, np.percentile(pts, 99.9, axis=0) + pad

    from shapely.geometry import LineString, Point, box
    keep = box(w, s, e, n).buffer(KEEP_MARGIN_DEG)    # ways on or just past the edge still count

    def inside(ring):
        g = LineString([p[:2] for p in ring]) if len(ring) > 1 else Point(ring[0][:2])
        return g.intersects(keep)

    nodes, ways = {}, []
    for f in feats:
        tags = tags_of(f["properties"])
        for ring in lines_of(f["geometry"]):
            if len(ring) < 2 or not inside(ring):
                continue
            refs = []
            for x, y, *_ in ring:
                key = (round(x, 7), round(y, 7))
                refs.append(nodes.setdefault(key, len(nodes) + 1))
            ways.append((refs, tags))
    opener = bz2.open if str(dst).endswith(".bz2") else open
    with opener(dst, "wt", encoding="utf-8") as out:
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6" generator="gdal_osm_to_xml">\n')
        out.write(f'  <bounds minlat="{s:.7f}" minlon="{w:.7f}" maxlat="{n:.7f}" maxlon="{e:.7f}"/>\n')
        for (x, y), i in nodes.items():
            out.write(f'  <node id="{i}" lat="{y:.7f}" lon="{x:.7f}"/>\n')
        for j, (refs, tags) in enumerate(ways, start=1):
            out.write(f'  <way id="{j}">')
            out.write("".join(f'<nd ref="{r}"/>' for r in refs))
            out.write("".join(f"<tag k={quoteattr(k)} v={quoteattr(v)}/>" for k, v in tags.items()))
            out.write("</way>\n")
        out.write("</osm>\n")
    return {"nodes": len(nodes), "ways": len(ways), "bounds": tuple(round(float(v), 6) for v in (s, w, n, e))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--pad", type=float, default=0.0, help="degrees added around the export box")
    a = ap.parse_args()
    print(convert(a.src, a.dst, a.pad))


if __name__ == "__main__":
    main()
