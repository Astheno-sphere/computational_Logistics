#!/usr/bin/env python3
"""Plate: when does success stop paying? -> docs/proposal/plates/erosion.svg

Top: one hundred crossings drawn at three moments of the prototype's median future (40% electric in
2026, 80% in 2035, 93% in 2041, the end of the package's 15 years), each glyph a crossing, sage electric.
Below: the package exactly as approved, run through the same 1,000 futures as make_proto.py (same seed,
same assumed ranges). Each thin line is one future's revenue divided by debt service; the line at 1.0
is the debt. Futures that sit below it three years running fail, drawn red, and their failure years are
ticked on the axis. Every electric crossing pays NOK 8.16 less while the debt stays where it was.

    python docs/proposal/make_plate_erosion.py
"""
from pathlib import Path

import numpy as np

import make_proto as mp

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F"
MONO = 'font-family="Roboto Mono,monospace"'
SANS = 'font-family="Inter,sans-serif"'


def car(x, y, col, s):
    return (f'<g transform="translate({x:.1f},{y:.1f}) scale({s})">'
            f'<path d="M0,6 h3 l3,-4 h9 l4,4 h4 v4 h-23 z" fill="{col}" fill-opacity="{.9 if col == SAGE else .2}" stroke="{col}" stroke-width="1"/></g>')


def simulate():
    F = mp.futures(np.random.default_rng(2026))
    Y = mp.YEARS
    base = 0.6 * mp.FOSSIL + 0.4 * mp.EV
    debt = base / 1.15
    t = np.arange(len(Y))
    share = 1 / (1 + np.exp(-F["k"][:, None] * (Y[None, :] - (2026 + np.log(1.5) / F["k"][:, None]))))
    price = (1 - share) * mp.FOSSIL + share * mp.EV
    vol = (1 + F["g"][:, None]) ** t * (price / base) ** F["eps"][:, None]
    cover = vol * price / debt
    below = cover < 1
    run3 = below[:, 2:] & below[:, 1:-1] & below[:, :-2]
    fail = run3.any(axis=1)
    fyear = np.where(fail, Y[np.argmax(run3, axis=1)], 0)
    return Y, share, cover, fail, fyear


