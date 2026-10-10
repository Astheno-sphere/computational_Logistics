#!/usr/bin/env python3
"""Plate: a plan is a tree, not a point -> docs/proposal/plates/tree.svg, from plates/proto.json.

Left, the strategic model's answer: one 2050 point. Right, the same question as this project asks it:
a radial tree of every one of the 904 pathways. The centre is 2026; the first ring is the instrument a
pathway opens with; each further ring is the next instrument, switched on at a signpost (the electric
share of crossings reaching 50, 65 or 80%). Every leaf is one pathway, coloured by the share of 1,000
prototype futures in which it meets all three 2050 targets. The widest-margin pathway glows red.

    python docs/proposal/make_plate_tree.py
"""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F"
MONO = 'font-family="Roboto Mono,monospace"'
SANS = 'font-family="Inter,sans-serif"'


def fate(s):
    return SAGE if s >= 0.6 else AMBER if s >= 0.4 else CREAM


def main():
    J = json.loads((HERE / "plates" / "proto.json").read_text())
    P = J["paths"]
    best = P[J["best"]]
    # tree keys: a node is the prefix of (instrument, threshold) steps
    key = lambda r, n: tuple((r["code"][i], (None if i == 0 else r["thr"][i - 1])) for i in range(n))
    leaves = sorted(P, key=lambda r: [(c, t or 0) for c, t in key(r, len(r["code"]))])
    W, H = 700, 262
    cx, cy = 466, 131
    R = [0, 34, 64, 94, 124]
    a0, a1 = np.radians(-150), np.radians(150)                 # arc of the fan (opens to the left)
    ang = {}
    for i, r in enumerate(leaves):
        ang[key(r, len(r["code"]))] = a0 + (a1 - a0) * (i + 0.5) / len(leaves)
    # an inner node sits at the mean angle of its descendants
    desc = defaultdict(list)
    for r in leaves:
        k = key(r, len(r["code"]))
        for n in range(1, len(r["code"]) + 1):
            desc[key(r, n)].append(ang[k])
    pos = lambda k: (cx + R[len(k)] * np.cos(np.mean(desc[k])), cy + R[len(k)] * np.sin(np.mean(desc[k])))
    share_of = {key(r, len(r["code"])): r["share"] for r in P}
    # best share among descendants, to colour inner edges
    bestdesc = defaultdict(float)
    for r in P:
        for n in range(1, len(r["code"]) + 1):
            bestdesc[key(r, n)] = max(bestdesc[key(r, n)], r["share"])
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Radial tree of 904 pathways against a single 2050 point">',
         '<defs><filter id="tg"><feGaussianBlur stdDeviation="2.4"/></filter></defs>']
    for rr in R[1:]:
        o.append(f'<circle cx="{cx}" cy="{cy}" r="{rr}" fill="none" stroke="{CREAM}" stroke-opacity=".07"/>')
    edges = sorted(desc.keys(), key=lambda k: bestdesc[k])
    for k in edges:
        parent = k[:-1]
        x1, y1 = (cx, cy) if not parent else pos(parent)
        x2, y2 = pos(k)
        s = bestdesc[k]
        col = fate(s); op = .65 if s >= 0.6 else .45 if s >= 0.4 else .12
        o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-opacity="{op}" stroke-width="{.5 + 1.4 * (len(k) == 1)}"/>')
    for k, s in share_of.items():
        x, y = pos(k)
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{1.3 if s < .4 else 1.9}" fill="{fate(s)}" fill-opacity="{.3 if s < .4 else .95}"/>')
    # the widest-margin pathway, glowing
    kb = key(best, len(best["code"]))
    pts = [(cx, cy)] + [pos(kb[:n]) for n in range(1, len(kb) + 1)]
    q = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    o.append(f'<polyline points="{q}" fill="none" stroke="{RED}" stroke-width="7" stroke-opacity=".3" filter="url(#tg)"/>')
    o.append(f'<polyline points="{q}" fill="none" stroke="{RED}" stroke-width="2.2"/>')
    bx, by = pts[-1]
    o.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="6" fill="none" stroke="{CREAM}" stroke-width="1.3"/>')
    # first-ring labels
    for c, name in (("P", "package"), ("Z", "zero-emission rate"), ("D", "distance charge"), ("E", "earmarking")):
        x, y = pos(((c, None),))
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9" fill="{INK}" stroke="{CREAM}" stroke-width="1.2"/>')
        o.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" {MONO} font-size="11" font-weight="600" fill="{CREAM}" text-anchor="middle">{c}</text>')
    o.append(f'<circle cx="{cx}" cy="{cy}" r="7" fill="{CREAM}"/>')
    o.append(f'<text x="{cx - 12}" y="{cy + 4}" {MONO} font-size="11" fill="{CREAM}" text-anchor="end">2026</text>')
    # callout for the best leaf
    kx, ky = W - 134, 10
    o.append(f'<path d="M{bx + 6:.1f},{by:.1f} H{kx - 14} L{kx},{ky + 26}" fill="none" stroke="{CREAM}" stroke-opacity=".6"/>')
    o.append(f'<rect x="{kx}" y="{ky}" width="132" height="62" fill="{INK}" stroke="{RED}" stroke-width="1"/>')
    o.append(f'<text x="{kx + 8}" y="{ky + 19}" {SANS} font-weight="800" font-size="13" fill="{CREAM}">earmark, then</text>')
    o.append(f'<text x="{kx + 8}" y="{ky + 35}" {SANS} font-weight="800" font-size="13" fill="{CREAM}">distance charge</text>')
    o.append(f'<text x="{kx + 8}" y="{ky + 53}" {MONO} font-size="11" fill="{RED}">margin +{best["margin"]:.2f}</text>')
    # left: the single point, then the project
    o.append(f'<text x="2" y="18" {MONO} font-size="11" fill="{DIM}" letter-spacing="1.2">A STRATEGIC MODEL</text>')
    o.append(f'<text x="2" y="40" {SANS} font-weight="800" font-size="16" fill="{CREAM}">one point: 2050</text>')
    o.append(f'<text x="2" y="59" {SANS} font-size="12.5" fill="{CREAM}">the end state, if every</text>')
    o.append(f'<text x="2" y="75" {SANS} font-size="12.5" fill="{CREAM}">assumption holds</text>')
    o.append(f'<circle cx="236" cy="46" r="7" fill="{CREAM}"/><circle cx="236" cy="46" r="15" fill="none" stroke="{CREAM}" stroke-opacity=".4"/>')
    o.append(f'<line x1="2" y1="88" x2="250" y2="88" stroke="{CREAM}" stroke-opacity=".25" stroke-dasharray="3 4"/>')
    o.append(f'<text x="2" y="108" {MONO} font-size="11" fill="{DIM}" letter-spacing="1.2">THIS PROJECT</text>')
    o.append(f'<text x="2" y="128" {SANS} font-weight="800" font-size="16" fill="{CREAM}">904 paths, each tested</text>')
    o.append(f'<text x="2" y="145" {SANS} font-size="12" fill="{CREAM}">leaf colour: futures on target, of 1,000</text>')
    o.append(f'<text x="2" y="172" {MONO} font-size="11" fill="{RED}" letter-spacing="1.2">SAME 2050, DIFFERENT FATE</text>')
    pairs = [("1", "DP", [0.5], "distance, then package"), ("2", "PD", [0.8], "package, then distance"),
             ("3", "ED", [0.5], "earmark, distance at 50%"), ("4", "ED", [0.8], "earmark, distance at 80%")]
    look = {(r["code"], tuple(r["thr"])): r for r in P}
    for n, (lab, code, thr, txt) in enumerate(pairs):
        r = look[(code, tuple(thr))]
        yy = 190 + n * 17 + (5 if n >= 2 else 0)
        o.append(f'<circle cx="8" cy="{yy - 4}" r="6.5" fill="{INK}" stroke="{CREAM}" stroke-width="1"/>')
        o.append(f'<text x="8" y="{yy - 0.5}" {MONO} font-size="9.5" fill="{CREAM}" text-anchor="middle">{lab}</text>')
        o.append(f'<text x="20" y="{yy}" {SANS} font-size="12" fill="{CREAM}">{txt}</text>')
        o.append(f'<rect x="174" y="{yy - 9}" width="{r["share"] * 60:.1f}" height="9" fill="{fate(r["share"])}"/>')
        o.append(f'<text x="250" y="{yy}" {MONO} font-size="11" fill="{CREAM}" text-anchor="end">{round(r["share"] * 100)}%</text>')
        # mark the leaf on the tree
        x, y = pos(key(r, len(r["code"])))
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" fill="{INK}" fill-opacity=".85" stroke="{CREAM}" stroke-width="1"/>')
        o.append(f'<text x="{x:.1f}" y="{y + 3.3:.1f}" {MONO} font-size="9.5" fill="{CREAM}" text-anchor="middle">{lab}</text>')
    o.append(f'<path d="M252,46 Q{cx - 140},46 {cx - 128},{cy - 20}" fill="none" stroke="{CREAM}" stroke-opacity=".35" stroke-dasharray="2 4"/>')
    o.append("</svg>")
    (HERE / "plates" / "tree.svg").write_text("".join(o))
    print("tree.svg", round(len("".join(o)) / 1024), "kB; best", best["code"], best["thr"], best["margin"])


if __name__ == "__main__":
    main()
