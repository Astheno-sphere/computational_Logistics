"""Run the three checkpoint evaluation suites serially on one authorized GPU.

This launcher never connects to another host or stops unrelated processes.
Only child processes created here are terminated. Existing outputs are refused.
"""

import argparse
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
MODELS = {"2b": "Qwen/Qwen3.5-2B", "9b": "Qwen/Qwen3.5-9B", "27b": "Qwen/Qwen3.8-27B"}
BASE = "http://127.0.0.1:8791"
ENDPOINT = BASE + "/v1/systemone"
METHOD = "lora_decision_head"
MEASUREMENTS = ("demo_requests", "workflows", "frontier_100", "games")
PROVIDER_SUITES = (
    ("coverage", "provider-comparison-v1", 189, 146, "f03b181d6470732dea6818df75c18ee80cb9401281bfe4fad410ed0829bac727"),
    ("jf100", "provider-comparison-jf100-v1", 300, 300, "03b5c41c198e04614a0add36c717c326570ed7b2982be0515fb7dca65efbb2ca"),
    ("ir-pilot", "provider-ir-pilot-v1", 132, 174, "519da8ff5432093fa88d79aaa9a101529f66692c6393a8e8f2e8996eeab279f3"),
    ("fizzbuzz", "provider-fizzbuzz-control-v1", 100, 300, "92809c48f5cfd0d8db9f764233be38f9902c15036cbf5be57f050cdbc5c458a0"),
    ("mailroom", "provider-mailroom-probe-v1", 87, 921, "25d00d67e4e31ec791d3ae1c67f69bbd15a0c778ca7c8746b7a8838506b63df3"),
)


def now():
    return datetime.now(timezone.utc).isoformat()


def enforce_resource_policy(gpu, expected_hostname):
    path = ROOT / "state/auto_research/resource_policy.json"
    raw = path.read_bytes()
    policy = json.loads(raw)
    if not isinstance(policy, dict):
        raise ValueError("resource policy must be a JSON object")
    hostname = socket.gethostname()
    required_host = policy.get("expected_hostname")
    if not isinstance(required_host, str) or not required_host or hostname != required_host or expected_hostname != required_host:
        raise ValueError(f"resource policy requires host {required_host!r}; actual host is {hostname!r}; --expected-hostname cannot override the policy")
    allowed = policy.get("allowed_gpu_indices")
    training = policy.get("training_gpu_indices")
    if any(not isinstance(indices, list) or not indices or
           any(type(index) is not int or index < 0 for index in indices)
           for indices in (allowed, training)):
        raise ValueError("resource policy requires allowed and training GPU index lists")
    if (type(policy.get("serial_evaluation_gpu_index")) is not int or
            gpu != policy["serial_evaluation_gpu_index"] or gpu not in allowed or gpu in training or
            not set(training) <= set(allowed)):
        raise ValueError("requested evaluation GPU violates the repository resource policy")
    if hostname in policy.get("prohibited_nodes", []):
        raise ValueError("resource policy prohibits this host")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(),
            "expected_hostname": required_host, "allowed_gpu_indices": allowed,
            "training_gpu_indices": training, "serial_evaluation_gpu_index": gpu}


