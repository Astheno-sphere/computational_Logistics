"""Evaluate pinned final checkpoints on complete held-out dataset profiles using N1 GPUs 0–3."""

import argparse
from collections import defaultdict
from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jev.data import validate_records
from jev.metrics import evaluate_probabilities, softmax
from jev.server import strict_json

HOSTNAME = "kwade5342000001"
GPUS = (0, 1, 2, 3)
SPLITS = ("test", "ood")
MODELS = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    "27b": ("Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
}
RELEASE_V2_HASHES = {
    "train": "80a9ec19da9c4065b72f7a9e5ff8d67e62c1d1dd2572dfd296e46bfe2ea5a182",
    "calibration": "dd21b26912a6b26a09c3b00ae66a7985ee760e737b94ada4fcc6320406d4db63",
    "validation": "1dc97079d4fc034a1ba16315f801b0a4715b30c2a3874ae05aeb60dd1e40e8bb",
    "test": "fa8d62775b96c1514f238c2d8a8f8b66515dada67d490978376545296593e29b",
    "ood": "9152bff7f3d9c83cce3f1423cc6e0e6b33286b3092b3f544cb18dcc37b35a7ee",
}
EXPANSION_HASHES = {
    "train": "91a3e3c715abd735509a5a23453161475aff85626f2c47563a8fab4e7dc79239",
    "calibration": "8a366dbb71dbe57b98a25da3071fc858beb7e8567adf4abf952c3d98f79bb94c",
    "validation": "bb49a3ca608dbeb543c56a20ee2f32e75f65be835fcb40ec40014af7351c6c7d",
    "test": "662d5e79da70eba77ad740eb37576b8157e53e5c1d8cd9344c60ec56d3969637",
    "ood": "364992ae82a2d8b6f3f4ed68a0efa06d9a6b9ae469d81113d4165f762eec0a94",
}
DATASET_PROFILES = {
    "release-v2": {"models": ("2b", "9b"), "sha256": RELEASE_V2_HASHES,
                   "manifest_sha256": None, "steps": 20204, "train_rows": 80816,
                   "partition": "per_split"},
    "browser-drone-expansion-v1": {
        "models": ("27b",), "sha256": EXPANSION_HASHES,
        "manifest_sha256": "ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df",
        "steps": 27581, "train_rows": 110324, "counts": {"test": 14902, "ood": 25379},
        "seed": 20260920,
        "calibration_ids_sha256": "a1903776bafb4af05654c91ceaf3dc19a1135f82384186e7216001c76190ddad",
        "partition": "concatenated_test_ood"},
}


def dataset_profile(name):
    if name not in DATASET_PROFILES:
        raise ValueError("Unknown dataset profile")
    return DATASET_PROFILES[name]


def selected_models(name, models=None):
    allowed = dataset_profile(name)["models"]
    models = tuple(allowed if models is None else models)
    if not models or len(set(models)) != len(models) or any(tag not in allowed for tag in models):
        raise ValueError("Model selection is incompatible with the pinned dataset profile")
    return tuple(tag for tag in allowed if tag in models)


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


def read_json(path):
    return strict_json(Path(path).read_bytes())


def write_json(path, value):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def implementation_identity():
    names = ("scripts/evaluate_checkpoints_parallel.py", "jev/model.py", "jev/api.py",
             "jev/data.py", "jev/metrics.py", "jev/serving.py")
    return {name: file_hash(ROOT / name) for name in names}


