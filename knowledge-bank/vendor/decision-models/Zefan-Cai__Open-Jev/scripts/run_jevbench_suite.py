"""Evaluate selected 2B/9B/27B checkpoints serially, with owned server cleanup.

Base weights must already be in the offline Hugging Face cache. The caller
stages checkpoints and the prepared public requests before launching this
driver. Gold is read only during offline summaries, after all servers stop.
"""
import argparse
from datetime import datetime, timezone
import http.client
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

from scripts import jevbench_openjev as benchmark
from scripts.run_service_suite import checkpoint_identity, gpu_snapshot, require_free_gpu, stop_child


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_REQUESTS_SHA256 = "2e20ff5f94dd04d015b3a7b9abd955757b6c5be25b55b97fcd141cb52f88b4aa"


def now():
    return datetime.now(timezone.utc).isoformat()


def slurm_environment():
    """Preserve the allocation's CUDA mapping; never choose physical GPU 0."""
    job = os.environ.get("SLURM_JOB_ID", "").strip()
    devices = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not job or re.fullmatch(r"(?:[0-9]+|GPU-[A-Za-z0-9-]+|MIG-[A-Za-z0-9/-]+)", devices) is None:
        raise ValueError("Run inside a Slurm allocation exposing exactly one CUDA device")
    env = dict(os.environ)
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONUNBUFFERED="1",
               PYTHONPATH=str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""))
    return env, {"job_id": job, "partition": env.get("SLURM_JOB_PARTITION"),
                 "node_list": env.get("SLURM_JOB_NODELIST"), "hostname": socket.gethostname(),
                 "cuda_visible_devices": devices, "logical_device": "cuda:0"}


def allocated_environment(args):
    host, gpu = getattr(args, "expected_host", None), getattr(args, "physical_gpu", None)
    if host is None and gpu is None:
        env, allocation = slurm_environment()
        return env, {"mode": "slurm", **allocation}
    if host != "kwade5342000001" or socket.gethostname() != host or type(gpu) is not int or gpu not in range(4):
        raise ValueError("Explicit N1 execution requires kwade5342000001 and physical GPU 0, 1, 2 or 3")
    snapshot = require_free_gpu(gpu)
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": snapshot["uuid"],
           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONUNBUFFERED": "1",
           "PYTHONPATH": str(ROOT) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    return env, {"mode": "n1_explicit", "hostname": host, "physical_gpu": gpu,
                 "cuda_visible_devices": snapshot["uuid"], "logical_device": "cuda:0", "initial_gpu": snapshot}


def wait_ready(server, log_path, identity, port, timeout):
    deadline = time.monotonic() + timeout
    base = f"http://127.0.0.1:{port}"
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Owned server exited {server.returncode}; inspect {log_path}")
        with log_path.open("rb") as stream:
            stream.seek(max(0, log_path.stat().st_size - 65536))
            lines = stream.read().decode(errors="replace").splitlines()
        own_ready = False
        for line in lines:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event == {"url": base, "model": identity["model"],
                                                     "method": identity["method"]}:
                own_ready = True
        if own_ready:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=min(5, max(.01, deadline - time.monotonic())))
            try:
                connection.request("GET", "/health")
                response = connection.getresponse()
                health = benchmark.strict_json(response.read())
                if response.status != 200 or health != {"status": "ready", "model": identity["model"],
                                                         "method": identity["method"]}:
                    raise RuntimeError("Health model/method identity differs")
                if server.poll() is not None:
                    raise RuntimeError("Owned server exited during readiness verification")
                return health
            except OSError:
                pass
            finally:
                connection.close()
        time.sleep(min(.25, max(0, deadline - time.monotonic())))
    raise TimeoutError(f"Owned server startup exceeded {timeout}s")


def run_collection(server, command, log_path, env, timeout, record, save):
    """Watch both exact child objects; terminate only the child we created."""
    process = None
    started = time.monotonic()
    try:
        if server.poll() is not None:
            raise RuntimeError("Owned server exited before collection")
        with log_path.open("x") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            record.update(pid=process.pid, command=command, started_at_utc=now())
            save()
            while process.poll() is None:
                if server.poll() is not None:
                    raise RuntimeError("Owned server exited during collection; no further requests permitted")
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("Collection exceeded its wall-clock limit")
                try:
                    process.wait(timeout=min(.25, remaining))
                except subprocess.TimeoutExpired:
                    pass
            record["exit_code"] = process.returncode
            return process.returncode
    finally:
        record["child_exit_code"] = stop_child(process)
        record["elapsed_seconds"] = time.monotonic() - started
        save()


