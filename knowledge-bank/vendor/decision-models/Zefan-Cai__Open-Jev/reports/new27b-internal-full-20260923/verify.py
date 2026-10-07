"""Independently audit a completed 27B full panel; stdlib only, no inference.

The CLI has fixed production data/checkpoint pins. The test harness supplies a
small spec directly to audit(); it cannot disable production pins through CLI.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys


SPLITS = ("test", "ood")
CODE_FILES = ("scripts/evaluate_internal_full.py", "scripts/evaluate_checkpoints_parallel.py",
              "jev/model.py", "jev/sharded_model.py", "jev/shared_resources.py", "jev/api.py",
              "jev/data.py", "jev/metrics.py")
THRESHOLDS = (.5, .7, .8, .9, .95, .99)
PRODUCTION = {
    "implementation_commit": "bf818f86a74869f65bc6b93966bf4d5a6f604c03",
    "implementation_sha256": {
        "scripts/evaluate_internal_full.py": "b436e8f6060acd43c90d53800c9127794ee9546c574d4344c27824f2406612bb",
        "scripts/evaluate_checkpoints_parallel.py": "6a271eae0d1382aa2619b2ec547866db3c16b34cbaa6d43a7a15824410ecf493",
        "jev/model.py": "500cedc059878de5070e8589aabe12d13d2df1065b703ab803f8b0928f64d7cc",
        "jev/sharded_model.py": "203ccce480104a3741058ad069ea243688d1e34aafdf6af214e64db7b6fb178b",
        "jev/shared_resources.py": "e910e6e556c8a4e1f6f404f7ae19ed8d5ad8bceb82e792f2b137498c4a989b48",
        "jev/api.py": "493f1fb9c3ffccbdc5f07d555791f9d86b3db7e1a53eef278230211cb6883254",
        "jev/data.py": "97c1764a5090f60476397baf889a864359e0d59b48d99ddf3b34335d3e1b138e",
        "jev/metrics.py": "cb460c78b877a24708a0a8f8ca6b51f9602491f6ea24cd14e9a828c03d92f78b",
    },
    "new": {"manifest": "7b26f948d2ae11f20d7a18be437d1ada616fc479e1596ae94be7596787fe4e54",
            "counts": {"test": 43301, "ood": 84486}, "hard_counts": {"test": 42789, "ood": 83924}, "hashes": {
                "train": "959dac64adc1717d92e9bb80371d4b940b2b5994f9e36e469b3eaed85883fdff",
                "calibration": "6a02712bc6dce4c99cae3acfa54cf049553d12e4b795cfa4c170bd7de5732981",
                "validation": "743ec57c076fee300bfe3e3eb364a8fb629addfd185724c0b66d58633bcd9372",
                "test": "2cd250906060a570e0c596f7bb6ee7fb299fbf314e011a8c72ecb78d70248295",
                "ood": "b575698e0f1006713ca736b96d1d8eb43a54d052e266c0f363b027b288f54498"}},
    "old": {"manifest": "56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97",
            "counts": {"test": 10532, "ood": 15920}, "hard_counts": {"test": 10046, "ood": 15446}, "hashes": {
                "train": "80a9ec19da9c4065b72f7a9e5ff8d67e62c1d1dd2572dfd296e46bfe2ea5a182",
                "calibration": "dd21b26912a6b26a09c3b00ae66a7985ee760e737b94ada4fcc6320406d4db63",
                "validation": "1dc97079d4fc034a1ba16315f801b0a4715b30c2a3874ae05aeb60dd1e40e8bb",
                "test": "fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b",
                "ood": "9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee"}},
    "checkpoint": "c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71",
    "temperature": 2.5343690298472983,
    "model": "Qwen/Qwen3.8-27B", "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def object_hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(payload):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("Nonfinite JSON number: " + value)

    return json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid)


class Snapshot:
    def __init__(self):
        self.files = {}

    def remember(self, name, path, digest):
        require(name not in self.files, "Duplicate snapshot role: " + name)
        self.files[name] = (Path(path), digest)
        return digest

    def json(self, name, path):
        raw = Path(path).read_bytes()
        self.remember(name, path, hashlib.sha256(raw).hexdigest())
        return strict_json(raw)

    def lines(self, name, path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for line in stream:
                require(line.endswith(b"\n") and line.strip(), "Partial/blank JSONL line: " + name)
                digest.update(line)
                yield strict_json(line)
        self.remember(name, path, digest.hexdigest())

    def check(self, name, expected):
        require(self.files[name][1] == expected, "Pinned file hash differs: " + name)

    def stable(self):
        for name, (path, digest) in self.files.items():
            require(file_hash(path) == digest, "Input changed during audit: " + name)


def distribution(values):
    require(isinstance(values, list) and values and all(type(v) in (int, float)
            and math.isfinite(v) and v >= 0 for v in values), "Invalid distribution")
    total = sum(values)
    require(math.isclose(total, 1., rel_tol=1e-6, abs_tol=1e-6), "Distribution does not sum to one")
    return [v / total for v in values]


def load_data(root, name, pin, snapshot):
    manifest = snapshot.json(name + "/manifest.json", root / "manifest.json")
    snapshot.check(name + "/manifest.json", pin["manifest"])
    require(manifest["sha256"] == pin["hashes"], "Manifest split hashes differ")
    rows, ids, groups = {}, set(), {}
    for split, digest in pin["hashes"].items():
        count, heldout = 0, []
        role = name + "/" + split + ".jsonl"
        for row in snapshot.lines(role, root / (split + ".jsonl")):
            count += 1
            require(row["split"] == split and row["id"] not in ids, "Source split/ID mismatch")
            ids.add(row["id"])
            require(groups.setdefault(row["group_id"], split) == split, "Cross-split source parent group")
            if split in SPLITS:
                target = distribution(row["target"])
                require(len(target) == len(row["options"]), "Candidate/target count mismatch")
                heldout.append({**{k: row[k] for k in ("id", "source", "kind", "group_id", "target")},
                                "question_id": row["metadata"].get("question_id", row["kind"]),
                                "row_sha256": object_hash(row)})
        snapshot.check(role, digest)
        require(count == manifest["counts"][split], "Source denominator differs")
        if split in SPLITS:
            require(count == pin["counts"][split], "Frozen held-out denominator differs")
            rows[split] = heldout
    return rows


def checkpoint(root, identity, pin, snapshot):
    required = {"model.json", "temperature.json", "head.pt", "adapter/adapter_config.json",
                "adapter/adapter_model.safetensors"}
    require(root.is_dir() and not root.is_symlink(), "Use original regular checkpoint directory")
    digest, files = hashlib.sha256(), {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink() and (path.is_dir() or path.is_file()), "Nonregular checkpoint path")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            digest.update(name.encode() + b"\0")
            own = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1048576), b""):
                    digest.update(block)
                    own.update(block)
            files[name] = snapshot.remember("checkpoint/" + name, path, own.hexdigest())
    require(digest.hexdigest() == pin["checkpoint"] == identity["checkpoint_sha256"], "Checkpoint tree pin differs")
    require(files == identity["files_sha256"] and required <= set(files), "Checkpoint file inventory differs")
    config = strict_json((root / "model.json").read_bytes())
    temperature = strict_json((root / "temperature.json").read_bytes())
    require(config["model_id"] == pin["model"] and config["revision"] == pin["revision"]
            and config["lora_rank"] == 8 and config["max_length"] == 4096, "Checkpoint configuration differs")
    require(temperature == identity["calibration"] and temperature["split"] == "calibration"
            and temperature["temperature"] == pin["temperature"] == identity["temperature"], "Frozen temperature differs")
    require(identity["tag"] == "new27b" and identity["model"] == pin["model"]
            and identity["revision"] == pin["revision"] and identity["lora_rank"] == 8
            and identity["saved_max_length"] == 4096, "Checkpoint identity differs")


def observation(row):
    p, q = distribution(row["probabilities"]), distribution(row["target"])
    selected = max(range(len(p)), key=p.__getitem__)
    brier = math.fsum((x - y) ** 2 for x, y in zip(p, q))
    return {"confidence": p[selected], "raw_confidence": max(row["probabilities"]),
            "correct": q[selected], "raw_correct": row["target"][selected],
            "hard": max(q) == 1., "raw_hard": max(row["target"]) == 1.,
            "nll": -math.fsum(y * math.log(max(x, 1e-15)) for x, y in zip(p, q)),
            "brier": brier, "expected_brier": brier + 1. - math.fsum(y * y for y in q),
            **{field: row[field] for field in ("source", "kind", "question_id")}}


def metrics(rows):
    """Independent reductions; no imports from evaluator or project metrics."""
    count = len(rows)
    require(count > 0, "Empty metric group")
    hard = [r for r in rows if r["hard"]]
    raw_hard = [r for r in rows if r["raw_hard"]]

    def coverage(threshold):
        selected = [r for r in rows if r["confidence"] >= threshold]
        selected_hard = [r for r in selected if r["hard"]]
        accuracy = math.fsum(r["correct"] for r in selected) / len(selected) if selected else None
        return {"threshold": threshold, "selected": len(selected), "coverage": len(selected) / count,
                "accuracy": math.fsum(r["correct"] for r in selected_hard) / len(selected_hard) if selected_hard else None,
                "expected_accuracy": accuracy, "expected_risk": 1. - accuracy if selected else None}

    buckets = defaultdict(list)
    for row in rows:
        buckets[min(int(row["confidence"] * 15), 14)].append(row)
    probability = {"count": count, "hard_count": len(hard),
                   "accuracy": math.fsum(r["correct"] for r in hard) / len(hard) if hard else None,
                   "expected_accuracy": math.fsum(r["correct"] for r in rows) / count,
                   **{key: math.fsum(r[key] for r in rows) / count for key in ("nll", "brier", "expected_brier")},
                   "multiclass_ece": math.fsum(abs(math.fsum(r["confidence"] - r["correct"] for r in group))
                                               for group in buckets.values()) / count,
                   "ece_bins": 15, "coverage": [coverage(t) for t in THRESHOLDS]}
    return {"count": count, "successful": count, "failed": 0, "inference_coverage": 1.,
            "hard_count": len(raw_hard),
            "accuracy_all_rows_failures_incorrect": math.fsum(r["raw_correct"] for r in raw_hard) / len(raw_hard) if raw_hard else None,
            "expected_accuracy_all_rows_failures_zero": math.fsum(r["raw_correct"] for r in rows) / count,
            "coverage": [{"threshold": t, "selected": sum(r["raw_confidence"] >= t for r in rows),
                          "total": count, "coverage": sum(r["raw_confidence"] >= t for r in rows) / count} for t in THRESHOLDS],
            "probability_metrics_all_rows": probability, "probability_metrics_successful_rows_only": probability}


def grouped(rows):
    result = metrics(rows)
    for field in ("source", "kind", "question_id"):
        groups = defaultdict(list)
        for row in rows:
            key = row["source"] + "/" + row[field] if field == "question_id" else row[field]
            groups[key].append(row)
        result["by_" + field] = {key: metrics(group) for key, group in sorted(groups.items())}
    return result


def compare(actual, expected, path="metrics", differences=None):
    differences = [] if differences is None else differences
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), "Metric keys differ: " + path)
        for key, value in expected.items():
            compare(actual[key], value, path + "/" + key, differences)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), "Metric list differs: " + path)
        for index, value in enumerate(expected):
            compare(actual[index], value, path + "/" + str(index), differences)
    elif type(expected) is float:
        require(type(actual) in (int, float) and math.isfinite(actual)
                and math.isclose(actual, expected, rel_tol=3e-11, abs_tol=3e-11), "Metric value differs: " + path)
        differences.append(abs(actual - expected))
    else:
        require(type(actual) is type(expected) and actual == expected, "Metric count/value differs: " + path)
    return differences


def audit(results, data, old_data, checkpoint_dir, implementation_root, *, spec=PRODUCTION):
    snapshot = Snapshot()
    snapshot.remember("audit/verify.py", Path(__file__), file_hash(__file__))
    summary = snapshot.json("results/summary.json", results / "summary.json")
    require(summary.get("status") == "complete", "Summary is incomplete; no audit pass can be produced")
    progresses = [snapshot.json(f"results/progress-{rank}.json", results / f"progress-{rank}.json") for rank in range(4)]
    require(all(p.get("status") == "complete" for p in progresses), "One or more shards are still running/incomplete")
    identity = snapshot.json("results/identity.json", results / "identity.json")
    require(summary["identity"] == identity, "Summary/identity mismatch")
    require(identity["schema_version"] == 1 and identity["backend"] == "fsdp4" and identity["world_size"] == 4
            and identity["row_batch_size"] == 1 and identity["max_length"] == 4096 and identity["prefix_cache"] is False
            and identity["partition"] == "concatenated_test_ood_index_mod4" and identity["temperature_fitted"] is False,
            "Evaluation execution identity differs")
    require(summary["temperature_fitted"] is False and summary["padding_included_in_denominators"] is False,
            "Temperature fitting or padding contamination reported")
    require(set(identity["implementation_sha256"]) == set(CODE_FILES), "Implementation inventory differs")
    require(identity["implementation_sha256"] == spec["implementation_sha256"], "Frozen implementation identity differs")
    for name in CODE_FILES:
        digest = snapshot.remember("implementation/" + name, implementation_root / name, file_hash(implementation_root / name))
        require(digest == spec["implementation_sha256"][name], "Runtime source snapshot differs from implementation pin: " + name)
    checkpoint(checkpoint_dir, identity["checkpoint"], spec, snapshot)
    new = load_data(data, "new-data", spec["new"], snapshot)
    old = load_data(old_data, "old-data", spec["old"], snapshot)
    subsets = {}
    for split in SPLITS:
        index = {row["id"]: i for i, row in enumerate(new[split])}
        subsets[split] = []
        for row in old[split]:
            require(row["id"] in index and row == new[split][index[row["id"]]], "Original release held-out record absent/changed")
            subsets[split].append(index[row["id"]])
    expected_data = {"manifest_sha256": spec["new"]["manifest"], "split_sha256": spec["new"]["hashes"],
                     "counts": spec["new"]["counts"],
                     "ordered_ids_sha256": {s: object_hash([r["id"] for r in new[s]]) for s in SPLITS},
                     "old_manifest_sha256": spec["old"]["manifest"], "old_split_sha256": spec["old"]["hashes"],
                     "old_counts": spec["old"]["counts"], "old_subset_indices_sha256": object_hash(subsets)}
    require(identity["data"] == expected_data, "Frozen full/old panel identity differs")
    items = [(split, index, row) for split in SPLITS for index, row in enumerate(new[split])]
    total = len(items)
    require(type(summary["total_rows"]) is int and summary["total_rows"] == total, "Full summary denominator differs")
    identity_sha = object_hash(identity)
    probe = snapshot.json("results/probe.json", results / "probe.json")
    probe_indices = [i * (total - 1) // 3 for i in range(4)]
    require(probe["status"] == "passed" and probe["eval_identity_sha256"] == identity_sha
            and probe["probe_indices"] == probe_indices and probe["max_logit_error_allowed"] == .05
            and len(probe["checks"]) == 4, "Different-row parity evidence incomplete")
    for rank, check in enumerate(probe["checks"]):
        row = items[probe_indices[rank]][2]
        require(check["rank"] == rank and check["row_id"] == row["id"] and check["row_sha256"] == row["row_sha256"]
                and check["passed"] is True and check["argmax_equal"] is True
                and type(check["max_logit_error"]) in (int, float) and 0 <= check["max_logit_error"] <= .05,
                "Parity check differs")
    records, observations = [None] * total, [None] * total
    max_probability_error = 0.
    require(set(summary["raw_sha256"]) == {f"shard-{rank}.jsonl" for rank in range(4)}, "Shard inventory differs")
    for rank in range(4):
        expected_count = len(range(rank, total, 4))
        progress = progresses[rank]
        rounds = (total + 3) // 4
        start = progress.get("resumed_at_round")
        require(type(start) is int and 0 <= start <= rounds, "Invalid resume cursor")
        require(progress["rank"] == rank and progress["planned_rows"] == expected_count
                and progress["successful_rows"] == expected_count and progress["failed_rows"] == 0
                and progress["pending_rows"] == 0 and progress["eval_identity_sha256"] == identity_sha
                and progress["padding_forwards"] == max(0, rounds - max(start, expected_count)), "Completed shard denominator differs")
        count = 0
        role = f"results/shard-{rank}.jsonl"
        for result in snapshot.lines(role, results / f"shard-{rank}.jsonl"):
            offset = rank + count * 4
            require(offset < total, "Extra shard row")
            split, index, row = items[offset]
            expected = {**row, "round": count, "split": split, "index": index, "rank": rank,
                        "eval_identity_sha256": identity_sha, "checkpoint_sha256": spec["checkpoint"],
                        "data_split_sha256": spec["new"]["hashes"][split]}
            require(canonical({key: result.get(key) for key in expected}) == canonical(expected), "Shard row order/ID/content identity differs")
            require(result["status"] == "ok", "Raw inference failed")
            logits = result["logits"]
            require(isinstance(logits, list) and len(logits) == len(row["target"])
                    and all(type(x) in (int, float) and math.isfinite(x) for x in logits), "Invalid raw logits")
            maximum = max(logits)
            weights = [math.exp((v - maximum) / spec["temperature"]) for v in logits]
            probabilities = [v / math.fsum(weights) for v in weights]
            stored = result["probabilities"]
            distribution(stored)
            require(len(stored) == len(probabilities), "Probability candidate count differs")
            error = max(abs(a - b) for a, b in zip(stored, probabilities))
            require(error <= 1e-12, "Frozen-temperature softmax mismatch")
            max_probability_error = max(max_probability_error, error)
            require(type(result["input_tokens"]) is int and result["input_tokens"] > 0
                    and type(result["wall_seconds"]) in (int, float) and math.isfinite(result["wall_seconds"])
                    and result["wall_seconds"] >= 0, "Invalid raw timing/token evidence")
            records[offset], observations[offset] = object_hash(result), observation(result)
            count += 1
        require(count == expected_count, "Missing shard rows; full evaluation incomplete")
        snapshot.check(role, summary["raw_sha256"][f"shard-{rank}.jsonl"])
        snapshot.check(role, progress["output_sha256"])
    reproduced, old_reproduced, denominators = {}, {}, {}
    offset = 0
    for split in SPLITS:
        count = 0
        for row in snapshot.lines("results/merged-" + split + ".jsonl", results / ("merged-" + split + ".jsonl")):
            require(count < len(new[split]) and object_hash(row) == records[offset + count], "Merged/sharded record differs")
            count += 1
        require(count == len(new[split]), "Merged split is incomplete")
        panel = observations[offset:offset + count]
        old_panel = [panel[index] for index in subsets[split]]
        require(sum(r["hard"] for r in panel) == spec["new"]["hard_counts"][split]
                and sum(r["hard"] for r in old_panel) == spec["old"]["hard_counts"][split], "Pinned hard-label denominator differs")
        require(all(r["correct"] in (0., 1.) for r in panel if r["hard"]), "Nonbinary correctness on hard target")
        reproduced[split], old_reproduced[split] = grouped(panel), grouped(old_panel)
        denominators[split] = {"count": count, "hard_count": sum(r["hard"] for r in panel),
                               "soft_count": sum(not r["hard"] for r in panel),
                               "hard_correct": sum(int(r["correct"]) for r in panel if r["hard"]),
                               "old_count": len(old_panel), "old_hard_count": sum(r["hard"] for r in old_panel),
                               "old_soft_count": sum(not r["hard"] for r in old_panel),
                               "old_hard_correct": sum(int(r["correct"]) for r in old_panel if r["hard"])}
        offset += count
    differences = compare(summary["splits"], reproduced, "splits")
    compare(summary["old_release_subset"], old_reproduced, "old_release_subset", differences)
    snapshot.stable()
    return {"schema_version": 1, "status": "passed", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
            "method": "Independent standard-library row validation, frozen-temperature softmax and metric reductions; no evaluator/metrics imports or inference.",
            "scope": "Complete original full Test/OOD and unchanged original-release subsets; no incomplete results accepted.",
            "total_rows": total, "old_subset_rows": sum(len(v) for v in subsets.values()),
            "denominators": denominators, "eval_identity_sha256": identity_sha,
            "checkpoint_sha256": spec["checkpoint"], "frozen_temperature": spec["temperature"],
            "pinned_implementation_commit": spec["implementation_commit"],
            "pinned_implementation_sha256": spec["implementation_sha256"],
            "maximum_probability_absolute_error": max_probability_error,
            "maximum_metric_absolute_error": max(differences, default=0.),
            "input_files_sha256": {name: digest for name, (_, digest) in sorted(snapshot.files.items())},
            "checks": {"all_sources_unchanged_during_audit": True, "four_complete_shards_exact_assignment": True,
                       "original_old_rows_content_and_order_preserved": True, "merged_matches_raw": True,
                       "all_full_and_old_grouped_metrics_reproduced": True, "hard_soft_denominators_verified": True,
                       "runtime_implementation_snapshot_verified": True, "checkpoint_tree_and_temperature_verified": True},
            "recomputed_splits": reproduced, "recomputed_old_release_subset": old_reproduced,
            "limitations": ["Validates the saved parity evidence, not a new CUDA parity measurement.",
                            "Applies the saved calibration temperature without refitting it.",
                            "Shared-node wall times are not single-GPU or API latency measurements."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("results", "data", "old-data", "checkpoint", "implementation-root", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), "Audit output already exists; choose a fresh path")
    report = audit(args.results, args.data, args.old_data, args.checkpoint, args.implementation_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "total_rows", "old_subset_rows", "denominators")}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, OverflowError) as error:
        print("Audit failed: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        sys.exit(1)