def load_data(path, expected_hashes=None, *, profile_name="release-v2"):
    """Pin all five files, but select only the complete immutable test/OOD splits."""
    path = Path(path)
    profile = dataset_profile(profile_name)
    if profile_name != "release-v2" and expected_hashes is not None:
        raise ValueError("Expansion dataset hashes cannot be overridden")
    expected_hashes = profile["sha256"] if expected_hashes is None else expected_hashes
    manifest = read_json(path / "manifest.json")
    if (manifest.get("sha256") != expected_hashes or (profile["manifest_sha256"] is not None
            and file_hash(path / "manifest.json") != profile["manifest_sha256"])):
        raise ValueError(f"Dataset is not the frozen {profile_name} manifest")
    rows, calibration_ids = {}, []
    for split, digest in expected_hashes.items():
        raw = (path / f"{split}.jsonl").read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Dataset checksum mismatch: {split}")
        if split in (*SPLITS, "calibration"):
            values = [strict_json(line) for line in raw.splitlines() if line.strip()]
            if len(values) != manifest["counts"][split] or any(row["split"] != split for row in values):
                raise ValueError(f"Dataset count/split mismatch: {split}")
            if split in SPLITS:
                rows[split] = values
            else:
                calibration_ids = [row["id"] for row in values]
    if any(not rows.get(split) for split in SPLITS):
        raise ValueError("Both held-out splits must be nonempty")
    validate_records(row for split in SPLITS for row in rows[split])
    heldout_ids = [row["id"] for split in SPLITS for row in rows[split]]
    if (len(set(heldout_ids)) != len(heldout_ids) or len(set(calibration_ids)) != len(calibration_ids)
            or set(heldout_ids) & set(calibration_ids)):
        raise ValueError("Duplicate or overlapping held-out/calibration IDs")
    identity = {"dataset_profile": profile_name, "partition": profile["partition"],
                "manifest_sha256": file_hash(path / "manifest.json"), "split_sha256": expected_hashes,
                "counts": {split: len(rows[split]) for split in SPLITS},
                "total_rows": sum(len(rows[split]) for split in SPLITS),
                "ordered_ids_sha256": {split: object_hash([row["id"] for row in rows[split]]) for split in SPLITS}}
    if "counts" in profile and identity["counts"] != profile["counts"]:
        raise ValueError("Dataset does not contain the complete profile's held-out records")
    return rows, identity, set(calibration_ids)