def run_suite(args):
    env, allocation = allocated_environment(args)
    for key in ("startup_timeout", "collection_timeout", "request_timeout"):
        if not math.isfinite(getattr(args, key)) or not 0 < getattr(args, key) <= 86400:
            raise ValueError("Timeouts must be finite, positive and at most one day")
    if args.request_timeout > 300 or args.max_length < 1 or args.batch_size < 1 or not 1024 <= args.port <= 65535:
        raise ValueError("Invalid request timeout, context/batch size or port")
    if args.input_sha256 != PUBLIC_REQUESTS_SHA256:
        raise ValueError("The suite requires every frozen public JevBench request")
    workloads, _ = benchmark.load_workloads(args.requests, args.input_sha256)
    if len(workloads) != 231:
        raise ValueError("Expected 231 frozen public requests")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(ROOT), "diff", "HEAD", "--name-only"], text=True).strip():
        raise ValueError("Commit reviewed source changes before launching the suite")
    upstream_commit = subprocess.check_output(
        ["git", "-C", str(args.upstream), "rev-parse", "HEAD"], text=True).strip()
    if upstream_commit != benchmark.UPSTREAM_COMMIT:
        raise ValueError("JevBench source commit differs")
    identities = {}
    checkpoints = {tag: value.resolve() for tag in ("2b", "9b", "27b")
                   if (value := getattr(args, "checkpoint_" + tag, None)) is not None}
    if not checkpoints:
        raise ValueError("Select at least one trained checkpoint")
    for tag, checkpoint in checkpoints.items():
        if not (checkpoint / "head.pt").is_file() or not (checkpoint / "adapter").is_dir():
            raise ValueError("Checkpoint must contain the decision head and LoRA adapter")
        config = benchmark.strict_json((checkpoint / "model.json").read_bytes())
        if type(config.get("lora_rank")) is not int or config["lora_rank"] <= 0:
            raise ValueError("The suite requires trained LoRA checkpoints")
        expected = checkpoint_identity(checkpoint, tag, commit, max_length=args.max_length)
        benchmark.validate_identity_config(expected)
        identities[tag] = expected
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "running", "started_at_utc": now(), "scope": benchmark.SCOPE,
                "allocation": allocation, "code_commit": commit, "upstream_commit": upstream_commit,
                "source_sha256": benchmark.sha256(Path(__file__).read_bytes()),
                "input_sha256": args.input_sha256, "model_order": list(checkpoints), "models": {},
                "batch_size": args.batch_size, "max_length": args.max_length, "port": args.port,
                "prefix_cache": False, "inference_identity_probe_requests": 0,
                "identity_verification": "Owned-child readiness and health; all seven checkpoint fields checked on every collected response.",
                "startup_timeout": args.startup_timeout, "collection_timeout": args.collection_timeout,
                "request_timeout": args.request_timeout}

    def save():
        manifest["updated_at_utc"] = now()
        temporary = output / "manifest.json.tmp"
        temporary.write_bytes(benchmark.json_bytes(manifest))
        temporary.replace(output / "manifest.json")

    error = None
    server = None
    save()
    try:
        for tag, checkpoint in checkpoints.items():
            directory = output / tag
            directory.mkdir()
            identity = identities[tag]
            identity_path = directory / "identity.json"
            identity_path.write_bytes(benchmark.json_bytes(identity))
            model = {"expected_identity": identity, "checkpoint": str(checkpoint), "collection": {}}
            manifest["models"][tag] = model
            save()
            if allocation["mode"] == "n1_explicit":
                model["gpu_preflight"] = require_free_gpu(args.physical_gpu, release_wait=30)
                if model["gpu_preflight"]["uuid"] != allocation["cuda_visible_devices"]:
                    raise RuntimeError("Physical GPU identity changed")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", args.port))
            server_command = [sys.executable, "-m", "jev.server", "--checkpoint", str(checkpoint),
                              "--device", "cuda:0", "--host", "127.0.0.1", "--port", str(args.port),
                              "--max-length", str(args.max_length), "--batch-size", str(args.batch_size),
                              "--no-prefix-cache"]
            server_log = directory / "server.log"
            with server_log.open("x") as log:
                try:
                    server = subprocess.Popen(server_command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                    model.update(server_pid=server.pid, server_command=server_command)
                    save()
                    model["health"] = wait_ready(server, server_log, identity, args.port, args.startup_timeout)
                    if allocation["mode"] == "n1_explicit":
                        model["gpu_loaded"] = gpu_snapshot(args.physical_gpu)
                        if (model["gpu_loaded"]["uuid"] != allocation["cuda_visible_devices"]
                                or {row["pid"] for row in model["gpu_loaded"]["compute_processes"]} != {server.pid}):
                            raise RuntimeError("Selected GPU is not exclusively occupied by the owned server")
                    command = [sys.executable, "-m", "scripts.jevbench_openjev", "collect",
                               "--requests", str(args.requests.resolve()), "--input-sha256", args.input_sha256,
                               "--endpoint", f"http://127.0.0.1:{args.port}/v1/systemone",
                               "--identity", str(identity_path), "--output", str(directory / "collection"),
                               "--timeout", str(args.request_timeout), "--max-seconds", str(args.collection_timeout)]
                    exit_code = run_collection(server, command, directory / "collection.log", env,
                                               args.collection_timeout, model["collection"], save)
                    collected = benchmark.strict_json((directory / "collection/report.json").read_bytes())
                    model["collection_status"] = collected["status"]
                    if (collected["expected_identity"] != identity or collected["input_sha256"] != args.input_sha256
                            or collected["planned_requests"] != 231 or collected["in_flight_requests"] != 0):
                        raise ValueError("Collection report identity or dispatch accounting differs")
                    if exit_code not in (0, 1) or collected["status"] not in ("complete", "complete_with_request_failures"):
                        raise RuntimeError("Collection stopped; partial evidence retained before cleanup")
                finally:
                    model["server_exit_code"] = stop_child(server)
                    model["server_stopped_at_utc"] = now()
                    server = None
                    save()
        manifest["status"] = ("complete_with_request_failures" if any(
            model["collection_status"] != "complete" for model in manifest["models"].values()) else "complete")
    except BaseException as caught:
        error = caught
        manifest.update(status="interrupted" if isinstance(caught, KeyboardInterrupt) else "failed",
                        error_type=type(caught).__name__, error=str(caught))
    finally:
        try:
            stop_child(server)
        except BaseException as caught:
            error = error or caught
            manifest.update(status="failed", cleanup_error=type(caught).__name__)
        manifest["server_cleanup_confirmed"] = server is None or server.poll() is not None
        # Only now read source gold. A timed-out or interrupted collection still
        # receives a partial aggregate when its durable evidence is readable.
        for tag, model in manifest["models"].items():
            directory = output / tag
            if not manifest["server_cleanup_confirmed"]:
                model["summary_deferred"] = "Owned server cleanup could not be confirmed"
                continue
            if not (directory / "collection/report.json").exists():
                continue
            try:
                aggregate = benchmark.summarize(args.upstream, directory / "collection")
                if model.get("collection_status") in ("complete", "complete_with_request_failures") and not aggregate["complete"]:
                    raise ValueError("Completed collection produced an incomplete verified aggregate")
                with (directory / "summary.json").open("xb") as stream:
                    stream.write(benchmark.json_bytes(aggregate))
                model["summary"] = {key: aggregate[key] for key in (
                    "n_planned", "n_attempted", "n_correct", "accuracy", "complete", "failed_requests", "pending_requests")}
            except BaseException as caught:
                error = error or caught
                model["summary_error"] = type(caught).__name__ + ": " + str(caught)
                manifest["status"] = "failed"
        manifest["finished_at_utc"] = now()
        save()
    if error is not None:
        raise error
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("requests", "upstream", "output-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    for tag in ("2b", "9b", "27b"):
        parser.add_argument("--checkpoint-" + tag, type=Path)
    parser.add_argument("--input-sha256", default=PUBLIC_REQUESTS_SHA256)
    parser.add_argument("--max-length", type=int, default=16384)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--port", type=int, default=8791)
    parser.add_argument("--startup-timeout", type=float, default=900)
    parser.add_argument("--collection-timeout", type=float, default=3600)
    parser.add_argument("--request-timeout", type=float, default=120)
    parser.add_argument("--expected-host", help="Explicit N1 mode: kwade5342000001")
    parser.add_argument("--physical-gpu", type=int, help="Explicit N1 mode: physical GPU 0 through 3")
    args = parser.parse_args(argv)
    if not any(getattr(args, "checkpoint_" + tag) for tag in ("2b", "9b", "27b")):
        parser.error("Supply at least one --checkpoint-2b/9b/27b")

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Received signal {signum}")

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        report = run_suite(args)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({"status": report["status"], "output": str(args.output_root)}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
