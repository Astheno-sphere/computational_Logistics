#!/usr/bin/env python3
"""Build a drivable, terrain-aware road graph from OpenStreetMap with OSMnx.

Pipeline: OSM (file or place name) -> drivable edges only -> project to UTM -> elevation
(DEM raster, or a function for tests) -> grades -> speeds and travel times -> energy per edge.
Every edge ends up with: length [m], grade [-], speed_kph, travel_time [s], energy_kwh.

CLI:
  python osm_network.py --osm grid_molde.osm --summary
  python osm_network.py --place "Molde, Norway" --dem dem.tif --out molde.graphml --summary
  python osm_network.py --osm grid_molde.osm --route 7.1592,62.7375 7.1826,62.7483 --weight energy_kwh
"""
import argparse
import json
import math
import sys

import networkx as nx
import osmnx as ox

# Ways a delivery vehicle may not use. OSMnx's graph_from_xml keeps every way, so filter here.
NOT_DRIVABLE = {"footway", "path", "pedestrian", "steps", "cycleway", "bridleway", "corridor",
                "elevator", "escalator", "platform", "proposed", "construction", "abandoned", "raceway"}
# Urban defaults in km/h where OSM has no maxspeed. Replace with local data before quoting results.
HWY_SPEEDS = {"motorway": 90, "trunk": 80, "primary": 60, "secondary": 50, "tertiary": 50,
              "unclassified": 40, "residential": 30, "living_street": 10, "service": 20}


class Vehicle:
    """Constant-speed traction model. Defaults: a 3.5 t electric van. All are assumptions."""

    def __init__(self, mass_kg=3500.0, crr=0.010, cda=2.2, eta=0.85, regen=0.6, air_density=1.225):
        self.mass, self.crr, self.cda, self.eta, self.regen, self.rho = mass_kg, crr, cda, eta, regen, air_density

    def edge_energy_kwh(self, length_m, grade, speed_kph):
        """Battery energy for one edge. Positive work is divided by drivetrain efficiency;
        negative work (downhill beyond rolling and drag) is recovered at `regen` efficiency."""
        v = speed_kph / 3.6
        theta = math.atan(grade)
        force = self.mass * 9.81 * (self.crr * math.cos(theta) + math.sin(theta)) + 0.5 * self.rho * self.cda * v * v
        work_j = force * length_m
        battery_j = work_j / self.eta if work_j >= 0 else work_j * self.regen
        return battery_j / 3.6e6


def load(osm=None, place=None):
    """Directed graph that respects one-way streets. Offline from a file, or online by place name."""
    if osm:
        G = ox.graph_from_xml(osm, simplify=False, retain_all=False)
    else:
        G = ox.graph_from_place(place, network_type="drive", simplify=False)
    drop = [(u, v, k) for u, v, k, d in G.edges(keys=True, data=True) if _hwy(d) in NOT_DRIVABLE]
    G.remove_edges_from(drop)
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    if len(G) and not nx.is_strongly_connected(G):
        # keep the largest strongly connected part so every stop can reach every other
        G = G.subgraph(max(nx.strongly_connected_components(G), key=len)).copy()
    return ox.project_graph(G)            # UTM zone picked from the data; Molde -> EPSG:32632


def _hwy(d):
    h = d.get("highway")
    return h[0] if isinstance(h, list) else h


def add_terrain(G, dem=None, elevation_fn=None):
    """Node elevations from a DEM raster (same CRS as G, or reprojected by OSMnx) or a function
    elevation_fn(x, y) in G's projected metres. Then edge grades (rise/run, signed)."""
    if dem:
        G = ox.elevation.add_node_elevations_raster(G, dem)
    elif elevation_fn:
        for n, d in G.nodes(data=True):
            d["elevation"] = float(elevation_fn(d["x"], d["y"]))
    else:
        for _, d in G.nodes(data=True):
            d["elevation"] = 0.0
    return ox.elevation.add_edge_grades(G, add_absolute=True)


