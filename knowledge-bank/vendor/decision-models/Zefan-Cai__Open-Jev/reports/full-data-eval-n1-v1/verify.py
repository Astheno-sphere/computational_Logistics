"""Independent CPU audit of completed release-v2 full-data evaluations.

Reads copied original outputs and checkpoint bytes; never imports jev, loads
tensors, refits calibration, contacts a host, or runs model/GPU inference.
"""
import argparse
from collections import defaultdict
import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
COMMIT = "99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e"
MANIFEST_SHA = "56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97"
SPLITS = ("test", "ood")
COUNTS = {"train": 80816, "calibration": 4761, "validation": 3792, "test": 10532, "ood": 15920}
HASHES = {
    "train": "80a9ec19da9c4065b72f7a9e5ff8d67e62c1d1dd2572dfd296e46bfe2ea5a182",
    "calibration": "dd21b26912a6b26a09c3b00ae66a7985ee760e737b94ada4fcc6320406d4db63",
    "validation": "1dc97079d4fc034a1ba16315f801b0a4715b30c2a3874ae05aeb60dd1e40e8bb",
    "test": "fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b",
    "ood": "9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee",
}
MODELS = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc", "8c37b393c27d2b58009463a89dd1a873b7c010ecd1b8c184c7ada5efe13f8bfb"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a", "a691105dd5751bfcf72d276a6ce075d45054db77ae3272e87b5f07b2bd7e2193"),
}
THRESHOLDS = (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)
SOURCE_FILES = ("scripts/evaluate_checkpoints_parallel.py", "jev/model.py", "jev/api.py",
                "jev/data.py", "jev/metrics.py", "jev/serving.py")
EVIDENCE_FILES = {"plan.json", "summary.json", "merged-test.jsonl", "merged-ood.jsonl"} | {
    f"shard-{rank}.{suffix}" for rank in range(4) for suffix in ("json", "jsonl", "log")}
