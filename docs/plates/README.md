# Plates

One idea per plate, told in the house style of [`visual-narrative`](../../skills/visual-narrative/SKILL.md).
All four run on real OpenStreetMap data for Molde through the same road graph as `osm-network` and
`vrp-solve`; every number on a plate is printed by the script that drew it.

| # | Plate | The method, as something you do | Measured | Script |
|---|---|---|---|---|
| 01 | [Freight pinch points](01-freight-pinch-points.png) | Route a van between every pair of junctions; colour each street by the share of routes on it | Øvre veg is on 18% of all fastest routes | `pinch_points.py` |
| 02 | [Where the detour goes](02-where-the-detour-goes.png) | Close that street and route every trip again | 32% of trips slower, by 10 s on average, 2 min at worst; Strandgata gains 13 points; 0.9% of trips impossible | `detour.py` |
| 03 | [The five-minute depot](03-the-five-minute-depot.png) | Time the drive from every junction to every other; keep the shortest average | 79% of buildings within 5 min of the best junction; 56% from the median junction | `reach.py` |
| 04 | [The shortest loop](04-the-shortest-loop.png) | Give one van 24 addresses and let a solver order them | 48 min of driving instead of 137 (65% less); OR-Tools agrees with PyVRP within 0.1% | `loop.py` |
| 05 | [The stock turns](05-the-stock-turns.png) | Draw one street twice, lighting each car by the simulated electric share | 3 in 10 electric in 2025, 9 in 10 in 2050 under the most robust package (synthetic behaviour) | `lineart/render.py stock-turns` |

The plates read as a sequence: where the network is fragile (01), what breaking it costs (02), where
to stand to serve the town (03), and how to drive it once you stand there (04).

## Rebuild

```bash
# once: fetch the Molde extract (data/osm/README.md), then
python skills/visual-narrative/scripts/pinch_points.py   # ~1 min
python skills/visual-narrative/scripts/detour.py         # ~2.5 min: all 7.7 M junction pairs, twice
python skills/visual-narrative/scripts/reach.py          # ~40 s; writes 03-depot.json for plate 04
python skills/visual-narrative/scripts/loop.py           # ~50 s
```

## What the plates assume
- Free-flow drive times from `osm-network`: OSM `maxspeed`, else its default speeds by road class; no
  turn penalties, signals or congestion. The town is flat in this model (no elevation data yet).
- Plate 04's addresses are drawn at random from OSM buildings (seed 7): an illustration of the method,
  not a real delivery day. A building counts from its nearest junction.
- Re-runs can differ in the last digit (ties among equally fast routes, and OSMnx's graph build order);
  no rounded figure on the plates changes.