def checkpoint_identity(path, tag, data_identity, calibration_ids, *, profile_name="release-v2"):
    profile = dataset_profile(profile_name)
    selected_models(profile_name, [tag])
    if data_identity.get("dataset_profile", "release-v2") != profile_name:
        raise ValueError("Checkpoint/data profile mismatch")
    if profile["manifest_sha256"] is not None and (
            data_identity.get("manifest_sha256") != profile["manifest_sha256"]
            or data_identity.get("split_sha256") != profile["sha256"]
            or data_identity.get("counts") != profile["counts"]
            or data_identity.get("total_rows") != sum(profile["counts"].values())
            or data_identity.get("partition") != profile["partition"]):
        raise ValueError("Checkpoint requires the frozen expansion manifest and all five split hashes")
    path = Path(path)
    config, temperature = read_json(path / "model.json"), read_json(path / "temperature.json")
    run, summary = read_json(path.parent / "run.json"), read_json(path.parent / "summary.json")
    if (config.get("model_id"), config.get("revision")) != MODELS[tag]:
        raise ValueError("Wrong checkpoint model/revision")
    if summary.get("status") != "complete" or summary.get("model") != config["model_id"]:
        raise ValueError("Checkpoint training is not complete")
    reload_error = summary.get("checkpoint_reload_max_error")
    if (run.get("model") != config["model_id"] or run.get("revision") != config["revision"]
            or run.get("steps") != profile["steps"] or summary.get("steps") != profile["steps"]
            or run.get("accumulation") != 4 or run.get("train_rows") != 0
            or run.get("max_length") != config.get("max_length") or run.get("lora_rank") != config.get("lora_rank")
            or run.get("training_sampling") != "shuffled" or summary.get("trained_rows_consumed") != profile["train_rows"]
            or type(reload_error) not in (int, float) or not math.isfinite(reload_error)
            or not 0 <= reload_error <= 0.05):
        raise ValueError(f"Checkpoint must be the completed {profile['steps']:,}-step/{profile['train_rows']:,}-row full pass with a passing reload check")
    if run.get("data_sha256") != data_identity["split_sha256"]:
        raise ValueError(f"Checkpoint was not trained with the frozen {profile_name} split hashes")
    if profile_name == "browser-drone-expansion-v1":
        distribution = run.get("distribution", {})
        if (distribution != summary.get("distribution")
                or any(type(distribution.get(key)) is not int or distribution[key] != value
                       for key, value in (("world_size", 4), ("global_batch_size", 4), ("local_rows_per_step", 1)))
                or distribution.get("backend") != "nccl" or distribution.get("device_type") != "cuda"
                or run.get("initialization") not in ("fresh_pinned_upstream", "strict_same_run_ddp_resume")
                or run.get("training_rows_consumed") != profile["train_rows"]
                or run.get("seed") != profile["seed"]
                or not isinstance(run.get("identity_sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", run["identity_sha256"]) is None
                or run.get("max_length") != 4096 or run.get("lora_rank") != 8):
            raise ValueError("Expansion checkpoint requires the completed four-rank CUDA DDP run")
    value = temperature.get("temperature")
    ids = run.get("calibration_ids", [])
    if (type(value) not in (int, float) or not math.isfinite(value) or value <= 0
            or temperature.get("split") != "calibration" or summary.get("temperature") != value
            or not ids or len(set(ids)) != len(ids) or not set(ids) <= calibration_ids
            or type(temperature.get("n")) is not int or temperature["n"] != len(ids)
            or temperature.get("ids_sha256") != hashlib.sha256(json.dumps(ids).encode()).hexdigest()):
        raise ValueError("Invalid saved calibration temperature/provenance; test fitting is forbidden")
    if profile_name == "browser-drone-expansion-v1":
        if (type(run.get("calibration_rows")) is not int or run["calibration_rows"] != 512 or len(ids) != 512
                or temperature["ids_sha256"] != profile["calibration_ids_sha256"]):
            raise ValueError("Expansion checkpoint requires its fixed 512-row calibration")
        calibration = [strict_json(line) for line in (path.parent / "calibration.jsonl").read_bytes().splitlines() if line.strip()]
        if ([row.get("id") for row in calibration] != ids
                or any(not isinstance(row.get("logits"), list) or not row["logits"]
                       or any(type(number) not in (int, float) or not math.isfinite(number) for number in row["logits"])
                       for row in calibration)):
            raise ValueError("Saved calibration predictions do not cover the fixed calibration IDs")
        training = [strict_json(line) for line in (path.parent / "training.jsonl").read_bytes().splitlines() if line.strip()]
        if ([row.get("step") for row in training] != list(range(1, profile["steps"] + 1))
                or any(row.get("world_size") != 4 or row.get("global_batch_size") != 4 for row in training)
                or any(type(row.get(key)) not in (int, float) or not math.isfinite(row[key])
                       for row in training for key in ("loss", "gradient_norm", "elapsed_seconds"))):
            raise ValueError("Expansion training log is not the complete finite four-rank full pass")
    if type(config.get("max_length")) is not int or config["max_length"] < 1:
        raise ValueError("Invalid checkpoint max_length")
    if not (path / "head.pt").is_file():
        raise ValueError("Missing final checkpoint head")
    if config.get("lora_rank"):
        if not (path / "adapter/adapter_config.json").is_file() or not any(
                (path / "adapter" / name).is_file() for name in ("adapter_model.safetensors", "adapter_model.bin")):
            raise ValueError("Missing final checkpoint adapter")
    digest = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            digest.update(str(file.relative_to(path)).encode() + b"\0")
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(1048576), b""):
                    digest.update(block)
    completion = {"steps": summary["steps"], "trained_rows_consumed": summary["trained_rows_consumed"],
                  "checkpoint_reload_max_error": reload_error, "run_sha256": file_hash(path.parent / "run.json"),
                  "summary_sha256": file_hash(path.parent / "summary.json")}
    if profile_name == "browser-drone-expansion-v1":
        completion.update(distribution=run["distribution"], run_identity_sha256=run["identity_sha256"],
                          calibration_predictions_sha256=file_hash(path.parent / "calibration.jsonl"),
                          training_log_sha256=file_hash(path.parent / "training.jsonl"))
    return {"dataset_profile": profile_name, "model": config["model_id"], "revision": config["revision"],
            "checkpoint_sha256": digest.hexdigest(), "temperature": value,
            "calibration": temperature, "max_length": config["max_length"],
            "training_completion": completion}


