"""Independent offline CPU audit of final 27B expansion predictions and bytes.

No project/model imports, tensor loading, calibration fitting or network calls.
"""
import argparse
from collections import defaultdict
import datetime
import hashlib
import json
import math
from pathlib import Path
import re

import expansion_contract as c


class Inputs:
    def __init__(self):
        self.bound = {}

    def bind(self, root, name, expected=None):
        path = c.safe_file(root, name)
        actual = c.info(path)
        c.require(expected is None or actual == expected, "Evidence bytes differ: "+name)
        c.require(path not in self.bound or self.bound[path] == actual, "Evidence changed: "+name)
        self.bound[path] = actual
        return path

    def read(self, root, name):
        return c.decode(self.bind(root, name).read_bytes())

    def rows(self, root, name):
        with self.bind(root, name).open("rb") as stream:
            for line in stream:
                if line.strip():
                    yield c.decode(line)

    def unchanged(self):
        for path, expected in self.bound.items():
            c.require(c.info(path) == expected, "Evidence changed during audit: "+path.name)


PINNED_SOURCE_ROOT = Path(__file__).resolve().parent / "pinned-source"


def pinned_source_bytes(name):
    c.require(name in c.PINNED_SOURCE_HASHES, "Unknown pinned source")
    raw = c.safe_file(PINNED_SOURCE_ROOT, name).read_bytes()
    c.require(hashlib.sha256(raw).hexdigest() == c.PINNED_SOURCE_HASHES[name],
              "Pinned producer bytes differ: " + name)
    return raw


def pinned_source():
    # Read the original producer archive instead of requiring private Git history.
    c.require(set(c.PINNED_SOURCE_HASHES) == set(c.SOURCE_FILES), "Pinned source file set")
    return {name: hashlib.sha256(pinned_source_bytes(name)).hexdigest()
            for name in c.SOURCE_FILES}, c.PINNED_POLICY_SHA


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def dataset(inputs, path, source):
    manifest = inputs.read(path, "manifest.json")
    c.require(c.info(path/"manifest.json")["sha256"] == c.MANIFEST_SHA
              and manifest["counts"] == c.COUNTS and manifest["sha256"] == c.HASHES, "Frozen expansion dataset identity")
    c.require(set(source["data_files"]) == {"manifest.json"} | {s+".jsonl" for s in c.HASHES}, "Source dataset file set")
    inputs.bind(path, "manifest.json", source["data_files"]["manifest.json"])
    rows, calibration, ids, groups = {}, {}, set(), {}
    for split, digest in c.HASHES.items():
        name = split+".jsonl"
        bound = inputs.bind(path, name, source["data_files"][name])
        c.require(c.info(bound)["sha256"] == digest, "Frozen split bytes: "+split)
        count = 0
        if split in c.SPLITS:
            rows[split] = []
        for row in inputs.rows(path, name):
            count += 1
            c.require(row["id"] not in ids and row["split"] == split, "Duplicate/wrong split dataset ID")
            ids.add(row["id"])
            c.require(groups.setdefault(row["group_id"], split) == split, "Group crosses dataset splits")
            if split in c.SPLITS:
                rows[split].append(row)
            elif split == "calibration":
                calibration[row["id"]] = {"target": row["target"], "options": row["options"]}
        c.require(count == c.COUNTS[split], "Frozen split row count: "+split)
    identity = {"dataset_profile": c.PROFILE, "partition": c.PARTITION,
                "manifest_sha256": c.MANIFEST_SHA, "split_sha256": c.HASHES,
                "counts": {s:c.COUNTS[s] for s in c.SPLITS}, "total_rows": sum(c.COUNTS[s] for s in c.SPLITS),
                "ordered_ids_sha256": {s:c.objsha([r["id"] for r in rows[s]]) for s in c.SPLITS}}
    return rows, calibration, identity


