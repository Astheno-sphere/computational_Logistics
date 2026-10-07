---
name: cl-foundations
description: Entry point for the Asthenosphere computational logistics plugin. Routes requests about road networks, terrain-aware routing, delivery planning (VRP), discrete choice, agent-based simulation, deep-uncertainty scenario analysis and backcasting, optimisation models (LP/MIP), Grasshopper data trees and the research knowledge bank to the right skill, and states the shared conventions (UTM 32N metres, seconds, kWh, assumptions to report).
---

# Asthenosphere: router and conventions

| Request is about | Use |
|---|---|
| Road graph from OSM, grades, travel time, energy, a single route | `osm-network` |
| Several stops, vans, capacity, time windows, fleet size | `vrp-solve` (uses `osm-network`) |
| Travel behaviour: estimate mode choice, value of time, WTP | `dcm-estimate` |
| Simulate behaviour and fleets to 2050 under policies | `abm-transport` (uses `dcm-estimate` output) |
| Futures under deep uncertainty, robust policies, scenario discovery, backcasting | `dmdu-explore` (wraps `abm-transport`) |
| Show ensembles and agents: SimWrapper dashboard, kepler.gl agent-flow map, Grasshopper pathway explorer | `viz-story` (runs `abm-transport`) |
| Depots, allocation, network flows, any LP/MIP, proving a route plan optimal | `opt-model` |
| Grasshopper trees: wrong counts, pairing, nulls, paths; GhPython tree I/O | `gh-datatree`, agent `gh-datatree-debugger` |
| Showing routes in Rhino/Grasshopper | `vrp-solve --paths` -> `cl_tree.routes_to_tree` -> polylines per `{vehicle}` |
| Which open-source skill, engine or MCP server exists for X | `knowledge-bank/catalog/` (start at its README) |

## Conventions
- Coordinates: input WGS84 lon/lat; computation in the local UTM zone (Molde, Kristiansund: EPSG:32632), metres.
- Time in seconds from shift start; energy in kWh; grade as rise/run.
- Every result states its assumptions: vehicle parameters, default speeds, DEM source or "flat".
- Present VRP results only from `--solver both` runs, with violations listed (normally none).
- Third-party code in `knowledge-bank/vendor/` is read and cited, never edited or copied into our code
  without its license (copyleft folders carry `_KB_COPYLEFT.txt`).
