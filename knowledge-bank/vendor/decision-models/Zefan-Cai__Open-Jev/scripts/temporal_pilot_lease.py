"""CPU-only registration for the queue controller's one bounded GPU 5 lease."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path


def process_identity(pid):
    root = Path("/proc") / str(pid)
    fields = (root / "stat").read_text().rsplit(")", 1)[1].split()
    if fields[0] == "Z":
        raise ValueError("Process is a zombie")
    return {"pid": pid, "start_ticks": int(fields[19]), "uid": root.stat().st_uid}


@contextmanager
def locked_lease(path):
    path = Path(path)
    with path.with_suffix(".lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield path


def write_lease(path, value):
    temporary = path.with_name(path.name + "." + str(os.getpid()) + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temporary, path)


def register(path, stamp, uuid, commit, output):
    pid = os.getpid()
    if os.getsid(pid) != pid:
        raise ValueError("Actual pilot must be its own session leader")
    identity = process_identity(pid)
    with locked_lease(path) as lease_path:
        lease = json.loads(lease_path.read_text())
        controller = lease["controller_identity"]
        if (lease["status"] != "available" or lease["controller_stamp"] != stamp
                or process_identity(controller["pid"]) != controller
                or lease["gpu"] != 5 or lease["gpu_uuid"] != uuid
                or os.environ.get("CUDA_VISIBLE_DEVICES") != uuid
                or lease["source_commit"] != commit or lease["maximum_runtime_seconds"] != 300
                or not Path(output).resolve().is_relative_to(Path(lease["task_directory"]).resolve())):
            raise ValueError("GPU lease/controller/source identity differs or is closing")
        lease.update(status="running", process_identity=identity)
        write_lease(lease_path, lease)
    return identity


def record_exit(path, stamp, identity, status):
    with locked_lease(path) as lease_path:
        lease = json.loads(lease_path.read_text())
        if lease["controller_stamp"] != stamp or lease.get("process_identity") != identity:
            raise ValueError("Refusing to update another pilot/controller lease")
        # The controller can close the lease while the pilot is finishing.
        if lease["status"] == "running":
            lease["status"] = "exited"
        lease["pilot_exit_status"] = status
        lease["session_cleanup_confirmed"] = False  # Only the external watcher can confirm actual exit.
        write_lease(lease_path, lease)