def gpu_snapshot(gpu):
    command = ["nvidia-smi", "--id", str(gpu), "--query-gpu=uuid,name,memory.used,utilization.gpu", "--format=csv,noheader,nounits"]
    rows = list(csv.reader(subprocess.check_output(command, text=True, timeout=15).strip().splitlines()))
    if len(rows) != 1 or len(rows[0]) != 4:
        raise RuntimeError("nvidia-smi did not identify exactly one GPU")
    uuid, name, memory, utilization = (value.strip() for value in rows[0])
    processes = []
    text = subprocess.check_output(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory", "--format=csv,noheader,nounits"], text=True, timeout=15)
    for row in csv.reader(text.strip().splitlines()):
        if len(row) != 4:
            raise RuntimeError("nvidia-smi returned an unexpected process row")
        if row[0].strip() == uuid:
            processes.append({"pid": int(row[1]), "name": row[2].strip(), "memory_mib": row[3].strip()})
    return {"physical_gpu": gpu, "uuid": uuid, "name": name, "memory_used_mib": float(memory),
            "utilization_percent": float(utilization), "compute_processes": processes}


def require_free_gpu(gpu, *, release_wait=0):
    deadline = time.monotonic() + release_wait
    while True:
        snapshot = gpu_snapshot(gpu)
        if not snapshot["compute_processes"] and snapshot["memory_used_mib"] <= 512 and snapshot["utilization_percent"] <= 5:
            return snapshot
        if time.monotonic() >= deadline:
            raise RuntimeError("evaluation GPU is occupied; no process was stopped: " + json.dumps(snapshot))
        time.sleep(1)


def require_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", 8791))


def checkpoint_identity(path, tag, commit, *, max_length=4096):
    config = json.loads((path / "model.json").read_text())
    if config["model_id"] != MODELS[tag]:
        raise ValueError(f"{tag} checkpoint contains the wrong base model")
    temperature = json.loads((path / "temperature.json").read_text())["temperature"]
    if type(temperature) not in (int, float) or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("checkpoint temperature must be finite and positive")
    digest = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            digest.update(str(file.relative_to(path)).encode() + b"\0")
            with file.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
    return {"model": config["model_id"], "method": METHOD, "checkpoint_sha256": digest.hexdigest(),
            "base_revision": config["revision"], "temperature": temperature,
            "code_commit": commit, "max_length": max_length}


def stop_child(process):
    """Reap this exact Popen child; never signal a discovered or unrelated PID."""
    if process is None:
        return None
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
    return process.wait(timeout=20)


def ready_line(log_path, model):
    with log_path.open("rb") as stream:
        stream.seek(max(0, log_path.stat().st_size - 65536))
        lines = stream.read().decode(errors="replace").splitlines()
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("url") == BASE and row.get("model") == model and row.get("method") == METHOD:
            return True
    return False


def wait_ready(process, log_path, expected, timeout):
    deadline = time.monotonic() + timeout
    last_error = "waiting for this child server's readiness log"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"server exited {process.returncode}; inspect {log_path}")
        # A matching health endpoint alone could belong to someone else's server.
        if ready_line(log_path, expected["model"]):
            try:
                with urlopen(BASE + "/health", timeout=5) as response:
                    health = json.load(response)
                if health.get("status") != "ready" or health.get("model") != expected["model"] or health.get("method") != expected["method"]:
                    raise RuntimeError("health model/method identity differs")
                return health
            except (OSError, ValueError) as error:
                last_error = str(error)
        time.sleep(1)
    raise TimeoutError(f"server startup exceeded {timeout}s: {last_error}; inspect {log_path}")


def probe_identity(process, expected):
    if process.poll() is not None:
        raise RuntimeError("own server is no longer running")
    payload = {"model": "open-jev", "state": "The lamp is on.", "questions": {
        "identity_probe": {"type": "noul", "instructions": "Does the state say the lamp is on?"}}}
    request = Request(ENDPOINT, json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=120) as response:
        result = json.load(response)
    metadata = result.get("metadata", {})
    actual = {"model": result.get("model"), **{key: metadata.get(key) for key in expected if key != "model"}}
    if actual != expected:
        raise RuntimeError("loaded service identity does not match the checkpoint: " + json.dumps(actual))
    if set(result.get("answers", {})) != {"identity_probe"} or result["answers"]["identity_probe"].get("type") != "noul":
        raise RuntimeError("identity probe did not return the requested Noul")
    probability = result["answers"]["identity_probe"].get("noul")
    if type(probability) not in (int, float) or not math.isfinite(probability) or not 0 <= probability <= 1:
        raise RuntimeError("identity probe did not return a finite Noul in [0, 1]")
    return result


def preflight_control_inputs(args):
    """Validate selected frozen controls on CPU, before acquiring a GPU lease."""
    evidence = {}
    if "contact" in args.measurements:
        from scripts.evaluate_contact_service import load_cases, phone_library
        phone_library()
        cases, inputs = load_cases(args.control_data_root, ("email", "phone"), ("test", "ood"))
        evidence["contact"] = {"selected_cases": len(cases), "inputs": inputs}
    if "amount" in args.measurements:
        from scripts.evaluate_amount_service import load_cases
        cases, inputs = load_cases(args.control_data_root, ("test", "ood"))
        evidence["amount"] = {"selected_cases": len(cases), "inputs": inputs}
    return evidence


