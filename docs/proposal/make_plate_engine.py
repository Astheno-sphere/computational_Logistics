#!/usr/bin/env python3
"""Plate: the engine, five layers and three claims -> docs/proposal/plates/engine.svg

An exploded axonometric drawn as vector from the project's own data. Layer 1 is Kristiansund's building
footprints (layers.json, OpenStreetMap); layer 2 a sample of homes standing for survey respondents;
layer 3 every building as an agent, coloured by its measured exposure (halves.json: Nordlandet, beyond
the toll bridge, in red); layers 4 and 5 show the shape of the ensemble and the pathway strip and are
illustrative until the prototype ensemble runs (the plate says so).

    python docs/proposal/make_plate_engine.py
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, TEAL, INK = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#7CBAC4", "#16120F"
W, H = 640, 712
CX, A, B = 445, 180, 80          # slab centre x, half-width and half-depth of the isometric slab
TOP, GAP = 26, 128               # y of the top slab's back corner, vertical gap between layers


def main():
    L = json.loads((HERE / "layers.json").read_text())
    S = json.loads((HERE / "plates" / "halves.json").read_text())["sides"]
    rng = np.random.default_rng(11)
    pts = np.array([p for _, r in L["buildings"] for p in r])
    x0, y0 = pts.min(axis=0); x1, y1 = pts.max(axis=0)
    x0, x1, y0, y1 = 433200, 439500, 6998100, 7000720            # same frame as the halves plate
    aspect = (y1 - y0) / (x1 - x0)

    def iso(x, y, k):
        """map metres to the slab of layer k (0 = top)."""
        u = (x - x0) / (x1 - x0); v = (y1 - y) / (y1 - y0)
        return CX + (u - v) * A, TOP + k * GAP + (u + v) * B

    def slab(k):
        c = [iso(x0, y1, k), iso(x1, y1, k), iso(x1, y0, k), iso(x0, y0, k)]
        return c, " ".join(f"{a:.1f},{b:.1f}" for a, b in c)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" '
           f'aria-label="Exploded axonometric of the engine: data, estimated choice, agents with memory, futures, pathways">',
           f'<defs><filter id="g"><feGaussianBlur stdDeviation="2.2"/></filter></defs>']
    # dashed verticals at the slab corners, behind everything
    c_top, _ = slab(0); c_bot, _ = slab(4)
    for (a, b), (c, d) in zip(c_top, c_bot):
        out.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{c:.1f}" y2="{d:.1f}" stroke="{CREAM}" stroke-opacity=".25" stroke-dasharray="3 4"/>')

    inside = [(c, r, s) for (c, r), s in zip(L["buildings"], S)
              if x0 < np.mean([p[0] for p in r]) < x1 and y0 < np.mean([p[1] for p in r]) < y1]
    layers = []
    # 5 (bottom, k=4): data, footprints
    g = []
    for c, r, s in inside[::2]:
        q = " ".join("%.1f,%.1f" % iso(px, py, 4) for px, py in r)
        g.append(f'<polygon points="{q}" fill="{CREAM}" fill-opacity=".9" stroke="none"/>')
    for w in L["roads"]:
        q = " ".join("%.1f,%.1f" % iso(px, py, 4) for px, py in w if x0 < px < x1 and y0 < py < y1)
        if q.count(",") > 1:
            g.append(f'<polyline points="{q}" fill="none" stroke="{CREAM}" stroke-opacity=".45" stroke-width=".6"/>')
    layers.append((4, "".join(g)))
    # 4 (k=3): respondents, a sample of homes
    homes = [r for c, r, s in inside if c in ("home", "flat")]
    idx = rng.choice(len(homes), 420, replace=False)
    g = []
    for i in idx:
        cx_, cy_ = np.mean(homes[i], axis=0); a, b = iso(cx_, cy_, 3)
        g.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="1.9" fill="{AMBER}"/>')
    layers.append((3, "".join(g)))
    # 3 (k=2): agents, every building, by measured exposure
    g = []
    for c, r, s in inside[::3]:
        cx_, cy_ = np.mean(r, axis=0); a, b = iso(cx_, cy_, 2)
        col = RED if s == 1 else CREAM
        g.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="1.5" fill="{col}" fill-opacity="{0.95 if s == 1 else 0.6}"/>')
    layers.append((2, "".join(g)))
    # 2 (k=1): futures, a fan of random walks across the slab (illustrative shape of 10^3 futures)
    g = []
    n = 110
    for j in range(n):
        v = 0.5 + np.cumsum(rng.normal(0, 0.026, 60)); v = np.clip(v, 0.03, 0.97)
        u = np.linspace(0.02, 0.98, 60)
        fate = "fail" if v[-1] < 0.28 else ("robust" if v[-1] > 0.55 else "near")
        col, op, sw = {"fail": (RED, .35, .6), "robust": (SAGE, .5, .65), "near": (CREAM, .12, .45)}[fate]
        q = " ".join("%.1f,%.1f" % (CX + (uu - vv) * A, TOP + 1 * GAP + (uu + vv) * B) for uu, vv in zip(u, v))
        g.append(f'<polyline points="{q}" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{sw}"/>')
    layers.append((1, "".join(g)))
    # 1 (k=0, top): pathways strip, five lines with signposts, the chosen one in red
    g = []
    for j, (lab, col, w) in enumerate([("A", SAGE, 1.6), ("B", SAGE, 1.6), ("C", RED, 3.0), ("D", CREAM, 1.2), ("E", CREAM, 1.2)]):
        v0 = 0.18 + j * 0.16
        uu = np.array([0.04, 0.3, 0.34, 0.58, 0.62, 0.96]); vv = np.array([v0, v0, v0 + 0.05, v0 + 0.05, v0 - 0.02, v0 - 0.02])
        P = [(CX + (a - b) * A, TOP + (a + b) * B) for a, b in zip(uu, vv)]
        q = " ".join("%.1f,%.1f" % p for p in P)
        if lab == "C":
            g.append(f'<polyline points="{q}" fill="none" stroke="{RED}" stroke-width="7" stroke-opacity=".25" filter="url(#g)"/>')
        g.append(f'<polyline points="{q}" fill="none" stroke="{col}" stroke-width="{w}"/>')
        for k in (1, 3):
            a, b = P[k]
            g.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.6" fill="{INK}" stroke="{col}" stroke-width="1.4"/>')
        a, b = P[0]
        g.append(f'<text x="{a - 8:.1f}" y="{b + 4:.1f}" font-family="Roboto Mono,monospace" font-size="10" fill="{col}" text-anchor="end">{lab}</text>')
    layers.append((0, "".join(g)))

    labels = {
        0: ("05", "PATHWAYS", "904 orders, 4 instruments", "claim 1 · claim 3 · A3", RED),
        1: ("04", "10³ FUTURES", "EMA Workbench", "claim 2", SAGE),
        2: ("03", "AGENTS", "acceptance remembered, ρ", "claim 1 · A1", RED),
        3: ("02", "ESTIMATED CHOICE", "two waves · Biogeme", "A2", AMBER),
        4: ("01", "DATA", "OSM · register · counts", "Kristiansund, real", CREAM),
    }
    for k in (4, 3, 2, 1, 0):                  # bottom first, so upper slabs occlude
        _, poly = slab(k)
        out.append(f'<polygon points="{poly}" fill="{INK}" fill-opacity=".92" stroke="{CREAM}" stroke-opacity=".75" stroke-width="1"/>')
        out.append(dict(layers)[k])
        no, head, sub, tag, col = labels[k]
        ly = TOP + k * GAP + B * 0.9
        out.append(f'<text x="14" y="{ly - 20:.0f}" font-family="Roboto Mono,monospace" font-size="13" fill="{col}" letter-spacing="1">{no}</text>')
        out.append(f'<text x="14" y="{ly:.0f}" font-family="Inter,sans-serif" font-weight="800" font-size="17" fill="{CREAM}">{head}</text>')
        out.append(f'<text x="14" y="{ly + 19:.0f}" font-family="Inter,sans-serif" font-size="13.5" fill="{DIM}">{sub}</text>')
        out.append(f'<text x="14" y="{ly + 37:.0f}" font-family="Roboto Mono,monospace" font-size="12.5" fill="{col}">{tag}</text>')
        lx = iso(x0, y1, k)[0] + (iso(x0, y0, k)[0] - iso(x0, y1, k)[0]) * 0.5
        out.append(f'<line x1="236" y1="{ly - 4:.0f}" x2="{lx - 6:.0f}" y2="{ly - 4:.0f}" stroke="{CREAM}" stroke-opacity=".35" stroke-dasharray="2 3"/>')
    # the bridge, ringed on the agent layer
    bx, by = iso(437020, 6999096, 2)
    out.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="9" fill="none" stroke="{CREAM}" stroke-width="1.2"/>')
    out.append('</svg>')
    (HERE / "plates").mkdir(exist_ok=True)
    (HERE / "plates" / "engine.svg").write_text("".join(out))
    print("engine.svg", round(len("".join(out)) / 1024), "kB;", len(inside), "buildings in frame, respondents 420")


if __name__ == "__main__":
    main()
