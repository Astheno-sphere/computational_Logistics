"""CPU-only audit of a frozen, already-copied early DDP log prefix.

No project imports, model/tensor loading, remote commands, snapshot access or
JF100 reads. Row coverage reconstructs the schedule; it does not replay gradients.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess


ROOT = Path(__file__).resolve().parents[2]
COMMIT = "99c5361d83edd5f9dbd11cb3f4bd9f9c54b5973e"
MANIFEST_SHA = "ba001b88787ce21576017897a0cbdedd5917ceb29ad3522b0e1fb7b4836d49df"
HASHES = {
    "train": "91a3e3c715abd735509a5a23453161475aff85626f2c47563a8fab4e7dc79239",
    "calibration": "8a366dbb71dbe57b98a25da3071fc858beb7e8567adf4abf952c3d98f79bb94c",
    "validation": "bb49a3ca608dbeb543c56a20ee2f32e75f65be835fcb40ec40014af7351c6c7d",
    "test": "662d5e79da70eba77ad740eb37576b8157e53e5c1d8cd9344c60ec56d3969637",
    "ood": "364992ae82a2d8b6f3f4ed68a0efa06d9a6b9ae469d81113d4165f762eec0a94",
}
SOURCE_FILES = ("jev/train_distributed.py", "jev/train.py", "jev/model.py", "jev/api.py", "jev/data.py", "jev/metrics.py")


def require(value, message):
    if not value:
        raise ValueError(message)


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    def nonfinite(value):
        raise ValueError("nonfinite JSON: "+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def read(path):
    return decode(Path(path).read_bytes())


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def counts(rows, field):
    return dict(sorted(Counter(row[field] for row in rows).items()))


def window_statistics(logs, width, total_steps, checkpoint_every):
    completed = len(logs)
    start = completed-width
    require(0 <= start < completed, "invalid complete-step window")
    first_time = logs[start-1]["elapsed_seconds"] if start else 0.0
    last_time = logs[-1]["elapsed_seconds"]
    chosen = logs[start:]
    intervals = [row["elapsed_seconds"]-(logs[index-1]["elapsed_seconds"] if index else 0)
                 for index, row in enumerate(logs) if index >= start]
    duration = last_time-first_time
    require(len(chosen) == len(intervals) == width and duration > 0, "window endpoint/count mismatch")
    saves = [step for step in range(checkpoint_every, completed, checkpoint_every) if start <= step < completed]
    mean = duration/width
    return {"first_completed_step_in_window": start+1, "last_completed_step_in_window": completed,
        "completed_steps": width, "scheduled_rows": 4*width,
        "elapsed_start_endpoint_step": start, "elapsed_start_seconds": first_time, "elapsed_end_seconds": last_time,
        "window_elapsed_seconds": duration, "mean_seconds_per_optimizer_step": mean,
        "optimizer_steps_per_second": width/duration, "scheduled_rows_per_second": 4*width/duration,
        "median_step_interval_seconds": statistics.median(intervals), "minimum_step_interval_seconds": min(intervals),
        "maximum_step_interval_seconds": max(intervals),
        "mean_loss": statistics.fmean(row["loss"] for row in chosen),
        "mean_gradient_norm_before_clipping": statistics.fmean(row["gradient_norm"] for row in chosen),
        "maximum_logged_peak_memory_gib": max(row["peak_memory_gib"] for row in chosen),
        "checkpoint_saves_whose_following_interval_is_in_window": saves,
        "remaining_optimizer_steps": total_steps-completed,
        "training_loop_remaining_seconds_at_observed_mean": (total_steps-completed)*mean,
        "training_loop_remaining_hours_at_observed_mean": (total_steps-completed)*mean/3600}


def audit(args):
    capture, run = read(args.evidence/"capture.json"), read(args.evidence/"run.json")
    require(capture["hostname"] == "kwade5342000001" and capture["source_commit"] == COMMIT, "capture source")
    require(capture["prefix_rechecked_unchanged"] is True and capture["run_rechecked_unchanged"] is True, "unstable capture")
    require(sha(args.evidence/"run.json") == capture["run_sha256"], "run copy bytes")
    log_path = args.evidence/"training-prefix.jsonl"
    require(sha(log_path) == capture["prefix_sha256"] and log_path.stat().st_size == capture["prefix_bytes"], "log copy bytes")
    logs = [decode(line) for line in log_path.read_bytes().splitlines() if line.strip()]
    completed = len(logs)
    require(completed >= 500 and completed == capture["complete_rows"] == capture["last_complete_step"], "insufficient/inconsistent prefix")
    require([row["step"] for row in logs] == list(range(1, completed+1)), "noncontiguous completed steps")
    for row in logs:
        require(type(row["step"]) is int, "step is not an integer")
        require(all(type(row[key]) is int and row[key] == 4 for key in ("world_size", "global_batch_size")), "log DDP topology")
        require(all(type(row[key]) in (int, float) and math.isfinite(row[key]) and row[key] >= 0
                    for key in ("loss", "gradient_norm", "elapsed_seconds", "peak_memory_gib")), "invalid numeric log field")
    require(all(b["elapsed_seconds"] > a["elapsed_seconds"] for a, b in zip(logs, logs[1:])), "nonincreasing elapsed time")
    fixed = {"model": "Qwen/Qwen3.8-27B", "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
             "commit": COMMIT, "steps": 27581, "train_rows": 0, "seed": 20260920,
             "training_sampling": "shuffled", "accumulation": 4, "max_length": 4096,
             "lora_rank": 8, "checkpoint_every": 500, "initialization": "fresh_pinned_upstream", "resume_step": 0,
             "resume_training": None, "training_rows_consumed": 110324}
    require(all(run.get(key) == value for key, value in fixed.items()), "run differs from fresh pinned full-pass plan")
    topology = run["distribution"]
    require(all(topology.get(key) == value for key, value in {
        "world_size": 4, "global_batch_size": 4, "local_rows_per_step": 1,
        "backend": "nccl", "device_type": "cuda", "row_order": "train[(completed_steps * 4 + rank) % len(train)]"}.items()), "run topology/order")
    source = {name: hashlib.sha256(subprocess.check_output(["git", "-C", str(ROOT), "show", COMMIT+":"+name])).hexdigest() for name in SOURCE_FILES}
    require(source == capture["source_files_sha256"] and topology["implementation_sha256"] == source["jev/train_distributed.py"], "source bytes mismatch")
    manifest = read(args.data/"manifest.json")
    require(sha(args.data/"manifest.json") == capture["data_files_sha256"]["manifest.json"] == MANIFEST_SHA, "frozen manifest bytes")
    require(manifest["sha256"] == run["data_sha256"] == HASHES, "five recorded split hashes")
    require(sha(args.data/"train.jsonl") == capture["data_files_sha256"]["train.jsonl"] == HASHES["train"], "actual train bytes")
    data = []
    with (args.data/"train.jsonl").open("rb") as stream:
        for line in stream:
            if line.strip():
                value = decode(line)
                require(value["split"] == "train", "non-training record in training input")
                data.append({key: value[key] for key in ("id", "source", "kind", "group_id")})
    require(len(data) == manifest["counts"]["train"] == 110324 and len({row["id"] for row in data}) == len(data), "frozen train count/ID uniqueness")
    original_ids_sha = object_sha([row["id"] for row in data])
    random.Random(run["seed"]).shuffle(data)
    shuffled_ids = [row["id"] for row in data]
    shuffle_sha = object_sha(shuffled_ids)
    require("train_ids" not in run, "unexpected run train_ids field; review its semantics")
    proof = None
    if args.shuffle_proof:
        proof = read(args.shuffle_proof)
        require(proof["train_ids_count"] == 110324 and proof["train_ids_sha256"] == shuffle_sha, "independent snapshot-selected ID hash mismatch")
        require(proof["run_identity_sha256"] == run["identity_sha256"], "independent snapshot run identity mismatch")
    consumed = 4*completed
    require(consumed <= len(data), "prefix crosses the planned single pass")
    prefix = data[:consumed]
    by_source_kind = Counter((row["source"], row["kind"]) for row in prefix)
    rank_rows = [data[rank:consumed:4] for rank in range(4)]
    require(all(len(rows) == completed for rows in rank_rows), "rank row count")
    require(len({row["id"] for rows in rank_rows for row in rows}) == consumed, "duplicate rank-scheduled ID")
    scheduled = [{"completed_step": index//4+1, "rank": index%4, "shuffled_train_index": index, **row}
                 for index, row in enumerate(prefix)]
    schedule_path = args.evidence/"reconstructed-scheduled-prefix.jsonl"
    with schedule_path.open("x") as stream:
        stream.writelines(json.dumps(row, sort_keys=True)+"\n" for row in scheduled)
    windows = {"all_completed": window_statistics(logs, completed, run["steps"], run["checkpoint_every"]),
               "last_100": window_statistics(logs, 100, run["steps"], run["checkpoint_every"]),
               "last_500": window_statistics(logs, 500, run["steps"], run["checkpoint_every"])}
    checkpoint_intervals = [{"save_after_step": step, "next_logged_step": step+1,
        "following_interval_seconds": logs[step]["elapsed_seconds"]-logs[step-1]["elapsed_seconds"]}
        for step in range(run["checkpoint_every"], completed, run["checkpoint_every"])]
    return {"schema_version": 1, "status": "passed", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "observation_captured_at_utc": capture["captured_at_utc"], "raw_evidence_directory": str(args.evidence),
        "scope": {"cpu_only": True, "model_loaded": False, "gpu_access": False, "remote_mutation": False,
                  "snapshot_access_by_this_audit": False, "jf100_access": False, "gradient_replay": False},
        "run": {**fixed, "identity_sha256": run["identity_sha256"], "distribution": topology,
                "training_rows_consumed_field_is_planned_total": True, "is_complete": False},
        "log_prefix": {"first_completed_step": 1, "last_completed_step": completed,
                       "contiguous": True, "finite_nonnegative_fields": True,
                       "strictly_increasing_elapsed_seconds": True, "world_size": 4, "global_batch_size": 4,
                       "latest_record": logs[-1], "completed_step_fraction": completed/run["steps"]},
        "data": {"manifest_sha256": MANIFEST_SHA, "recorded_five_split_sha256": HASHES,
            "actual_file_hashes_checked_here": ["manifest.json", "train.jsonl"], "train_rows": len(data),
            "original_ordered_ids_sha256": original_ids_sha, "shuffled_ordered_ids_sha256": shuffle_sha,
            "shuffle": "random.Random(20260920).shuffle once, balanced=False, limit=0",
            "train_ids_present_in_run_json": False, "independent_snapshot_digest_crosscheck": proof,
            "full_train_by_source": counts(data, "source"), "full_train_by_kind": counts(data, "kind")},
        "early_coverage": {"basis": "Source-code and frozen-input schedule corresponding to continuous completed-step logs; row IDs were not logged by each rank.",
            "scheduled_rows_for_completed_steps": consumed, "unique_ids": consumed, "fraction_of_frozen_train_rows": consumed/len(data),
            "rank_row_rule": "For completed step s and rank r: shuffled_train[(4*(s-1)+r)%110324]",
            "rank_rows": [len(rows) for rows in rank_rows], "by_source": counts(prefix, "source"), "by_kind": counts(prefix, "kind"),
            "by_source_kind": [{"source": source, "kind": kind, "rows": count} for (source, kind), count in sorted(by_source_kind.items())],
            "by_rank": [{"rank": rank, "rows": len(rows), "ordered_ids_sha256": object_sha([row["id"] for row in rows]),
                         "by_source": counts(rows, "source"), "by_kind": counts(rows, "kind")} for rank, rows in enumerate(rank_rows)],
            "ordered_prefix_ids_sha256": object_sha(shuffled_ids[:consumed]), "reconstructed_schedule_sha256": sha(schedule_path)},
        "observed_rate_windows": windows, "checkpoint_following_intervals": checkpoint_intervals,
        "timing_interpretation": {"clock_origin": "After model loading, baseline evaluation and fresh RNG setup; immediately before the training loop.",
            "logged_time_boundary": "After optimizer update and peak all-reduce invocation; before this step's log write/print and snapshot save.",
            "save_cost": "A save after step k is included in elapsed[k+1]-elapsed[k]. Following intervals also include training and other overhead; save duration is not separately measured.",
            "eta_scope": "Remaining optimizer-loop steps at each observed mean. Includes only the historical save/loop overhead represented by that window; excludes final snapshot save, calibration, held-out evaluation, reload and future downtime.",
            "forecast_is_commitment": False},
        "evidence_sha256": {"audit_script": sha(Path(__file__)), "capture": sha(args.evidence/"capture.json"),
            "run": sha(args.evidence/"run.json"), "training_prefix": sha(log_path), "source_files": source,
            "shuffle_proof": sha(args.shuffle_proof) if args.shuffle_proof else None},
        "limitations": ["This is not an independent replay of gradients or optimizer updates; continuous saved logs and the pinned schedule support the coverage reconstruction.",
            "A source/kind is counted when its row is scheduled; this does not measure task quality or generalization.",
            "Early windows cover only a small portion of the shuffled mixture; input-length/candidate variation and future saves can change throughput."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--data", type=Path, default=ROOT/"data/browser-drone-expansion-v1")
    parser.add_argument("--shuffle-proof", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT/"reports/runtime-checks/27b-ddp-early-training.json")
    args = parser.parse_args()
    require(not args.output.exists(), "Do not overwrite an existing audit")
    result = audit(args)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"status": result["status"], "completed_steps": result["log_prefix"]["last_completed_step"],
                      "scheduled_rows": result["early_coverage"]["scheduled_rows_for_completed_steps"],
                      "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
