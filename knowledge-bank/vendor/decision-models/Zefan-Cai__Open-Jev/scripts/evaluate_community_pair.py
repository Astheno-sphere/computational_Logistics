"""Frozen new-v3 holdout panel, followed by a one-GPU paired 27B evaluation.

CPU panel building never imports torch. The caller owns GPU leases and launches
this process; no server, scheduler, retry, calibration fit or model mutation.
"""
import argparse
from collections import Counter, defaultdict
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

from jev.data import SPLITS, validate_records
from jev.metrics import evaluate_probabilities, softmax
from jev.serving import candidate_batches
from scripts.evaluate_checkpoints_parallel import canonical, file_hash, read_json, write_json
from scripts.run_service_suite import checkpoint_identity

ROOT = Path(__file__).resolve().parents[1]
VERSION = "community-pair-v1"
NEW_VERSIONS = {"community-routing-v3", "sql-semantics-v3", "community-workflow-v3"}
MODEL = "Qwen/Qwen3.8-27B"
REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
INPUT_FIELDS = ("state", "question", "kind", "options")
TAGS = ("v2-final", "v3-final")


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def jsonl(path):
    with Path(path).open() as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def input_digest(row):
    # Sorting options detects the same labeled task under candidate permutation.
    return digest({**{key: row[key] for key in INPUT_FIELDS}, "options": sorted(row["options"])})


def select_panel(directories, per_source_split=128, seed=20260921):
    if type(per_source_split) is not int or not 1 <= per_source_split <= 128:
        raise ValueError("Panel size must be between 1 and 128 per source/split")
    buckets, bindings = defaultdict(list), []
    excluded_ids, excluded_groups, excluded_inputs = set(), set(), set()
    seen_ids, group_splits, versions = set(), {}, set()
    for directory in sorted(map(Path, directories), key=lambda p: p.name):
        manifest = read_json(directory / "manifest.json")
        config = manifest["configuration"]
        version = config.get("generator_version", config.get("version"))
        if version not in NEW_VERSIONS or version in versions:
            raise ValueError("Only distinct new SQL/routing v3 datasets may enter the panel")
        versions.add(version)
        hashes = manifest["files_sha256"]
        if set(hashes) != {split + ".jsonl" for split in SPLITS}:
            raise ValueError("Every source must bind all five split files")
        for split in SPLITS:
            path = directory / (split + ".jsonl")
            if file_hash(path) != hashes[path.name]:
                raise ValueError("New source dataset checksum differs")
            for row in jsonl(path):
                if row["split"] != split or row["id"] in seen_ids:
                    raise ValueError("Source split mismatch or repeated ID")
                seen_ids.add(row["id"])
                old = group_splits.setdefault(row["group_id"], split)
                if old != split:
                    raise ValueError("A source group crosses splits")
                if split in ("test", "ood"):
                    buckets[row["source"], split].append(row)
                else:
                    excluded_ids.add(row["id"])
                    excluded_groups.add(row["group_id"])
                    excluded_inputs.add(input_digest(row))
        bindings.append({"version": version, "manifest_sha256": file_hash(directory / "manifest.json"),
                         "files_sha256": hashes})
    if not buckets:
        raise ValueError("No new held-out records")
    selected = []
    for (source, split), values in sorted(buckets.items()):
        grouped = defaultdict(list)
        for row in values:
            if row["id"] in excluded_ids or row["group_id"] in excluded_groups or input_digest(row) in excluded_inputs:
                raise ValueError("New held-out record overlaps train/calibration/validation")
            grouped[row["group_id"]].append(row)
        groups = sorted(grouped, key=lambda group: digest([seed, source, split, group]))
        ordered = [sorted(grouped[group], key=lambda row: digest([seed, row["id"]])) for group in groups]
        taken = 0
        for position in range(max(map(len, ordered))):
            for candidates in ordered:
                if position < len(candidates):
                    selected.append(candidates[position])
                    taken += 1
                    if taken == per_source_split:
                        break
            if taken == per_source_split:
                break
    validate_records(selected)
    return selected, {"schema_version": 1, "version": VERSION, "seed": seed,
        "per_source_split": per_source_split, "source_bindings": bindings,
        "selection": "round-robin hash-ordered groups, hash-order views inside each group; independent of labels/predictions",
        "counts": [{"source": source, "split": split, "rows": count,
                    "unique_groups": len({row["group_id"] for row in selected if (row["source"], row["split"]) == (source, split)})}
                   for (source, split), count in
                   sorted(Counter((row["source"], row["split"]) for row in selected).items())],
        "rows": len(selected), "unique_groups": len({row["group_id"] for row in selected}),
        "correlated_views_beyond_first_per_group": len(selected) - len({row["group_id"] for row in selected}),
        "independent_case_count_claimed": False, "ordered_ids_sha256": digest([row["id"] for row in selected]),
        "selection_precedes_inference": True, "excluded_splits": ["train", "calibration", "validation"],
        "model_input_fields": list(INPUT_FIELDS)}


