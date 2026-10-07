"""Explicit four-GPU evaluation leases with ownership-scoped supervision.

This does not change the fixed N1 shared training policy. Each evaluation group
has its own hostname, physical GPU UUIDs and memory limits supplied by the caller.
"""
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
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
import time

from .shared_resources import (cleanup_owned_children, enable_subreaper,
                               owned_descendants, process_identity, require)


@dataclass(frozen=True)
class EvalPolicy:
    hostname: str
    gpu_indices: tuple
    gpu_uuids: tuple
    allocator_limit_mib: int
    own_limit_mib: int
    free_margin_mib: int

    def __post_init__(self):
        require(isinstance(self.hostname, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", self.hostname),
                "An explicit hostname is required")
        require(self.hostname.lower().split(".")[0] not in {"reserved-evaluation-host", "n4-4", "ms-n4-4"},
                "N4-4 is excluded from evaluation allocations")
        require(isinstance(self.gpu_indices, tuple) and len(self.gpu_indices) == 4
                and all(type(i) is int and 0 <= i < 8 for i in self.gpu_indices)
                and len(set(self.gpu_indices)) == 4, "Exactly four distinct physical GPU indices 0 through 7 are required")
        require(isinstance(self.gpu_uuids, tuple) and len(self.gpu_uuids) == 4
                and all(isinstance(value, str) and re.fullmatch(
                    r"GPU-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value)
                        for value in self.gpu_uuids)
                and len(set(self.gpu_uuids)) == 4, "Exactly four distinct full GPU UUIDs are required")
        require(type(self.allocator_limit_mib) is int and type(self.own_limit_mib) is int
                and 0 < self.allocator_limit_mib < self.own_limit_mib,
                "Owned memory limit must exceed the positive allocator limit")
        require(type(self.free_margin_mib) is int and self.free_margin_mib >= 2048,
                "Free memory margin must be at least 2048 MiB")

    def as_dict(self):
        return {"schema_version": 1, "hostname": self.hostname, "gpu_indices": list(self.gpu_indices),
                "gpu_uuids": list(self.gpu_uuids), "allocator_limit_mib": self.allocator_limit_mib,
                "own_limit_mib": self.own_limit_mib, "free_margin_mib": self.free_margin_mib}

    @property
    def sha256(self):
        return object_hash(self.as_dict())


def object_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_eval_policy(path):
    def unique_pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate policy key")
            result[key] = value
        return result
    value = json.loads(Path(path).read_text(), object_pairs_hook=unique_pairs)
    fields = {"schema_version", "hostname", "gpu_indices", "gpu_uuids",
              "allocator_limit_mib", "own_limit_mib", "free_margin_mib"}
    require(isinstance(value, dict) and set(value) == fields and type(value["schema_version"]) is int
            and value["schema_version"] == 1, "A complete version-1 evaluation policy is required")
    require(type(value["gpu_indices"]) is list and type(value["gpu_uuids"]) is list, "GPU identities must be explicit lists")
    return EvalPolicy(**{**{key: value[key] for key in fields - {"schema_version", "gpu_indices", "gpu_uuids"}},
                         "gpu_indices": tuple(value["gpu_indices"]), "gpu_uuids": tuple(value["gpu_uuids"])})


def validate_visible_devices(visible, policy):
    require(isinstance(policy, EvalPolicy) and isinstance(visible, str)
            and tuple(visible.split(",")) == policy.gpu_uuids,
            "CUDA visibility must exactly match the four policy UUIDs in order")
    return policy.gpu_indices


def apply_allocator_budget(device, *, policy, torch_module=None):
    """Call in every rank before CUDA initialization, NCCL or model allocation."""
    require(isinstance(policy, EvalPolicy) and socket.gethostname() == policy.hostname,
            "Evaluation allocator hostname differs from explicit policy")
    validate_visible_devices(os.environ.get("CUDA_VISIBLE_DEVICES", ""), policy)
    if type(device) is int:
        logical = device
    elif re.fullmatch(r"cuda:[0-9]+", str(device)):
        logical = int(str(device).split(":")[1])
    else:
        raise ValueError("Use an explicit CUDA logical device index")
    require(0 <= logical < 4, "Logical CUDA device is outside the evaluation policy")
    if torch_module is None:
        import torch as torch_module
    cuda = torch_module.cuda
    require(not cuda.is_initialized(), "Apply evaluation allocator limit before CUDA initialization")
    total = cuda.get_device_properties(logical).total_memory
    limit = policy.allocator_limit_mib * 1024**2
    require(type(total) is int and total > limit, "Device memory is incompatible with allocator budget")
    cuda.set_per_process_memory_fraction(limit / total, logical)
    return {"policy_sha256": policy.sha256, "logical_device": logical,
            "physical_gpu": policy.gpu_indices[logical], "gpu_uuid": policy.gpu_uuids[logical],
            "allocator_limit_mib": policy.allocator_limit_mib, "total_device_bytes": total,
            "allocator_fraction": limit / total,
            "enforcement": "PyTorch allocator only; aggregate owned NVML watchdog is separately required"}


def _number(value, *, optional=False):
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float("nan")
    if optional and (not math.isfinite(result) or result < 0):
        return None
    require(math.isfinite(result) and result >= 0, "Invalid GPU memory telemetry")
    return result


def parse_gpu_snapshot(inventory, processes, policy):
    expected = dict(zip(policy.gpu_indices, policy.gpu_uuids))
    result = {}
    for line in inventory.splitlines():
        if not line.strip():
            continue
        values = [value.strip() for value in line.split(",")]
        require(len(values) == 4, "Malformed GPU inventory row")
        index, uuid, total, free = values
        index = int(index)
        require(index not in result and expected.get(index) == uuid, "Inventory GPU index/UUID differs from policy")
        result[index] = {"uuid": uuid, "total_mib": _number(total), "free_mib": _number(free), "processes": []}
        require(0 < result[index]["total_mib"] and result[index]["free_mib"] <= result[index]["total_mib"],
                "GPU free/total memory telemetry is inconsistent")
    require(set(result) == set(expected), "All four policy GPUs must be present")
    by_uuid, seen = {uuid: index for index, uuid in expected.items()}, set()
    for line in processes.splitlines():
        if not line.strip():
            continue
        values = [value.strip() for value in line.split(",", 3)]
        require(len(values) == 4, "Malformed GPU process row")
        uuid, pid, used, name = values
        pid = int(pid)
        require(uuid in by_uuid and pid > 0 and (uuid, pid) not in seen, "Unexpected/duplicate GPU process identity")
        seen.add((uuid, pid))
        result[by_uuid[uuid]]["processes"].append({"pid": pid, "used_mib": _number(used, optional=True), "name": name})
    return result


def gpu_snapshot(policy, *, reader=subprocess.check_output):
    common = ["nvidia-smi", "--id=" + ",".join(policy.gpu_uuids)]
    inventory = reader([*common, "--query-gpu=index,uuid,memory.total,memory.free", "--format=csv,noheader,nounits"], text=True, timeout=2)
    processes = reader([*common, "--query-compute-apps=gpu_uuid,pid,used_gpu_memory,process_name", "--format=csv,noheader,nounits"], text=True, timeout=2)
    return parse_gpu_snapshot(inventory, processes, policy)


def _check_snapshot(policy, snapshot):
    require(set(snapshot) == set(policy.gpu_indices)
            and all(snapshot[i]["uuid"] == uuid for i, uuid in zip(policy.gpu_indices, policy.gpu_uuids)),
            "Telemetry allocation differs from policy")
    require(not any("nvidia-cuda-mps-server" in p["name"] for row in snapshot.values() for p in row["processes"]),
            "MPS memory cannot be safely attributed to this job")


def preflight_eval(policy, snapshot, *, hostname=None):
    require((hostname or socket.gethostname()) == policy.hostname, "Evaluation hostname differs from policy")
    _check_snapshot(policy, snapshot)
    required = policy.own_limit_mib + policy.free_margin_mib
    for index in policy.gpu_indices:
        require(snapshot[index]["free_mib"] >= required,
                f"GPU {index} lacks {required} MiB of free capacity; no neighbor is stopped")
    return {"policy_sha256": policy.sha256, "required_free_mib": required,
            "free_mib": {str(i): snapshot[i]["free_mib"] for i in policy.gpu_indices},
            "foreign_processes_allowed": True}


def owned_memory(policy, snapshot, owned, *, identity_reader=None):
    identity_reader = identity_reader or process_identity
    usage, matched = {index: 0.0 for index in policy.gpu_indices}, []
    for index, row in snapshot.items():
        for process in row["processes"]:
            expected = owned.get(process["pid"])
            if expected is None:
                continue
            current = identity_reader(process["pid"])
            if current is None or current["start_time"] != expected["start_time"]:
                continue
            require(process["used_mib"] is not None, "Owned GPU memory is unavailable; stop only this job")
            usage[index] += process["used_mib"]
            matched.append({"pid": process["pid"], "start_time": expected["start_time"],
                            "gpu_index": index, "used_mib": process["used_mib"]})
    return usage, matched


def check_owned_budget(policy, snapshot, owned, *, identity_reader=None):
    _check_snapshot(policy, snapshot)
    usage, matched = owned_memory(policy, snapshot, owned, identity_reader=identity_reader)
    require(all(value <= policy.own_limit_mib for value in usage.values()),
            "Aggregate owned GPU memory exceeded evaluation budget: " + str(usage))
    return {"owned_mib": {str(i): value for i, value in usage.items()}, "owned_processes": matched}


@contextmanager
def gpu_locks(policy, *, lock_root=Path("/tmp")):
    # Names also conflict with the existing N1 guards for overlapping indices.
    with ExitStack() as stack:
        for index in sorted(policy.gpu_indices):
            handle = stack.enter_context((Path(lock_root) / f"open-jev-eval-gpu-{index}.lock").open("a+"))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def validate_stage(stage):
    require(isinstance(stage, dict) and set(stage) == {"argv", "timeout_seconds"},
            "Specify exactly one finite stage with argv and timeout_seconds")
    require(isinstance(stage["argv"], list) and stage["argv"]
            and all(isinstance(value, str) and value and "\0" not in value for value in stage["argv"]),
            "Stage argv must be a nonempty argument list")
    timeout = stage["timeout_seconds"]
    require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 604800,
            "Stage timeout must be positive and at most seven days")
    return {"argv": list(stage["argv"]), "timeout_seconds": timeout}


def _write_report(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


class EvalRunError(RuntimeError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def run_eval_stage(stage, *, policy_path, output_dir, poll_seconds=1):
    """Run one finite stage; never retry or signal processes outside our subtree."""
    stage, policy = validate_stage(stage), load_eval_policy(policy_path)
    require(type(poll_seconds) in (int, float) and 0 < poll_seconds <= 2, "Poll interval must be in (0, 2] seconds")
    require(socket.gethostname() == policy.hostname, "Evaluation hostname differs from policy")
    require(not owned_descendants(), "Controller must be dedicated with no existing children")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    frozen_policy = output_dir / "policy.json"
    _write_report(frozen_policy, policy.as_dict())
    _write_report(output_dir / "stage-spec.json", stage)
    report = {"schema_version": 1, "status": "running", "stage": stage, "stage_sha256": object_hash(stage),
              "policy": policy.as_dict(), "policy_sha256": policy.sha256, "cwd": os.getcwd(),
              "controller": process_identity(os.getpid()), "started_at": time.time(), "exit_code": None,
              "automatic_retries": 0, "own_peak_mib": {str(i): 0.0 for i in policy.gpu_indices},
              "limitations": "Sampled owned NVML watchdog; allocator cap excludes non-PyTorch allocations."}
    report_path = output_dir / "stage.json"
    _write_report(report_path, report)
    child, owned, handlers, leases = None, {}, {}, ExitStack()

    def interrupted(signum, frame):
        raise RuntimeError("Evaluation controller received signal " + str(signum))

    try:
        enable_subreaper()
        for signum in (signal.SIGTERM, signal.SIGINT):
            handlers[signum] = signal.signal(signum, interrupted)
        leases.enter_context(gpu_locks(policy))
        report["preflight"] = preflight_eval(policy, gpu_snapshot(policy))
        require(not owned_descendants(), "Controller acquired unexpected children before launch")
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(policy.gpu_uuids), CUDA_DEVICE_ORDER="PCI_BUS_ID",
                   OPEN_JEV_EVAL_POLICY=str(frozen_policy))
        report["cuda_visible_devices"] = env["CUDA_VISIBLE_DEVICES"]
        report["allocator_enforcement"] = "Every rank must call apply_allocator_budget before CUDA initialization"
        with (output_dir / "stage.log").open("wb") as log:
            started, last_flush = time.monotonic(), 0.0
            child = subprocess.Popen(stage["argv"], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            identity = process_identity(child.pid)
            report["leader"] = identity or {"pid": child.pid, "start_time": None}
            if identity is not None:
                owned[child.pid] = identity
            _write_report(report_path, report)
            while True:
                require(time.monotonic() - started < stage["timeout_seconds"], "Finite evaluation stage timeout expired")
                owned.update(owned_descendants())
                snapshot = gpu_snapshot(policy)
                owned.update(owned_descendants())
                usage, matched = owned_memory(policy, snapshot, owned)
                for index, value in usage.items():
                    report["own_peak_mib"][str(index)] = max(report["own_peak_mib"][str(index)], value)
                report["last_owned_processes"], report["last_sample_at"] = matched, time.time()
                check_owned_budget(policy, snapshot, owned)
                if time.monotonic() - last_flush >= 10:
                    _write_report(report_path, report)
                    last_flush = time.monotonic()
                report["exit_code"] = child.poll()
                if report["exit_code"] is not None:
                    require(report["exit_code"] == 0, "Evaluation child exited unsuccessfully")
                    report["status"] = "completed"
                    break
                time.sleep(min(poll_seconds, max(0, stage["timeout_seconds"] - (time.monotonic() - started))))
    except BaseException as error:
        report["status"], report["stop_reason"] = "failed", {"type": type(error).__name__, "message": str(error)}
    finally:
        if child is not None:
            for signum in handlers:
                signal.signal(signum, signal.SIG_IGN)
            try:
                owned.update(owned_descendants())
                cleanup = cleanup_owned_children(child, term_timeout=10, kill_timeout=10)
                report["cleanup"] = cleanup
                owned.update({entry["pid"]: entry for entry in cleanup["owned"]})
                report["exit_code"] = child.poll()
                require(cleanup["confirmed"], "Owned child cleanup was not confirmed")
                require(report["status"] != "completed" or not (cleanup["term_signals"] or cleanup["kill_signals"]),
                        "Leader exited with remaining children; stage is incomplete")
                snapshot = gpu_snapshot(policy)
                _check_snapshot(policy, snapshot)
                usage, matched = owned_memory(policy, snapshot, owned)
                require(not matched, "Owned GPU processes remain after cleanup")
                report["post_cleanup_owned_mib"] = {str(i): value for i, value in usage.items()}
                report["owned_gpu_cleanup_confirmed"] = True
            except BaseException as error:
                report["status"], report["cleanup_error"] = "failed", {"type": type(error).__name__, "message": str(error)}
        leases.close()
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        report["finished_at"] = time.time()
        _write_report(report_path, report)
    if report["status"] != "completed":
        raise EvalRunError("Evaluation stage failed; inspect " + str(report_path), report)
    return report