def training_identity(inputs, root, calibration, test_rows):
    run, summary = inputs.read(root, "run.json"), inputs.read(root, "summary.json")
    model, temperature = inputs.read(root, "checkpoint/model.json"), inputs.read(root, "checkpoint/temperature.json")
    c.require(summary.get("status") == "complete" and summary.get("inference_ready", True) is not False, "Training incomplete")
    c.require(run["model"] == summary["model"] == model["model_id"] == c.MODEL
              and run["revision"] == model["revision"] == c.REVISION, "Pinned 27B model/revision")
    c.require(run["steps"] == summary["steps"] == c.STEPS and
              summary["trained_rows_consumed"] == run["training_rows_consumed"] == c.COUNTS["train"], "Full DDP completion cursor")
    c.require(c.STEPS*4 == c.COUNTS["train"] and run["accumulation"] == 4 and run["train_rows"] == 0
              and run["training_sampling"] == "shuffled" and run["seed"] == c.SEED, "DDP training selection")
    c.require(run["data_sha256"] == c.HASHES, "Training dataset hashes")
    c.require(run["initialization"] in ("fresh_pinned_upstream", "strict_same_run_ddp_resume")
              and run.get("commit") == c.TRAINING_COMMIT
              and run.get("identity_sha256") == c.RUN_IDENTITY, "Training initialization/source identity")
    ddp = run["distribution"]
    c.require(ddp == summary["distribution"] and ddp["world_size"] == ddp["global_batch_size"] == 4
              and ddp["local_rows_per_step"] == 1 and ddp["backend"] == "nccl" and ddp["device_type"] == "cuda"
              and ddp["bitwise_single_process_equivalence"] is False
              and re.fullmatch(r"[0-9a-f]{64}", ddp.get("implementation_sha256", "")), "Four-rank CUDA DDP provenance")
    c.require(run["max_length"] == model["max_length"] == 4096 and run["lora_rank"] == model["lora_rank"] == 8
              and model["method"] == "independent_candidate_lora_nll_brier", "Checkpoint inference configuration")
    log = list(inputs.rows(root, "training.jsonl"))
    c.require([r.get("step") for r in log] == list(range(1, c.STEPS+1)), "Incomplete/noncontiguous training log")
    c.require(all(r.get("world_size") == r.get("global_batch_size") == 4 for r in log)
              and all(finite(r.get(key)) for r in log for key in ("loss", "gradient_norm", "elapsed_seconds")), "Invalid training log")
    ids = run["calibration_ids"]
    c.require(len(ids) == len(set(ids)) == run["calibration_rows"] == c.CALIBRATION_N
              and set(ids) <= calibration.keys(), "Fixed calibration coverage")
    c.require(hashlib.sha256(json.dumps(ids).encode()).hexdigest() == c.CALIBRATION_IDS_SHA
              and temperature["ids_sha256"] == c.CALIBRATION_IDS_SHA and temperature["split"] == "calibration"
              and temperature["n"] == c.CALIBRATION_N, "Fixed calibration identity")
    c.require(finite(temperature["temperature"]) and temperature["temperature"] > 0
              and temperature["temperature"] == summary["temperature"], "Saved calibration temperature")
    predicted = list(inputs.rows(root, "calibration.jsonl"))
    c.require([r.get("id") for r in predicted] == ids, "Saved calibration prediction IDs")
    for result in predicted:
        row = calibration[result["id"]]
        c.require(result["target"] == row["target"] and len(result["logits"]) == len(row["options"])
                  and all(finite(x) for x in result["logits"]), "Invalid saved calibration logits/target")
    trained = list(inputs.rows(root, "trained_test.jsonl"))
    reloaded = list(inputs.rows(root, "reload_check.jsonl"))
    test_by_id = {r["id"]:r for r in test_rows}
    c.require(run["eval_rows"] == c.CALIBRATION_N and len(trained) == c.CALIBRATION_N
              and [r["id"] for r in trained] == run["evaluation_ids"] and len(reloaded) == 1, "Saved reload/sample evidence coverage")
    for result in [*trained, *reloaded]:
        row = test_by_id[result["id"]]
        c.require(result["target"] == row["target"] and len(result["logits"]) == len(row["options"])
                  and all(finite(x) for x in result["logits"]), "Invalid saved test/reload logits")
    c.require(reloaded[0]["id"] == trained[0]["id"], "Reload row differs from reference")
    error = max(abs(a-b) for a,b in zip(reloaded[0]["logits"], trained[0]["logits"]))
    recorded = summary["checkpoint_reload_max_error"]
    c.require(finite(recorded) and 0 <= recorded <= .05 and error <= .05
              and math.isclose(recorded, error, rel_tol=0, abs_tol=1e-9), "Saved checkpoint reload check")
    adapter = inputs.read(root, "checkpoint/adapter/adapter_config.json")
    c.require(adapter["peft_type"] == "LORA" and adapter["r"] == 8
              and adapter.get("base_model_name_or_path") in (None, "", c.MODEL)
              and adapter.get("revision") in (None, c.REVISION), "Adapter upstream identity")
    completion = {"steps": c.STEPS, "trained_rows_consumed": c.COUNTS["train"], "checkpoint_reload_max_error": recorded,
                  "run_sha256": c.info(root/"run.json")["sha256"], "summary_sha256": c.info(root/"summary.json")["sha256"],
                  "distribution": ddp, "run_identity_sha256": run["identity_sha256"],
                  "calibration_predictions_sha256": c.info(root/"calibration.jsonl")["sha256"],
                  "training_log_sha256": c.info(root/"training.jsonl")["sha256"]}
    identity = {"dataset_profile": c.PROFILE, "model": c.MODEL, "revision": c.REVISION,
                "checkpoint_sha256": c.checkpoint_digest(root/"checkpoint"), "temperature": temperature["temperature"],
                "calibration": temperature, "max_length": 4096, "training_completion": completion}
    return identity, run


