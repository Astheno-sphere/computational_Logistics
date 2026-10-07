#!/usr/bin/env python3
"""Plate 01: freight pinch points.

Route a vehicle between every pair of junctions by the fastest path and colour each street by the
share of those routes that use it (edge betweenness, Freeman 1977; Porta et al. 2006). The road
graph comes from osm-network, so the plate and the routing skills read OSM the same way.

    python skills/visual-narrative/scripts/pinch_points.py            # Molde, data/osm/molde.osm.bz2
    python skills/visual-narrative/scripts/pinch_points.py --osm other.osm --place "KRISTIANSUND" --water-label ""
"""
import argparse
import bz2
import re
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle
from shapely.geometry import LineString

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "osm-network" / "scripts")]
import coast  # noqa: E402
import osm_network as on  # noqa: E402
import plate as P  # noqa: E402

warnings.filterwarnings("ignore")
RAMP = LinearSegmentedColormap.from_list("pinch", ["#3B4752", "#6A7782", P.PAPER, P.ACCENT])
BUILDING = "#1A2229"       # context sits below the quietest street


def street_graph(osm):
    """Simplified drivable graph with travel times, and one row per street segment to draw."""
    G = on.add_costs(on.add_terrain(ox.simplify_graph(on.load(osm=osm))))
    D = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if not D.has_edge(u, v) or D[u][v]["travel_time"] > d["travel_time"]:
            D.add_edge(u, v, **d)
    rows = {}
    for u, v, d in D.edges(data=True):
        key = (min(u, v), max(u, v))
        geom = d.get("geometry") or LineString([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])
        name = d.get("name")
        rows.setdefault(key, {"geometry": geom, "name": name[0] if isinstance(name, list) else name,
                              "highway": on._hwy(d), "bridge": d.get("bridge"), "tunnel": d.get("tunnel")})
    segs = gpd.GeoDataFrame(list(rows.values()), index=list(rows.keys()), crs=G.graph["crs"])
    return D, segs, G.graph["crs"]


