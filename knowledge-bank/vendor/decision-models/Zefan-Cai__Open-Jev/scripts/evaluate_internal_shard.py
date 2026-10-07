"""Evaluate one frozen four-rank assignment from an internal migration campaign.

All ranks score complete candidate rows with the existing FSDP4 implementation.
Probe receipts and append-only raw shards are evidence for the separate campaign
audit; this worker never imports old predictions or produces aggregate scores.
"""
import argparse
from datetime import timedelta
import os
from pathlib import Path
import time

from jev.eval_resources import apply_allocator_budget, load_eval_policy, validate_visible_devices
from jev.metrics import softmax
from jev.shared_resources import require
from scripts import internal_eval_campaign as campaign

canonical, file_hash, object_hash, write_json = campaign.canonical, campaign.file_hash, campaign.object_hash, campaign.write_json


def read_json(path):
    return campaign.strict_json(Path(path).read_bytes())


def assignments(items, manifest, group_id, rank):
    """Preserve full-panel offsets even when old completed rows are excluded."""
    indices = campaign.rank_indices(manifest, group_id, rank)
    require(all(type(index) is int and 0 <= index < len(items) for index in indices), "Assignment index outside full panel")
    return [(round_index, global_index, *items[global_index]) for round_index, global_index in enumerate(indices)]


def evaluation_identity(manifest, campaign_sha256, group_id):
    group = campaign.get_group(manifest, group_id)
    return {"schema_version": 1, "checkpoint": manifest["checkpoint"], "data": manifest["data"],
            "backend": "fsdp4", "world_size": 4, "row_batch_size": 1, "max_length": 4096,
            "prefix_cache": False, "temperature_fitted": False,
            "partition": "remaining_global_indices[ordinal::group_count][rank::4]",
            "campaign_sha256": campaign_sha256, "campaign_group_id": group_id,
            "group_ordinal": group["ordinal"], "group_count": manifest["group_count"], "policy": group["policy"],
            "implementation_sha256": manifest["implementation_sha256"],
            "allocator_config": os.environ.get("PYTORCH_CUDA_ALLOC_CONF", "")}


def row_identity(assigned, rank, identity):
    from scripts.evaluate_internal_full import row_identity as old_row_identity
    round_index, global_index, split, index, row = assigned
    return {**old_row_identity((round_index, split, index, row), rank, identity), "global_index": global_index,
            **{key: identity[key] for key in ("campaign_sha256", "campaign_group_id", "group_ordinal")}}


def validate_result(result, assigned, rank, identity):
    from scripts.evaluate_internal_full import validate_result as validate_old_result
    round_index, _, split, index, row = assigned
    require(all(result.get(key) == value for key, value in row_identity(assigned, rank, identity).items()),
            "Raw campaign assignment/identity differs")
    validate_old_result(result, (round_index, split, index, row), rank, identity)


def read_prefix(path, assigned, rank, identity):
    import json
    result = []
    if Path(path).exists():
        with Path(path).open("rb") as stream:
            for line in stream:
                require(line.endswith(b"\n") and line.strip(), "Partial or blank raw line; preserve evidence for recovery")
                require(len(result) < len(assigned), "Extra raw campaign rows")
                row = json.loads(line)
                validate_result(row, assigned[len(result)], rank, identity)
                result.append(row)
    return result


def checked_memory(reader):
    memory = reader()
    require(isinstance(memory, dict) and memory.get("backend") in {"cuda", "cpu"}, "Memory backend is required")
    fields = ("allocated_bytes", "reserved_bytes", "max_allocated_bytes", "max_reserved_bytes")
    require(all(type(memory.get(key)) is int and memory[key] >= 0 for key in fields), "Invalid memory telemetry")
    require(memory["max_allocated_bytes"] >= memory["allocated_bytes"]
            and memory["max_reserved_bytes"] >= memory["reserved_bytes"], "Memory peak is below current usage")
    return memory


