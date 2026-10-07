---
name: visual-narrative
description: Make single-page explainer plates that teach one computational-urbanism or logistics idea — a concept stated as a procedure, one highlighted instance among many, map apparatus, citations and the code that builds it. Use when a result, method or concept needs one figure that explains it to planners, students or social media, or when asked for a plate, explainer, carousel slide or diagram "in our style".
---

# visual-narrative

One plate, one idea. `scripts/plate.py` holds the fixed page; each plate is a script that draws only
its hero figure into it.

```bash
python skills/visual-narrative/scripts/pinch_points.py          # plate 01, Molde (data/osm/molde.osm.bz2), ~1 min
python skills/visual-narrative/scripts/pinch_points.py --osm kristiansund.osm --place "KRISTIANSUND" --water-label ""
```

| Plate | Idea | Script | Output |
|---|---|---|---|
| 01 | Freight pinch points: edge betweenness on fastest routes, Molde | `scripts/pinch_points.py` | `docs/plates/01-freight-pinch-points.png` |

| Helper | Does |
|---|---|
| `scripts/plate.py` | the page: kicker, label, framed hero, rule, headline with one accent word, sentence, code, sources, footer; north arrow, scale bar |
| `scripts/coast.py` | sea polygons from OSM coastline ways (land left, sea right), shrinking the frame past a lat/lon-cut extract's loose ends |

## The grammar (v0, from a 5-image study of a reference series; refine as the study grows)
1. **Say the idea as a procedure.** The sentence under the headline is something the reader could do:
   "Send a van between every pair of junctions…", not "Betweenness measures…". Write it first; if it
   cannot be written as steps, the plate is not ready.
2. **One instance, in the one accent.** Draw the whole system in paper-on-ink, then show *one* instance
   of the concept in `ACCENT` (a glowing corridor, one route, one part). The accent is never decoration.
3. **The accent word names the accent thing.** The coloured word in the headline is the concept the
   accent marks in the figure.
4. **Show the cause, not only the place.** Plate 01's fjord explains why one street carries the town;
   draw the geography that forces the result, and crop so it fills the frame.
5. **Fixed page** (`plate.py`): italic lowercase kicker posing the question · caps document label
   (place — dataset — size) · framed hero · rule · caps headline · one or two sentences · code
   caption · sources · series footer and plate number. 1440 × 1800 px.
6. **Restraint:** ink ground, context (buildings) darker than the quietest street, a single accent; a ramp
   only when a value is being read, legend labelled in the reader's words ("share of fastest routes").
7. **Proof:** scale bar, north arrow, cited sources, the real function call. Every number on the plate
   comes out of the script that drew it.
8. **Scale for the body or vehicle** when the geometry is abstract (a person, a van): not used yet; a
   town-scale map has no room for it, a street-scale inset would.

## Rules
- Our palette and voice, not the reference's: `INK #10161B`, `PAPER #E8E1CF`, `ACCENT #FF5B3A`.
  Study other people's work for method; never trace their plates or reuse their artwork.
- Compute first, write second: draft the sentence and callouts from the script's printed results.
  Callouts state a measured value ("on 18 % of fastest routes"), never an effect nobody computed.
- Say what the data cannot carry: `--caveat` prints a note line on the plate. Plate 01 is flat (no DEM)
  and uses default speeds where OSM has no `maxspeed` (`osm-network` HWY_SPEEDS).
- OSM data: credit "© OpenStreetMap contributors (ODbL)" on the plate.

## Needs
`osmnx` (through `osm-network`), `networkx`, `geopandas`, `shapely`, `matplotlib`. Molde extract:
`data/osm/molde.osm.bz2` (Overpass, 2026-08-29, bbox 62.72–62.78 N, 7.05–7.25 E, ODbL).
