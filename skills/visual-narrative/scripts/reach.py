#!/usr/bin/env python3
"""Plate 03: the five-minute depot.

Time the drive from every junction to every other; the junction with the shortest average drive is
where one depot reaches the town fastest (closeness centrality on travel time). Then count the
buildings a van from there reaches within five minutes, against the median over every junction.

    python skills/visual-narrative/scripts/reach.py
"""
import argparse
import json
from pathlib import Path

import networkx as nx
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from scipy.spatial import cKDTree

import basemap as B
import plate as P

NEAR = LinearSegmentedColormap.from_list("near", [B.QUIET, "#6A7782", P.PAPER])
MINUTES = 5
CALLOUT = (-500, 1500)


def drive_times(D):
    """Seconds from each junction to every junction it can reach."""
    return {s: nx.single_source_dijkstra_path_length(D, s, weight="travel_time") for s in D}


def frontier(town, t, limit):
    """Points where a street segment crosses `limit` seconds from the source (linear along the street)."""
    G, pts = town.G, []
    for (u, v), geom in zip(town.segs.index, town.segs.geometry):
        tu, tv = t.get(u, np.inf), t.get(v, np.inf)
        if tu > tv:
            u, v, tu, tv = v, u, tv, tu
        if not (tu <= limit < tv) or not np.isfinite(tu):
            continue
        frac = (limit - tu) / (tv - tu) if np.isfinite(tv) else 1.0
        start = np.hypot(geom.coords[0][0] - G.nodes[u]["x"], geom.coords[0][1] - G.nodes[u]["y"])
        end = np.hypot(geom.coords[-1][0] - G.nodes[u]["x"], geom.coords[-1][1] - G.nodes[u]["y"])
        p = geom.interpolate(frac if start <= end else 1 - frac, normalized=True)
        pts.append((p.x, p.y))
    return np.array(pts) if pts else np.empty((0, 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", default=B.DEFAULT_OSM)
    ap.add_argument("--out", default="docs/plates/03-the-five-minute-depot.png")
    ap.add_argument("--depot-json", default="docs/plates/03-depot.json", help="where plate 04 reads the depot")
    a = ap.parse_args()

    town = B.load(a.osm)
    D, G = town.D, town.G
    T = drive_times(D)
    n = len(D)
    # the depot must reach (almost) the whole town; among those, the shortest mean drive
    mean = {s: np.mean(list(t.values())) for s, t in T.items() if len(t) >= 0.99 * n}
    depot = min(mean, key=mean.get)

    nodes = list(D)
    tree = cKDTree([(G.nodes[v]["x"], G.nodes[v]["y"]) for v in nodes])
    bld = B.buildings(town)
    _, idx = tree.query(np.c_[bld.centroid.x, bld.centroid.y])
    door = [nodes[i] for i in idx]

    per_node = {}
    for v in door:
        per_node[v] = per_node.get(v, 0) + 1

    def within(src, minutes=MINUTES):
        return sum(c for v, c in per_node.items() if T[src].get(v, np.inf) <= minutes * 60) / len(door)

    p_depot = within(depot)
    p_typ = float(np.median([within(s) for s in D]))     # median over every junction as the depot
    worst = max(T[depot].get(v, np.inf) for v in door)

    segs = town.segs.copy()
    tmax = float(np.percentile(list(T[depot].values()), 95))
    seg_t = np.array([min(T[depot].get(u, np.inf), T[depot].get(v, np.inf)) for u, v in segs.index])
    segs["t"] = seg_t
    dx, dy = G.nodes[depot]["x"], G.nodes[depot]["y"]
    on_street = {n for _, _, d in G.edges(depot, data=True) for n in B.names(d)}
    name = min(on_street) if on_street else "unnamed junction"

    fig, ax = P.figure(P.Plate(
        kicker="where one depot reaches the most doors",
        label=f"MOLDE  —  {len(bld):,} BUILDINGS  —  DRIVE TIME FROM ONE DEPOT",
        headline=[("THE", False), ("FIVE-MINUTE", True), ("DEPOT", False)],
        sentence=(f"Time the drive from every junction to every other and keep the one with the shortest average. "
                  f"From there one van reaches {p_depot:.0%} of Molde's buildings within {MINUTES} minutes; "
                  f"from the median junction, {p_typ:.0%}."),
        code='nx.single_source_dijkstra_path_length(G, depot, weight="travel_time")',
        sources=("Closeness: Bavelas, J. Acoust. Soc. Am. 22, 1950; Sabidussi, Psychometrika 31, 1966. Free-flow times, "
                 "no turn or signal delays; buildings count from their nearest junction. " + B.OSM_CREDIT),
        number="03",
    ))
    B.frame(ax, town)
    B.context(ax, town)
    far = np.isfinite(seg_t)
    B.network(ax, segs[far], 1 - np.clip(seg_t[far] / tmax, 0, 1), ramp=NEAR, base=0.4, gain=1.8)
    # the one instance: the five-minute edge, where each street crosses the limit
    edge = frontier(town, T[depot], MINUTES * 60)
    ax.scatter(edge[:, 0], edge[:, 1], s=30, color=P.ACCENT, alpha=0.18, lw=0, zorder=4)
    ax.scatter(edge[:, 0], edge[:, 1], s=4, color=P.ACCENT, lw=0, zorder=4.1)
    B.mark(ax, (dx, dy), size=9)
    B.callout(ax, (dx, dy), f"DEPOT  ·  {name.upper()}", f"{p_depot:.0%} of buildings within {MINUTES} min", CALLOUT)
    B.apparatus(ax)
    B.legend(ax, "DRIVE TIME FROM THE DEPOT", [(0, f"{tmax / 60:.0f} min"), (1, "0 min")], ramp=NEAR)
    ax.text(0.62, 0.115, f"●  THE {MINUTES}-MINUTE EDGE", transform=ax.transAxes, color=P.ACCENT, size=6.3,
            fontfamily=P.SANS, zorder=7)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    P.save(fig, a.out)
    lon_lat = __import__("pyproj").Transformer.from_crs(town.crs, "EPSG:4326", always_xy=True).transform(dx, dy)
    Path(a.depot_json).write_text(json.dumps({"node": int(depot), "lon": lon_lat[0], "lat": lon_lat[1],
                                              "street": name, "mean_drive_s": mean[depot]}, indent=2) + "\n")
    print(f"{a.out}: depot {depot} on {name} at {lon_lat}")
    print(f"  mean drive {mean[depot]:.0f} s (median junction {np.median(list(mean.values())):.0f} s)")
    print(f"  buildings within {MINUTES} min: depot {p_depot:.1%}, median junction {p_typ:.1%}; worst {worst / 60:.1f} min")


if __name__ == "__main__":
    main()
