---
name: visual-narrative
description: Make single-page explainer plates that teach one computational-urbanism or logistics idea — a concept stated as a procedure, one highlighted instance among many, map apparatus, citations and the code that builds it. Use when a result, method or concept needs one figure that explains it to planners, students or social media, or when asked for a plate, explainer, carousel slide or diagram "in our style".
---

# visual-narrative

One plate, one idea. `scripts/plate.py` holds the fixed page; each plate is a script that draws only
its hero figure into it.

```bash
python skills/visual-narrative/scripts/pinch_points.py                       # plate 01, bundled Helsinki sample
python skills/visual-narrative/scripts/pinch_points.py --pbf molde.osm.pbf \
    --place "MOLDE" --crs EPSG:32632 --caveat ""                              # full extract: real figures
```

| Plate | Idea | Script | Output |
|---|---|---|---|
| 01 | Freight pinch points: edge betweenness on fastest routes | `scripts/pinch_points.py` | `docs/plates/01-freight-pinch-points.png` |

## The grammar (v0, from a 5-image study of a reference series; refine as the study grows)
1. **Say the idea as a procedure.** The sentence under the headline is something the reader could do:
   "Send a van between every pair of junctions…", not "Betweenness measures…". Write it first; if it
   cannot be written as steps, the plate is not ready.
2. **One instance, in the one accent.** Draw the whole system in paper-on-ink, then show *one* instance
   of the concept in `ACCENT` (a glowing corridor, one route, one part). The accent is never decoration.
3. **The accent word names the accent thing.** The coloured word in the headline is the concept the
   accent marks in the figure.
4. **Fixed page** (`plate.py`): italic lowercase kicker posing the question · caps document label
   (place — dataset — method) · framed hero · rule · caps headline · one or two sentences · code
   caption · sources · series footer and plate number. 1440 × 1800 px.
5. **Restraint:** ink ground, one line weight for context, a single accent; a ramp only when a value is
   being read, legend labelled in the reader's words ("share of fastest routes"), not the metric's.
6. **Proof:** scale bar, north arrow, cited sources, the real function call. Every number on the plate
   comes out of the script that drew it.
7. **Scale for the body or vehicle** when the geometry is abstract (a person, a van) — not yet used.

## Rules
- Our palette and voice, not the reference's: `INK #10161B`, `PAPER #E8E1CF`, `ACCENT #FF5B3A`.
  Study other people's work for method; never trace their plates or reuse their artwork.
- Say what the data cannot carry. Plate 01's default extract has gaps in street coverage, so its
  shares illustrate the method; the `--caveat` line prints that on the plate until a full extract is used.
- Callouts state a measured value, not an interpretation the model didn't compute ("on 19 % of fastest
  routes", not "the only crossing").
- OSM data: credit "© OpenStreetMap contributors (ODbL)" on the plate.

## Needs
`pyrosm` (reads `.osm.pbf` offline; bundles a Helsinki sample), `networkx`, `geopandas`, `matplotlib`.
Full extracts: download a region from Geofabrik on your own machine and pass `--pbf`.
