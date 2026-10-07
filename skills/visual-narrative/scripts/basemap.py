"""Shared base map for town-scale plates: road graph, fjord, buildings, frame, apparatus, legend.

Every map plate loads a Town once, draws its own layer with network()/glow()/callout(), and leaves
the page, the geography and the apparatus to this module so all plates read as one series.
"""
import bz2
import re
import sys
import warnings
from dataclasses import dataclass
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

DEFAULT_OSM = str(HERE.parents[2] / "data" / "osm" / "molde.osm.bz2")
RAMP = LinearSegmentedColormap.from_list("pinch", ["#3B4752", "#6A7782", P.PAPER, P.ACCENT])
BUILDING = "#1A2229"       # context sits below the quietest street
DIMWATER = "#4A6474"
QUIET = "#3B4752"          # a street that carries nothing in this plate's story


@dataclass
class Town:
    G: object              # projected MultiDiGraph from osm-network (simplified), node x/y, travel_time
    D: object              # DiGraph: cheapest parallel edge per direction
    segs: object           # GeoDataFrame, one row per street segment, index (min(u,v), max(u,v))
    crs: str
    feats: object          # buildings, coastline, water
    sea: object
    bounds: tuple          # extent the sea polygon was built for


def names(d):
    """Every street name on an edge. OSMnx's simplify merges ways into a list whose order varies
    between runs (set order), so never take name[0]."""
    n = d.get("name")
    return set(n) if isinstance(n, list) else ({n} if n else set())


def street_name(d):
    """One deterministic label per edge: the alphabetically first of its names."""
    n = names(d)
    return min(n) if n else None


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


def load(osm=DEFAULT_OSM):
    if not Path(osm).exists():
        sys.exit(f"{osm} not found: fetch it with the Overpass query in data/osm/README.md")
    G = on.add_costs(on.add_terrain(ox.simplify_graph(on.load(osm=osm))))
    D = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if not D.has_edge(u, v) or D[u][v]["travel_time"] > d["travel_time"]:
            D.add_edge(u, v, **d)
    rows = {}
    for u, v, d in D.edges(data=True):
        key = (min(u, v), max(u, v))
        geom = d.get("geometry") or LineString([(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])])
        rows.setdefault(key, {"geometry": geom, "name": street_name(d), "names": names(d), "highway": on._hwy(d)})
    crs = G.graph["crs"]
    segs = gpd.GeoDataFrame(list(rows.values()), index=list(rows.keys()), crs=crs)
    feats = ox.features_from_xml(osm, tags={"building": True, "natural": ["coastline", "water"]}).to_crs(crs)
    nat = feats["natural"] if "natural" in feats else None
    sea, fb = coast.sea_polygons(feats[nat == "coastline"], extract_bounds(osm, crs) or tuple(segs.total_bounds))
    return Town(G, D, segs, crs, feats, sea, fb)


def per_segment(town, edge_values, agg=max):
    """Directed-edge values -> one value per drawn segment (the busier direction by default)."""
    out = {}
    for (u, v), x in edge_values.items():
        k = (min(u, v), max(u, v))
        out[k] = agg(out[k], x) if k in out else x
    return np.array([out.get(k, 0.0) for k in town.segs.index])


def buildings(town):
    f = town.feats
    if "building" not in f:
        return f.iloc[:0]
    return f[f["building"].notna() & f.geom_type.isin(["Polygon", "MultiPolygon"])]


def frame(ax, town, shift_n=700, x_pct=(5, 95), focus=None, width=None):
    """Crop to the town (central street segments), with the fjord below; never past the extract.
    focus: geometries to centre on instead, shown `width` metres wide (a street-scale plate)."""
    box = ax.get_position()
    aspect = (box.height * P.H) / (box.width * P.W)
    if focus is not None:
        c = gpd.GeoSeries(list(focus)).union_all().envelope.centroid
        x0, x1, cy = c.x - width / 2, c.x + width / 2, c.y + shift_n
    else:
        mid = town.segs.geometry.centroid
        x0, x1 = np.percentile(mid.x, x_pct)
        cy = np.percentile(mid.y, 50) + shift_n
    x0, x1 = max(x0, town.bounds[0]), min(x1, town.bounds[2])     # never past the extract's sides
    half_w = (x1 - x0) / 2
    bottom = max(cy - half_w * aspect, town.bounds[1])
    ax.set_xlim((x0 + x1) / 2 - half_w, (x0 + x1) / 2 + half_w)
    ax.set_ylim(bottom, bottom + 2 * half_w * aspect)
    ax.set_aspect("equal", adjustable="box")


