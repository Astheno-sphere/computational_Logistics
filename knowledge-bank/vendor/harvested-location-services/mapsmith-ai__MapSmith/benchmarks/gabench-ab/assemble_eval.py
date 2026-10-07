"""Assemble per-task artifacts into the layout GABench's evaluator expects,
then run its deterministic step-by-step evaluation.

The evaluator infers the physical-output directory from the result path
(process_raw_results): the component named `results` becomes `output_results`
and the file name becomes `output`. That inference is reproduced by
`_paths.inferred_output_dir`, and it must be the only source of truth here —
assembling artifacts anywhere else leaves PEA looking at an empty directory,
which scores as an agent that wrote no files instead of a harness that put them
in the wrong place.

Our per-task archives (artifacts/task_*/**) are snapshots of GABench's output/
directory, so merging them back preserves each task's relative layout and PEA's
file-existence checks see what each run actually produced.

Usage: python assemble_eval.py <model-key> [a b c] [--rep N]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paths import gabench_root, inferred_output_dir, resolve_result_file  # noqa: E402

GABENCH = gabench_root()
PYTHON = sys.executable


def artifacts_dir(results: Path, rep: int) -> Path:
    """`artifacts/` next to the log; the pre-rep-dimension runs used repN_artifacts."""
    current = results.parent / "artifacts"
    legacy = results.parent / f"rep{rep}_artifacts"
    return current if current.exists() or not legacy.exists() else legacy


def assemble(model: str, arm: str, rep: int) -> Path:
    results = resolve_result_file(model, arm, rep)
    if not results.exists():
        raise SystemExit(f"no results to evaluate: {results}")
    src_dir = artifacts_dir(results, rep)
    out = inferred_output_dir(results)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    n = 0
    for task_dir in sorted(src_dir.glob("task_*")):
        for f in task_dir.rglob("*"):
            if f.is_file():
                dest = out / f.relative_to(task_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                n += 1
    print(f"{model} arm {arm} rep {rep}: {n} artifact files -> {out}", flush=True)
    if n == 0:
        print(f"  WARNING: no artifacts found under {src_dir} — every PEA "
              "file-existence check will fail", flush=True)
    return results


def evaluate(results: Path, model: str, arm: str, rep: int) -> None:
    print(f"\n=== EVALUATION {model} arm {arm.upper()} rep {rep} ({results.name}) ===",
          flush=True)
    subprocess.run(
        [PYTHON, str(GABENCH / "evaluation" / "step_by_step.py"),
         "--benchmark", str(GABENCH / "benchmark" / "benchmark.csv"),
         "--result", str(results)],
        cwd=str(GABENCH),
        check=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="assemble artifacts and score a run")
    parser.add_argument("model", help="model key from config.yaml")
    parser.add_argument("arms", nargs="*", default=None, help="arms to score (default: a b)")
    parser.add_argument("--rep", type=int, default=1, help="repetition index")
    args = parser.parse_args()
    for arm_key in args.arms or ["a", "b"]:
        evaluate(assemble(args.model, arm_key, args.rep), args.model, arm_key, args.rep)
