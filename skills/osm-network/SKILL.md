---
name: osm-network
description: Build a drivable, terrain-aware road graph from OpenStreetMap (file or place name) with OSMnx, with per-edge length, grade, speed, travel time and vehicle energy, and find fastest, shortest or least-energy routes. Use for any routing, accessibility or VRP work that needs real road costs instead of straight lines.
---

# osm-network

`scripts/osm_network.py` turns OSM data into a directed graph that the other logistics skills share.

## Pipeline
1. **Load**: `--osm file.osm` (offline) or `--place "Molde, Norway"` (online). One-way streets stay
   one-way. Footways, paths, steps and cycleways are removed. Only the largest strongly connected
   part is kept, so every stop can reach every other.
2. **Project** to the local UTM zone (Molde/Kristiansund: EPSG:32632), metres everywhere.
3. **Terrain**: `--dem dem.tif` sets node elevations (OSMnx raster sampler); edge `grade` = rise/run.
   Without a DEM the graph is flat: say so in any result.
4. **Costs**: speed from `maxspeed`, else `HWY_SPEEDS` defaults (assumptions); `travel_time` [s];
   `energy_kwh` from `Vehicle` (mass, rolling, drag, drivetrain efficiency, regeneration).

## Use
```
python scripts/osm_network.py --osm data/synthetic/grid_molde.osm --summary
python scripts/osm_network.py --osm data/synthetic/grid_molde.osm --route 7.1592,62.7375 7.1826,62.7483 --weight energy_kwh
python scripts/osm_network.py --place "Kristiansund, Norway" --dem dem.tif --out ksu.graphml
```
In Python: `G = build(osm=..., dem=...)`, `route(G, nearest(G, lon, lat), ..., weight)`.

## Rules
- Least-energy routing uses **Bellman-Ford**, not Dijkstra: downhill edges are negative with
  regeneration. A negative cycle is physically impossible while `regen < 1`; the code fails loudly if
  bad data creates one (usually a DEM spike).
- Vehicle and speed values are assumptions. Report them with results; replace with operator data.
- Energy is constant-speed traction: no acceleration, stops or HVAC. Real use is higher.
- DEMs drape bridges and tunnels over the ground. Check those edges by hand.

## Tested (`tests/test_osm_network.py`)
UTM projection, footway removal, one-way rule, flat-road energy vs hand calculation, uphill > |downhill|,
least-energy route vs independent Bellman-Ford on a 120 m synthetic hill.
