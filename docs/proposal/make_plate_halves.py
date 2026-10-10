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
    x0, y0, x1 = 433200, 6998100, min(x1, 439500)
    y1 = min(y1, 7000720)   # district scale: the bridge, both halves, the tunnel portal

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

    LAND, SEA, SHADOW = "#2a201a", INK, "#0b0806"
    fig = plt.figure(figsize=(14, 14 * (y1 - y0) / (x1 - x0)), dpi=160)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off(); ax.set_facecolor(LAND)
    ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color=LAND, zorder=0))
    # topography as vector contours, every 10 m, every 50 m stronger
    gx_ = np.linspace(x0, x1, W); gy_ = np.linspace(y1, y0, H)
    ax.contour(gx_, gy_, dem, levels=np.arange(10, 220, 10), colors=CREAM, linewidths=0.35, alpha=0.13, zorder=1)
    ax.contour(gx_, gy_, dem, levels=np.arange(50, 220, 50), colors=CREAM, linewidths=0.7, alpha=0.22, zorder=1)
    from shapely.geometry import MultiPolygon
    for poly in (sea.geoms if isinstance(sea, MultiPolygon) else [sea]):
        xs, ys = poly.exterior.xy
        ax.fill(xs, ys, color=SEA, zorder=2, lw=0)
        ax.plot(xs, ys, color=CREAM, lw=0.6, alpha=0.35, zorder=2)
    ax.add_collection(LineCollection(L["roads"], colors=CREAM, linewidths=0.5, alpha=0.22, zorder=3))
    far = [r for (c, r), b in zip(L["buildings"], bside) if b == 1]
    near = [r for (c, r), b in zip(L["buildings"], bside) if b == 0]
    sh = lambda rings: [[(x + 7, y - 7) for x, y in r] for r in rings]
    ax.add_collection(PolyCollection(sh(near) + sh(far), facecolors=SHADOW, edgecolors="none", alpha=0.85, zorder=4))
    ax.add_collection(PolyCollection(near, facecolors="#E6DCC8", edgecolors="none", zorder=5))
    ax.add_collection(PolyCollection(far, facecolors=RED, edgecolors="none", zorder=5))
    for lw, al in ((9, 0.10), (5, 0.18)):
        ax.add_collection(LineCollection(L["rv70"], colors=AMBER, linewidths=lw, alpha=al, zorder=6))
    ax.add_collection(LineCollection(L["rv70"], colors=AMBER, linewidths=2.0, zorder=6))
    for w in F["tunnel"]:
        w = np.array(w)
        ax.plot(w[:, 0], w[:, 1], color=TEAL, lw=8, alpha=0.12, zorder=6)
        ax.plot(w[:, 0], w[:, 1], color=TEAL, lw=2.2, ls=(0, (3, 2)), zorder=6)

    def callout(p, dx, dy, head, body, c):
        ax.add_patch(plt.Circle(p, 95, fill=False, ec=CREAM, lw=1.4, zorder=9))
        ax.add_patch(plt.Circle(p, 22, color=c, zorder=9))
        ex, ey = p[0] + dx, p[1] + dy                      # elbow: out vertically, then across
        ax.plot([p[0], p[0], ex], [p[1] + (95 if dy > 0 else -95), ey, ey], color=CREAM, lw=0.9, zorder=9)
        tx = ex + (40 if dx > 0 else -40); ha = "left" if dx > 0 else "right"
        ax.text(tx, ey + 25, head, color=CREAM, fontsize=11.5, fontweight="bold", family="DejaVu Sans", ha=ha, va="bottom",
                zorder=10, bbox=dict(boxstyle="square,pad=0.45", fc=INK, ec="none"))
        ax.text(tx, ey - 25, body, color=c, fontsize=10, family="monospace", ha=ha, va="top", zorder=10,
                bbox=dict(boxstyle="square,pad=0.45", fc=INK, ec="none"))

    callout(bmid, 700, 650, "A · NORDSUNDBRUA", "toll station, rv. 70", RED)
    callout(exit_pt, -450, 520, "B · TOWARDS OMSUNDBRUA", "second station, beyond the frame", AMBER)
    callout(portal, -500, -700, "C · ATLANTERHAVSTUNNELEN", "fv. 64, toll-free since 2020", TEAL)
    for name, (ix, iy) in F["islands"].items():
        if name and x0 + 200 < ix < x1 - 200 and y0 + 200 < iy < y1 - 200 and not (ix > x1 - 1900 and iy > y1 - 900):
            ax.text(ix, iy, name.upper(), color=CREAM, alpha=0.7, fontsize=9.5, family="monospace", ha="center",
                    va="center", zorder=8)
    if far_name:
        fc = cent[(bside == 1) & (cent[:, 0] < x1) & (cent[:, 1] > y0)].mean(axis=0)
        ax.text(fc[0] + 700, fc[1] + 150, far_name, color=RED, fontsize=12, family="monospace", fontweight="bold",
                ha="center", zorder=8, bbox=dict(boxstyle="square,pad=0.3", fc=INK, ec="none", alpha=0.75))
    sx, sy = x0 + 220, y0 + 200
    ax.plot([sx, sx + 500], [sy, sy], color=CREAM, lw=3.2, zorder=9, solid_capstyle="butt")
    ax.plot([sx + 250, sx + 500], [sy, sy], color=INK, lw=1.6, zorder=10, solid_capstyle="butt")
    ax.text(sx, sy + 70, "0", color=CREAM, fontsize=9, family="monospace", zorder=9)
    ax.text(sx + 500, sy + 70, "500 m", color=CREAM, fontsize=9, family="monospace", ha="right", zorder=9)
    ax.add_patch(plt.Circle((sx + 760, sy + 60), 85, fill=False, ec=CREAM, lw=1.1, zorder=9))
    ax.plot([sx + 760, sx + 760], [sy + 10, sy + 130], color=CREAM, lw=1.6, zorder=9)
    ax.text(sx + 760, sy + 170, "N", color=CREAM, fontsize=9, ha="center", zorder=9)
    # run box, mono, top right
    ax.text(x1 - 120, y1 - 120, "OSM GRAPH  10,978 JUNCTIONS\nWITHOUT THE BRIDGE  6,580 | 4,398\nJUNCTION PAIRS CUT  48%\nBUILDINGS  6,728\nTERRAIN  COPERNICUS GLO-30",
            color=CREAM, fontsize=8.8, family="monospace", ha="right", va="top", linespacing=1.6, zorder=10,
            bbox=dict(boxstyle="square,pad=0.8", fc=INK, ec=CREAM, lw=0.6, alpha=0.92))
    # paper grain
    rng = np.random.default_rng(7)
    ax.imshow(rng.normal(0.5, 0.5, (H // 2, W // 2)), extent=(x0, x1, y0, y1), cmap="gray", alpha=0.035, zorder=11,
              interpolation="nearest")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    out = HERE / "plates"; out.mkdir(exist_ok=True)
    fig.savefig(out / "halves.png", dpi=160, facecolor=INK)
    res["sides"] = bside.tolist()
    (out / "halves.json").write_text(json.dumps(res))
    print("wrote", out / "halves.png")


if __name__ == "__main__":
    main()
