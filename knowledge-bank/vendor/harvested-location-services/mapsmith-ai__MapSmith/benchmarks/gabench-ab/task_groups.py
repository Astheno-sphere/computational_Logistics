"""Frozen task groups for the arm-C experiment. Selected before any C run.

Repeating all 57 tasks across three arms is not affordable, so the experiment
runs on a subset — and a subset chosen after seeing results is how a noise floor
gets mistaken for an effect. Both groups below were therefore derived
mechanically from the four published A/B runs (2026-08-19/20) and frozen here
before the first arm-C run. `derive_groups.py` recomputes them from those logs,
so the selection is reproducible rather than asserted.

DEFECTIVE — every task whose plan failed static validation on the first attempt
in at least one of the four runs (Sonnet A/B, Haiku A/B). This is where the gate
can do anything at all: on the other tasks arms B and C differ from A only by
sampling. Note the property is stochastic — the same task passes validation in
one run and fails in another — so with repetitions this measures a *rate* of
defective plans per task, not a flag. Task 56 is defective in 3 of 4 runs, always
with UNPARSABLE_PLAN: likely a parsing problem of its own, to be read separately
before being counted as a defective plan.

CONTROL — tasks that passed validation cleanly in all four runs, so both arms are
the same system on them. Two things it buys: an *intra-arm* noise floor (rep i vs
rep j of the same arm), which the first experiment could only infer from
untouched tasks; and protection against regression to the mean, since tasks
picked because they scored badly once tend to score better next time whatever we
change. Selection rule, applied to the 48 always-clean tasks: keep the domain mix
of DEFECTIVE (4 raster / 2 vector / 2 3D / 1 geostatistical, scaled to 6), and
within each domain take the task whose reference toolchain length is closest to
the median length of the defective tasks of that domain, lowest ID breaking ties.
Length matters because it correlates with both defect rate and score, so an
unmatched control group would measure difficulty instead of noise.
Result: mean toolchain length 9.2 (control) against 9.4 (defective).
"""

from __future__ import annotations

DEFECTIVE = ("6", "25", "26", "28", "32", "33", "42", "53", "56")
CONTROL = ("3", "4", "11", "35", "43", "55")

GROUPS = {
    "defective": DEFECTIVE,
    "control": CONTROL,
    "defective+control": DEFECTIVE + CONTROL,
}


def task_ids(group: str) -> tuple[str, ...]:
    try:
        return GROUPS[group]
    except KeyError:
        raise SystemExit(
            f"unknown task group {group!r}; choose from {sorted(GROUPS)}"
        ) from None


if __name__ == "__main__":
    for name, ids in GROUPS.items():
        print(f"{name:20s} n={len(ids):<3} {','.join(ids)}")