def main():
    Y, share, cover, fail, fyear = simulate()
    med = np.median(share, axis=0)
    W, H = 470, 300
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="When the toll base stops covering its debt, across 1,000 futures">']
    # three moments, one hundred crossings each
    for k, yr in enumerate((2026, 2035, 2041)):
        ev = int(round(med[list(Y).index(yr)] * 100))
        x0 = 4 + k * 160
        o.append(f'<text x="{x0}" y="12" {MONO} font-size="11.5" font-weight="600" fill="{CREAM}">{yr}</text>')
        o.append(f'<text x="{x0 + 40}" y="12" {MONO} font-size="11" fill="{SAGE}">{ev}% electric</text>')
        for i in range(100):
            r, c = divmod(i, 20)
            o.append(car(x0 + c * 7.4, 20 + r * 8.2, SAGE if i < ev else CREAM, 0.27))
        rev = (ev * mp.EV + (100 - ev) * mp.FOSSIL) / 100
        o.append(f'<text x="{x0}" y="74" {MONO} font-size="11" fill="{AMBER}">NOK {rev:.2f} a crossing</text>')
    # the fan of futures: revenue over debt service
    X0, X1, Y0, Y1 = 34, 462, 96, 236
    X = lambda y: X0 + (y - 2026) / 24 * (X1 - X0)
    V = lambda c: Y1 - (c - 0.80) / 0.50 * (Y1 - Y0)
    o.append(f'<rect x="{X(2026):.1f}" y="{V(1.0):.1f}" width="{X1 - X0}" height="{Y1 - V(1.0):.1f}" fill="{RED}" fill-opacity=".06"/>')
    order = np.argsort(fail)                          # failing futures drawn last, on top
    for i in order[::3] if False else order:
        c = np.clip(cover[i], 0.8, 1.3)
        q = " ".join(f"{X(y):.1f},{V(v):.1f}" for y, v in zip(Y, c))
        col, op, w = (RED, .22, .7) if fail[i] else (CREAM, .05, .6)
        o.append(f'<polyline points="{q}" fill="none" stroke="{col}" stroke-opacity="{op}" stroke-width="{w}"/>')
    mc = np.median(cover, axis=0)
    o.append(f'<polyline points="{" ".join(f"{X(y):.1f},{V(v):.1f}" for y, v in zip(Y, mc))}" fill="none" stroke="{AMBER}" stroke-width="2"/>')
    o.append(f'<line x1="{X0}" y1="{V(1.0):.1f}" x2="{X1}" y2="{V(1.0):.1f}" stroke="{RED}" stroke-width="1.6" stroke-dasharray="6 4"/>')
    o.append(f'<text x="{X0 - 4}" y="{V(1.0) + 4:.1f}" {MONO} font-size="11" fill="{RED}" text-anchor="end">debt</text>')
    o.append(f'<text x="{X0 - 4}" y="{V(1.2) + 4:.1f}" {MONO} font-size="10.5" fill="{DIM}" text-anchor="end">+20%</text>')
    # end of the package's 15 years
    o.append(f'<line x1="{X(2041):.1f}" y1="{Y0 - 6}" x2="{X(2041):.1f}" y2="{Y1}" stroke="{CREAM}" stroke-opacity=".45" stroke-dasharray="2 3"/>')
    o.append(f'<text x="{X(2041) + 4:.1f}" y="{Y0 + 4}" {MONO} font-size="10.5" fill="{CREAM}">package ends 2041</text>')
    o.append(f'<text x="{X(2027):.1f}" y="{V(1.2) - 4:.1f}" {MONO} font-size="10.5" fill="{AMBER}">median future</text>')
    # failure years ticked along the axis
    o.append(f'<line x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}" stroke="{DIM}"/>')
    yrs, cnt = np.unique(fyear[fail], return_counts=True)
    for y, n in zip(yrs, cnt):
        o.append(f'<rect x="{X(y) - 4:.1f}" y="{Y1 + 2}" width="8" height="{n * 0.32:.1f}" fill="{RED}" fill-opacity=".85"/>')
    for y in (2026, 2035, 2041, 2050):
        o.append(f'<text x="{X(y):.1f}" y="{Y1 + 34}" {MONO} font-size="11" fill="{DIM}" text-anchor="{'end' if y == 2050 else 'start' if y == 2026 else 'middle'}">{y}</text>')
    o.append(f'<text x="{X(2026.4):.1f}" y="{V(0.93):.1f}" {SANS} font-size="12.5" font-weight="700" fill="{CREAM}">What replaces the lost revenue,</text>')
    o.append(f'<text x="{X(2026.4):.1f}" y="{V(0.93) + 16:.1f}" {SANS} font-size="12.5" font-weight="700" fill="{CREAM}">and will the people who pay <tspan fill="{RED}">accept it?</tspan></text>')
    by41 = (fail & (fyear <= 2041)).mean()
    o.append(f'<text x="{X0}" y="{H - 14}" {SANS} font-weight="800" font-size="14" fill="{RED}">{by41 * 100:.0f}% of futures</text>')
    o.append(f'<text x="{X0 + 106}" y="{H - 14}" {SANS} font-size="12.5" fill="{CREAM}">fail to cover the debt before 2041; {fail.mean() * 100:.0f}% by 2050</text>')
    o.append(f'<text x="{X0}" y="{H - 1}" {MONO} font-size="10" fill="{DIM}">each line one future: revenue ÷ debt service · red: three years below</text>')
    o.append("</svg>")
    (HERE / "plates" / "erosion.svg").write_text("".join(o))
    print("erosion.svg ok · fail by 2041", round(by41, 3), "by 2050", round(fail.mean(), 3), "median shares", [round(float(med[list(Y).index(y)]), 2) for y in (2026, 2035, 2041)])


if __name__ == "__main__":
    main()