def shard_rows(rows, rank, *, partition="per_split"):
    if type(rank) is not int or rank not in GPUS:
        raise ValueError("Shard rank must be 0, 1, 2 or 3")
    if partition not in ("per_split", "concatenated_test_ood"):
        raise ValueError("Unknown partition rule")
    result, offset = [], 0
    for split in SPLITS:
        result.extend((split, index, row) for index, row in enumerate(rows[split]) if (index + offset) % 4 == rank)
        if partition == "concatenated_test_ood":
            offset += len(rows[split])
    return result


def shard_identity(rows, rank, *, partition="per_split"):
    assigned = shard_rows(rows, rank, partition=partition)
    return {"partition": partition, "rank": rank, "total_rows": len(assigned),
            "counts": {split: sum(item[0] == split for item in assigned) for split in SPLITS},
            "ordered_rows_sha256": object_hash([(split, index, row["id"], object_hash(row))
                                                for split, index, row in assigned])}


def row_identity(split, index, row, rank, identity):
    return {"id": row["id"], "split": split, "index": index, "shard_rank": rank,
            "source": row["source"], "group_id": row["group_id"], "kind": row["kind"],
            "target": row["target"], "row_sha256": object_hash(row), "checkpoint": identity,
            "question_id": row["metadata"].get("question_id", row["kind"])}


def evaluate_shard(rows, rank, identity, scorer, output, *, partition="per_split"):
    """One output per assigned row, including inference errors; no fabricated probabilities."""
    counts = {"rows": 0, "ok": 0, "error": 0}
    with Path(output).open("x") as stream:
        for split, index, row in shard_rows(rows, rank, partition=partition):
            result = row_identity(split, index, row, rank, identity)
            try:
                values, tokens = scorer.score([row])
                logits = values[0] if len(values) == 1 else []
                if (len(logits) != len(row["options"]) or any(type(value) not in (int, float)
                        or not math.isfinite(value) for value in logits)
                        or type(tokens) is not int or tokens < 1):
                    raise ValueError("Scorer returned invalid logits/input token count")
                result.update(status="ok", logits=logits, probabilities=softmax(logits, identity["temperature"]),
                              input_tokens=tokens)
            except Exception as error:
                result.update(status="error", error_type=type(error).__name__, error=str(error)[:1000])
            counts["rows"] += 1
            counts[result["status"]] += 1
            stream.write(canonical(result) + "\n")
            stream.flush()
    return counts


def summarize(results):
    good = [row for row in results if row["status"] == "ok"]
    successful = evaluate_probabilities([row["target"] for row in good], [row["probabilities"] for row in good]) if good else None
    hard_count = hard_correct = expected_correct = 0
    for row in results:
        target = row["target"]
        truth = [float(i == target) for i in range(len(row.get("probabilities", [])))] if isinstance(target, int) else target
        hard = isinstance(target, int) or max(truth) == 1.0
        hard_count += hard
        if row["status"] == "ok":
            prediction = max(range(len(row["probabilities"])), key=row["probabilities"].__getitem__)
            correct = float(prediction == target) if isinstance(target, int) else target[prediction]
            expected_correct += correct
            hard_correct += correct if hard else 0
    coverage = []
    for threshold in (0.5, 0.7, 0.8, 0.9, 0.95, 0.99):
        selected = sum(max(row["probabilities"]) >= threshold for row in good)
        coverage.append({"threshold": threshold, "selected": selected, "total": len(results),
                         "coverage": selected / len(results)})
    return {"count": len(results), "successful": len(good), "failed": len(results) - len(good),
            "inference_coverage": len(good) / len(results), "hard_count": hard_count,
            "accuracy_all_rows_failures_incorrect": hard_correct / hard_count if hard_count else None,
            "expected_accuracy_all_rows_failures_zero": expected_correct / len(results), "coverage": coverage,
            "probability_metrics_all_rows": successful if len(good) == len(results) else None,
            "probability_metrics_successful_rows_only": successful}


