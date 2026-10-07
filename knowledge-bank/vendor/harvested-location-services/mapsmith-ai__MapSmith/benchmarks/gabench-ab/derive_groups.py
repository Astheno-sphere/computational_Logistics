"""Recompute the frozen task groups from the published A/B logs.

The point of freezing DEFECTIVE and CONTROL in task_groups.py is that they were
chosen mechanically, before any arm-C run. This script is how that claim stays
checkable: it re-derives both groups from the four rep-1 logs and compares them
to the frozen tuples, exiting non-zero if they drift.

Usage: python derive_groups.py [model-key ...]      (default: claude haiku)
"""

from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paths import gabench_root, resolve_result_file  # noqa: E402
from task_groups import CONTROL, DEFECTIVE  # noqa: E402

CONTROL_SIZE = 6


def first_round_issues(models: list[str]) -> dict[str, dict[str, int]]:
    """task -> {run: number of validation issues on the FIRST attempt}."""
    per_task: dict[str, dict[str, int]] = defaultdict(dict)
    for model in models:
        for arm in ("a", "b"):
            path = resolve_result_file(model, arm, 1)
            if not path.exists():
                raise SystemExit(f"missing published run: {path}")
            for line in path.read_text(encoding="utf-8").splitlines():
                record = json.loads(line)
                rounds = (record.get("gate_audit") or {}).get("rounds") or []
                # round 0 is the plan as first written: arms A and B both record
                # it, and only B acts on it
                per_task[str(record["task_id"])][f"{model}_{arm}"] = (
                    len(rounds[0]["issues"]) if rounds else -1
                )
    return per_task


def benchmark_meta() -> dict[str, tuple[str, int]]:
    path = gabench_root() / "benchmark" / "benchmark.csv"
    with open(path, encoding="utf-8-sig") as f:
        return {r["ID"]: (r["Domain"], int(r["Toolchain Length"])) for r in csv.DictReader(f)}


def pick_control(
    clean: list[str], defective: list[str], meta: dict[str, tuple[str, int]]
) -> list[str]:
    """Same domain mix as the defective group, matched on toolchain length."""
    by_domain: dict[str, list[str]] = defaultdict(list)
    for task in defective:
        by_domain[meta[task][0]].append(task)
    quotas = {
        domain: round(len(tasks) * CONTROL_SIZE / len(defective))
        for domain, tasks in by_domain.items()
    }
    picked: list[str] = []
    for domain, quota in quotas.items():
        target = statistics.median(meta[t][1] for t in by_domain[domain])
        candidates = sorted(
            (abs(meta[t][1] - target), int(t), t) for t in clean if meta[t][0] == domain
        )
        picked += [c[2] for c in candidates[:quota]]
    return sorted(picked, key=int)


def main() -> int:
    models = sys.argv[1:] or ["claude", "haiku"]
    per_task = first_round_issues(models)
    runs = 2 * len(models)
    complete = [t for t in sorted(per_task, key=int) if len(per_task[t]) == runs]
    defective = [t for t in complete if any(n > 0 for n in per_task[t].values())]
    clean = [t for t in complete if all(n == 0 for n in per_task[t].values())]
    meta = benchmark_meta()
    control = pick_control(clean, defective, meta)

    print(f"runs read: {runs} | tasks with all runs: {len(complete)}")
    print(f"defective ({len(defective)}): {','.join(defective)}")
    print(f"always clean ({len(clean)}): {','.join(clean)}")
    print(f"control ({len(control)}): {','.join(control)}")
    for label, ids in (("defective", defective), ("control", control)):
        lengths = [meta[t][1] for t in ids]
        print(f"  {label:10s} mean toolchain length {statistics.mean(lengths):.2f}")

    drift = []
    if tuple(defective) != DEFECTIVE:
        drift.append(f"DEFECTIVE frozen as {DEFECTIVE}, derived {tuple(defective)}")
    if tuple(control) != CONTROL:
        drift.append(f"CONTROL frozen as {CONTROL}, derived {tuple(control)}")
    if drift:
        print("\nFROZEN GROUPS DRIFTED:")
        for line in drift:
            print(f"  - {line}")
        return 1
    print("\nfrozen groups match the derivation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