def extract_bounds(osm, crs):
    """The extract's own <bounds> in the plate CRS (the box the coastline was cut on)."""
    opener = bz2.open if str(osm).endswith(".bz2") else open
    with opener(osm, "rt", encoding="utf-8") as f:
        head = f.read(4096)
    m = re.search(r'<bounds minlat="([\d.-]+)" minlon="([\d.-]+)" maxlat="([\d.-]+)" maxlon="([\d.-]+)"', head)
    if not m:
        return None
    s, w, n, e = map(float, m.groups())
    import pyproj
    t = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = zip(*[t.transform(lon, lat) for lon, lat in [(w, s), (w, n), (e, s), (e, n)]])
    return min(xs), min(ys), max(xs), max(ys)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", default=str(HERE.parents[2] / "data" / "osm" / "molde.osm.bz2"))
    ap.add_argument("--place", default="MOLDE")
    ap.add_argument("--water-label", default="MOLDEFJORDEN")
    ap.add_argument("--out", default="docs/plates/01-freight-pinch-points.png")
    ap.add_argument("--caveat", default="")
    a = ap.parse_args()

    D, segs, crs = street_graph(a.osm)
    eb = nx.edge_betweenness_centrality(D, weight="travel_time", normalized=True)
    share = {}
    for (u, v), b in eb.items():               # the busier direction of each street segment
        k = (min(u, v), max(u, v))
        share[k] = max(share.get(k, 0.0), b)
    segs["share"] = [share.get(k, 0.0) for k in segs.index]
    named = segs.dropna(subset=["name"]).groupby("name").share.max().sort_values(ascending=False)
    lead_name, lead_share = named.index[0], float(named.iloc[0])
    corridor = segs[(segs.name == lead_name) & (segs.share >= 0.6 * lead_share)]
    vmax = float(segs.share.max())

    feats = ox.features_from_xml(a.osm, tags={"building": True, "natural": ["coastline", "water"]}).to_crs(crs)
    nat = feats["natural"] if "natural" in feats else None
    sea, fb = coast.sea_polygons(feats[nat == "coastline"], extract_bounds(a.osm, crs) or tuple(segs.total_bounds))
    # crop to the town: the central 90 % of street segments, centred so the fjord fills the lower part
    mid = segs.geometry.centroid
    xs, ys = mid.x.to_numpy(), mid.y.to_numpy()
    x0, x1 = np.percentile(xs, [5, 95])
    yc = np.percentile(ys, 50) + FRAME_SHIFT_N

    fig, ax = P.figure(P.Plate(
        kicker="a town pressed between fjord and mountain",
        label=f"{a.place}  —  DRIVE NETWORK  —  {len(D):,} JUNCTIONS",
        headline=[("FREIGHT", False), ("PINCH", True), ("POINTS", False)],
        sentence=SENTENCE.format(name=lead_name, share=lead_share),
        code='nx.edge_betweenness_centrality(G, weight="travel_time")',
        sources=("Freeman, Sociometry 40, 1977; Porta, Crucitti & Latora, Environment and Planning B 33, 2006; "
                 "© OpenStreetMap contributors (ODbL)" + (f"\nNote: {a.caveat}." if a.caveat else "")),
    ))
    # frame: the network's extent at the hero box's aspect
    box = ax.get_position()
    aspect = (box.height * P.H) / (box.width * P.W)
    cx, cy = (x0 + x1) / 2, yc
    half_w = (x1 - x0) / 2
    bottom = max(cy - half_w * aspect, fb[1])          # never show past the extract's southern edge
    ax.set_xlim(cx - half_w, cx + half_w)
    ax.set_ylim(bottom, bottom + 2 * half_w * aspect)
    ax.set_aspect("equal", adjustable="box")

    gpd.GeoSeries([sea], crs=crs).plot(ax=ax, color=P.WATER, lw=0, zorder=1)
    lakes = feats[(nat == "water") & feats.geom_type.isin(["Polygon", "MultiPolygon"])]
    if len(lakes):
        lakes.plot(ax=ax, color=P.WATER, lw=0, zorder=1)
    if "building" in feats:
        b = feats[feats["building"].notna() & feats.geom_type.isin(["Polygon", "MultiPolygon"])]
        b.plot(ax=ax, color=BUILDING, lw=0, zorder=2)

    order = segs.sort_values("share")
    lines = [np.asarray(g.coords) for g in order.geometry]
    t = (order.share / vmax).clip(0, 1).to_numpy()
    ax.add_collection(LineCollection(lines, colors=RAMP(t), linewidths=0.45 + 4.2 * t ** 1.5,
                                     capstyle="round", zorder=3))
    for g in corridor.geometry:                 # the one instance: glow under the leading corridor
        ax.plot(*np.asarray(g.coords).T, color=P.ACCENT, lw=14, alpha=0.16, solid_capstyle="round", zorder=2.5)

    hot = corridor.geometry.iloc[int(np.argmax(corridor.share.to_numpy()))].interpolate(0.5, normalized=True)
    tx, ty = hot.x + CALLOUT[0], hot.y + CALLOUT[1]
    ha = "left" if CALLOUT[0] > 0 else "right"
    ax.annotate(lead_name.upper(), xy=(hot.x, hot.y), xytext=(tx, ty), color=P.PAPER, size=7.5,
                fontfamily=P.SANS, ha=ha, va="bottom", zorder=6,
                arrowprops=dict(arrowstyle="-", color=P.PAPER, lw=0.6, shrinkA=0, shrinkB=3))
    ax.annotate(f"on {lead_share:.0%} of all fastest routes", xy=(tx, ty), xytext=(0, -3),
                textcoords="offset points", color=P.ACCENT, size=7, fontfamily=P.SANS, ha=ha, va="top", zorder=6)
    if a.water_label:
        xl, yl = ax.get_xlim(), ax.get_ylim()
        wx, wy = WATER_XY or ((xl[0] + xl[1]) / 2, yl[0] + 0.2 * (yl[1] - yl[0]))
        ax.text(wx, wy, a.water_label, color=DIMWATER, size=10, ha="center", va="center",
                fontfamily=P.SERIF, style="italic", zorder=4)

    ax.set_xlabel(""); ax.set_ylabel("")
    P.north_arrow(ax)
    xl, yl = ax.get_xlim(), ax.get_ylim()
    P.scale_bar(ax, 1000, xl[0] + 0.05 * (xl[1] - xl[0]), yl[0] + 0.05 * (yl[1] - yl[0]), "1 km")
    lx, ly, lw_ = 0.62, 0.045, 0.32
    for k in range(60):
        ax.add_patch(Rectangle((lx + lw_ * k / 60, ly), lw_ / 60 + 0.001, 0.012, transform=ax.transAxes,
                               color=RAMP(k / 59), lw=0, zorder=7))
    ax.text(lx, ly + 0.028, "SHARE OF FASTEST ROUTES USING THE STREET", transform=ax.transAxes,
            color=P.PAPER, size=6.3, fontfamily=P.SANS, zorder=7)
    for f in (0, 0.5, 1):
        ax.text(lx + lw_ * f, ly - 0.022, f"{vmax * f:.0%}", transform=ax.transAxes, color=P.DIM,
                size=6.3, ha="center", fontfamily=P.SANS, zorder=7)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    P.save(fig, a.out)
    print(f"{a.out}: {len(D)} junctions, {D.number_of_edges()} directed links")
    for name, v in named.head(8).items():
        print(f"  {v:6.1%}  {name}")


SENTENCE = ("Send a van between every pair of junctions by its fastest route. Between fjord and hillside "
            "there is little room for a second road: {share:.0%} of all those routes pass along {name}.")
FRAME_SHIFT_N = 700        # metres north of the median junction for the frame centre (more fjord below)
CALLOUT = (-900, 900)      # label offset from the hottest segment, metres
WATER_XY = None            # override the fjord label position (x, y) in the plate CRS
DIMWATER = "#4A6474"

if __name__ == "__main__":
    main()
