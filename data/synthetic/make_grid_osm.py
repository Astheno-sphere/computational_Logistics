#!/usr/bin/env python3
"""Write grid_molde.osm: a synthetic 7x7 street grid at Molde harbour.

For tests and lessons only (not real streets). One eastbound one-way street,
and one footway that vehicles must not use. Terrain is added by the caller
(see examples/showcase.py).
"""
from __future__ import print_function

import math
import os

LON0, LAT0 = 7.1592, 62.7375        # Molde harbour
N = 7
D_LAT = 0.0018                      # ~200 m
D_LON = 0.0039                      # ~200 m at this latitude


def node_id(i, j):
    return 1 + i * N + j


def write(path):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<osm version="0.6" generator="cl-examples">']
    for i in range(N):
        for j in range(N):
            lines.append('  <node id="{}" lat="{:.7f}" lon="{:.7f}"/>'.format(
                node_id(i, j), LAT0 + i * D_LAT, LON0 + j * D_LON))
    wid = 1000
    for i in range(N):                       # east-west streets
        wid += 1
        tags = [("highway", "residential"), ("name", "Row {}".format(i))]
        if i == 3:
            tags.append(("oneway", "yes"))  # eastbound only
        if i == 5:
            tags = [("highway", "footway")]  # not drivable
        lines.append('  <way id="{}">'.format(wid))
        lines.extend('    <nd ref="{}"/>'.format(node_id(i, j)) for j in range(N))
        lines.extend('    <tag k="{}" v="{}"/>'.format(k, v) for k, v in tags)
        lines.append('  </way>')
    for j in range(N):                       # north-south streets
        wid += 1
        lines.append('  <way id="{}">'.format(wid))
        lines.extend('    <nd ref="{}"/>'.format(node_id(i, j)) for i in range(N))
        lines.append('    <tag k="highway" v="{}"/>'.format("tertiary" if j == 3 else "residential"))
        lines.append('  </way>')
    lines.append('</osm>')
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    return path


if __name__ == "__main__":
    out = write(os.path.join(os.path.dirname(os.path.abspath(__file__)), "grid_molde.osm"))
    print("wrote", out)
