# BLUEPRINT v5.6 — the whole proposal in one table

**Principle (non-negotiable): no flex.** Every figure is titled and captioned in OUR words and shows OUR data. The Abhinav posters are reused as visual *grammar* only — rebuilt with Kristiansund, pathway and tariff numbers. Nothing appears as "prior work" or portfolio. If a figure cannot honestly carry our content, it is dropped, not relabelled.

## A. Page-by-page blueprint

| Page | Title (kicker / headline) | What the page argues | Figure(s) — OUR title · what it shows and the depth it adds | Tools & Git on the page |
|---|---|---|---|---|
| **1** | 01 · THE PROBLEM / **What an equilibrium cannot carry** | Equilibrium models answer "what 2050," never "how we get there"; and the toll base is already eroding, measured. | **Fig 1a "One place, three moments"** (hex/zone grammar ← demand poster): Kristiansund zones at 2026 / 2035 / 2050, each shaded by estimated acceptance and electric share — the same place becoming a path, holding in some zones, eroding where the discount bites. *Depth:* names the three things an equilibrium cannot hold — fleet turns over slowly, acceptance carries (ρ), debt is due on a schedule. · **Fig 1b "What a crossing earns"** (calculator-readout grammar ← energy poster): the tariff erosion as a line-by-line readout — 27.20 tag → 19.04 zero-emission = −30% per electric crossing, against unchanged debt. *Depth:* turns the headline number into arithmetic the panel can check. | repo link in footer; `[N1]` shown honestly as "counted in A1" |
| **2** | 02 · FIT, GAP / **A dynamic layer beside the national models** | Names NTM6, RTM, NGM, tramodsim; places the PhD inside TØI's own programme; states the gap nobody has filled. | **Fig 2 "One network, the layers it must carry"** (stacked-strips grammar ← seven-predictions poster): one Kristiansund street graph, strips = DATA · CHOICE (DCM) · ACCEPTANCE (ABM) · FLEET · EMISSIONS · REVENUE · FREIGHT, each tagged with its article and tool. *Depth:* shows the dynamic layer as strata that the equilibrium collapses into one number. | each strip tagged with its tool (Biogeme, EMA, OSMnx, NGM) |
| **3** | 03 · THE MODEL / **What each agent decides and remembers** | The equations (1)–(3); acceptance estimated first, then carried; what would falsify it. | **Fig 3 "What memory does"** (OUR existing trajectory plate, kept — it is already proposal-grade): three agents' acceptance 2026→2050 with ρ labels and the λ line they cross or hold. *Depth:* footer in plain words — "acceptance next year = memory of last year + what you pay + what you were told." | Biogeme named; the one honesty paragraph lives here (Swissmetro −5214.9 vs ≈−5214.8) |
| **4** | 04 · CASE / **Kristiansund, where acceptance is live** | A real town charging since June 2026; where freight enters; the survey and hypotheses. | **Fig 4 "The toll is a map of who can avoid it"** (the REAL OSM map, kept — best plate in the set): zones by toll exposure, three traced trips, the freight corridor, callouts. *Depth:* 48% connectivity split at the bridge, the toll-free tunnel, `[N1]`. · *(optional)* **Fig 4b "The town as the model sees it"** (isometric + Grasshopper-node grammar ← Ladybug poster): Kristiansund massing with the two stations — signals the parametric pipeline. Optional; cut if the page is tight. | OSMnx · NetworkX named |
| **5** | 05 · PLAN / **The robust front, and the stack behind it** | A3 is a search; robustness over regret; finishes in three years; receipts for every number. | **Fig 5a "The robust front"** (Pareto grammar ← evolutionary-optimization poster; BUILT): acceptance margin × futures-on-target, pathways A–E, E chosen (widest λ it survives). *Depth:* y = the largest rise in the threshold a path survives, reported as a result. · **Fig 5b "What replaces the lost revenue"** (erosion fan, kept): revenue ÷ debt across 1,000 futures, 22% fail before 2041. · **THE TOOLS COLUMNS** (five, see Table C). | Tools columns here; "89 tests, every number traces to a commit"; repo link; submission tagged |
| **6** | REFERENCES | — | none | full bibliography; evidence commit hashes |