def build_panel(directories, output, per_source_split=128, seed=20260921):
    rows, manifest = select_panel(directories, per_source_split, seed)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "panel.jsonl").write_text("".join(canonical(row) + "\n" for row in rows))
    manifest["panel_sha256"] = file_hash(output / "panel.jsonl")
    write_json(output / "manifest.json", manifest)
    return manifest


def load_panel(directory, directories):
    directory = Path(directory)
    manifest = read_json(directory / "manifest.json")
    if manifest.get("version") != VERSION or file_hash(directory / "panel.jsonl") != manifest["panel_sha256"]:
        raise ValueError("Frozen panel bytes differ")
    rows = list(jsonl(directory / "panel.jsonl"))
    expected, identity = select_panel(directories, manifest["per_source_split"], manifest["seed"])
    if rows != expected or {k: v for k, v in manifest.items() if k != "panel_sha256"} != identity:
        raise ValueError("Panel differs from its frozen deterministic source selection")
    return rows, manifest


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def completed_identity(specification, panel, commit):
    path, data = Path(specification["checkpoint"]), Path(specification["training_data"])
    expected = specification["expected"]
    for key in ("training_commit", "run_identity_sha256"):
        if re.fullmatch(r"[0-9a-f]{40}" if key == "training_commit" else r"[0-9a-f]{64}", expected[key]) is None:
            raise ValueError("A frozen training code/run identity is required")
    config, run, summary = [read_json(p) for p in (path / "model.json", path.parent / "run.json", path.parent / "summary.json")]
    if ((config["model_id"], config["revision"]) != (MODEL, REVISION)
            or (run.get("model"), run.get("revision")) != (MODEL, REVISION)
            or summary.get("status") != "complete" or summary.get("model") != MODEL
            or any(type(expected[k]) is not int or expected[k] <= 0 for k in ("steps", "trained_rows_consumed"))
            or run.get("steps") != expected["steps"] or summary.get("steps") != expected["steps"]
            or summary.get("trained_rows_consumed") != expected["trained_rows_consumed"]
            or run.get("training_rows_consumed") != expected["trained_rows_consumed"]
            or run.get("commit") != expected["training_commit"]
            or run.get("identity_sha256") != expected["run_identity_sha256"]
            or run.get("max_length") != config.get("max_length") or run.get("lora_rank") != config.get("lora_rank")
            or not finite(summary.get("checkpoint_reload_max_error"))
            or not 0 <= summary["checkpoint_reload_max_error"] <= .05):
        raise ValueError("Checkpoint is not the pinned completed 27B stage with a passing reload")
    hashes = expected["data_sha256"]
    if set(hashes) != set(SPLITS) or run.get("data_sha256") != hashes:
        raise ValueError("Training must bind all five expected data hashes")
    panel_ids = {row["id"] for row in panel}
    panel_groups = {row["group_id"] for row in panel}
    panel_inputs = {input_digest(row) for row in panel}
    calibration_ids = set()
    for split in SPLITS:
        file = data / (split + ".jsonl")
        if file_hash(file) != hashes[split]:
            raise ValueError("Training data bytes changed")
        if split not in ("train", "calibration", "validation"):
            continue
        for row in jsonl(file):
            if row["split"] != split:
                raise ValueError("Training source split differs")
            if row["id"] in panel_ids or row["group_id"] in panel_groups or input_digest(row) in panel_inputs:
                raise ValueError("Panel overlaps this checkpoint's train/calibration/validation data")
            if split == "calibration":
                calibration_ids.add(row["id"])
    temperature = read_json(path / "temperature.json")
    ids = run.get("calibration_ids", [])
    if (not ids or len(set(ids)) != len(ids) or not set(ids) <= calibration_ids
            or temperature.get("split") != "calibration" or temperature.get("n") != len(ids)
            or temperature.get("ids_sha256") != hashlib.sha256(json.dumps(ids).encode()).hexdigest()
            or not finite(temperature.get("temperature")) or temperature["temperature"] <= 0
            or summary.get("temperature") != temperature["temperature"]):
        raise ValueError("Saved temperature or calibration provenance differs")
    calibration = list(jsonl(path.parent / "calibration.jsonl"))
    if ([row.get("id") for row in calibration] != ids or any(
            not row.get("logits") or any(not finite(number) for number in row["logits"]) for row in calibration)):
        raise ValueError("Saved calibration predictions are incomplete or nonfinite")
    if (not (path / "head.pt").is_file() or not (path / "adapter/adapter_config.json").is_file()
            or not any((path / "adapter" / name).is_file() for name in ("adapter_model.safetensors", "adapter_model.bin"))):
        raise ValueError("Final trained checkpoint weights are missing")
    identity = checkpoint_identity(path, "27b", commit, max_length=config["max_length"])
    identity.update(training_completion={"steps": expected["steps"], "trained_rows_consumed": expected["trained_rows_consumed"],
        "run_identity_sha256": run["identity_sha256"], "reload_max_error": summary["checkpoint_reload_max_error"],
        "run_sha256": file_hash(path.parent / "run.json"), "summary_sha256": file_hash(path.parent / "summary.json"),
        "calibration_predictions_sha256": file_hash(path.parent / "calibration.jsonl")},
        data_sha256=hashes, calibration=temperature)
    return identity