def context(ax, town, water_label="MOLDEFJORDEN", water_y=0.2):
    gpd.GeoSeries([town.sea], crs=town.crs).plot(ax=ax, color=P.WATER, lw=0, zorder=1)
    f = town.feats
    nat = f["natural"] if "natural" in f else None
    if nat is not None:
        lakes = f[(nat == "water") & f.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(lakes):
            lakes.plot(ax=ax, color=P.WATER, lw=0, zorder=1)
    b = buildings(town)
    if len(b):
        b.plot(ax=ax, color=BUILDING, lw=0, zorder=2)
    if water_label:
        xl, yl = ax.get_xlim(), ax.get_ylim()
        ax.text((xl[0] + xl[1]) / 2, yl[0] + water_y * (yl[1] - yl[0]), water_label, color=DIMWATER, size=10,
                ha="center", va="center", fontfamily=P.SERIF, style="italic", zorder=4)


def network(ax, segs, t, ramp=RAMP, base=0.45, gain=4.2, zorder=3):
    """Draw segments coloured and weighted by t in [0, 1]; quiet streets first, loud on top."""
    t = np.clip(np.asarray(t, dtype=float), 0, 1)
    order = np.argsort(t)
    lines = [np.asarray(segs.geometry.iloc[i].coords) for i in order]
    ax.add_collection(LineCollection(lines, colors=ramp(t[order]), linewidths=base + gain * t[order] ** 1.5,
                                     capstyle="round", zorder=zorder))


def glow(ax, geoms, color=P.ACCENT, lw=14, alpha=0.16):
    for g in geoms:
        parts = g.geoms if g.geom_type.startswith("Multi") else [g]
        for p in parts:
            ax.plot(*np.asarray(p.coords).T, color=color, lw=lw, alpha=alpha, solid_capstyle="round", zorder=2.5)


def callout(ax, xy, title, value, offset):
    """Leader line from xy to a two-line label: title in paper, measured value in the accent."""
    tx, ty = xy[0] + offset[0], xy[1] + offset[1]
    ha = "left" if offset[0] > 0 else "right"
    ax.annotate(title, xy=xy, xytext=(tx, ty), color=P.PAPER, size=7.5, fontfamily=P.SANS, ha=ha,
                va="bottom", zorder=6, arrowprops=dict(arrowstyle="-", color=P.PAPER, lw=0.6, shrinkA=0, shrinkB=3))
    ax.annotate(value, xy=(tx, ty), xytext=(0, -3), textcoords="offset points", color=P.ACCENT, size=7,
                fontfamily=P.SANS, ha=ha, va="top", zorder=6)


def apparatus(ax, metres=1000, label="1 km"):
    ax.set_xlabel(""); ax.set_ylabel("")
    P.north_arrow(ax)
    xl, yl = ax.get_xlim(), ax.get_ylim()
    P.scale_bar(ax, metres, xl[0] + 0.05 * (xl[1] - xl[0]), yl[0] + 0.05 * (yl[1] - yl[0]), label)


def legend(ax, title, ticks, ramp=RAMP, x=0.62, y=0.045, w=0.32):
    """ticks: [(position 0..1, text), ...]"""
    for k in range(60):
        ax.add_patch(Rectangle((x + w * k / 60, y), w / 60 + 0.001, 0.012, transform=ax.transAxes,
                               color=ramp(k / 59), lw=0, zorder=7))
    ax.text(x, y + 0.028, title, transform=ax.transAxes, color=P.PAPER, size=6.3, fontfamily=P.SANS, zorder=7)
    for pos, text in ticks:
        ax.text(x + w * pos, y - 0.022, text, transform=ax.transAxes, color=P.DIM, size=6.3, ha="center",
                fontfamily=P.SANS, zorder=7)


def mark(ax, xy, text=None, color=P.ACCENT, size=7):
    """A point marker (depot, closure) with an optional small caps label."""
    ax.scatter([xy[0]], [xy[1]], s=size ** 2, color=color, zorder=8, edgecolors=P.INK, linewidths=0.8)
    if text:
        ax.text(xy[0], xy[1] + 120, text, color=color, size=6.5, ha="center", fontfamily=P.SANS, zorder=8)


OSM_CREDIT = "© OpenStreetMap contributors (ODbL)"
