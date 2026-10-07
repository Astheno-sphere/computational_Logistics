#!/usr/bin/env python3
"""Plate 01: freight pinch points.

Route a vehicle between every pair of junctions by the fastest path and colour each street by the
share of those routes that use it (edge betweenness, Freeman 1977; Porta et al. 2006).

    python skills/visual-narrative/scripts/pinch_points.py                      # bundled Helsinki extract
    python skills/visual-narrative/scripts/pinch_points.py --pbf molde.osm.pbf --place "MOLDE" --crs 32632
"""
import argparse
import os
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pyrosm
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap

sys.path.insert(0, str(Path(__file__).parent))
import plate as P  # noqa: E402

warnings.filterwarnings("ignore")

# km/h when maxspeed is missing: assumptions, as in osm-network's HWY_SPEEDS
SPEEDS = {"motorway": 90, "trunk": 70, "primary": 50, "secondary": 40, "tertiary": 40,
          "unclassified": 30, "residential": 30, "living_street": 10, "service": 15}

RAMP = LinearSegmentedColormap.from_list("pinch", [P.FAINT, "#5E6B75", P.PAPER, P.ACCENT])


def speed(row):
    try:
        return float(str(row.maxspeed).split()[0])
    except (TypeError, ValueError):
        hw = row.highway if isinstance(row.highway, str) else "unclassified"
        return SPEEDS.get(hw.replace("_link", ""), 30)


