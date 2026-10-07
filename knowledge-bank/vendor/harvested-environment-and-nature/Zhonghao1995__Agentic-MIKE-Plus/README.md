# Agentic MIKE+

**A headless, natural-language-driven, automated modelling workflow for MIKE+.**
**Skills + an MCP server** for [Claude Code](https://www.anthropic.com/claude-code), Codex, Hermes, or OpenClaw: describe a goal in plain language and the agent inspects, edits, runs, reads, and plots a MIKE+ model. Automated modelling and analysis, end to end, without ever opening the GUI.

<p>
  <a href="https://github.com/Zhonghao1995/Agentic-MIKE-Plus/actions/workflows/ci.yml"><img src="https://github.com/Zhonghao1995/Agentic-MIKE-Plus/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://glama.ai/mcp/servers/Zhonghao1995/Agentic-MIKE-Plus"><img src="https://glama.ai/mcp/servers/Zhonghao1995/Agentic-MIKE-Plus/badges/score.svg" alt="Glama score" /></a>
  <img src="https://img.shields.io/badge/python-3.11_x64-3776AB" alt="Python 3.11 x64" />
  <img src="https://img.shields.io/badge/MIKE%2B-2026-0a7d8c" alt="MIKE+ 2026" />
  <img src="https://img.shields.io/badge/MCP-1.28-7C3AED" alt="MCP 1.28" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT license" />
  <img src="https://img.shields.io/badge/status-experimental-orange" alt="experimental" />
</p>

> [!TIP]
> **Need a model to run? [SWMMCanada](https://github.com/Zhonghao1995/SWMMCanada) builds one anywhere in Canada.**
> It is the upstream, open-data model builder for this agentic workflow: draw an area on a map and it assembles a ready-to-run stormwater model from Canadian open data (real municipal storm networks for 8 cities, synthesized everywhere else), giving the agent a real network to run, edit, read, and plot. Try the hosted demo with no install at **[swmm.h2ox.me](https://swmm.h2ox.me/)**, or see the project at **[h2ox.me](https://www.h2ox.me/)**.

> Experimental / pre-release. One MCP server + skills wrapping DHI's Python stack (`mikeplus` / `mikeio` / `mikeio1d`). Verified end to end on the MIKE+ 2026 `Sirius_RTC` example. Sibling of [agentic-swmm-workflow](https://github.com/Zhonghao1995/agentic-swmm-workflow).

## Install: just tell your agent

It is the AI era. You don't wire this up by hand. Paste this to your AI coding agent (Claude Code, Codex, Hermes, OpenClaw):

```text
Install "Agentic MIKE+" for me: an MCP server + skills to drive MIKE+ headless.

1. Clone https://github.com/Zhonghao1995/Agentic-MIKE-Plus and skim its README.
2. With Python 3.11 x64 (mikeplus needs 3.9-3.11, not 3.12+):
     py -3.11 -m venv .venv
     .venv\Scripts\python.exe -m pip install -r requirements.lock
     .venv\Scripts\python.exe -m pip install -e ".[run]"
   (read/plot only, no license: drop the lock and use `pip install -e .`)
3. Register with me (Claude Code):
     claude mcp add mike-plus -- "<abs-repo>\.venv\Scripts\python.exe" -m mikeplus_mcp.server
   (Codex / Hermes / OpenClaw: copy config/mcp.sample.json)
4. Copy skills/* into ~/.claude/skills/, then run scripts/smoke_test.py (should find 18 tools).
5. Tell me the tools and which need a MIKE+ license (run/edit/import do; read/plot/compare don't).
```

Needs **Python 3.11 (x64)**. Two install profiles:

- **Read & plot.** License-free and cross-platform: `pip install -e .` (no `mikeplus`).
- **Run & edit too.** Windows + a licensed **MIKE+ 2026**: `pip install -e ".[run]"` (or `pip install -r requirements.lock` for the exact pinned environment).

`mikeplus` is an optional `[run]` extra, so teammates who only read results or make figures install nothing license-bound.

## Why it matters

- **Natural-language-driven.** Describe the task in plain words; the agent plans and runs it: no scripting, no GUI clicking. (A sub-agent did this autonomously.)
- **Fully headless.** Runs with no GUI, on a workstation, a server, in CI, or under an agent. Built for batch and scenario automation.
- **MCP-native and portable.** One server speaks the Model Context Protocol; works with **Claude Code, Codex, Hermes, or OpenClaw** via a single config line, and installs with pip.
- **Low barrier to share.** Reading results and plotting need no MIKE+ license; only running or editing does. Teammates analyse model output with nothing but `pip install`.
- **Reproducible & tested.** Deterministic tools, structured-JSON output, a pinned lockfile, and a license-free unit-test suite in CI, verified on a real model, not a chat-to-model black box.
- **Engine-agnostic and extensible.** Results use a common schema (ready to sit beside SWMM and LSTM); add a tool or skill by dropping in a file.

<p align="center">
  <img src="docs/figs/overview.png" alt="Agentic MIKE+ overview: agentic-workflow advantages, core functionality and tools, and which capabilities need a MIKE+ license" width="900" />
</p>

## How it works

Skills (markdown playbooks) tell the agent *when and how*; the agent calls **MCP tools**; each tool runs in an isolated **worker subprocess** that imports only `mikeplus` *or* `mikeio*`: the two cannot share a process. The server itself imports neither.

```
agent  ->  reads skills/*.md  ->  calls MCP tools  ->  workers (mikeplus / mikeio1d)
```

<p align="center">
  <img src="docs/figs/workflow.png" alt="From one plain-language sentence to a finished MIKE+ run, automatically and without the GUI" width="900" />
</p>

## Tools (one server, `mike-plus`)

| Tool | Does | License |
|---|---|---|
| `mike_model_info` | model overview: simulations, scenarios, model type, element counts | yes |
| `mike_set_scenario` | activate an existing scenario (verified by re-opening the model) | yes |
| `mike_get_values` / `mike_set_values` | read / change parameters (e.g. pipe diameter) | yes |
| `mike_run` | run a simulation headless, return `.res1d` + a parsed QA status (completed / errors / warnings) | yes |
| `mike_import_swmm` | import an EPA SWMM (or EPANET) `.inp` into a new MIKE+ model: the SWMMCanada bridge | yes |
| `mike_results_list` / `summary` / `read` | list contents / peaks / one time series | no |
| `mike_results_flooding` | which nodes flood: peak water level vs ground level, ranked | no |
| `mike_results_compare` | baseline vs scenario: delta peak / volume / timing, RMSE, NSE; or every element ranked by change | no |
| `mike_plot_rain_flow` / `timeseries` / `network` | stacked hydrograph / series / network map | no |
| `mike_plot_compare` / `mike_plot_profile` | overlay of two runs / longitudinal profile (bed, crown, ground, max water level) | no |
| `mike_rain_to_dfs0` | rainfall CSV to a MIKE+ `.dfs0` (intensity, read-back verified) | no |
| `mike_manifest_write` | provenance manifest: model, inputs, edits, run QA, results, figures, each with sha256 | no |

Ten skills orchestrate them: `mike-end-to-end` (the SOP: modes, run directory, stop rules, QA gates), `mike-model`, `mike-params`, `mike-runner`, `mike-import`, `mike-results`, `mike-compare`, `mike-plot`, `mike-rain`, `mike-audit`.

**Install the skills** into any skills-aware agent (Claude Code, Codex, OpenCode, …) in one command, no clone needed:

```bash
npx skills add Zhonghao1995/Agentic-MIKE-Plus      # all 10; add --list to preview, or --skill <name> for one
```

## Demo: `Sirius_RTC` (MIKE 1D, 568 nodes, 576 links)

<p align="center">
  <img src="docs/figs/sirius_rtc_network.png" alt="Sirius_RTC network layout" width="900" />
</p>
<p align="center">
  <img src="docs/figs/sirius_rtc_rain_flow.png" alt="Rainfall-runoff hydrograph for the busiest pipe" width="900" />
</p>

Full evidence (commands, outputs, and the honest license boundary) is in **[docs/verification.md](docs/verification.md)**.

## Development

The engine-agnostic core is covered by a **license-free** test suite (no MIKE+ / `mikeplus` needed) that also runs in CI:

```bash
pip install -e .            # read/plot core (add ".[run]" for run/edit)
pip install pytest
pytest                      # ~0.5 s, no license required
```

The tests pin the result schema, the res1d column matcher, the engine-log QA parser, the compare / rain / manifest / SWMM-inp helpers, and tool discovery, so a change can't silently break them. Add a tool or skill by dropping a file under `mikeplus_mcp/tools/` or `skills/` (auto-discovered), and ship a test with it.

## License

MIT © 2026 Zhonghao Zhang, University of Victoria. Built on DHI's `mikeplus` / `mikeio` / `mikeio1d` and the Model Context Protocol. MIKE+ is a product of DHI; running models requires a valid DHI license.