def package_identity(inputs, package, training, checkpoint, run):
    manifest = inputs.read(package, "manifest.json")
    c.require(manifest["kind"] == "local_inference_weight_package" and manifest["model"] == c.MODEL
              and manifest["revision"] == c.REVISION and manifest["weights_license"] == "Apache-2.0", "Wrong inference package")
    expected_names = {"checkpoint/"+name for name in c.WEIGHT_FILES}
    c.require({name for name in manifest["files"] if name.startswith("checkpoint/")} == expected_names, "Package inference file set")
    c.require(c.file_set(package) == set(manifest["files"]) | {"manifest.json"}, "Unlisted/missing package files")
    for name, expected in manifest["files"].items():
        inputs.bind(package, name, expected)
        if name in expected_names:
            c.require(expected == c.info(c.safe_file(training, name)), "Packaged weights differ from evaluated checkpoint")
    provenance = inputs.read(package, "provenance.json")
    c.require(provenance["model"] == c.MODEL and provenance["revision"] == c.REVISION
              and provenance["calibration"] == checkpoint["calibration"], "Package model/calibration provenance")
    data = provenance["data"]
    c.require(data["name"] == c.PROFILE and data["manifest_sha256"] == c.MANIFEST_SHA
              and data["sha256"] == c.HASHES and data["rows_by_split"] == c.COUNTS, "Package data provenance")
    trained = provenance["training"]
    c.require(trained["steps"] == c.STEPS and trained["records_consumed"] == trained["selected_train_rows"] == c.COUNTS["train"]
              and trained["one_full_pass"] is True and trained["seed"] == c.SEED and trained["sampling"] == "shuffled"
              and trained["run_identity_sha256"] == run["identity_sha256"] and trained["code_commit"] == run["commit"], "Package training provenance")
    keys = ("world_size", "local_rows_per_step", "global_batch_size", "backend", "device_type",
            "implementation_sha256", "bitwise_single_process_equivalence")
    c.require(trained["distribution"] == {key:run["distribution"][key] for key in keys}, "Package DDP provenance")
    for name in c.RUN_FILES:
        c.require(provenance["source_evidence"][name] == c.info(training/name), "Package source evidence differs: "+name)
    return {"manifest": c.info(package/"manifest.json"), "provenance": c.info(package/"provenance.json"),
            "inference_files": {name:manifest["files"][name] for name in sorted(expected_names)}}