def merge_shards(rows, identity, directory, plan_sha256, gpu_uuids, *, profile_name="release-v2", data_identity=None):
    """Refuse incomplete or mixed output before writing any merged result or metric."""
    profile = dataset_profile(profile_name)
    partition = profile["partition"]
    if identity.get("dataset_profile", "release-v2") != profile_name:
        raise ValueError("Merge checkpoint/profile mismatch")
    if data_identity is not None and (
            data_identity.get("dataset_profile") != profile_name or data_identity.get("partition") != partition
            or data_identity.get("counts") != {split: len(rows[split]) for split in SPLITS}
            or data_identity.get("total_rows") != sum(len(rows[split]) for split in SPLITS)
            or data_identity.get("ordered_ids_sha256") != {
                split: object_hash([row["id"] for row in rows[split]]) for split in SPLITS}):
        raise ValueError("Merge data profile/partition/denominator mismatch")
    if profile_name != "release-v2" and (data_identity is None
            or data_identity.get("manifest_sha256") != profile["manifest_sha256"]
            or data_identity.get("split_sha256") != profile["sha256"]
            or data_identity.get("counts") != profile["counts"]):
        raise ValueError("Expansion merge requires the frozen manifest and all five split hashes")
    directory = Path(directory)
    merged, worker_reports = {}, []
    for rank in GPUS:
        path = directory / f"shard-{rank}.jsonl"
        report = read_json(directory / f"shard-{rank}.json")
        if (report.get("status") != "complete" or report.get("rank") != rank
                or report.get("checkpoint") != identity or report.get("plan_sha256") != plan_sha256
                or report.get("dataset_profile", "release-v2") != profile_name
                or (data_identity is not None and report.get("data_identity") != data_identity)
                or report.get("assignment") != shard_identity(rows, rank, partition=partition)
                or report.get("gpu_uuid") != gpu_uuids[rank] or report.get("output_sha256") != file_hash(path)):
            raise ValueError(f"Invalid shard provenance/completion: {rank}")
        actual = [strict_json(line) for line in path.read_bytes().splitlines() if line.strip()]
        expected = shard_rows(rows, rank, partition=partition)
        if len(actual) != len(expected):
            raise ValueError(f"Missing/extra shard rows: {rank}")
        for result, (split, index, row) in zip(actual, expected):
            if any(result.get(key) != value for key, value in row_identity(split, index, row, rank, identity).items()):
                raise ValueError(f"Shard row identity/order mismatch: {rank}/{row['id']}")
            key = (split, index)
            if key in merged:
                raise ValueError("Duplicate merged row")
            if result.get("status") == "ok":
                logits, probabilities = result.get("logits", []), result.get("probabilities", [])
                if (len(logits) != len(row["options"]) or len(probabilities) != len(logits)
                        or any(type(value) not in (int, float) or not math.isfinite(value) for value in logits + probabilities)
                        or type(result.get("input_tokens")) is not int or result["input_tokens"] < 1):
                    raise ValueError("Invalid raw logits/probabilities/tokens")
                expected_probabilities = softmax(logits, identity["temperature"])
                if any(abs(a - b) > 1e-12 for a, b in zip(probabilities, expected_probabilities)):
                    raise ValueError("Probabilities do not use the saved checkpoint temperature")
            elif result.get("status") != "error" or not result.get("error_type") or not result.get("error"):
                raise ValueError("Invalid row status/error record")
            elif any(key in result for key in ("logits", "probabilities")):
                raise ValueError("Failed rows must not contain invented predictions")
            merged[key] = result
        counts = {status: sum(row["status"] == status for row in actual) for status in ("ok", "error")}
        if report.get("counts") != {"rows": len(actual), **counts}:
            raise ValueError("Shard summary counts do not match raw rows")
        worker_reports.append(report)
    summaries = {}
    for split in SPLITS:
        ordered = [merged[(split, index)] for index in range(len(rows[split]))]
        with (directory / f"merged-{split}.jsonl").open("x") as stream:
            stream.writelines(canonical(row) + "\n" for row in ordered)
        groups = {key: defaultdict(list) for key in ("source", "kind", "group_id")}
        for row in ordered:
            for key in groups:
                groups[key][row[key]].append(row)
        summaries[split] = {**summarize(ordered), **{
            "by_" + key: {name: summarize(items) for name, items in sorted(group.items())}
            for key, group in groups.items()}}
    return {"status": "complete" if all(value["failed"] == 0 for value in summaries.values()) else "completed_with_errors",
            "dataset_profile": profile_name, "partition": partition, "data_identity": data_identity,
            "total_rows": len(merged), "checkpoint": identity, "splits": summaries, "workers": worker_reports,
            "performance_scope": "Four concurrent independent model replicas; throughput timing is not comparable to single-GPU latency."}


