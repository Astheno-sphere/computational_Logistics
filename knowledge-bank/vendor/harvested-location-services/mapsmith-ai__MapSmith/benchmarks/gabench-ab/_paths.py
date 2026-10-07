"""Where the GABench checkout and our results live.

The harness never assumes a fixed location: set GABENCH_ROOT to your GABench
clone (and optionally AB_RESULTS to a results directory), or keep GABench as a
sibling of this directory and both defaults just work.
"""

from __future__ import annotations

import os
from pathlib import Path

HARNESS_DIR = Path(__file__).resolve().parent


def gabench_root(required: bool = True) -> Path:
    """The GABench checkout. required=False just resolves the path, for code
    that only needs the pure functions (see test_gate.py)."""
    env = os.environ.get("GABENCH_ROOT", "").strip()
    root = Path(env).resolve() if env else HARNESS_DIR.parent / "GABench"
    if required and not (root / "benchmark" / "benchmark.csv").exists():
        raise SystemExit(
            f"GABench not found at {root}. Clone https://github.com/GeoX-Lab/GABench "
            "and point GABENCH_ROOT at it."
        )
    return root


def results_root() -> Path:
    env = os.environ.get("AB_RESULTS", "").strip()
    return Path(env).resolve() if env else HARNESS_DIR / "results"


def use_gabench_cwd() -> Path:
    """Move into the GABench checkout, because PEA depends on it.

    The evaluator validates every `*_path` argument by asking whether the file
    exists, and its second attempt is a plain relative probe against the
    process's working directory (step_by_step.py: "Check in current working
    directory (for original dataset inputs)"). Dataset inputs are relative
    paths like `dataset/Temperature.geojson`, so a script run from anywhere else
    scores them all as missing: PEA comes out several points lower with no
    warning and every other metric unchanged. Measured on our haiku arm A:
    0.320 from the GABench root, 0.192 from the harness directory — same logs,
    same artifacts, same code. Analysis scripts call this so where the user
    happens to stand cannot change the numbers.
    """
    root = gabench_root()
    os.chdir(root)
    return root


def run_dir(model: str, arm: str, rep: int) -> Path:
    """One directory per (arm, repetition).

    The repetition has to be part of the DIRECTORY, not just the file name:
    GABench's evaluator derives the physical-output directory from the result
    path by replacing the 'results' component with 'output_results' and dropping
    the file name (evaluation/step_by_step.py, process_raw_results). With
    several repetitions under one arm directory they would all map to the same
    output directory, so PEA's file-existence checks would score repetition 3
    against the artifacts of repetition 5 — a silent wrong number, not an error.
    """
    return results_root() / model / f"arm_{arm}_rep{rep}"


def result_file(model: str, arm: str, rep: int) -> Path:
    return run_dir(model, arm, rep) / f"rep{rep}.jsonl"


def resolve_result_file(model: str, arm: str, rep: int = 1) -> Path:
    """Where a finished run's log actually is.

    The published 2026-08 A/B ran before the per-repetition layout existed, so
    its logs live in results/{model}/arm_{arm}/rep1.jsonl. Analysis scripts read
    both layouts; new runs only ever write the current one.
    """
    current = result_file(model, arm, rep)
    if current.exists():
        return current
    legacy = results_root() / model / f"arm_{arm}" / f"rep{rep}.jsonl"
    return legacy if legacy.exists() else current


def inferred_output_dir(result_path: Path) -> Path:
    """The physical-output directory GABench's evaluator will look in.

    Mirrors process_raw_results: the path component literally named 'results'
    becomes 'output_results' and 'output' is appended in place of the file name.
    Assembling artifacts anywhere else means PEA silently sees an empty
    directory and every file-existence check fails — which reads as a bad agent
    instead of a bad harness. Deriving it from the same input as the evaluator
    is what keeps the two in agreement when AB_RESULTS points outside the
    harness directory.
    """
    parts = Path(result_path).resolve().parts
    for i, part in enumerate(parts):
        if part.lower() == "results":
            return Path(*parts[:i], "output_results", *parts[i + 1 : -1], "output")
    raise SystemExit(
        f"{result_path} has no 'results' path component: GABench's evaluator "
        "cannot infer an output directory from it (see process_raw_results)."
    )
