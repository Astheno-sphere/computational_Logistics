# STATE v5.6 — latest, 2026-10-20

Branch `claude/lucid-galileo-3ss28v` @ `6712b76`. Build files in `docs/proposal/v56/`. Nothing deleted.

## 1. Proposal build status (per page)

| Page | Title | Text | Figure(s) | Figure status | Integrity tier | Editable JSON |
|---|---|---|---|---|---|---|
| **1** | What an equilibrium cannot carry | ✓ final | Fig 1a *One place, three moments* · Fig 1b *What a crossing earns* | 1b ✓ built · **1a rebuilding on real OSM map** | exposure REAL · fleet/revenue PROTOTYPE | fig1.json (pending) |
| **2** | A dynamic layer beside the national models | ✓ final | Fig 2 *One network, the layers it must carry* | **rebuilding on real OSM map** (faithful) | network REAL · choice/acceptance TO-ESTIMATE · fleet/rev PROTOTYPE | fig2.json (pending) |
| **3** | What each agent decides and remembers | ✓ final | Fig 3 *What memory does* (3-agent trajectories) | keep existing good plate → make JSON-driven | ILLUSTRATIVE | fig3.json (pending) |
| **4** | Kristiansund, where acceptance is live | ✓ final | Fig 4 *The toll is a map of who can avoid it* | ✓ **done** (real OSM map) | REAL | raster (real map) |
| **5** | The robust front, and the stack behind it | ✓ final | Fig 5a *Robust front* · Fig 5b *erosion fan* · Tools columns | **5a ✓ DONE (faithful, JSON)** · 5b pending · tools ✓ (demo) | 5a PROTOTYPE · tools REAL | robustfront.json ✓ |
| **6** | References | ✓ verified | — | — | — | — |

## 2. Figure ledger (the five posters → our figures)

| Our figure | Your poster (grammar) | Status | Quality bar |
|---|---|---|---|
| **The robust front** | Evolutionary optimization (NSGA-II) | ✓ **DONE** | faithful rebuild, our data, JSON-driven ✓ |
| What a crossing earns | Energy calculator readout | ✓ built | good; to JSON-ify |
| One place, three moments | Ride-hailing demand (hex × time) | rebuilding | on real Kristiansund map base |
| One network, the layers | Seven predictions stacked | rebuilding | on real OSM map base |
| What memory does | (our own trajectory plate) | keep | already proposal-grade |
| Kristiansund toll map | (our own OSM render) | ✓ done | real cartography |
| Tools columns | — | ✓ built | 5 columns, Rhino/Grasshopper honest |

## 3. Integrity / open items

| Item | Status |
|---|---|
| Four-tier labelling (REAL / PROTOTYPE / ILLUSTRATIVE / PLACEHOLDER) | ✓ rule set, applied |
| Swissmetro reference | ✓ fixed to ≈ −5214.8 (ours −5214.9) |
| 904 = four of five instruments | ✓ fixed (perm(4,k)·3^(k−1)) |
| Test count | **89** now (recount at the submission tag) |
| `[N1]` trip-avoidance share | open placeholder — counted in A1 |
| Führer volume | `[to confirm]` from DOI |
| "estimated" never attached to acceptance | ✓ enforced |

## 4. What's left to COMPLETE the proposal

1. Build **Fig 1a** (one place, three moments) and **Fig 2** (layer stack) on the real OSM map — faithful, to the robust-front bar.
2. Make **Fig 3** (what memory does) and **Fig 1b** JSON-driven.
3. Build **Fig 5b** (erosion fan).
4. **Assemble** the five pages + references into one HTML proposal, figures dropped into place.
5. Guided `main` **README** (repo tour) + **one PR into main** + tag the submission. Delete nothing.

## 5. Next task after the proposal
**Cover letter.** (Queued — begins once the proposal is complete.)
