#!/usr/bin/env python3
"""Plate P5, the robust front -> docs/proposal/plates/p5-robust-front.svg (and a PNG preview if chromium is present).

Every mark is computed from docs/proposal/study.json (25 packages x 60 futures, prototype ensemble):
  x = share of the 60 futures in which the package meets the 2050 target (study.json: robustness)
  y = acceptance PROXY: share of commuters whose commuting is not made worse in 2030 (study.json: accept).
      This is the prototype's proxy, not the acceptance margin A1/A3 will estimate; the plate says so.
Drawn in the poster grammar of the reference set: palette strip with hex codes, scatter with the front,
selected point with dashed crosshairs, a strip of chosen options, spec box, receipts line.
Run: python docs/proposal/make_plate_p5.py
"""
import json
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "skills" / "abm-transport" / "scripts"))
import abm  # noqa: E402  (lever ranges)

GROUND, CREAM, BODY, DIM = "#2E151C", "#E8DFD0", "#CBBFB0", "#A59686"
SAGE, AMBER, TERRA, RED, TEAL = "#9DB886", "#D4A530", "#D4835C", "#C45545", "#7CBAC4"
SANS, SERIF, MONO = "Montserrat,Inter,sans-serif", "Spectral,Georgia,serif", "'JetBrains Mono',monospace"
W, H = 1600, 700
LEVER_NAMES = [("toll_nok", "TOLL", "NOK/trip"), ("ev_toll_share", "EV TOLL", "EV pays"),
               ("transit_freq_gain", "BUS", "freq. gain"), ("bike_infra", "BIKE", "network"),
               ("ev_subsidy_knok", "EV SUBSIDY", "kNOK")]


def pareto(pts):
    """Indices not dominated when both coordinates are maximised."""
    return [i for i, a in enumerate(pts) if not any(b[0] >= a[0] and b[1] >= a[1] and b != a for b in pts)]