def add_costs(G, vehicle=None, hwy_speeds=None):
    """Speeds, travel times and per-edge energy. Downhill energy can be negative (regeneration)."""
    vehicle = vehicle or Vehicle()
    G = ox.routing.add_edge_speeds(G, hwy_speeds=hwy_speeds or HWY_SPEEDS, fallback=30)
    G = ox.routing.add_edge_travel_times(G)
    for _, _, d in G.edges(data=True):
        d["energy_kwh"] = vehicle.edge_energy_kwh(d["length"], d.get("grade", 0.0), d["speed_kph"])
    return G


def build(osm=None, place=None, dem=None, elevation_fn=None, vehicle=None):
    return add_costs(add_terrain(load(osm=osm, place=place), dem=dem, elevation_fn=elevation_fn), vehicle)


def nearest(G, lon, lat):
    """Nearest graph node to a WGS84 point (G is projected, so transform the point first)."""
    import pyproj
    to_g = pyproj.Transformer.from_crs("EPSG:4326", G.graph["crs"], always_xy=True)
    x, y = to_g.transform(lon, lat)
    return ox.distance.nearest_nodes(G, x, y)


def energy_route(G, orig, dest):
    """Least-energy route. Energy can be negative downhill, so Dijkstra is not valid; Bellman-Ford
    is, as long as the graph has no negative cycle. Physically there is none: a closed loop returns
    to the same height and pays rolling and drag losses, but regeneration below 100% guarantees it;
    we still check and fail loudly instead of returning a wrong route."""
    try:
        return nx.bellman_ford_path(G, orig, dest, weight=_min_weight("energy_kwh"))
    except nx.NetworkXUnbounded:
        raise ValueError("negative energy cycle: check vehicle.regen (<1) and DEM spikes")


def _min_weight(attr):
    # MultiDiGraph: use the cheapest parallel edge
    return lambda u, v, data: min(d[attr] for d in data.values())


def route(G, orig, dest, weight="travel_time"):
    if weight == "energy_kwh":
        path = energy_route(G, orig, dest)
    else:
        path = nx.shortest_path(G, orig, dest, weight=_min_weight(weight))
    return {"weight": weight, "nodes": path, **route_totals(G, path)}


def route_totals(G, path):
    tot = {"length_m": 0.0, "travel_time_s": 0.0, "energy_kwh": 0.0, "climb_m": 0.0}
    for u, v in zip(path[:-1], path[1:]):
        d = min(G[u][v].values(), key=lambda e: e["travel_time"])
        tot["length_m"] += d["length"]
        tot["travel_time_s"] += d["travel_time"]
        tot["energy_kwh"] += d["energy_kwh"]
        tot["climb_m"] += max(0.0, G.nodes[v]["elevation"] - G.nodes[u]["elevation"])
    return {k: round(x, 6 if k == "energy_kwh" else 3) for k, x in tot.items()}


def summary(G):
    grades = [abs(d.get("grade", 0.0)) for *_, d in G.edges(data=True)]
    return {"crs": str(G.graph["crs"]), "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
            "length_km": round(sum(d["length"] for *_, d in G.edges(data=True)) / 1000, 3),
            "oneway_edges": sum(1 for *_, d in G.edges(data=True) if d.get("oneway")),
            "max_abs_grade": round(max(grades), 4) if grades else 0.0,
            "strongly_connected": nx.is_strongly_connected(G)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--osm", help="OSM XML file (offline)")
    src.add_argument("--place", help='place name for an online download, e.g. "Molde, Norway"')
    ap.add_argument("--dem", help="DEM GeoTIFF for elevations (otherwise flat)")
    ap.add_argument("--out", help="write GraphML here")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--route", nargs=2, metavar="LON,LAT", help="origin and destination")
    ap.add_argument("--weight", default="travel_time", choices=["travel_time", "length", "energy_kwh"])
    a = ap.parse_args(argv)
    G = build(osm=a.osm, place=a.place, dem=a.dem)
    out = {}
    if a.summary:
        out["summary"] = summary(G)
    if a.route:
        (o_lon, o_lat), (d_lon, d_lat) = [map(float, p.split(",")) for p in a.route]
        out["route"] = route(G, nearest(G, o_lon, o_lat), nearest(G, d_lon, d_lat), a.weight)
    if a.out:
        ox.save_graphml(G, a.out)
        out["graphml"] = a.out
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
