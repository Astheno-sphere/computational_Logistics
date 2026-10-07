"""Full fixed-temperature internal evaluation, separate from the training queue.

Launch four ranks through run_shared_sequence.py. No sampling, fitting, automatic
retry, checkpoint selection or legacy exclusive-GPU launcher is used here.
"""
import argparse
from collections import defaultdict
from datetime import timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from jev.data import validate_records
from jev.metrics import softmax
from jev.shared_resources import apply_allocator_budget, load_shared_policy, require, validate_visible_devices
from jev.train_distributed import on_rank_zero
from scripts.evaluate_checkpoints_parallel import (MODELS, RELEASE_V2_HASHES, canonical, file_hash,
                                                   object_hash, read_json, summarize, write_json)

ROOT = Path(__file__).resolve().parents[1]
V2_MANIFEST = "7b26f948d2ae11f20d7a18be437d1ada616fc479e1596ae94be7596787fe4e54"
V2_HASHES = {
    "train": "959dac64adc1717d92e9bb80371d4b940b2b5994f9e36e469b3eaed85883fdff",
    "calibration": "6a02712bc6dce4c99cae3acfa54cf049553d12e4b795cfa4c170bd7de5732981",
    "validation": "743ec57c076fee300bfe3e3eb364a8fb629addfd185724c0b66d58633bcd9372",
    "test": "2cd250906060a570e0c596f7bb6ee7fb299fbf314e011a8c72ecb78d70248295",
    "ood": "b575698e0f1006713ca736b96d1d8eb43a54d052e266c0f363b027b288f54498",
}
OLD_MANIFEST = "56105dc9fc89ef74919f5beb60bb6ae8c6e17bb95699dab59205f67d8b338d97"
COUNTS = {"test": 43301, "ood": 84486}
OLD_COUNTS = {"test": 10532, "ood": 15920}
TAGS = {"new27b": "27b", "new2b": "2b", "new9b": "9b", "old2b": "2b", "old9b": "9b"}


def load_frozen_data(path, manifest_sha256, split_hashes, counts):
    path = Path(path)
    require(file_hash(path / "manifest.json") == manifest_sha256, "Dataset manifest changed")
    manifest = read_json(path / "manifest.json")
    require(manifest.get("sha256") == split_hashes, "Dataset split hash manifest differs")
    rows = {}
    heldout_ids, other_ids = set(), set()
    for split, digest in split_hashes.items():
        raw = (path / (split + ".jsonl")).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == digest, "Dataset bytes changed: " + split)
        parsed = [json.loads(line) for line in raw.splitlines() if line.strip()]
        require(len(parsed) == manifest["counts"][split] and all(row["split"] == split for row in parsed),
                "Dataset split count/assignment differs")
        ids = [row["id"] for row in parsed]
        require(len(set(ids)) == len(ids), "Duplicate dataset IDs")
        if split in counts:
            require(len(parsed) == counts[split] and not heldout_ids.intersection(ids), "Full held-out denominator differs")
            heldout_ids.update(ids)
            rows[split] = parsed
        else:
            other_ids.update(ids)
    require(not heldout_ids.intersection(other_ids), "Held-out IDs overlap train/calibration/validation")
    validate_records(row for values in rows.values() for row in values)
    return rows


def load_panel(data, old_data):
    rows = load_frozen_data(data, V2_MANIFEST, V2_HASHES, COUNTS)
    old = load_frozen_data(old_data, OLD_MANIFEST, RELEASE_V2_HASHES, OLD_COUNTS)
    subsets = {}
    for split in COUNTS:
        index = {row["id"]: (i, object_hash(row)) for i, row in enumerate(rows[split])}
        subsets[split] = []
        for row in old[split]:
            require(row["id"] in index and index[row["id"]][1] == object_hash(row),
                    "Old held-out row is absent or changed in the full new panel: " + row["id"])
            subsets[split].append(index[row["id"]][0])
    identity = {"manifest_sha256": V2_MANIFEST, "split_sha256": V2_HASHES, "counts": COUNTS,
                "ordered_ids_sha256": {s: object_hash([r["id"] for r in rows[s]]) for s in COUNTS},
                "old_manifest_sha256": OLD_MANIFEST, "old_split_sha256": RELEASE_V2_HASHES,
                "old_counts": OLD_COUNTS, "old_subset_indices_sha256": object_hash(subsets)}
    return [(split, index, row) for split in COUNTS for index, row in enumerate(rows[split])], subsets, identity