def load(pbf, crs):
    osm = pyrosm.OSM(pbf)
    nodes, edges = osm.get_network(network_type="driving", nodes=True)
    edges = edges[~edges.highway.isin(["trail", "track", "path"])].copy()  # pyrosm lets these through
    edges = edges.to_crs(crs)
    edges["length"] = edges.length
    edges["travel_time"] = edges["length"] / (edges.apply(speed, axis=1) / 3.6)
    G = nx.DiGraph()
    for r in edges.itertuples():
        oneway = str(r.oneway).lower() in {"yes", "true", "1"}
        pairs = [(r.u, r.v)] if oneway else [(r.u, r.v), (r.v, r.u)]
        for a, b in pairs:
            if not G.has_edge(a, b) or G[a][b]["travel_time"] > r.travel_time:
                G.add_edge(a, b, travel_time=r.travel_time, idx=r.Index)
    G = G.subgraph(max(nx.strongly_connected_components(G), key=len)).copy()
    context = {}
    for name, getter in [("buildings", osm.get_buildings), ("natural", osm.get_natural)]:
        g = getter()
        context[name] = None if g is None else g.to_crs(crs)
    return edges, G, context


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pbf", default=os.path.join(os.path.dirname(pyrosm.__file__), "data", "Helsinki.osm.pbf"))
    ap.add_argument("--place", default="HELSINKI  —  KLUUVI · KRUUNUNHAKA · KALLIO")
    ap.add_argument("--crs", default="EPSG:3067")
    ap.add_argument("--out", default="docs/plates/01-freight-pinch-points.png")
    ap.add_argument("--caveat", default="pyrosm's bundled sample extract has gaps in street coverage, "
                    "so shares illustrate the method; run on a full extract for real figures")
    a = ap.parse_args()

    edges, G, ctx = load(a.pbf, a.crs)
    eb = nx.edge_betweenness_centrality(G, weight="travel_time", normalized=True)
    # one value per OSM way segment: the busier direction
    share = {}
    for (u, v), b in eb.items():
        i = G[u][v]["idx"]
        share[i] = max(share.get(i, 0.0), b)
    edges["share"] = edges.index.map(share).fillna(0.0)
    vmax = float(edges.share.max())
    named = (edges.dropna(subset=["name"]).groupby("name").share.max().sort_values(ascending=False))
    lead_name = named.index[0]
    # the corridor: every segment of the leading street carrying at least 60 % of its peak
    corridor = edges[(edges.name == lead_name) & (edges.share >= 0.6 * named.iloc[0])]
    bridges = edges[edges.bridge.notna() & edges.name.notna()].sort_values("share", ascending=False)

    fig, ax = P.figure(P.Plate(
        kicker="where every delivery has to pass",
        label=f"{a.place}  —  DRIVE NETWORK",
        headline=[("FREIGHT", False), ("PINCH", True), ("POINTS", False)],
        sentence=("Send a van between every pair of junctions by its fastest route. The street most of "
                  "those routes are forced to share is where one lane closure stalls the whole district."),
        code='nx.edge_betweenness_centrality(G, weight="travel_time")',
        sources=("Freeman, Sociometry 40, 1977; Porta, Crucitti & Latora, Environment and Planning B 33, 2006; "
                 "© OpenStreetMap contributors (ODbL), read with pyrosm\n" + (f"Note: {a.caveat}." if a.caveat else "")),
    ))

    x0, y0, x1, y1 = edges.total_bounds
    pad = 60
    # square-ish frame around the network, matching the hero box aspect
    box = ax.get_position()
    aspect = (box.height * P.H) / (box.width * P.W)
    cx, cy, half_w = (x0 + x1) / 2, (y0 + y1) / 2, max((x1 - x0) / 2, (y1 - y0) / 2 / aspect) + pad
    ax.set_xlim(cx - half_w, cx + half_w); ax.set_ylim(cy - half_w * aspect, cy + half_w * aspect)
    ax.set_aspect("equal", adjustable="box")

    nat = ctx.get("natural")
    if nat is not None:
        water = nat[(nat.natural == "water") & nat.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(water):
            water.plot(ax=ax, color=P.WATER, lw=0, zorder=1)
    if ctx.get("buildings") is not None:
        ctx["buildings"].boundary.plot(ax=ax, color=P.FAINT, lw=0.35, zorder=2)

    order = edges.sort_values("share")
    segs = [np.asarray(g.coords) if g.geom_type == "LineString" else np.vstack([np.asarray(p.coords) for p in g.geoms])
            for g in order.geometry]
    t = (order.share / vmax).clip(0, 1).to_numpy()
    ax.add_collection(LineCollection(segs, colors=RAMP(t), linewidths=0.5 + 4.5 * t ** 1.5,
                                     capstyle="round", zorder=3))
    # the one instance: glow under the leading corridor
    for g in corridor.geometry:
        xy = np.asarray(g.coords) if g.geom_type == "LineString" else np.vstack([np.asarray(q.coords) for q in g.geoms])
        ax.plot(*xy.T, color=P.ACCENT, lw=16, alpha=0.16, solid_capstyle="round", zorder=2.5)

    def callout(geom, lines, dx, dy):
        p = geom.interpolate(0.5, normalized=True)
        ha = "left" if dx > 0 else "right"
        ax.annotate(lines[0], xy=(p.x, p.y), xytext=(p.x + dx, p.y + dy), color=P.PAPER, size=7.5,
                    fontfamily=P.SANS, ha=ha, va="bottom", zorder=6,
                    arrowprops=dict(arrowstyle="-", color=P.PAPER, lw=0.6, shrinkA=0, shrinkB=3))
        ax.annotate(lines[1], xy=(p.x + dx, p.y + dy), xytext=(0, -3), textcoords="offset points",
                    color=P.ACCENT, size=7, fontfamily=P.SANS, ha=ha, va="top", zorder=6)

    hot = corridor.loc[corridor.share.idxmax()].geometry
    callout(hot, [lead_name.upper(), f"on {named.iloc[0]:.0%} of all fastest routes"], -380, 170)

    ax.set_xlabel(""); ax.set_ylabel("")
    P.north_arrow(ax)
    xl, yl = ax.get_xlim(), ax.get_ylim()
    P.scale_bar(ax, 200, xl[0] + 0.05 * (xl[1] - xl[0]), yl[0] + 0.05 * (yl[1] - yl[0]))

    # legend: the ramp, labelled in route share
    lx, ly, lw_ = 0.62, 0.045, 0.32
    ax.add_patch(__import__("matplotlib").patches.Rectangle(
        (lx - 0.02, ly - 0.04), lw_ + 0.05, 0.1, transform=ax.transAxes, color=P.INK, lw=0, zorder=6.5))
    for k in range(60):
        ax.add_patch(__import__("matplotlib").patches.Rectangle(
            (lx + lw_ * k / 60, ly), lw_ / 60 + 0.001, 0.012, transform=ax.transAxes,
            color=RAMP(k / 59), lw=0, zorder=7))
    ax.text(lx, ly + 0.028, "SHARE OF FASTEST ROUTES USING THE STREET", transform=ax.transAxes,
            color=P.PAPER, size=6.3, fontfamily=P.SANS, zorder=7)
    for f in (0, 0.5, 1):
        ax.text(lx + lw_ * f, ly - 0.022, f"{vmax * f:.0%}", transform=ax.transAxes, color=P.DIM,
                size=6.3, ha="center", fontfamily=P.SANS, zorder=7)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    P.save(fig, a.out)
    print(f"{a.out}: {G.number_of_nodes()} junctions, {G.number_of_edges()} directed links")
    for name, v in named.head(6).items():
        print(f"  {v:6.1%}  {name}")
    for r in bridges.itertuples():
        print(f"  bridge {r.share:6.1%}  {r.name}")


if __name__ == "__main__":
    main()
