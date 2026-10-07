"""Fixed-step continued LoRA training with a released-checkpoint baseline."""
import argparse
import gc
import hashlib
import json
import math
from pathlib import Path
import random
import time

from jev.frontier_controls_v4 import FAMILIES, audit, digest
from jev.metrics import evaluate_probabilities, fit_temperature, softmax
from jev.train import source_checkout_commit


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def checkpoint_identity(path):
    path = Path(path)
    required = ("model.json", "head.pt", "temperature.json", "adapter/adapter_config.json")
    if any(not (path / name).is_file() for name in required):
        raise ValueError("A released LoRA checkpoint with head and temperature is required")
    weights = [p for p in (path / "adapter").glob("adapter_model.*") if p.suffix in (".bin", ".safetensors")]
    if not weights:
        raise ValueError("Checkpoint adapter weights are missing")
    names = sorted([*required, *(p.relative_to(path).as_posix() for p in weights)])
    hashes = {name: file_sha(path / name) for name in names}
    config = json.loads((path / "model.json").read_text())
    revision = config.get("revision")
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdefABCDEF" for c in revision):
        raise ValueError("Released checkpoint requires a pinned 40-character base revision")
    temperature = float(json.loads((path / "temperature.json").read_text())["temperature"])
    if not math.isfinite(temperature) or temperature <= 0 or config["lora_rank"] < 1:
        raise ValueError("Invalid released temperature or LoRA rank")
    return {"files_sha256": hashes, "sha256": digest(hashes), "config": config, "temperature": temperature}


def select_groups(rows, limit, seed):
    """Keep all four counterfactuals; round-robin families without using labels."""
    if limit < 4 or limit % 4:
        raise ValueError("Row limits must be positive multiples of four")
    groups = {}
    for row in rows:
        groups.setdefault(row["group_id"], []).append(row)
    if any(len(group) != 4 for group in groups.values()):
        raise ValueError("Every control group must contain four counterfactuals")
    buckets = {family: [] for family in FAMILIES}
    for group in groups.values():
        buckets[group[0]["metadata"]["scenario_family"]].append(group)
    for bucket in buckets.values():
        bucket.sort(key=lambda group: digest([seed, group[0]["group_id"]]))
    selected = []
    while len(selected) < limit and any(buckets.values()):
        for family in FAMILIES:
            if buckets[family] and len(selected) < limit:
                selected.extend(sorted(buckets[family].pop(), key=lambda row: row["id"]))
    if len(selected) != limit:
        raise ValueError("Requested more rows than the frozen split contains")
    return selected


def load_selection(directory, train_rows, calibration_rows, eval_rows, seed):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    all_rows, splits = [], {}
    for name, expected in manifest["files_sha256"].items():
        path = directory / name
        if file_sha(path) != expected:
            raise ValueError("Frozen dataset hash changed: " + name)
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if any(row["split"] != path.stem for row in rows):
            raise ValueError("Record is in the wrong split")
        splits[path.stem] = rows
        all_rows.extend(rows)
    audit(all_rows)
    counts = {"train": train_rows, "calibration": calibration_rows, "test": eval_rows, "ood": eval_rows}
    selected = {name: select_groups(splits[name], count, seed) for name, count in counts.items()}
    identity = {"manifest_sha256": file_sha(directory / "manifest.json"),
                "split_sha256": manifest["files_sha256"],
                "selected_ids": {name: [row["id"] for row in rows] for name, rows in selected.items()},
                "selected_sha256": {name: digest(rows) for name, rows in selected.items()}}
    return selected, identity


def enable_adaptation(model):
    """Loaded PEFT adapters are frozen by default; train only LoRA A/B and head."""
    model.requires_grad_(False)
    names = []
    for name, parameter in model.named_parameters():
        if name.startswith("head.") or ".lora_A." in name or ".lora_B." in name:
            parameter.requires_grad_(True)
            names.append(name)
    if not any(".lora_A." in name for name in names) or not any(name.startswith("head.") for name in names):
        raise ValueError("Continued training requires an existing LoRA adapter and decision head")
    model.backbone.gradient_checkpointing_enable()
    model.backbone.enable_input_require_grads()
    return names


