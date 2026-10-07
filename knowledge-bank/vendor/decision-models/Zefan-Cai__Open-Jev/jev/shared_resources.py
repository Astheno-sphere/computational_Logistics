"""Opt-in shared N1 GPU budget and ownership-scoped subprocess supervision.

Legacy exclusive launchers do not import or activate this mode. GPU memory is
attributed by PID plus start time, never username or process-name matching.
"""
import ctypes
from contextlib import contextmanager
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

HOSTNAME = "configure-your-explicit-hostname"
GPU_UUIDS = (
    "GPU-00000000-0000-0000-0000-000000000001",
    "GPU-00000000-0000-0000-0000-000000000002",
    "GPU-00000000-0000-0000-0000-000000000003",
    "GPU-00000000-0000-0000-0000-000000000004",
)
PROJECT_LOCKS = ("/tmp/open-jev-n1-four-gpu-schedule.lock", "/tmp/open-jev-n1-gpu-0-3.lock",
                 *(f"/tmp/open-jev-eval-gpu-{i}.lock" for i in range(4)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass(frozen=True)
class SharedPolicy:
    allocator_limit_mib: int = 30720
    own_limit_mib: int = 34816
    free_margin_mib: int = 2048

    def __post_init__(self):
        require(type(self.allocator_limit_mib) is int and 0 < self.allocator_limit_mib <= 32768,
                "Shared allocator budget must be positive and at most 32 GiB")
        require(type(self.own_limit_mib) is int and self.allocator_limit_mib < self.own_limit_mib <= 34816,
                "Aggregate owned GPU budget must exceed allocator budget and be at most 34 GiB")
        require(type(self.free_margin_mib) is int and self.free_margin_mib >= 2048,
                "Prelaunch free-memory margin must be at least 2 GiB")

    def as_dict(self):
        return {"schema_version": 1, "mode": "shared", "hostname": HOSTNAME,
                "gpu_indices": [0, 1, 2, 3], "gpu_uuids": list(GPU_UUIDS),
                "allocator_limit_mib": self.allocator_limit_mib, "own_limit_mib": self.own_limit_mib,
                "free_margin_mib": self.free_margin_mib}

    @property
    def sha256(self):
        return hashlib.sha256(json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_shared_policy(path):
    value = json.loads(Path(path).read_text())
    expected = SharedPolicy().as_dict()
    require(isinstance(value, dict) and set(value) == set(expected), "Explicit complete shared policy is required")
    for key in ("schema_version", "mode", "hostname", "gpu_indices", "gpu_uuids"):
        require(value[key] == expected[key] and type(value[key]) is type(expected[key]),
                "Shared policy host, mode or physical allocation differs: " + key)
    return SharedPolicy(**{key: value[key] for key in ("allocator_limit_mib", "own_limit_mib", "free_margin_mib")})


def selected_devices(indices):
    indices = tuple(indices)
    require(indices and len(indices) == len(set(indices)) and all(type(i) is int and i in range(4) for i in indices),
            "Only unique physical N1 GPU indices 0 through 3 are allowed")
    return indices


def validate_visible_devices(visible):
    devices = visible.split(",")
    require(devices and len(devices) == len(set(devices)) and all(value in GPU_UUIDS for value in devices),
            "Shared CUDA visibility must contain only the pinned N1 GPU 0–3 UUIDs")
    return tuple(GPU_UUIDS.index(value) for value in devices)


def apply_allocator_budget(device, *, policy, torch_module=None):
    """Apply before application CUDA allocations, NCCL and any model loading.

    PyTorch may initialize the CUDA context while setting this allocator limit.
    It does not bound non-PyTorch CUDA/NCCL allocations; the controller separately
    monitors aggregate owned NVML usage with a lower-than-40-GiB stopping limit.
    """
    require(isinstance(policy, SharedPolicy), "An explicit validated shared policy is required")
    require(socket.gethostname() == HOSTNAME, "Shared allocator setup is authorized only on pinned N1-1")
    visible = validate_visible_devices(os.environ.get("CUDA_VISIBLE_DEVICES", ""))
    text = str(device)
    if isinstance(device, int) and not isinstance(device, bool):
        logical = device
    elif re.fullmatch(r"cuda:[0-9]+", text):
        logical = int(text.split(":", 1)[1])
    else:
        raise ValueError("Use an explicit CUDA logical device index")
    require(0 <= logical < len(visible), "CUDA logical device is outside the shared visibility map")
    if torch_module is None:
        import torch as torch_module
    cuda = torch_module.cuda
    require(not cuda.is_initialized(), "Apply the shared allocator budget before CUDA initialization/application allocations")
    total = cuda.get_device_properties(logical).total_memory
    limit = policy.allocator_limit_mib * 1024**2
    require(type(total) is int and total > limit, "Reported device total memory is incompatible with the budget")
    fraction = limit / total
    cuda.set_per_process_memory_fraction(fraction, logical)
    return {"policy_sha256": policy.sha256, "logical_device": logical, "physical_gpu": visible[logical],
            "gpu_uuid": GPU_UUIDS[visible[logical]], "allocator_limit_mib": policy.allocator_limit_mib,
            "total_device_bytes": total, "allocator_fraction": fraction,
            "enforcement": "PyTorch allocator only; aggregate owned NVML watchdog is separately required"}


def _number(value, *, optional=False):
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        if optional:
            return None
        raise ValueError("GPU memory telemetry is not numeric")
    if not math.isfinite(parsed) or parsed < 0:
        if optional:
            return None
        raise ValueError("GPU memory telemetry is negative or nonfinite")
    return parsed


def parse_gpu_snapshot(inventory, processes):
    result = {}
    for line in inventory.splitlines():
        if not line.strip():
            continue
        values = [value.strip() for value in line.split(",")]
        require(len(values) == 4, "Malformed GPU inventory row")
        index, uuid, total, free = values
        index = int(index)
        require(index in range(4) and index not in result and uuid == GPU_UUIDS[index], "Physical GPU UUID/index differs")
        result[index] = {"uuid": uuid, "total_mib": _number(total), "free_mib": _number(free), "processes": []}
        require(0 < result[index]["total_mib"] and result[index]["free_mib"] <= result[index]["total_mib"],
                "GPU free/total memory telemetry is inconsistent")
    require(set(result) == set(range(4)), "All four pinned GPU inventory rows are required")
    seen = set()
    for line in processes.splitlines():
        if not line.strip():
            continue
        values = [value.strip() for value in line.split(",", 3)]
        require(len(values) == 4, "Malformed GPU process row")
        uuid, pid, used, name = values
        require(uuid in GPU_UUIDS, "GPU process telemetry escapes the selected devices")
        pid = int(pid)
        require(pid > 0 and (uuid, pid) not in seen, "Duplicate or invalid GPU process identity")
        seen.add((uuid, pid))
        result[GPU_UUIDS.index(uuid)]["processes"].append({"pid": pid, "used_mib": _number(used, optional=True), "name": name})
    return result


def gpu_snapshot(*, reader=subprocess.check_output):
    # --id restricts both queries to the explicitly authorized physical devices.
    common = ["nvidia-smi", "--id=0,1,2,3"]
    inventory = reader([*common, "--query-gpu=index,uuid,memory.total,memory.free", "--format=csv,noheader,nounits"], text=True, timeout=2)
    processes = reader([*common, "--query-compute-apps=gpu_uuid,pid,used_gpu_memory,process_name", "--format=csv,noheader,nounits"], text=True, timeout=2)
    return parse_gpu_snapshot(inventory, processes)


def preflight_shared(policy, snapshot, indices=(0, 1, 2, 3), *, hostname=None):
    require(isinstance(policy, SharedPolicy) and (hostname or socket.gethostname()) == HOSTNAME,
            "Shared execution is authorized only on pinned N1-1")
    indices = selected_devices(indices)
    required = policy.allocator_limit_mib + policy.free_margin_mib
    for index in indices:
        row = snapshot[index]
        require(row["uuid"] == GPU_UUIDS[index], "Preflight physical GPU identity changed")
        require(row["free_mib"] >= required, f"GPU {index} lacks {required} MiB of free capacity; no neighbor is stopped")
        require(not any("nvidia-cuda-mps-server" in process["name"] for process in row["processes"]),
                "MPS memory cannot be safely attributed to this job")
    return {"policy_sha256": policy.sha256, "required_free_mib": required,
            "free_mib": {str(i): snapshot[i]["free_mib"] for i in indices},
            "foreign_processes_allowed": True, "physical_gpu_indices": list(indices)}


def owned_memory(snapshot, owned, *, identity_reader=None):
    identity_reader = identity_reader or process_identity
    usage = {index: 0.0 for index in range(4)}
    matched = []
    for index, row in snapshot.items():
        for process in row["processes"]:
            expected = owned.get(process["pid"])
            if expected is None:
                continue
            current = identity_reader(process["pid"])
            if current is None or current["start_time"] != expected["start_time"]:
                continue  # Never attribute a reused neighbor PID to this job.
            require(process["used_mib"] is not None, "Owned GPU process memory is unavailable; stop only this job")
            usage[index] += process["used_mib"]
            matched.append({"pid": process["pid"], "start_time": expected["start_time"], "gpu_index": index,
                            "used_mib": process["used_mib"]})
    return usage, matched


def check_owned_budget(policy, snapshot, owned, indices=(0, 1, 2, 3), *, identity_reader=None):
    indices = selected_devices(indices)
    require(not any("nvidia-cuda-mps-server" in process["name"]
                    for index in indices for process in snapshot[index]["processes"]),
            "MPS memory cannot be safely attributed to this job")
    usage, matched = owned_memory(snapshot, owned, identity_reader=identity_reader)
    require(not any(usage[index] for index in set(range(4)) - set(indices)), "Owned process used an unassigned GPU")
    require(all(usage[index] <= policy.own_limit_mib for index in indices),
            "Aggregate owned GPU memory exceeded the shared budget: " + str(usage))
    return {"owned_mib": {str(index): usage[index] for index in indices}, "owned_processes": matched}


# Ownership and pidfd cleanup helpers derive from the reviewed finite sequence
# guard, with a second ancestry check against parent-PID reuse during /proc scans.
# The caller must be dedicated: all descendants are this controller's own job.
def open_pidfd(pid):
 if hasattr(os,'pidfd_open'):return os.pidfd_open(pid,0)
 # The N1 Python build omits os.pidfd_open; use the x86-64 Linux syscall.
 if os.uname().machine!='x86_64':raise RuntimeError('Unsupported pidfd fallback architecture')
 fd=ctypes.CDLL(None,use_errno=True).syscall(434,pid,0)
 if fd<0:raise OSError(ctypes.get_errno(),'pidfd_open failed')
 return fd

def enable_subreaper():
 if not hasattr(signal,'pidfd_send_signal'):
  raise RuntimeError('Linux pidfd support is required for owned-process cleanup')
 os.close(open_pidfd(os.getpid()))
 if ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)!=0:
  raise OSError(ctypes.get_errno(),'Cannot enable Linux child subreaper')

def process_identity(pid):
 try:fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
 except (FileNotFoundError,ProcessLookupError):return None
 return {'pid':pid,'ppid':int(fields[1]),'start_time':int(fields[19]),'state':fields[0]}

def owned_descendants():
 processes={}
 for path in Path('/proc').iterdir():
  if not path.name.isdigit():continue
  try:info=process_identity(int(path.name))
  except PermissionError:continue
  if info is not None:processes[info['pid']]=info
 parents={os.getpid()};owned={}
 while True:
  found={pid:info for pid,info in processes.items() if pid not in parents and info['ppid'] in parents}
  if not found:break
  owned.update(found);parents.update(found)
 return {pid:info for pid,info in owned.items() if _confirmed_ancestry(info,owned)}


def _confirmed_ancestry(identity, owned):
    """Recheck child-to-root identities before accepting a PPID scan result."""
    expected = identity
    seen = set()
    while expected is not None and expected["pid"] not in seen:
        seen.add(expected["pid"])
        current = process_identity(expected["pid"])
        if current is None or current["start_time"] != expected["start_time"]:
            return False
        if current["ppid"] == os.getpid():
            return True
        expected = owned.get(current["ppid"])
    return False

def signal_owned(identity,signum):
 try:fd=open_pidfd(identity['pid'])
 except ProcessLookupError:return False
 try:
  current=process_identity(identity['pid'])
  if current is None or current['start_time']!=identity['start_time']:return False
  try:signal.pidfd_send_signal(fd,signum)
  except ProcessLookupError:return False
  return True
 finally:os.close(fd)

def cleanup_owned_children(leader,term_timeout=30,kill_timeout=30):
 # Subreaping keeps detached rank processes ours even after their launcher exits.
 # PID start times plus pidfds prevent signalling a reused, unrelated PID.
 owned={};sent_term=set();sent_kill=set();started=time.monotonic()
 while True:
  leader.poll()
  owned.update(owned_descendants())
  remaining={}
  for pid,identity in owned.items():
   current=process_identity(pid)
   if current is None or current['start_time']!=identity['start_time']:continue
   if current['state']=='Z' and pid!=leader.pid:
    try:os.waitpid(pid,os.WNOHANG)
    except ChildProcessError:pass
    current=process_identity(pid)
    if current is None or current['start_time']!=identity['start_time']:continue
   remaining[pid]=current
  if not remaining:
   # A /proc snapshot can race with reparenting. ECHILD is the final kernel
   # check that this subreaper has neither a live child nor an unreaped orphan.
   try:reaped,status=os.waitpid(-1,os.WNOHANG)
   except ChildProcessError:
    return {'confirmed':True,'owned':[{'pid':v['pid'],'start_time':v['start_time']} for v in owned.values()],
            'term_signals':len(sent_term),'kill_signals':len(sent_kill),'remaining':[]}
   if reaped==leader.pid and leader.returncode is None:leader.returncode=os.waitstatus_to_exitcode(status)
  elapsed=time.monotonic()-started
  if elapsed>=term_timeout+kill_timeout:
   raise RuntimeError('Owned processes did not exit: '+str(sorted(remaining)))
  signum,sent=(signal.SIGTERM,sent_term) if elapsed<term_timeout else (signal.SIGKILL,sent_kill)
  for identity in remaining.values():
   key=(identity['pid'],identity['start_time'])
   if identity['state']!='Z' and key not in sent and signal_owned(identity,signum):sent.add(key)
  time.sleep(.1)


class SharedRunError(RuntimeError):
    """A finite sequence stopped; its report records incomplete stages."""

    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


class SharedRunInterrupted(RuntimeError):
    pass


@contextmanager
def project_locks():
    handles = []
    try:
        for path in PROJECT_LOCKS:
            handle = open(path, "a+")
            handles.append(handle)
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def _write_report(path, report):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _validate_stages(stages):
    require(isinstance(stages, list) and stages, "An explicit finite nonempty stage list is required")
    result = []
    for stage in stages:
        require(isinstance(stage, dict) and set(stage) == {"name", "argv", "gpu_indices", "timeout_seconds"},
                "Each stage must specify name, argv, gpu_indices and timeout_seconds")
        require(isinstance(stage["name"], str) and re.fullmatch(r"[a-zA-Z0-9_-]+", stage["name"]),
                "Use a simple unique stage name")
        argv = stage["argv"]
        require(isinstance(argv, list) and argv and all(isinstance(value, str) and value and "\0" not in value for value in argv),
                "Stage argv must be a nonempty argument list, not a shell string")
        timeout = stage["timeout_seconds"]
        require(type(timeout) in (int, float) and math.isfinite(timeout) and 0 < timeout <= 7 * 86400,
                "Each command needs a positive finite timeout of at most seven days")
        result.append({**stage, "gpu_indices": list(selected_devices(stage["gpu_indices"]))})
    require(len({stage["name"] for stage in result}) == len(result), "Stage names must be unique")
    return result


def _run_shared_stage(stage, *, policy, policy_path, output_dir, poll_seconds):
    report = {**stage, "status": "running", "started_at": time.time(), "exit_code": None,
              "policy_sha256": policy.sha256, "cwd": os.getcwd(),
              "command_sha256": hashlib.sha256(json.dumps(stage["argv"], separators=(",", ":")).encode()).hexdigest(),
              "own_peak_mib": {str(i): 0.0 for i in stage["gpu_indices"]}}
    report_path = output_dir / (stage["name"] + ".json")
    child = None
    owned = {}
    try:
        require(not owned_descendants(), "Dedicated shared controller already has children; refusing to claim them")
        report["preflight"] = preflight_shared(policy, gpu_snapshot(), stage["gpu_indices"])
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=",".join(GPU_UUIDS[i] for i in stage["gpu_indices"]),
                   CUDA_DEVICE_ORDER="PCI_BUS_ID", OPEN_JEV_SHARED_POLICY=str(policy_path))
        report["cuda_visible_devices"] = env["CUDA_VISIBLE_DEVICES"]
        report["allocator_enforcement"] = "Child must apply apply_allocator_budget before application CUDA allocations"
        with (output_dir / (stage["name"] + ".log")).open("wb") as log:
            started = time.monotonic()
            last_flush = started - 10
            child = subprocess.Popen(stage["argv"], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            identity = process_identity(child.pid)
            report["leader"] = identity or {"pid": child.pid, "start_time": None}
            if identity is not None:
                owned[child.pid] = identity
            _write_report(report_path, report)
            while True:
                if time.monotonic() - started >= stage["timeout_seconds"]:
                    raise TimeoutError("Finite stage timeout expired")
                owned.update(owned_descendants())
                snapshot = gpu_snapshot()
                owned.update(owned_descendants())
                # Keep observed peaks even when the following budget check fails.
                usage, matched = owned_memory(snapshot, owned)
                for index in stage["gpu_indices"]:
                    report["own_peak_mib"][str(index)] = max(report["own_peak_mib"][str(index)], usage[index])
                report["last_owned_processes"] = matched
                report["last_sample_at"] = time.time()
                sampled = time.monotonic()
                if sampled - last_flush >= 10:
                    _write_report(report_path, report)
                    last_flush = sampled
                check_owned_budget(policy, snapshot, owned, stage["gpu_indices"])
                report["exit_code"] = child.poll()
                if report["exit_code"] is not None:
                    require(report["exit_code"] == 0, "Child command exited unsuccessfully")
                    report["status"] = "completed"
                    break
                time.sleep(min(poll_seconds, max(0, stage["timeout_seconds"] - (time.monotonic() - started))))
    except BaseException as error:
        report["status"] = "failed"
        report["stop_reason"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        if child is not None:
            # Finish bounded own-child cleanup even if another interrupt arrives.
            handlers = {signum: signal.signal(signum, signal.SIG_IGN) for signum in (signal.SIGTERM, signal.SIGINT)}
            try:
                owned.update(owned_descendants())
                cleanup = cleanup_owned_children(child, term_timeout=10, kill_timeout=10)
                report["cleanup"] = cleanup
                owned.update({entry["pid"]: entry for entry in cleanup["owned"]})
                report["exit_code"] = child.poll()
                require(cleanup["confirmed"], "Owned child cleanup was not confirmed")
                require(report["status"] != "completed" or not (cleanup["term_signals"] or cleanup["kill_signals"]),
                        "Leader exited while owned children were still running; stage is incomplete")
                usage, matched = owned_memory(gpu_snapshot(), owned)
                require(not matched, "Owned GPU processes remain after cleanup")
                report["post_cleanup_owned_mib"] = {str(i): usage[i] for i in stage["gpu_indices"]}
                report["owned_gpu_cleanup_confirmed"] = True
            except BaseException as error:
                report["status"] = "failed"
                report["cleanup_error"] = {"type": type(error).__name__, "message": str(error)}
            finally:
                for signum, handler in handlers.items():
                    signal.signal(signum, handler)
        report["finished_at"] = time.time()
        _write_report(report_path, report)
    return report


def run_shared_sequence(stages, *, policy_path, output_dir, poll_seconds=1):
    """Run a finite sequence in a dedicated Linux controller, with no retries.

    Commands must themselves call apply_allocator_budget in every CUDA process.
    This supervisor only enforces the sampled aggregate NVML threshold. It does
    not claim a hard bound on instantaneous CUDA/NCCL allocation or neighbors.
    All project locks stay held through cleanup and across stages.
    """
    stages = _validate_stages(stages)
    require(type(poll_seconds) in (int, float) and 0 < poll_seconds <= 2, "Watchdog poll interval must be in (0, 2] seconds")
    policy = load_shared_policy(policy_path)
    require(socket.gethostname() == HOSTNAME, "Shared execution is authorized only on pinned N1-1")
    require(not owned_descendants(), "Shared launcher must be a dedicated process without existing children")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    frozen_policy = output_dir / "policy.json"
    frozen_policy.write_text(json.dumps(policy.as_dict(), indent=2) + "\n")
    report = {"schema_version": 1, "mode": "shared", "status": "running", "policy": policy.as_dict(),
              "policy_sha256": policy.sha256, "started_at": time.time(), "stages": [], "planned_stages": stages,
              "automatic_retries": 0, "limitations": "Sampled NVML watchdog; allocator cap excludes non-PyTorch allocations"}
    report_path = output_dir / "sequence.json"
    _write_report(report_path, report)

    def interrupted(signum, frame):
        raise SharedRunInterrupted("Shared controller received signal " + str(signum))

    handlers = {signum: signal.signal(signum, interrupted) for signum in (signal.SIGTERM, signal.SIGINT)}
    try:
        enable_subreaper()
        with project_locks():
            for stage in stages:
                result = _run_shared_stage(stage, policy=policy, policy_path=frozen_policy,
                                           output_dir=output_dir, poll_seconds=poll_seconds)
                report["stages"].append(result)
                _write_report(report_path, report)
                require(result["status"] == "completed", "Sequence stopped after stage " + stage["name"])
            report["status"] = "completed"
    except BaseException as error:
        report["status"] = "failed"
        report["stop_reason"] = {"type": type(error).__name__, "message": str(error)}
    finally:
        for signum, handler in handlers.items():
            signal.signal(signum, handler)
        report["finished_at"] = time.time()
        _write_report(report_path, report)
    if report["status"] != "completed":
        raise SharedRunError("Shared sequence failed; inspect " + str(report_path), report)
    return report
