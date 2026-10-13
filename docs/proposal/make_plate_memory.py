#!/usr/bin/env python3
"""Plate: what memory does -> docs/proposal/plates/memory.svg

Equation (2) worked through for three people with the values printed on the plate (illustrative, not
estimates): A(t) = rho * A(t-1) + (1 - rho) * (a0 - kappa * bill(t)), where bill is the monthly toll
relative to a daily fossil commuter's (44 crossings at NOK 27.20). The instruments are the same for all
three: the package from 2026, the zero-emission discount, a distance charge in 2035 that ends it.
The commuter buys an electric car in 2029; the van goes electric in 2033. Memory rho decides how fast each
person's acceptance follows their bill, and whether it dips below the threshold lambda.

    python docs/proposal/make_plate_memory.py
"""
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK, TEAL = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F", "#7CBAC4"
MONO = 'font-family="Roboto Mono,monospace"'
SANS = 'font-family="Inter,sans-serif"'
YEARS = np.arange(2024, 2041)
LAM = 0.38


def bills(dose, ev_year):
    b = np.zeros(len(YEARS))
    for i, y in enumerate(YEARS):
        if y < 2026:
            continue
        rate = 27.20
        if ev_year and y >= ev_year:
            rate = 19.04
        if y >= 2035:
            rate = 24.0
        b[i] = dose * rate / 27.20
    return b


def path(rho, a0, kap, b, start):
    A = np.zeros(len(YEARS)); a = start
    for i, y in enumerate(YEARS):
        if y >= 2026:
            a = rho * a + (1 - rho) * (a0 - kap * b[i])
        A[i] = a
    return A


def person(x, g, h, col):
    hd = h * 0.1
    return (f'<circle cx="{x}" cy="{g - h + hd:.1f}" r="{hd:.1f}" fill="{col}"/>'
            f'<path d="M{x - h * .12:.1f},{g - h + 2.2 * hd:.1f} h{h * .24:.1f} l{h * .04:.1f},{h * .42:.1f} h{-h * .32:.1f} z" fill="{col}"/>'
            f'<line x1="{x - 1.5}" y1="{g - h * .45:.1f}" x2="{x - 3.5}" y2="{g}" stroke="{col}" stroke-width="1.6"/>'
            f'<line x1="{x + 1.5}" y1="{g - h * .45:.1f}" x2="{x + 3.5}" y2="{g}" stroke="{col}" stroke-width="1.6"/>')


def vehicle(x, g, col, van=False):
    if van:
        return (f'<path d="M{x},{g - 6} v-16 h22 l8,8 v8 z" fill="none" stroke="{col}" stroke-width="1.3"/>'
                f'<circle cx="{x + 6}" cy="{g - 3}" r="3" fill="{INK}" stroke="{col}"/><circle cx="{x + 24}" cy="{g - 3}" r="3" fill="{INK}" stroke="{col}"/>')
    return (f'<path d="M{x},{g - 6} h4 l5,-7 h14 l6,7 h5 v5 h-34 z" fill="none" stroke="{col}" stroke-width="1.3"/>'
            f'<circle cx="{x + 8}" cy="{g - 1}" r="3" fill="{INK}" stroke="{col}"/><circle cx="{x + 26}" cy="{g - 1}" r="3" fill="{INK}" stroke="{col}"/>')