def evaluate(model, rows, path, temperature, torch):
    model.eval()
    result = []
    with torch.inference_mode(), Path(path).open("w") as handle:
        for row in rows:
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            started = time.perf_counter()
            logits = model([row])[0].float().cpu().tolist()
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            record = {"id": row["id"], "split": row["split"], "kind": row["kind"],
                      "family": row["metadata"]["scenario_family"], "target": row["target"],
                      "logits": logits, "probabilities": softmax(logits, temperature),
                      "temperature": temperature, "wall_seconds": time.perf_counter() - started}
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            result.append(record)
    return result


def calibrate(rows):
    if not rows or any(row["split"] != "calibration" for row in rows):
        raise ValueError("Temperature fitting accepts only independent calibration rows")
    return fit_temperature([row["logits"] for row in rows], [row["target"] for row in rows])


def summarize(rows):
    def metrics(selected):
        return evaluate_probabilities([row["target"] for row in selected], [row["probabilities"] for row in selected])
    return {**metrics(rows), "mean_wall_seconds": sum(row["wall_seconds"] for row in rows) / len(rows),
            "by_family": {family: metrics([row for row in rows if row["family"] == family])
                          for family in sorted({row["family"] for row in rows})},
            "by_kind": {kind: metrics([row for row in rows if row["kind"] == kind])
                        for kind in sorted({row["kind"] for row in rows})}}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run(args):
    if (args.steps < 1 or args.accumulation < 1 or args.max_length < 0
            or any(not math.isfinite(x) for x in (args.lr, args.head_lr, args.brier_weight))
            or args.lr <= 0 or args.head_lr <= 0 or args.brier_weight < 0):
        raise ValueError("Training settings must be positive; Brier weight must be nonnegative")
    out = Path(args.output)
    if out.exists():
        raise FileExistsError("Choose a new immutable run directory")
    initial = checkpoint_identity(args.checkpoint)
    rows, selection = load_selection(args.data, args.train_rows, args.calibration_rows, args.eval_rows, args.seed)
    commit = source_checkout_commit(__file__)
    import torch
    from importlib.metadata import version
    from jev.model import DecisionModel
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    out.mkdir(parents=True)
    lock = {"checkpoint": initial, "selection": selection, "settings": vars(args), "code_commit": commit,
            "runner_sha256": file_sha(__file__), "selection_policy": "whole_groups_family_round_robin",
            "checkpoint_selection": "fixed_final_step_no_test_or_validation_selection",
            "runtime": {"torch": str(torch.__version__), "transformers": version("transformers"), "peft": version("peft")}}
    write_json(out / "run.lock.json", lock)
    started = time.perf_counter()
    model = DecisionModel.load(args.checkpoint, device=args.device)
    if args.max_length:
        model.max_length = args.max_length
    baseline = {split: evaluate(model, rows[split], out / f"baseline_{split}.jsonl", initial["temperature"], torch)
                for split in ("test", "ood")}
    print(json.dumps({"event": "baseline_complete", "test_rows": len(rows["test"]), "ood_rows": len(rows["ood"])}), flush=True)
    names = enable_adaptation(model)
    write_json(out / "trainable.json", {"names": names, "parameters": sum(p.numel() for p in model.parameters() if p.requires_grad)})
    optimizer = torch.optim.AdamW([
        {"params": [p for p in model.backbone.parameters() if p.requires_grad], "lr": args.lr},
        {"params": [p for p in model.head.parameters() if p.requires_grad], "lr": args.head_lr}], weight_decay=0.01)
    training_rows = list(rows["train"])
    random.Random(args.seed).shuffle(training_rows)
    model.train()
    with (out / "training.jsonl").open("w") as handle:
        for step in range(args.steps):
            optimizer.zero_grad(set_to_none=True)
            total = 0.0
            for micro in range(args.accumulation):
                row = training_rows[(step * args.accumulation + micro) % len(training_rows)]
                logits = model([row])[0].float()
                target = torch.tensor(row["target"], device=logits.device)
                loss = -(target * logits.log_softmax(-1)).sum() + args.brier_weight * ((logits.softmax(-1) - target) ** 2).sum()
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite training loss")
                (loss / args.accumulation).backward()
                total += float(loss.detach()) / args.accumulation
            norm = torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            if not torch.isfinite(norm):
                raise FloatingPointError("Nonfinite training gradient")
            optimizer.step()
            record = {"step": step + 1, "loss": total, "gradient_norm": float(norm),
                      "wall_seconds": time.perf_counter() - started}
            handle.write(json.dumps(record) + "\n")
            handle.flush()
            print(json.dumps(record), flush=True)
    model.save(out / "checkpoint")
    calibration = evaluate(model, rows["calibration"], out / "calibration.jsonl", 1.0, torch)
    temperature = calibrate(calibration)
    write_json(out / "checkpoint/temperature.json", {"temperature": temperature, "split": "calibration",
               "n": len(calibration), "selected_ids_sha256": digest(selection["selected_ids"]["calibration"])})
    # Freeze temperature before evaluating the trained checkpoint on test/OOD.
    write_json(out / "calibration.lock.json", {"temperature": temperature, "split": "calibration",
               "selection_sha256": selection["selected_sha256"]["calibration"], "checkpoint": checkpoint_identity(out / "checkpoint")})
    trained = {split: evaluate(model, rows[split], out / f"trained_{split}.jsonl", temperature, torch)
               for split in ("test", "ood")}
    checks = [rows["test"][0], next(row for row in rows["test"] if row["kind"] == "noul"), rows["ood"][0]]
    reference = {row["id"]: row for split in trained.values() for row in split}
    del optimizer, model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    model = DecisionModel.load(out / "checkpoint", device=args.device)
    reloaded = evaluate(model, checks, out / "reload-check.jsonl", temperature, torch)
    reload_error = max(abs(p - q) for row in reloaded for p, q in zip(row["probabilities"], reference[row["id"]]["probabilities"]))
    if reload_error > 0.005:
        raise ValueError(f"Saved/reloaded probability mismatch: {reload_error}")
    if checkpoint_identity(args.checkpoint) != initial:
        raise ValueError("Released baseline checkpoint was changed during the run")
    metrics = {f"{name}_{split}": summarize(values) for name, predictions in (("baseline", baseline), ("trained", trained)) for split, values in predictions.items()}
    summary = {"status": "complete", "metrics": metrics, "steps": args.steps,
               "training_rows_consumed": args.steps * args.accumulation,
               "released_temperature": initial["temperature"], "trained_temperature": temperature,
               "reload_max_probability_error": reload_error, "baseline_checkpoint": initial,
               "trained_checkpoint": checkpoint_identity(out / "checkpoint"), "code_commit": commit,
               "selection": selection, "wall_seconds": time.perf_counter() - started,
               "limitations": ["One bounded synthetic pilot seed; no JevBench or natural-request improvement claim",
                               "Controlled OOD variants of the same workflows, not wholly new domains",
                               "Continued training starts from a released checkpoint, not a pretrained base"]}
    write_json(out / "summary.json", summary)
    print(json.dumps({"event": "complete", "summary": str(out / "summary.json"), "metrics": metrics}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--steps", type=int, default=64)
    parser.add_argument("--train-rows", type=int, default=256)
    parser.add_argument("--calibration-rows", type=int, default=64)
    parser.add_argument("--eval-rows", type=int, default=128)
    parser.add_argument("--accumulation", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--head-lr", type=float, default=5e-5)
    parser.add_argument("--brier-weight", type=float, default=0.1)
    parser.add_argument("--max-length", type=int, default=0, help="0 retains the released checkpoint limit")
    parser.add_argument("--seed", type=int, default=20261002)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
