---
name: visual-narrative
description: The house style for every figure Asthenosphere shows to people — single-page explainer plates that each teach one transport or logistics idea, with the method stated as a procedure, one highlighted instance among many, the geography that causes the result, map apparatus, citations and the code that computed it. Use whenever a result, scenario, method or concept needs a figure for planners, students, a thesis, a README or social media, or when asked for a plate, explainer, carousel slide or diagram "in our style".
---

# visual-narrative

**This is the repository's core visual language.** Any figure meant for other people follows it; new
plates extend the series rather than inventing a new look. The grammar was reverse-engineered from a
study of a reference series of computational-urbanism diagrams and is refined plate by plate.

```bash
python skills/visual-narrative/scripts/pinch_points.py    # 01  ~1 min
python skills/visual-narrative/scripts/detour.py          # 02  ~2.5 min
python skills/visual-narrative/scripts/reach.py           # 03  ~40 s, writes docs/plates/03-depot.json
python skills/visual-narrative/scripts/loop.py            # 04  ~50 s, reads 03-depot.json
```
Molde extract first: `data/osm/README.md`. Gallery and measured results: `docs/plates/README.md`.

| Plate | Idea | Method | Script |
|---|---|---|---|
| 01 | Freight pinch points | edge betweenness on fastest routes | `pinch_points.py` |
| 02 | Where the detour goes | close a street, re-route every pair, betweenness gain | `detour.py` |
| 03 | The five-minute depot | closeness on drive time, five-minute frontier, buildings reached | `reach.py` |
| 04 | The shortest loop | one-van routing with `vrp-solve` (PyVRP, OR-Tools cross-check) vs order received | `loop.py` |
| 05 | The stock turns | stacked street elevations, cars lit by the simulated electric share (2025, 2050) | `lineart/render.py stock-turns` |

| Helper | Does |
|---|---|
| `plate.py` | the page: kicker, label, framed hero, rule, headline with one accent word, sentence, code, sources, footer; north arrow, scale bar |
| `basemap.py` | `load()` a town once (osm-network graph, segments, buildings, fjord); `frame` (town or street scale, never past the extract), `context`, `network`, `glow`, `callout`, `mark`, `legend`, `apparatus` |
| `coast.py` | sea polygons from OSM coastline ways (land left, sea right), robust to a lat/lon-cut extract |

## A new plate
1. Pick one idea and write the sentence as a procedure the reader could do. No procedure, no plate.
2. Compute. Print every number the plate will state.
3. Draw with `basemap`: `frame` → `context` → `network` (the whole system, quiet) → the one instance
   in the accent (`glow`, a frontier, a route) → `callout` with a measured value → `apparatus` → `legend`.
4. Write sentence and callouts from the printed numbers. Look at the render; fix overlaps, clipping
   and anything the eye lands on before the instance.
5. Add it to the table above, `docs/plates/README.md` and, if it joins the series, the README grid.

## The grammar (v1: from a 5-image study, refined over plates 01–04)
1. **Say the idea as a procedure.** "Send a van between every pair of junctions…", not "Betweenness
   measures…".
2. **One instance, in the one accent.** The system in paper-on-ink, *one* instance in `ACCENT`: a
   corridor (01, 02), a frontier (03), a route (04). If the accent covers most of the frame (a first
   draft of 03 did), draw its edge instead.
3. **The accent word names the accent thing** (PINCH, DETOUR, FIVE-MINUTE, LOOP).
4. **Show the cause, not only the place.** The fjord explains Molde's single corridor; draw the
   geography that forces the result.
5. **Pick the scale of the effect.** A town-scale result gets the town; a local one gets a street-scale
   frame (02 at 2.2 km). An effect too small to see is a framing error, not a finding.
6. **Fixed page** (`plate.py`): italic lowercase kicker posing the question · caps label (place — what —
   how many) · framed hero · rule · caps headline · one or two sentences · code · sources · footer.
   1440 × 1800 px.
7. **Restraint:** ink ground, buildings darker than the quietest street, one accent; a ramp only when a
   value is read, legend in the reader's words ("share of fastest routes", "drive time from the depot").
8. **Proof:** scale bar, north arrow, cited sources, the real function call; the comparison that makes
   a number mean something (56% from the median junction; 137 min as received; OR-Tools within 0.1%).
