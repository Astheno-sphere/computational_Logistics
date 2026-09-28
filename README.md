# Computational Logistics: Claude Code skills for Rhino 8 + Grasshopper

Terrain-aware logistics for Molde and Kristiansund, run by Claude Code
through Rhino MCP. It follows Abhinav Bhardwaj's skill-plugin architecture:
a foundation layer with a router, specialist skills, calculators and an
orchestrated workflow. It also fixes what his plugins lack: routers checked by
tests, standard frontmatter, and real solvers instead of arithmetic only.

## What's inside

| Skill | Does |
|---|---|
| `cl-foundations` (auto) | shared UTM32N frame, layer contract, routing canon, anti-patterns, router |
| `rhino-mcp-bridge` | MCP session procedure, preflight, city model (`city_visualizer_v2.py`) |
| `gh-canvas` | `ghkit.py`: build/wire/solve/bake Grasshopper by name at runtime, plugin inventory, recipes |
| `grasshopper-plugins` | which free plugin for which logistics job (Heron, Ladybug, Galapagos, Wallacei, Elefront, Hops, ...) |
| `routing` | OSM road graph, time/distance/grade/energy routes (exact with regeneration), bake to Rhino |
| `cl-calculator` | `grade_cost.py`, `route_energy.py` (stdlib, `--json`) |
| `cl-train` | Lessons 0-7: Rhino + Grasshopper together, on this project |

`lib/cl_frame.py` holds the only copy of the frame constants.
`docs/abhinav-patterns.md` is the analysis of his repos this plugin is built from.

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

- **Tested here (`pytest tests`, 14 passing):**
  - frame maths vs PROJ (< 1 mm)
  - least-energy routing vs brute-force Bellman-Ford
  - one-way/access rules
  - calculator physics and CLI
  - skill structure: router targets exist, frontmatter keys are standard
  - Rhino-side scripts avoid py3-only syntax
- **Not testable outside Rhino:** everything that calls RhinoCommon or
  Grasshopper (`ghkit`, `rhino_preflight`, `rhino_route` baking, recipes).
  Lessons 0-2 are the live test. If a call errors, paste the traceback to
  Claude Code; the fix is usually a component or port name on your plugin
  version.

## Honest limits

- Vehicle parameters are assumptions; replace them with operator data.
- Energy = constant-speed traction (+ optional HVAC). No stop-and-go, so real
  consumption is higher. Calibrate before quoting.
- Heights come from 30 m-class DEMs (SRTM/ALOS via Heron). Bridges and tunnels
  follow the ground.
- Multi-stop VRP (OR-Tools via Hops) and ferry edges are specified but not built yet.