def score_one(scorer, row):
    inputs = {key: row[key] for key in INPUT_FIELDS}
    logits, tokens = [], 0
    for batch in candidate_batches([inputs], 4):
        values, used = scorer.score([piece for _, piece in batch])
        if len(values) != len(batch) or type(used) is not int or used <= 0:
            raise ValueError("Scorer row or token count differs")
        for (_, piece), vector in zip(batch, values):
            expected = 2 if piece["kind"] == "noul" else len(piece["options"])
            if len(vector) != expected or any(not finite(value) for value in vector):
                raise ValueError("Scorer returned nonfinite or malformed logits")
            logits.extend(vector)
        tokens += used
    if len(logits) != len(row["target"]):
        raise ValueError("Reassembled logits do not match the complete candidate set")
    return logits, tokens


def evaluate_rows(rows, scorer, identity, output, deadline=None):
    results = []
    with Path(output).open("x") as stream:
        for index, row in enumerate(rows):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Paired evaluation time bound reached")
            result = {"id": row["id"], "index": index, "source": row["source"], "split": row["split"],
                      "kind": row["kind"], "input_sha256": input_digest(row), "target": row["target"],
                      "checkpoint_sha256": identity["checkpoint_sha256"], "temperature": identity["temperature"]}
            started = time.perf_counter()
            try:
                logits, tokens = score_one(scorer, row)
                result.update(status="ok", logits=logits, input_tokens=tokens,
                              probabilities_uncalibrated=softmax(logits),
                              probabilities_calibrated=softmax(logits, identity["temperature"]))
            except Exception as error:
                result.update(status="error", error_type=type(error).__name__, error=str(error)[:1000])
            result["wall_seconds"] = time.perf_counter() - started
            stream.write(canonical(result) + "\n")
            stream.flush()
            results.append(result)
    return results


def noul_diagnostics(rows, by_id):
    if not all(row["kind"] == "noul" and row["options"] == ["no", "yes"] for row in rows):
        return None
    gold_counts = {"no": 0, "yes": 0}
    errors, pending = dict(gold_counts), dict(gold_counts)
    confusion = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for row in rows:
        if row["target"] not in ([1., 0.], [0., 1.]):
            continue  # Soft targets have no unique binary gold label.
        gold = "yes" if row["target"][1] == 1. else "no"
        gold_counts[gold] += 1
        result = by_id.get(row["id"])
        if result is None:
            pending[gold] += 1
        elif result["status"] != "ok":
            errors[gold] += 1
        else:
            probabilities = result["probabilities_calibrated"]
            prediction = "yes" if probabilities[1] > probabilities[0] else "no"
            confusion[{("yes", "yes"): "tp", ("no", "yes"): "fp",
                       ("yes", "no"): "fn", ("no", "no"): "tn"}[gold, prediction]] += 1
    denominator = sum(gold_counts.values())
    sensitivity = confusion["tp"] / gold_counts["yes"] if gold_counts["yes"] else None
    specificity = confusion["tn"] / gold_counts["no"] if gold_counts["no"] else None
    return {"hard_label_denominator": denominator, "soft_target_rows_excluded": len(rows) - denominator,
            "gold_counts": gold_counts, "correct_by_gold": {"no": confusion["tn"], "yes": confusion["tp"]},
            "valid_prediction_confusion": confusion, "errors_by_gold": errors, "pending_by_gold": pending,
            "all_row_sensitivity": sensitivity, "all_row_specificity": specificity,
            "all_row_balanced_accuracy": (sensitivity + specificity) / 2 if sensitivity is not None and specificity is not None else None,
            "always_no_accuracy_reference": gold_counts["no"] / denominator if denominator else None,
            "failure_policy": "Errors and missing predictions remain incorrect in each gold-class denominator."}


