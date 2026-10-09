#!/usr/bin/env python3
"""Town outlines for the proposal's maps -> docs/proposal/towns.json.

For Molde and Kristiansund (OSM extracts in data/osm): simplified street segments with their road class
and the share of all fastest junction-to-junction routes that use them (edge betweenness, as plate 01),
sea polygons, and a sample of building centroids where the figures place agents. UTM 32N metres.

    python docs/proposal/make_towns.py          # ~3 min
"""
import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills/visual-narrative/scripts"))
import basemap as B  # noqa: E402

MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary"}
N_BUILDINGS = 2500


def town_json(osm, seed):
    t = B.load(str(osm))
    eb = nx.edge_betweenness_centrality(t.D, weight="travel_time", normalized=True)
    share = B.per_segment(t, eb)
    x0, y0, x1, y1 = t.segs.total_bounds
    bx0, by0, bx1, by1 = t.bounds
    x0, y0, x1, y1 = max(x0, bx0), max(y0, by0), min(x1, bx1), min(y1, by1)
    frame = box(x0, y0, x1, y1)
    roads = []
    for (geom, hwy, name), s in zip(t.segs[["geometry", "highway", "name"]].itertuples(index=False), share):
        g = geom.simplify(4).intersection(frame)
        for part in getattr(g, "geoms", [g]):
            if part.geom_type == "LineString" and len(part.coords) > 1:
                maj = int(str(hwy).replace("_link", "") in MAJOR)
                roads.append([maj, [[round(x), round(y)] for x, y in part.coords], round(float(s), 4)])
    sea = []
    for poly in getattr(t.sea, "geoms", [t.sea]) if t.sea is not None else []:
        p = poly.intersection(frame).simplify(6)
        for q in getattr(p, "geoms", [p]):
            if q.geom_type == "Polygon" and q.area > 2000:
                sea.append([[round(x), round(y)] for x, y in q.exterior.coords])
    bld = B.buildings(t)
    c = np.c_[bld.centroid.x, bld.centroid.y]
    c = c[(c[:, 0] > x0) & (c[:, 0] < x1) & (c[:, 1] > y0) & (c[:, 1] < y1)]
    pick = np.random.default_rng(seed).choice(len(c), size=min(N_BUILDINGS, len(c)), replace=False)
    named = t.segs.assign(share=share).dropna(subset=["name"]).groupby("name").share.max().sort_values(ascending=False)
    return {"bbox": [round(x0), round(y0), round(x1), round(y1)], "roads": roads, "sea": sea,
            "junctions": len(t.D), "buildings": len(bld), "points": c[pick].round().astype(int).tolist(),
            "pinch": [named.index[0], round(float(named.iloc[0]), 3)]}


def main():
    out = {name: town_json(ROOT / f"data/osm/{name}.osm.bz2", seed) for seed, name in enumerate(("molde", "kristiansund"))}
    for k, v in out.items():
        print(k, v["bbox"], len(v["roads"]), "roads", len(v["sea"]), "sea", v["junctions"], "junctions",
              v["buildings"], "buildings; pinch", v["pinch"])
    (ROOT / "docs/proposal/towns.json").write_text(json.dumps(out, separators=(",", ":")))


if __name__ == "__main__":
    main()