9. **Scale for the body or vehicle** when geometry is abstract: not used yet (a street-scale inset).

## Grammar v2: line-art plates (from a 20-plate study, applied in `docs/proposal/src/proposal5.html` and plate 05)
Map plates (v1) prove a place. Line-art plates explain a mechanism. Same page, different drawing.
1. **Thin cream line on a dark ground**, one accent colour for the single thing the plate is about
   (one orange dot, one awning, one word). Vegetation is stippled dots; people and vehicles are line
   drawings at true scale, so the reader can measure the scene by the body.
2. **Pick the drawing type from the idea**, not from habit:
   | Idea | Drawing | Example |
   |---|---|---|
   | layers that build on each other | exploded axonometric, labels down the left, dashed guides, file or article tags | the engine (A1 to A3) |
   | many inputs, one operation, selected outputs | node-wire tree: bezier branches into a component box, lists out | robust filter |
   | change over time in one place | stacked elevations with a time label per row and a hatched sky band | the stock turns |
   | where something reaches | catchment blobs around an accent dot on the street grid | depot reach |
   | two worlds compared | LEFT and RIGHT panels, same scale, same projection | street versus project |
   | the code behind the result | terminal window, arrow, map or chart produced | toolbench plates |
3. **Page:** italic lowercase kicker · drawing · rule · caps title with at most one accent word · one
   plain lowercase sentence that says what happens · source line · author line.
4. **Every count drawn is a computed count** (cars lit = electric share from the run, dots = futures
   met). If a number is illustrative, the source line says so.
5. **Depth by occlusion:** objects behind are drawn first; buildings carry a ground-coloured fill so
   trees and wires pass behind them. Labels get a ground-coloured halo instead of a box.
6. **Primitives** live in `lineart/lineart.js` (person, tree, treePlan, car, house, hatch, wire,
   component, scalebar, catchment, iso). `lineart/render.py <name> <out.png>` renders a plate HTML
   to a 1440 × 1800 PNG with the prototype numbers injected.

### Three families and their typography (`LINEART_THEMES`; `render.py <plate> <out> <theme>`)
| Family | Use it for | Ground / line / accent | Title type | Page furniture |
|---|---|---|---|---|
| oxblood | tools and methods (engine, filter, toolbench) | #2f1519 / #EFE3CC / #D9734E | Roboto 900, caps, wide | italic kicker, rule, lowercase sentence |
| charcoal | ideas about places and people (urban theory, the stock, the street) | #151413 / #E9E1D0 / #D2412B | Inter 800, caps, tight tracking (-0.015em), one accent word | large grey subtitle sentence, "Source: author, year, chapter" bottom left, author name bottom right, scale bar with a caps label |
| sage | step-by-step "how to" plates (one command, one result) | #161512 / #EDE6D6 / #8FA07E | Inter 800, two lines, second line in the accent | "[ SECTION ]" bracket label top left, large plate number top right, mono terminal window, arrow to the result |

Rules shared by all three: one accent; text never sits on a line without a ground-coloured halo; the
subtitle is a plain sentence in lowercase; the source line names the data or the author and chapter.

**Still to learn (next study):** isometric street scenes with facades, stoops, awnings and people at
true scale; elevations with a time band (morning, noon, evening, night); left/right comparison pairs;
stacked density sections. Build `facade`, `stoop`, `awning`, `bench`, `bicycle`, `lamp` primitives
for them and draw a Molde street in that manner (charcoal family).

## Rules
- Our palette and voice, not the reference's: `INK #10161B`, `PAPER #E8E1CF`, `ACCENT #FF5B3A`.
  Study other work for method; never trace its plates or reuse its artwork.
- Compute first, write second. Callouts state measured values, never an effect nobody computed. Plate
  02 exists because plate 01's draft claimed "one closure stalls the district"; measured, it costs 10 s.
- Report what breaks: trips made impossible (02), random addresses (04), free-flow times, no elevation.
- Numbers on a plate must survive a re-run at their printed rounding; prefer medians over "a typical
  junction" picked by rank (03's first draft moved from 63% to 55% between runs).
- OSM data: credit "© OpenStreetMap contributors (ODbL)"; extracts are fetched, not committed.

## Needs
`osmnx`, `networkx`, `geopandas`, `shapely`, `scipy`, `matplotlib`; `pyvrp`, `ortools` for plate 04.