def metrics_for(rows, results):
    by_id = {result["id"]: result for result in results}
    groups = defaultdict(Counter)
    good, hard_count, hard_correct, positive_hits = [], 0, 0, 0
    attempted, errors = 0, 0
    for row in rows:
        hard = max(row["target"]) == 1.
        hard_count += hard
        group = groups[row["source"], row["group_id"]]
        group["rows"] += 1
        group["hard_rows"] += hard
        result = by_id.get(row["id"])
        if result is None:
            continue
        attempted += 1
        if result["status"] != "ok":
            errors += 1
            continue
        probabilities = result["probabilities_calibrated"]
        top = max(range(len(probabilities)), key=probabilities.__getitem__)
        hit = row["target"][top] > 0
        positive_hits += hit
        hard_correct += bool(hard and hit)
        group["positive_hits"] += hit
        group["hard_correct"] += bool(hard and hit)
        good.append(result)
    distributions = {}
    for key in ("uncalibrated", "calibrated"):
        distributions[key] = evaluate_probabilities([result["target"] for result in good],
            [result["probabilities_" + key] for result in good]) if good else None
    hard_groups = [group for group in groups.values() if group["hard_rows"]]
    report = {"denominator": len(rows), "attempted": attempted, "errors": errors, "pending": len(rows) - attempted,
        "valid_vectors": len(good), "valid_vector_coverage": len(good) / len(rows),
        "top1_positive_set_hits": positive_hits, "all_row_positive_set_accuracy": positive_hits / len(rows),
        "hard_label_denominator": hard_count, "hard_label_correct": hard_correct,
        "hard_label_accuracy": hard_correct / hard_count if hard_count else None,
        "soft_target_rows_excluded_from_hard_accuracy": len(rows) - hard_count,
        "distribution_metrics_valid_vectors_only": distributions,
        "group_macro": {"group_key": ["source", "group_id"], "group_count": len(groups),
            "positive_set_accuracy": sum(group["positive_hits"] / group["rows"] for group in groups.values()) / len(groups),
            "hard_label_group_count": len(hard_groups), "groups_without_hard_labels": len(groups) - len(hard_groups),
            "hard_label_accuracy": sum(group["hard_correct"] / group["hard_rows"] for group in hard_groups) / len(hard_groups) if hard_groups else None,
            "weighting": "Mean of within-group accuracies; each source/group_id receives equal weight in this reported subset.",
            "failure_policy": "Errors and missing predictions remain incorrect within their group; groups with no hard-label rows are excluded only from hard-label accuracy."}}
    diagnostic = noul_diagnostics(rows, by_id)
    if diagnostic is not None:
        report["noul_binary"] = diagnostic
    return report


def summarize(rows, results):
    source_rows = {row["id"]: row for row in rows}
    if len({result["id"] for result in results}) != len(results):
        raise ValueError("Duplicate paired inference result")
    for result in results:
        row = source_rows.get(result["id"])
        if row is None or any(result[key] != row[key] for key in ("source", "split", "kind", "target")) or result["input_sha256"] != input_digest(row):
            raise ValueError("Paired inference result is not bound to this panel")
    buckets = defaultdict(list)
    for row in rows:
        buckets[row["source"], row["split"], row["kind"]].append(row)
    return {"overall": metrics_for(rows, results), "by_source_split_kind": [
        {"source": source, "split": split, "kind": kind, **metrics_for(values, results)}
        for (source, split, kind), values in sorted(buckets.items())]}


def validate_pair_identities(identities):
    before, after = (identities[tag] for tag in TAGS)
    if (before["base_revision"] != after["base_revision"] or
            before["training_completion"]["run_identity_sha256"] == after["training_completion"]["run_identity_sha256"]):
        raise ValueError("Paired checkpoints must bind distinct completed runs on the same base revision")
    # Equal artifacts are a valid no-change outcome, not a failed experiment.
    return before["checkpoint_sha256"] == after["checkpoint_sha256"]


