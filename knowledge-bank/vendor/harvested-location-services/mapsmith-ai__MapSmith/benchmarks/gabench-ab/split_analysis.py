"""Decisive test: is an aggregate delta caused by the gate, or run-to-run noise?

The gate can only affect tasks whose plan it repaired. If the untouched tasks
move as much as the touched ones, the aggregate delta is variance, not effect.
"""
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paths import resolve_result_file, use_gabench_cwd  # noqa: E402

# PEA is working-directory dependent (see _paths.use_gabench_cwd): this must
# happen before any evaluation, or the PEA column is quietly wrong.
GAB = use_gabench_cwd()
sys.path.insert(0, str(GAB))
from evaluation.step_by_step import evaluate_single_entry, process_raw_results  # noqa: E402

if len(sys.argv) < 2:
    raise SystemExit("usage: python split_analysis.py <model-key>")
model = sys.argv[1]


def touched(arm: str) -> set[str]:
    ids = set()
    path = resolve_result_file(model, arm, 1)
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        rounds = (r.get("gate_audit") or {}).get("rounds", [])
        if len(rounds) > 1:  # a repair round actually ran
            ids.add(str(r["task_id"]))
    return ids


def per_task(arm: str) -> dict:
    entries = process_raw_results(
        str(resolve_result_file(model, arm, 1)),
        str(GAB / "benchmark" / "benchmark.csv"),
    )
    out = {}
    for e in entries:
        r = evaluate_single_entry(e)
        out[str(e["id"])] = {
            "TAO": r["TAO"]["f1"], "TIO": r["TIO"]["score"],
            "TEM": r["TEM"]["score"], "PEA": r["PEA"]["score"],
        }
    return out


gate_tasks = touched("b")
a, b = per_task("a"), per_task("b")
print(f"\nmodello: {model} | task riparati dal gate: {sorted(gate_tasks, key=int)}\n")
print(f"{'gruppo':<22}{'n':>4}{'dTAO':>9}{'dTIO':>9}{'dTEM':>9}{'dPEA':>9}")
for label, ids in (
    ("riparati dal gate", gate_tasks),
    ("NON toccati", set(a) & set(b) - gate_tasks),
):
    ids = sorted(i for i in ids if i in a and i in b)
    if not ids:
        continue
    row = f"{label:<22}{len(ids):>4}"
    for m in ("TAO", "TIO", "TEM", "PEA"):
        deltas = [b[i][m] - a[i][m] for i in ids]
        row += f"{statistics.mean(deltas):>+9.3f}"
    print(row)
print("\nse i NON toccati si muovono come i riparati, il delta aggregato e' rumore.")
