#!/usr/bin/env python3
"""Plate: two halves, one bridge -> docs/proposal/plates/halves.jpg and halves.json

Every building in the Kristiansund extract is assigned to the side of Nordsundbrua (the toll station on
rv. 70) it reaches without the bridge, using the OpenStreetMap road graph. Terrain is the Copernicus
GLO-30 surface model, hillshaded. Also located from the data: the rv. 70 exit towards Omsundbrua (the
second station, outside the extract) and the portal of Atlanterhavstunnelen (fv. 64, toll-free since
2020). Every number on the plate is printed by this script.

    python docs/proposal/make_plate_halves.py  [path/to/copernicus_N63_E007.tif]
"""
import bz2
import json
import os
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import rasterio
from matplotlib.collections import LineCollection, PolyCollection
from pyproj import Transformer
from rasterio.warp import Resampling, reproject
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "skills" / "osm-network" / "scripts"))
import osm_network as on  # noqa: E402
sys.path.insert(0, str(ROOT / "skills" / "visual-narrative" / "scripts"))
import coast as coast_helper  # noqa: E402,F401
sys.modules["coast_helper"] = coast_helper

INK, CREAM, DIM, RED, AMBER, TEAL = "#16120F", "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#7CBAC4"
DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N63_00_E007_00_DEM/Copernicus_DSM_COG_10_N63_00_E007_00_DEM.tif"


def osm_features(tr):
    nodes, ways = {}, []
    for _, el in ET.iterparse(bz2.open(ROOT / "data/osm/kristiansund.osm.bz2")):
        if el.tag == "node":
            nodes[el.get("id")] = tr.transform(float(el.get("lon")), float(el.get("lat")))
        elif el.tag == "way":
            tags = {t.get("k"): t.get("v") for t in el.findall("tag")}
            if (tags.get("place") == "island" or tags.get("name") == "Atlanterhavstunnelen"
                    or tags.get("natural") == "coastline" or (tags.get("name") or "").startswith("Nordlandet ")):
                ways.append((tags, [nd.get("ref") for nd in el.findall("nd")]))
        if el.tag in ("node", "way", "relation"):
            el.clear()
    out = {"islands": {}, "tunnel": [], "coast": [], "nordlandet": []}
    for tags, refs in ways:
        pts = np.array([nodes[r] for r in refs if r in nodes])
        if not len(pts):
            continue
        if tags.get("place") == "island":
            out["islands"][tags.get("name")] = pts.mean(axis=0).tolist()
        elif tags.get("natural") == "coastline":
            out["coast"].append(pts.tolist())
        elif tags.get("name") == "Atlanterhavstunnelen":
            out["tunnel"].append(pts.tolist())
        else:
            out["nordlandet"].append((tags.get("name"), pts.mean(axis=0).tolist()))
    return out


class _Coast:
    def __init__(self, lines):
        from shapely.geometry import LineString
        self.geometry = [LineString(l) for l in lines if len(l) > 1]


