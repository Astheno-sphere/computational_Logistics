# Absorption checklist

Everything we want to learn from, what we take from it, where it lands in this repo, and its state.
Legend: ✅ done · ◐ partly · ○ planned · ✕ not absorbed (reason given). Priority: P1 now, P2 next, P3 later.

**Rule for sources.** Open-licensed material (code, the McNeel books) is kept in `knowledge-bank/` with
its license and credit. Paid books (Abhinav Bhardwaj's three) are **not** copied, summarised chapter by
chapter or paraphrased: read them yourself; here we only map their *published tables of contents* to
skills we build from open sources. That keeps the work yours and the authors' rights intact.

## 1. Abhinav Bhardwaj, *72 Ways Architects Use Claude* (2026), by chapter

His method, which we adopt for every skill: **exact command, runnable code on real libraries, and a
verification step before anything touches a drawing.** Ours: `SKILL.md` + scripts + tests + a
"Tested" section, and two independent solvers for every plan.

| Chapter | What we absorb | Our skill | State | P |
|---|---|---|---|---|
| A. Concept (brief to programme, adjacency graph, weighted scoring) | adjacency as a graph, option scoring as a model | `opt-model` (scoring/assignment as LP/MIP) | ○ | P3 |
| B. Site and Urban: pull and clean OSM | drivable graph, one-way, UTM, any city | `osm-network` | ✅ | P1 |
| B. 15-minute catchments | isochrones on the road/walk graph | `isochrone-access` | ○ | P1 |
| B. Rank streets by movement | betweenness/closeness, space syntax style | `street-centrality` (NetworkX, momepy in bank) | ○ | P2 |
| B. Sun and shadow | solar position, shadow casting on massing | later, with massing | ○ | P3 |
| B. Zoning constraints, census catchment | data connectors per country | `geodata-*` connectors | ○ | P2 |
| C. Write and debug GHPython / C# | tree-aware scripting, probe and diagnose | `gh-datatree` + `gh-datatree-debugger` | ✅ | P1 |
| C. Decode an inherited definition | probe every component, report structure | `gh_tree_probe` (whole document) | ◐ | P1 |
| C. Multi-objective optimisation, Pareto front | NSGA-II on routing/siting objectives (time vs energy vs vans) | `pareto-plan` (pymoo) | ○ | P2 |
| C. Drive the live model over MCP | Rhino MCP in the bank, baking routes | `rhino-bake` | ○ | P1 |
| D. Documentation and BIM | IFC takeoffs | ✕ out of logistics scope for now | | P3 |
| E. Codes: rule to checkable script | constraints as code with tests | pattern used in `opt-model` | ◐ | P3 |
| F. Sustainability (Ladybug, Honeybee, EPW) | energy and climate inputs (winter energy for EVs) | later, link to `osm-network` energy | ○ | P3 |
| G, H. Communication, practice | README/portfolio discipline | README, ROADMAP | ◐ | P3 |

## 2. Abhinav Bhardwaj, *Grasshopper Data Trees* (52 pp.), by chapter, plus Issa (McNeel, open)

| Chapter | Covered by | State |
|---|---|---|
| 1-2 The problem, anatomy of a tree | `cl_tree.Tree`, `topology()`; Issa 3_1 | ✅ |
| 3 Where trees come from | `from_nested`, probe shows levels added per component; Issa 3_2 | ✅ |
| 4 Matching | `match()`; rules checked against Issa 3_3 | ✅ (output-path rule marked VERIFY) |
| 5 Flatten, Graft, Simplify | `flatten/graft/simplify` (leading+trailing per Issa 3_5_7) | ✅ |
| 6 Path manipulation | `trim/shift/path_mapper/flip`; Split Tree and Relative Items | ◐ add `split`, `relative_items` |
| 7 Reading and navigating | probe + diagnoser | ✅ (live Rhino run pending) |
| 8 Applied patterns: facade windows, slabs and cores, parcel subdivision, tensor-field streets, typology zoning, diagrids | recipe tests in `reference/datatrees.md`; first: parcel subdivision, street networks | ○ P2 |
| 9 Quick reference | `reference/datatrees.md` | ✅ |

## 3. Abhinav Bhardwaj, *Computational Urbanism* (1,050 pp.), by part

| Part / topic | Open source in the bank | Our skill | State | P |
|---|---|---|---|---|
| I. Cities as complex systems; Python, GeoPandas | geopandas, networkx, osmnx | foundations in `osm-network` | ◐ | P1 |
| II. Space Syntax | networkx; momepy | `street-centrality` | ○ | P2 |
| II. Urban morphology (momepy, OSMnx) | momepy, osmnx | `morphology` | ○ | P3 |
| II. Rhino/Grasshopper urban modelling | rhino3dm, Heron, GH MCP | `rhino-bake`, `gis-to-rhino` | ○ | P1 |
| III. Generative design (shape grammars, L-systems, CA) | compas | later | ○ | P3 |
| III. Multi-objective evolutionary optimisation | pymoo (catalog), Galapagos/Wallacei (GH) | `pareto-plan` | ○ | P2 |
| III. Agent-based modelling | mesa, mesa-geo, SUMO, MATSim (link) | `fleet-sim` | ○ | P3 |
| III. Environmental simulation | ladybug, honeybee | later | ○ | P3 |
| III. ML/DL, computer vision, big data | rl4co, routefinder (learned routing) | `learned-routing` experiments | ○ | P3 |
| III. Digital twins | Speckle, Rhino Compute | later | ○ | P3 |
| III. CityEngine | ✕ proprietary | | |
| IV. Integrated workflows, research methods | this repo's README/ROADMAP | ◐ | P1 |

## 4. Optimisation and solvers

| Item | State | Note |
|---|---|---|
| AMPL-style modelling (sets/params/vars/constraints, data separate) | ✅ `opt-model` (Pyomo) | export .nl for AMPL solvers |
| Gurobi | ✅ free pip edition (2,000 vars, measured) | full academic license free; then no limit |
| CPLEX | ✅ Community Edition (1,000 vars, measured) | IBM Academic Initiative for full |
| HiGHS | ✅ open source, no limit | default fallback |
| AMPL itself (amplpy) | ◐ installed, needs AMPL CE license | register for Community Edition |
| PyVRP, OR-Tools | ✅ `vrp-solve` | OR-Tools isolated in a subprocess (HiGHS clash) |
| Exact CVRP to certify heuristics | ✅ `cvrp_exact` | test proves PyVRP optimal on Molde grid |

## 5. Data: any city, any country

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

## 6. Rhino, Grasshopper, GIS tools

| Tool | In bank | Use | State |
|---|---|---|---|
| Heron (Grasshopper GIS: shapefile, DEM, OSM, REST; Earth Anchor Point) | ✅ `blueherongis/Heron` (MIT) | GIS into Rhino at true coordinates | ○ `gis-to-rhino` P1 |
| QGIS / PyQGIS processing | ✅ processing framework (GPL, isolated) | batch GIS, layering, styling | ○ P2 |
| qgis_mcp | link-only (no license) | QGIS from Claude | ✕ until licensed |
| Rhino MCP / Grasshopper MCP servers | ✅ 4 open ones | live model control | ◐ used by debugger agent |
| Ladybug Tools | ✅ (AGPL, isolated) | climate, sun | ○ P3 |
| Layering and massing | Issa *Essential Mathematics* (open) for vectors, transforms, NURBS | `massing` (extrude parcels, heights from data) | ○ P2 |

## 6b. Libraries named in *72 Ways* ("real libraries with current APIs")

| Library | In bank | Used by our code |
|---|---|---|
| OSMnx | ✅ MIT | `osm-network` |
| GeoPandas | ✅ BSD-3 | via OSMnx |
| pandas | ✅ BSD-3 (user guide) | via OSMnx/GeoPandas |
| shapely | ✅ BSD-3 | via OSMnx/GeoPandas |
| pymoo | ✅ Apache-2.0 | `pareto-plan` ○ |
| Ladybug, Honeybee (core, energy, radiance) | ✅ AGPL, isolated | ○ P3 |
| IfcOpenShell | ✅ GPL/LGPL, isolated (Python part) | ✕ out of scope for now |
| pyRevit | ✅ GPL, isolated | ✕ out of scope for now |
| rhino3dm | ✅ MIT | Hops outputs (`servers/hops_app.py`) |

## 7. Agents, harnesses, models

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

## 8. Environment and repo

| Item | State |
|---|---|
| Network: Geonorge (ws.geonorge.no), Overpass, Nominatim blocked in this cloud environment | ○ allow hosts in environment settings |
| Separate knowledge-bank repo (size ~800 MB) | ○ needs your decision |
| CI running the tests on every push | ○ P2 |
| Author name and code license | ○ needs your decision |
