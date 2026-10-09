#!/usr/bin/env python3
"""Assemble docs/proposal/index.html from src/proposal.html, towns.json (make_towns.py) and study.json (make_data.py)."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from refs import renumber  # noqa: E402
here = Path(__file__).parent
html = (here / "src" / "proposal.html").read_text(encoding="utf-8")
towns = (here / "towns.json").read_text(encoding="utf-8")
study = (here / "study.json").read_text(encoding="utf-8")
hairline = (here / "vendor" / "hairline.min.js").read_text(encoding="utf-8")
(here / "index.html").write_text(html.replace("/*TOWNS*/null", towns).replace("/*STUDY*/null", study).replace("/*HAIRLINE*/", hairline), encoding="utf-8")
print("wrote", here / "index.html")

# the five-page proposal in the line-art plate grammar (src/proposal5.html -> proposal5.html)
p5 = (here / "src" / "proposal5.html").read_text(encoding="utf-8")
lineart = (here.parents[1] / "skills" / "visual-narrative" / "lineart" / "lineart.js").read_text(encoding="utf-8")
(here / "proposal5.html").write_text(p5.replace("/*LINEART*/", lineart).replace("/*TOWNS*/null", towns).replace("/*STUDY*/null", study), encoding="utf-8")
print("wrote", here / "proposal5.html")

# the five-page ranked proposal, same grammar (src/five-page.html -> proposal-5p.html)
p5s = renumber((here / "src" / "five-page.html").read_text(encoding="utf-8"))
(here / "proposal-5p.html").write_text(p5s.replace("/*LINEART*/", lineart).replace("/*TOWNS*/null", towns).replace("/*STUDY*/null", study), encoding="utf-8")
print("wrote", here / "proposal-5p.html")

# the portfolio: the same plate grammar at full length (src/portfolio-*.html/css/js -> portfolio.html)
import base64, io, json  # noqa: E402
from PIL import Image  # noqa: E402


def jpeg_uri(path, width=1200):
    im = Image.open(path).convert("RGB")
    im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


src5 = (here / "src" / "five-page.html").read_text(encoding="utf-8")
head = src5[:src5.index("</style>") + len("</style>")].replace("<title>The Path to 2050</title>", "<title>Path to 2050 Portfolio</title>", 1)
# the plate script of the five-page source, with every plate guarded so absent svgs are skipped
plates = src5[src5.index("<script>\nconst TOWNS"):]
plates = plates[:plates.index("</script>") + len("</script>")]
dcm = json.loads((here.parents[1] / "docs" / "results" / "transplan_study.json").read_text(encoding="utf-8"))["dcm"]
body = (here / "src" / "portfolio-body.html").read_text(encoding="utf-8")
for key, name in {"01": "01-freight-pinch-points", "02": "02-where-the-detour-goes", "03": "03-the-five-minute-depot", "04": "04-the-shortest-loop"}.items():
    body = body.replace(f"/*IMG:{key}*/", jpeg_uri(here.parents[1] / "docs" / "plates" / f"{name}.png"))
port = (head + "\n<style>\n" + (here / "src" / "portfolio.css").read_text(encoding="utf-8") + "</style>\n" + body
        + "\n<script>/*LINEART*/</script>\n" + plates
        + "\n<script>\nconst DCM=" + json.dumps(dcm) + ";\n" + (here / "src" / "portfolio-plates.js").read_text(encoding="utf-8") + "</script>\n")
port = renumber(port).replace("/*LINEART*/", lineart).replace("/*TOWNS*/null", towns).replace("/*STUDY*/null", study)
(here / "portfolio.html").write_text(port, encoding="utf-8")
print("wrote", here / "portfolio.html")

# the five-page A3 proposal (src/a3.html + src/a3-plates.js -> proposal-a3.html)
a3 = renumber((here / "src" / "a3.html").read_text(encoding="utf-8"))
a3 = (a3.replace("/*A3PLATES*/", (here / "src" / "a3-plates.js").read_text(encoding="utf-8"))
        .replace("/*LINEART*/", lineart).replace("/*TOWNS*/null", towns)
        .replace("/*BRIDGE*/null", (here / "bridge.json").read_text(encoding="utf-8")))
(here / "proposal-a3.html").write_text(a3, encoding="utf-8")
print("wrote", here / "proposal-a3.html")
