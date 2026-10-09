# Capability checklist

Everything we want to learn from, what we take from it, where it lands in this repo, and its state.
Legend: ✅ done · ◐ partly · ○ planned · ✕ not absorbed (reason given). Priority: P1 now, P2 next, P3 later.

**Rule for sources.** Open-licensed material (code, the McNeel books) is indexed in `knowledge-bank/` with
its license and credit. Paid books are cited, never copied or summarised.

## 1. Optimisation and solvers

| Item | State | Note |
|---|---|---|
| AMPL-style modelling (sets/params/vars/constraints, data separate) | ✅ `opt-model` (Pyomo) | export .nl for AMPL solvers |
| Gurobi | ✅ free pip edition (2,000 vars, measured) | full academic license free; then no limit |
| CPLEX | ✅ Community Edition (1,000 vars, measured) | IBM Academic Initiative for full |
| HiGHS | ✅ open source, no limit | default fallback |
| AMPL itself (amplpy) | ◐ installed, needs AMPL CE license | register for Community Edition |
| PyVRP, OR-Tools | ✅ `vrp-solve` | OR-Tools isolated in a subprocess (HiGHS clash) |
| Exact CVRP to certify heuristics | ✅ `cvrp_exact` | test proves PyVRP optimal on Molde grid |

## 2. Data: any city, any country

The framework is place-agnostic: give `osm-network` a file or a place name and it picks the local UTM zone.
Molde and Kristiansund are the test case, not the limit.

| Source | Coverage | License (check per dataset) | Connector | State |
|---|---|---|---|---|
| OpenStreetMap (Overpass, Geofabrik extracts) | global | ODbL (share-alike; fetch at use, do not vendor) | `osm-network --place` / `--osm` | ✅ offline; online blocked here |
| Overture Maps | global | CDLA/ODbL by theme | overturemaps-py in bank | ○ P2 |
| Copernicus GLO-30 / SRTM DEM | global | free with attribution | `osm-network --dem` | ◐ raster input works; downloader ○ P1 |
| Kartverket / Geonorge: høydedata (1 m DTM), adresser, stedsnavn, N50 | Norway | mostly CC BY 4.0 | `geodata-no` | ○ P1, hosts blocked here |
| Entur GTFS | Norway public transport | NLOD | gtfs_kit in bank | ○ P2 |
| National equivalents (USGS 3DEP, UK OS OpenData, ...) | per country | per provider | `geodata-<cc>` pattern | ○ P3 |

## 3. Rhino, Grasshopper, GIS tools

| Tool | In bank | Use | State |
|---|---|---|---|
| Heron (Grasshopper GIS: shapefile, DEM, OSM, REST; Earth Anchor Point) | ✅ `blueherongis/Heron` (MIT) | GIS into Rhino at true coordinates | ○ `gis-to-rhino` P1 |
| QGIS / PyQGIS processing | ✅ processing framework (GPL, isolated) | batch GIS, layering, styling | ○ P2 |
| qgis_mcp | link-only (no license) | QGIS from Claude | ✕ until licensed |
| Rhino MCP / Grasshopper MCP servers | ✅ 4 open ones | live model control | ◐ used by debugger agent |
| Ladybug Tools | ✅ (AGPL, isolated) | climate, sun | ○ P3 |
| Layering and massing | Issa *Essential Mathematics* (open) for vectors, transforms, NURBS | `massing` (extrude parcels, heights from data) | ○ P2 |

## 4. Agents, harnesses, models

| Item | State | Note |
|---|---|---|
| Claude Code plugin (skills, agents, router) | ✅ this repo | `claude --plugin-dir .` |
| Our own MCP server (skills as tools) | ✅ `servers/mcp_server.py`, `.mcp.json` | any MCP host, incl. Hermes Agent |
| Grasshopper Hops components | ✅ `servers/hops_app.py` | routes and VRP into Grasshopper |
| jSwan (JSON in Grasshopper), Rhino.Inside.Revit | ✅ in bank (MIT) | ○ P2 |
| Claude Agent SDK, MCP SDKs | ✅ in bank | for scripted pipelines |
| Hermes Agent (Nous Research) | ✅ core in bank (MIT) | compare harness design; run open models |
| Open LLM serving (vLLM, llama.cpp, Ollama) | ✅ docs in bank | local models for offline agents |
| Fine-tuning a logistics/Grasshopper model | ○ P3 | needs data we generate (probe dumps, solved instances); Hugging Face blocked here |
| Evaluation of agents on our tasks | ○ P2 | the test suite becomes the benchmark |

## 5. Environment and repo

| Item | State |
|---|---|
| Network: Geonorge (ws.geonorge.no), Overpass, Nominatim blocked in this cloud environment | ○ allow hosts in environment settings |
| Separate knowledge-bank repo (size ~800 MB) | ○ needs your decision |
| CI running the tests on every push | ○ P2 |
| Author name and code license | ○ needs your decision |