def preflight_provider_inputs(args):
    """Bind the original five suites without reading model answers or using a GPU."""
    if "provider_quality" not in args.measurements:
        return {}
    from jev.api import compile_request
    from scripts.benchmark_inference_latency import digest

    evidence = {}
    for name, directory, request_count, gold_count, manifest_sha256 in PROVIDER_SUITES:
        root = args.provider_data_root / directory
        manifest_raw = (root / "manifest.json").read_bytes()
        if hashlib.sha256(manifest_raw).hexdigest() != manifest_sha256:
            raise ValueError(f"{name}: frozen provider manifest differs")
        manifest = json.loads(manifest_raw)
        files, documents = {}, {}
        for filename in ("requests.json", "gold.json"):
            raw = (root / filename).read_bytes()
            expected = manifest["files"][filename]
            expected = expected["sha256"] if isinstance(expected, dict) else expected
            actual = hashlib.sha256(raw).hexdigest()
            if actual != expected:
                raise ValueError(f"{name}: frozen {filename} differs")
            files[filename] = {"sha256": actual, "bytes": len(raw)}
            documents[filename] = json.loads(raw)
        workloads, golds = documents["requests.json"]["workloads"], documents["gold.json"]["rows"]
        if len(workloads) != request_count or len(golds) != gold_count:
            raise ValueError(f"{name}: frozen provider counts differ")
        by_id, questions = {}, {}
        for workload in workloads:
            identifier, request = workload["id"], workload["request"]
            if identifier in by_id or workload["request_sha256"] != digest(request):
                raise ValueError(f"{name}: duplicate request or changed request hash")
            by_id[identifier] = workload
            questions[identifier] = {row["id"]: row for row in compile_request(request["state"], request["questions"])}
        identities = set()
        for gold in golds:
            identifier, question = gold["request_id"], gold.get("question_id", "decision")
            if ((identifier, question) in identities or identifier not in by_id or
                    gold["request_sha256"] != by_id[identifier]["request_sha256"] or
                    question not in questions[identifier]):
                raise ValueError(f"{name}: duplicate or unbound gold question")
            identities.add((identifier, question))
            compiled = questions[identifier][question]
            if gold["kind"] != compiled["kind"] or gold["answer_keys"] != compiled["answer_keys"]:
                raise ValueError(f"{name}: gold kind or candidate order differs")
        evidence[name] = {"directory": str(root), "manifest_sha256": manifest_sha256,
                          "requests": request_count, "labelled_decisions": gold_count, "files": files}
    return evidence


def preflight_trec_inputs(args):
    """Bind the complete isolated TREC inputs on CPU; qrels never reach the client."""
    if "trec" not in args.measurements:
        return {}
    from jev.ir_eval import load_external_holdout
    from scripts.evaluate_trec_provider import load_input
    from scripts.summarize_trec_provider import INPUT_SHA256, MANIFEST_SHA256

    if args.trec_input is None:
        raise ValueError("--trec-input is required when trec is selected")
    paths = [args.trec_input, args.trec_holdout_root]
    if getattr(args, "output_root", None) is not None:
        paths.append(args.output_root)
    for benchmark in MANIFEST_SHA256:
        paths.extend(args.trec_holdout_root / benchmark / name
                     for name in ("manifest.json", "candidates.jsonl", "qrels.txt"))
    if any(Path(path).resolve().is_relative_to((ROOT / name).resolve())
           for path in paths for name in ("data", "train")):
        raise ValueError("TREC inputs, qrels and outputs must remain outside data/train")
    document, raw = load_input(args.trec_input, INPUT_SHA256)
    holdouts = {}
    for benchmark, count in (("dl19", 43), ("dl20", 54)):
        path = args.trec_holdout_root / benchmark / "manifest.json"
        if hashlib.sha256(path.read_bytes()).hexdigest() != MANIFEST_SHA256[benchmark]:
            raise ValueError("Frozen TREC external manifest differs")
        holdout = load_external_holdout(path)
        prepared = {query["id"]: query for query in document["queries"] if query["benchmark"] == benchmark}
        if (holdout["manifest"]["benchmark"] != "TREC-" + benchmark.upper() or len(prepared) != count or
                set(prepared) != set(holdout["queries"]) or set(prepared) != set(holdout["qrels"])):
            raise ValueError("Full TREC query/qrel coverage differs")
        for identifier, query in prepared.items():
            if ([row["id"] for row in query["documents"]] !=
                    [row["id"] for row in holdout["queries"][identifier]["documents"]]):
                raise ValueError("TREC candidate IDs or BM25 order differ")
        holdouts[benchmark] = {"manifest": str(path), "manifest_sha256": MANIFEST_SHA256[benchmark],
                              "files_sha256": holdout["manifest"]["files_sha256"], "queries": count}
    return {"input": str(args.trec_input), "input_sha256": INPUT_SHA256, "input_bytes": len(raw),
            "queries": len(document["queries"]), "planned_max_requests": 873, "holdouts": holdouts}


