#!/usr/bin/env python3
"""Render a line-art plate (HTML using lineart.js) to PNG, injecting the prototype numbers it draws.

    python skills/visual-narrative/lineart/render.py stock-turns docs/plates/05-the-stock-turns.png
    python skills/visual-narrative/lineart/render.py banner docs/brand/banner.png
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def data():
    st = json.loads((ROOT / "docs/proposal/study.json").read_text())
    tr = st["trace"]
    molde = [i for i, z in enumerate(tr["zone"]) if z == "Molde"]
    cars = [i for i in molde if tr["mode50"][i] == 0]
    ev50 = sum(tr["ev50"][i] for i in cars) / len(cars)
    # 2025: the share the prototype population starts from (abm.population, illustrative)
    return {"ev25": 0.30, "ev50": round(ev50, 3)}


def banner_data():
    st = json.loads((ROOT / "docs/proposal/study.json").read_text())
    tw = json.loads((ROOT / "docs/proposal/towns.json").read_text())["molde"]
    x0, y0, x1, y1 = tw["bbox"]
    roads = [[int(r[2] > 0.08), [[round((a - x0) / (x1 - x0), 4), round((y1 - b) / (y1 - y0), 4)] for a, b in r[1]]]
             for r in tw["roads"] if r[0] or r[2] > 0.02]
    return {"meets": st["packages_list"][0]["meets"], "roads": roads}


def main(name, out):
    global data
    if name == "banner":
        data = banner_data
    html = (HERE / f"{name}.html").read_text(encoding="utf-8")
    html = html.replace("/*LINEART*/", (HERE / "lineart.js").read_text(encoding="utf-8"))
    html = html.replace("/*DATA*/null", json.dumps(data()))
    tmp = HERE / f".{name}.built.html"
    tmp.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1440, "height": 1800}, device_scale_factor=2 if name == "banner" else 1)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(tmp.as_uri())
        pg.wait_for_timeout(1200)
        if errors:
            sys.exit(f"page errors: {errors}")
        pg.locator(".plate").screenshot(path=out)
        b.close()
    tmp.unlink()
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