def main():
    s = json.loads((HERE / "study.json").read_text())
    pk = s["packages_list"]
    pts = [(q["robustness"], q["accept"]) for q in pk]
    front = sorted(pareto(pts), key=lambda i: pts[i][0])
    rest = [i for i in range(len(pk)) if i not in front]
    second = set(pareto([pts[i] for i in rest]))
    near = {rest[j] for j in second}
    sel = next(i for i, q in enumerate(pk) if q["id"] == s["best"])
    nf = s["futures"]

    X0, X1, Y0, Y1 = 112, 940, 168, 520            # plot box
    xmax = 0.8
    px = lambda v: X0 + (X1 - X0) * v / xmax        # noqa: E731
    py = lambda v: Y1 - (Y1 - Y0) * v               # noqa: E731
    o = []
    t = lambda x, y, txt, size=13, fill=CREAM, w=400, f=MONO, a="start", ls=0, extra="": o.append(  # noqa: E731
        f'<text x="{x}" y="{y}" font-family="{f}" font-size="{size}" font-weight="{w}" fill="{fill}" '
        f'text-anchor="{a}" letter-spacing="{ls}" {extra}>{escape(str(txt))}</text>')
    o.append(f'<rect width="{W}" height="{H}" fill="{GROUND}"/>')

    # palette strip: the colours are part of the content
    chips = [(SAGE, "#9DB886", "sage: on the front", 1), (AMBER, "#D4A530", "amber: next to the front", 1),
             (CREAM, "#E8DFD0 (35%)", "ghost: dominated", .35), (TERRA, "#D4835C", f"terracotta: chosen, {s['best']}", 1),
             (RED, "#C45545", "warm red: objective axes", 1)]
    for k, (c, hx, lab, al) in enumerate(chips):
        x = 72 + k * 288
        o.append(f'<rect x="{x}" y="26" width="268" height="30" rx="15" fill="{c}" fill-opacity="{al}"/>')
        t(x + 134, 47, hx, 14, GROUND if al == 1 else CREAM, 500, a="middle")
        t(x + 134, 78, lab, 12.5, BODY, 600, SANS, "middle", .4)
    o.append(f'<line x1="72" y1="98" x2="{W-72}" y2="98" stroke="{CREAM}" stroke-opacity=".3"/>')

    # headers
    t(112, 130, "2D PARETO SCATTER", 17, CREAM, 800, SANS, ls=.8)
    t(112, 152, f"no policy and {len(pk)-1} packages, each scored over {nf} futures", 14, BODY, 400, SERIF)
    t(940, 130, "SELECTED", 17, TERRA, 800, SANS, "end", .8)
    q = pk[sel]
    t(940, 152, f"{s['best']} | {round(q['robustness']*nf)} OF {nf} FUTURES | {q['accept']*100:.1f}% NOT WORSE OFF", 13, BODY, 400, MONO, "end")

    # axes and grid
    for v in (0, .2, .4, .6, .8, 1.0):
        y = py(v)
        o.append(f'<line x1="{X0}" y1="{y}" x2="{X1}" y2="{y}" stroke="{CREAM}" stroke-opacity="{.12 if v else 0}" stroke-dasharray="3 6"/>')
        t(X0 - 12, y + 5, f"{round(v*100)}%", 13, RED, 400, a="end")
    for v in (0, .2, .4, .6, .8):
        t(px(v), Y1 + 24, f"{round(v*100)}%", 13, RED, 400, a="middle")
        o.append(f'<line x1="{px(v)}" y1="{Y1}" x2="{px(v)}" y2="{Y1+6}" stroke="{RED}"/>')
    o.append(f'<path d="M{X0} {Y0-6} V{Y1} H{X1}" fill="none" stroke="{RED}" stroke-width="1.4"/>')
    t(px(.4), Y1 + 54, f"SHARE OF THE {nf} FUTURES THAT MEET THE 2050 TARGET (%)", 14, CREAM, 800, SANS, "middle", .8)
    o.append(f'<text transform="translate(52 {(Y0+Y1)/2}) rotate(-90)" font-family="{SANS}" font-size="14" font-weight="800" fill="{CREAM}" '
             f'text-anchor="middle" letter-spacing=".8">ACCEPTANCE PROXY, 2030 (%)</text>')

    # dominated ghosts, near-front, front line, front dots
    for i in rest:
        if i in near:
            continue
        o.append(f'<circle cx="{px(pts[i][0]):.1f}" cy="{py(pts[i][1]):.1f}" r="7" fill="{CREAM}" fill-opacity=".35"/>')
    for i in sorted(near, key=lambda i: pts[i][0]):
        o.append(f'<circle cx="{px(pts[i][0]):.1f}" cy="{py(pts[i][1]):.1f}" r="8" fill="{AMBER}"/>')
    d = " ".join(f"{'M' if k == 0 else 'L'}{px(pts[i][0]):.1f} {py(pts[i][1]):.1f}" for k, i in enumerate(front))
    o.append(f'<path d="{d}" fill="none" stroke="{SAGE}" stroke-width="1.6" stroke-opacity=".7"/>')
    for i in front:
        o.append(f'<circle cx="{px(pts[i][0]):.1f}" cy="{py(pts[i][1]):.1f}" r="9.5" fill="{SAGE}"/>')

    # selected point, ring and dashed crosshairs
    sx, sy = px(pts[sel][0]), py(pts[sel][1])
    o.append(f'<line x1="{X0}" y1="{sy}" x2="{sx}" y2="{sy}" stroke="{TERRA}" stroke-dasharray="5 5" stroke-opacity=".8"/>')
    o.append(f'<line x1="{sx}" y1="{sy}" x2="{sx}" y2="{Y1}" stroke="{TERRA}" stroke-dasharray="5 5" stroke-opacity=".8"/>')
    o.append(f'<circle cx="{sx}" cy="{sy}" r="19" fill="none" stroke="{CREAM}" stroke-width="1.6"/>')
    o.append(f'<circle cx="{sx}" cy="{sy}" r="10" fill="{TERRA}"/>')
    t(sx + 4, Y1 - 10, f"{pts[sel][0]*100:.1f}%", 12.5, TERRA, 500)
    t(X0 + 10, sy - 8, f"{pts[sel][1]*100:.1f}%", 12.5, TERRA, 500)

    # chosen options A..E: the front, thinned to at most five, always keeping both ends and the selected one
    keep = sorted({front[0], front[-1], sel} | {front[round(k * (len(front) - 1) / 4)] for k in range(5)}, key=lambda i: pts[i][0])[:5]
    for L, i in zip("ABCDE", keep):
        x, y = px(pts[i][0]), py(pts[i][1])
        dxl, dyl = (16, 6) if i == keep[0] else ((0, -32) if i == sel else (0, -18))
        t(x + dxl, y + dyl, L, 15, CREAM if i != sel else TERRA, 800, SANS, "middle")

    # trade-off arrow along the front, with the measured numbers
    a, b = front[0], front[-1]
    dx, dy = (pts[b][0] - pts[a][0]) * 100, (pts[a][1] - pts[b][1]) * 100
    t(X1 - 6, py(.90), "TRADE-OFF ALONG THE FRONT", 14, CREAM, 800, SANS, "end", .8)
    t(X1 - 6, py(.90) + 22, f"+{dx:.0f} points of futures costs -{dy:.0f} points of acceptance", 14, BODY, 400, SERIF, "end")
    o.append(f'<path d="M{X1-250} {py(.90)+34} Q{X1-190} {py(.90)+70} {X1-120} {py(.78)}" fill="none" stroke="{CREAM}" stroke-opacity=".55" marker-end="url(#ah)"/>')
    o.insert(1, f'<defs><marker id="ah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 1 L9 5 L0 9" fill="none" stroke="{CREAM}" stroke-opacity=".7"/></marker></defs>')
    t(px(.30), py(.97) + 2, "THE FRONT", 15, SAGE, 800, SANS, ls=1)
    t(px(.10), py(.30), "DOMINATED", 14, CREAM, 500, SANS, ls=.8, extra='fill-opacity=".7"')
    t(X0 + 10, Y1 - 12 - 90, "", 1)

    # right column: what each chosen package does (levers, bars from zero)
    cx = 1010
    t(cx, 130, "WHAT EACH CHOSEN PACKAGE DOES", 17, CREAM, 800, SANS, ls=.8)
    t(cx, 152, "lever settings, each bar from zero to the lever's maximum", 14, BODY, 400, SERIF)
    for r, (L, i) in enumerate(zip("ABCDE", keep)):
        y = 182 + r * 66
        c = TERRA if i == sel else SAGE
        t(cx, y + 32, f"{L}", 22, c, 800, SANS)
        t(cx + 30, y + 22, pk[i]["id"], 14, CREAM, 500)
        t(cx + 30, y + 40, f"{round(pts[i][0]*nf)}/{nf} · {pts[i][1]*100:.0f}%", 12, DIM, 400)
        for k, (key, _, _) in enumerate(LEVER_NAMES):
            lo, hi, _ = abm.LEVERS[key]
            v = (pk[i]["levers"][key] - lo) / (hi - lo)
            bx = cx + 160 + k * 74
            o.append(f'<rect x="{bx}" y="{y}" width="46" height="46" fill="{CREAM}" fill-opacity=".07"/>')
            o.append(f'<rect x="{bx}" y="{y + 46 * (1 - v):.1f}" width="46" height="{46 * v:.1f}" fill="{c}" fill-opacity=".85"/>')
    for k, (_, name, unit) in enumerate(LEVER_NAMES):
        t(cx + 160 + k * 74 + 23, 182 + 5 * 66 + 2, name, 11, BODY, 600, SANS, "middle", .5)
        t(cx + 160 + k * 74 + 23, 182 + 5 * 66 + 17, unit, 10.5, DIM, 400, MONO, "middle")

    # bottom: rule, title, caption, spec box, receipts
    o.append(f'<line x1="72" y1="582" x2="{W-72}" y2="582" stroke="{CREAM}" stroke-opacity=".3"/>')
    o.append(f'<text x="72" y="632" font-family="{SANS}" font-size="46" font-weight="800" fill="{CREAM}" letter-spacing="-.5">THE <tspan fill="{SAGE}">ROBUST</tspan> FRONT</text>')
    t(72, 666, "Robust is not optimal. It is the path that still works when the future refuses to cooperate.", 21, BODY, 400, SERIF)
    bx = 1000
    o.append(f'<rect x="{bx}" y="598" width="528" height="70" rx="4" fill="none" stroke="{CREAM}" stroke-opacity=".4"/>')
    spec = [f"ENSEMBLE: {len(pk)-1} PACKAGES + NO POLICY x {nf} FUTURES = {s['runs']:,} RUNS", f"AGENTS: {s['agents']:,} | TARGET: {s['target']*100:.0f}% OF 2025 CO2 BY 2050",
            "Y IS THE PROTOTYPE PROXY, NOT THE ESTIMATED MARGIN", "BEHAVIOUR SYNTHETIC UNTIL THE A1 SURVEY"]
    for k, ln in enumerate(spec):
        t(bx + 14, 617 + k * 15, ln, 11.5, BODY, 400)
    t(72, 692, "choice pipeline reproduced on real Swissmetro data (LL -5214.9)  ·  fast engine within 15-16% of the network model  ·  tests at the tagged commit [to confirm]", 11.5, DIM, 400)

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="Plate P5, the robust front: no policy and {len(pk)-1} packages '
           f'by share of futures meeting the 2050 target and an acceptance proxy; package {s["best"]} selected on the Pareto front.">\n' + "\n".join(o) + "\n</svg>\n")
    out = HERE / "plates" / "p5-robust-front.svg"
    out.write_text(svg, encoding="utf-8")
    print("front", [pk[i]["id"] for i in front], "near", sorted(pk[i]["id"] for i in near), "selected", s["best"], "| keep", [pk[i]["id"] for i in keep])
    print(f"tradeoff +{dx:.0f} futures pts / -{dy:.0f} acceptance pts;", out.name, f"{out.stat().st_size//1024} kB")
    chrome = "/opt/pw-browsers/chromium"
    if Path(chrome).exists():
        html = out.with_suffix(".preview.html")
        html.write_text(f'<body style="margin:0;background:#000"><img src="{out.name}" style="width:{W}px;display:block">', encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H+130}",
                        "--virtual-time-budget=3000", f"--screenshot={out.with_suffix('.png')}", html.as_uri()], capture_output=True)
        html.unlink()


if __name__ == "__main__":
    main()
