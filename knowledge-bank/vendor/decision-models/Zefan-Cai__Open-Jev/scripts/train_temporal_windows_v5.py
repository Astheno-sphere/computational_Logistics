"""One predeclared temporal pilot, fixed regression rows, and temperature ablations."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from jev.metrics import softmax
from jev.train import source_checkout_commit
from scripts.audit_temporal_windows_v5 import audit_directory, epoch_seconds
from scripts import train_frontier_controls_v4 as core
from scripts.temporal_pilot_lease import record_exit, register


def directory_sha(path):
    path = Path(path)
    digest = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            digest.update(str(file.relative_to(path)).encode() + b"\0")
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def noul_status(row, temperature):
    yes = softmax(row["logits"], temperature)[1]
    return "no" if yes <= 0.2 else "yes" if yes >= 0.8 else "abstained"


def temperature_metrics(rows, temperature):
    transformed = [{**row, "probabilities": softmax(row["logits"], temperature), "temperature": temperature} for row in rows]
    summary = core.summarize(transformed)
    names = ("count", "accuracy", "nll", "brier", "multiclass_ece")
    compact = {key: summary[key] for key in names}
    compact["by_family"] = {name: {key: value[key] for key in names} for name, value in summary["by_family"].items()}
    compact["by_kind"] = {name: {key: value[key] for key in names} for name, value in summary["by_kind"].items()}
    noul = [row for row in rows if row["kind"] == "noul"]
    statuses = [noul_status(row, temperature) for row in noul]
    accepted = sum(value != "abstained" for value in statuses)
    correct = sum(value == ("yes" if row["target"][1] == 1.0 else "no") for row, value in zip(noul, statuses))
    compact["noul_thresholds_0.2_0.8"] = {"n": len(noul), "correct": correct,
        "accuracy": correct / len(noul) if noul else None, "accepted": accepted,
        "coverage": accepted / len(noul) if noul else None, "abstentions": len(noul) - accepted,
        "error_among_accepted": (accepted - correct) / accepted if accepted else None}
    return compact


def four_combinations(baseline, trained, released_temperature, trained_temperature):
    return {weight + "_logits_at_" + calibration + "_temperature": temperature_metrics(rows, temperature)
            for weight, rows in (("baseline", baseline), ("trained", trained))
            for calibration, temperature in (("released", released_temperature), ("trained", trained_temperature))}


def paired_decisions(baseline, trained, released_temperature, trained_temperature):
    if [row["id"] for row in baseline] != [row["id"] for row in trained]:
        raise ValueError("Paired regression IDs differ")
    result = {"n": len(baseline), "correct_to_correct": 0, "incorrect_to_correct": 0,
              "correct_to_incorrect": 0, "incorrect_to_incorrect": 0, "argmax_changed": 0,
              "noul_status_transitions": {}}
    for a, b in zip(baseline, trained):
        if a["target"] != b["target"] or a["kind"] != b["kind"]:
            raise ValueError("Paired regression targets or types differ")
        before, after = (max(range(len(row["logits"])), key=row["logits"].__getitem__) for row in (a, b))
        truth = a["target"].index(1.0)
        result[("correct" if before == truth else "incorrect") + "_to_" + ("correct" if after == truth else "incorrect")] += 1
        result["argmax_changed"] += int(before != after)
        if a["kind"] == "noul":
            transition = noul_status(a, released_temperature) + "_to_" + noul_status(b, trained_temperature)
            result["noul_status_transitions"][transition] = result["noul_status_transitions"].get(transition, 0) + 1
    return result


def prepare(args):
    plan = json.loads(Path(args.plan).read_text())
    if core.file_sha(Path(args.dataset) / "manifest.json") != plan["dataset_manifest_sha256"]:
        raise ValueError("V5 dataset differs from the predeclared plan")
    audit = audit_directory(args.dataset)
    settings = plan["settings"]
    if settings != {"steps": 64, "accumulation": 4, "train_rows": 128, "calibration_rows": 32,
                    "eval_rows_per_split": 32, "lr": 2e-5, "head_lr": 5e-5,
                    "brier_weight": 0.1, "seed": 20261002, "max_length": 4096}:
        raise ValueError("Fixed v5 training schedule changed")
    initial = core.checkpoint_identity(args.checkpoint)
    proof = json.loads((Path(__file__).resolve().parents[1] / "reports/efficiency-20261002/h200-2b-package-provenance.json").read_text())
    expected = {name.removeprefix("checkpoint/"): value["sha256"] for name, value in proof["files"].items()}
    if (initial["files_sha256"] != expected or initial["config"]["revision"] != plan["base_revision"]
            or proof["checkpoint_sha256"] not in plan["base_checkpoint"]
            or directory_sha(args.checkpoint) != proof["checkpoint_sha256"]):
        raise ValueError("The exact released 2B checkpoint is required")
    selected, selection = core.load_selection(args.dataset, 128, 32, 32, 20261002)
    regression_lock = json.loads(Path(args.regression_lock).read_text())["selection"]
    _, current = core.load_selection(args.regression_data, 256, 64, 128, 20261002)
    if current != regression_lock:
        raise ValueError("Original v4 regression selection or hashes changed")
    regression = {}
    for split in ("test", "ood"):
        lookup = {row["id"]: row for row in map(json.loads, (Path(args.regression_data) / (split + ".jsonl")).read_text().splitlines())}
        regression[split] = [lookup[key] for key in regression_lock["selected_ids"][split]]
    return plan, initial, selected, selection, regression, audit


def regression_predictions(checkpoint, rows, output, prefix, temperature, device):
    import torch
    from jev.model import DecisionModel
    model = DecisionModel.load(checkpoint, device=device)
    predictions = {split: core.evaluate(model, values, output / (prefix + "_v4_" + split + ".jsonl"), temperature, torch)
                   for split, values in rows.items()}
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return predictions


def read_journal(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def run_registered(args):
    plan, initial, selected, selection, regression, audit = prepare(args)
    commit = source_checkout_commit(__file__)
    if commit != args.expected_commit:
        raise ValueError("Pilot source differs from the pushed immutable commit")
    output = Path(args.output)
    if output.exists():
        raise FileExistsError("Choose a new immutable pilot directory")
    output.mkdir(parents=True)
    core.write_json(output / "pilot.lock.json", {"plan": plan, "plan_sha256": core.file_sha(args.plan),
        "code_commit": commit, "wrapper_sha256": core.file_sha(__file__), "baseline_checkpoint": initial,
        "v5_selection": selection, "v4_regression_selection": json.loads(Path(args.regression_lock).read_text())["selection"],
        "independent_v5_audit": audit})
    baseline_regression = regression_predictions(args.checkpoint, regression, output, "baseline", initial["temperature"], args.device)
    adaptation = output / "adaptation"
    settings = plan["settings"]
    core.run(SimpleNamespace(checkpoint=args.checkpoint, data=args.dataset, output=str(adaptation), device=args.device,
        steps=settings["steps"], accumulation=settings["accumulation"], train_rows=128, calibration_rows=32, eval_rows=32,
        lr=settings["lr"], head_lr=settings["head_lr"], brier_weight=settings["brier_weight"], max_length=4096, seed=settings["seed"]))
    training = json.loads((adaptation / "summary.json").read_text())
    trained_temperature = training["trained_temperature"]
    trained_regression = regression_predictions(adaptation / "checkpoint", regression, output, "trained", trained_temperature, args.device)
    summaries, paired, subgroup = {}, {}, {}
    for split in ("test", "ood"):
        before = read_journal(adaptation / ("baseline_" + split + ".jsonl"))
        after = read_journal(adaptation / ("trained_" + split + ".jsonl"))
        summaries["v5_" + split] = four_combinations(before, after, initial["temperature"], trained_temperature)
        summaries["v4_" + split] = four_combinations(baseline_regression[split], trained_regression[split], initial["temperature"], trained_temperature)
        paired["v5_" + split] = paired_decisions(before, after, initial["temperature"], trained_temperature)
        paired["v4_" + split] = paired_decisions(baseline_regression[split], trained_regression[split], initial["temperature"], trained_temperature)
        groups = {"boundary": {}, "offset_pair": {}}
        for row in selected[split]:
            state = row["state"]
            delta = epoch_seconds(state["request_received_at"]) - epoch_seconds(state["delivered_at"])
            end = state["return_window_hours"] * 3600
            boundary = "exception" if state["exception_approved"] else "before_delivery" if delta < 0 else "at_delivery" if delta == 0 else "inside_window" if delta < end else "at_deadline" if delta == end else "after_deadline"
            offsets = state["delivered_at"][-6:] + " to " + state["request_received_at"][-6:]
            for category, label in (("boundary", boundary), ("offset_pair", offsets)):
                groups[category].setdefault(label, set()).add(row["id"])
        subgroup[split] = {category: {label: four_combinations([r for r in before if r["id"] in ids], [r for r in after if r["id"] in ids], initial["temperature"], trained_temperature)
                                     for label, ids in values.items()} for category, values in groups.items()}
    if core.checkpoint_identity(args.checkpoint) != initial:
        raise ValueError("Released checkpoint changed")
    core.write_json(output / "summary.json", {"status": "complete", "code_commit": commit,
        "plan_sha256": core.file_sha(args.plan), "released_temperature": initial["temperature"],
        "trained_temperature": trained_temperature, "steps": 64, "training_rows_consumed": 256,
        "distinct_training_rows": 128, "reload_max_probability_error": training["reload_max_probability_error"],
        "trained_checkpoint": training["trained_checkpoint"], "metrics": summaries, "paired_decisions": paired,
        "boundary_offset_results": subgroup, "scope": plan["scope"],
        "limitation": "One fixed synthetic pilot; v4 regression rows were already development evidence; four temperature combinations isolate descriptive effects, not causal/generalization proof"})


def run(args):
    identity = register(args.lease, args.controller_stamp, args.gpu_uuid, args.expected_commit, args.output)
    status = "failed"
    try:
        run_registered(args)
        status = "complete"
    finally:
        record_exit(args.lease, args.controller_stamp, identity, status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "dataset", "regression-data", "regression-lock", "plan", "output", "expected-commit", "lease", "controller-stamp", "gpu-uuid"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
