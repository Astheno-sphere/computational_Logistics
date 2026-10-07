"""Offline inference-only release packaging. No tensor loading or uploads."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import tempfile

from jev import metrics as probability_metrics

ROOT = Path(__file__).resolve().parents[1]
QWEN_LICENSE_SHA256 = "bbedc3fda3305820b977265f01b8619d87570a6739de3a5582c3464840f1e57a"
MODELS = {"Qwen/Qwen3.5-2B": "15852e8c16360a2fea060d615a32b45270f8a8fc",
          "Qwen/Qwen3.5-9B": "c202236235762e1c871ad0ccb60c8ee5ba337b9a",
          "Qwen/Qwen3.8-27B": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"}
DATASETS = {
    "56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97":
        {"name": "release-v2", "source_composition": ["release-v1", "reasoning-control-v1"]},
    "ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df":
        {"name": "browser-drone-expansion-v1", "source_composition": ["release-v2", "browser-v1", "drone-control-v1"]},
}
SPLITS = ("train", "calibration", "validation", "test", "ood")
MODEL_FILES = {"head.pt", "model.json", "temperature.json", "adapter/adapter_config.json"}
WEIGHT_FILES = {"adapter/adapter_model.safetensors", "adapter/adapter_model.bin"}
METRIC_FIELDS = {"count", "hard_count", "accuracy", "expected_accuracy", "nll", "brier", "expected_brier",
                 "multiclass_ece", "ece_bins", "coverage", "mean_latency_seconds", "ordinal_mae",
                 "optimal_action_hit", "optimal_set_probability_mass", "by_kind", "by_source", "by_question"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def digest(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Required input must be a regular nonsymlink file: " + path.name)
    hasher, size = hashlib.sha256(), 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
            size += len(chunk)
    return {"sha256": hasher.hexdigest(), "bytes": size}


def bind(path, inputs):
    path = Path(path)
    value = digest(path)
    require(path not in inputs or inputs[path] == value, "Input changed during verification: " + path.name)
    inputs[path] = value
    return value


def decode(raw):
    def invalid(value):
        raise ValueError("Nonstandard/nonfinite JSON constant: " + value)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key is forbidden")
            result[key] = value
        return result
    return json.loads(raw, parse_constant=invalid, object_pairs_hook=unique)


def read_json(path, inputs):
    expected = bind(path, inputs)
    raw = Path(path).read_bytes()
    require({"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} == expected, "JSON changed while reading")
    return decode(raw)


def read_lines(path, inputs):
    expected = bind(path, inputs)
    raw = Path(path).read_bytes()
    require({"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} == expected, "JSONL changed while reading")
    return [decode(line) for line in raw.splitlines() if line.strip()]


def select(rows, limit, seed, balanced):
    rows = list(rows)
    random.Random(seed).shuffle(rows)
    if balanced:
        buckets = {}
        for row in rows:
            buckets.setdefault((row["source"], row["kind"]), []).append(row)
        rows = []
        while any(buckets.values()):
            for bucket in buckets.values():
                if bucket:
                    rows.append(bucket.pop())
    return rows[:limit] if limit else rows


def checkpoint_files(checkpoint):
    require(checkpoint.is_dir() and not checkpoint.is_symlink(), "Missing or symlinked final checkpoint directory")
    found = set()
    for path in checkpoint.rglob("*"):
        require(not path.is_symlink(), "Symlinks are forbidden inside checkpoint")
        relative = path.relative_to(checkpoint).as_posix()
        if path.is_dir():
            require(relative == "adapter", "Unexpected checkpoint directory")
        else:
            require(path.is_file(), "Nonregular checkpoint entry")
            found.add(relative)
    require(found <= MODEL_FILES | WEIGHT_FILES | {"adapter/README.md"}, "Unexpected checkpoint file; optimizer/credentials/extra files are forbidden")
    require(MODEL_FILES <= found and len(found & WEIGHT_FILES) == 1, "Incomplete or ambiguous inference checkpoint")
    return sorted(found - {"adapter/README.md"})


def prediction_rows(path, expected, inputs):
    values = read_lines(path, inputs)
    require(len(values) == len(expected), "Prediction count differs: " + path.name)
    for value, row in zip(values, expected):
        require(all(value.get(key) == row[key] for key in ("id", "group_id", "source", "kind", "target", "question_id", "target_basis")), "Prediction identity/target differs: " + path.name)
        logits = value.get("logits")
        require(isinstance(logits, list) and len(logits) == len(row["target"]) and all(finite(x) for x in logits), "Invalid prediction logits: " + path.name)
        probabilities = value.get("probabilities")
        require(isinstance(probabilities, list) and len(probabilities) == len(logits) and
                all(finite(x) and 0 <= x <= 1 for x in probabilities) and
                all(math.isclose(a, b, rel_tol=1e-5, abs_tol=2e-6) for a, b in zip(probabilities, probability_metrics.softmax(logits))), "Saved probabilities disagree with logits: " + path.name)
        require(finite(value.get("latency_seconds")) and value["latency_seconds"] >= 0, "Invalid saved latency: " + path.name)
    return values


def close(first, second):
    if isinstance(first, dict):
        return isinstance(second, dict) and first.keys() == second.keys() and all(close(v, second[k]) for k, v in first.items())
    if isinstance(first, list):
        return isinstance(second, list) and len(first) == len(second) and all(close(a, b) for a, b in zip(first, second))
    if finite(first) and finite(second):
        return math.isclose(first, second, rel_tol=1e-8, abs_tol=1e-8)
    return first == second


def recompute_metrics(values, temperature):
    """Same stdlib math and rounding path as both training entrypoints."""
    probabilities = [probability_metrics.softmax([x / temperature for x in row["logits"]]) for row in values]
    result = probability_metrics.evaluate_probabilities([row["target"] for row in values], probabilities)
    result["mean_latency_seconds"] = sum(row["latency_seconds"] for row in values) / len(values)
    for field, name in (("kind", "by_kind"), ("source", "by_source"), ("question_id", "by_question")):
        def group(row):
            return row["source"] + "/" + row[field] if field == "question_id" else row[field]
        result[name] = {}
        for key in sorted({group(row) for row in values}):
            pairs = [(row, p) for row, p in zip(values, probabilities) if group(row) == key]
            metric = probability_metrics.evaluate_probabilities([row["target"] for row, _ in pairs], [p for _, p in pairs])
            if field == "kind" and key == "score":
                metric["ordinal_mae"] = sum(abs(sum(i * x for i, x in enumerate(p)) - sum(i * x for i, x in enumerate(row["target"]))) for row, p in pairs) / len(pairs)
            if field == "source" and key.startswith("wikispeedia"):
                metric.update(optimal_action_hit=sum(row["target"][max(range(len(p)), key=p.__getitem__)] > 0 for row, p in pairs) / len(pairs),
                              optimal_set_probability_mass=sum(sum(x for x, y in zip(p, row["target"]) if y > 0) for row, p in pairs) / len(pairs))
            result[name][key] = metric
    return result


def normalized_metric(metric):
    require(isinstance(metric, dict) and set(metric) <= METRIC_FIELDS, "Unexpected metric metadata")
    require({"count", "hard_count", "accuracy", "expected_accuracy", "nll", "brier", "expected_brier", "multiclass_ece", "ece_bins", "coverage"} <= set(metric), "Incomplete metric fields")
    require(type(metric.get("count")) is int and metric["count"] > 0, "Invalid metric count")
    require(type(metric["hard_count"]) is int and 0 <= metric["hard_count"] <= metric["count"], "Invalid hard-label count")
    require((metric["accuracy"] is None) == (metric["hard_count"] == 0), "Accuracy/hard-label count mismatch")
    for key in ("accuracy", "expected_accuracy", "multiclass_ece"):
        require(metric[key] is None or finite(metric[key]) and 0 <= metric[key] <= 1, "Invalid probability metric")
    for key in ("nll", "brier", "expected_brier"):
        require(finite(metric[key]) and metric[key] >= 0, "Invalid loss metric")
    result = {}
    for key, value in metric.items():
        if key.startswith("by_"):
            require(isinstance(value, dict), "Invalid metric grouping")
            require(all(isinstance(k, str) and len(k) < 300 and not any(c in k for c in '\n\r') and not k.startswith(("/", "~")) for k in value), "Invalid metric group name")
            result[key] = {k: normalized_metric(v) for k, v in value.items()}
            require(sum(v["count"] for v in result[key].values()) == metric["count"], "Metric group counts do not sum to total")
        elif key == "coverage":
            require(isinstance(value, list), "Invalid metric coverage")
            result[key] = []
            for item in value:
                require(isinstance(item, dict) and set(item) <= {"threshold", "selected", "coverage", "accuracy", "expected_accuracy", "expected_risk"}, "Unexpected coverage metadata")
                require(all(x is None or finite(x) for x in item.values()), "Nonfinite/non-numeric coverage")
                require(type(item.get("selected")) is int and 0 <= item["selected"] <= metric["count"] and
                        finite(item.get("coverage")) and abs(item["coverage"] - item["selected"] / metric["count"]) < 1e-9, "Coverage denominator mismatch")
                result[key].append(dict(item))
        else:
            require(value is None or finite(value), "Nonfinite/non-numeric metric")
            result[key] = value
    return result


def reject_sensitive_config(value):
    if isinstance(value, dict):
        require(not set(k.lower() for k in value) & {"password", "secret", "api_key", "access_token", "refresh_token", "authorization", "credentials", "private_key", "environment", "env"}, "Sensitive adapter metadata is forbidden")
        for child in value.values():
            reject_sensitive_config(child)
    elif isinstance(value, list):
        for child in value:
            reject_sensitive_config(child)


def verify_run(run_directory, data_directory, inputs):
    run_directory = Path(run_directory)
    require(run_directory.is_dir() and not run_directory.is_symlink(), "Run must be a nonsymlink directory")
    require(not (run_directory / "resume.json").exists(), "A resume-only snapshot is not a completed model")
    run = read_json(run_directory / "run.json", inputs)
    summary = read_json(run_directory / "summary.json", inputs)
    require(summary.get("status") == "complete" and summary.get("inference_ready", True) is not False, "Training run is not complete")
    checkpoint = run_directory / "checkpoint"
    files = checkpoint_files(checkpoint)
    config = read_json(checkpoint / "model.json", inputs)
    require(set(config) == {"model_id", "revision", "max_length", "lora_rank", "method"}, "Unexpected model config fields")
    require(run.get("model") in MODELS and run.get("revision") == MODELS[run["model"]], "Unverified upstream model/revision")
    require(config["model_id"] == run["model"] == summary.get("model") and config["revision"] == run["revision"], "Model/revision mismatch")
    require(config["method"] == "independent_candidate_lora_nll_brier", "Unsupported inference method")
    require(config["max_length"] == run.get("max_length") and config["lora_rank"] == run.get("lora_rank") and type(run["lora_rank"]) is int and run["lora_rank"] > 0, "Model configuration differs from run")
    for key in ("steps", "accumulation", "max_length"):
        require(type(run.get(key)) is int and run[key] > 0, "Invalid training field: " + key)
    for key in ("train_rows", "calibration_rows", "eval_rows", "seed"):
        require(type(run.get(key)) is int and run[key] >= 0, "Invalid training field: " + key)
    for key in ("lr", "head_lr", "brier_weight"):
        require(finite(run.get(key)) and run[key] >= 0, "Invalid training field: " + key)
    require(summary.get("steps") == run["steps"] and summary.get("trained_rows_consumed") == run["steps"] * run["accumulation"], "Training completion/record count mismatch")
    require(re.fullmatch(r"[0-9a-f]{40}", run.get("commit", "")) is not None, "Missing training code commit")
    ddp = run.get("distribution")
    identity_key = "identity_sha256" if ddp else "run_identity_sha256"
    require(re.fullmatch(r"[0-9a-f]{64}", run.get(identity_key, "")) is not None, "Missing run identity hash")
    if ddp:
        require(ddp == summary.get("distribution") and ddp.get("world_size") == ddp.get("global_batch_size") == run["accumulation"] == 4 and ddp.get("local_rows_per_step") == 1, "DDP topology/global batch mismatch")
        require(ddp.get("backend") in ("nccl", "gloo") and ddp.get("device_type") == ("cuda" if ddp["backend"] == "nccl" else "cpu") and
                re.fullmatch(r"[0-9a-f]{64}", ddp.get("implementation_sha256", "")) is not None and ddp.get("bitwise_single_process_equivalence") is False, "Invalid DDP provenance")
        require(run.get("initialization") in ("fresh_pinned_upstream", "strict_same_run_ddp_resume"), "Unsupported DDP initialization")
    log = read_lines(run_directory / "training.jsonl", inputs)
    require([row.get("step") for row in log] == list(range(1, run["steps"] + 1)), "Training log has an incomplete/noncontiguous optimizer cursor")
    require(all(finite(row.get(k)) for row in log for k in ("loss", "gradient_norm", "elapsed_seconds")), "Training log contains nonfinite/missing values")
    if ddp:
        require(all(row.get("world_size") == row.get("global_batch_size") == 4 for row in log), "Training log DDP topology mismatch")
    data = Path(data_directory or run["data"])
    require(data.is_dir() and not data.is_symlink(), "Frozen data directory must be available locally")
    manifest = read_json(data / "manifest.json", inputs)
    hashes = run.get("data_sha256", {})
    require(set(hashes) == set(SPLITS) and manifest.get("sha256") == hashes, "Run/data manifest hash mapping differs")
    selected, counts, all_ids = {}, {}, set()
    sampling = run.get("training_sampling", "source_kind_round_robin")
    require(sampling in ("source_kind_round_robin", "shuffled"), "Unsupported training sampling")
    for split in SPLITS:
        path = data / (split + ".jsonl")
        require(bind(path, inputs)["sha256"] == hashes[split], "Frozen data checksum differs: " + split)
        rows = []
        parsed_hash, parsed_bytes = hashlib.sha256(), 0
        with path.open("rb") as handle:
            for line in handle:
                parsed_hash.update(line)
                parsed_bytes += len(line)
                if not line.strip():
                    continue
                item = decode(line)
                row = {k: item[k] for k in ("id", "group_id", "source", "kind", "target", "split")}
                row.update(question_id=item["metadata"].get("question_id", row["kind"]),
                           target_basis=item["metadata"].get("target_basis", "hard_label"))
                require(row["split"] == split and row["id"] not in all_ids, "Wrong split or duplicate data ID")
                require(isinstance(row["target"], list) and row["target"] and all(finite(x) and x >= 0 for x in row["target"]) and abs(sum(row["target"]) - 1) < 1e-6, "Invalid source target")
                all_ids.add(row["id"])
                rows.append(row)
        require({"sha256": parsed_hash.hexdigest(), "bytes": parsed_bytes} == inputs[path], "Data changed while parsing: " + split)
        counts[split] = len(rows)
        require(counts[split] == manifest.get("counts", {}).get(split) and counts[split] > 0, "Data manifest count differs: " + split)
        if split != "validation":
            limit = run["train_rows"] if split == "train" else run["calibration_rows"] if split == "calibration" else run["eval_rows"]
            selected[split] = select(rows, limit, run["seed"], split != "train" or sampling == "source_kind_round_robin")
    for split, key in (("calibration", "calibration_ids"), ("test", "evaluation_ids"), ("ood", "ood_ids")):
        require(run.get(key) == [row["id"] for row in selected[split]], "Saved selected IDs differ from frozen data: " + split)
    predictions = {}
    for split, name in (("calibration", "calibration.jsonl"), ("test", "trained_test.jsonl"), ("ood", "trained_ood.jsonl")):
        predictions[split] = prediction_rows(run_directory / name, selected[split], inputs)
    baseline_names = ("baseline_test.jsonl", "baseline_ood.jsonl", "baseline_calibration.jsonl")
    baseline = {}
    for split, name in zip(("test", "ood", "calibration"), baseline_names):
        baseline[split] = prediction_rows(run_directory / name, selected[split], inputs)
        if ddp:
            require(inputs[run_directory / name]["sha256"] == run.get("original_baseline_sha256", {}).get(name), "DDP original baseline checksum mismatch")
    temperature = read_json(checkpoint / "temperature.json", inputs)
    require(set(temperature) == {"temperature", "split", "n", "ids_sha256"}, "Unexpected calibration metadata")
    require(finite(temperature["temperature"]) and temperature["temperature"] > 0 and temperature["temperature"] == summary.get("temperature"), "Temperature differs or is nonfinite")
    require(temperature["split"] == "calibration" and type(temperature["n"]) is int and temperature["n"] == len(selected["calibration"]), "Calibration split/count mismatch")
    expected_ids_hash = hashlib.sha256(json.dumps(run["calibration_ids"]).encode()).hexdigest()
    require(temperature["ids_sha256"] == expected_ids_hash, "Calibration ID hash mismatch")
    require(finite(summary.get("baseline_temperature")) and summary["baseline_temperature"] > 0, "Invalid baseline temperature")
    for values, recorded in ((predictions["calibration"], temperature["temperature"]), (baseline["calibration"], summary["baseline_temperature"])):
        fitted = probability_metrics.fit_temperature([r["logits"] for r in values], [r["target"] for r in values])
        require(close(fitted, recorded), "Recorded temperature differs from calibration-only refit")
    reloaded = prediction_rows(run_directory / "reload_check.jsonl", selected["test"][:1], inputs)[0]["logits"]
    reference = predictions["test"][0]["logits"]
    error = max(abs(a - b) for a, b in zip(reference, reloaded))
    recorded_error = summary.get("checkpoint_reload_max_error")
    require(finite(recorded_error) and 0 <= recorded_error <= 0.05 and finite(error) and error <= 0.05 and abs(error - recorded_error) <= 1e-9, "Reload evidence is nonfinite, mismatched, or inconsistent with summary")
    metric_names = {prefix + "_" + split for prefix in ("baseline", "baseline_calibrated", "trained", "calibrated") for split in ("test", "ood")}
    require(set(summary.get("metrics", {})) == metric_names, "Missing/unsupported summary metric sections")
    metrics = {name: normalized_metric(value) for name, value in summary["metrics"].items()}
    require(all(value["count"] == len(selected[name.rsplit("_", 1)[1]]) for name, value in metrics.items()), "Summary metrics count differs from selected predictions")
    for split in ("test", "ood"):
        for prefix, values, temp in (("baseline", baseline[split], 1), ("baseline_calibrated", baseline[split], summary["baseline_temperature"]),
                                     ("trained", predictions[split], 1), ("calibrated", predictions[split], temperature["temperature"])):
            name = prefix + "_" + split
            require(close(metrics[name], recompute_metrics(values, temp)), "Summary metrics disagree with raw predictions: " + name)
    adapter = read_json(checkpoint / "adapter/adapter_config.json", inputs)
    reject_sensitive_config(adapter)
    require(adapter.get("peft_type") == "LORA" and adapter.get("r") == run["lora_rank"], "Adapter type/rank mismatch")
    require(adapter.get("base_model_name_or_path") in (None, "", run["model"]) and adapter.get("revision") in (None, run["revision"]), "Adapter upstream identity mismatch or local path")
    for name in files:
        require(bind(checkpoint / name, inputs)["bytes"] > 0, "Empty inference file")
    distribution = None if not ddp else {k: ddp[k] for k in ("world_size", "local_rows_per_step", "global_batch_size", "backend", "device_type", "implementation_sha256", "bitwise_single_process_equivalence")}
    provenance = {"schema_version": 1, "weights_license": "Apache-2.0", "code_license": "MIT", "model": run["model"], "revision": run["revision"],
                  "training": {**{k: run[k] for k in ("steps", "accumulation", "max_length", "lora_rank", "lr", "head_lr", "brier_weight", "seed")},
                               "sampling": sampling, "records_consumed": summary["trained_rows_consumed"], "selected_train_rows": len(selected["train"]),
                               "one_full_pass": summary["trained_rows_consumed"] == len(selected["train"]) == counts["train"],
                               "code_commit": run["commit"], "run_identity_sha256": run[identity_key], "distribution": distribution,
                               "initialization": "fresh_pinned_upstream", "resumed_within_run": bool(run.get("resume_training") or run.get("resumed_from"))},
                  "data": {**DATASETS.get(inputs[data / "manifest.json"]["sha256"], {"name": "custom frozen dataset", "source_composition": []}),
                           "manifest_sha256": inputs[data / "manifest.json"]["sha256"], "sha256": hashes, "rows_by_split": counts,
                           "selected_rows": {s: len(rows) for s, rows in selected.items()},
                           "selected_ids_sha256": {s: hashlib.sha256(json.dumps([r["id"] for r in rows]).encode()).hexdigest() for s, rows in selected.items()}},
                  "calibration": temperature, "baseline_temperature": summary["baseline_temperature"],
                  "metric_verification": {"implementation_sha256": bind(Path(probability_metrics.__file__), inputs)["sha256"],
                                          "core_and_grouped_sections_recomputed": 8, "calibration_only_temperatures_refitted": 2},
                  "reload": {"recorded_max_error": recorded_error, "recomputed_saved_logit_max_error": error,
                             "performed_by_packager": False, "scope": "Compares saved reload and trained-test logits. No tensor deserialization or GPU inference; no production-time weight digest was recorded by training."},
                  "source_evidence": {name: inputs[run_directory / name] for name in ("run.json", "summary.json", "training.jsonl", "calibration.jsonl", "trained_test.jsonl", "trained_ood.jsonl", "reload_check.jsonl", *baseline_names)},
                  "excluded_evaluations": "No separate full-data, JF100, browser/drone pilot, simulator or closed-loop evaluation is imported."}
    return files, provenance, metrics


def model_card(provenance, metrics):
    p, t, d = provenance, provenance["training"], provenance["data"]
    lines = ["---", "license: apache-2.0", "base_model: " + p["model"], "tags:", "- open-jev", "- non-generative", "---", "",
             "# Open-Jev decision checkpoint", "", "This local package contains an Open-Jev LoRA adapter and scalar decision head derived from " + p["model"] + ".",
             "Upstream revision: `" + p["revision"] + "`. The upstream model/tokenizer are required and are not bundled.", "",
             "The adapter and Yes-minus-No-initialized scalar head are modified training products. Weights use Apache-2.0; Open-Jev source code remains MIT. See LICENSE, LICENSE-CODE and UPSTREAM.md.", "",
             "## Recorded training", "", f"{t['steps']:,} optimizer steps × global batch {t['accumulation']} = {t['records_consumed']:,} consumed rows; {t['selected_train_rows']:,} selected train rows out of {d['rows_by_split']['train']:,}.",
             "Dataset: " + d["name"] + "; source composition: " + (", ".join(d["source_composition"]) or "no named release profile matched") + ".",
             "Training coverage: " + ("one full pass over all train rows." if t["one_full_pass"] else "bounded/repeated selection; this is not one full pass over all train rows."),
             "Topology: " + ("four-rank DDP, one row per rank per step; independent rank RNG streams." if t["distribution"] else "single process with gradient accumulation."),
             "Code commit: `" + t["code_commit"] + "`. Full normalized hyperparameters and data hashes are in provenance.json.", "",
             "## Recorded evaluation", "", f"The source run evaluated {d['selected_rows']['test']:,}/{d['rows_by_split']['test']:,} test rows and {d['selected_rows']['ood']:,}/{d['rows_by_split']['ood']:,} OOD rows using source/kind-balanced selection.",
             f"These results do not represent a separate full-data evaluation of all {d['rows_by_split']['test'] + d['rows_by_split']['ood']:,} held-out rows. Other pilot or benchmark results are not merged into this card.",
             f"Temperature {p['calibration']['temperature']:.8g} was recorded for {p['calibration']['n']:,} calibration rows; their ID hash is retained.", "",
             "| Measurement | Rows | Hard-label accuracy | Expected accuracy | NLL | Brier | ECE |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    def cell(value):
        return "n/a" if value is None else format(value, ".6g")
    for name in sorted(metrics):
        m = metrics[name]
        lines.append("| " + name + " | " + str(m["count"]) + " | " + " | ".join(cell(m.get(k)) for k in ("accuracy", "expected_accuracy", "nll", "brier", "multiclass_ece")) + " |")
    lines += ["", "## Load with Open-Jev", "", "From an Open-Jev source checkout, install the training/inference dependencies and start the decision server:", "",
              "```bash", "python -m pip install '.[train]'",
              "python -m jev.server --checkpoint /path/to/package/checkpoint \\",
              f"  --device cuda:0 --max-length {t['max_length']} --batch-size 1 \\",
              "  --host 127.0.0.1 --port 8791", "```", "",
              "A suitable GPU and the exact upstream weights/tokenizer revision listed above are required, either cached locally or downloaded by the loader. The scalar decision head requires Open-Jev's loader; AutoPeftModel generation alone does not implement these decisions.",
              "", "## Verification scope", "", "Packaging verified source hashes, completed-step logs, frozen-data selection, model identity, calibration binding and saved reload logits. Both temperatures and all eight core/grouped metric sections were recomputed from the verified saved predictions using the repository's stdlib metrics. It hashes the current weight bytes but does not load tensors or repeat model inference. The training summary did not record output-weight hashes, so the historical reload is not an independent verification of the current packaged bytes.",
              "", "Synthetic sampled scores do not establish general agent, browser, game, flight or closed-loop competence. The manifest identifies a local package; it does not imply an upload or public release.", ""]
    return "\n".join(lines)


def package(run_directory, output_directory, data_directory=None):
    run_directory, output = Path(run_directory), Path(output_directory)
    require(not output.exists() and not output.is_symlink(), "Output must be a new directory")
    require(not output.resolve().is_relative_to(run_directory.resolve()), "Output must be outside the source run")
    inputs = {}
    files, provenance, metrics = verify_run(run_directory, data_directory, inputs)
    data_path = Path(data_directory or read_json(run_directory / "run.json", inputs)["data"])
    require(not output.resolve().is_relative_to(data_path.resolve()), "Output must be outside the frozen data")
    license_path, attribution, code_license = ROOT / "third_party/qwen/LICENSE", ROOT / "third_party/qwen/README.md", ROOT / "LICENSE"
    require(bind(license_path, inputs)["sha256"] == QWEN_LICENSE_SHA256, "Upstream Apache-2.0 license bytes differ from pinned evidence")
    bind(code_license, inputs)
    require(b"MIT License" in code_license.read_bytes(), "Missing source MIT license")
    bind(attribution, inputs)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="." + output.name + ".incomplete-", dir=output.parent))
    try:
        copies = {"checkpoint/" + name: run_directory / "checkpoint" / name for name in files}
        copies.update({"LICENSE": license_path, "LICENSE-CODE": code_license, "UPSTREAM.md": attribution})
        for name, source in copies.items():
            destination = temporary / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            require(digest(destination) == inputs[source], "Copy differs from verified source: " + name)
        for name, value in (("provenance.json", provenance), ("metrics.json", metrics)):
            (temporary / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        (temporary / "README.md").write_text(model_card(provenance, metrics))
        manifest = {"schema_version": 1, "kind": "local_inference_weight_package", "weights_license": "Apache-2.0",
                    "model": provenance["model"], "revision": provenance["revision"],
                    "files": {p.relative_to(temporary).as_posix(): digest(p) for p in sorted(temporary.rglob("*")) if p.is_file()},
                    "scope": "All package files except this manifest are listed. Manifest SHA-256 is returned separately; no upload performed."}
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
        for path, expected in inputs.items():
            require(digest(path) == expected, "Source changed before publication: " + path.name)
        require(not output.exists() and not output.is_symlink(), "Output appeared during packaging; refusing replacement")
        manifest_hash = digest(temporary / "manifest.json")["sha256"]
        os.rename(temporary, output)
        return {"output": str(output), "manifest_sha256": manifest_hash, "files": len(manifest["files"]), "uploaded": False}
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Completed run containing run.json, summary.json and final checkpoint")
    parser.add_argument("--output", required=True, help="Absent local package directory outside the source run/data")
    parser.add_argument("--data", help="Relocate frozen data locally; hashes and selection must still match the source run")
    args = parser.parse_args()
    print(json.dumps(package(args.run, args.output, args.data)))


if __name__ == "__main__":
    main()
