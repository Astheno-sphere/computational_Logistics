#!/usr/bin/env python3
"""Plate: one household, three years -> docs/proposal/plates/household.svg (illustrative, and labelled so)

A street elevation on Nordlandet drawn three times over a time band, 2026, 2029 and 2035, in line art at
true human scale. The same household each time: its car (fossil, then electric), its monthly toll bill at
two crossings a working day (44 a month) at the Kristiansund tag rates, 27.20 then 19.04, then a
vehicle-neutral distance charge of 24 per crossing (the prototype's D), and its acceptance as a gauge that
carries from row to row through the memory term of equation (2). The acceptance values are illustrative.

    python docs/proposal/make_plate_household.py
"""
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK, TEAL = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F", "#7CBAC4"
MONO = 'font-family="Roboto Mono,monospace"'
SANS = 'font-family="Inter,sans-serif"'
rng = np.random.default_rng(3)


def person(x, g, h=34, solid=False, col=CREAM, stride=0):
    head = 3.4 * h / 34
    hy = g - h + head
    s = []
    fill = col if solid else "none"
    s.append(f'<circle cx="{x}" cy="{hy:.1f}" r="{head:.1f}" fill="{fill}" stroke="{col}" stroke-width="1.1"/>')
    neck, hip = hy + head, g - h * 0.45
    if solid:
        s.append(f'<path d="M{x - 4.2 * h / 34},{neck + 1:.1f} h{8.4 * h / 34:.1f} l{1.2 * h / 34:.1f},{(hip - neck) * 0.95:.1f} h{-10.8 * h / 34:.1f} z" fill="{col}"/>')
    else:
        s.append(f'<line x1="{x}" y1="{neck:.1f}" x2="{x}" y2="{hip:.1f}" stroke="{col}" stroke-width="1.1"/>')
    s.append(f'<line x1="{x}" y1="{neck + 3:.1f}" x2="{x - 5 * h / 34:.1f}" y2="{hip - 2:.1f}" stroke="{col}" stroke-width="1.1"/>')
    s.append(f'<line x1="{x}" y1="{neck + 3:.1f}" x2="{x + 5 * h / 34:.1f}" y2="{hip - 2:.1f}" stroke="{col}" stroke-width="1.1"/>')
    s.append(f'<line x1="{x - 1}" y1="{hip:.1f}" x2="{x - 3 - stride}" y2="{g}" stroke="{col}" stroke-width="1.3"/>')
    s.append(f'<line x1="{x + 1}" y1="{hip:.1f}" x2="{x + 3 + stride}" y2="{g}" stroke="{col}" stroke-width="1.3"/>')
    return "".join(s)


def house(x, g, w=118, h=58):
    s = [f'<rect x="{x}" y="{g - h}" width="{w}" height="{h}" fill="{INK}" stroke="{CREAM}" stroke-width="1"/>',
         f'<path d="M{x - 6},{g - h} L{x + w / 2},{g - h - 34} L{x + w + 6},{g - h}" fill="{INK}" stroke="{CREAM}" stroke-width="1"/>']
    for k in range(3):
        wx = x + 12 + k * 36
        s.append(f'<rect x="{wx}" y="{g - h + 10}" width="18" height="16" fill="none" stroke="{CREAM}" stroke-width=".8"/>')
        s.append(f'<line x1="{wx + 9}" y1="{g - h + 10}" x2="{wx + 9}" y2="{g - h + 26}" stroke="{CREAM}" stroke-width=".6"/>')
    s.append(f'<rect x="{x + w - 30}" y="{g - 30}" width="16" height="30" fill="none" stroke="{CREAM}" stroke-width=".9"/>')
    for k in range(3):
        s.append(f'<line x1="{x + w - 34 - k * 3}" y1="{g - k * 3}" x2="{x + w - 10 + k * 3}" y2="{g - k * 3}" stroke="{CREAM}" stroke-width=".7"/>')
    # hatch on the gable, a texture cue
    for k in range(6):
        s.append(f'<line x1="{x + w / 2 - 22 + k * 8}" y1="{g - h - 4}" x2="{x + w / 2 - 14 + k * 8}" y2="{g - h - 14}" stroke="{CREAM}" stroke-opacity=".35" stroke-width=".6"/>')
    return "".join(s)


