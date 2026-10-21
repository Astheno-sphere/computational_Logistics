#!/usr/bin/env python3
"""Kristiansund as a Rhino model -> docs/proposal/rhino/kristiansund.3dm

Writes the computed map layers (layers.json, from OpenStreetMap) into a .3dm file with one Rhino layer
per class, in UTM 32N metres: building footprints by use (extruded to a nominal 7 m until heights are
sourced), the drivable network, rv. 70, bus routes, and the bridge at Nordsundbrua (bridge.json). Open
it in Rhino and compose figures in Grasshopper (Heron can add terrain and further GIS layers).

    python docs/proposal/make_rhino.py
"""
import json
from pathlib import Path

import rhino3dm as r

HERE = Path(__file__).resolve().parent
COLOURS = {"home": (236, 227, 210), "flat": (210, 200, 182), "work": (212, 165, 48), "roads": (148, 139, 126),
           "rv70": (210, 65, 43), "bus": (124, 186, 196), "bridge": (210, 65, 43)}


def main():
    L = json.loads((HERE / "layers.json").read_text())
    B = json.loads((HERE / "bridge.json").read_text())
    m = r.File3dm()
    m.Settings.ModelUnitSystem = r.UnitSystem.Meters
    idx = {}
    for name, (cr, cg, cb) in COLOURS.items():
        lay = r.Layer(); lay.Name = name; lay.Color = (cr, cg, cb, 255)
        idx[name] = m.Layers.Add(lay)

    def attrs(layer):
        a = r.ObjectAttributes(); a.LayerIndex = idx[layer]; return a

    def polyline(pts, closed=False):
        pl = r.Polyline([r.Point3d(x, y, 0) for x, y in pts] + ([r.Point3d(*pts[0], 0)] if closed else []))
        return pl.ToPolylineCurve()

    n = 0
    for cls, ring in L["buildings"]:
        if len(ring) < 3:
            continue
        ext = r.Extrusion.Create(polyline(ring, closed=True), 7.0, True)
        if ext:
            m.Objects.AddExtrusion(ext, attrs(cls)); n += 1
    for layer in ("roads", "rv70", "bus"):
        for pts in L[layer]:
            if len(pts) > 1:
                m.Objects.AddCurve(polyline(pts), attrs(layer))
    for x, y in B["bridge_xy"]:
        m.Objects.AddPoint(r.Point3d(x, y, 0), attrs("bridge"))
    out = HERE / "rhino" / "kristiansund.3dm"
    out.parent.mkdir(exist_ok=True)
    m.Write(str(out), 8)
    print("buildings", n, "roads", len(L["roads"]), "rv70", len(L["rv70"]), "bus", len(L["bus"]),
          "->", out, round(out.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
