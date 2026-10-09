#!/usr/bin/env python3
"""One self-contained page that renders anywhere -> docs/proposal/standalone.html.

Opens index.html in Chromium, lets every figure draw, and saves the result with the figures baked in
as SVG, so the page needs no JavaScript to show them. The plates are embedded as JPEG data URIs. The
only scripts left are hairline's (the animated line figures at the section openings), which re-mount
over their own static snapshot when scripts are allowed.

    python docs/proposal/build.py && python docs/proposal/build_standalone.py

Also writes the body-only variant published as the hosted page (the host adds <html>/<head>/<body>).
"""
import base64
import io
import re
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PLATES = HERE.parent / "plates"


def plate_uri(name, width=760):
    im = Image.open(PLATES / name).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main(out_dir=HERE):
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto((HERE / "index.html").as_uri())
        pg.wait_for_timeout(1500)
        if errors:
            sys.exit(f"page errors: {errors}")
        # drop the drawing script and its data (the SVGs it drew stay); keep hairline's
        pg.evaluate("""() => {
          for (const s of [...document.scripts]) if (s.textContent.includes("const TOWNS=")) s.remove();
          for (const a of document.querySelectorAll(".plates a")) a.removeAttribute("href");
          // hairline adopts its stylesheet; write it out so the static snapshot is styled without scripts
          const css = [...document.adoptedStyleSheets].flatMap(sh => [...sh.cssRules].map(r => r.cssText)).join(" ");
          if (css) { const st = document.createElement("style"); st.textContent = css; document.head.appendChild(st); }
        }""")
        html = pg.content()
        b.close()
    for name in sorted(x.name for x in PLATES.glob("0*.png")):
        html = html.replace(f'src="../plates/{name}"', f'src="{plate_uri(name)}"')
    html = html.replace(' loading="lazy"', "").replace(" Click to enlarge.", "")
    assert "../plates/" not in html
    (out_dir / "standalone.html").write_text(html, encoding="utf-8")

    # hosted variant: the host wraps the page, so keep <title>, styles, font links and the body only
    head = re.search(r"<head>(.*?)</head>", html, re.S).group(1)
    keep = re.findall(r"<title>.*?</title>|<link[^>]+fonts[^>]*>|<style[^>]*>.*?</style>", head, re.S)
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S).group(1)
    hosted = "\n".join(keep) + "\n<style>:root{color-scheme:dark}</style>\n" + body
    (out_dir / "hosted.html").write_text(hosted, encoding="utf-8")
    for f in ("standalone.html", "hosted.html"):
        print(f, f"{(out_dir / f).stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE)
