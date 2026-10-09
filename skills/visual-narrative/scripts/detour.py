#!/usr/bin/env python3
"""Plate 02: where the detour goes.

Close the street plate 01 found (every segment of it, both directions), route every trip between
every pair of junctions again by its fastest path, and measure what the town pays: trips that get
slower, by how much, trips that cannot be made at all, and which streets absorb the diverted routes.

    python skills/visual-narrative/scripts/detour.py                  # closes plate 01's leading street
    python skills/visual-narrative/scripts/detour.py --close "Storgata"
"""
import argparse
from pathlib import Path

import networkx as nx
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

import basemap as B
import plate as P
from pinch_points import pinch

ABSORB = LinearSegmentedColormap.from_list("absorb", [B.QUIET, "#6A7782", P.PAPER, P.ACCENT])
CALLOUT_ABSORB = (260, -330)
CALLOUT_CLOSED = (-260, 300)
FRAME_W = 2200             # metres across: street scale, so the detour is visible
FRAME_SHIFT_N = 250


def dur(seconds):
    return f"{seconds:.0f} s" if seconds < 90 else f"{seconds / 60:.0f} min"


def all_pairs_time(D):
    """Sum and count of finite fastest-route times over ordered pairs, plus per-source maps."""
    return {s: nx.single_source_dijkstra_path_length(D, s, weight="travel_time") for s in D}


def compare(before, after, nodes):
    slower, added, unreachable, total = 0, [], 0, 0
    for s in nodes:
        b, a = before[s], after.get(s, {})
        for t, tb in b.items():
            if t == s:
                continue
            total += 1
            ta = a.get(t)
            if ta is None:
                unreachable += 1
            elif ta > tb + 1.0:          # more than a second slower
                slower += 1
                added.append(ta - tb)
    return {"pairs": total, "slower": slower, "unreachable": unreachable,
            "mean_added_s": float(np.mean(added)) if added else 0.0,
            "p90_added_s": float(np.percentile(added, 90)) if added else 0.0,
            "max_added_s": float(np.max(added)) if added else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", default=B.DEFAULT_OSM)
    ap.add_argument("--close", default=None, help="street name to close (default: plate 01's leading street)")
    ap.add_argument("--out", default="docs/plates/02-where-the-detour-goes.png")
    a = ap.parse_args()

    town = B.load(a.osm)
    eb0, segs0, named, _ = pinch(town)
    closed = a.close or named.index[0]
    cut = [(u, v) for u, v, d in town.D.edges(data=True) if closed in B.names(d)]
    D1 = town.D.copy()
    D1.remove_edges_from(cut)

    before, after = all_pairs_time(town.D), all_pairs_time(D1)
    r = compare(before, after, list(town.D))
    eb1 = nx.edge_betweenness_centrality(D1, weight="travel_time", normalized=True)
    gain = {e: eb1.get(e, 0.0) - eb0.get(e, 0.0) for e in set(eb0) | set(eb1)}
    segs = town.segs.copy()
    segs["gain"] = B.per_segment(town, {e: max(g, 0.0) for e, g in gain.items()})
    segs["closed"] = [k in {(min(u, v), max(u, v)) for u, v in cut} for k in segs.index]
    open_named = segs[~segs.closed].dropna(subset=["name"])
    absorber = open_named.groupby("name").gain.max().sort_values(ascending=False)
    abs_name, abs_gain = absorber.index[0], float(absorber.iloc[0])
    abs_segs = segs[(segs.name == abs_name) & (segs.gain >= 0.6 * abs_gain)]
    gmax = float(segs.gain.max())

    slower = r["slower"] / r["pairs"]
    lost = r["unreachable"] / r["pairs"]
    sentence = (f"Close {closed} and send every van again by its fastest route. {slower:.0%} of all trips get "
                f"slower, but only by {dur(r['mean_added_s'])} on average and {dur(r['max_added_s'])} at worst: "
                f"{abs_name} takes the diverted routes.")
    fig, ax = P.figure(P.Plate(
        kicker="what one closed street costs the town",
        label=f"MOLDE  —  {closed.upper()} CLOSED  —  {r['pairs'] / 1e6:.1f} M TRIPS RECOMPUTED",
        headline=[("WHERE", False), ("THE", False), ("DETOUR", True), ("GOES", False)],
        sentence=sentence,
        code='G.remove_edges_from(closed); nx.edge_betweenness_centrality(G, weight="travel_time")',
        sources=(f"{lost:.1%} of trips become impossible (junctions reached only from {closed}). Free-flow "
                 "osm-network times, default speeds where OSM has no maxspeed. " + B.OSM_CREDIT),
        number="02",
    ))
    B.frame(ax, town, focus=list(segs[segs.closed].geometry) + list(abs_segs.geometry), width=FRAME_W,
            shift_n=FRAME_SHIFT_N)
    B.context(ax, town, water_y=0.12)
    B.network(ax, segs, segs.gain / gmax, ramp=ABSORB)
    for g in segs[segs.closed].geometry:          # the closed street: dashed, quiet, not the accent
        ax.plot(*np.asarray(g.coords).T, color=P.PAPER, lw=1.6, ls=(0, (2, 2)), zorder=5)
    B.glow(ax, abs_segs.geometry)
    hot = abs_segs.geometry.iloc[int(np.argmax(abs_segs.gain.to_numpy()))].interpolate(0.5, normalized=True)
    B.callout(ax, (hot.x, hot.y), abs_name.upper(), f"+{abs_gain:.0%} of all fastest routes", CALLOUT_ABSORB)
    c = segs[segs.closed].geometry.iloc[0].interpolate(0.5, normalized=True)
    B.callout(ax, (c.x, c.y), f"{closed.upper()}  ·  CLOSED", f"{slower:.0%} of trips slower", CALLOUT_CLOSED)
    B.apparatus(ax, 200, "200 m")
    B.legend(ax, "EXTRA SHARE OF FASTEST ROUTES AFTER THE CLOSURE",
             [(0, "+0%"), (0.5, f"+{gmax / 2:.0%}"), (1, f"+{gmax:.0%}")])

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    P.save(fig, a.out)
    print(f"{a.out}: closed {closed} ({len(cut)} directed links)")
    for k, v in r.items():
        print(f"  {k}: {v:,.1f}" if isinstance(v, float) else f"  {k}: {v:,}")
    for name, v in absorber.head(5).items():
        print(f"  +{v:6.1%}  {name}")


if __name__ == "__main__":
    main()