def predictions(inputs, directory, rows, identity, checkpoint, plan, summary):
    merged, workers, errors = {}, [], []
    for rank in range(4):
        assigned = c.assignments(rows, rank)
        assignment = c.assignment_identity(assigned, rank)
        report = inputs.read(directory, f"shard-{rank}.json")
        c.require(assignment == plan["assignments"][str(rank)] == report["assignment"], "Expansion shard assignment")
        c.require(report["status"] == "complete" and report["rank"] == rank and report["checkpoint"] == checkpoint
                  and report["dataset_profile"] == c.PROFILE and report["data_identity"] == identity, "Shard completion/profile identity")
        c.require(report["gpu_uuid"] == plan["gpu_uuids"][rank] and report["plan_sha256"] == c.info(directory/"plan.json")["sha256"], "Shard plan/GPU binding")
        name = f"shard-{rank}.jsonl"
        c.require(report["output_sha256"] == c.info(directory/name)["sha256"], "Shard output hash")
        actual = list(inputs.rows(directory, name))
        c.require(len(actual) == len(assigned) and report["counts"] == {"rows":len(assigned), "ok":len(assigned), "error":0}, "Missing/extra/failed predictions")
        for result, (split, index, row) in zip(actual, assigned):
            expected = {"id":row["id"], "split":split, "index":index, "shard_rank":rank,
                        "source":row["source"], "group_id":row["group_id"], "kind":row["kind"], "target":row["target"],
                        "row_sha256":c.objsha(row), "checkpoint":checkpoint, "question_id":row["metadata"].get("question_id", row["kind"])}
            c.require(all(result.get(key) == value for key,value in expected.items()), "Prediction row identity/order")
            c.require((split,index) not in merged and result["status"] == "ok", "Duplicate/failed prediction")
            logits, probabilities = result["logits"], result["probabilities"]
            c.require(len(logits) == len(probabilities) == len(row["options"]) and all(finite(x) for x in logits), "Invalid logit shape/value")
            c.distribution(probabilities)
            c.require(type(result["input_tokens"]) is int and result["input_tokens"] > 0, "Invalid input token count")
            weights = [math.exp((x-max(logits))/checkpoint["temperature"]) for x in logits]
            error = max(abs(a-b/sum(weights)) for a,b in zip(probabilities, weights))
            c.require(error <= 1e-12, "Prediction differs from saved-temperature softmax")
            errors.append(error)
            merged[split,index] = result
        workers.append(report)
    c.require(len(merged) == len({r["id"] for r in merged.values()}) == identity["total_rows"], "Full expansion prediction coverage")
    c.require(summary["workers"] == workers and set(summary["splits"]) == set(c.SPLITS), "Summary workers/splits")
    comparison, metrics, groups = c.Comparison(), {}, {}
    for split in c.SPLITS:
        ordered = [merged[split,i] for i in range(c.COUNTS[split])]
        c.require(list(inputs.rows(directory, f"merged-{split}.jsonl")) == ordered, "Original merged file order/content")
        recomputed = c.summarize(ordered)
        groups[split] = {}
        for field in ("source", "kind", "group_id"):
            buckets = defaultdict(list)
            for row in ordered:
                buckets[row[field]].append(row)
            grouped = {name:c.summarize(values) for name,values in sorted(buckets.items())}
            recomputed["by_"+field] = grouped
            groups[split][field] = {"count":len(grouped), "metrics_sha256":c.objsha(grouped)}
        comparison.check(recomputed, summary["splits"][split], split)
        metrics[split] = {key:value for key,value in recomputed.items() if key != "by_group_id"}
    return metrics, {"numeric_metric_leaves_checked":comparison.numeric_leaves, "max_metric_absolute_error":comparison.max_error,
                     "max_raw_probability_error":max(errors), "group_metrics":groups}


