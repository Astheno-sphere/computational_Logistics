"""CPU-only independent arithmetic audit of saved 2B full-pass evidence.

No jev metrics/packager imports, tensor loading, remote access, or model calls.
Usage: python reports/fullpass-2b-n1/verify.py --evidence runs/fullpass-n1-v1/2b-evidence
"""
import argparse
from collections import defaultdict, deque
import datetime
import hashlib
import json
import math
from pathlib import Path
import random


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, "duplicate JSON key"
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def read(path):
    return decode(Path(path).read_bytes())


def rows(path):
    with Path(path).open("rb") as handle:
        return [decode(line) for line in handle if line.strip()]


def softmax(logits, temperature=1.0):
    maximum = max(logits)
    weights = [math.exp((v - maximum) / temperature) for v in logits]
    total = sum(weights)
    return [v / total for v in weights]


def evaluate(values, temperature):
    probabilities = [softmax(r["logits"], temperature) for r in values]
    observations, nll, brier, expected_brier = [], [], [], []
    bins = defaultdict(list)
    for row, p in zip(values, probabilities):
        p = [x / sum(p) for x in p]
        q = [x / sum(row["target"]) for x in row["target"]]
        prediction = p.index(max(p))
        confidence, correct, hard = p[prediction], q[prediction], max(q) == 1
        observations.append((confidence, correct, hard))
        bins[min(14, int(confidence * 15))].append((confidence, correct))
        nll.append(-sum(t * math.log(max(x, 1e-15)) for x, t in zip(p, q)))
        squared = sum((x - t) ** 2 for x, t in zip(p, q))
        brier.append(squared)
        expected_brier.append(squared + 1 - sum(t * t for t in q))
    def coverage(chosen):
        hard = [correct for _, correct, is_hard in chosen if is_hard]
        accuracy = sum(correct for _, correct, _ in chosen) / len(chosen) if chosen else None
        return {"selected": len(chosen), "coverage": len(chosen) / len(values),
                "accuracy": sum(hard) / len(hard) if hard else None,
                "expected_accuracy": accuracy, "expected_risk": 1 - accuracy if chosen else None}
    overall = coverage(observations)
    metric = {"count": len(values), "hard_count": sum(o[2] for o in observations),
              "accuracy": overall["accuracy"], "expected_accuracy": overall["expected_accuracy"],
              "nll": sum(nll) / len(values), "brier": sum(brier) / len(values),
              "expected_brier": sum(expected_brier) / len(values), "ece_bins": 15,
              "multiclass_ece": sum(abs(sum(c for c, _ in b) - sum(q for _, q in b)) for b in bins.values()) / len(values),
              "coverage": [{"threshold": t, **coverage([o for o in observations if o[0] >= t])}
                           for t in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99)]}
    return metric, probabilities


def full_metrics(values, temperature):
    metric, _ = evaluate(values, temperature)
    metric["mean_latency_seconds"] = sum(r["latency_seconds"] for r in values) / len(values)
    for field, name in (("kind", "by_kind"), ("source", "by_source"), ("question_id", "by_question")):
        groups = defaultdict(list)
        for row in values:
            groups[(row["source"], row[field]) if field == "question_id" else row[field]].append(row)
        metric[name] = {}
        for key, subset in sorted(groups.items()):
            group, probabilities = evaluate(subset, temperature)
            if field == "kind" and key == "score":
                group["ordinal_mae"] = sum(abs(sum(i * x for i, x in enumerate(p)) - sum(i * x for i, x in enumerate(r["target"]))) for r, p in zip(subset, probabilities)) / len(subset)
            if field == "source" and key.startswith("wikispeedia"):
                group["optimal_action_hit"] = sum(r["target"][p.index(max(p))] > 0 for r, p in zip(subset, probabilities)) / len(subset)
                group["optimal_set_probability_mass"] = sum(sum(x for x, q in zip(p, r["target"]) if q > 0) for r, p in zip(subset, probabilities)) / len(subset)
            metric[name]["/".join(key) if isinstance(key, tuple) else key] = group
    return metric


