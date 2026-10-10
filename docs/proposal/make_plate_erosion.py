#!/usr/bin/env python3
"""Plate: the base erodes -> docs/proposal/plates/erosion.svg

One hundred crossings drawn three times, each car a vector glyph: today (40 electric, the national share
in September 2026), the prototype's median for 2035 (80) and an all-electric fleet (100). Under each grid,
what those hundred crossings earn at the Kristiansund tag rates (27.20 fossil, 19.04 zero-emission) against
the same debt line: what a hundred crossings had to earn in an all-fossil fleet.

    python docs/proposal/make_plate_erosion.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F"
MONO = 'font-family="Roboto Mono,monospace"'
SANS = 'font-family="Inter,sans-serif"'


def car(x, y, col, s=1.0):
    return (f'<g transform="translate({x:.1f},{y:.1f}) scale({s})">'
            f'<path d="M0,6 h3 l3,-4 h9 l4,4 h4 v4 h-23 z" fill="{col}" fill-opacity="{.9 if col == SAGE else .18}" stroke="{col}" stroke-width=".9"/>'
            f'<circle cx="5.5" cy="10" r="1.8" fill="{INK}" stroke="{col}" stroke-width=".8"/><circle cx="17.5" cy="10" r="1.8" fill="{INK}" stroke="{col}" stroke-width=".8"/></g>')


def main():
    W, H = 470, 262
    cases = [("TODAY", 40, "national, Sept 2026"), ("2035", 80, "prototype median"), ("ALL ELECTRIC", 100, "no fossil left")]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="One hundred crossings three times, with the revenue they raise">']
    full = 100 * 27.20
    for k, (lab, ev, sub) in enumerate(cases):
        x0 = 4 + k * 158
        o.append(f'<text x="{x0}" y="13" {MONO} font-size="11.5" font-weight="600" fill="{CREAM}" letter-spacing="1">{lab}</text>')
        o.append(f'<text x="{x0}" y="27" {MONO} font-size="10.5" fill="{DIM}">{sub}</text>')
        for i in range(100):
            r, c = divmod(i, 10)
            o.append(car(x0 + c * 14, 36 + r * 10.4, SAGE if i < ev else CREAM, 0.54))
        rev = ev * 19.04 + (100 - ev) * 27.20
        lost = 1 - rev / full
        by, bw = 150, 138
        o.append(f'<rect x="{x0}" y="{by}" width="{bw}" height="14" fill="none" stroke="{CREAM}" stroke-opacity=".25"/>')
        o.append(f'<rect x="{x0}" y="{by}" width="{bw * rev / full:.1f}" height="14" fill="{AMBER}"/>')
        o.append(f'<line x1="{x0 + bw}" y1="{by - 5}" x2="{x0 + bw}" y2="{by + 19}" stroke="{RED}" stroke-width="2"/>')
        o.append(f'<text x="{x0}" y="{by + 34}" {MONO} font-size="16" font-weight="600" fill="{AMBER}">NOK {rev / 100:.2f}</text>')
        o.append(f'<text x="{x0}" y="{by + 49}" {MONO} font-size="10.5" fill="{DIM}">per crossing</text>')
        o.append(f'<text x="{x0}" y="{by + 74}" {SANS} font-weight="800" font-size="20" fill="{RED}">−{lost * 100:.0f}%</text>')
    o.append(f'<line x1="4" y1="{H - 14}" x2="20" y2="{H - 14}" stroke="{RED}" stroke-width="2"/>')
    o.append(f'<text x="26" y="{H - 10}" {MONO} font-size="10.5" fill="{CREAM}">what a crossing earned when every car paid NOK 27.20</text>')
    o.append("</svg>")
    (HERE / "plates" / "erosion.svg").write_text("".join(o))
    print("erosion.svg ok")


if __name__ == "__main__":
    main()
