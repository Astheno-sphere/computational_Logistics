#!/usr/bin/env python3
"""Assemble docs/proposal/index.html from src/proposal.html, towns.json (make_towns.py) study.json (make_data.py) and motion.json (make_motion.py)."""
from pathlib import Path
here = Path(__file__).parent
html = (here / "src" / "proposal.html").read_text(encoding="utf-8")
towns = (here / "towns.json").read_text(encoding="utf-8")
study = (here / "study.json").read_text(encoding="utf-8")
motion = (here / "motion.json").read_text(encoding="utf-8")
motion_js = (here / "src" / "motion.js").read_text(encoding="utf-8").replace("/*MOTION*/null", motion)
hairline = (here / "vendor" / "hairline.min.js").read_text(encoding="utf-8")
(here / "index.html").write_text(html.replace("/*TOWNS*/null", towns).replace("/*STUDY*/null", study).replace("/*HAIRLINE*/", hairline).replace("/*MOTION_JS*/", motion_js), encoding="utf-8")
print("wrote", here / "index.html")
