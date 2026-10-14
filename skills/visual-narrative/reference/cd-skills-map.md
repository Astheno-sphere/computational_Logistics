# Map of Abhinav Bhardwaj's Computational Design Skills, for our visuals

Source: https://github.com/Abhinavbwj/Claude-skills-for-Computational-Designers (MIT, copyright
Abhinav Bhardwaj; commit `7a090c9`, 2026-03-26). Read 2026-10-14. Credit him wherever we adapt anything.
We do not copy its text into this repo; we load the files below on demand. The plugin is already visible
to Claude as `computational-design-skills:*`, so no install is needed.

## What it is, and what it is not
18 skills, about 35,000 lines of reference text, 7 Python calculators, for AEC computational design
(Grasshopper, Revit, geometry, structure, fabrication, environment). It is **knowledge and calculators**.
It holds **no graphic style**: no typography, plate layout, colour behaviour, motion grammar or
renderer. The look of his videos (plates, flow fields, one scale, two-act motion) is not written down
here. Our reverse-engineered version is `motion-plate-spec.md`. Do not expect this plugin to produce his
visuals by itself; it supplies the *content* a plate can be built from.

## Which file to load for which visual job (path from `skills/`, line pointers at that commit)
| Job on a plate | Load | Where |
|---|---|---|
| Agents as flocks, trails, emergence | `algorithmic-patterns` | SKILL.md §4 agent architecture and Reynolds boids (l. 238-282); `references/pattern-catalog.md` boids (l. 265) |
| Texture and growth fields | `algorithmic-patterns` | reaction-diffusion, SKILL.md l. 319; Gray-Scott, pattern-catalog l. 443 |
| Flow physics behind a streamline layer | `environmental-simulation/references/cfd-basics.md` | Navier-Stokes l. 12, buoyancy l. 48, streamlines l. 602. Theory only: **no solver code**, so a flow field still needs our own particle advection |
| Sun arc and a clock chip | `cd-calculator/scripts/solar_calculator.py` | runnable: declination, hour angle, altitude, azimuth, sunrise and sunset |
| Space syntax, GIS, urban analytics for the maps | `data-driven-design/SKILL.md` | GIS l. 88, space syntax l. 254, urban heat island l. 410, urban analytics l. 423 |
| Choosing and drawing a chart of results | `data-driven-design/SKILL.md` | data visualisation for design l. 560, spatial data visualisation l. 574 |
| Pareto fronts and design-space exploration (our A3 robustness plates) | `generative-design/SKILL.md` | Pareto optimality l. 187, front visualisation l. 195 |
| Browser 3D (isometric, orbit views) | `scripting-reference/references/web-3d-reference.md` | Three.js setup from l. 3; SKILL.md l. 1055 |
| Grasshopper and Rhino pipelines, Speckle | `interoperability` | whole skill; relevant to our Hops components |

Load one file at a time. The README's own design is progressive disclosure: `cd-foundations` routes, the
specialist skill carries the workflow, `references/` is read only when needed.

## Gaps this leaves for us
1. **No renderer for his look.** Motion, flow fields and type are ours to build (see `motion-plate-spec.md`
   and the proposal's Plate A in `docs/proposal/make_motion.py` and `src/motion.js`).
2. **No fluid solver code**, only the equations. For the vortices in his heat video we would need a small 2D
   solver or a particle stand-in.
3. **Our domain is transport and logistics**, not buildings. Use his skills for method (agents, Pareto,
   space syntax, solar geometry), not for building codes.