def main():
    people = [
        ("Daily commuter, Nordlandet", "crosses twice a working day · electric car in 2029", 1.0, 2029, 0.80, 0.87, 0.57, 0.30, CREAM, "car"),
        ("Occasional crosser, Kirkelandet", "a few crossings a month", 0.2, None, 0.50, 0.55, 0.30, 0.50, TEAL, "walk"),
        ("Van driver, local firm", "many crossings · electric van in 2033", 1.4, 2033, 0.30, 0.75, 0.32, 0.40, AMBER, "van"),
    ]
    W, H = 1000, 316
    X0, X1, Y0, Y1 = 440, 960, 34, 236
    X = lambda y: X0 + (y - YEARS[0]) / (YEARS[-1] - YEARS[0]) * (X1 - X0)
    Yv = lambda a: Y1 - (a - 0.22) / 0.34 * (Y1 - Y0)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Three people, same instruments, acceptance moving at the speed of memory">']
    # event lines
    for y, lab in ((2026, "package starts"), (2035, "distance charge")):
        o.append(f'<line x1="{X(y):.1f}" y1="{Y0 - 8}" x2="{X(y):.1f}" y2="{Y1}" stroke="{CREAM}" stroke-opacity=".3" stroke-dasharray="3 4"/>')
        o.append(f'<text x="{X(y) + 5:.1f}" y="{Y0 - 12}" {MONO} font-size="11" fill="{CREAM}">{lab}</text>')
    o.append(f'<line x1="{X0}" y1="{Yv(LAM):.1f}" x2="{X1}" y2="{Yv(LAM):.1f}" stroke="{RED}" stroke-width="1.4" stroke-dasharray="6 4"/>')
    o.append(f'<text x="{X0 - 8}" y="{Yv(LAM) + 4:.1f}" {MONO} font-size="11" fill="{RED}" text-anchor="end">λ 0.38</text>')
    o.append(f'<line x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}" stroke="{DIM}"/>')
    for y in (2026, 2029, 2033, 2035, 2040):
        o.append(f'<text x="{X(y):.1f}" y="{Y1 + 16}" {MONO} font-size="11" fill="{DIM}" text-anchor="middle">{y}</text>')
    o.append(f'<text x="{X0 - 8}" y="{Yv(0.5) + 4:.1f}" {MONO} font-size="11" fill="{DIM}" text-anchor="end">0.5</text>')
    o.append(f'<text x="{X0 - 8}" y="{Yv(0.3) + 4:.1f}" {MONO} font-size="11" fill="{DIM}" text-anchor="end">0.3</text>')
    for k, (name, sub, dose, ev, rho, a0, kap, st, col, kind) in enumerate(people):
        A = path(rho, a0, kap, bills(dose, ev), st)
        q = " ".join(f"{X(y):.1f},{Yv(a):.1f}" for y, a in zip(YEARS, A))
        o.append(f'<polyline points="{q}" fill="none" stroke="{col}" stroke-width="2.4"/>')
        below = [(y, a) for y, a in zip(YEARS, A) if a < LAM]
        for y, a in below:
            o.append(f'<circle cx="{X(y):.1f}" cy="{Yv(a):.1f}" r="3.2" fill="{col}" stroke="{RED}" stroke-width="1.4"/>')
        if ev:
            i = list(YEARS).index(ev)
            o.append(f'<circle cx="{X(ev):.1f}" cy="{Yv(A[i]):.1f}" r="5.5" fill="{SAGE}" stroke="{INK}" stroke-width="1.5"/>')
            o.append(f'<text x="{X(ev) + (-9 if kind == "car" else 12):.1f}" y="{Yv(A[i]) + (-9 if kind == "car" else 22):.1f}" {MONO} font-size="11" fill="{SAGE}" text-anchor="{"end" if kind == "car" else "start"}">goes electric</text>')
        ye, ae = YEARS[-1], A[-1]
        note = {"car": "slow both ways", "walk": "barely moved: low dose", "van": "fast: follows the bill"}[kind]
        nx = {"car": X(2036.3), "walk": X(2035.6), "van": X(2026.6)}[kind]
        ny = {"car": Yv(0.415) - 8, "walk": Yv(0.5) - 12, "van": Yv(0.3) + 24}[kind]
        o.append(f'<text x="{nx:.1f}" y="{ny:.1f}" {MONO} font-size="11.5" fill="{col}">{note}</text>')
        # agent card on the left
        cy = 52 + k * 84
        o.append(f'<line x1="14" y1="{cy + 22}" x2="380" y2="{cy + 22}" stroke="{col}" stroke-opacity=".5"/>')
        o.append(person(30, cy + 20, 34, col))
        if kind == "car":
            o.append(vehicle(44, cy + 20, SAGE))
        elif kind == "van":
            o.append(vehicle(44, cy + 20, AMBER, van=True))
        o.append(f'<text x="92" y="{cy - 2}" {SANS} font-weight="800" font-size="14" fill="{CREAM}">{name}</text>')
        o.append(f'<text x="92" y="{cy + 14}" {SANS} font-size="11.5" fill="{DIM}">{sub}</text>')
        o.append(f'<text x="92" y="{cy + 38}" {MONO} font-size="11.5" fill="{col}">memory ρ = {rho} · dose {dose}</text>')
        tag = {"car": ("crosses λ in 2031, held above", CREAM), "van": ("below λ again from 2035", RED), "walk": ("always above λ", TEAL)}[kind]
        o.append(f'<text x="92" y="{cy + 55}" {MONO} font-size="11" fill="{tag[1]}">{tag[0]}</text>')
    o.append(f'<text x="14" y="{H - 6}" {MONO} font-size="10.5" fill="{DIM}">reduced form of (2): δ·dose written as −κ·bill, info and z folded into a₀, scaled by (1−ρ); a₀ 0.55–0.87, κ 0.30–0.57 · illustrative, not estimates</text>')
    o.append("</svg>")
    (HERE / "plates" / "memory.svg").write_text("".join(o))
    for name, sub, dose, ev, rho, a0, kap, st, col, kind in people:
        A = path(rho, a0, kap, bills(dose, ev), st); print(name, "min", round(A.min(), 3), "2040", round(A[-1], 3))


if __name__ == "__main__":
    main()
