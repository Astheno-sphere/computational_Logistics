"""Synthetic CPU compatibility comparison; produces no model evaluation scores."""
import argparse
import ast
import datetime
import hashlib
import json
from pathlib import Path
import random

import expansion_contract as c
from verify import pinned_source_bytes


def review():
    names = ("jev/metrics.py", "scripts/evaluate_checkpoints_parallel.py")
    source = {name: pinned_source_bytes(name) for name in names}
    # The pinned metrics module contains only stdlib imports and definitions.
    # Execute only its definitions and the producer's summary function: no
    # controller, dataset, model, tensor, capture, or GPU execution is involved.
    metrics = {}
    exec(compile(source[names[0]], names[0], "exec"), metrics)
    tree = ast.parse(source[names[1]])
    summary = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "summarize")
    producer = {"evaluate_probabilities": metrics["evaluate_probabilities"]}
    exec(compile(ast.Module(body=[summary], type_ignores=[]), "<pinned-summarize>", "exec"), producer)
    rng = random.Random(20260920)
    batches = []
    for size in (1, 2, 15, 30, 100, 1000):
        batch = []
        for index in range(size):
            count = rng.randint(2, 10)
            probabilities = metrics["softmax"]([rng.uniform(-30, 30) for _ in range(count)])
            if index % 3 == 0:
                target = rng.randrange(count)
            elif index % 3 == 1:
                target = [float(candidate == index % count) for candidate in range(count)]
            else:
                target = metrics["softmax"]([rng.uniform(-4, 4) for _ in range(count)])
            batch.append({"status": "ok", "probabilities": probabilities, "target": target})
        batches.append(batch)
    batches.append([{"status": "ok", "probabilities": [value, 1-value], "target": [1., 0.]}
                    for value in (.5, .7, .8, .9, .95, .99, 1.)])
    comparison = c.Comparison()
    for index, rows in enumerate(batches):
        comparison.check(c.summarize(rows), producer["summarize"](rows), str(index))
    return {"schema_version": 1, "status": "passed",
            "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "scope": "Synthetic CPU arithmetic compatibility; no model evaluation scores.",
            "producer_commit": c.COMMIT,
            "producer_source_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in source.items()},
            "independent_arithmetic_sha256": c.HELPER_SHA,
            "review_script_sha256": c.info(Path(__file__))["sha256"],
            "seed": 20260920, "synthetic_batches": len(batches),
            "synthetic_rows": sum(map(len, batches)),
            "cases": ["integer targets", "one-hot targets", "soft targets", "varying class counts",
                      "ties", "coverage threshold boundaries", "zero and unit probabilities"],
            "numeric_leaves_compared": comparison.numeric_leaves,
            "max_absolute_error": comparison.max_error,
            "tolerance": {"relative": 1e-10, "absolute": 1e-10},
            "model_inference_performed": False, "model_evaluation_complete": False,
            "real_dataset_rows_read": False, "tensor_loading_performed": False,
            "ssh_or_gpu_used": False, "model_scores": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    c.require(not args.output.exists() and not args.output.is_symlink(), "Preserve existing review result")
    result = review()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({key: result[key] for key in ("status", "synthetic_rows", "numeric_leaves_compared", "max_absolute_error")}))


if __name__ == "__main__":
    main()