def enforce_host_policy(policy_path, hostname=None):
    hostname = socket.gethostname() if hostname is None else hostname
    machine = hostname.rstrip(".").split(".")[0].lower()
    policy = read_json(policy_path)
    if (machine != HOSTNAME or policy.get("expected_hostname") != HOSTNAME
            or policy.get("parallel_data_evaluation_gpu_indices") != list(GPUS)
            or not set(GPUS) <= set(policy.get("allowed_gpu_indices", []))
            or machine in policy.get("prohibited_nodes", [])):
        raise RuntimeError("Parallel data evaluation requires N1-1 and its explicit GPU 0–3 phase policy")
    return {"hostname": machine, "policy_sha256": file_hash(policy_path), "gpu_indices": list(GPUS)}


def require_free_gpus():
    occupied = {line.strip() for line in subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid", "--format=csv,noheader"], text=True).splitlines() if line.strip()}
    inventory = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid,memory.used,utilization.gpu",
                                         "--format=csv,noheader,nounits"], text=True)
    selected = {}
    for line in inventory.splitlines():
        index, uuid, memory, utilization = [part.strip() for part in line.split(",")]
        if int(index) in GPUS:
            if int(index) in selected or uuid in occupied or int(memory) >= 512 or int(utilization) >= 10:
                raise RuntimeError("All four requested GPUs must be free; no process launched")
            selected[int(index)] = uuid
    if set(selected) != set(GPUS) or len(set(selected.values())) != 4:
        raise RuntimeError("Incomplete/duplicate four-GPU inventory")
    return [selected[index] for index in GPUS]


@contextmanager
def gpu_lease(lock_root=Path("/tmp")):
    names = ["open-jev-n1-gpu-0-3.lock", *[f"open-jev-eval-gpu-{index}.lock" for index in GPUS]]
    with ExitStack() as stack:
        for name in names:
            stream = stack.enter_context((Path(lock_root) / name).open("a+"))
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(f"GPU scheduling lease already held: {name}") from error
        yield


def stop_owned_children(processes):
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=20)