def measurement_commands(args, output, model, checkpoint, *, identity=None, provider_inputs=None, trec_inputs=None):
    common = ["--endpoint", ENDPOINT, "--expected-model", model, "--expected-method", METHOD]
    games = [sys.executable, "-m", "scripts.evaluate_game_service", *common,
             "--seeds", "10001,10002,10003", "--max-steps", "40", "--output-dir", str(output / "games")]
    if args.include_doom:
        games.extend(["--include-doom", "--doom-decision-mode", getattr(args, "doom_decision_mode", "combined-v1")])
    commands = [
        ("demo_requests", [sys.executable, "-m", "scripts.check_demo_requests", "--endpoint", ENDPOINT,
                           "--output", str(output / "demo_requests.jsonl")]),
        ("workflows", [sys.executable, "-m", "scripts.evaluate_workflow_service", *common,
                       "--cases", str(args.workflow_cases), "--split", "test", "ood", "--per-workflow", "12",
                       "--checkpoint-id", str(checkpoint), "--output-dir", str(output / "workflows")]),
        ("frontier_100", [sys.executable, "-m", "jev.eval_frontier", *common,
                          "--source", str(args.frontier_source), "--output-dir", str(output / "frontier")]),
        ("games", games),
    ]
    for task in ("browser", "drone"):
        if task not in args.measurements:
            continue
        commands.append((task, [sys.executable, "-m", f"scripts.evaluate_{task}_service", *common,
                         "--cases", str(getattr(args, f"{task}_cases")), "--split", "test", "ood",
                         "--parents-per-split", "20", "--variants-per-parent", "3", "--seed", "42",
                         "--expected-revision", identity["base_revision"],
                         "--expected-checkpoint-sha256", identity["checkpoint_sha256"],
                         "--output-dir", str(output / task)]))
    for task in ("contact", "amount"):
        if task not in args.measurements:
            continue
        command = [sys.executable, "-m", f"scripts.evaluate_{task}_service", *common,
                   "--data-root", str(args.control_data_root), "--splits", "test", "ood",
                   "--expected-revision", identity["base_revision"],
                   "--expected-checkpoint-sha256", identity["checkpoint_sha256"],
                   "--expected-temperature", str(identity["temperature"]),
                   "--output-dir", str(output / task)]
        if task == "contact":
            command.extend(["--corpora", "email", "phone"])
        commands.append((task, command))
    if "provider_quality" in args.measurements:
        for name, _, _, _, _ in PROVIDER_SUITES:
            frozen = provider_inputs[name]
            commands.append(("provider_quality_" + name, [sys.executable, "-m", "scripts.evaluate_openjev_provider", *common,
                             "--requests", str(Path(frozen["directory"]) / "requests.json"),
                             "--input-sha256", frozen["files"]["requests.json"]["sha256"],
                             "--expected-base-revision", identity["base_revision"],
                             "--expected-checkpoint-sha256", identity["checkpoint_sha256"],
                             "--expected-temperature", str(identity["temperature"]),
                             "--expected-code-commit", identity["code_commit"],
                             "--expected-max-length", str(identity["max_length"]),
                             "--output", str(output / "provider_quality" / name)]))
    if "trec" in args.measurements:
        commands.append(("trec", [sys.executable, "-m", "scripts.evaluate_openjev_trec", *common,
                         "--input", trec_inputs["input"], "--input-sha256", trec_inputs["input_sha256"],
                         "--expected-base-revision", identity["base_revision"],
                         "--expected-checkpoint-sha256", identity["checkpoint_sha256"],
                         "--expected-temperature", str(identity["temperature"]),
                         "--expected-code-commit", identity["code_commit"],
                         "--expected-max-length", str(identity["max_length"]),
                         "--output", str(output / "trec")]))
    return [(phase, command) for phase, command in commands
            if phase in args.measurements or ("provider_quality" in args.measurements and phase.startswith("provider_quality_"))]


