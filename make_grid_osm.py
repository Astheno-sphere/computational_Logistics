#!/usr/bin/env python3
"""Write examples/grid_molde.osm: a synthetic 7x7 street grid at Molde harbour.

For tests and lessons only (not real streets). One eastbound one-way street,
one footway that buses must not use, and a hill function for terrain.
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


def hill(x, y, cx=None, cy=None):
    """Terrain for tests: 60 m hill north-west of the harbour (model metres)."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cl_frame as F
    if cx is None:
        cx, cy = F.to_local(LON0 + 1.5 * D_LON, LAT0 + 3.5 * D_LAT)
    return 60.0 * math.exp(-(((x - cx) / 350.0) ** 2 + ((y - cy) / 350.0) ** 2))


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