## B. Image reuse map (grammar in → our content out)

| Your poster (grammar) | Becomes — OUR figure | Page | Our data / labels on it | Honest basis for the reuse |
|---|---|---|---|---|
| Evolutionary optimization (NSGA-II Pareto) | **The robust front** | 5 | acceptance margin × futures-on-target; pathways A–E; ε-NSGA-II convergence | MORDM *is* a many-objective evolutionary search — this is the correct picture of our method, not decoration |
| Seven predictions stacked (one graph, N layers) | **One network, the layers it must carry** | 2 | our model's layers over the Kristiansund graph | the grammar is "one street network, many layers"; the layers are ours |
| Ride-hailing demand (hex zones over 3 times) | **One place, three moments** | 1 | Kristiansund zones, acceptance + electric share at 2026/2035/2050 | our prototype ABM output; any not-yet-estimated value is marked illustrative |
| Energy calculator (readout panel + section) | **What a crossing earns** | 1 | Vegamot tariff erosion; revenue vs debt | our real tariff numbers run through the same readout form |
| Ladybug sun-path (isometric + node) | **The town as the model sees it** *(optional)* | 4 | isometric Kristiansund + the two stations | reuse of the isometric + Grasshopper-node grammar only; dropped if space is tight |

## C. The tools columns (printed as five columns, page 5)

| ESTIMATE | EXPLORE | NETWORK | FREIGHT | COMPOSE |
|---|---|---|---|---|
| **Biogeme** — mixed logit · ICLV | **EMA Workbench** — ε-NSGA-II · PRIM | **OSMnx · NetworkX** — OR-Tools · MATSim | **NGM** — national freight model | **Rhino · Grasshopper** — Ladybug · Blender |
| acceptance and carrier mode choice estimated on real survey data, not assumed | 1,000 futures, robust search, scenario discovery where the robust set breaks (MORDM) | real road graphs, routing checks, and a dynamic cross-check the fast engine is measured against | commodity chains, mode split, class load factors and empty running carried to the network | every figure computed from the data, geo-referenced and drawn in one parametric pipeline |
| A1 · A2 | A3 | A1 · A3 | A3 | all plates |

The COMPOSE column is honest: the figures were composed in Rhino + Grasshopper (+ Ladybug), so the proposal names those tools. No person is named — tools only.

## D. Git — how the repo carries the proposal
- **Footer on every page:** `github.com/Astheno-sphere/computational_logistics`.
- **Page 5 receipts line:** "89 automated tests; every number traces to a tagged commit" (recount at the tag; the build has shown 87/89/92 — settle on one).
- **Guided `main` README** (separate from the sheets): one-paragraph pitch + proposal link; a "start here" table (proposal · evidence · skills · plates); three runnable evidence bullets (Swissmetro LL −5214.9, static fidelity ~15%, MATSim dynamic ~19% / breaks under congestion); the skills list; the test badge.
- **Assembly:** build v5.6 on a branch off `lucid-galileo` (e.g. `v5.6-plates`), one PR into `main`, tag the submission commit. Delete nothing; every branch and plate stays.

## E. What changed from the uploaded v5.5 build
- Eight sheets → **five pages + references** (the two "supplement" sheets fold into the body).
- The muddy twin-city isometric is **dropped**; the four posters are **re-titled into our figures** (Table B), not shown as portfolio.
- Leaked build-notes, the hex-swatch legend, truncated labels — **stripped**.
- Prose cut ~40% back toward ~2,900 words; no triple-stating.
- Rhino/Grasshopper now named honestly in COMPOSE.