INFERENCE_FILES = {"checkpoint/adapter/adapter_config.json", "checkpoint/adapter/adapter_model.safetensors",
                   "checkpoint/head.pt", "checkpoint/model.json", "checkpoint/temperature.json"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    def invalid(value):
        raise ValueError("nonfinite JSON value: "+value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def read(path):
    return decode(Path(path).read_bytes())


def records(path):
    with Path(path).open("rb") as stream:
        return [decode(line) for line in stream if line.strip()]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def objsha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def distribution(values):
    require(isinstance(values, list) and bool(values), "empty/non-list distribution")
    require(all(type(x) in (int, float) and math.isfinite(x) and x >= 0 for x in values), "invalid distribution")
    total = sum(values)
    require(math.isclose(total, 1, rel_tol=1e-6, abs_tol=1e-6), "distribution sum differs from one")
    return [x/total for x in values]


def probability_metrics(values):
    """Independent arithmetic with the historical public metric definitions."""
    observations, nll, brier, expected_brier = [], [], [], []
    bins = defaultdict(list)
    for row in values:
        p = distribution(row["probabilities"])
        target = row["target"]
        q = [float(i == target) for i in range(len(p))] if type(target) is int else distribution(target)
        require(len(q) == len(p) and sum(q) > 0, "target class count/range")
        predicted = p.index(max(p))
        confidence, correct, hard = p[predicted], q[predicted], max(q) == 1
        observations.append((confidence, correct, hard))
        bins[min(14, int(confidence*15))].append((confidence, correct))
        nll.append(-sum(t*math.log(max(x, 1e-15)) for x, t in zip(p, q)))
        squared = sum((x-t)**2 for x, t in zip(p, q))
        brier.append(squared)
        expected_brier.append(squared+1-sum(t*t for t in q))
    def selected(items):
        hard = [correct for _, correct, is_hard in items if is_hard]
        expected = sum(row[1] for row in items)/len(items) if items else None
        return {"selected": len(items), "coverage": len(items)/len(values),
                "accuracy": sum(hard)/len(hard) if hard else None,
                "expected_accuracy": expected, "expected_risk": 1-expected if items else None}
    overall = selected(observations)
    return {"count": len(values), "hard_count": sum(item[2] for item in observations),
            "accuracy": overall["accuracy"], "expected_accuracy": overall["expected_accuracy"],
            "nll": sum(nll)/len(values), "brier": sum(brier)/len(values),
            "expected_brier": sum(expected_brier)/len(values), "ece_bins": 15,
            "multiclass_ece": sum(abs(sum(c for c, _ in group)-sum(t for _, t in group)) for group in bins.values())/len(values),
            "coverage": [{"threshold": t, **selected([item for item in observations if item[0] >= t])} for t in THRESHOLDS]}


def summarize(values):
    require(bool(values) and all(row["status"] == "ok" for row in values), "Cannot certify failed/incomplete predictions")
    metrics = probability_metrics(values)
    # Historical outer fields use the original target; inner metrics normalize it.
    hard_count, correct, hard_correct = 0, [], []
    for row in values:
        target, predicted = row["target"], row["probabilities"].index(max(row["probabilities"]))
        hard = type(target) is int or max(target) == 1
        value = float(predicted == target) if type(target) is int else target[predicted]
        hard_count += hard
        correct.append(value)
        if hard:
            hard_correct.append(value)
    coverage = []
    for threshold in THRESHOLDS:
        count = sum(max(row["probabilities"]) >= threshold for row in values)
        coverage.append({"threshold": threshold, "selected": count, "total": len(values), "coverage": count/len(values)})
    return {"count": len(values), "successful": len(values), "failed": 0, "inference_coverage": 1.0,
            "hard_count": hard_count, "accuracy_all_rows_failures_incorrect": sum(hard_correct)/hard_count if hard_count else None,
            "expected_accuracy_all_rows_failures_zero": sum(correct)/len(values), "coverage": coverage,
            "probability_metrics_all_rows": metrics, "probability_metrics_successful_rows_only": metrics}


class Comparison:
    def __init__(self):
        self.numeric_leaves = 0
        self.max_error = 0.0

    def check(self, expected, actual, path):
        if isinstance(expected, dict):
            require(isinstance(actual, dict) and expected.keys() == actual.keys(), "metric keys: "+path)
            for key in expected:
                self.check(expected[key], actual[key], path+"/"+str(key))
        elif isinstance(expected, list):
            require(isinstance(actual, list) and len(expected) == len(actual), "metric list: "+path)
            for index, (a, b) in enumerate(zip(expected, actual)):
                self.check(a, b, path+"/"+str(index))
        elif expected is None:
            require(actual is None, "metric null: "+path)
        else:
            require(type(actual) in (int, float) and math.isfinite(actual), "metric nonnumeric: "+path)
            require(math.isclose(expected, actual, rel_tol=1e-10, abs_tol=1e-10), "metric difference: "+path)
            self.numeric_leaves += 1
            self.max_error = max(self.max_error, abs(expected-actual))


def audit(args):
    evidence, checkpoint_root, package = args.evidence, args.checkpoint_evidence, args.package
    weight_package = args.weight_package or ROOT/"runs/model-packages/release-v2-fullpass-n1-v1"/args.model
    capture = read(evidence/"capture.json")
    require(capture["status"] == "copied_completed_model" and capture["read_only_remote"] is True, "capture incomplete")
    source = capture["source_before"]
    require(source == capture["source_after"], "source changed during capture")
    require(source["tag"] == args.model and source["hostname"] == "kwade5342000001" and source["source_commit"] == COMMIT, "source identity")
    require(set(source["files"]) == EVIDENCE_FILES, "complete 16-file source evidence set")
    for name, info in source["files"].items():
        require(sha(evidence/name) == info["sha256"] and (evidence/name).stat().st_size == info["bytes"], "copied bytes: "+name)
    plan, summary = read(evidence/"plan.json"), read(evidence/"summary.json")
    require(summary["status"] == "complete" and plan["tag"] == args.model, "model summary is not complete")
    require(plan["partition"] == "Within each frozen split, file index modulo four", "wrong historical partition")
    controller_states = {}
    for label in ("before", "after"):
        path, info = evidence/f"controller-manifest-{label}.json", capture["controller_manifests"][label]
        require(sha(path) == info["sha256"] and path.stat().st_size == info["bytes"], "captured controller bytes: "+label)
        controller = read(evidence/f"controller-manifest-{label}.json")
        require(controller["model_order"] == ["2b", "9b"] and controller["phase"] == "parallel_data_eval", "controller protocol")
        state = controller["models"][args.model]
        require(state["status"] == "complete" and state["exit_codes"] == [0]*4, "workers not reaped successfully")
        require([child["rank"] for child in state["children"]] == list(range(4)), "controller worker ranks")
        require([child["gpu_uuid"] for child in state["children"]] == plan["gpu_uuids"], "controller physical GPUs")
        require(controller["gpu_uuids"] == plan["gpu_uuids"] and len(set(plan["gpu_uuids"])) == 4, "GPU UUID identity")
        for key in ("data_identity", "implementation_sha256", "policy"):
            require(controller[key] == plan[key], "controller/plan "+key)
        controller_states[label] = {"status": controller["status"], "current_model": controller.get("current_model"),
            "gpus_free_after_cleanup": controller.get("gpus_free_after_cleanup"), "sha256": sha(evidence/f"controller-manifest-{label}.json")}
    implementation = {name: hashlib.sha256(subprocess.check_output(["git", "-C", str(ROOT), "show", COMMIT+":"+name])).hexdigest() for name in SOURCE_FILES}
    require(implementation == plan["implementation_sha256"] == source["implementation_sha256"], "actual source bytes differ from pinned commit")
    policy_sha = hashlib.sha256(subprocess.check_output(["git", "-C", str(ROOT), "show", COMMIT+":state/auto_research/resource_policy.json"])).hexdigest()
    require(plan["policy"] == {"hostname": "kwade5342000001", "policy_sha256": policy_sha, "gpu_indices": [0, 1, 2, 3]}, "resource policy")
    require(source["policy_sha256"] == policy_sha, "snapshot resource policy")

    data_manifest = read(args.data/"manifest.json")
    require(sha(args.data/"manifest.json") == MANIFEST_SHA and data_manifest["sha256"] == HASHES and data_manifest["counts"] == COUNTS, "frozen dataset manifest")
    data, ids, groups, calibration_ids = {}, set(), {}, set()
    for split, digest in HASHES.items():
        require(sha(args.data/(split+".jsonl")) == digest == source["data_files_sha256"][split+".jsonl"], "dataset bytes: "+split)
        values = records(args.data/(split+".jsonl"))
        require(len(values) == COUNTS[split], "dataset count: "+split)
        for row in values:
            require(row["id"] not in ids and row["split"] == split, "duplicate/wrong split dataset ID")
            ids.add(row["id"])
            require(groups.setdefault(row["group_id"], split) == split, "group crosses splits")
        if split in SPLITS:
            data[split] = values
        elif split == "calibration":
            calibration_ids = {row["id"] for row in values}
    identity = {"manifest_sha256": MANIFEST_SHA, "split_sha256": HASHES,
                "counts": {split: COUNTS[split] for split in SPLITS},
                "ordered_ids_sha256": {split: objsha([row["id"] for row in data[split]]) for split in SPLITS}}
    require(source["data_files_sha256"]["manifest.json"] == MANIFEST_SHA, "remote manifest bytes")
    require(identity == plan["data_identity"] == summary["data_identity"], "data identity mismatch")

    expected = read(package/"source-evaluation-identity.json")
    checkpoint = plan["checkpoint"]
    require(expected["code_commit"] == COMMIT and expected["checkpoint_identity"] == checkpoint == summary["checkpoint"], "checkpoint/source identity")
    require(expected["data_identity"] == identity, "package source dataset identity")
    model, revision, expected_sha = MODELS[args.model]
    require((checkpoint["model"], checkpoint["revision"], checkpoint["checkpoint_sha256"]) == (model, revision, expected_sha), "fixed completed checkpoint")
    run, trained = read(checkpoint_root/"run.json"), read(checkpoint_root/"summary.json")
    require(trained["status"] == "complete" and trained["steps"] == run["steps"] == 20204 and trained["trained_rows_consumed"] == 80816, "training incomplete")
    require(run["model"] == model and run["revision"] == revision and run["data_sha256"] == HASHES, "training identity")
    completion = checkpoint["training_completion"]
    require(completion["run_sha256"] == sha(checkpoint_root/"run.json") and completion["summary_sha256"] == sha(checkpoint_root/"summary.json"), "training evidence bytes")
    require(completion["steps"] == 20204 and completion["trained_rows_consumed"] == 80816, "checkpoint completion cursor")
    require(type(completion["checkpoint_reload_max_error"]) in (int, float) and 0 <= completion["checkpoint_reload_max_error"] <= .05, "saved reload check")
    require(source["checkpoint_state"] == {"checkpoint_sha256": expected_sha,
        "run_sha256": completion["run_sha256"], "summary_sha256": completion["summary_sha256"]}, "remote current checkpoint identity")
    snapshots = sorted(checkpoint_root.glob("source-snapshot-*.json"))
    require(bool(snapshots), "original source checkpoint snapshot missing")
    checkpoint_snapshot = read(snapshots[-1])
    require({"checkpoint/"+name: info for name, info in source["checkpoint_files"].items()} == checkpoint_snapshot["checkpoint_current_bytes"], "source checkpoint bytes changed since package snapshot")
    for name, info in checkpoint_snapshot["files"].items():
        require(sha(checkpoint_root/name) == info["sha256"] and (checkpoint_root/name).stat().st_size == info["bytes"], "source snapshot evidence: "+name)
    current = checkpoint_root/"checkpoint"
    temperature = read(current/"temperature.json")
    require(temperature == checkpoint["calibration"] and temperature["temperature"] == checkpoint["temperature"] == trained["temperature"], "saved temperature identity")
    require(temperature["split"] == "calibration" and temperature["n"] == len(run["calibration_ids"]) == 512, "calibration count")
    require(set(run["calibration_ids"]) <= calibration_ids and len(set(run["calibration_ids"])) == 512, "calibration IDs")
    require(temperature["ids_sha256"] == hashlib.sha256(json.dumps(run["calibration_ids"]).encode()).hexdigest(), "ordered calibration IDs")
    require(math.isfinite(checkpoint["temperature"]) and checkpoint["temperature"] > 0 and checkpoint["max_length"] == 4096, "temperature/context configuration")
    package_manifest, provenance = read(package/"manifest.json"), read(package/"provenance.json")
    require(sha(weight_package/"manifest.json") == sha(package/"manifest.json"), "local weight package manifest")
    require({name for name in package_manifest["files"] if name.startswith("checkpoint/")} == INFERENCE_FILES, "complete packaged inference file set")
    require(sha(weight_package/"provenance.json") == sha(package/"provenance.json"), "package provenance metadata copy")
    bound_package_files = {}
    for name, info in package_manifest["files"].items():
        require(sha(weight_package/name) == info["sha256"] and (weight_package/name).stat().st_size == info["bytes"], "local package file differs: "+name)
        if name.startswith("checkpoint/"):
            require(source["checkpoint_files"].get(name.removeprefix("checkpoint/")) == info, "packaged inference file differs: "+name)
            bound_package_files[name] = info
    require(provenance["calibration"] == temperature and provenance["data"]["sha256"] == HASHES, "package provenance")
    for name in ("run.json", "summary.json", "calibration.jsonl"):
        require(provenance["source_evidence"][name]["sha256"] == sha(checkpoint_root/name), "package source evidence: "+name)

    merged, worker_reports, maximum_probability_error = {}, [], 0.0
    for rank in range(4):
        assigned = [(split, index, row) for split in SPLITS for index, row in enumerate(data[split]) if index % 4 == rank]
        assignment = {"counts": {split: sum(s == split for s, _, _ in assigned) for split in SPLITS},
                      "ordered_rows_sha256": objsha([(split, index, row["id"], objsha(row)) for split, index, row in assigned])}
        report = read(evidence/f"shard-{rank}.json")
        require(len(assigned) == 6613 and assignment == plan["assignments"][str(rank)] == report["assignment"], "shard assignment")
        require(report["status"] == "complete" and report["rank"] == rank and report["checkpoint"] == checkpoint, "shard completion identity")
        require(report["gpu_uuid"] == plan["gpu_uuids"][rank] and report["plan_sha256"] == sha(evidence/"plan.json"), "shard plan/GPU binding")
        require(report["output_sha256"] == sha(evidence/f"shard-{rank}.jsonl"), "shard output bytes")
        require(report["counts"] == {"rows": 6613, "ok": 6613, "error": 0}, "shard error/missing predictions")
        actual = records(evidence/f"shard-{rank}.jsonl")
        require(len(actual) == len(assigned), "shard denominator")
        for result, (split, index, row) in zip(actual, assigned):
            row_identity = {"id": row["id"], "split": split, "index": index, "shard_rank": rank,
                "source": row["source"], "group_id": row["group_id"], "kind": row["kind"], "target": row["target"],
                "row_sha256": objsha(row), "checkpoint": checkpoint, "question_id": row["metadata"].get("question_id", row["kind"])}
            require(all(result.get(key) == value for key, value in row_identity.items()), "raw row identity/order")
            require((split, index) not in merged and result["status"] == "ok", "duplicate/failed raw prediction")
            logits, probabilities = result["logits"], result["probabilities"]
            require(len(logits) == len(probabilities) == len(row["options"]) and all(type(x) in (int, float) and math.isfinite(x) for x in logits), "logit shape/value")
            distribution(probabilities)
            require(type(result["input_tokens"]) is int and result["input_tokens"] > 0, "input token count")
            weights = [math.exp((x-max(logits))/checkpoint["temperature"]) for x in logits]
            recomputed = [x/sum(weights) for x in weights]
            error = max(abs(a-b) for a, b in zip(recomputed, probabilities))
            require(error <= 1e-12, "raw probabilities differ from saved-temperature softmax")
            maximum_probability_error = max(maximum_probability_error, error)
            merged[split, index] = result
        worker_reports.append(report)
    require(len(merged) == len({row["id"] for row in merged.values()}) == 26452, "full held-out coverage")
    require(summary["workers"] == worker_reports, "summary worker reports")
    comparison, metrics, group_counts, group_hashes = Comparison(), {}, {}, {}
    for split in SPLITS:
        original = records(evidence/f"merged-{split}.jsonl")
        values = [merged[split, index] for index in range(COUNTS[split])]
        require(original == values, "merged file differs from original shard rows/order")
        recomputed = summarize(values)
        counts, hashes = {}, {}
        for field in ("source", "kind", "group_id"):
            buckets = defaultdict(list)
            for row in values:
                buckets[row[field]].append(row)
            grouped = {name: summarize(rows) for name, rows in sorted(buckets.items())}
            recomputed["by_"+field] = grouped
            counts[field], hashes[field] = len(grouped), objsha(grouped)
        comparison.check(recomputed, summary["splits"][split], split)
        metrics[split] = {key: value for key, value in recomputed.items() if key != "by_group_id"}
        group_counts[split], group_hashes[split] = counts, hashes
    require(set(summary["splits"]) == set(SPLITS), "unexpected/missing summary split")
    return {"schema_version": 1, "status": "passed", "audited_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Independent CPU arithmetic and source-byte audit of this completed trained checkpoint; no model loading, inference, calibration fitting or remote activity by verifier.",
        "model": model, "revision": revision, "evaluation_source_commit": COMMIT,
        "checkpoint": checkpoint, "package_bound_inference_files": bound_package_files,
        "controller_states": controller_states, "model_evaluation_complete": True,
        "controller_complete_at_capture": controller_states["after"]["status"] == "complete" and controller_states["after"]["gpus_free_after_cleanup"] is True,
        "data_identity": identity, "all_five_split_counts": COUNTS, "all_dataset_ids_unique": True, "groups_do_not_cross_splits": True,
        "coverage": {"expected_rows": 26452, "unique_ids": 26452, "shard_rows": [6613]*4,
                     "missing": 0, "duplicate": 0, "failed": 0, "merged_original_order_verified": True},
        "verification": {"verifier_sha256": sha(Path(__file__)), "capture_sha256": sha(evidence/"capture.json"),
            "source_files": source["files"], "implementation_sha256": implementation,
            "numeric_metric_leaves_checked": comparison.numeric_leaves, "max_metric_absolute_error": comparison.max_error,
            "max_raw_probability_error": maximum_probability_error, "group_counts": group_counts,
            "independently_recomputed_group_metrics_sha256": group_hashes,
            "package_manifest_sha256": sha(package/"manifest.json"), "package_provenance_sha256": sha(package/"provenance.json"),
            "checkpoint_source_snapshot_sha256": sha(snapshots[-1]),
            "package_source_evaluation_identity_sha256": sha(package/"source-evaluation-identity.json")},
        "metrics": metrics, "full_data_baseline_evaluated": False, "full_data_training_gain": None,
        "limitations": ["No full-data baseline exists in this run. Earlier 512-row-per-split baseline results cannot establish full-data training gain.",
            "Per-group metrics were recomputed and compared for every group; compact report retains source/kind metrics and group counts/hashes. Original complete summary remains in ignored evidence.",
            "Snapshot/checkpoint hashes bind this evaluation to the packaged inference files; the trainer's historical reload lacked a contemporaneous weight digest.",
            "Synthetic held-out decision accuracy is not end-to-end game, browser or flight performance. Four-replica wall time is not single-GPU latency."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--checkpoint-evidence", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--weight-package", type=Path, help="Defaults to runs/model-packages/release-v2-fullpass-n1-v1/<model>")
    parser.add_argument("--data", type=Path, default=ROOT/"data/release-v2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), "Preserve existing audit; output already exists")
    try:
        result = audit(args)
    except Exception as error:
        result = {"status": "failed", "model": args.model, "error_type": type(error).__name__, "error": str(error),
                  "model_evaluation_complete": False, "metrics": None}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+"\n")
        raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": result["status"], "model": args.model, "rows": 26452,
                      "numeric_metric_leaves_checked": result["verification"]["numeric_metric_leaves_checked"],
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