def checkpoint_identity(path, tag, expected_sha256):
    require(tag in TAGS and re.fullmatch(r"[0-9a-f]{64}", expected_sha256), "A supported tag and checkpoint SHA256 are required")
    path = Path(path)
    require(path.is_dir() and not path.is_symlink(), "Checkpoint must be a regular directory")
    digest, files = hashlib.sha256(), {}
    for entry in sorted(path.rglob("*")):
        require(not entry.is_symlink() and (entry.is_file() or entry.is_dir()), "Nonregular checkpoint entry")
        if entry.is_file():
            relative = entry.relative_to(path).as_posix()
            digest.update(relative.encode() + b"\0")
            with entry.open("rb") as stream:
                for block in iter(lambda: stream.read(1048576), b""):
                    digest.update(block)
            files[relative] = file_hash(entry)
    require(digest.hexdigest() == expected_sha256, "Checkpoint bytes differ from the explicit pin")
    required = {"model.json", "temperature.json", "head.pt", "adapter/adapter_config.json", "adapter/adapter_model.safetensors"}
    require(required <= set(files), "Complete safetensors LoRA/head/calibration checkpoint is required")
    config, calibration = read_json(path / "model.json"), read_json(path / "temperature.json")
    require((config.get("model_id"), config.get("revision")) == MODELS[TAGS[tag]] and config.get("lora_rank") == 8,
            "Checkpoint model/revision/LoRA rank differs")
    temperature = calibration.get("temperature")
    require(type(temperature) in (int, float) and math.isfinite(temperature) and temperature > 0
            and calibration.get("split") == "calibration", "Invalid saved calibration; fitting is forbidden")
    return {"tag": tag, "model": config["model_id"], "revision": config["revision"], "lora_rank": 8,
            "checkpoint_sha256": expected_sha256, "files_sha256": files, "temperature": temperature,
            "calibration": calibration, "saved_max_length": config["max_length"]}


def implementation_identity():
    names = ("scripts/evaluate_internal_full.py", "scripts/evaluate_checkpoints_parallel.py", "jev/model.py",
             "jev/sharded_model.py", "jev/shared_resources.py", "jev/api.py", "jev/data.py", "jev/metrics.py")
    return {name: file_hash(ROOT / name) for name in names}


