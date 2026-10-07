# GABench A–E: does plan validation help a GIS agent — and does enforcing it?

This harness measures two ideas in isolation: **validating a typed plan against
the live tool registry before execution**, and then **executing that plan as
written instead of letting the agent improvise past it**. It runs
[GABench](https://github.com/GeoX-Lab/GABench) unmodified — subclassing its
agents rather than editing them — so its deterministic evaluator scores our
logs without changes.

Results and interpretation, for every arm below:
[`docs/benchmarks.md`](../../docs/benchmarks.md).

## The five arms

All arms share everything: model, prompts, tools, data, and a typed planner that
emits `[{"step_id": 1, "tool": ..., "arguments": {...}}, ...]`.

| | Static validation of the plan | Who executes |
|---|---|---|
| **Arm A** | no | ReAct solver (improvises) |
| **Arm B** | yes — unknown tool (with did-you-mean), missing/unknown/mistyped arguments, malformed steps; machine-readable errors go back to the planner, ≤2 repair rounds | ReAct solver (improvises) |
| **Arm C** | yes, identical to B | the plan itself: steps in order, `$stepN` references resolved from real outputs, stop at the first failure, **no model in the loop** |
| **Arm D** | yes, plus the data flow: every input path must exist on disk or be an earlier step's declared output, rewritten to `output/<name>` or to a `$stepN` reference where possible — a replica of what MapSmith's `validate_plan` refuses | as C |
| **Arm E** | as D | as C, with one prompt change: the planner is given the full argument documentation instead of the compacted signatures |

A→B isolates the gate. B→C isolates who executes. C→D isolates a gate that
understands references from one that only checks names and types. D→E isolates
telling the planner the argument rules, changing no validation logic at all.
Arm A records the same validation audit *without acting on it*, so you can see
whether two arms produced defective plans on the same tasks.

Arm C is the configuration MapSmith ships (`execute_plan`), and enforcing a plan
cuts both ways by design: a plan the gate could not fix executes zero steps and
scores zero, where an improvising solver would have salvaged part of the task.
That is a property of the idea being measured, not a harness failure, so
`exec_audit` records the stop reason for every task instead of hiding it.

## Run it

```bash
# 1. GABench itself (its own instructions: uv sync, model endpoint in config.yaml)
git clone https://github.com/GeoX-Lab/GABench
cd GABench && uv sync

# 2. point the harness at it (or keep GABench as a sibling directory)
export GABENCH_ROOT=/path/to/GABench

# 3. run the arms, from the GABench root so its config.yaml/.env resolve
python /path/to/gabench-ab/run_ab.py --arm a --model <key> --all --rep 1
python /path/to/gabench-ab/run_ab.py --arm b --model <key> --all --rep 1
# arms c, d and e run on the frozen groups; d and e are planner-only (no solver calls)
python /path/to/gabench-ab/run_ab.py --arm c --model <key> --group defective+control --rep 1

# 4. assemble artifacts and score a run
python /path/to/gabench-ab/assemble_eval.py <key> a b c --rep 1
```

The five-arm, five-repetition recipe published in
[`docs/benchmarks.md`](../../docs/benchmarks.md) loops the same two commands over
`a b c d e` with the repetition as the outer loop, so an interrupted run still
leaves a balanced design.

`--model <key>` is a key from GABench's `config.yaml`. `--group` uses the frozen
task groups in `task_groups.py`; `--ids 1,2,3` and `--all` also work. Runs
resume: completed tasks are skipped, so an interrupted run continues where it
stopped. Arms must run **sequentially** — they share GABench's `output/`
working directory.

Results land in `results/{model}/arm_{arm}_rep{rep}/rep{rep}.jsonl`. The
repetition is part of the directory on purpose: the evaluator derives the
physical-output directory by rewriting that path, so repetitions sharing a
directory would score each other's artifacts (see `_paths.run_dir`).

Inspect a finished run:

```bash
python gate_stats.py <results>/rep1.jsonl   # what the gate caught
python split_analysis.py <key>              # effect vs run-to-run noise (one rep per arm)
python rep_analysis.py <key> --arms a b c d e   # arms x repetitions, every delta next to its noise
python derive_groups.py                     # re-derive the frozen task groups from the A/B logs
python cost_check.py <usage.jsonl> <in-price> <out-price>   # token spend
python test_gate.py                         # closed-form gate test, no API calls
python test_enforced.py                     # closed-form executor test, no API calls
```

`split_analysis.py` is the one that decides interpretation on a single
repetition: it splits per-task deltas into the tasks the gate actually repaired
and the ones it never touched. On the untouched tasks the two arms are the same
system, so whatever they differ by *is* the run-to-run noise floor — compare
your aggregate delta against that before believing it. With several repetitions,
`rep_analysis.py` measures that floor directly, within one arm.

## Notes on method

- **The solver prompt carries compact tool signatures** (name, typed
  arguments, one-line description) instead of raw tool objects — ~26k
  characters instead of ~148k. This is a declared change from upstream,
  applied identically to every arm; without it the input cost per task is
  roughly four times higher for no measured benefit. It has a price that took
  a while to notice: keeping only the first line of a description drops the
  `Args:` block, where rules like `output_name: Output filename (must end with
  .tif)` live. An improvising solver still learns them — from the error the
  tool returns — while an enforced plan never does, which flatters the
  improvising arms in a way that has nothing to do with improvisation.
- **Each task starts from a clean output directory** and its artifacts are
  archived afterwards. Without this, a task can "succeed" by reusing a
  previous run's files — observed on our first smoke test.
- **Logs keep the upstream history format** (`Action: {...}` in assistant
  turns, observations as user turns), plus `gate_audit` and `exec_audit`, so
  `evaluation/step_by_step.py` runs unchanged. `test_enforced.py` asserts that
  GABench's own extractor recovers exactly the calls the executor made: get that
  format wrong and an arm reports zero tool calls, which reads as a catastrophic
  agent rather than a broken harness.
- **`status` in a record means "the harness finished this task"**, not "the plan
  worked". Upstream's resume logic skips only `status: success` and its evaluator
  prefers the last successful record per task, so marking an enforced plan that
  stopped on a tool error as `error` would silently re-run and re-plan those
  tasks. The plan's own outcome is in `plan_status`, `failed_step` and
  `exec_audit`.
- **A failed tool does not raise in GABench's stdio mode.** Its client adapter
  keeps only the reply text and drops the protocol's `isError` flag, so a tool
  exception arrives as a successful result whose text starts with `Error calling
  tool ...`. The ReAct solver gets away with it (the model reads the text); an
  executor must not. Our first live smoke test reported "3/3 steps, no errors"
  on a task where all three tools had failed — `tool_reply_failed` and its
  pinned strings in `test_enforced.py` exist because of it.
- **PEA depends on the working directory.** The evaluator checks `*_path`
  arguments by asking whether the file exists, and its fallback is a relative
  probe against the current directory, where dataset inputs like
  `dataset/x.geojson` live. Run an analysis script from elsewhere and PEA comes
  out several points lower with every other metric unchanged — 0.320 against
  0.192 on the same logs, in our case. The scripts here move into the GABench
  root themselves (`_paths.use_gabench_cwd`) so this cannot bite silently.
- **Task selection is frozen before the runs**, in `task_groups.py`: the tasks
  whose plans were ever defective, plus a control group of never-defective tasks
  matched on domain mix and reference-toolchain length. Choosing tasks after
  seeing results is how regression to the mean gets published as an effect.
- This directory contains only our own code and links to their repository;
  nothing of theirs is redistributed. When it was written that was a
  constraint -- GABench shipped no license file -- and we asked
  ([GeoX-Lab/GABench#2](https://github.com/GeoX-Lab/GABench/issues/2)). On
  2026-09-03 they added Apache-2.0 and closed the issue, so redistribution is
  now permitted; the layout stays as it is because it is the cleaner one.
