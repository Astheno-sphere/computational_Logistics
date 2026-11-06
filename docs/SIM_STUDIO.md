# Sim studio: reproduce a logistics paper on a real Norwegian map, then show it

Goal: take an operations-research paper (PSV supply, ferries, offshore helicopters, worker routing),
**reproduce its result**, run it on real geography (Oslofjord, the fields west of Stavanger), and turn
the validated result into a short 2.5D video and post. Reproduction comes first; pictures come last.

## Pipeline

```
paper ─► paper-extract ─► scenario.yaml
                               │
world (studio/worlds) ─────────┤
                               ▼
                     SOLVER (PyVRP / OR-Tools / Pyomo)  ── plan
                               ▼
                     SIMULATOR (studio/sim/replay.py, SimPy) ── trajectory (the contract)
                               ▼
                     sim-corrector: plan ▸ replay = plan ▸ contract ▸ paper KPIs   ── report.json
                               ▼  (scene.py refuses anything that failed)
                     visual-director: scene.json ─► render (draft here, final on Actions)
                               ▼
                     sim-narrator: captions + post, numbers only from report.json
```

**The contract** (`studio/contract.py`) is the one table between computing and drawing: one row per agent
per timestamp (`agent_id, t, lon, lat, alt_m, state, load`) plus an agents table (`cls, vmax_mps,
capacity, domain`). Solvers and simulators write it; renderers only read it. A rendering bug can no
longer change a result, and a result bug cannot reach a video.

## Agents (Claude Code skills in `skills/`)

| Skill | Job | Blocks when |
|---|---|---|
| `paper-extract` | paper → `scenario.yaml` with a source or a flagged assumption for every value | a parameter has neither |
| `sim-corrector` | four gates: plan, replay = plan, contract, paper KPIs within tolerance | any gate fails |
| `visual-director` | motion grammar in the house palette; drafts here, finals on Actions | scene from an invalid report |
| `sim-narrator` | captions and post from `report.json`, with status: reproduced / re-run under assumptions / did not reproduce | a number without a source |

## Where things run

| Work | Where | Why |
|---|---|---|
| Fetch worlds (OSM, Sodir; later Kartverket, AIS) | GitHub Actions `studio-fetch-world` → release | those hosts are blocked in the Claude workspace |
| Solve, simulate, validate, draft renders, stills | Claude workspace | all tested here (`studio/TOOLS.md`) |
| Final 1080p videos | GitHub Actions `studio-render` → release | 2 CPUs, no GPU here; Actions runs in parallel at no cost on a public repo |
| Hosting and sharing videos | muse.ai / LinkedIn, from your browser | muse.ai hosts video; it cannot run Blender or deck.gl |

## Try it

```bash
python -m studio.examples.toy_fjord --out studio/out/toy      # synthetic: solve → replay → validate → scene
python -m pytest -q tests/test_studio.py                         # the contract catches each bug class
python studio/render_deck/render.py --scene studio/out/toy/scene.json --out studio/out/toy/draft.mp4
```

The toy's first run already paid for the framework: the corrector stopped a plan that overloaded a
vessel and sailed 35% further than the solver's own objective (a PyVRP 0.14 index change), and a
baseline that ignored capacity. Both would have looked fine on screen.

## Next
1. Run `studio-fetch-world` for both worlds; check land polygons and Sodir layers.
2. Pick the first paper (candidate: Nafstad et al. 2020, offshore helicopter scheduling, *C&OR*, CC BY)
   and run `paper-extract`.
3. Sea-lane graph from Kystverket reference routes so vessel legs follow fairways, not straight lines.
4. Only then: video grammar v1 from the first real result.
