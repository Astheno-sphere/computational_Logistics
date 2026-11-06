# Sim studio tool collection

Status is **tested**, not claimed. Tested in the Claude workspace on 2026-11-06 (x86-64, 2 CPU, 7.8 GB,
no GPU, Python 3.13, Node 22). "Actions" = GitHub-hosted runner (open internet, 4 CPU).

| Layer | Tool | Licence | Here | Where it runs | Used for | Status |
|---|---|---|---|---|---|---|
| World | OSM coastline via Overpass + `visual-narrative/coast.py` | ODbL | blocked | Actions → release | land polygons | written, first run pending |
| World | Sodir FactMaps WGS84 FeatureServer | NLOD | blocked | Actions → release | installations, fields, pipelines | written, first run pending |
| World | Kartverket Sjøkart dybdedata; NGU Oslofjord 1 m grid | open (Kartverket/NGU terms) | blocked | manual download | depth, lanes, relief | manual (Geonorge order) |
| World | Kystverket Historic AIS (HAIS), GeoParquet | open | blocked | manual order | validate routes/speeds vs real traffic | manual |
| World | Kystverket reference routes for navigation | NLOD | blocked | manual | sea-lane graph | manual |
| World | `searoute` 1.x | Apache-2.0 | ok | here | long-haul look-alike legs only ("not for routing") | installed |
| Solver | PyVRP 0.14 | MIT | ok | here | VRP/VRPTW/PDP, multi-depot, hetero fleet, multi-trip | tested (toy reproduces its objective to 0.003%) |
| Solver | OR-Tools 9.15, Pyomo + HiGHS | Apache-2.0 / BSD / MIT | ok | here | cross-check; exact MILP models from papers | in repo (`vrp-solve`, `opt-model`) |
| Solver | AMPL | commercial (academic free) | no | laptop | paper models written in AMPL | user's machine |
| Sim | SimPy 4.1 | MIT | ok | here | time, queues (berths/helidecks), time windows | tested (`studio/sim/replay.py`) |
| Sim | Fossen PythonVehicleSimulator (`supply.py` OSV) | MIT | not installed | here | ship manoeuvring / DP time when a paper needs it | candidate |
| Sim | VISIR-2 weather routing | GPL | not installed | here, separate module | currents/waves/wind routing papers | candidate (copyleft: keep isolated) |
| Sim | movingpandas 0.23 | BSD | ok | here | trajectory ops, AIS comparison | installed |
| Contract | `studio/contract.py` | MIT (ours) | ok | here + CI | validation, KPIs, paper comparison | tested (12 tests) |
| Render | deck.gl 9 TripsLayer via headless Chrome (SwiftShader) + ffmpeg | MIT / LGPL | ok | here (drafts), Actions (finals) | 2.5D animated maps | tested: 640×360 ≈ 8 fps, 1080² still OK |
| Render | Blender 5.2 as `bpy` | GPL | ok | here (stills), Actions/laptop (video) | low-poly 3D hero shots | tested: Workbench 1.4 s, Cycles CPU 4 s, EEVEE 47 s per 640×360 frame |
| Render | BlenderGIS add-on | GPL | not installed | laptop | DEM/OSM import into Blender | candidate |
| Render | Remotion 4 (system Chrome) | Remotion licence (free for individuals/small teams) | ok | here | captions, title cards, compositing | tested |
| Skills | `remotion-dev/skills` (remotion-best-practices) | see repo | — | install per project | Remotion correctness | candidate |
| Skills | SimPy skill (`k-dense-ai/scientific-agent-skills`; also vendored in `knowledge-bank/`) | see repo | — | install per project | SimPy patterns | candidate |
| Publish | muse.ai | commercial | blocked | user's browser | hosting/sharing finished MP4s | not a renderer: it hosts video, it does not compute |

## Network map (why the pipeline is split)
Reachable here: GitHub (git, `gh` API, release downloads), raw.githubusercontent, PyPI, npm.
Blocked here: Kartverket/Geonorge, Kystverket, Sodir, Overpass, OSM and Carto tiles, unpkg, muse.ai.
So: **data in** via Actions → release → `--pull`; **compute** here (solve, simulate, validate, drafts);
**heavy renders** on Actions; **publishing** from your browser.

## Before adding a tool
Read its licence and code (knowledge-bank rule). Copyleft (GPL: VISIR-2, Blender, BlenderGIS) runs as a
separate process or file exchange; never import it into our MIT code.