def summarize_provider_output(output, frozen, expected):
    """Score retained responses locally; the inference client never receives gold."""
    from scripts import evaluate_openjev_provider as client
    from scripts.summarize_provider_quality import summarize

    gold_raw = (Path(frozen["directory"]) / "gold.json").read_bytes()
    if hashlib.sha256(gold_raw).hexdigest() != frozen["files"]["gold.json"]["sha256"]:
        raise ValueError("Frozen provider gold changed after preflight")
    workloads, _ = client.load_workloads(output / "requests.json", frozen["files"]["requests.json"]["sha256"])
    report_raw = (output / "report.json").read_bytes()
    report = json.loads(report_raw)
    samples_raw = (output / "samples.jsonl").read_bytes()
    samples = [json.loads(line) for line in samples_raw.splitlines() if line.strip()]
    attempts_raw = (output / "attempts.jsonl").read_bytes()
    attempts = [json.loads(line) for line in attempts_raw.splitlines() if line.strip()]
    if (len(attempts) != len(samples) or report["started_requests"] != len(samples) or report["in_flight_requests"] != 0 or
            any(attempt.get("event") != "attempt_started" or
                attempt.get("request_id") != sample["request_id"] or
                attempt.get("request_sha256") != sample["request_sha256"]
                for attempt, sample in zip(attempts, samples))):
        raise ValueError("Provider dispatch journal has an unmatched or changed attempt; do not score or retry")
    if (report["expected_identity"] != expected or report["input_sha256"] != frozen["files"]["requests.json"]["sha256"] or
            report["planned_requests"] != len(workloads) or report["attempted_requests"] != len(samples) or
            report["pending_requests"] != len(workloads) - len(samples) or len(samples) > len(workloads) or
            report["source_sha256"] != hashlib.sha256(Path(client.__file__).read_bytes()).hexdigest() or
            any(report[key] != value for key, value in (("concurrency", 1), ("warmups", 0), ("retries", 0), ("prefix_cache", False)))):
        raise ValueError("Provider collection identity, counts or protocol differ")
    for workload, sample in zip(workloads, samples):
        if (sample["request_id"] != workload["id"] or sample["request_sha256"] != workload["request_sha256"] or
                sample["mode"] != expected["model"] or sample["phase"] != "measured" or sample["repetition"] != 0 or
                type(sample["success"]) is not bool):
            raise ValueError("Provider sample identity or order differs")
        if sample["success"]:
            response = client.strict_json(sample["raw_response"])
            if (sample["http_status"] != 200 or
                    json.dumps(response, ensure_ascii=False, separators=(",", ":"), allow_nan=False) !=
                    json.dumps(sample["response"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)):
                raise ValueError("Provider raw response differs")
            client.validate_response(workload["request"], response, expected)
    successful = sum(sample["success"] for sample in samples)
    if report["successful_requests"] != successful or report["failed_requests"] != len(samples) - successful:
        raise ValueError("Provider success counts differ")
    complete = report["status"] in ("complete", "complete_with_request_failures")
    if complete and (len(samples) != len(workloads) or any(sample.get("fatal") for sample in samples)):
        raise ValueError("Provider completion has missing or fatal requests")
    if complete and (report["status"] == "complete") != (successful == len(samples)):
        raise ValueError("Provider completion status differs from request failures")
    quality = summarize(json.loads(gold_raw)["rows"], samples)
    quality.update(provider=expected["model"], expected_identity=expected, collection_status=report["status"],
                   gold_sha256=hashlib.sha256(gold_raw).hexdigest(), samples_sha256=hashlib.sha256(samples_raw).hexdigest(),
                   journal_sha256=hashlib.sha256(attempts_raw).hexdigest(),
                   collection_report_sha256=hashlib.sha256(report_raw).hexdigest(),
                   input_sha256=report["input_sha256"])
    path = output / "quality.json"
    raw = (json.dumps(quality, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
    return {"collection_status": report["status"], "quality_path": str(path),
            "quality_sha256": hashlib.sha256(raw).hexdigest(), "quality_status": quality["status"],
            "overall": quality["overall"], "pending_count": quality["pending_count"]}


def summarize_trec_output(output, frozen, expected):
    """Replay settled responses against isolated qrels, then write a new text-free summary."""
    from scripts.summarize_openjev_trec import summarize

    report_raw = (output / "report.json").read_bytes()
    report = json.loads(report_raw)
    if (report.get("status") not in ("complete", "completed_with_query_failures", "stopped_budget",
                                     "stopped_fatal", "interrupted_or_failed") or
            report.get("expected_identity") != expected or report.get("input_sha256") != frozen["input_sha256"] or
            type(report.get("in_flight_requests")) is not int or report["in_flight_requests"] != 0):
        raise ValueError("TREC collection is in-flight or its status/input/model identity differs")
    quality = summarize(output, {name: Path(row["manifest"]) for name, row in frozen["holdouts"].items()})
    if (quality["expected_identity"] != expected or quality["runner_status"] != report["status"] or
            quality["input_and_raw_sha256"]["report.json"] != hashlib.sha256(report_raw).hexdigest()):
        raise ValueError("TREC offline summary differs from the settled collection")
    path = output / "summary.json"
    raw = (json.dumps(quality, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
    return {"collection_status": report["status"], "quality_status": quality["status"],
            "summary_path": str(path), "summary_sha256": hashlib.sha256(raw).hexdigest(),
            "qrel_query_denominator": quality["qrel_query_denominator"], "benchmarks": quality["benchmarks"]}


def audit_demo_identities(path, expected):
    """The demo checker lacks identity flags, so verify all retained responses."""
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if "response" not in row:
            continue
        response = row["response"]
        metadata = response.get("metadata", {})
        actual = {"model": response.get("model"), **{key: metadata.get(key) for key in expected if key != "model"}}
        if actual != expected:
            raise RuntimeError("demo request returned a different model/checkpoint/method identity")


def run_measurement(command, log_path, env, timeout, *, record=None, update=None):
    start = time.monotonic()
    row = {} if record is None else record
    row.update(command=command, started_at_utc=now(), log=str(log_path))
    process = None
    try:
        with log_path.open("x") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            row["pid"] = process.pid
            if update:
                update()
            row["exit_code"] = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        row.update(exit_code=124, timeout=True)
    except BaseException as error:
        row.update(exit_code=130 if isinstance(error, KeyboardInterrupt) else 1,
                   error_type=type(error).__name__, error=str(error))
        raise
    finally:
        row["child_exit_code"] = stop_child(process)
        row.update(ended_at_utc=now(), elapsed_seconds=time.monotonic() - start)
        if update:
            update()
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-hostname", required=True)
    parser.add_argument("--gpu", type=int, default=3)
    parser.add_argument("--checkpoint-root", type=Path, default=Path("../runs"))
    parser.add_argument("--checkpoint-template", default="{tag}-pilot-v1/checkpoint")
    parser.add_argument("--models", nargs="+", choices=list(MODELS), default=list(MODELS),
                        help="Evaluate only these completed checkpoints, in the supplied order")
    parser.add_argument("--frontier-source", type=Path, default=Path("../evals/jev-frontier-100"))
    parser.add_argument("--workflow-cases", type=Path, default=Path("data/workflows-v1/workflow_cases.jsonl"))
    parser.add_argument("--browser-cases", type=Path, default=Path("data/browser-v1/cases.jsonl"))
    parser.add_argument("--drone-cases", type=Path, default=Path("data/drone-control-v1/cases.jsonl"))
    parser.add_argument("--control-data-root", type=Path, default=ROOT / "data",
                        help="Root of frozen email/phone/amount corpora; required only for selected controls")
    parser.add_argument("--provider-data-root", type=Path, default=ROOT / "data",
                        help="Root of the five original frozen provider suites; used only by provider_quality")
    parser.add_argument("--trec-input", type=Path,
                        help="Frozen input-only 97-query TREC file; required only by trec")
    parser.add_argument("--trec-holdout-root", type=Path, default=ROOT / "runs/external/ir-holdout/prepared",
                        help="Isolated frozen DL19/DL20 manifests and complete qrels for offline TREC scoring")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--measurements", nargs="+", choices=(*MEASUREMENTS, "browser", "drone", "contact", "amount", "provider_quality", "trec"), default=list(MEASUREMENTS),
                        help="Measurements in standard order; browser/drone, contact/amount, provider_quality and trec are opt-in")
    parser.add_argument("--include-doom", action="store_true")
    parser.add_argument("--doom-decision-mode", choices=("combined-v1", "typed-v1"), default="combined-v1",
                        help="Doom only: legacy combined action or the three training-aligned typed questions")
    parser.add_argument("--include-latency", action="store_true")
    parser.add_argument("--latency-request", type=Path, default=Path("examples/community/drone.json"))
    parser.add_argument("--max-length", type=int, default=4096,
                        help="Maximum encoded candidate length for checkpoint servers; never truncates")
    parser.add_argument("--batch-size", type=int, default=16,
                        help="Candidate sequences per checkpoint server batch")
    parser.add_argument("--startup-timeout", type=float, default=600)
    parser.add_argument("--measurement-timeout", type=float, default=3600)
    args = parser.parse_args(argv)
    if args.gpu != 3:
        parser.error("this allocation reserves only physical GPU 3 for evaluation; GPUs 0–2 train")
    if socket.gethostname() != args.expected_hostname:
        parser.error(f"host mismatch: actual {socket.gethostname()!r}; no GPU or process was touched")
    try:
        resource_policy = enforce_resource_policy(args.gpu, args.expected_hostname)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if any(not math.isfinite(value) or value <= 0 for value in (args.startup_timeout, args.measurement_timeout)):
        parser.error("timeouts must be finite and positive")
    if min(args.max_length, args.batch_size) < 1:
        parser.error("max-length and batch-size must be positive")
    if "trec" in args.measurements and args.max_length != 16384:
        parser.error("the frozen TREC follow-up requires --max-length 16384")
    if len(set(args.models)) != len(args.models):
        parser.error("models must be distinct")
    if "{tag}" not in args.checkpoint_template:
        parser.error("checkpoint-template must contain {tag}")
    for key in ("checkpoint_root", "frontier_source", "workflow_cases", "browser_cases", "drone_cases", "control_data_root", "provider_data_root", "trec_holdout_root", "output_root", "latency_request"):
        setattr(args, key, getattr(args, key).resolve())
    if args.trec_input is not None:
        args.trec_input = args.trec_input.resolve()
    if "workflows" in args.measurements and not args.workflow_cases.is_file():
        parser.error("workflow cases must exist when workflows are selected")
    if "browser" in args.measurements and not args.browser_cases.is_file():
        parser.error("browser cases must exist when browser is selected")
    if "drone" in args.measurements and not args.drone_cases.is_file():
        parser.error("drone cases must exist when drone is selected")
    if "frontier_100" in args.measurements and not args.frontier_source.is_dir():
        parser.error("external frozen Frontier checkout must exist when frontier_100 is selected")
    if "games" in args.measurements and args.include_doom and importlib.util.find_spec("vizdoom") is None:
        parser.error("--include-doom requires ViZDoom in this runtime; no substitute will be used")
    if args.include_latency and not args.latency_request.is_file():
        parser.error("latency request file does not exist")
    try:
        control_inputs = preflight_control_inputs(args)
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        parser.error(f"control preflight failed: {error}")
    try:
        provider_inputs = preflight_provider_inputs(args)
    except (ImportError, OSError, KeyError, TypeError, ValueError) as error:
        parser.error(f"provider preflight failed: {error}")
    try:
        trec_inputs = preflight_trec_inputs(args)
    except (ImportError, OSError, KeyError, TypeError, ValueError) as error:
        parser.error(f"TREC preflight failed: {error}")
    commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    args.output_root.mkdir(parents=True, exist_ok=False)
    manifest_path = args.output_root / "manifest.json"
    env = {**os.environ, "CUDA_DEVICE_ORDER": "PCI_BUS_ID",
           "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "PYTHONUNBUFFERED": "1",
           "PYTHONPATH": str(ROOT) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")}
    manifest = {"status": "starting", "created_at_utc": now(), "hostname": socket.gethostname(),
                "physical_gpu": args.gpu, "child_cuda_visible_devices": None,
                "resource_policy": resource_policy,
                "child_logical_device": "cuda:0", "port": 8791, "code_commit": commit,
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "configuration": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
                "models": {}, "current_phase": "preflight", "suite_pid": os.getpid()}
    if control_inputs:
        manifest["control_inputs"] = control_inputs
    if provider_inputs:
        manifest["provider_inputs"] = provider_inputs
    if trec_inputs:
        manifest["trec_inputs"] = trec_inputs

    def save():
        manifest["updated_at_utc"] = now()
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        temporary.replace(manifest_path)
        print(json.dumps({"status": manifest["status"], "phase": manifest["current_phase"]}), flush=True)

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    server = None
    save()
    # Cooperating suites cannot both pass an idle-card check and race to load it.
    with open(f"/tmp/open-jev-eval-gpu-{args.gpu}.lock", "a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock.seek(0)
            lock.truncate()
            lock.write(json.dumps({"pid": os.getpid(), "output": str(args.output_root)}))
            lock.flush()
            manifest["status"] = "running"
            for tag in args.models:
                model = MODELS[tag]
                output = args.output_root / tag
                output.mkdir()
                checkpoint = (args.checkpoint_root / args.checkpoint_template.format(tag=tag)).resolve()
                manifest["current_phase"] = f"{tag}/checkpoint_preflight"
                save()
                expected = checkpoint_identity(checkpoint, tag, commit, max_length=args.max_length)
                model_report = {"checkpoint": str(checkpoint), "expected_identity": expected, "measurements": {}}
                manifest["models"][tag] = model_report
                manifest["current_phase"] = f"{tag}/gpu_preflight"
                save()
                model_report["gpu_preflight"] = require_free_gpu(args.gpu, release_wait=30)
                # UUID avoids CUDA/nvidia-smi index ordering differences.
                env["CUDA_VISIBLE_DEVICES"] = model_report["gpu_preflight"]["uuid"]
                manifest["child_cuda_visible_devices"] = env["CUDA_VISIBLE_DEVICES"]
                model_report["cuda_visible_devices"] = env["CUDA_VISIBLE_DEVICES"]
                require_free_port()
                command = [sys.executable, "-m", "jev.server", "--checkpoint", str(checkpoint), "--device", "cuda:0",
                           "--host", "127.0.0.1", "--port", "8791", "--max-length", str(args.max_length),
                           "--batch-size", str(args.batch_size)]
                server_log = output / "server.log"
                with server_log.open("x") as log:
                    manifest["current_phase"] = f"{tag}/server_startup"
                    server = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                    model_report.update(server_pid=server.pid, server_command=command, server_log=str(server_log))
                    save()
                    try:
                        model_report["health"] = wait_ready(server, server_log, expected, args.startup_timeout)
                        allocated = gpu_snapshot(args.gpu)
                        if server.pid not in {row["pid"] for row in allocated["compute_processes"]}:
                            raise RuntimeError("own server was not observed on the selected physical GPU")
                        model_report["gpu_loaded"] = allocated
                        model_report["identity_probe"] = probe_identity(server, expected)
                        for phase, command in measurement_commands(args, output, model, checkpoint, identity=expected,
                                                                   provider_inputs=provider_inputs, trec_inputs=trec_inputs):
                            manifest["current_phase"] = f"{tag}/{phase}"
                            row = {}
                            model_report["measurements"][phase] = row
                            save()
                            run_measurement(command, output / f"{phase}.log", env, args.measurement_timeout,
                                            record=row, update=save)
                            if phase == "demo_requests" and (output / "demo_requests.jsonl").exists():
                                audit_demo_identities(output / "demo_requests.jsonl", expected)
                            if phase.startswith("provider_quality_"):
                                name = phase.removeprefix("provider_quality_")
                                row["quality"] = summarize_provider_output(output / "provider_quality" / name,
                                                                           provider_inputs[name], expected)
                                save()
                                if row["quality"]["collection_status"] not in ("complete", "complete_with_request_failures"):
                                    # A timed-out handler can still be computing: clean up without another probe/request.
                                    raise RuntimeError("Provider collection stopped; retained partial quality before server cleanup")
                            if phase == "trec":
                                row["quality"] = summarize_trec_output(output / "trec", trec_inputs, expected)
                                save()
                                if row["quality"]["collection_status"] not in ("complete", "completed_with_query_failures"):
                                    raise RuntimeError("TREC collection stopped; retained partial quality before server cleanup")
                            save()  # Save semantic/schema failures before checking service availability.
                            probe_identity(server, expected)
                    finally:
                        model_report["server_exit_code"] = stop_child(server)
                        model_report["server_stopped_at_utc"] = now()
                        server = None
                        save()
                model_report["gpu_after_shutdown"] = require_free_gpu(args.gpu, release_wait=30)
                save()
            if args.include_latency:
                manifest["current_phase"] = "latency/gpu_preflight"
                manifest["latency_gpu_preflight"] = require_free_gpu(args.gpu, release_wait=30)
                env["CUDA_VISIBLE_DEVICES"] = manifest["latency_gpu_preflight"]["uuid"]
                save()
                manifest["current_phase"] = "latency/no_training_vs_generation"
                save()
                command = [sys.executable, "-m", "scripts.benchmark_generation", "--request", str(args.latency_request),
                           "--device", "cuda:0", "--repeats", "3", "--output", str(args.output_root / "latency.json")]
                manifest["latency"] = {}
                run_measurement(command, args.output_root / "latency.log", env, args.measurement_timeout,
                                record=manifest["latency"], update=save)
                manifest["latency_gpu_after_shutdown"] = require_free_gpu(args.gpu, release_wait=30)
            failed = any(row["exit_code"] != 0 for model in manifest["models"].values() for row in model["measurements"].values())
            failed |= manifest.get("latency", {}).get("exit_code", 0) != 0
            manifest.update(status="complete_with_measurement_failures" if failed else "complete", current_phase="finished", ended_at_utc=now())
            save()
            return 1 if failed else 0
        except BaseException as error:
            manifest.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                            error_type=type(error).__name__, error=str(error), ended_at_utc=now())
            save()
            raise
        finally:
            stop_child(server)


if __name__ == "__main__":
    raise SystemExit(main())