def tree(x, g, r=22):
    s = [f'<line x1="{x}" y1="{g}" x2="{x}" y2="{g - 30}" stroke="{CREAM}" stroke-width="1.2"/>',
         f'<line x1="{x}" y1="{g - 18}" x2="{x - 7}" y2="{g - 28}" stroke="{CREAM}" stroke-width=".8"/>']
    for _ in range(170):
        a = rng.uniform(0, 2 * np.pi); d = r * np.sqrt(rng.uniform(0, 1))
        px, py = x + d * np.cos(a), g - 40 + d * np.sin(a) * 0.9
        op = 0.35 + 0.55 * (np.cos(a + 2.3) * 0.5 + 0.5)          # lit from the upper left
        s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r=".9" fill="{CREAM}" fill-opacity="{op:.2f}"/>')
    return "".join(s)


def car(x, g, ev):
    col = SAGE if ev else CREAM
    s = [f'<path d="M{x},{g - 8} h6 l8,-10 h26 l10,10 h10 v8 h-60 z" fill="{INK}" stroke="{col}" stroke-width="1.3"/>',
         f'<circle cx="{x + 13}" cy="{g}" r="4.5" fill="{INK}" stroke="{col}" stroke-width="1.2"/>',
         f'<circle cx="{x + 46}" cy="{g}" r="4.5" fill="{INK}" stroke="{col}" stroke-width="1.2"/>',
         f'<line x1="{x + 27}" y1="{g - 18}" x2="{x + 27}" y2="{g - 9}" stroke="{col}" stroke-width=".8"/>']
    if ev:
        s.append(f'<path d="M{x + 2},{g - 4} c-8,0 -10,-12 -18,-12 v-10" fill="none" stroke="{SAGE}" stroke-width="1" stroke-dasharray="2 2"/>')
        s.append(f'<rect x="{x - 20}" y="{g - 36}" width="8" height="14" fill="none" stroke="{SAGE}" stroke-width="1"/>')
    else:
        for k in range(3):
            s.append(f'<circle cx="{x - 5 - k * 6}" cy="{g - 3 - k * 2}" r="{1.4 + k * .6}" fill="none" stroke="{CREAM}" stroke-opacity="{.5 - k * .12}"/>')
    return "".join(s)


def bridge(x, g):
    s = [f'<path d="M{x},{g} Q{x + 50},{g - 26} {x + 110},{g - 30}" fill="none" stroke="{CREAM}" stroke-width="1.6"/>',
         f'<path d="M{x},{g - 9} Q{x + 50},{g - 35} {x + 110},{g - 39}" fill="none" stroke="{CREAM}" stroke-width=".7"/>']
    for k in range(9):
        t = k / 8; bx = x + 110 * t; by = g - 30 * (2 * t - t * t)
        s.append(f'<line x1="{bx:.1f}" y1="{by:.1f}" x2="{bx:.1f}" y2="{by - 9:.1f}" stroke="{CREAM}" stroke-width=".6"/>')
    gx, gy = x + 26, g - 13
    s.append(f'<line x1="{gx}" y1="{gy}" x2="{gx}" y2="{gy - 46}" stroke="{CREAM}" stroke-width="1.6"/>')
    s.append(f'<line x1="{gx}" y1="{gy - 46}" x2="{gx + 34}" y2="{gy - 46}" stroke="{CREAM}" stroke-width="1.6"/>')
    s.append(f'<rect x="{gx + 22}" y="{gy - 46}" width="12" height="9" fill="{RED}"/>')
    return "".join(s), (gx + 28, gy - 37)


def gauge(cx, cy, v, r=22):
    col = RED if v < 0.38 else (AMBER if v < 0.5 else SAGE)
    s = [f'<path d="M{cx - r},{cy} A{r},{r} 0 0 1 {cx + r},{cy}" fill="none" stroke="{CREAM}" stroke-opacity=".3" stroke-width="5"/>']
    a = np.pi * (1 - v)
    ex, ey = cx + r * np.cos(a), cy - r * np.sin(a)
    large = 0
    s.append(f'<path d="M{cx - r},{cy} A{r},{r} 0 {large} 1 {ex:.1f},{ey:.1f}" fill="none" stroke="{col}" stroke-width="5"/>')
    s.append(f'<line x1="{cx}" y1="{cy}" x2="{cx + (r - 6) * np.cos(a):.1f}" y2="{cy - (r - 6) * np.sin(a):.1f}" stroke="{CREAM}" stroke-width="1.4"/>')
    s.append(f'<text x="{cx}" y="{cy + 14}" {MONO} font-size="10" fill="{col}" text-anchor="middle">{v:.2f}</text>')
    return "".join(s)


