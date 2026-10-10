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
    # 2 (k=1): futures, the chosen pathway's acceptance in 120 prototype futures (red if it ever falls below that future's threshold)
    J = json.loads((HERE / "plates" / "proto.json").read_text())
    g = []
    for traj, lam in zip(J["chosen_A"], J["chosen_lam"]):
        traj = np.array(traj); fail = (traj < lam).any()
        u = np.linspace(0.02, 0.98, len(traj)); v = np.clip(1.15 - 1.2 * traj, 0.03, 0.97)
        col, op, sw = (RED, .55, .7) if fail else (SAGE, .45, .6)
        q = " ".join("%.1f,%.1f" % (CX + (uu - vv) * A, TOP + 1 * GAP + (uu + vv) * B) for uu, vv in zip(u, v))
        g.append(f'<polyline points="{q}" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{sw}"/>')
    layers.append((1, "".join(g)))
    # 1 (k=0, top): the five picked pathways as lines, stations at their signposts, the widest-margin one in red
    g = []
    P = J["paths"]
    for j, i in enumerate(J["pick"]):
        r = P[i]; lab = "ABCDE"[j]
        col = RED if i == J["best"] else (SAGE if r["share"] >= 0.6 else AMBER if r["share"] >= 0.4 else CREAM)
        w = 3.0 if col == RED else 1.5
        v0 = 0.14 + j * 0.18
        st = [0.40] + list(r["thr"])
        P2 = [(CX + (a - v0) * A, TOP + (a + v0) * B) for a in (0.04, 0.96)]
        q = " ".join("%.1f,%.1f" % p for p in P2)
        if col == RED:
            g.append(f'<polyline points="{q}" fill="none" stroke="{RED}" stroke-width="7" stroke-opacity=".25" filter="url(#g)"/>')
        g.append(f'<polyline points="{q}" fill="none" stroke="{col}" stroke-width="{w}"/>')
        for e_, c_ in zip(st, r["code"]):
            a = 0.04 + (e_ - 0.40) / 0.60 * 0.92
            px_, py_ = CX + (a - v0) * A, TOP + (a + v0) * B
            g.append(f'<circle cx="{px_:.1f}" cy="{py_:.1f}" r="4.6" fill="{INK}" stroke="{col}" stroke-width="1.4"/>')
        a0x, a0y = P2[0]
        g.append(f'<text x="{a0x - 8:.1f}" y="{a0y + 4:.1f}" font-family="Roboto Mono,monospace" font-size="11" fill="{col}" text-anchor="end">{lab}</text>')
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