def implementation_hashes():
    return {name: file_hash(ROOT / name) for name in ("scripts/evaluate_community_pair.py",
        "scripts/run_service_suite.py", "jev/model.py", "jev/serving.py", "jev/metrics.py", "jev/api.py")}


def run(panel, directories, plan_path, output, max_seconds=14400):
    if not finite(max_seconds) or not 0 < max_seconds <= 86400:
        raise ValueError("Evaluation time bound must be positive and at most one day")
    deadline = time.monotonic() + max_seconds
    plan = read_json(plan_path)
    if (plan.get("schema_version") != 1 or list(plan.get("models", {})) != list(TAGS)
            or plan.get("panel_manifest_sha256") != file_hash(Path(panel) / "manifest.json")):
        raise ValueError("A frozen panel and ordered v2-final/v3-final plan are required")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if commit != plan["evaluation_commit"]:
        raise ValueError("Evaluation checkout differs from the pinned plan")
    subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--"], check=True)
    rows, manifest = load_panel(panel, directories)
    identities = {tag: completed_identity(plan["models"][tag], rows, commit) for tag in TAGS}
    content_equal = validate_pair_identities(identities)
    devices = os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",")
    if len(devices) != 1 or re.fullmatch(r"[0-9]+|GPU-[a-fA-F0-9-]+", devices[0]) is None:
        raise ValueError("Caller must expose exactly one leased CUDA device")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "status": "running", "panel": manifest,
              "plan_sha256": file_hash(plan_path), "evaluation_commit": commit,
              "identities_before": identities, "identities_after": {}, "checkpoint_content_equal": content_equal,
              "implementation_sha256": implementation_hashes(),
              "models": {tag: summarize(rows, []) for tag in TAGS}, "max_seconds": max_seconds,
              "retries": 0, "prefix_cache": False, "candidate_batch_size": 4,
              "publication_status": "requires_independent_postrun_audit"}
    write_json(output / "report.json", report)
    try:
        import torch
        from jev.model import DecisionModel
        from jev.serving import TorchScorer
        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise ValueError("Exactly one visible CUDA device is required")
        report["device"] = {"cuda_visible_devices": devices[0], "name": torch.cuda.get_device_name(0)}
        for tag in TAGS:
            model = DecisionModel.load(plan["models"][tag]["checkpoint"], device="cuda:0")
            if (model.model_id, model.revision, model.max_length) != (MODEL, REVISION, identities[tag]["max_length"]):
                raise ValueError("Loaded model identity differs")
            results = evaluate_rows(rows, TorchScorer(model), identities[tag], output / (tag + ".jsonl"), deadline)
            del model
            gc.collect()
            torch.cuda.empty_cache()
            after = completed_identity(plan["models"][tag], rows, commit)
            if after != identities[tag]:
                raise ValueError("Checkpoint/data/completion identity changed during inference")
            report["identities_after"][tag] = after
            report["models"][tag] = summarize(rows, results)
            write_json(output / "report.json", report)
        load_panel(panel, directories)
        if implementation_hashes() != report["implementation_sha256"]:
            raise ValueError("Evaluation implementation changed during the run")
        report["status"] = "complete" if all(report["models"][tag]["overall"]["errors"] == 0 for tag in TAGS) else "complete_with_errors"
    except BaseException as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error)[:1000])
        raise
    finally:
        for tag in TAGS:
            predictions = output / (tag + ".jsonl")
            if predictions.exists():
                try:
                    report["models"][tag] = summarize(rows, list(jsonl(predictions)))
                except (ValueError, KeyError) as error:
                    report.update(status="failed", result_audit_error=str(error)[:1000])
        write_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build-panel")
    build.add_argument("--data", action="append", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--per-source-split", type=int, default=128)
    build.add_argument("--seed", type=int, default=20260921)
    evaluate = subparsers.add_parser("run")
    evaluate.add_argument("--data", action="append", type=Path, required=True)
    evaluate.add_argument("--panel", type=Path, required=True)
    evaluate.add_argument("--plan", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--max-seconds", type=float, default=14400)
    args = parser.parse_args()
    report = build_panel(args.data, args.output, args.per_source_split, args.seed) if args.command == "build-panel" else run(args.panel, args.data, args.plan, args.output, args.max_seconds)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
