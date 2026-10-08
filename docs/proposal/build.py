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