def cuda_memory(device):
    import torch
    return {"backend": "cuda", "allocated_bytes": torch.cuda.memory_allocated(device),
            "reserved_bytes": torch.cuda.memory_reserved(device),
            "max_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "max_reserved_bytes": torch.cuda.max_memory_reserved(device)}


def probe_gate(items, rank, scorer, manifest, group_id, fixtures, directory, memory_reader, *, name="probe.json"):
    """Record every deterministic fixture under mixed-row and same-row forwards."""
    import torch.distributed as dist
    from jev.train_distributed import on_rank_zero
    from scripts.evaluate_internal_full import all_errors, checked_score
    rows = fixtures["rows"]
    require(rows and len({row["global_index"] for row in rows}) == len(rows), "Nonempty unique probe rows required")
    for fixture in rows:
        index = fixture["global_index"]
        require(type(index) is int and 0 <= index < len(items)
                and fixture["row_sha256"] == object_hash(items[index][-1]), "Probe fixture row changed")
    own = {index: {"global_index": fixture["global_index"], "row_sha256": fixture["row_sha256"], "rank": rank}
           for index, fixture in enumerate(rows) if index % 4 == rank}
    report = {"status": "pending", "probe_contract_sha256": campaign.probe_contract(manifest, group_id),
              "campaign_group_id": group_id, "fixtures_sha256": manifest["probe_fixtures"]["sha256"],
              "scope": "Deterministic byte-shape fixtures, not a maximum token-length guarantee or latency benchmark"}

    def persist(errors=None):
        gathered, memories = [None] * 4, [None] * 4
        dist.all_gather_object(gathered, list(own.values()))
        memory_error, memory = None, None
        try:
            memory = checked_memory(memory_reader)
        except Exception as caught:
            memory_error = type(caught).__name__ + ": " + str(caught)
        errors = list(errors or []) + all_errors(memory_error)
        dist.all_gather_object(memories, memory)
        order = {fixture["global_index"]: i for i, fixture in enumerate(rows)}
        report.update(rows=sorted([row for values in gathered for row in values], key=lambda row: order[row["global_index"]]),
                      memory={"by_rank": memories})
        if errors:
            report.update(status="failed", errors=errors)
        else:
            try:
                report["validation"] = campaign.validate_probe(report, manifest, fixtures, group_id)
                report["status"] = "passed"
            except Exception as caught:
                report.update(status="failed", errors=[type(caught).__name__ + ": " + str(caught)])
        on_rank_zero(lambda: write_json(Path(directory) / name, report))

    def score(index, phase, store):
        error = None
        try:
            started = time.perf_counter()
            logits, tokens = checked_score(scorer, items[rows[index]["global_index"]][-1])
            value = {"logits": logits, "input_tokens": tokens, "wall_seconds": time.perf_counter() - started,
                     "memory": checked_memory(memory_reader)}
            if store:
                own[index][phase] = value
        except Exception as caught:
            error = type(caught).__name__ + ": " + str(caught)
            if store:
                own[index][phase] = {"status": "error", "error": error}
        errors = all_errors(error)
        if errors:
            persist(errors)
            raise RuntimeError("Deterministic probe failed; no full rows started: " + str(errors))

    for offset in range(0, len(rows), 4):
        index = offset + rank
        score(index if index < len(rows) else 0, "different_row", index < len(rows))
    for index in range(len(rows)):
        score(index, "same_row", index % 4 == rank)
    persist()
    require(report["status"] == "passed", "Deterministic probe parity/reference gate failed; no full rows started")
    return report


def evaluate_worker(items, manifest, group_id, rank, scorer, identity, directory, *, start=0, collective=True):
    from scripts.evaluate_internal_full import all_errors, checked_score
    assigned = assignments(items, manifest, group_id, rank)
    rounds = (len(campaign.group_indices(manifest, group_id)) + 3) // 4
    require(type(start) is int and 0 <= start <= rounds, "Invalid resume round")
    directory = Path(directory)
    path = directory / f"shard-{rank}.jsonl"
    progress = {"status": "running", "rank": rank, "campaign_group_id": group_id,
                "planned_rows": len(assigned), "successful_rows": min(start, len(assigned)), "failed_rows": 0,
                "padding_forwards": 0, "eval_identity_sha256": object_hash(identity), "resumed_at_round": start}
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


def verify_inputs(manifest, group):
    from scripts.evaluate_internal_full import checkpoint_identity, load_panel
    paths = group["paths"]
    items, _, data = load_panel(paths["data"], paths["old_data"])
    checkpoint = checkpoint_identity(paths["checkpoint"], "new27b", manifest["checkpoint"]["checkpoint_sha256"])
    require(checkpoint == manifest["checkpoint"] and data == manifest["data"], "Campaign checkpoint/data identity differs")
    require(campaign.implementation_identity() == manifest["implementation_sha256"], "Campaign code identity differs")
    return items


def run(args):
    import torch
    import torch.distributed as dist
    rank, local_rank, size = (int(os.environ.get(name, -1)) for name in ("RANK", "LOCAL_RANK", "WORLD_SIZE"))
    require(size == 4 and 0 <= rank < 4 and rank == local_rank and int(os.environ.get("LOCAL_WORLD_SIZE", -1)) == 4,
            "Use exactly four local torchrun ranks")
    require(0 < args.timeout_seconds <= 3600, "Collective timeout must be positive and bounded")
    manifest, digest = campaign.read_campaign(args.campaign, args.campaign_sha256)
    group = campaign.get_group(manifest, args.group_id)
    policy = load_eval_policy(group["paths"]["resource_policy"])
    require(policy.as_dict() == group["policy"] and policy.sha256 == group["policy_sha256"], "Campaign resource policy changed")
    validate_visible_devices(os.environ.get("CUDA_VISIBLE_DEVICES", ""), policy)
    controller = os.environ.get("OPEN_JEV_EVAL_POLICY")
    require(controller and load_eval_policy(controller).sha256 == policy.sha256, "Use the evaluation ownership watchdog")
    fixtures = campaign.load_probe_fixtures(args.campaign, manifest)
    identity = evaluation_identity(manifest, digest, args.group_id)
    device = torch.device("cuda", local_rank)
    allocation = apply_allocator_budget(device, policy=policy)
    torch.cuda.set_device(device)
    # Some installed Transformers/PEFT versions initialize CUDA during import.
    # Apply the allocator cap before importing those or their evaluator helpers.
    from jev.model import DecisionModel
    from jev.sharded_model import reload_replicated_checkpoint, shard_frozen_base
    from jev.train_distributed import on_rank_zero
    from scripts.evaluate_internal_full import aligned_resume_round, all_errors
    items = verify_inputs(manifest, group)
    dist.init_process_group("nccl", timeout=timedelta(seconds=args.timeout_seconds))
    directory = Path(args.output)
    try:
        hashes = [None] * 4
        dist.all_gather_object(hashes, object_hash(identity))
        require(len(set(hashes)) == 1, "Ranks disagree on campaign evaluation identity")

        def prepare():
            if args.resume:
                require(not args.probe_only, "Probe-only launches require a fresh output directory")
                require(read_json(directory / "identity.json") == identity, "Resume campaign/checkpoint/data/code changed")
            else:
                directory.mkdir(parents=True, exist_ok=False)
                write_json(directory / "identity.json", identity)
            name = "probe.json"
            if args.resume:
                attempt = 1
                while (directory / f"probe-resume-{attempt}.json").exists():
                    attempt += 1
                name = f"probe-resume-{attempt}.json"
            return name
        probe_name = on_rank_zero(prepare)
        assigned = assignments(items, manifest, args.group_id, rank)
        error, prefix = None, []
        try:
            prefix = read_prefix(directory / f"shard-{rank}.jsonl", assigned, rank, identity)
        except Exception as caught:
            error = type(caught).__name__ + ": " + str(caught)
        require(not all_errors(error), "Raw prefix is invalid; all existing evidence is preserved")
        counts = [None] * 4
        dist.all_gather_object(counts, len(prefix))
        start = aligned_resume_round(counts, [len(assignments(items, manifest, args.group_id, i)) for i in range(4)])
        del prefix
        write_json(directory / f"allocation-{rank}.json", allocation)
        checkpoint = manifest["checkpoint"]
        model = DecisionModel(checkpoint["model"], checkpoint["revision"], device="cpu", lora_rank=8, max_length=4096)
        shard_frozen_base(model, device)
        reload_replicated_checkpoint(model, group["paths"]["checkpoint"])
        model.eval()

        def scorer(row):
            prompt = {key: row[key] for key in ("state", "question", "kind", "options")}
            with torch.no_grad():
                logits = model([prompt])[0].float().cpu().tolist()
            return logits, model.last_input_tokens

        probe_gate(items, rank, scorer, manifest, args.group_id, fixtures, directory, lambda: cuda_memory(device), name=probe_name)
        if not args.probe_only:
            evaluate_worker(items, manifest, args.group_id, rank, scorer, identity, directory, start=start)
        error = None
        try:
            require(file_hash(args.campaign) == digest, "Campaign changed during evaluation")
            verify_inputs(manifest, group)
            require(load_eval_policy(group["paths"]["resource_policy"]).as_dict() == group["policy"], "Resource policy changed")
            campaign.load_probe_fixtures(args.campaign, manifest)
        except Exception as caught:
            error = type(caught).__name__ + ": " + str(caught)
        require(not all_errors(error), "Pinned inputs changed during evaluation; results require review")

        def finish():
            result = {"status": "probe_passed" if args.probe_only else "complete", "campaign_sha256": digest,
                      "campaign_group_id": args.group_id, "eval_identity_sha256": object_hash(identity),
                      "probe_receipt": {"path": probe_name, "sha256": file_hash(directory / probe_name)},
                      "padding_included_in_denominators": False, "aggregate_metrics_produced": False}
            if not args.probe_only:
                for worker_rank in range(4):
                    expected = assignments(items, manifest, args.group_id, worker_rank)
                    require(len(read_prefix(directory / f"shard-{worker_rank}.jsonl", expected, worker_rank, identity))
                            == len(expected), "Campaign group is incomplete")
                result.update(identity=identity, total_rows=len(campaign.group_indices(manifest, args.group_id)),
                              raw_sha256={f"shard-{r}.jsonl": file_hash(directory / f"shard-{r}.jsonl") for r in range(4)})
            write_json(directory / ("completion.json" if args.probe_only else "summary.json"), result)
            return result
        on_rank_zero(finish)
    finally:
        dist.destroy_process_group()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--campaign-sha256", required=True)
    parser.add_argument("--group-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