def refit(values):
    """Minimize convex cross-entropy in inverse temperature, independently."""
    prepared = []
    for row in values:
        logits = [v - max(row["logits"]) for v in row["logits"]]
        total = sum(row["target"])
        prepared.append((logits, sum(q / total * v for q, v in zip(row["target"], logits))))
    def loss(beta):
        return sum(math.log(sum(math.exp(beta * v) for v in logits)) - beta * target for logits, target in prepared) / len(prepared)
    low, high = 1 / 20, 1 / 0.05
    ratio = (math.sqrt(5) - 1) / 2
    a, b = high - ratio * (high - low), low + ratio * (high - low)
    fa, fb = loss(a), loss(b)
    for _ in range(90):
        if fa < fb:
            high, b, fb = b, a, fa
            a = high - ratio * (high - low)
            fa = loss(a)
        else:
            low, a, fa = a, b, fb
            b = low + ratio * (high - low)
            fb = loss(b)
    beta = min((a, b, 1 / 20, 1 / 0.05), key=loss)
    return 1 / beta, loss(beta), loss


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=Path("data/release-v2"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("independent-audit.json"))
    args = parser.parse_args()
    snapshots = sorted(args.evidence.glob("source-snapshot-*.json"))
    assert snapshots, "source snapshot missing"
    snapshot = read(snapshots[-1])
    for name, info in snapshot["files"].items():
        assert sha(args.evidence / name) == info["sha256"], name
        assert (args.evidence / name).stat().st_size == info["bytes"], name
    run, summary = read(args.evidence / "run.json"), read(args.evidence / "summary.json")
    manifest = read(args.data / "manifest.json")
    assert sha(args.data / "manifest.json") == "56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97"
    assert run["data_sha256"] == manifest["sha256"]
    assert summary["status"] == "complete" and summary["steps"] == run["steps"] == 20204
    assert summary["trained_rows_consumed"] == run["steps"] * run["accumulation"] == 80816
    assert run["train_rows"] == 0 and run["training_sampling"] == "shuffled" and not run["resume_training"]
    log = rows(args.evidence / "training.jsonl")
    assert [r["step"] for r in log] == list(range(1, 20205))
    assert all(math.isfinite(r[k]) and r[k] >= 0 for r in log for k in ("loss", "gradient_norm", "elapsed_seconds"))
    assert all(b["elapsed_seconds"] >= a["elapsed_seconds"] for a, b in zip(log, log[1:]))
    selected, all_ids, group_splits = {}, set(), {}
    for split in ("train", "calibration", "validation", "test", "ood"):
        assert sha(args.data / (split + ".jsonl")) == run["data_sha256"][split]
        records = []
        for row in rows(args.data / (split + ".jsonl")):
            assert row["split"] == split and row["id"] not in all_ids
            all_ids.add(row["id"])
            assert group_splits.setdefault(row["group_id"], split) == split
            records.append({**{k: row[k] for k in ("id", "group_id", "kind", "source", "target")},
                            "question_id": row["metadata"].get("question_id", row["kind"]),
                            "target_basis": row["metadata"].get("target_basis", "hard_label")})
        assert len(records) == manifest["counts"][split]
        if split in ("train", "validation"):
            continue
        random.Random(run["seed"]).shuffle(records)
        buckets = {}
        for row in records:
            buckets.setdefault((row["source"], row["kind"]), []).append(row)
        active = deque(buckets.values())
        selected[split] = []
        while active and len(selected[split]) < 512:
            bucket = active.popleft()
            selected[split].append(bucket.pop())
            if bucket:
                active.append(bucket)
        ids_key = {"test": "evaluation_ids", "ood": "ood_ids", "calibration": "calibration_ids"}[split]
        assert [r["id"] for r in selected[split]] == run[ids_key]
    predictions, max_probability_error = {}, 0.0
    for split in ("test", "ood", "calibration"):
        for stage in ("baseline", "trained"):
            name = stage + "_" + split + ".jsonl" if (stage, split) != ("trained", "calibration") else "calibration.jsonl"
            values = rows(args.evidence / name)
            assert len(values) == 512
            for value, expected in zip(values, selected[split]):
                assert all(value[k] == v for k, v in expected.items()), name
                assert len(value["logits"]) == len(expected["target"]) == len(value["probabilities"])
                assert all(math.isfinite(v) for v in value["logits"])
                assert math.isfinite(value["latency_seconds"]) and value["latency_seconds"] >= 0
                for x, y in zip(softmax(value["logits"]), value["probabilities"]):
                    assert math.isfinite(y) and math.isclose(x, y, rel_tol=1e-5, abs_tol=2e-6)
                    max_probability_error = max(max_probability_error, abs(x-y))
            predictions[stage, split] = values
    temperatures = {}
    for stage, key in (("baseline", "baseline_temperature"), ("trained", "temperature")):
        independent, optimum, loss = refit(predictions[stage, "calibration"])
        recorded = summary[key]
        regret = loss(1 / recorded) - optimum
        assert math.isclose(recorded, independent, rel_tol=1e-4, abs_tol=1e-5) and abs(regret) < 1e-9
        temperatures[stage] = {"recorded": recorded, "independent_convex_refit": independent,
                               "calibration_nll_regret": regret, "calibration_rows": 512}
    config, temperature = read(args.evidence / "checkpoint/model.json"), read(args.evidence / "checkpoint/temperature.json")
    assert config["model_id"] == run["model"] == "Qwen/Qwen3.5-2B"
    assert config["revision"] == run["revision"] == "15852e8c16360a2fea060d615a32b45270f8a8fc"
    assert config["method"] == "independent_candidate_lora_nll_brier"
    assert config["lora_rank"] == run["lora_rank"] and config["max_length"] == run["max_length"]
    assert temperature == {"temperature": summary["temperature"], "split": "calibration", "n": 512,
                           "ids_sha256": hashlib.sha256(json.dumps(run["calibration_ids"]).encode()).hexdigest()}
    checked, maximum_error = 0, 0.0
    def compare(a, b, path):
        nonlocal checked, maximum_error
        if isinstance(a, dict):
            assert a.keys() == b.keys(), path
            for key in a:
                compare(a[key], b[key], path + "/" + key)
        elif isinstance(a, list):
            assert len(a) == len(b), path
            for i, (x, y) in enumerate(zip(a, b)):
                compare(x, y, path + "/" + str(i))
        elif a is None:
            assert b is None, path
        else:
            assert type(b) in (int, float) and math.isfinite(b), path
            assert math.isclose(a, b, rel_tol=1e-8, abs_tol=1e-8), (path, a, b)
            maximum_error = max(maximum_error, abs(a-b))
            checked += 1
    metrics = {}
    for split in ("test", "ood"):
        for prefix, stage, temp in (("baseline", "baseline", 1), ("baseline_calibrated", "baseline", summary["baseline_temperature"]),
                                    ("trained", "trained", 1), ("calibrated", "trained", summary["temperature"])):
            name = prefix + "_" + split
            metrics[name] = full_metrics(predictions[stage, split], temp)
            compare(metrics[name], summary["metrics"][name], name)
    assert metrics.keys() == summary["metrics"].keys()
    reload = rows(args.evidence / "reload_check.jsonl")
    assert len(reload) == 1
    assert all(reload[0][k] == v for k, v in selected["test"][0].items())
    reference = predictions["trained", "test"][0]["logits"]
    assert len(reload[0]["logits"]) == len(reference) and all(math.isfinite(x) for x in reload[0]["logits"])
    reload_error = max(abs(a-b) for a, b in zip(reload[0]["logits"], reference))
    assert reload_error == summary["checkpoint_reload_max_error"] == 0
    comparisons = []
    for split in ("test", "ood"):
        for source, trained in metrics["calibrated_"+split]["by_source"].items():
            base = metrics["baseline_calibrated_"+split]["by_source"][source]
            comparisons.append({"split": split, "source": source, "count": trained["count"], "hard_count": trained["hard_count"],
                                "baseline": {k: base[k] for k in ("accuracy", "expected_accuracy", "nll", "brier", "multiclass_ece")},
                                "trained": {k: trained[k] for k in ("accuracy", "expected_accuracy", "nll", "brier", "multiclass_ece")},
                                "expected_accuracy_delta": trained["expected_accuracy"]-base["expected_accuracy"]})
    report = {"schema_version": 1, "audited_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "passed": True, "failures": [],
              "scope": "Independent CPU arithmetic from saved predictions; no model/tensor loading, GPU calls, JF100 inspection, game or closed-loop evaluation.",
              "model": run["model"], "revision": run["revision"], "training_code_commit": run["commit"], "run_identity_sha256": run["run_identity_sha256"],
              "training": {"completed_steps": 20204, "global_batch": 4, "records_consumed": 80816, "frozen_train_rows": 80816,
                           "sampling": "shuffled", "resume_training": False, "training_log_steps_contiguous": True,
                           "elapsed_seconds": summary["elapsed_seconds"], "coverage_basis": "Saved run configuration and one finite, contiguous training log per optimizer step; no independent replay of gradients."},
              "data": {"name": "release-v2", "manifest_sha256": sha(args.data / "manifest.json"), "sha256": run["data_sha256"],
                       "rows_by_split": manifest["counts"], "selected": {"test": 512, "ood": 512, "calibration": 512},
                       "sampling": "source_kind_round_robin", "seed": run["seed"], "all_data_ids_unique": True, "groups_do_not_cross_splits": True,
                       "scope_note": "512 test + 512 OOD sampled rows, not a full 26,452-row held-out evaluation. Target probabilities, IDs and question metadata bind to the frozen rows."},
              "verification": {"independent_script_sha256": sha(__file__), "numeric_metric_leaves_checked": checked,
                               "core_and_grouped_sections": 8, "maximum_metric_absolute_error": maximum_error,
                               "maximum_raw_probability_absolute_error": max_probability_error, "temperatures": temperatures},
              "reload": {"saved_test_rows": 1, "maximum_saved_logit_difference": reload_error,
                         "current_weights_loaded": False, "historical_reload_cryptographically_bound_to_current_weights": False,
                         "limitation": "Training saved no contemporaneous output-weight digest. Current checkpoint byte hashes establish the snapshot identity only; they do not prove the historical reload used these same bytes."},
              "source_snapshot_sha256": sha(snapshots[-1]), "source_evidence": snapshot["files"], "checkpoint_current_bytes": snapshot["checkpoint_current_bytes"],
              "metrics": metrics, "source_comparisons_calibrated": comparisons}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"passed": True, "output": str(args.output), "sha256": sha(args.output),
                      "numeric_leaves_checked": checked, "maximum_error": maximum_error, "temperatures": temperatures}))


if __name__ == "__main__":
    main()
