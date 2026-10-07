# Training coverage beyond release-v2

Audit: 2026-09-20 01:49 UTC, checkout
`e7522225d4a73b790b87a2cd3c837df17c7bede4`.

**The largest missing dedicated training families are browser actions,
partially observed tactical control, and stateful catalog/menu games.** Their
five community adapters have no dedicated rows in release-v2. This ranking
prioritizes verified public demo contracts that already have local request
builders. It is not an exhaustive survey of X or evidence that another task is
unimportant.

This audit uses [the pinned public source inventory](public-capabilities.md),
the [release-v2 report](../reports/data-manifests/release-v2.json), local data
cards, and counts from the five release-v2 split files. All five file hashes
match the report. The report's own SHA-256 is
`56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97`.
No JF100 item, question, state, or label was read for this audit. Frozen data and
active training configurations were not changed. The initial
[browser snapshot controls](browser-data.md) now provide a separate corpus;
[drone snapshot controls](drone-data.md) now supply another. The broader
application simulators proposed below remain future work.

## What is actually in the training split

Release-v2 contains **80,816 training rows**, out of 115,821 rows across all
splits. The report's per-source totals include evaluation splits; they must
not be reported as training counts. The broad `metadata.family` values such as
`policy` also combine unrelated applications, so source IDs are used here.

| Public task / local source | Train rows | Train groups | What those rows teach |
| --- | ---: | ---: | --- |
| Customer-context controls: `customer-control-v1` | 4,206 | 701 | Six local customer judgments from controlled scenarios; not the recovered private launch query |
| Customer service: `workflow-controls-v1/customer_service` | 4,392 | 183 | Independent policy labels, one Noul per action, including consent/counterfactual controls |
| Security incidents: `workflow-controls-v1/security_incidents` | 8,874 | 174 | Simplified local disposition/authorization policy |
| Agent traces: `workflow-controls-v1/agent_trace_observability` | 3,780 | 180 | Local evidence and permission rules; not arbitrary semantic task-completion judgment |
| Invoices: `workflow-controls-v1/invoice_processing` | 5,370 | 179 | Local accounting/approval rules over generated records |
| Painting: `painting-geometry-v1` | 23,552 | 46 | Pixels of exact rectangles/circles through four output forms; not free-form artistic composition |
| Snake: `snake-v1` | 12,508 | 3,127 | Visible-state heuristic action and exact immediate-collision labels |
| Mario-style proxy: `tile_platformer-v1` | 1,346 | 63 | Original tile terrain/physics and a single combined action Choice |
| T-Rex-style proxy: `trex_runner-v1` | 28 | 28 | The local runner's very small finite observation space and combined action Choice |
| Doom: `vizdoom-basic-v1` | 6,354 | 309 | ViZDoom basic movement Choice, attack Noul, alignment Score |
| Wikiracing: `wikispeedia-v1` | 1,700 | 224 | Independent BFS-derived labels on an externally sourced frozen graph; targets are grouping units |
| Reasoning/verification: `reasoning-control-v1` | 5,442 | 1,814 | Seven independently generated exact reasoning families |
| Additional control: `tic_tac_toe-v1` | 3,264 | 452 | Exact minimax; not a verified Jev launch demo |

Groups have different meanings across sources: a painting scene supplies many
pixels; a Doom group is an episode; a workflow parent supplies several
counterfactual cases and action questions. They are not interchangeable units
of diversity. These counts establish data availability, not checkpoint
competence or proof that every row was visited during a bounded training run.

The workflow forms are documented in [workflows.md](workflows.md), game labels
and split limits in [games.md](games.md), painting in
[painting.md](painting.md), and exact reasoning controls in
[reasoning-data.md](reasoning-data.md). Wikispeedia is not wholly synthetic:
[its data card](wikiracing-case.md) records the external graph provenance and
the absence of a separately verified archive redistribution license.

### T-Rex finite-state diagnosis

A separate [training-only audit](../reports/data-manifests/trex-training-coverage.json)
confirms that the local runner has nine obstacle configurations at four speeds:
36 distinct visible states in total, of which 28 are assigned to training.
Those same 28 rows are preserved in release-v2 and the active browser/drone
expansion. More seeds or episodes cannot expand this observation space.

The training labels choose `jump_full` 20 times, `jump_short` twice, `duck`
twice and `keep_running` four times. Under the local collision function,
`jump_full` is safe for all 28 training states; 11 states admit multiple safe
actions. The one-hot labels therefore teach the declared teacher preference,
not the complete set of safe actions. All states use fixed geometry and
`normal/running` mode. This diagnosis does not establish the cause of a model's
held-out errors.

The browser adapter uses a three-way `maneuver` and a conditional two-way
`jump_profile`, whereas these training rows use one combined four-way Choice.
A future, separately versioned corpus could adapt the existing training states
to that contract, yielding 56 task rows but still only 28 states. Broader physics
coverage requires independently collected or generated dynamic states and
trajectories. Neither change has been made to the active frozen corpus.

