#!/usr/bin/env python3
"""Plate: the robust front -> docs/proposal/plates/front.svg, from plates/proto.json (make_proto.py).

Every one of the 904 pathways is a dot: acceptance margin across, share of the 1,000 futures meeting all
three 2050 targets up. Ghosts fail most futures; amber meet 40 to 60%; sage meet 60% or more. The five
picked pathways (the non-dominated points, filled out along the upper envelope) drop into a strip of lines
whose stations are the signposts: the electric share of crossings at which each instrument switches on.

    python docs/proposal/make_plate_front.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F"
NAMES = {"P": "package revision", "Z": "zero-emission rate", "D": "distance charge", "E": "earmarking"}
MONO = 'font-family="Roboto Mono,monospace"'


def main():
    J = json.loads((HERE / "plates" / "proto.json").read_text())
    P = J["paths"]
    W, H = 1000, 625
    X0, X1, Y0, Y1 = 70, 960, 30, 330                     # scatter box
    mx0, mx1, sy1 = -0.31, 0.10, 0.80
    X = lambda m: X0 + (m - mx0) / (mx1 - mx0) * (X1 - X0)
    Y = lambda s: Y1 - s / sy1 * (Y1 - Y0)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Robust front of 904 pathways">',
         '<defs><filter id="gl"><feGaussianBlur stdDeviation="3"/></filter></defs>']
    # axes and grid
    for s in (0.2, 0.4, 0.6):
        o.append(f'<line x1="{X0}" y1="{Y(s):.1f}" x2="{X1}" y2="{Y(s):.1f}" stroke="{CREAM}" stroke-opacity=".08"/>')
        o.append(f'<text x="{X0 - 8}" y="{Y(s) + 4:.1f}" {MONO} font-size="15" fill="{DIM}" text-anchor="end">{int(s * 100)}%</text>')
    o.append(f'<line x1="{X(0):.1f}" y1="{Y0}" x2="{X(0):.1f}" y2="{Y1}" stroke="{CREAM}" stroke-opacity=".35" stroke-dasharray="4 4"/>')
    o.append(f'<text x="{X(0) - 6:.1f}" y="{Y1 - 8}" {MONO} font-size="13" fill="{CREAM}" text-anchor="end">margin 0</text>')
    o.append(f'<text x="{X(-0.3) + 4:.1f}" y="{Y(0.5):.1f}" {MONO} font-size="13" fill="{DIM}">no margin at any rise</text>')
    o.append(f'<line x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}" stroke="{DIM}"/><line x1="{X0}" y1="{Y0}" x2="{X0}" y2="{Y1}" stroke="{DIM}"/>')
    for m in (-0.3, -0.2, -0.1, 0.0, 0.1):
        o.append(f'<text x="{X(m):.1f}" y="{Y1 + 16}" {MONO} font-size="15" fill="{DIM}" text-anchor="middle">{m:+.1f}</text>')
    o.append(f'<text x="{(X0 + X1) / 2:.0f}" y="{Y1 + 34}" {MONO} font-size="15" fill="{DIM}" text-anchor="middle" letter-spacing="1.5">ACCEPTANCE MARGIN</text>')
    o.append(f'<text x="18" y="{(Y0 + Y1) / 2:.0f}" {MONO} font-size="15" fill="{DIM}" text-anchor="middle" letter-spacing="1.5" transform="rotate(-90 18 {(Y0 + Y1) / 2:.0f})">FUTURES ON TARGET</text>')
    # dots, with deterministic jitter so ties stay visible
    for n, r in enumerate(P):
        jx = ((n * 37) % 11 - 5) * 0.0011; jy = ((n * 53) % 9 - 4) * 0.0018
        s, m = r["share"], max(r["margin"], -0.305)
        if s >= 0.6:
            o.append(f'<circle cx="{X(m + jx):.1f}" cy="{Y(s + jy):.1f}" r="3.6" fill="{SAGE}"/>')
        elif s >= 0.4:
            o.append(f'<circle cx="{X(m + jx):.1f}" cy="{Y(s + jy):.1f}" r="3.0" fill="{AMBER}" fill-opacity=".85"/>')
        else:
            o.append(f'<circle cx="{X(m + jx):.1f}" cy="{Y(s + jy):.1f}" r="2.4" fill="{CREAM}" fill-opacity=".16"/>')
    # upper envelope
    env = [P[i] for i in J["envelope"]]
    q = " ".join(f"{X(r['margin']):.1f},{Y(r['share']):.1f}" for r in env)
    o.append(f'<polyline points="{q}" fill="none" stroke="{CREAM}" stroke-opacity=".5" stroke-width="1" stroke-dasharray="3 3"/>')
    o.append(f'<text x="{X(env[-1]["margin"]) - 4:.1f}" y="{Y(env[-1]["share"]) - 46:.1f}" {MONO} font-size="14" fill="{CREAM}" text-anchor="end">best pathway at each margin</text>')
    # picked pathways
    letters = "ABCDE"
    strip_y0, gap = 446, 31
    sx0, sx1 = 300, 800
    E = lambda e: sx0 + (e - 0.40) / 0.60 * (sx1 - sx0)
    for k, i in enumerate(J["pick"]):
        r = P[i]; col = RED if i == J["best"] else (SAGE if r["share"] >= 0.6 else AMBER if r["share"] >= 0.4 else CREAM)
        cx, cy = X(r["margin"]), Y(r["share"])
        o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" stroke="{CREAM}" stroke-width="1.3"/>')
        o.append(f'<text x="{cx + 12:.1f}" y="{cy - 10:.1f}" {MONO} font-size="18" font-weight="600" fill="{col}">{letters[k]}</text>')
        ly = strip_y0 + k * gap
        # leader from dot down to its strip line (dashed, faint)
        o.append(f'<path d="M{cx:.1f},{cy + 9:.1f} V{Y1 + 44} " stroke="{col}" stroke-opacity=".35" stroke-dasharray="2 3" fill="none"/>')
        # strip line: stations at 40% (start) and each threshold
        stations = [(0.40, r["code"][0])] + [(t, c) for t, c in zip(r["thr"], r["code"][1:])]
        if col == RED:
            o.append(f'<line x1="{sx0}" y1="{ly}" x2="{sx1}" y2="{ly}" stroke="{RED}" stroke-width="8" stroke-opacity=".22" filter="url(#gl)"/>')
        o.append(f'<line x1="{sx0}" y1="{ly}" x2="{sx1}" y2="{ly}" stroke="{col}" stroke-width="{3 if col == RED else 1.8}"/>')
        for t, c in stations:
            x = E(t)
            o.append(f'<circle cx="{x:.1f}" cy="{ly}" r="10" fill="{INK}" stroke="{col}" stroke-width="1.6"/>')
            o.append(f'<text x="{x:.1f}" y="{ly + 4}" {MONO} font-size="12" font-weight="600" fill="{CREAM}" text-anchor="middle">{c}</text>')
        o.append(f'<text x="{sx0 - 16}" y="{ly + 5}" {MONO} font-size="16" font-weight="600" fill="{col}" text-anchor="end">{letters[k]}</text>')
        seq = " then ".join(NAMES[c] for c in r["code"])
        short = " → ".join({"P": "package", "Z": "ZE rate", "D": "distance", "E": "earmark"}[c] for c in r["code"])
        o.append(f'<text x="{sx0 - 34}" y="{ly + 5}" font-family="Inter,sans-serif" font-size="13.5" fill="{CREAM}" text-anchor="end">{short}</text>')
        o.append(f'<text x="{sx1 + 14}" y="{ly + 4}" {MONO} font-size="14" fill="{CREAM}">{int(round(r["share"] * 100))}% · {r["margin"]:+.2f}</text>')
    winners = sorted(J["pick"], key=lambda i: -P[i]["share"])[:1] + [J["best"]]
    bx0, by0 = X(-0.245), Y(0.70)
    o.append(f'<rect x="{bx0 - 10:.0f}" y="{by0 - 22:.0f}" width="420" height="78" fill="{INK}" stroke="{CREAM}" stroke-opacity=".5"/>')
    for n, i in enumerate(winners):
        r = P[i]; lab = "ABCDE"[J["pick"].index(i)]
        txt = (f"{lab} · distance charge alone: {round(r['share'] * 100)}% of futures on target" if n == 0 else
               f"{lab} · earmark first, distance charge at 50% electric: widest margin")
        col = SAGE if n == 0 else RED
        o.append(f'<text x="{bx0:.0f}" y="{by0 + n * 30:.0f}" font-family="Inter,sans-serif" font-size="15" font-weight="700" fill="{col}">{txt}</text>')
    o.append(f'<text x="{bx0:.0f}" y="{by0 + 50:.0f}" {MONO} font-size="12.5" fill="{DIM}">coverage against acceptance: the trade-off the thesis estimates</text>')
    for e in (0.4, 0.5, 0.65, 0.8, 1.0):
        o.append(f'<text x="{E(e):.1f}" y="{strip_y0 - 18}" {MONO} font-size="14" fill="{DIM}" text-anchor="middle">{int(e * 100)}%</text>')
    o.append(f'<text x="{sx0}" y="{strip_y0 - 36}" {MONO} font-size="14" fill="{DIM}" letter-spacing="1.2">SIGNPOST · ELECTRIC SHARE THAT SWITCHES IT ON</text>')
    o.append(f'<text x="{sx1 + 14}" y="{strip_y0 - 40}" {MONO} font-size="13" fill="{DIM}">futures · margin</text>')
    # key for instruments
    ky = strip_y0 + 5 * gap + 4
    key = "  ·  ".join(f"{c} {n}" for c, n in NAMES.items())
    o.append(f'<text x="{sx0}" y="{ky}" {MONO} font-size="14" fill="{CREAM}" fill-opacity=".8">{key}</text>')
    # run box
    o.append(f'<rect x="{X(-0.16):.0f}" y="{Y(0.30):.0f}" width="330" height="92" fill="{INK}" stroke="{CREAM}" stroke-opacity=".6"/>')
    for n, line in enumerate(("904 PATHWAYS · 1,000 FUTURES", "2026 TO 2050 · 22.6 M PATHWAY-YEARS",
                              f"SAGE {J['robust']} · AMBER {J['near']} · GHOST {J['fail']}", "PROTOTYPE · PARAMETERS ASSUMED")):
        o.append(f'<text x="{X(-0.16) + 320:.0f}" y="{Y(0.30) + 22 + n * 20:.0f}" {MONO} font-size="13" fill="{CREAM}" text-anchor="end">{line}</text>')
    o.append("</svg>")
    (HERE / "plates" / "front.svg").write_text("".join(o))
    print("front.svg", round(len("".join(o)) / 1024), "kB")


if __name__ == "__main__":
    main()
