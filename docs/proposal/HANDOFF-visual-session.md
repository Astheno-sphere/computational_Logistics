# Handoff: the visual-skills session (2026-10-13 to 2026-10-19)

For another Claude conversation. Read this first; it replaces reading the session. Branch:
`claude/lucid-galileo-3ss28v`. Session link (private, owner only): https://claude.ai/code/session_01R9GhGBszoaVuMnZFy7dzXb

## Standing rules from Arshad
- Save tokens. Do not load skills or tools that are not needed. Do not install unless told; installs go in a venv.
- HTML first, never PDF unless asked. No em dashes. Numbers must trace to the repo; never invent them.
- Figures follow TRAIL.md: each plate shows what only our work produced, and its title names the finding.

## What was built (all pushed on the branch)
| File | What |
|---|---|
| `skills/visual-narrative/reference/motion-plate-spec.md` | Layout, type, colour and motion rules measured from one 30 s reference video |
| `skills/visual-narrative/reference/cd-skills-map.md` | Which of Bhardwaj's 18 Computational Design skills to load for which plate job |
| `docs/proposal/make_motion.py`, `motion.json`, `src/motion.js` | Plate A: 60 futures (study.json) and 1,000 commuters on the Molde and Kristiansund networks, no policy then P12 |
| `docs/proposal/plate-a.html` | Plate A on its own page |
| `docs/proposal/src/a3v4.html` + `build.py` | Plate A as a screen-only exhibit after sheet 5 of `proposal-v4.html`, hidden in print |
| `tests/test_motion.py` | Checks motion.json against study.json (4 and 41 of 60 futures) |
| `docs/proposal/TRAIL.md` | One decision row added |

v4.5 (`claude/clever-bell-tctxe3`) was merged into this branch. 89 tests pass in a venv.
`origin/main` moved on 14 Oct (Swissmetro evidence, two-engine fidelity benchmark) and `origin/matsim-bridge` exists. Neither is merged here.

## Findings
- Bhardwaj's repo (Claude-skills-for-Computational-Designers, MIT) is knowledge plus 7 calculators for AEC design. It holds no graphic style and no fluid solver.
- The pasted `abhinav-poster-style` skill is a static poster system. v4.5 already uses its house tokens: sage good, amber moderate, red fails, teal free alternative, cream text. It has no motion grammar; `motion-plate-spec.md` covers that.
- Plate A deviates from that skill in four ways: no labelled palette-chip strip, no spec box of real parameters, no "Source:" line, kicker not lowercase italic.
- The five-plate spec (P1 to P5) is the Stage D brief for plates v4.5 already names. Build P3 and P5 first: they come straight from model data.

## Number check on the five-plate spec
Confirmed: tariff NOK 34 / 27.20 / 19.04 (30% less); Swissmetro final log-likelihood -5214.875 (evidence/dcm-swissmetro on main); fast engine within 15-16% MAPE (main only).
Wrong as written: P4 "48% of trips can avoid both stations". The repo's 48% is "48% of junction pairs lose every road connection" when the Kristiansund graph splits at the bridge. The share of trips that avoid both stations is still the placeholder `[N1]`, to be counted in A1.
Unverified: "road-to-sea corridor, heavy-vehicle signpost fires first"; the symbols rho and lambda against equation 2; "10^3 futures" against make_mc.py.

## Known issues and open items
- Arshad saw Plate A with no animation. Likely the reduce-motion check in `src/motion.js`, or the viewer not running the animation timer. Not reproduced; only stills were checked.
- `standalone.html` is stale (older long proposal). The old `src/proposal.html` still carries an earlier Plate A.
- Four of the five A3 sheets measure slightly taller than their frames offline; identical in the untouched v4.5 build, probably the web font not loading.
- Open choices: oxblood `#2E151C` versus v4.5 charcoal `#16120F`; Montserrat versus Inter for titles; which wording for the P4 callout.
- Arshad will supply: five reference images, the "self-discovery" findings, and v4.5 changes. None received yet.

## Environment
Venv with all dependencies: `/tmp/claude-0/-home-user-computational-Logistics/4a037f22-dfdf-5433-87d5-b0986551c2d1/scratchpad/venv` (session scratch, may not persist). Chromium at `/opt/pw-browsers/chromium`; Playwright is installed without browsers. Bhardwaj repo cloned read-only at `/home/user/abhinavbwj/claude-skills-for-computational-designers`.

## Update 2026-10-20: the v5.5 build
- `docs/proposal/proposal-v5.5.html` is now generated: edit `src/proposal-v55.html`, then run `python docs/proposal/build_v55.py`. Do not edit the output by hand; `v5.5-content.md` is no longer the source.
- Plates P1 to P5 are the computed plates already in `docs/proposal/plates` (answers, engine, memory, halves, front), re-toned by the build. The 25-package plate `p5-robust-front.svg` (older ensemble, 60 futures) is not used on the page.
- Open items kept open on purpose: `[N1]` (share of trips avoiding both stations, counted in A1) and five `[to confirm]` markers (references and the AI-use wording).
- Print: A3 portrait, margins none, background graphics on. Checked: 8 pages (5 body, references, 2 supplement sheets).
- Checks that cannot be done offline: Overpass and Google Fonts are blocked in the sandbox; fonts are embedded for that reason.
