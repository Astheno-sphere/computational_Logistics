# Example — Sirius_RTC

The verification case used throughout this project is **Sirius_RTC**, a
collection-system model **bundled with MIKE+** (DHI) under the installation's
`Examples/CS, Rivers, 2D/Sirius RTC/` folder.

- Engine: MIKE 1D (collection system, `CS_MIKE1D`)
- Size: **568 nodes, 576 links, 863 catchments**
- Features: real-time-control (RTC) rules, pumps/weirs/orifices to a WWTP, a
  1-year CDS (Chicago) design storm
- Active simulation: `Rainfall_CDS_1yearHD`

## Model files are not included

DHI's example model files (`*.sqlite`, `*.mupp`, `*.dfs0`, `*.res1d`) ship with
every MIKE+ install and are **not redistributed in this repository**. The figures
under [`docs/figs/`](../../docs/figs/) are derived visualisations of this example
(credit: DHI MIKE+ examples).

## Reproduce

1. Copy the example folder to a writable working location (always work on a copy —
   `mikeplus` has no undo):
   ```
   <MIKE+ install>\Examples\CS, Rivers, 2D\Sirius RTC\   ->   <your working copy>\
   ```
2. Point the tools at the copied `Sirius_RTC.sqlite`, e.g.:
   ```
   python scripts/call_tool.py mike_model_info "{\"sqlite\": \"<copy>/Sirius_RTC.sqlite\"}"
   ```
3. Or describe the task in natural language to an MCP-connected agent — see
   [docs/verification.md](../../docs/verification.md) for the full walkthrough.
