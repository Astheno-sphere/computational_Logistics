"""Launch a bounded, revision-pinned comparison on three unoccupied GPUs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


MODELS = [
    ("2b", "Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    ("9b", "Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    ("27b", "Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
]



def _gpu_indices(value, field):
    if (not isinstance(value, list) or not value
            or any(type(index) is not int or index < 0 for index in value) or len(set(value)) != len(value)):
        raise ValueError(f"resource policy {field} must be distinct nonnegative GPU indices")
    return set(value)


def enforce_resource_policy(root, gpus, policy_path=None, *, hostname=None):
    """Apply every binding policy before querying GPUs or spawning a process.

    The repo's current user restriction cannot be bypassed with a CLI override.
    A separately supplied policy adds restrictions; generic checkouts with no
    saved policy retain occupancy-only behavior.
    """
    _gpu_indices(list(gpus), "requested GPUs")
    hostname = socket.gethostname() if hostname is None else hostname
    machine = hostname.rstrip(".").split(".")[0].lower()
    default = Path(root) / "state/auto_research/resource_policy.json"
    paths = [default] if default.exists() else []
    if policy_path is not None:
        explicit = Path(policy_path)
        if not explicit.is_file():
            raise ValueError(f"resource policy does not exist: {explicit}")
        if explicit.resolve() not in {path.resolve() for path in paths}:
            paths.append(explicit)
    verified = []
    for path in paths:
        raw = path.read_bytes()
        policy = json.loads(raw)
        if not isinstance(policy, dict):
            raise ValueError("resource policy must be a JSON object")
        expected = policy.get("expected_hostname")
        if not isinstance(expected, str) or not expected.strip() or any(char.isspace() for char in expected):
            raise ValueError("resource policy requires an expected_hostname")
        expected = expected.rstrip(".").split(".")[0].lower()
        allowed = _gpu_indices(policy.get("allowed_gpu_indices"), "allowed_gpu_indices")
        training = _gpu_indices(policy.get("training_gpu_indices"), "training_gpu_indices")
        if not training <= allowed:
            raise ValueError("resource policy training GPUs are outside the allowed GPU set")
        evaluation = policy.get("serial_evaluation_gpu_index")
        if evaluation is not None and (type(evaluation) is not int or evaluation not in allowed or evaluation in training):
            raise ValueError("resource policy evaluation GPU must be allowed and separate from training")
        prohibited = policy.get("prohibited_nodes", [])
        if not isinstance(prohibited, list) or any(not isinstance(node, str) or not node for node in prohibited):
            raise ValueError("resource policy prohibited_nodes must contain nonempty host names")
        prohibited = {node.rstrip(".").split(".")[0].lower() for node in prohibited}
        if machine in prohibited or machine != expected:
            raise ValueError(f"resource policy forbids host {hostname!r}; required hostname is {expected!r}")
        if not set(gpus) <= training:
            raise ValueError(f"resource policy forbids training GPUs {sorted(set(gpus) - training)}; allowed training GPUs are {sorted(training)}")
        verified.append({"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                         "expected_hostname": expected, "training_gpu_indices": sorted(training)})
    return {"hostname": hostname, "enforced": bool(verified), "policies": verified}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--gpus", type=int, nargs=3, default=[0, 1, 2])
    parser.add_argument("--steps", type=int, default=400)
    parser.add_argument("--eval-rows", type=int, default=256)
    parser.add_argument("--calibration-rows", type=int, default=192)
    parser.add_argument("--seed", type=int, default=20260919)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--training-sampling", choices=("source_kind_round_robin", "shuffled"), default="shuffled")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--resource-policy", type=Path, help="Additional host/GPU policy; any repository policy remains binding")
    args = parser.parse_args()
    if len(set(args.gpus)) != 3 or min(args.steps, args.eval_rows, args.calibration_rows) < 1:
        parser.error("require three distinct GPUs and positive run sizes")
    root = Path(__file__).resolve().parents[1]
    resource_policy = enforce_resource_policy(root, args.gpus, args.resource_policy)
    subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "jev", "scripts"], cwd=root, check=True,
                   stdout=subprocess.DEVNULL)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    process_uuids = {value.strip() for value in subprocess.check_output(
        ["nvidia-smi", "--query-compute-apps=gpu_uuid", "--format=csv,noheader"], text=True).splitlines()}
    inventory = subprocess.check_output(["nvidia-smi", "--query-gpu=index,uuid,memory.used,utilization.gpu",
                                         "--format=csv,noheader,nounits"], text=True)
    free, gpu_uuids = {}, {}
    for line in inventory.splitlines():
        index, uuid, memory, utilization = [x.strip() for x in line.split(",")]
        gpu_uuids[int(index)] = uuid
        free[int(index)] = uuid not in process_uuids and int(memory) < 512 and int(utilization) < 10
    if not all(free.get(gpu, False) for gpu in args.gpus):
        raise RuntimeError("requested GPUs are not all free; no process launched")
    args.run_root.mkdir(parents=True, exist_ok=False)
    runs = []
    for gpu, (tag, model, revision) in zip(args.gpus, MODELS):
        output, log = args.run_root / tag, args.run_root / (tag + ".log")
        command = [args.python, "-u", "-m", "jev.train", "--model", model, "--revision", revision,
                   "--data", str(args.data.resolve()), "--output", str(output.resolve()),
                   "--steps", str(args.steps), "--train-rows", "0", "--max-length", "4096",
                   "--eval-rows", str(args.eval_rows), "--calibration-rows", str(args.calibration_rows),
                   "--seed", str(args.seed), "--checkpoint-every", str(args.checkpoint_every),
                   "--training-sampling", args.training_sampling]
        environment = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu_uuids[gpu], OMP_NUM_THREADS="4",
                           TOKENIZERS_PARALLELISM="false")
        with log.open("w") as stream:
            process = subprocess.Popen(command, cwd=root, env=environment, stdout=stream,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        runs.append({"model": model, "tag": tag, "pid": process.pid, "gpu": gpu, "gpu_uuid": gpu_uuids[gpu],
                     "command": command, "output": str(output.resolve()), "log": str(log.resolve())})
        (args.run_root / "launch.json").write_text(json.dumps({"commit": commit, "resource_policy": resource_policy, "runs": runs}, indent=2) + "\n")
    print(json.dumps({"commit": commit, "resource_policy": resource_policy, "runs": runs}, indent=2))


if __name__ == "__main__":
    main()
