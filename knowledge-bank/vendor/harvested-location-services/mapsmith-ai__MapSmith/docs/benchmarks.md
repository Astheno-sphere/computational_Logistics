# Does plan validation help GIS agents? An A/B on GABench

MapSmith's core bet is that agents fail at geoprocessing less because they
"don't know GIS" and more because they hallucinate interfaces: tools that do
not exist, arguments that were never declared, values of the wrong type.
`validate_plan` exists to catch all of that *before* anything runs. This page
measures that idea on a third-party benchmark, with a deterministic evaluator
— no LLM judging an LLM.

## Setup

- **Benchmark**: [GABench](https://github.com/GeoX-Lab/GABench) — 57 executable
  GIS analysis tasks (urban heat, flood risk, burn scars, transit equity…)
  over a 133-tool MCP server, with expert reference toolchains. GABench is
  used unmodified; its evaluator runs unchanged on our logs. (We publish our
  *results* and our own harness code and link to their repository rather than
  redistributing it. GABench shipped no license file when this was written;
  we asked, and on 2026-09-03 they added Apache-2.0 —
  [GeoX-Lab/GABench#2](https://github.com/GeoX-Lab/GABench/issues/2).)

  **Cite GABench itself, not us**: Bo Yu, Cheng Yang, Dongyang Hou, Chengfu Liu,
  Jiayao Liu, Chi Wang, Zhiming Zhang, Haifeng Li and Wentao Yang,
  *GeoAgentBench: A Dynamic Execution Benchmark for Tool-Augmented Agents in
  Spatial Analysis*, arXiv:2604.13888, 15 April 2026
  ([doi:10.48550/arXiv.2604.13888](https://doi.org/10.48550/arXiv.2604.13888)).

  **Their counts and ours differ, and both are stated rather than quietly
  reconciled.** The paper describes 117 atomic tools and 53 tasks across 6 GIS
  domains. The checkout we ran in August 2026 served **133** tools and **57**
  tasks, and those are the numbers used throughout this page: the 133 is the set
  the extension-rule figure below is taken over, and the 57 is the task range our
  four A/B runs covered (ids reach 56, of which 48 passed plan validation in all
  four). We have not established which of the two describes the repository as it
  stands today, and we are not going to guess -- a reader comparing this page
  with the paper meets the difference here instead of finding it.
- **Agent**: GABench's own plan-and-react architecture, with one change kept
  identical across every arm: the planner emits a **typed plan** — a JSON
  list of `{step_id, tool, arguments}` — instead of prose, and the solver's
  system prompt embeds compact tool signatures instead of raw tool objects
  (~26k chars instead of ~148k; declared methodology change, applied to all
  arms).

  **What that compression costs, found later and worth knowing before reading
  any number on this page**: the compact signature keeps a tool's name, typed
  arguments and the first line of its description, which drops the `Args:`
  section — and that is where the per-argument rules live, such as
  `output_name: Output filename (must end with .tif)`. Measured on the live
  registry: **86 of the 133 tools state an extension rule that the compact form
  throws away** (25,441 characters against 77,937 for the full descriptions).
  So neither planner nor solver was ever told those rules. It applies
  identically to every arm, so the comparisons hold; but part of the absolute
  failure rate below is ours, and
  more importantly it is *one concrete piece* of the information an improvising
  solver recovers from error messages and an enforced plan cannot. Separating
  "the model cannot plan this" from "we never told it the rules" needed a run
  with the full argument documentation: that is [arm E](#arms-d-and-e-a-gate-that-knows-the-data-flow-and-a-prompt-we-broke-ourselves),
  and it is the one arm on this page that moved a metric past its noise floor.
- **Models**: `claude-sonnet-5` and `claude-haiku-4-5` — planner and solver
  are the same model within a run. The second model tests the obvious
  hypothesis: a smaller model writes dirtier plans, so validation should
  help it more.
- **The single experimental variable**:
  - **Arm A** — the typed plan goes straight to the solver.
  - **Arm B** — the typed plan is first validated statically against the live
    tool registry (unknown tool with did-you-mean suggestions, missing /
    unknown / mistyped arguments, malformed steps). Machine-readable errors
    go back to the planner, which repairs the plan — at most 2 rounds — and
    only then the solver runs. This mirrors MapSmith's `validate_plan`
    error-code design.
- **Hygiene**: the tool output directory is wiped before every task (no
  cross-task artifact reuse); every task's artifacts are archived for the
  physical-output checks; results use GABench's history format so
  `evaluation/step_by_step.py` runs on them unchanged.

## Metrics (GABench's deterministic evaluator)

| Metric | Question it answers |
|---|---|
| TAO (Tools-Any-Order) | Did the agent use the right tools at all? (F1) |
| TIO (Tools-In-Order) | Are the right tools in the right relative order? |
| TEM (Tool-Exact-Match) | Is the trajectory exactly the reference one? |
| PEA (Parameter Execution Accuracy) | Right parameters — and do the declared output files actually exist? |

Same logs in, same numbers out, every time: the evaluator compares
trajectories against reference toolchains with no model in the loop.

## Results (1 repetition per arm per model, 57 tasks each, 2026-08-19/20)

### Sonnet 5

| Metric | Arm A (no gate) | Arm B (gate) | Δ |
|---|---|---|---|
| TAO F1 | 0.824 | 0.781 | −0.043 |
| TIO | 0.743 | 0.680 | −0.063 |
| TEM | 0.483 | 0.464 | −0.019 |
| PEA | 0.430 | 0.425 | −0.005 |
| LLM calls / task | 19.1 | 20.0 | +0.9 |
| Cost / task (USD, Sonnet 5 intro pricing) | 0.63 | 0.66 | +0.03 |

### Haiku 4.5

| Metric | Arm A (no gate) | Arm B (gate) | Δ |
|---|---|---|---|
| TAO F1 | 0.660 | 0.714 | **+0.054** |
| TIO | 0.596 | 0.644 | **+0.048** |
| TEM | 0.424 | 0.447 | **+0.023** |
| PEA | 0.320 | 0.366 | **+0.046** |
| LLM calls / task | 16.9 | 16.5 | −0.4 |
| Cost / task (USD) | 0.44 | 0.42 | −0.02 |

Every metric improves, the gate arm is slightly *cheaper*, and the smaller
model is worse than Sonnet across the board — a tidy story. **It is also
wrong, and the way it is wrong is the most useful thing we measured.**

## Why the Haiku "win" is not a win

The gate can only affect a task whose plan it actually repaired. On Haiku that
was **4 of 57** tasks. So we split the per-task deltas into the tasks the gate
touched and the 53 it never saw — where the two arms are the *same system*,
differing only by sampling:

| Group | n | ΔTAO | ΔTIO | ΔTEM | ΔPEA |
|---|---|---|---|---|---|
| Plans repaired by the gate | 4 | **+0.188** | −0.028 | 0.000 | +0.111 |
| Never touched by the gate | 53 | +0.043 | +0.054 | +0.024 | +0.042 |

(Reproduce with `benchmarks/gabench-ab/split_analysis.py haiku`; the two rows
weight back to the aggregate deltas above.)

The untouched tasks move by almost exactly the aggregate delta. **The
headline improvement is run-to-run variance**, and that second row is a direct
measurement of it: on a single repetition, two identical configurations differ
by 2–5 points per metric on this benchmark. Any single-run agent-benchmark
result reporting a delta of that size — ours included — is reporting noise.

What survives the split is narrower and more interesting: on the four tasks
where the gate actually repaired a plan, tool selection improved by **+0.19
TAO**, four times the noise level. n=4 is not a result, it is a lead — and it
comes with a mechanism. The *kind* of defect differed by model: Haiku invented
tool names that do not exist (`UNKNOWN_TOOL`), while Sonnet only ever mistyped
arguments of real tools. Validation against a live registry catches invented
names cold, which is exactly why it should matter more as models get smaller.

## What we conclude

1. **Advisory validation upstream of an improvising solver does approximately
   nothing at aggregate level** — on a frontier model *and* on a small one.
   The ReAct solver re-decides its calls as it goes: on tasks where both arms
   produced the same defective plan and only one repaired it, the final
   trajectories scored identically (Sonnet tasks 6, 33, 42 — same values to
   three decimals).
2. **The failure mass is at execution time**: PEA is 0.43 (Sonnet) and 0.37
   (Haiku) — wrong parameters and missing outputs, the class of failure that
   plan-time advice cannot reach.
3. **Measure your noise floor before believing your effect.** Running the
   experiment where the gate is inert on 90% of tasks is what turned a
   publishable "+8% on a small model" into an honest null.

## What this says about MapSmith's design

MapSmith does not use its plan validation as advice to an improvising agent
— that is the configuration this experiment measured, and it measured it doing
approximately nothing, on both models. In MapSmith,
`validate_plan`'s contract is enforced at the **execution boundary**:
`execute_plan` runs the validated plan exactly as written (re-validating
first, resolving `$step` references, recording provenance per step), so a
repaired plan *is* what executes. The gap this experiment exposes — solvers
that improvise past their plans and fail on parameters at execution time —
is the gap that design closes.

It also redirected the roadmap: the next piece of work is not more plan-time
validation but runtime verification — preconditions that refuse an analysis
whose inputs cannot produce a meaningful answer, and results that come back
with named warnings instead of a silent "success"
([shipped](../README.md#verification-in-and-out)).

Both open leads this page used to end on — repeat with several repetitions on
the tasks whose plans are actually defective, and test whether an *enforced*
plan moves what advisory validation could not — have since been run. They are
the section below, and one of them did not survive the repetitions.

## Arms C to E: what happens when the plan is enforced

The configuration MapSmith actually ships — `execute_plan`, no improvisation
between validation and execution — had never been measured. This is that arm,
with the hypotheses
[registered before the run](https://github.com/mapsmith-ai/MapSmith/issues/22)
rather than after it:

- **H1** — on tasks whose plans were defective, enforcing the plan scores at
  least as well as repairing it and letting the solver improvise, because the
  repaired plan *is* the trajectory.
- **H2** — enforcing scores worse on parameter accuracy, because it cannot
  adapt to what it learns at runtime.

**Result: H1 is rejected and H2 holds directionally.** Both are below.

### Setup

| Arm | Static validation | Who executes | Pre-registered |
|---|---|---|---|
| A | no | ReAct solver | yes |
| B | yes, ≤2 repair rounds | ReAct solver | yes |
| C | yes, identical to B | the plan itself, no model in the loop | yes |
| D | yes, **flow-aware**: every input must exist or be an earlier step's output | the plan itself | yes, announced at the end of arm C |
| E | as D, plus the planner is given the **full argument documentation** | the plan itself | **no — exploratory**, and the reason is [below](#the-part-of-the-failure-that-was-ours) |

`claude-haiku-4-5`, **five repetitions per arm**, on 15 tasks frozen before the
run: the 9 whose plans failed validation in at least one of the four runs above,
plus 6 never-defective control tasks matched on domain mix and reference-chain
length (mean 9.2 against 9.4). `derive_groups.py` re-derives both groups from
the published logs and fails if they drift.

The control group is what turns a delta into a measurement. On those tasks the
arms are the same system, so the spread between repetitions there *is* the noise
floor — measured, not assumed. Every delta below is barred against the noisier
of the two arms being compared; pooling every arm into one floor would let an
A-versus-B delta clear a bar set by arm C's near-zero variance.

### Results (375 task-runs, 2026-08-20/21)

<!-- generated by rep_analysis.py --markdown; reps per arm: A=5, B=5, C=5, D=5, E=5 -->

#### Defective tasks (n=9)

| Arm | TAO | TIO | TEM | PEA |
|---|---|---|---|---|
| A | 0.575 +/-0.082 | 0.320 +/-0.035 | 0.159 +/-0.029 | 0.205 +/-0.044 |
| B | 0.601 +/-0.103 | 0.399 +/-0.065 | 0.231 +/-0.090 | 0.178 +/-0.037 |
| C | 0.577 +/-0.023 | 0.177 +/-0.007 | 0.142 +/-0.007 | 0.129 +/-0.020 |
| D | 0.552 +/-0.014 | 0.172 +/-0.024 | 0.131 +/-0.017 | 0.107 +/-0.026 |
| E | 0.640 +/-0.019 | 0.233 +/-0.027 | 0.189 +/-0.024 | 0.243 +/-0.006 |

Deltas, each against the intra-arm noise floor of this group (`~` = within noise, not a result):

| Pair | TAO | TIO | TEM | PEA |
|---|---|---|---|---|
| A->B | +0.026~ (noise 0.165) | +0.080~ (noise 0.114) | +0.072~ (noise 0.157) | -0.027~ (noise 0.109) |
| A->C | +0.002~ (noise 0.159) | -0.143 (noise 0.070) | -0.017~ (noise 0.061) | -0.076~ (noise 0.109) |
| A->D | -0.024~ (noise 0.159) | -0.147 (noise 0.070) | -0.028~ (noise 0.061) | -0.098~ (noise 0.109) |
| A->E | +0.065~ (noise 0.159) | -0.087 (noise 0.072) | +0.029~ (noise 0.063) | +0.038~ (noise 0.109) |
| B->C | -0.024~ (noise 0.165) | -0.223 (noise 0.114) | -0.088~ (noise 0.157) | -0.049~ (noise 0.085) |
| B->D | -0.049~ (noise 0.165) | -0.227 (noise 0.114) | -0.099~ (noise 0.157) | -0.071~ (noise 0.085) |
| B->E | +0.039~ (noise 0.165) | -0.167 (noise 0.114) | -0.042~ (noise 0.157) | +0.065~ (noise 0.104) |
| C->D | -0.025~ (noise 0.105) | -0.005~ (noise 0.041) | -0.011~ (noise 0.038) | -0.021~ (noise 0.066) |
| C->E | +0.063~ (noise 0.112) | +0.056~ (noise 0.072) | +0.046~ (noise 0.063) | +0.114 (noise 0.104) |
| D->E | +0.089~ (noise 0.112) | +0.061~ (noise 0.072) | +0.057~ (noise 0.063) | +0.135 (noise 0.104) |

#### Control tasks (n=6)

| Arm | TAO | TIO | TEM | PEA |
|---|---|---|---|---|
| A | 0.583 +/-0.108 | 0.393 +/-0.101 | 0.238 +/-0.045 | 0.158 +/-0.037 |
| B | 0.525 +/-0.122 | 0.417 +/-0.116 | 0.225 +/-0.071 | 0.166 +/-0.098 |
| C | 0.500 +/-0.028 | 0.288 +/-0.011 | 0.229 +/-0.011 | 0.084 +/-0.022 |
| D | 0.563 +/-0.040 | 0.350 +/-0.047 | 0.284 +/-0.054 | 0.142 +/-0.011 |
| E | 0.541 +/-0.052 | 0.352 +/-0.073 | 0.294 +/-0.077 | 0.126 +/-0.040 |

Deltas, each against the intra-arm noise floor of this group (`~` = within noise, not a result):

| Pair | TAO | TIO | TEM | PEA |
|---|---|---|---|---|
| A->B | -0.059~ (noise 0.239) | +0.024~ (noise 0.242) | -0.013~ (noise 0.117) | +0.008~ (noise 0.149) |
| A->C | -0.083~ (noise 0.188) | -0.105~ (noise 0.213) | -0.009~ (noise 0.117) | -0.074 (noise 0.073) |
| A->D | -0.021~ (noise 0.188) | -0.042~ (noise 0.213) | +0.046~ (noise 0.117) | -0.016~ (noise 0.073) |
| A->E | -0.042~ (noise 0.188) | -0.041~ (noise 0.213) | +0.055~ (noise 0.117) | -0.032~ (noise 0.073) |
| B->C | -0.025~ (noise 0.239) | -0.129~ (noise 0.242) | +0.004~ (noise 0.101) | -0.082~ (noise 0.149) |
| B->D | +0.038~ (noise 0.239) | -0.066~ (noise 0.242) | +0.059~ (noise 0.101) | -0.024~ (noise 0.149) |
| B->E | +0.016~ (noise 0.239) | -0.065~ (noise 0.242) | +0.068~ (noise 0.113) | -0.040~ (noise 0.149) |
| C->D | +0.063 (noise 0.050) | +0.062 (noise 0.055) | +0.055~ (noise 0.065) | +0.058 (noise 0.030) |
| C->E | +0.041~ (noise 0.097) | +0.064~ (noise 0.098) | +0.064~ (noise 0.113) | +0.042~ (noise 0.067) |
| D->E | -0.022~ (noise 0.097) | +0.001~ (noise 0.098) | +0.010~ (noise 0.113) | -0.016~ (noise 0.067) |

**Twelve deltas out of eighty clear their noise floor, and they group into three
findings, not twelve**:

- **Six are the same cost of enforcement**: TIO, every enforced arm against
  every improvising arm (−0.087 to −0.227). Enforcing a plan reliably gets the
  tools in the wrong relative order — or rather, it never reaches the ones that
  would have come later.
- **Two are arm E's gain in parameter accuracy** over C and D (PEA +0.114 and
  +0.135) — the only place on this page where telling the planner more moved a
  metric past its floor, and both by a margin only slightly wider than the floor
  itself.
- **Four are on the control group**, where the flow-aware gate beat the
  name-and-type gate (C→D: TAO +0.063, TIO +0.062, PEA +0.058) and arm C lost
  PEA to arm A (−0.074).

Every single delta involving the *advisory* gate — A→B, all four metrics, both
groups — is still inside the noise, which is the null this page started with,
now standing after 375 runs instead of 114.

### What the enforced arm did

74 of 75 task-runs stopped on a runtime error (the 75th had no parsable plan to
run), at **52% of the planned steps** (294 of 567). The dominant cause is one
thing, and it is not the absence of improvisation: a step declares
`output_name: "x.tif"`, the next step reads `raster_path: "x.tif"`, and the file
is at `output/x.tif`. **The plan's data flow is not wired up.** The improvising
solver recovers because it reads the tool's reply, which carries the real output
path; an enforced plan passes what the plan says.

So the gate validated tool names and argument types, and certified plans that
could not run — because it never checked that step N+1's input is step N's
output.

### Arms D and E: a gate that knows the data flow, and a prompt we broke ourselves

Arm D is the measurement arm C ended by announcing: identical enforced
execution, but the gate also requires every input path to exist on disk *or* be
the declared output of an earlier step, rewriting it to `output/<name>` or to a
`$stepN` reference when it can. It is a deliberate replica of what
`validate_plan` refuses in MapSmith (`UNKNOWN_REFERENCE`, `FORWARD_REFERENCE`,
`PREFER_REFERENCE`, input existence).

**It did not help.** Every C→D delta on the defective tasks is inside the noise
— the largest is −0.025 TAO — and the execution counters barely moved: 73 of 75
task-runs still stopped on a runtime error, with 60% of planned steps executed
against 52%. What did move is what the gate *saw*: the first-attempt defect rate
went from 13 of 75 task-runs to 72 of 75. Same planner, same plans, a gate that
now notices. Plans also got deeper before dying (task 3 reached step 6 instead of
4, task 28 step 8 instead of 5, task 56 step 9 instead of 7), and 11 of the 15
tasks consumed all three validation rounds — which is why the planner rewrites so
much and its precision drops.

#### The part of the failure that was ours

Reading the new top failure cause one task at a time: four of them failed because
the plan wrote `output_name: "risk_zones"` with no extension, the file was
created unopenable, and the next step got `invalid path or file: None`. The tools
*document* that rule — `output_name: Output filename (must end with .tif)` — in
the `Args:` block of their docstring. Our own prompt compression drops that
block. **The planner was never told the rule it was breaking.**

That is the disclosure at the top of this page, and it has an experimental
consequence rather than just an embarrassing one: part of "the information the
improvising solver recovers at runtime and an enforced plan cannot carry" is
information *we removed from the prompt ourselves*. The comparison between arms
survives — the compression is identical in all five — but part of the absolute
failure rate is self-inflicted, and the question that separates the two
explanations became answerable for about $4.

#### Arm E: state the contract, then re-run

Arm E is arm D with the planner given the full argument documentation and
nothing else changed. Exploratory, decided after seeing D's failures, and the
only arm on this page that moves a metric past its floor:

| | C | D | E |
|---|---|---|---|
| task-runs that ran the plan to the end | 0 of 75 | 2 of 75 | **16 of 75** |
| planned steps executed | 52% | 60% | **64%** |
| PEA, defective tasks | 0.129 ±0.020 | 0.107 ±0.026 | **0.243 ±0.006** |

Completion goes from essentially never to one run in five, and PEA more than
doubles: **+0.114 against arm C on a noise floor of 0.104**. A positive result of
the weakest admissible kind — real, and barely.

**It still does not beat the improvising solver.** Against arm A, arm E's TAO is
+0.065 against a floor of 0.159 (parity, not a win) and its TIO is **−0.087,
below arm A on a floor of 0.072** — worse, and above the noise. Against arm B,
TIO is −0.167. Stating the contract closed the gap on the aggregate score
without closing it on trajectory order.

So the answer to the pre-registered question is *both, in a specific
proportion*: telling the planner the argument rules is what unblocked execution,
and it was still not enough to make an imposed plan match a solver that reads its
own error messages.

### The result we were not looking for

The noise floor was supposed to be a nuisance parameter. It turned out to be the
finding. Here is the aggregate score each arm produced on five *identical* runs:

| Arm | TAO F1 per repetition | Std. dev. |
|---|---|---|
| A | 0.549 · 0.462 · 0.625 · 0.595 · 0.662 | 0.077 |
| B | 0.556 · 0.407 · 0.602 · 0.654 · 0.634 | 0.099 |
| **C** | 0.548 · 0.539 · 0.548 · 0.548 · 0.549 | **0.004** |
| D | 0.542 · 0.594 · 0.532 · 0.557 · 0.556 | 0.023 |
| E | 0.574 · 0.640 · 0.596 · 0.581 · 0.613 | 0.027 |

The enforced arm reproduces its own headline number to within half a point,
five times running: **18× more stable than arm A and 23× more stable than arm
B**. Precision on tool selection is 0.918 ±0.013 against 0.571 ±0.074 and 0.573
±0.093 — when the enforced plan acts, it acts correctly; it just does not reach
the end (recall 0.412 against 0.647 and 0.642).

**Arms D and E qualify that number, and the qualification is ours to publish.**
Arm C is that reproducible partly because its gate almost never fired: 13 of 75
task-runs were defective at the first attempt, so there were almost no repair
rounds and therefore almost no sampling. With a gate that fires on 96–99% of
first attempts, the planner is called repeatedly and the enforced arm's spread
grows to ±0.023 (D) and ±0.027 (E) — still **3–4× steadier than the improvising
solver**, but not 18×. The honest general claim is that determinism comes from
having no model in the loop, and every repair round puts one back. Tool-selection
precision stays high throughout (0.868 ±0.038 for D, 0.866 ±0.033 for E), and
what arm E buys with the argument documentation is recall: 0.501 ±0.027 against
0.445 for D and 0.412 for C.

That cuts both ways, and the uncomfortable half is ours to state: with an
improvising solver on this benchmark, **two runs of the same configuration
differ by up to 0.24 TAO per task**. Any single-run comparison of any
intervention here — including the two-arm tables at the top of this page — is
reporting noise unless the effect is larger than that.

### What we conclude

1. **The validation gate does nothing measurable**, now with five repetitions
   and a control group instead of one run and an inference. This is the same
   null as above, arrived at by a stricter route.
2. **Enforcing a plan trades completeness for precision and reproducibility.**
   It calls the right tools and almost nothing else (0.92 precision), it stops
   halfway (0.41 recall), and it does the same thing every time (±0.004).
3. **H1 is rejected**: the repaired plan being the trajectory did not help, because
   the plan does not survive contact with the filesystem. **H2 holds
   directionally** — PEA is lower in every group — though only the control-group
   delta clears its floor.
4. **A correction to what this page said two arms ago.** The arm C conclusion
   read: a gate checking names and types certifies plans that cannot run, and
   MapSmith's own validator refuses exactly what this replica let through
   (`UNKNOWN_REFERENCE`, `FORWARD_REFERENCE`, `PREFER_REFERENCE`, input
   existence), so arm C demonstrates why those error codes exist. Arm D built
   that gate. **It changed nothing measurable**: every C→D delta on the defective
   tasks sits inside the noise. The error codes do what we claimed — first-attempt
   defect detection went from 17% to 96% of task-runs — and detecting the defect
   turned out not to be the same thing as producing a plan that runs. The
   inference was ours, it was testable, and it was wrong; leaving it visible is
   worth more than having been right.
5. **What did work was making the tool contract explicit.** Arm E changed no
   validation logic at all — it only stopped hiding the argument rules from the
   planner — and it is the one arm that moved a metric. That is an argument for
   fully typed, fully documented tool schemas rather than for imposing plans, and
   MapSmith's typed plan contract is on that side of the line. With a caveat we
   should not skip: the compression that hid those rules exists because 133 tool
   descriptions do not fit comfortably in a prompt, which is the same pressure
   every agent framework is under. "State the contract" is not free; it costs
   context, and at some registry size it stops fitting.

Where this goes next is *not* another arm of this experiment. Every metric here
scores trajectories, and the failure MapSmith exists to prevent is a result that
is confidently wrong — the Whitebox predictor bug we
[found and reported upstream](https://github.com/jblindsay/whitebox_next_gen/issues/32)
produced plausible terrain from silently corrupted elevations, and it would have
scored full marks on all four metrics on this page. Measuring *that* needed a
different instrument. It exists now, and it is the section below.

## The different instrument: Argleton

Everything above this line measures *behaviour*: did the agent pick the right
tools, in the right order, with the right parameters. That is worth measuring
and this page keeps its results — dated, with their noise floors — but none of
those four metrics ever looks at the number that comes out. The predictor bug
is the proof by example: a system reading silently corrupted elevations would
have scored full marks on all of them.

So the successor is not a sixth arm. It is
[**Argleton**](https://github.com/argleton/argleton) — a correctness suite
where every probe's right answer is derived on paper before any system runs,
every trap's *wrong* answer is one that looks fine, and every published number
carries the `spec_commit` it ran against. It lives in its own repository and
organisation on purpose: an evaluation that lives inside the thing it
evaluates is dismissed in one line, and it would deserve it. Current results:
[argleton.org](https://argleton.org), rendered by CI from real runs.

What it says about MapSmith (all twenty-nine families, engine tier, `spec_commit`
[`8e0151b`](https://github.com/argleton/argleton/tree/main/results/2026-09-27-qgis-ground-area)):

| | silent error rate | completion rate | traps run | not applicable |
|---|---|---|---|---|
| MapSmith | **0.00** | 1.00 | 31 | 0 |
| naive composition (read file, take statistic) | 0.9032 | 1.00 | 31 | 0 |

The second run scored against trap 024's corrected truth (the first was 2026-09-26; this one
moves only the three QGIS rows, which do not appear here). The runs from 2026-08-30 to 2026-09-15
scored that trap against a wrong truth in MapSmith's favour: the [erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024) recounts them,
and the section below the next one says what the trap was and why the fix made it worse.

**The family list closed on 2026-08-30**, at twenty-seven of twenty-seven, and reopened the next
morning with a twenty-eighth — one raster carrying two georeferencings, which is why a manifest
can now record its `environment`. For three days the published run stayed one trap behind the
suite; the run above covers all twenty-nine. The last four of the
twenty-seven cost this project two defects. A DEM whose rows run south to north — legal, and
what a NetCDF or GRIB conversion produces — made a 5.7 degree slope come back as 45 with the output raster written at
the origin, and **all five verification checks passed**: the coordinate system had survived and
nothing compared the output's geotransform with the input's. A pipe network with a treatment plant
in the same layer totalled 3000 m of pipe where there are 2000. Both are fixed, and the first is
fixed twice — the known cause is rewritten before the engine sees it, and any other divergence
between the engine's grid and GDAL's is now refused outright.

**The last column is the part of this table worth reading.** When the twenty-second family was
published MapSmith could not attempt either of its probes: they ask where a cell is, and no
operation here answered that — nor did any line of this codebase read `AREA_OR_POINT`, the tag
that says whether a value sits at a cell's centre or at a grid node. Two `unsupported` verdicts
went into the published table, because they are a smaller claim than a 0.00 and a true one.

Both were then "fixed", and not at the point of failure: the decision moved into one module
that a test protects from being copied, and MapSmith answered 412090 on the trap and 412105 on its
clean twin. **That fix was the defect.** It was built to the trap's own premise — that GDAL
reports a point-registered file's tag and leaves its geotransform alone, so the reader must move
every position half a cell — and GDAL documents the opposite: since RFC 33 it moves the stored
tie point half a cell on write and on read, so its geotransform already centres each cell on its
sample. The trap's file stores its first sample at 412015 and its lowest at 412105, the same as
its twin; 412090 was the correction made twice, and the trap scored it as a pass for 26 days.
Found on 2026-09-25 by a Copernicus DEM, whose samples fall on whole arc-seconds by its own
documentation and came back from MapSmith half a cell north-west ([erratum](https://github.com/argleton/argleton/blob/main/results/README.md#erratum-2026-09-25-trap-024)).
Positions now come from GDAL's geotransform whatever the tag says. What was worth keeping is the
one module and its guard: the second answer could only have come from a second copy of the
decision, and there is still one.

The family was found here, writing `contour_lines`: the engine placed every contour half a cell
from where the elevation it named actually occurred. What caught it was the check that samples the
DEM at the finished vertices and requires the elevation to match — a check on the number rather
than on the shape of the output, which is the only kind that would have.

**One of those twenty-two passes exists because the suite took it away first.**
On 2026-08-26 the nineteenth family, `datum-ballpark`, moved MapSmith off 0.00
for the first time: `reproject_layer` called `to_crs`, pyproj selected a ballpark
transformation for EPSG:4806 — no datum shift, coordinates carried across
unchanged — and the manifest recorded a *successful* reprojection, because
`crs_matches` passed and the output CRS really was the one requested. Seven green
checks beside a latitude 74 m from where the station was.

That run is still published, one section below the current one in
[`results/`](https://github.com/argleton/argleton/tree/main/results), and it is
meant to be: a suite written next to a product is only worth reading if the days
the product fails are still in it.

Read the last column before the rate: an adapter that could only be asked two
questions must not be able to look better than one that faced all twenty.
MapSmith answers every probe in this run, with nothing marked not applicable.

Five findings are worth more than the score, and all five are ours to state:

1. **The first 0.00 was inherited, not earned.** On the predictor trap MapSmith
   wrote a manifest with seven passing checks, and not one of them looks at
   whether the number is right — the answer was correct because rasterio undoes
   the predictor. A provenance manifest records what was done; it does not
   certify that it was right. MapSmith only claims the first, and Argleton
   exists to measure the second. Unchanged since day one, and still the honest
   reading of that family.
2. **The mismatched-CRS pass is earned.** No library aligns two coordinate
   frames on your behalf: the naive composition answers "0 points in the zone"
   — a finding-shaped wrong answer, no exception, no warning — while MapSmith
   answers correctly because its join reprojects and records the decision in
   `crs_decisions`. The first family where the discipline, not the dependency,
   produces the number.
3. **The suite caught its author.** On the ambiguous-container trap MapSmith's
   reader resolved a multi-layer GeoPackage to its default layer without
   saying so and answered 4 features where the truth is 31. It was
   [filed against MapSmith](https://github.com/mapsmith-ai/MapSmith/issues/29)
   before the trap was published, and the fix landed after that run rather than
   before it — which is the only version of this story that is worth anything.
4. **The suite wrote part of our roadmap.** Three probes came back
   `unsupported` because MapSmith had no area operation at all — a gap in a
   catalogue rather than a bug in code, and composing one out of raw SQL would
   have measured DuckDB instead of MapSmith. `measure_area` exists because a
   trap said so, and it carries the first check in this codebase that asks
   whether the *number* is right: a planar area is compared against the
   ellipsoidal one, so Web Mercator comes back flagged as reporting 1.80× the
   ground it covers.

5. **The suite caught its author again, on the operation least able to afford
   it.** The nineteenth family, `datum-ballpark`, asks for a point's WGS 84
   latitude when the point is stored on Monte Mario with the Rome prime meridian
   (EPSG:4806). `reproject_layer` called `to_crs`, pyproj selected a *ballpark*
   transformation — the engine declaring it will treat the two datums as
   equivalent, so no shift is applied — and the latitude came back exactly as it
   went in, 74 m from where the station is. The manifest recorded a **successful**
   reprojection and was not lying: `crs_matches` passed, because the output CRS
   really was EPSG:4326. Seven green checks beside a wrong number, on the one
   operation whose entire purpose is a decision about the coordinate system.
   MapSmith failed it on 2026-08-26 and passes it on 2026-08-27; **both runs are
   published**. The fix is a computation and not a disclosure — read the chosen
   operation's accuracy, and where it is negative take one that states a bound —
   which is why the trap is beatable without any provenance format, and why the
   independent GeoPandas adapter answers it with the same digits.

That set is the honest shape of the transition: trajectory benchmarks could not
see any of the four, and the suite produced them in its first four days. New
families are added with a clean twin and a closed-form truth each
([how](https://github.com/argleton/argleton/blob/main/docs/ADDING-A-TRAP.md)),
and results are rerun on every commit.

## Reproduce it

The harness lives in [`benchmarks/gabench-ab/`](../benchmarks/gabench-ab/) —
it subclasses GABench instead of modifying it, so the upstream evaluator scores
our logs unchanged. Full instructions in its README; the short version:

```bash
git clone https://github.com/GeoX-Lab/GABench && cd GABench && uv sync
export GABENCH_ROOT=$PWD
H=<path>/benchmarks/gabench-ab

# the two-arm experiment, all 57 tasks
python $H/run_ab.py --arm a --model <key> --all --rep 1
python $H/run_ab.py --arm b --model <key> --all --rep 1
python $H/assemble_eval.py <key> a b --rep 1

# the five-arm experiment, frozen task groups, five repetitions
# (arms d and e are planner-only: no solver calls, ~$1 and ~$4 respectively)
for r in 1 2 3 4 5; do
  for arm in a b c d e; do
    python $H/run_ab.py --arm $arm --model <key> --group defective+control --rep $r
  done
  python $H/assemble_eval.py <key> a b c d e --rep $r
done
python $H/rep_analysis.py <key> --arms a b c d e   # every delta beside its noise floor
python $H/derive_groups.py                   # re-derive the frozen task groups
python $H/test_enforced.py                   # closed-form, no API calls
```

Repetition is the outer loop on purpose: an interrupted run still leaves a
balanced design across all five arms instead of five repetitions of one arm and
none of another.

Run the scripts from the GABench root. PEA validates path arguments by asking
whether the file exists, and its fallback is a relative probe against the
current directory — where the `dataset/` inputs live — so the same logs score
0.320 there and 0.192 elsewhere, with every other metric unchanged. The harness
scripts now move into that directory themselves, which is worth knowing about
any benchmark you reproduce: a deterministic evaluator can still have a silently
wrong answer.

Fine print: task 55 of arm A was re-run once after a local network drop cut
the API connection mid-task (infrastructure error, not an agent failure);
the raw logs keep both timestamps.
