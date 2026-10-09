#!/usr/bin/env python3
"""Assemble docs/proposal/index.html from src/proposal.html, towns.json (make_towns.py) and study.json (make_data.py)."""
from pathlib import Path
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