def main():
    W, H, PW = 1020, 330, 340
    rows = [
        (2026, False, 44 * 27.20, 0.30, "opposes the package", "fossil car, tag rate NOK 27.20"),
        (2029, True, 44 * 19.04, 0.55, "bill falls 30%, acceptance carries (ρ)", "electric car, NOK 19.04"),
        (2035, True, 44 * 24.00, 0.33, "discount ends, acceptance drops", "vehicle-neutral NOK 24"),
    ]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="One household on Nordlandet in 2026, 2029 and 2035">']
    for k, (yr, ev, bill, acc, story, how) in enumerate(rows):
        x0 = k * PW + 10
        g = 220
        if k:
            o.append(f'<line x1="{x0 - 6}" y1="18" x2="{x0 - 6}" y2="{H - 70}" stroke="{CREAM}" stroke-opacity=".18" stroke-dasharray="3 4"/>')
        o.append(f'<line x1="{x0}" y1="{g}" x2="{x0 + PW - 20}" y2="{g}" stroke="{CREAM}" stroke-width="1"/>')
        for t in range(0, PW - 20, 14):
            o.append(f'<line x1="{x0 + t}" y1="{g + 1}" x2="{x0 + t - 6}" y2="{g + 7}" stroke="{CREAM}" stroke-opacity=".25" stroke-width=".6"/>')
        o.append(tree(x0 + 22, g))
        o.append(house(x0 + 44, g))
        o.append(car(x0 + 170, g - 4, ev))
        # the household: two adults and a child, solid because they pay
        o.append(person(x0 + 112, g, 34, True, RED))
        o.append(person(x0 + 124, g, 32, True, RED))
        o.append(person(x0 + 135, g, 21, True, RED))
        o.append(person(x0 + 318, g - 30, 33, False, CREAM, stride=2))
        br, gate = bridge(x0 + 232, g)
        o.append(br)
        # dashed relation: household to the gantry it pays
        o.append(f'<path d="M{x0 + 124},{g - 40} C{x0 + 170},{g - 120} {gate[0] - 40},{gate[1] - 60} {gate[0]},{gate[1]}" fill="none" stroke="{RED}" stroke-width="1" stroke-dasharray="3 3"/>')
        # bill tag and gauge
        o.append(f'<rect x="{x0 + 150}" y="40" width="128" height="40" rx="6" fill="{INK}" stroke="{AMBER}"/>')
        o.append(f'<text x="{x0 + 160}" y="57" {MONO} font-size="10" fill="{DIM}">TOLL BILL / MONTH</text>')
        o.append(f'<text x="{x0 + 160}" y="73" {MONO} font-size="13" font-weight="600" fill="{AMBER}">NOK {bill:,.0f}</text>')
        o.append(gauge(x0 + 60, 66, acc))
        o.append(f'<text x="{x0 + 60}" y="32" {MONO} font-size="10" fill="{DIM}" text-anchor="middle">ACCEPTANCE</text>')
        o.append(f'<text x="{x0}" y="{g + 30}" {MONO} font-size="15" font-weight="600" fill="{CREAM}">{yr}</text>')
        o.append(f'<text x="{x0 + 48}" y="{g + 30}" {SANS} font-size="12" fill="{CREAM}">{story}</text>')
        o.append(f'<text x="{x0 + 48}" y="{g + 46}" {MONO} font-size="10" fill="{DIM}">{how}</text>')
        if k < 2:
            o.append(f'<path d="M{x0 + 90},66 C{x0 + 200},10 {x0 + PW - 60},10 {x0 + PW + 44},52" fill="none" stroke="{CREAM}" stroke-opacity=".45" stroke-dasharray="2 3"/>')
            o.append(f'<text x="{x0 + PW - 20}" y="22" {MONO} font-size="10" fill="{CREAM}" fill-opacity=".7" text-anchor="middle">ρ carries it</text>')
    # time band
    o.append(f'<rect x="10" y="{H - 44}" width="{W - 20}" height="22" rx="11" fill="none" stroke="{CREAM}" stroke-opacity=".6"/>')
    o.append(f'<text x="{W / 2}" y="{H - 29}" {MONO} font-size="11" fill="{CREAM}" text-anchor="middle" letter-spacing="2">2026 · BEFORE · 2029 · THE CAR TURNS · 2035 · THE INSTRUMENT TURNS</text>')
    o.append(f'<text x="10" y="{H - 6}" {MONO} font-size="9.5" fill="{DIM}">44 crossings a month; tariffs Vegamot and prototype D; acceptance values illustrative · people at true scale against a 2.6 m storey</text>')
    o.append("</svg>")
    (HERE / "plates" / "household.svg").write_text("".join(o))
    print("household.svg", round(len("".join(o)) / 1024), "kB")


if __name__ == "__main__":
    main()
