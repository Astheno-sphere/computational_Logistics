---
name: visual-director
description: Motion grammar for sim studio videos - turns a validated trajectory into a 2.5D animated scene (camera fitted to the study area, one accent for the thing the paper is about, state halos for waiting and loading, live clock and measured KPIs) in the visual-narrative house palette, and renders drafts here and 1080p finals on GitHub Actions. Use when a corrector-approved simulation needs a video, still or LinkedIn format.
---

# visual-director

Extends `visual-narrative` from plates to motion. Same palette and voice (`studio/style.json`, copied
from `plate.py`): ink ground, paper linework, **one** accent.

## Pipeline
`studio.scene.build_scene(...)` (refuses invalid trajectories) → `scene.json` →
`python studio/render_deck/render.py --scene ... --format draft|square|vertical|wide [--still]`.
Draft (640×360) and stills render in this workspace (software WebGL, ~8 frames/s at draft).
Finals: run workflow `studio-render` (Actions), download the MP4 from the release it creates.

## Grammar (v0, to be refined per video like plates 01-04)
1. One question as the kicker, one idea as the title; the accent is the optimised plan or the one
   agent the paper is about. Baseline in paper, never a second accent.
2. Show the cause: the coast, the field layout, the weather window. Use world data, not decoration.
3. Time is explicit: clock always on; waiting and loading are halos in their state colour.
4. Numbers on screen come only from `kpi_track`, built from `studio.contract.kpis`.
5. Credit line always: paper DOI, data sources with licence (Sodir NLOD, Kartverket, Kystverket,
   © OpenStreetMap contributors ODbL), and "SYNTHETIC" when any geometry or demand is invented.
6. Formats: square 1080², vertical 1080×1350 for LinkedIn; wide 1920×1080 for talks.

## Not yet (deliberately)
Low-poly 3D vessels, Blender hero shots (`bpy` 5.2 works here: Workbench ~1 s/frame, Cycles CPU
~4 s/frame at 640×360; finals belong on Actions), Remotion captions (works here with system Chrome).
Add each only when a paper's story needs it.