def wait_free_gpus(expected, timeout=30):
    """Allow driver cleanup after our children exit; never stop an unrelated process."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            if require_free_gpus() == expected:
                return
        except RuntimeError:
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("Four GPUs were not free after child cleanup")
        time.sleep(1)


def worker(plan_path, rank):
    plan = read_json(plan_path)
    profile_name = plan.get("dataset_profile", "release-v2")
    profile = dataset_profile(profile_name)
    selected_models(profile_name, [plan["tag"]])
    policy = enforce_host_policy(plan["policy_path"])
    if (rank not in GPUS or os.environ.get("CUDA_VISIBLE_DEVICES") != plan["gpu_uuids"][rank]
            or implementation_identity() != plan["implementation_sha256"] or policy != plan["policy"]
            or os.getppid() != plan["controller_pid"]):
        raise ValueError("Worker GPU/code identity mismatch")
    rows, data_identity, calibration_ids = load_data(plan["data"], profile_name=profile_name)
    identity = checkpoint_identity(plan["checkpoint_path"], plan["tag"], data_identity, calibration_ids, profile_name=profile_name)
    if data_identity != plan["data_identity"] or identity != plan["checkpoint"]:
        raise ValueError("Worker checkpoint/data identity mismatch")
    assignment = shard_identity(rows, rank, partition=profile["partition"])
    if plan["partition"] != profile["partition"] or plan["assignments"][str(rank)] != assignment:
        raise ValueError("Worker profile/assignment mismatch")
    from jev.model import DecisionModel
    from jev.serving import TorchScorer
    import torch
    started = time.perf_counter()
    model = DecisionModel.load(plan["checkpoint_path"], device="cuda:0")
    loaded = time.perf_counter()
    path = Path(plan_path).parent / f"shard-{rank}.jsonl"
    counts = evaluate_shard(rows, rank, identity, TorchScorer(model), path, partition=profile["partition"])
    torch.cuda.synchronize()
    finished = time.perf_counter()
    if (checkpoint_identity(plan["checkpoint_path"], plan["tag"], data_identity, calibration_ids, profile_name=profile_name) != identity
            or implementation_identity() != plan["implementation_sha256"]):
        raise ValueError("Checkpoint/code changed during evaluation")
    write_json(path.with_suffix(".json"), {"status": "complete", "rank": rank, "checkpoint": identity,
               "dataset_profile": profile_name, "data_identity": data_identity,
               "gpu_uuid": plan["gpu_uuids"][rank], "plan_sha256": file_hash(plan_path),
               "assignment": assignment,
               "output_sha256": file_hash(path), "counts": counts,
               "model_load_seconds": loaded - started, "shard_inference_seconds": finished - loaded,
               "peak_memory_gib": torch.cuda.max_memory_allocated() / 2**30})


def run(args):
    profile_name = getattr(args, "dataset_profile", "release-v2")
    profile = dataset_profile(profile_name)
    models = selected_models(profile_name, getattr(args, "models", None))
    policy_path = ROOT / "state/auto_research/resource_policy.json"
    policy = enforce_host_policy(policy_path)
    rows, data_identity, calibration_ids = load_data(args.data, profile_name=profile_name)
    checkpoints = {tag: Path(getattr(args, "checkpoint_" + tag, None) or args.checkpoint_root / tag / "checkpoint").resolve()
                   for tag in models}
    identities = {tag: checkpoint_identity(path, tag, data_identity, calibration_ids, profile_name=profile_name) for tag, path in checkpoints.items()}
    implementation = implementation_identity()
    with gpu_lease():
        gpu_uuids = require_free_gpus()
        args.output_root.mkdir(parents=True, exist_ok=False)
        manifest = {"status": "running", "phase": "parallel_data_eval", "policy": policy,
                    "dataset_profile": profile_name, "partition": profile["partition"],
                    "data_identity": data_identity, "gpu_uuids": gpu_uuids, "models": {},
                    "implementation_sha256": implementation, "model_order": list(models)}
        manifest_path = args.output_root / "manifest.json"
        write_json(manifest_path, manifest)
        try:
            for tag in models:
                wait_free_gpus(gpu_uuids)
                directory = args.output_root / tag
                directory.mkdir()
                plan = {"tag": tag, "dataset_profile": profile_name,
                        "data": str(args.data.resolve()), "data_identity": data_identity,
                        "checkpoint_path": str(checkpoints[tag]), "checkpoint": identities[tag],
                        "gpu_uuids": gpu_uuids, "implementation_sha256": implementation,
                        "policy_path": str(policy_path), "policy": policy, "controller_pid": os.getpid(),
                        "assignments": {str(rank): shard_identity(rows, rank, partition=profile["partition"]) for rank in GPUS},
                        "partition": profile["partition"]}
                plan_path = directory / "plan.json"
                write_json(plan_path, plan)
                processes, started = [], time.perf_counter()
                manifest["current_model"] = tag
                manifest["models"][tag] = {"status": "running", "children": []}
                write_json(manifest_path, manifest)
                try:
                    for rank in GPUS:
                        command = [sys.executable, "-u", str(Path(__file__).resolve()), "--worker-plan", str(plan_path.resolve()),
                                   "--worker-rank", str(rank)]
                        env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu_uuids[rank], TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
                        with (directory / f"shard-{rank}.log").open("x") as log:
                            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                                       stderr=subprocess.STDOUT, start_new_session=False)
                        processes.append(process)
                        manifest["models"][tag]["children"].append({"pid": process.pid, "rank": rank, "gpu_uuid": gpu_uuids[rank]})
                        write_json(manifest_path, manifest)
                    while any(process.poll() is None for process in processes):
                        if any(process.poll() not in (None, 0) for process in processes):
                            raise RuntimeError("An evaluation worker failed; inspect retained shard logs")
                        time.sleep(1)
                    exits = [process.wait() for process in processes]
                    if any(exits):
                        raise RuntimeError(f"Evaluation worker exit codes: {exits}")
                finally:
                    stop_owned_children(processes)
                    manifest["models"][tag]["exit_codes"] = [process.returncode for process in processes]
                    write_json(manifest_path, manifest)
                summary = merge_shards(rows, identities[tag], directory, file_hash(plan_path), gpu_uuids,
                                       profile_name=profile_name, data_identity=data_identity)
                summary["four_gpu_wall_seconds_including_load"] = time.perf_counter() - started
                summary["data_identity"] = data_identity
                write_json(directory / "summary.json", summary)
                manifest["models"][tag]["status"] = summary["status"]
                write_json(manifest_path, manifest)
                if summary["status"] != "complete":
                    raise RuntimeError("Inference failures retained in full-denominator summary; evaluation did not fully succeed")
            if load_data(args.data, profile_name=profile_name)[1] != data_identity or implementation_identity() != implementation:
                raise ValueError("Dataset/code changed during evaluation")
            wait_free_gpus(gpu_uuids)
            manifest["gpus_free_after_cleanup"] = True
            manifest["status"] = "complete"
        except BaseException as error:
            manifest.update(status="failed", error_type=type(error).__name__, error=str(error))
            current = manifest["models"].get(manifest.get("current_model"))
            if current and current["status"] == "running":
                current["status"] = "failed"
            try:
                manifest["gpus_free_after_cleanup"] = require_free_gpus() == gpu_uuids
            except Exception:
                manifest["gpus_free_after_cleanup"] = False
            raise
        finally:
            write_json(manifest_path, manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-profile", choices=DATASET_PROFILES, default="release-v2")
    parser.add_argument("--models", choices=MODELS, nargs="+")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--checkpoint-root", type=Path)
    parser.add_argument("--checkpoint-2b", type=Path)
    parser.add_argument("--checkpoint-9b", type=Path)
    parser.add_argument("--checkpoint-27b", type=Path)
    parser.add_argument("--worker-plan", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-rank", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_plan is not None:
        if args.worker_rank not in GPUS:
            parser.error("worker rank required")
        worker(args.worker_plan, args.worker_rank)
    else:
        try:
            models = selected_models(args.dataset_profile, args.models)
        except ValueError as error:
            parser.error(str(error))
        args.data = args.data or ROOT / "data" / args.dataset_profile
        if not args.output_root or (args.checkpoint_root is None and any(getattr(args, "checkpoint_" + tag) is None for tag in models)):
            parser.error("--output-root and either --checkpoint-root or paths for every selected checkpoint are required")
        previous = {signum: signal.signal(signum, handle_signal) for signum in (signal.SIGTERM, signal.SIGINT)}
        try:
            print(json.dumps(run(args), indent=2))
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


def handle_signal(signum, frame):
    raise InterruptedError(f"Evaluation controller received signal {signum}")


if __name__ == "__main__":
    main()
