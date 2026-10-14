#!/usr/bin/env python3
"""towns.json (OSM-derived Molde / Kristiansund graph) -> MATSim network.xml.

    python make_network.py --town molde --out scenario/molde/network.xml

* Nodes: segment endpoints of the largest connected component, x/y in EPSG:32632 (UTM 32N metres, as in towns.json).
* Links: one per direction (both directions of every road: towns.json has no one-way flag), modes="car".
* freespeed: HWY_SPEEDS by class (major 50 km/h, minor 30 km/h; same as the static benchmark) in m/s.
* capacity (veh/h) and permlanes by class: ASSUMED (major 1500 veh/h, minor 600 veh/h, 1 lane), see common.py.
* length: polyline length of the (4 m-simplified) OSM segment in metres.
"""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import common as C


def build(town):
    G = C.build_graph(C.load_town(town))
    ids = {n: f"n{i}" for i, n in enumerate(sorted(G.nodes))}
    net = ET.Element("network", name=f"{town} (towns.json, {C.CRS})")
    nodes = ET.SubElement(net, "nodes")
    for n in sorted(G.nodes):
        ET.SubElement(nodes, "node", id=ids[n], x=str(n[0]), y=str(n[1]))
    links = ET.SubElement(net, "links", capperiod="01:00:00")
    k = 0
    for u, v, e in sorted(G.edges(data=True), key=lambda t: (ids[t[0]], ids[t[1]])):
        for a, b in ((u, v), (v, u)):
            k += 1
            ET.SubElement(links, "link", id=f"l{k}", **{"from": ids[a], "to": ids[b]},
                          length=f"{e['L']:.2f}", freespeed=f"{C.V_KMH[e['cls']] / 3.6:.4f}",
                          capacity=f"{C.CAPACITY[e['cls']] * C.LANES[e['cls']]:.0f}",
                          permlanes=str(C.LANES[e["cls"]]), modes="car")
    return net, G


def write(net, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(net)
    body = ET.tostring(net, encoding="unicode")
    path.write_text('<?xml version="1.0" encoding="utf-8"?>\n'
                    '<!DOCTYPE network SYSTEM "http://www.matsim.org/files/dtd/network_v2.dtd">\n' + body + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--town", choices=C.TOWN_NAMES, default="molde")
    ap.add_argument("--out", type=Path, default=None, help="default: scenario/<town>/network.xml next to this script")
    a = ap.parse_args()
    out = a.out or C.HERE / "scenario" / a.town / "network.xml"
    net, G = build(a.town)
    write(net, out)
    print(f"{a.town}: {G.number_of_nodes()} nodes, {2 * G.number_of_edges()} directed links, "
          f"{sum(e['L'] for *_, e in G.edges(data=True)) / 1000:.1f} km of road -> {out}")


if __name__ == "__main__":
    main()
