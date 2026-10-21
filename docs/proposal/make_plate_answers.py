#!/usr/bin/env python3
"""Plate: one place, two answers -> docs/proposal/plates/answers.svg

The real blocks around Nordsundbrua (layers.json, OpenStreetMap; nominal heights 7, 13 and 9 m for homes,
flats and work until heights are sourced) drawn in axonometric twice. Left: the strategic model's answer,
one settled 2050. Right: the same place as a path, 2026, 2035 and 2050 stacked, each slab carrying what the
prototype computes for that year: the electric share of crossings (cars on rv. 70 lit in sage), what a
crossing earns (27.20 - 8.16 x share) and median acceptance on the chosen pathway (plates/proto.json).

    python docs/proposal/make_plate_answers.py
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F"
MONO = 'font-family="Roboto Mono,monospace"'
BX, BY, R = 437060, 6999020, 340            # window centred on the bridge
HEIGHT = {"home": 7, "flat": 13, "work": 9}


def main():
    L = json.loads((HERE / "layers.json").read_text())
    side = json.loads((HERE / "plates" / "halves.json").read_text())["sides"]
    J = json.loads((HERE / "plates" / "proto.json").read_text())
    yrs = J["years"]
    ev = {y: J["ev_median"][yrs.index(y)] for y in (2026, 2035, 2050)}
    acc = {y: J["acc_median"][yrs.index(y)] for y in (2026, 2035, 2050)}
    blds = [(c, r, s) for (c, r), s in zip(L["buildings"], side)
            if abs(np.mean([p[0] for p in r]) - BX) < R and abs(np.mean([p[1] for p in r]) - BY) < R]
    roads = [[p for p in w if abs(p[0] - BX) < R and abs(p[1] - BY) < R] for w in L["roads"]]
    rv = [[p for p in w if abs(p[0] - BX) < R and abs(p[1] - BY) < R] for w in L["rv70"]]
    rv_pts = np.array([p for w in rv for p in w])
    rng = np.random.default_rng(5)
    car_idx = np.sort(rng.choice(len(rv_pts), min(36, len(rv_pts)), replace=False))
    car_order = rng.permutation(len(car_idx))

    def make_iso(cx, cy, a, b):
        def iso(x, y, z=0.0):
            u = (x - (BX - R)) / (2 * R); v = ((BY + R) - y) / (2 * R)
            return cx + (u - v) * a, cy + (u + v) * b - z
        return iso

    def block(iso, zscale, ev_share, label=None, slab_col=CREAM):
        g = []
        c = [iso(BX - R, BY + R), iso(BX + R, BY + R), iso(BX + R, BY - R), iso(BX - R, BY - R)]
        g.append('<polygon points="%s" fill="#221b16" stroke="%s" stroke-opacity=".55" stroke-width=".8"/>' % (" ".join("%.1f,%.1f" % p for p in c), slab_col))
        for w in roads:
            if len(w) > 1:
                g.append('<polyline points="%s" fill="none" stroke="%s" stroke-opacity=".28" stroke-width=".5"/>' % (" ".join("%.1f,%.1f" % iso(*p) for p in w), CREAM))
        for w in rv:
            if len(w) > 1:
                g.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.4"/>' % (" ".join("%.1f,%.1f" % iso(*p) for p in w), AMBER))
        order = sorted(blds, key=lambda t: iso(np.mean([p[0] for p in t[1]]), np.mean([p[1] for p in t[1]]))[1])
        for cl, r, s in order:
            h = HEIGHT.get(cl, 7) * zscale
            ring = r + [r[0]]
            base = [iso(*p) for p in ring]; top = [iso(p[0], p[1], h) for p in ring]
            g.append('<polygon points="%s" fill="#0b0806" fill-opacity=".8"/>' % " ".join("%.1f,%.1f" % (x + h * .35, y + h * .15) for x, y in base))
            light, dark = ("#b8473a", "#7a2c24") if s == 1 else ("#bfb4a0", "#7d7466")
            for (x1_, y1_), (x2_, y2_), (x3_, y3_), (x4_, y4_) in zip(base[:-1], base[1:], top[1:], top[:-1]):
                if y2_ + y1_ < y3_ + y4_ + 2 * h - 0.01 or True:
                    shade = light if (x2_ - x1_) > 0 else dark
                    g.append(f'<polygon points="{x1_:.1f},{y1_:.1f} {x2_:.1f},{y2_:.1f} {x3_:.1f},{y3_:.1f} {x4_:.1f},{y4_:.1f}" fill="{shade}"/>')
            g.append('<polygon points="%s" fill="%s" stroke="#0b0806" stroke-width=".3"/>' % (" ".join("%.1f,%.1f" % q for q in top), RED if s == 1 else CREAM))
        n_ev = int(round(ev_share * len(car_idx)))
        for k, i in enumerate(car_idx):
            x, y = iso(*rv_pts[i], 1.0)
            col = SAGE if car_order[k] < n_ev else CREAM
            g.append(f'<rect x="{x - 2.7:.1f}" y="{y - 1.6:.1f}" width="5.4" height="3.2" fill="{col}" stroke="{INK}" stroke-width=".4"/>')
        return "".join(g)

    W, H = 600, 352
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="One place drawn twice: one settled 2050, and the same place as a path 2026, 2035, 2050">']
    # left: one answer
    isoL = make_iso(150, 92, 128, 74)
    o.append(block(isoL, 0.9, ev[2050]))
    o.append(f'<text x="18" y="22" {MONO} font-size="11" fill="{DIM}" letter-spacing="1.2">LEFT · THE STRATEGIC MODEL</text>')
    o.append(f'<text x="18" y="40" font-family="Inter,sans-serif" font-weight="800" font-size="15" fill="{CREAM}">One answer: 2050</text>')
    o.append(f'<text x="18" y="{H - 52}" font-family="Inter,sans-serif" font-size="12" fill="{CREAM}">one settled state, every car</text>')
    o.append(f'<text x="18" y="{H - 36}" font-family="Inter,sans-serif" font-size="12" fill="{CREAM}">already where it ends up</text>')
    o.append(f'<text x="18" y="{H - 16}" {MONO} font-size="10" fill="{DIM}">no year in between · heights 3x</text>')
    o.append(f'<line x1="298" y1="14" x2="298" y2="{H - 10}" stroke="{CREAM}" stroke-opacity=".3" stroke-dasharray="3 4"/>')
    # right: the path, three slabs
    o.append(f'<text x="312" y="22" {MONO} font-size="11" fill="{DIM}" letter-spacing="1.2">RIGHT · THIS PROJECT</text>')
    o.append(f'<text x="312" y="40" font-family="Inter,sans-serif" font-weight="800" font-size="15" fill="{CREAM}">The same place as a <tspan fill="{RED}">path</tspan></text>')
    for k, y in enumerate((2050, 2035, 2026)):
        cy = 56 + k * 94
        iso = make_iso(392, cy, 74, 42)
        o.append(block(iso, 0.55, ev[y]))
        tx = 478
        rev = 27.20 - 8.16 * ev[y]
        o.append(f'<text x="{tx}" y="{cy + 22}" {MONO} font-size="13" font-weight="600" fill="{CREAM}">{y}</text>')
        o.append(f'<text x="{tx}" y="{cy + 38}" {MONO} font-size="9.5" fill="{SAGE}">{int(round(ev[y] * 100))}% electric</text>')
        o.append(f'<text x="{tx}" y="{cy + 52}" {MONO} font-size="9.5" fill="{AMBER}">NOK {rev:.2f}/crossing</text>')
        o.append(f'<text x="{tx}" y="{cy + 66}" {MONO} font-size="9.5" fill="{RED}">acceptance {acc[y]:.2f}</text>')
        if k < 2:
            o.append(f'<line x1="400" y1="{cy + 84}" x2="400" y2="{cy + 104}" stroke="{CREAM}" stroke-opacity=".4" stroke-dasharray="2 3"/>')
    o.append(f'<text x="312" y="{H - 6}" {MONO} font-size="9.5" fill="{DIM}">years from the prototype run, pathway E, page 5 · heights 3x</text>')
    o.append("</svg>")
    (HERE / "plates" / "answers.svg").write_text("".join(o))
    print("answers.svg", round(len("".join(o)) / 1024), "kB;", len(blds), "buildings;", "ev", ev, "acc", acc)


if __name__ == "__main__":
    main()
