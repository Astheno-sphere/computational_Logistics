# Computational Logistics: Claude Code skills for Rhino 8 + Grasshopper

Terrain-aware logistics for Molde and Kristiansund, run by Claude Code
through Rhino MCP. It follows Abhinav Bhardwaj's skill-plugin architecture:
a foundation layer with a router, specialist skills, calculators and an
orchestrated workflow. It also fixes what his plugins lack: routers checked by
tests, standard frontmatter, and real solvers instead of arithmetic only.

> **Status (honest):** the skills below are **planned, not built yet**. What exists today is the
> knowledge bank and its tooling (`tools/`, `tests/`), plus `make_grid_osm.py` and `grid_molde.osm`.

## Knowledge bank (built)

`knowledge-bank/` collects open-source skills, MCP servers, solvers and guides, license-checked and
credited, and assembles them into a catalog. Start at `knowledge-bank/README.md`, then
`knowledge-bank/catalog/README.md`. What we still lack and what comes next: `knowledge-bank/ROADMAP.md`.

## Planned skills (not built yet)

| Skill | Does |
|---|---|
| `cl-foundations` (auto) | shared UTM32N frame, layer contract, routing canon, anti-patterns, router |
| `rhino-mcp-bridge` | MCP session procedure, preflight, city model (`city_visualizer_v2.py`) |
| `gh-canvas` | `ghkit.py`: build/wire/solve/bake Grasshopper by name at runtime, plugin inventory, recipes |
| `grasshopper-plugins` | which free plugin for which logistics job (Heron, Ladybug, Galapagos, Wallacei, Elefront, Hops, ...) |
| `routing` | OSM road graph, time/distance/grade/energy routes (exact with regeneration), bake to Rhino |
| `cl-calculator` | `grade_cost.py`, `route_energy.py` (stdlib, `--json`) |
| `cl-train` | Lessons 0-7: Rhino + Grasshopper together, on this project |

Planned: `lib/cl_frame.py` (the only copy of the frame constants) and `docs/abhinav-patterns.md`
(the analysis of his repos). The install and lesson steps below describe the planned plugin.

## Install (Windows, same machine as Rhino)

1. Unzip to a stable folder, e.g. `C:\Tools\computational-logistics`.
   Keep the folder structure: scripts find `lib/` relative to themselves.
2. Start Claude Code in your project folder with the plugin loaded:
   ```
   claude --plugin-dir "C:\Tools\computational-logistics"
   ```
3. Make sure Rhino 8 is open and your Rhino MCP server is connected (`/mcp`
   in Claude Code shows it).
4. Tell Claude Code where your OSM files are, e.g.
   `D:\osm\molde.osm` and `D:\osm\kristiansund.osm`.

## First session

```
/cl-train 0
```

Claude Code may list it as `/computational-logistics:cl-train`. Lesson 0:
- discovers your MCP tools
- checks units and the EarthAnchorPoint
- creates the layers
- writes `inventory/gh_inventory.json`: every Grasshopper plugin and component on
  your machine, so Claude uses your real component names from then on

Then run `/cl-train 1`, then 2, and so on.

## What has been tested, and what hasn't

- **Tested now (`python3 -m pytest tests`, 7 passing):** the knowledge-bank license classifier
  (permissive vs copyleft vs not-open-source) and the catalog's domain classifier and frontmatter parser.
- **Not built, so not tested:** every skill listed above, the Rhino-side scripts and the calculators.

## Honest limits

- Vehicle parameters are assumptions; replace them with operator data.
- Energy = constant-speed traction (+ optional HVAC). No stop-and-go, so real
  consumption is higher. Calibrate before quoting.
- Heights come from 30 m-class DEMs (SRTM/ALOS via Heron). Bridges and tunnels
  follow the ground.
- Multi-stop VRP (OR-Tools via Hops) and ferry edges are specified but not built yet.
