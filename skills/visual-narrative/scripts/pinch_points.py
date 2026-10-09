#!/usr/bin/env python3
"""Plate 01: freight pinch points.

Route a vehicle between every pair of junctions by the fastest path and colour each street by the
share of those routes that use it (edge betweenness, Freeman 1977; Porta et al. 2006).

    python skills/visual-narrative/scripts/pinch_points.py            # Molde, data/osm/molde.osm.bz2
"""
import argparse
from pathlib import Path

import networkx as nx
import numpy as np

import basemap as B
import plate as P

SENTENCE = ("Send a van between every pair of junctions by its fastest route. Between fjord and hillside "
            "there is little room for a second road: {share:.0%} of all those routes pass along {name}.")
CALLOUT = (-900, 900)      # label offset from the hottest segment, metres


def pinch(town):
    """Share of all fastest routes on each segment; the leading street and its corridor."""
    eb = nx.edge_betweenness_centrality(town.D, weight="travel_time", normalized=True)
    segs = town.segs.copy()
    segs["share"] = B.per_segment(town, eb)
    named = segs.dropna(subset=["name"]).groupby("name").share.max().sort_values(ascending=False)
    lead = named.index[0]
    corridor = segs[(segs.name == lead) & (segs.share >= 0.6 * named.iloc[0])]
    return eb, segs, named, corridor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", default=B.DEFAULT_OSM)
    ap.add_argument("--place", default="MOLDE")
    ap.add_argument("--water-label", default="MOLDEFJORDEN")
    ap.add_argument("--out", default="docs/plates/01-freight-pinch-points.png")
    ap.add_argument("--caveat", default="")
    a = ap.parse_args()

    town = B.load(a.osm)
    _, segs, named, corridor = pinch(town)
    lead, share = named.index[0], float(named.iloc[0])
    vmax = float(segs.share.max())

    fig, ax = P.figure(P.Plate(
        kicker="a town pressed between fjord and mountain",
        label=f"{a.place}  —  DRIVE NETWORK  —  {len(town.D):,} JUNCTIONS",
        headline=[("FREIGHT", False), ("PINCH", True), ("POINTS", False)],
        sentence=SENTENCE.format(name=lead, share=share),
        code='nx.edge_betweenness_centrality(G, weight="travel_time")',
        sources=("Freeman, Sociometry 40, 1977; Porta, Crucitti & Latora, Environment and Planning B 33, 2006; "
                 + B.OSM_CREDIT + (f"\nNote: {a.caveat}." if a.caveat else "")),
        number="01",
    ))
    B.frame(ax, town)
    B.context(ax, town, a.water_label)
    B.network(ax, segs, segs.share / vmax)
    B.glow(ax, corridor.geometry)
    hot = corridor.geometry.iloc[int(np.argmax(corridor.share.to_numpy()))].interpolate(0.5, normalized=True)
    B.callout(ax, (hot.x, hot.y), lead.upper(), f"on {share:.0%} of all fastest routes", CALLOUT)
    B.apparatus(ax)
    B.legend(ax, "SHARE OF FASTEST ROUTES USING THE STREET",
             [(0, "0%"), (0.5, f"{vmax / 2:.0%}"), (1, f"{vmax:.0%}")])

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    P.save(fig, a.out)
    print(f"{a.out}: {len(town.D)} junctions, {town.D.number_of_edges()} directed links")
    for name, v in named.head(8).items():
        print(f"  {v:6.1%}  {name}")


if __name__ == "__main__":
    main()