def audit(args):
    evidence, data, package = args.evidence, args.data, args.package
    inputs = Inputs()
    capture = inputs.read(evidence, "capture.json")
    c.require(capture["status"] == "copied_completed_expansion" and capture["read_only_remote"] is True
              and capture["model_inference_performed"] is False, "Incomplete/wrong capture")
    source = capture["source_before"]
    c.require(source == capture["source_after"] and source["status"] == "ready", "Unstable source capture")
    c.require(source["hostname"] == c.HOSTNAME and source["tag"] == "27b" and source["source_commit"] == c.COMMIT
              and source["source_root"] == c.REMOTE and source["source_run"] == c.REMOTE_RUN
              and source["source_data"] == c.REMOTE_DATA, "Wrong expansion source identity")
    checkpoint_names = c.checkpoint_names(evidence/"training/checkpoint")
    names = {"evaluation/"+name for name in c.EVAL_FILES} | {"training/"+name for name in c.RUN_FILES}
    names |= {"training/checkpoint/"+name for name in checkpoint_names}
    extra = {"capture.json", "controller-manifest-before.json", "controller-manifest-after.json"}
    c.require(set(source["files"]) == names and c.file_set(evidence) == names | extra, "Complete capture file set")
    for name, expected in source["files"].items():
        inputs.bind(evidence, name, expected)
    directory = evidence/"evaluation"
    plan, summary = inputs.read(directory, "plan.json"), inputs.read(directory, "summary.json")
    c.require(plan["tag"] == "27b" and summary["status"] == "complete", "Expansion evaluation incomplete")
    c.require(plan["data"] == c.REMOTE_DATA and plan["checkpoint_path"] == c.REMOTE_RUN+"/checkpoint"
              and plan["policy_path"] == source["source_checkout"]+"/state/auto_research/resource_policy.json", "Plan source paths")
    implementation, policy_sha = pinned_source()
    c.require(implementation == source["implementation_sha256"] == plan["implementation_sha256"], "Pinned evaluator source bytes")
    policy = {"hostname":c.HOSTNAME, "policy_sha256":policy_sha, "gpu_indices":[0,1,2,3]}
    c.require(source["policy_sha256"] == policy_sha and plan["policy"] == policy, "Pinned resource policy")
    c.require(len(plan["gpu_uuids"]) == len(set(plan["gpu_uuids"])) == 4, "Physical GPU identity")
    c.require(capture["controller_manifests"]["before"] == capture["controller_manifests"]["after"], "Controller changed during capture")
    for label in ("before", "after"):
        name = f"controller-manifest-{label}.json"
        inputs.bind(evidence, name, capture["controller_manifests"][label])
        controller = inputs.read(evidence, name)
        c.require(controller["status"] == "complete" and controller["gpus_free_after_cleanup"] is True
                  and controller["phase"] == "parallel_data_eval" and controller["model_order"] == ["27b"], "Controller incomplete/wrong model order")
        state = controller["models"]["27b"]
        c.require(set(controller["models"]) == {"27b"} and state["status"] == "complete" and state["exit_codes"] == [0]*4, "Workers not completed/reaped")
        c.require([r["rank"] for r in state["children"]] == list(range(4))
                  and [r["gpu_uuid"] for r in state["children"]] == plan["gpu_uuids"], "Controller worker identities")
        for key in ("dataset_profile", "partition", "data_identity", "gpu_uuids", "implementation_sha256", "policy"):
            c.require(controller[key] == plan[key], "Controller/plan identity: "+key)
    rows, calibration, identity = dataset(inputs, data, source)
    for item in (plan, summary):
        c.require(item["dataset_profile"] == c.PROFILE and item["partition"] == c.PARTITION
                  and item["data_identity"] == identity, "Expansion profile/partition/data identity")
    c.require(summary["total_rows"] == identity["total_rows"], "Expansion summary denominator")
    checkpoint, run = training_identity(inputs, evidence/"training", calibration, rows["test"])
    c.require(checkpoint == plan["checkpoint"] == summary["checkpoint"]
              and checkpoint["checkpoint_sha256"] == source["checkpoint_sha256"], "Evaluated checkpoint/training identity")
    package_proof = package_identity(inputs, package, evidence/"training", checkpoint, run)
    metrics, verification = predictions(inputs, directory, rows, identity, checkpoint, plan, summary)
    inputs.unchanged()
    c.require(c.file_set(evidence) == names | extra, "Evidence file set changed during audit")
    return {"schema_version":1, "status":"passed", "model":c.MODEL, "revision":c.REVISION,
            "audited_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "evaluation_source_commit":c.COMMIT, "dataset_profile":c.PROFILE, "data_identity":identity,
            "all_five_split_counts":c.COUNTS, "checkpoint":checkpoint, "package":package_proof,
            "model_evaluation_complete":True, "controller_complete_at_capture":True,
            "coverage":{"expected_rows":identity["total_rows"], "unique_ids":identity["total_rows"],
                        "shard_rows":[len(c.assignments(rows, r)) for r in range(4)], "missing":0, "duplicate":0, "failed":0},
            "verification":{**verification, "implementation_sha256":implementation,
                            "capture_sha256":c.info(evidence/"capture.json")["sha256"],
                            "audit_code_sha256":{name:c.info(Path(__file__).parent/name)["sha256"]
                                                 for name in ("verify.py", "expansion_contract.py")},
                            "independent_arithmetic_sha256":c.HELPER_SHA, "bound_input_files":len(inputs.bound)},
            "metrics":metrics, "model_inference_performed":False, "calibration_refitted":False,
            "full_data_baseline_evaluated":False, "full_data_training_gain":None,
            "limitations":["CPU arithmetic and byte-identity audit; no tensor loading or repeat model inference.",
                           "Captured current checkpoint bytes bind packaged weights and evaluation records; saved reload logits do not retroactively prove historical loaded weight bytes.",
                           "No full-data baseline; different 2B/9B training mixtures prevent size-only or training-gain conclusions.",
                           "Synthetic held-out decisions are not end-to-end browser, game or flight success; four-replica timing is not single-GPU latency."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--package", required=True, type=Path, help="Actual offline inference weight package, including all payload files")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    c.require(not args.output.exists() and not args.output.is_symlink(), "Preserve existing audit output")
    c.require(all(not args.output.resolve().is_relative_to(p.resolve()) for p in (args.evidence,args.data,args.package)), "Audit output must be outside read-only inputs")
    try:
        result = audit(args)
    except Exception as error:
        result = {"status":"failed", "model":c.MODEL, "error_type":type(error).__name__, "error":str(error),
                  "model_evaluation_complete":False, "metrics":None}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            stream.write(json.dumps(result, indent=2)+"\n")
        raise
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status":result["status"], "model":c.MODEL, "rows":result["coverage"]["expected_rows"]}))


if __name__ == "__main__":
    main()