## Verified surfaces with no dedicated training source in release-v2

| Verified public family | Current local evidence | Training gap |
| --- | --- | --- |
| [Browser Use Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) | Observed DOM IDs, operation/target/value request builder, stale-snapshot validation; separate snapshot action corpus now available | No browser data in release-v2; no multi-step DOM trajectories, browser executor, or independent completion evaluation |
| [HEIST//ONE](https://github.com/AbdelStark/heist-one) | Per-guard threat, suspicion, intent and observed-target adapter | No local guard simulation, partial-observation trajectories, or tactical training labels |
| [Jev drone](https://github.com/RomanSlack/jev-drone) | Maneuver/risk/target-loss adapter and explicit climb-clearance requirement; separate synthetic snapshot corpus | No drone data in release-v2; no perception/control trajectories or simulator outcome labels |
| [JevScape](https://github.com/Skyvern-AI/jevscape) | Catalog action, immediate tick action and poll-interval adapter | No skill/inventory/dialog trajectories or timing-policy labels |
| [Pokémon Red](https://github.com/valentynkit/jev-plays-pokemon-red) | Legal action and per-candidate faint-forecast adapter | No battle/menu/navigation episodes or outcome labels |
| Harsha's code-security / tariff workloads | Four-field security example and a 255-option synthetic catalog example | No dedicated vulnerability labels or nontrivial 255-class catalog training |
| Harsha's fraud / 28-field support workloads | Independently authored request examples | Related policy/support data exist, but no dedicated four-field fraud or 28-field support corpus; no operational records |
| Official semantic retrieval/ranking and structured extraction | General primitives and import infrastructure | No dedicated semantic retrieval or document-extraction training source in this mixture |

[community.md](community.md) explicitly labels the first five forms as adapters.
Release-v2 contains no dedicated training source or full-game evaluation for
them; the separate browser and drone corpora cover snapshot decisions. The checked-in JSON requests
are inference examples, not supervised training datasets. A model successfully
answering their schema smoke checks does not close these gaps.

## Priority 1: grounded browser decisions

The initial `browser-control-v1` build has 21,980 supervised records across all
splits, including 13,814 train records from 631 parent scenes. It covers finite
snapshot widget decisions and has not entered release-v2. It supplies neither
the multi-step executor nor the task-completion evaluation proposed below.

**Proposed next corpus (new version):** generated from original local pages
and finite application state machines. Start with search/filter/detail,
dropdown selection, forms using caller-supplied text candidates, pagination,
and asynchronous wait/completion. No live accounts or external websites are
needed.

Use the exact input from `browser_request`: caller goal, visible DOM element
table, current snapshot, and finite text candidates. Generate page layouts,
labels, record values, and element IDs independently. The target operation
comes from a shortest successful plan over the small application graph; keep
only states where the plan's next decision is determined by visible information.
An alternative shortest action can be accepted as another optimal action rather
than labeled wrong. Train target/value fan-outs only when their conditional
question has a defined answer; do not invent labels for irrelevant branches.

The current adapter trusts each element's `actions` list; a copied `disabled`
flag alone does not prevent offering that element. Disabled or inaccessible
elements must therefore have no offered actions, and the executor must recheck
availability. The API permits one-candidate Choices but the training validator
requires at least two: omit and count forced single-candidate supervised heads
without modifying the runtime request or inventing distractors. Map labels via
`compile_request` answer keys, retain exact rendered model inputs, and keep
oracle answers solely in metadata or the separate case/evaluation file.

**Minimal generation target:** 1,000 distinct task/layout groups, capped at
12 observed decisions per task. Reserve complete templates/layouts and their
trajectories together; ID splits use 70/10/10/10 by group, with another 200
groups from separate OOD layout/template generators. All variants of the same
application and task stay together. Deduplicate exact observations before
reporting counts.

**Evaluation target:** 100 fixed ID tasks and 100 fixed OOD tasks in the local
executor, at most 15 actions each. Report independently checked goal success,
premature `DONE`, incompatible targets, stale-proposal rejections, and action
count, with paired random/teacher baselines. Stale-snapshot rejection is a
software check and must be reported separately from model accuracy. This would
establish bounded browser-task evidence, not arbitrary-browser competence.

## Priority 2: partial-observation tactical control

The separate `drone-control-v1` corpus now contains 25,249 supervised records,
including 15,694 train records, from 500 parent scenes. It supplies disclosed
snapshot geometry/evidence labels, without executed trajectories or outcome
measurements, and has not entered release-v2.

**Proposed trajectory corpora:** `guard-control-v1` and a future version of
the drone controls. Start with
original deterministic grid/kinematic simulators, not source code or media from
the community projects. They are controlled proxies for the HEIST and drone
contracts, not a claim to reproduce their complete engines.

For guards, generate rooms, occlusion, visible entities and event histories;
feed only one guard's local evidence through `heist_request`. Include the local
evidence rubric in observations. Derive threat/suspicion labels from that rubric,
and intent/target labels from visible evidence. An intruder behind an unobserved
wall must not turn identical visible observations into contradictory supervised
labels. Hidden world state can determine episode outcomes, not the input-only
classification oracle.

For drones, generate measured obstacle gaps, relative motion, altitude limits,
clearance and target-visibility history through `drone_request`. A disclosed
kinematic model supplies clearance/time-to-collision risk bins and maneuver
labels; a disclosed observation policy defines when target loss is supported.
Do not treat an occlusion timer as proof of an unobserved physical event. Keep
the controller's collision reflex and raw model maneuver separate.

**Minimal generation target:** 500 independent scene/episode groups per
simulator, at most 20 observations per episode, collected with both teacher and
seeded random actions. Partition whole layouts and episodes, with separate OOD
geometry, speeds, and occlusion durations; do not split adjacent frames into
different partitions. Omit duplicated or unanswerable observation labels.

**Evaluation target:** 100 fixed ID and 100 fixed OOD episodes per simulator,
reporting collision/detection/false-alarm outcomes as applicable, progress,
reflex interventions, and primitive label metrics. Score raw choices as well as
executed choices so a controller cannot conceal a poor policy. These exact-rule
targets do not establish calibrated real-world risk or real-aircraft ability.

## Priority 3: stateful catalog and menu games

**Proposed corpora:** `catalog-rpg-v1` and `battle-menu-v1`, using original small
resource-gathering and turn-based battle environments. Reuse the RuneScape and
Pokémon adapter shapes, but no ROM, commercial game state, upstream assets, or
undocumented game implementation is required.

The catalog environment should include gather/process/sell cycles, inventory
limits, interrupted actions, food/health, dialogs and visible action deadlines.
Supervise next catalog action, immediate tick action, and poll interval. Define
poll targets from an explicit observable deadline/cost rule rather than an
arbitrary label or hidden future event.

The battle environment should expose player/opponent stats, a finite menu and
legal actions. Exact independently implemented damage transitions provide
per-candidate faint labels; a small dynamic program supplies action targets for
the stated goal. Begin with deterministic mechanics. If stochastic outcomes are
added, derive targets by an exact outcome distribution or recorded repeated
trials rather than assigning made-up confidence values.

**Minimal generation target:** 500 independent quest/battle groups for each
environment, capped at 20 decisions per episode. Group all menu states,
counterfactual actions and combat variants of one scenario together. Hold out
catalog compositions, map layouts and opponent configurations, not only RNG
seeds. Keep nominal IDs independent of target labels.

**Evaluation target:** 100 fixed ID and 100 fixed OOD episodes for each engine.
Report objective completion, return, invalid actions, decisions/polls per
completed objective, and battle-faint forecast Brier score alongside calibration
coverage. These results would support the original proxy tasks; playing the
actual RuneScape or Pokémon game still requires a lawful environment integration
and separate evaluation.

## Important gaps outside these three priorities

- **Existing game representations:** Doom now has an explicit `typed-v1` runtime
  matching its training movement Choice, attack Noul and alignment Score. The
  default `combined-v1` and its historical evaluation evidence remain separate;
  new typed-mode model rollouts are still needed. See [games.md](games.md).
  Original Mario/T-Rex adapters still differ from the local training runtimes.
  T-Rex has only four test observations and no OOD data. More repeated seeds
  cannot enlarge its 36-state observation space; expand the declared simulator
  and create a separately versioned corpus if broader coverage is wanted.
- **Specialized classification:** the 801 training code-semantics rows are
  restricted arithmetic/program execution, not vulnerability analysis. A next
  security corpus could use original source/sink/sanitizer templates plus an
  independent taint interpreter. A 255-choice catalog corpus should require
  matching described product attributes to a generated taxonomy, not merely
  repeat an explicit correct class ID. Neither would establish real customs or
  broad code-review competence.
- **Customer language and judgment:** customer-control metadata marks 3,606
  training rows `en` and 600 `en+zh`; this is narrow controlled wording, not
  broad multilingual data. Workflow sources still lack arbitrary human wording,
  subjective disagreement labels and full operational trajectories. Realistic
  text and calibrated uncertainty require separate reviewed sources or original
  annotation work.
- **Painting and context:** 46 training scenes cannot support a claim of rich
  prompt-to-art composition. Longer distractor-rich application inputs also
  need independent generation and a declared context-capacity protocol; changing
  the service input limit alone is not new training coverage. The PlayJev visual
  model is a separate community extension, with no corresponding visual training
  source in release-v2.

The counts above and proposed quotas must remain separate in release claims.
Any new corpus should have its own generator, provenance, grouped split hashes,
independent oracle checks and immutable evaluation protocol before entering a
new mixture version. Fixed current runs remain reproducible; no automatic merge
into release-v2 or use of external benchmark labels is proposed here.
