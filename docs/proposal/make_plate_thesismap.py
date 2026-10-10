#!/usr/bin/env python3
"""Plate: the thesis as a routing tree -> docs/proposal/plates/thesismap.svg

Data sources sit on the month they become available; wires carry them into the four articles, which sit
on their submission month; the articles wire into the three claims on the right. Wire colour is the
ladder level a source belongs to: teal needs no new data (Level 1), amber is survey wave 1 (Level 2),
sage is wave 2 (Level 3). Cut the amber and sage wires and the teal tree still reaches A1 and A3.

    python docs/proposal/make_plate_thesismap.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
CREAM, DIM, RED, AMBER, SAGE, INK, TEAL = "#ECE3D2", "#948B7E", "#D2412B", "#D4A530", "#9DB886", "#16120F", "#7CBAC4"
MONO = 'font-family="Roboto Mono,monospace"'
SANS = 'font-family="Inter,sans-serif"'
W, H = 1000, 282
MX0, MX1, AXY = 40, 740, 160
M = lambda m: MX0 + m / 36 * (MX1 - MX0)


def wire(x1, y1, x2, y2, col, w=1.5, op=.75):
    my = (y1 + y2) / 2
    return f'<path d="M{x1:.1f},{y1:.1f} C{x1:.1f},{my:.1f} {x2:.1f},{my:.1f} {x2:.1f},{y2:.1f}" fill="none" stroke="{col}" stroke-width="{w}" stroke-opacity="{op}"/>'


def hwire(x1, y1, x2, y2, col, w=1.5, op=.75):
    mx = (x1 + x2) / 2
    return f'<path d="M{x1:.1f},{y1:.1f} C{mx:.1f},{y1:.1f} {mx:.1f},{y2:.1f} {x2:.1f},{y2:.1f}" fill="none" stroke="{col}" stroke-width="{w}" stroke-opacity="{op}"/>'


def node(x, y, label, col, w=None, anchor="middle"):
    w = w or 8.0 * len(label) + 18
    x0 = x - w / 2
    return (f'<rect x="{x0:.1f}" y="{y - 12}" width="{w:.1f}" height="24" rx="12" fill="{INK}" stroke="{col}" stroke-width="1.3"/>'
            f'<text x="{x:.1f}" y="{y + 4.5}" {MONO} font-size="12.5" fill="{CREAM}" text-anchor="middle">{label}</text>'), w


def main():
    # data sources: (label, month, row y, level colour, feeds)
    data = [
        ("road networks · OSM", 0.0, 100, 16, TEAL, ["A1"]),
        ("national ranges", 0.0, 96, 54, TEAL, ["A1"]),
        ("vehicle register", 2.0, 280, 16, TEAL, ["A1"]),
        ("station counts", 4.0, 250, 54, TEAL, ["A1"]),
        ("WAVE 1 · month 6", 6, 160, 92, AMBER, ["A2"]),
        ("public record 2019–26", 8.0, 470, 16, TEAL, ["A2"]),
        ("WAVE 2 · month 18", 18, 410, 92, SAGE, ["A2"]),
        ("dated events", 26.0, 580, 54, TEAL, ["A3"]),
    ]
    arts = {"A1": (12, "agents with memory", "RQ1"), "A2": (24, "acceptance that persists", "RQ2"),
            "A3": (32, "robust pathways", "RQ3"), "A4": (34, "discount revision", "optional")}
    claims = [("1", "acceptance margin", ["A2", "A3"]), ("2", "uncertainty by source", ["A1", "A3"]),
              ("3", "signposts tested twice", ["A3"])]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Thesis map: data sources wired to four articles on a 36-month axis, articles wired to three claims">',
         '<defs><filter id="tmg"><feGaussianBlur stdDeviation="2.2"/></filter></defs>']
    # time bands under the axis
    for m0, m1, y, lab, col in ((0, 3, 194, "Sikt · pilot", TEAL), (0, 16, 210, "30 ECTS coursework", CREAM), (33, 36, 194, "summary", CREAM)):
        o.append(f'<rect x="{M(m0):.1f}" y="{y}" width="{M(m1) - M(m0):.1f}" height="8" fill="{col}" fill-opacity=".28"/>')
        o.append(f'<text x="{M(m1) + 6 if lab != "summary" else M(m0) - 6:.1f}" y="{y + 8}" {MONO} font-size="11" fill="{col}" text-anchor="{"start" if lab != "summary" else "end"}">{lab}</text>')
    # axis
    o.append(f'<line x1="{MX0}" y1="{AXY}" x2="{MX1}" y2="{AXY}" stroke="{DIM}" stroke-width="1.2"/>')
    for m in range(0, 37, 6):
        o.append(f'<line x1="{M(m):.1f}" y1="{AXY - 4}" x2="{M(m):.1f}" y2="{AXY + 4}" stroke="{DIM}"/>')
        o.append(f'<text x="{M(m):.1f}" y="{AXY + 20}" {MONO} font-size="11.5" fill="{DIM}" text-anchor="middle">{"month " if m == 0 else ""}{m}</text>')
    # data nodes and wires into articles
    for lab, m, x, y, col, feeds in data:
        for a in feeds:
            ax = M(arts[a][0])
            o.append(wire(x, y + 12, ax, AXY - 9, col, 1.8 if col != TEAL else 1.4, .8 if col != TEAL else .55))
        # stem to the axis at the month it arrives
        o.append(f'<line x1="{M(m):.1f}" y1="{AXY - 3}" x2="{M(m):.1f}" y2="{AXY + 3}" stroke="{col}" stroke-width="2"/>')
        s, _ = node(x, y, lab, col)
        o.append(s)
    # article to article: the engine and estimates flow forward
    for a, b, lab in (("A1", "A3", "engine"), ("A2", "A3", "ρ, η"), ("A3", "A4", "")):
        x1, x2 = M(arts[a][0]), M(arts[b][0])
        o.append(f'<path d="M{x1:.1f},{AXY + 9} Q{(x1 + x2) / 2:.1f},{AXY + 46 if a == "A1" else AXY + 30} {x2:.1f},{AXY + 9}" fill="none" stroke="{RED}" stroke-width="1.4" stroke-opacity=".7" stroke-dasharray="{"4 3" if b == "A4" else "none"}"/>')
        if lab:
            o.append(f'<text x="{(x1 + x2) / 2:.1f}" y="{(AXY + 36 if a == "A1" else AXY + 27):.1f}" {MONO} font-size="10.5" fill="{RED}" text-anchor="middle">{lab}</text>')
    # article markers
    for a, (m, name, rq) in arts.items():
        x = M(m)
        solid = a != "A4"
        if a == "A3":
            o.append(f'<rect x="{x - 11}" y="{AXY - 11}" width="22" height="22" fill="{RED}" fill-opacity=".45" filter="url(#tmg)"/>')
        o.append(f'<rect x="{x - 8}" y="{AXY - 8}" width="16" height="16" fill="{RED if solid else INK}" stroke="{RED}" stroke-width="1.4"/>')
        if not solid:
            o.append(f'<text x="{x}" y="{AXY - 14}" {MONO} font-size="11" fill="{RED}" text-anchor="middle">A4</text>')
        lx, anchor = {"A3": (x - 46, "start"), "A4": (x - 85, "start")}.get(a, (x, "middle"))
        if a != "A4":
            o.append(f'<line x1="{x:.1f}" y1="{AXY + 9}" x2="{x:.1f}" y2="224" stroke="{RED}" stroke-opacity=".35" stroke-dasharray="2 3"/>' if a != "A3" else "")
            o.append(f'<text x="{lx:.1f}" y="240" {SANS} font-weight="800" font-size="14" fill="{RED}" text-anchor="{anchor}">{a} <tspan {MONO} font-weight="400" font-size="11" fill="{DIM}">{rq} · month {m}</tspan></text>')
            o.append(f'<text x="{lx:.1f}" y="257" {SANS} font-weight="700" font-size="13.5" fill="{CREAM}" text-anchor="{anchor}">{name}</text>')
        else:
            o.append(f'<text x="{lx:.1f}" y="277" {SANS} font-size="12" fill="{CREAM}" text-anchor="{anchor}"><tspan fill="{RED}" font-weight="800">A4</tspan> optional: {name}, with planners</text>')
    # claims on the right, wired from the articles
    CX = 800
    for k, (n, lab, src) in enumerate(claims):
        cy = 40 + k * 50
        for a in src:
            col = RED
            o.append(hwire(M(arts[a][0]) + 8, AXY - 2 - 4 * ("A1A2A3".index(a) // 2), CX - 14, cy, col, 1.3, .55))
        o.append(f'<circle cx="{CX}" cy="{cy}" r="14" fill="{INK}" stroke="{CREAM}" stroke-width="1.4"/>')
        o.append(f'<text x="{CX}" y="{cy + 5}" {SANS} font-weight="800" font-size="14" fill="{CREAM}" text-anchor="middle">{n}</text>')
        o.append(f'<text x="{CX + 22}" y="{cy + 5}" {SANS} font-size="13" fill="{CREAM}">{lab}</text>')
    o.append(f'<text x="{CX - 14}" y="12" {MONO} font-size="11" fill="{DIM}" letter-spacing="1.2">CLAIMS</text>')
    o.append("</svg>")
    (HERE / "plates" / "thesismap.svg").write_text("".join(o))
    print("thesismap.svg ok")


if __name__ == "__main__":
    main()