def main():
    dem_path = sys.argv[1] if len(sys.argv) > 1 else DEM_URL
    L = json.loads((HERE / "layers.json").read_text())
    B = json.loads((HERE / "bridge.json").read_text())
    tr = Transformer.from_crs(4326, 32632, always_xy=True)
    bp = np.array([p for _, r in L["buildings"] for p in r])
    x0, y0 = bp.min(axis=0) - 250
    x1, y1 = bp.max(axis=0) + 250
    x0, y0 = 431300, 6997350          # the town: south of here the frame is sea and the mainland beyond Omsundbrua

    with tempfile.NamedTemporaryFile(suffix=".osm", delete=False) as tmp:
        tmp.write(bz2.open(ROOT / "data/osm/kristiansund.osm.bz2").read())
    try:
        G = on.load(osm=tmp.name)
    finally:
        os.unlink(tmp.name)
    names = lambda d: d.get("name") if isinstance(d.get("name"), list) else [d.get("name")]
    bridge = [(u, v) for u, v, d in G.edges(data=True) if "Nordsundbrua" in names(d)]
    U = G.to_undirected()
    U = U.subgraph(max(nx.connected_components(U), key=len)).copy()
    U.remove_edges_from(bridge)
    parts = sorted(nx.connected_components(U), key=len, reverse=True)[:2]
    side = {n: i for i, c in enumerate(parts) for n in c}
    ids = list(side)
    tree = cKDTree(np.array([[G.nodes[i]["x"], G.nodes[i]["y"]] for i in ids]))
    side_of = lambda p: side[ids[tree.query(p)[1]]]

    cent = np.array([np.mean(r, axis=0) for _, r in L["buildings"]])
    bside = np.array([side[ids[j]] for j in tree.query(cent)[1]])
    cls = [c for c, _ in L["buildings"]]
    cnt = {s: Counter(c for c, b in zip(cls, bside) if b == s) for s in (0, 1)}

    F = osm_features(tr)
    nl_sides = Counter(side_of(p) for _, p in F["nordlandet"])
    far_name = "NORDLANDET" if nl_sides and nl_sides.most_common(1)[0][0] == 1 else None
    # tunnel portal: the tunnel node that meets the street network most closely, inside the frame
    tun = np.array([p for w in F["tunnel"] for p in w])
    tun = tun[(tun[:, 0] > x0) & (tun[:, 0] < x1) & (tun[:, 1] > y0) & (tun[:, 1] < y1)]
    kirk = np.array(F["islands"].get("Kirkelandet", tun.mean(axis=0)))
    portal = tun[np.argmin(np.hypot(*(tun - kirk).T))]      # the Kristiansund end of the tunnel
    rv = np.array([p for w in L["rv70"] for p in w])
    rv = rv[(rv[:, 0] > x0) & (rv[:, 0] < x1) & (rv[:, 1] > y0) & (rv[:, 1] < y1)]
    exit_pt = rv[np.argmax(rv[:, 0])]
    bmid = np.mean(B["bridge_xy"], axis=0)

    hf = cnt[1]["home"] + cnt[1]["flat"]; hn = cnt[0]["home"] + cnt[0]["flat"]
    res = {"junctions": int(len(U)), "parts": [len(c) for c in parts], "pairs_cut": B["pairs_cut"],
           "buildings": len(cls), "homes_far": hf, "homes_near": hn, "homes_far_share": round(hf / (hf + hn), 3),
           "work_far": cnt[1]["work"], "work_near": cnt[0]["work"],
           "work_far_share": round(cnt[1]["work"] / (cnt[1]["work"] + cnt[0]["work"]), 3),
           "far_side_named": far_name, "nordlandet_features_by_side": dict(nl_sides),
           "portal_side": int(side_of(portal)), "portal_xy": [round(v) for v in portal],
           "exit_xy": [round(v) for v in exit_pt], "bridge_xy": [round(v) for v in bmid]}

    # coastline for a crisp sea, terrain for relief
    from coast_helper import sea_polygons
    sea, fb = sea_polygons(_Coast(F["coast"]), (x0, y0, x1, y1))
    x0, y0, x1, y1 = fb
    rv = np.array([p for w in L["rv70"] for p in w])
    rv = rv[(rv[:, 0] > x0) & (rv[:, 0] < x1 - 60) & (rv[:, 1] > y0) & (rv[:, 1] < y1)]
    exit_pt = rv[np.argmax(rv[:, 0])]
    res["exit_xy"] = [round(v) for v in exit_pt]
    W, H = int((x1 - x0) / 5), int((y1 - y0) / 5)
    dem = np.zeros((H, W), dtype="float32")
    with rasterio.open(dem_path) as src:
        reproject(rasterio.band(src, 1), dem, dst_transform=rasterio.transform.from_bounds(x0, y0, x1, y1, W, H),
                  dst_crs="EPSG:32632", resampling=Resampling.cubic)
    gy, gx = np.gradient(dem, 5)
    slope = np.arctan(1.6 * np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(315), np.radians(40)
    shade = np.clip(np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect), 0, 1)
    lo, hi = np.array([0x2c, 0x23, 0x1c]) / 255, np.array([0x7a, 0x66, 0x4f]) / 255
    tt = np.clip(dem / 110, 0, 1)[..., None]
    rgb = np.clip((lo * (1 - tt) + hi * tt) * (0.5 + 0.8 * shade[..., None]), 0, 1)
    res["max_elev_m"] = round(float(dem.max()))
    print(json.dumps(res, indent=1))

    fig = plt.figure(figsize=(14, 14 * (y1 - y0) / (x1 - x0)), dpi=160)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.imshow(rgb, extent=(x0, x1, y0, y1), origin="upper", interpolation="bilinear")
    from shapely.geometry import MultiPolygon
    for poly in (sea.geoms if isinstance(sea, MultiPolygon) else [sea]):
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, color=INK, zorder=1)
        for hole in poly.interiors:
            hx, hy = hole.xy
            ax.fill(hx, hy, color="none")
    ax.add_collection(LineCollection(L["roads"], colors=CREAM, linewidths=0.45, alpha=0.30, zorder=2))
    far = [r for (c, r), b in zip(L["buildings"], bside) if b == 1]
    near = [r for (c, r), b in zip(L["buildings"], bside) if b == 0]
    ax.add_collection(PolyCollection(near, facecolors=CREAM, edgecolors="none", alpha=0.80, zorder=3))
    ax.add_collection(PolyCollection(far, facecolors=RED, edgecolors="none", alpha=0.95, zorder=3))
    ax.add_collection(LineCollection(L["rv70"], colors=AMBER, linewidths=2.4, zorder=4))
    for w in F["tunnel"]:
        w = np.array(w); ax.plot(w[:, 0], w[:, 1], color=TEAL, lw=2.8, ls=(0, (3, 2)), zorder=4)

    def clamp(p):
        return (min(max(p[0], x0 + 120), x1 - 2300), min(max(p[1], y0 + 400), y1 - 450))

    def card(p, off, head, body, c):
        ax.add_patch(plt.Circle(p, 110, fill=False, ec=c, lw=1.8, zorder=6))
        ax.annotate(f"{head}\n{body}", xy=p, xytext=clamp((p[0] + off[0], p[1] + off[1])), zorder=8,
                    fontsize=10.5, family="monospace", color=CREAM, linespacing=1.55,
                    bbox=dict(boxstyle="square,pad=0.6", fc=INK, ec=c, lw=1.1),
                    arrowprops=dict(arrowstyle="-", color=c, lw=1.0, shrinkA=0, shrinkB=9))

    card(bmid, (350, 750), "A  NORDSUNDBRUA", "toll station on rv. 70", RED)
    card(exit_pt, (-2500, -650), "B  TOWARDS OMSUNDBRUA", "second station, beyond the frame", AMBER)
    card(portal, (-900, -1500), "C  ATLANTERHAVSTUNNELEN", "fv. 64, toll-free since 2020", TEAL)
    labels = dict(F["islands"])
    for name, (ix, iy) in labels.items():
        if name and x0 < ix < x1 and y0 < iy < y1:
            ax.text(ix, iy, name.upper(), color=CREAM, alpha=0.8, fontsize=9.5, family="monospace", ha="center",
                    va="center", zorder=7, bbox=dict(boxstyle="square,pad=0.25", fc=INK, ec="none", alpha=0.6))
    if far_name:
        fc = cent[bside == 1].mean(axis=0)
        ax.text(fc[0], fc[1] + 500, far_name, color=RED, fontsize=11, family="monospace", fontweight="bold",
                ha="center", zorder=7, bbox=dict(boxstyle="square,pad=0.25", fc=INK, ec="none", alpha=0.7))
    sx, sy = x0 + 250, y0 + 230
    ax.plot([sx, sx + 1000], [sy, sy], color=CREAM, lw=2.4, zorder=8)
    ax.plot([sx, sx + 500], [sy, sy], color=INK, lw=1.0, zorder=9)
    ax.text(sx, sy + 110, "0", color=CREAM, fontsize=9, family="monospace", zorder=8)
    ax.text(sx + 1000, sy + 110, "1 km", color=CREAM, fontsize=9, family="monospace", ha="right", zorder=8)
    ax.annotate("N", xy=(sx + 1350, sy + 420), xytext=(sx + 1350, sy + 40), color=CREAM, fontsize=10, ha="center",
                zorder=8, arrowprops=dict(arrowstyle="-|>", color=CREAM, lw=1.3))
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    out = HERE / "plates"; out.mkdir(exist_ok=True)
    fig.savefig(out / "halves.png", dpi=160, facecolor=INK)
    (out / "halves.json").write_text(json.dumps(res, indent=1))
    print("wrote", out / "halves.png")


if __name__ == "__main__":
    main()
