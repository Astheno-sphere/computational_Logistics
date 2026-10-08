#!/usr/bin/env python3
"""Assemble docs/proposal/index.html from src/ pages and towns.json (OSM outlines, see data/osm)."""
from pathlib import Path
here = Path(__file__).parent
html = (here / "src" / "layer1.html").read_text(encoding="utf-8")
towns = (here / "towns.json").read_text(encoding="utf-8")
(here / "index.html").write_text(html.replace("/*TOWNS*/null", towns), encoding="utf-8")
print("wrote", here / "index.html")
