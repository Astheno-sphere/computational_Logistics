#!/usr/bin/env python3
"""Build docs/proposal/proposal-v5.5.html from src/proposal-v55.html.

One self-contained page: fonts embedded (vendor/fonts, SIL OFL), plates inlined. The plates are the
computed plates already in docs/proposal/plates (made by the make_plate_*.py scripts); here they are only
re-toned to the v5.5 system (oxblood ground, v5.5 palette, Montserrat / Spectral / JetBrains Mono),
their ids are namespaced so several can share one page, and two article labels on the engine plate are
corrected to the v5.5 numbering (A1 choice estimated, A2 acceptance that persists, A3 pathways).

    python docs/proposal/build_v55.py
"""
import base64
import io
import re
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PLATES = HERE / "plates"
FONTS = HERE / "vendor" / "fonts"

# plate name -> accessible description
ALT = {
    "answers": "Left, a strategic model's single settled 2050 for Kristiansund. Right, the same place in 2026, 2035 and 2050 along one pathway: the electric share, the toll paid per crossing and the acceptance index change year by year.",
    "household": "One Nordlandet household in 2026, 2029 and 2035: the car turns electric, the toll bill falls, then the discount ends and acceptance drops.",
    "engine": "Five isometric layers: data, estimated choice, agents with memory, 1,000 futures, and pathways, each tagged with its article, claim and tool.",
    "memory": "Acceptance over 2026 to 2040 for three agents, a commuter, an occasional crosser and a van driver, against the threshold lambda.",
    "front": "Prototype result: 904 pathways scored against 1,000 futures, share of futures on target against acceptance margin, with the signposts of five chosen pathways.",
    "erosion": "Toll paid per crossing falls from NOK 23.94 to 19.61 as the fleet electrifies, against debt, across a fan of futures.",
    "tree": "904 ordered instrument sequences as a radial tree; the same instruments in two orders reach 67% and 36% of futures.",
    "thesismap": "Data sources, the two survey waves and the three claims along the 36-month plan.",
}

# colour map: v4.5 plate tokens -> v5.5 tokens
COLOURS = {"#16120F": "#2E151C", "#0B0806": "#1F0E13", "#ECE3D2": "#E8DFD0", "#D2412B": "#C45545", "#221B16": "#3A1D25"}
FONT_MAP = {"Roboto Mono,monospace": "JetBrains Mono,monospace", "Inter,sans-serif": "Montserrat,sans-serif"}
# engine plate: article labels follow the v5.5 numbering
TEXT_FIXES = {"engine": {"A2 · Biogeme": "A1 · Biogeme", "claim 1 · A1 · ρ": "claim 1 · A2 · ρ"},
              # Montserrat is wider than the Inter these plates were drawn in: move the second half of one caption
              "erosion": {'<text x="140" y="286"': '<text x="166" y="286"'}}


def font_css():
    spec = [("Montserrat", 700, "normal", "montserrat-latin-700-normal"), ("Montserrat", 800, "normal", "montserrat-latin-800-normal"),
            ("Montserrat", 900, "normal", "montserrat-latin-900-normal"), ("Spectral", 400, "normal", "spectral-latin-400-normal"),
            ("Spectral", 400, "italic", "spectral-latin-400-italic"), ("Spectral", 600, "normal", "spectral-latin-600-normal"),
            ("JetBrains Mono", 400, "normal", "jetbrains-mono-latin-400-normal"), ("JetBrains Mono", 500, "normal", "jetbrains-mono-latin-500-normal"),
            ("JetBrains Mono", 400, "normal", "jetbrains-mono-greek-400-normal")]
    out = []
    for fam, w, st, fn in spec:
        b64 = base64.b64encode((FONTS / f"{fn}.woff2").read_bytes()).decode()
        rng = "U+0370-03FF" if "greek" in fn else "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
        out.append(f"@font-face{{font-family:'{fam}';font-style:{st};font-weight:{w};font-display:block;"
                   f"src:url(data:font/woff2;base64,{b64}) format('woff2');unicode-range:{rng}}}")
    return "\n".join(out)


def plate_svg(name):
    s = (PLATES / f"{name}.svg").read_text(encoding="utf-8")
    s = re.sub(r"<\?xml[^>]*\?>\s*", "", s)
    for old, new in COLOURS.items():
        s = re.sub(old, new, s, flags=re.I)
    for old, new in FONT_MAP.items():
        s = s.replace(f'font-family="{old}"', f'font-family="{new}"').replace(f"font-family:{old}", f"font-family:{new}")
    for old, new in TEXT_FIXES.get(name, {}).items():
        assert old in s, (name, old)
        s = s.replace(old, new)
    # unique ids per plate
    ids = set(re.findall(r'\bid="([^"]+)"', s))
    for i in ids:
        s = s.replace(f'id="{i}"', f'id="{name}-{i}"').replace(f"url(#{i})", f"url(#{name}-{i})")
        s = s.replace(f'href="#{i}"', f'href="#{name}-{i}"')
    # responsive root: keep the viewBox, drop fixed size, add a role and a description
    root = re.search(r"<svg\b[^>]*>", s).group(0)
    new_root = re.sub(r'\s(width|height)="[^"]*"', "", root)
    new_root = new_root.replace("<svg", f'<svg role="img" aria-label="{ALT[name]}"', 1)
    return s.replace(root, new_root, 1)


def halves_uri(width=2000):
    """The Kristiansund map: ground shifted from the v4.5 charcoal to the v5.5 oxblood, dark pixels only."""
    im = Image.open(PLATES / "halves.png").convert("RGB")
    px = im.load()
    dr, dg, db = 0x2E - 25, 0x15 - 21, 0x1C - 18
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            w = max(0.0, min(1.0, 1 - (max(r, g, b) - 45) / 40))
            if w:
                px[x, y] = (min(255, round(r + dr * w)), min(255, round(g + dg * w)), min(255, round(b + db * w)))
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


GREEK = re.compile("([ρλβθδηγεκΦ])")


def main():
    html = (HERE / "src" / "proposal-v55.html").read_text(encoding="utf-8")
    # Greek letters in running text use the mono face (the serif subset has no Greek)
    head, body = html.split("<body>", 1)
    parts = re.split(r"(<svg.*?</svg>|<style.*?</style>|<script.*?</script>|<[^>]+>)", body, flags=re.S)
    body = "".join(p if p.startswith("<") else GREEK.sub(r'<span class="gk">\1</span>', p) for p in parts)
    html = head + "<body>" + body
    html = html.replace("/*FONTS*/", font_css())
    for name in ALT:
        html = html.replace(f"<!--PLATE:{name}-->", plate_svg(name))
    html = html.replace("<!--HALVES-->", f'<img alt="Kristiansund, every building assigned to the side of Nordsundbrua it reaches without the bridge; the toll stations, the toll-free tunnel and three traced trips." src="{halves_uri()}">')
    assert "<!--PLATE" not in html and "<!--HALVES" not in html
    out = HERE / "proposal-v5.5.html"
    out.write_text(html, encoding="utf-8")
    print("wrote", out.name, f"{out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