def assignments(items, rank):
    require(type(rank) is int and 0 <= rank < 4, "Exactly four ranks are required")
    return [(offset // 4, *item) for offset, item in enumerate(items) if offset % 4 == rank]


def row_identity(assigned, rank, identity):
    round_index, split, index, row = assigned
    return {"round": round_index, "split": split, "index": index, "rank": rank, "id": row["id"],
            "source": row["source"], "kind": row["kind"], "group_id": row["group_id"], "target": row["target"],
            "question_id": row["metadata"].get("question_id", row["kind"]), "row_sha256": object_hash(row),
            "eval_identity_sha256": object_hash(identity), "checkpoint_sha256": identity["checkpoint"]["checkpoint_sha256"],
            "data_split_sha256": identity["data"]["split_sha256"][split]}


def validate_result(result, assigned, rank, identity):
    require(all(result.get(key) == value for key, value in row_identity(assigned, rank, identity).items()),
            "Raw row ID/order/checkpoint/data identity differs")
    require(result.get("status") == "ok", "A recorded inference error requires review; it cannot be silently retried or removed")
    logits, probabilities = result.get("logits"), result.get("probabilities")
    require(isinstance(logits, list) and len(logits) == len(assigned[-1]["target"])
            and all(type(value) in (int, float) and math.isfinite(value) for value in logits), "Invalid raw logits")
    expected = softmax(logits, identity["checkpoint"]["temperature"])
    require(isinstance(probabilities, list) and len(probabilities) == len(expected)
            and all(type(value) in (int, float) and math.isfinite(value) and abs(value - target) <= 1e-12
                    for value, target in zip(probabilities, expected)), "Raw probabilities do not use the frozen temperature")
    require(type(result.get("input_tokens")) is int and result["input_tokens"] > 0, "Invalid raw token count")


def read_prefix(path, assigned, rank, identity):
    if not Path(path).exists():
        return []
    result = []
    with Path(path).open("rb") as stream:
        for line in stream:
            require(line.endswith(b"\n") and line.strip(), "Partial or blank raw line; preserve the file for explicit recovery")
            require(len(result) < len(assigned), "Extra raw rows")
            row = json.loads(line)
            validate_result(row, assigned[len(result)], rank, identity)
            result.append(row)
    return result


def aligned_resume_round(counts, totals):
    require(len(counts) == len(totals) == 4 and all(type(n) is int and 0 <= n <= total for n, total in zip(counts, totals)),
            "Invalid four-rank resume counts")
    completed = max(counts)
    require(all(count == min(completed, total) for count, total in zip(counts, totals)),
            "FSDP resume requires equal completed round prefixes; raw shards are preserved")
    return completed


def all_errors(error):
    import torch.distributed as dist
    errors = [None] * 4
    dist.all_gather_object(errors, error)
    return [value for value in errors if value is not None]


def checked_score(scorer, row):
    logits, tokens = scorer(row)
    require(isinstance(logits, list) and len(logits) == len(row["target"])
            and all(type(v) in (int, float) and math.isfinite(v) for v in logits)
            and type(tokens) is int and tokens > 0, "Scorer produced invalid logits/tokens")
    return logits, tokens


def parity_gate(items, rank, scorer, identity, directory):
    """One different row per rank, followed by the same four reference rows."""
    import torch.distributed as dist
    require(len(items) >= 4, "Four deterministic parity rows are required")
    indices = [i * (len(items) - 1) // 3 for i in range(4)]
    probes = [items[index][-1] for index in indices]
    error, own = None, None
    try:
        own = checked_score(scorer, probes[rank])[0]
    except Exception as caught:
        error = type(caught).__name__ + ": " + str(caught)
    errors = all_errors(error)
    if errors:
        on_rank_zero(lambda: write_json(Path(directory) / "probe.json", {"status": "failed", "errors": errors,
                                                                       "eval_identity_sha256": object_hash(identity)}))
        raise RuntimeError("Different-row FSDP parity probe failed")
    reference = None
    for index, row in enumerate(probes):
        error = None
        try:
            values = checked_score(scorer, row)[0]
            if rank == index:
                reference = values
        except Exception as caught:
            error = type(caught).__name__ + ": " + str(caught)
        errors = all_errors(error)
        if errors:
            on_rank_zero(lambda: write_json(Path(directory) / "probe.json", {"status": "failed", "errors": errors,
                                                                           "eval_identity_sha256": object_hash(identity)}))
            raise RuntimeError("Same-row FSDP reference probe failed")
    difference = max(abs(a - b) for a, b in zip(own, reference))
    same_argmax = max(range(len(own)), key=own.__getitem__) == max(range(len(reference)), key=reference.__getitem__)
    check = {"rank": rank, "row_id": probes[rank]["id"], "row_sha256": object_hash(probes[rank]),
             "max_logit_error": difference, "argmax_equal": same_argmax, "passed": difference <= .05 and same_argmax}
    checks = [None] * 4
    dist.all_gather_object(checks, check)
    report = {"status": "passed" if all(row["passed"] for row in checks) else "failed", "checks": checks,
              "eval_identity_sha256": object_hash(identity), "probe_indices": indices, "max_logit_error_allowed": .05,
              "scope": "Different rank rows versus same-row collective references; no measured speedup claimed"}
    on_rank_zero(lambda: write_json(Path(directory) / "probe.json", report))
    require(report["status"] == "passed", "Different-row FSDP parity gate failed; full evaluation was not started")
    return report


def evaluate_worker(items, rank, scorer, identity, directory, *, start=0):
    assigned = assignments(items, rank)
    collective = identity["backend"] == "fsdp4"
    rounds = (len(items) + 3) // 4 if collective else len(assigned)
    directory = Path(directory)
    path = directory / f"shard-{rank}.jsonl"
    progress = {"status": "running", "rank": rank, "planned_rows": len(assigned), "successful_rows": min(start, len(assigned)),
                "failed_rows": 0, "padding_forwards": 0, "eval_identity_sha256": object_hash(identity), "resumed_at_round": start}
    last_flush = 0
    with path.open("ab") as stream:
        try:
            for round_index in range(start, rounds):
                real = round_index < len(assigned)
                row = assigned[round_index][-1] if real else items[0][-1]
                error, result = None, None
                started = time.perf_counter()
                try:
                    logits, tokens = checked_score(scorer, row)
                    if real:
                        result = {**row_identity(assigned[round_index], rank, identity), "status": "ok", "logits": logits,
                                  "probabilities": softmax(logits, identity["checkpoint"]["temperature"]),
                                  "input_tokens": tokens, "wall_seconds": time.perf_counter() - started}
                except Exception as caught:
                    error = type(caught).__name__ + ": " + str(caught)
                    if real:
                        result = {**row_identity(assigned[round_index], rank, identity), "status": "error",
                                  "error_type": type(caught).__name__, "error": str(caught),
                                  "wall_seconds": time.perf_counter() - started}
                try:
                    if real:
                        stream.write((canonical(result) + "\n").encode())
                        stream.flush()
                        progress["successful_rows" if error is None else "failed_rows"] += 1
                    else:
                        progress["padding_forwards"] += 1
                    if time.monotonic() - last_flush >= 10:
                        os.fsync(stream.fileno())
                        write_json(directory / f"progress-{rank}.json", progress)
                        last_flush = time.monotonic()
                except Exception as caught:
                    error = error or type(caught).__name__ + ": " + str(caught)
                errors = all_errors(error) if collective else ([error] if error else [])
                if errors:
                    raise RuntimeError("Inference/I/O failed; no row is skipped: " + str(errors))
            os.fsync(stream.fileno())
            progress.update(status="complete", output_sha256=file_hash(path))
        except BaseException as caught:
            progress.update(status="failed", error_type=type(caught).__name__, error=str(caught))
            raise
        finally:
            progress["pending_rows"] = progress["planned_rows"] - progress["successful_rows"] - progress["failed_rows"]
            write_json(directory / f"progress-{rank}.json", progress)
    return progress


def grouped_metrics(records):
    groups = {field: defaultdict(list) for field in ("source", "kind", "question_id")}
    for row in records:
        for field in groups:
            key = row["source"] + "/" + row[field] if field == "question_id" else row[field]
            groups[field][key].append(row)
    return {**summarize(records), **{"by_" + field: {key: summarize(values) for key, values in sorted(mapping.items())}
                                   for field, mapping in groups.items()}}


def merge_results(items, subsets, identity, directory):
    directory = Path(directory)
    records = {}
    for rank in range(4):
        assigned = assignments(items, rank)
        values = read_prefix(directory / f"shard-{rank}.jsonl", assigned, rank, identity)
        require(len(values) == len(assigned), "Full evaluation is incomplete; no scores are produced")
        for row in values:
            key = row["split"], row["index"]
            require(key not in records, "Duplicate merged row")
            records[key] = row
    require(len(records) == len(items), "Missing or extra full-panel rows")
    metrics, old_metrics = {}, {}
    for split, count in identity["data"]["counts"].items():
        ordered = [records[(split, index)] for index in range(count)]
        temporary = directory / ("merged-" + split + ".jsonl.tmp")
        with temporary.open("w") as stream:
            for row in ordered:
                stream.write(canonical(row) + "\n")
        temporary.replace(directory / ("merged-" + split + ".jsonl"))
        metrics[split] = grouped_metrics(ordered)
        old_metrics[split] = grouped_metrics([ordered[index] for index in subsets[split]])
    report = {"status": "complete", "identity": identity, "total_rows": len(items), "splits": metrics,
              "old_release_subset": old_metrics, "temperature_fitted": False,
              "padding_included_in_denominators": False,
              "raw_sha256": {f"shard-{rank}.jsonl": file_hash(directory / f"shard-{rank}.jsonl") for rank in range(4)},
              "performance_scope": "Shared-node four-GPU throughput; not single-GPU/API latency or measured speedup"}
    write_json(directory / "summary.json", report)
    return {"status": "complete", "total_rows": len(items), "summary_sha256": file_hash(directory / "summary.json")}


def run(args):
    import torch
    import torch.distributed as dist
    from jev.model import DecisionModel
    from jev.sharded_model import shard_frozen_base, reload_replicated_checkpoint
    rank, local_rank, size = (int(os.environ.get(name, -1)) for name in ("RANK", "LOCAL_RANK", "WORLD_SIZE"))
    require(size == 4 and 0 <= rank < 4 and local_rank == rank and int(os.environ.get("LOCAL_WORLD_SIZE", -1)) == 4,
            "Use exactly four local torchrun ranks")
    require(args.backend == ("fsdp4" if args.tag == "new27b" else "replica"), "Use FSDP4 for new27b and replicas for 2B/9B")
    require(0 < args.timeout_seconds <= 3600, "Collective timeout must be positive and bounded")
    policy = load_shared_policy(args.resource_policy)
    require(validate_visible_devices(os.environ.get("CUDA_VISIBLE_DEVICES", "")) == (0, 1, 2, 3), "Pinned N1 GPUs 0–3 are required")
    controller_policy = os.environ.get("OPEN_JEV_SHARED_POLICY")
    require(controller_policy and load_shared_policy(controller_policy).sha256 == policy.sha256, "Use the shared ownership watchdog")
    items, subsets, data_identity = load_panel(args.data, args.old_data)
    checkpoint = checkpoint_identity(args.checkpoint, args.tag, args.checkpoint_sha256)
    identity = {"schema_version": 1, "checkpoint": checkpoint, "data": data_identity, "backend": args.backend,
                "world_size": 4, "row_batch_size": 1, "max_length": 4096, "prefix_cache": False,
                "partition": "concatenated_test_ood_index_mod4", "policy": policy.as_dict(),
                "implementation_sha256": implementation_identity(), "temperature_fitted": False,
                "allocator_config": os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "")}
    device = torch.device("cuda", local_rank)
    allocation = apply_allocator_budget(device, policy=policy)
    torch.cuda.set_device(device)
    dist.init_process_group("nccl", timeout=timedelta(seconds=args.timeout_seconds))
    directory = Path(args.output)
    try:
        hashes = [None] * 4
        dist.all_gather_object(hashes, object_hash(identity))
        require(len(set(hashes)) == 1, "Ranks disagree on the full evaluation identity")

        def prepare():
            if args.resume:
                require(read_json(directory / "identity.json") == identity, "Resume identity/checkpoint/data/code changed")
            else:
                directory.mkdir(parents=True, exist_ok=False)
                write_json(directory / "identity.json", identity)
        on_rank_zero(prepare)
        assigned = assignments(items, rank)
        error, prefix = None, []
        try:
            prefix = read_prefix(directory / f"shard-{rank}.jsonl", assigned, rank, identity)
        except Exception as caught:
            error = type(caught).__name__ + ": " + str(caught)
        require(not all_errors(error), "A raw prefix is invalid; existing evidence is preserved")
        counts = [None] * 4
        dist.all_gather_object(counts, len(prefix))
        start = aligned_resume_round(counts, [len(assignments(items, i)) for i in range(4)]) if args.backend == "fsdp4" else len(prefix)
        del prefix
        write_json(directory / f"allocation-{rank}.json", allocation)
        if args.backend == "fsdp4":
            model = DecisionModel(checkpoint["model"], checkpoint["revision"], device="cpu", lora_rank=8, max_length=4096)
            shard_frozen_base(model, device)
            reload_replicated_checkpoint(model, args.checkpoint)
        else:
            model = DecisionModel.load(args.checkpoint, device=str(device))
            model.max_length = 4096
        model.eval()

        def scorer(row):
            prompt = {key: row[key] for key in ("state", "question", "kind", "options")}
            with torch.no_grad():
                values = model([prompt])[0].float().cpu().tolist()
            return values, model.last_input_tokens

        if args.backend == "fsdp4":
            parity_gate(items, rank, scorer, identity, directory)
        evaluate_worker(items, rank, scorer, identity, directory, start=start)
        require(checkpoint_identity(args.checkpoint, args.tag, args.checkpoint_sha256) == checkpoint
                and implementation_identity() == identity["implementation_sha256"], "Checkpoint/code changed during evaluation")
        # Rehash all data files before final metrics, without importing or fitting a model.
        on_rank_zero(lambda: require(load_panel(args.data, args.old_data)[2] == data_identity, "Evaluation data changed"))
        result = on_rank_zero(lambda: merge_results(items, subsets, identity, directory))
        if rank == 0:
            print(json.dumps(result), flush=True)
    finally:
        dist.destroy_process_group()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("data", "old-data", "checkpoint", "resource-policy", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--tag", required=True, choices=tuple(TAGS))
    parser.add_argument("--backend", required=True, choices=("replica", "fsdp4"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
