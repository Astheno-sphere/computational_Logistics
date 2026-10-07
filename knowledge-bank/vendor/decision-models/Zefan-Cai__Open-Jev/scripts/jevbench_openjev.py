"""Prepare, collect and score the pinned 231-task PUBLIC JevBench subset.

Collection reads only frozen state/questions, never gold. Run a local Open-Jev
server separately; this script does not load weights or allocate a GPU. Raw
requests and responses belong in an ignored/private run directory. Only the
aggregate produced by ``summarize`` is intended for public reporting.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import http.client
import importlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

from jev.api import compile_request
from jev.server import strict_json
from scripts.evaluate_openjev_provider import (
    IdentityError, digest, load_workloads, local_endpoint, validate_identity_config,
)


UPSTREAM_COMMIT = "f8ce71361165846101d02ebc83ad44e47ae44fc3"
PUBLIC_FILES = {
    "original": (72, "5c2414edb3006b8bfcb70fda433f0f9ca015759433849f8d3104328a1f7c4180"),
    "easy": (48, "231df3c2c8e88a1a8c137ebe85de96ba70fabd330849098ac7b3c52c70b7172b"),
    "hard": (111, "89e9e6becb33ed88c1de7d42dcc87531b2fb64cfaef4e1986faf7c37b3f80ebb"),
}
SCOPE = (
    "231 public JevBench tasks only: 72 original, 48 easy, 111 hard. "
    "The private and judge tiers are unavailable; this is not the full 534-task "
    "benchmark and no full-benchmark composite is computed. ZefanCai Open-Jev "
    "uses Qwen LoRA weights and a decision head; it is a different system from "
    "the Kotoba and Codiv projects also called OpenJev."
)


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def load_upstream(path):
    """Import scoring only from the exact clean source checkout, then hash data."""
    path = Path(path).resolve()
    commit = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True)
    if commit != UPSTREAM_COMMIT or dirty:
        raise ValueError("JevBench must be a clean checkout of the pinned commit")
    for name, module in list(sys.modules.items()):
        if name == "jevbench" or name.startswith("jevbench."):
            if not Path(module.__file__).resolve().is_relative_to(path):
                raise ValueError("A different JevBench source is already imported")
    sys.path.insert(0, str(path))
    try:
        modules = {name: importlib.import_module("jevbench." + name) for name in
                   ("tasks", "scoring", "summarize", "adapters.base")}
    finally:
        sys.path.pop(0)
    tiers, manifest = {}, {}
    for tier, (count, expected_hash) in PUBLIC_FILES.items():
        source = path / "datasets" / "public" / (tier + ".jsonl")
        if sha256(source.read_bytes()) != expected_hash:
            raise ValueError("Public JevBench source checksum differs")
        tasks = modules["tasks"].load_jsonl(str(source))
        if len(tasks) != count or any(task.split != "public" for task in tasks):
            raise ValueError("Public JevBench task count or split differs")
        tiers[tier] = tasks
        manifest[tier] = {"rows": count, "file_sha256": expected_hash,
                          "canonical_sha256": modules["tasks"].dataset_hash(tasks),
                          "kinds": dict(Counter(task.question["type"] for task in tasks)),
                          "families": dict(Counter(task.family for task in tasks))}
    tasks = [task for group in tiers.values() for task in group]
    if len({task.id for task in tasks}) != len(tasks):
        raise ValueError("Duplicate JevBench task IDs")
    return SimpleNamespace(tiers=tiers, tasks=tasks, manifest=manifest,
                           task_module=modules["tasks"], scoring=modules["scoring"],
                           summary=modules["summarize"], base=modules["adapters.base"])


def request_document(upstream):
    workloads = []
    for task in upstream.tasks:
        request = {"state": task.state, "questions": {"decision": upstream.base.build_question(task)}}
        record, = compile_request(request["state"], request["questions"])
        labels = ["no", "yes"] if record["kind"] == "noul" else record["answer_keys"]
        if set(labels) != set(task.labels):
            raise ValueError("Compiled candidate coverage differs from the upstream labels")
        # Upstream serializes some criteria maps in a different order from its
        # labels list. Preserve the exact native request order, as its own
        # TypeSafe adapter does; scoring uses an exact set and lexical ties.
        workloads.append({"id": task.id, "request": request, "request_sha256": digest(request)})
    return {"schema_version": 1, "workloads": workloads}


def prepare(upstream_path, output):
    upstream = load_upstream(upstream_path)
    raw = json_bytes(request_document(upstream))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "requests.json").write_bytes(raw)
    manifest = {"upstream_url": "https://github.com/fstandhartinger/jevbench",
                "upstream_commit": UPSTREAM_COMMIT, "scope": SCOPE,
                "public_files": upstream.manifest, "requests_sha256": sha256(raw),
                "dataset_hash": upstream.task_module.dataset_hash(upstream.tasks),
                "planned_requests": len(upstream.tasks), "gold_in_requests": False,
                "license_note": "Upstream THIRD-PARTY.md grants MIT to the harness and 72 original public decisions only. Keep all prepared inputs/raw responses private; do not assume the remaining dataset is MIT."}
    (output / "manifest.json").write_bytes(json_bytes(manifest))
    return manifest


def native_probs(request, response, expected, prefix_cache=False):
    """Bind checkpoint identity; leave distribution rounding to JevBench scoring."""
    if not isinstance(response, dict) or not isinstance(response.get("metadata"), dict):
        raise IdentityError("Missing Open-Jev identity metadata")
    metadata = response["metadata"]
    actual = {"model": response.get("model"),
              **{key: metadata.get(key) for key in expected if key != "model"}}
    if (actual != expected or type(metadata.get("max_length")) is not int
            or type(metadata.get("temperature")) not in (int, float)
            or not isinstance(metadata.get("prefix_cache"), dict)
            or metadata["prefix_cache"].get("enabled") is not prefix_cache):
        # A run declares its prefix-cache setting up front (default: off, the
        # upstream protocol); every response must match it exactly.
        raise IdentityError("Open-Jev identity differs or prefix caching differs from the run setting")
    if not isinstance(response.get("answers"), dict) or set(response["answers"]) != {"decision"}:
        raise ValueError("Expected one native decision answer")
    question = request["questions"]["decision"]
    answer = response["answers"]["decision"]
    if not isinstance(answer, dict) or answer.get("type") != question["type"]:
        raise ValueError("Native answer type differs")
    usage = response.get("usage", {})
    if not isinstance(usage, dict) or type(usage.get("input_tokens")) is not int or usage["input_tokens"] < 0:
        raise ValueError("Missing nonnegative integer token usage")
    if question["type"] == "noul":
        value = answer.get("noul")
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid native Noul probability")
        return {"no": 1 - value, "yes": value}
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict):
        raise ValueError("Missing native probability mapping")
    if question["type"] == "choice" and answer.get("choice") not in question["criteria"]:
        raise ValueError("Native choice is outside the candidate set")
    # Exact label coverage, finite values and the 0.001/0.02 sum tolerances
    # belong to upstream score_task. Never normalize or infer probabilities here.
    return probabilities


def attempt(workload, endpoint, expected, timeout, prefix_cache=False):
    parsed = local_endpoint(endpoint)
    sample = {"request_id": workload["id"], "request_sha256": workload["request_sha256"],
              "success": False, "model": expected["model"], "probs_source": "native",
              "started_at": datetime.now(timezone.utc).isoformat()}
    started = time.perf_counter()
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    try:
        payload = json.dumps({**workload["request"], "model": "open-jev"},
                             ensure_ascii=False, allow_nan=False).encode()
        connection.request("POST", parsed.path, payload, {"Content-Type": "application/json"})
        received = connection.getresponse()
        sample["http_status"] = received.status
        raw = received.read()
        sample["raw_response"] = raw.decode("utf-8", errors="replace")
        sample["raw_response_sha256"] = sha256(raw)
        if received.status != 200:
            sample["fatal"] = received.status not in (400, 413, 422)
            raise ValueError(f"HTTP {received.status}; not a successful inference")
        response = strict_json(raw)
        json.dumps(response, allow_nan=False)
        sample["response"] = response
        sample["probs_as_returned"] = native_probs(workload["request"], response, expected, prefix_cache)
        sample["success"] = True
    except (Exception, KeyboardInterrupt) as error:
        sample["error_type"], sample["error"] = type(error).__name__, str(error)
        if isinstance(error, (IdentityError, OSError, http.client.HTTPException, KeyboardInterrupt)):
            sample["fatal"] = True
    finally:
        sample["wall_ms"] = (time.perf_counter() - started) * 1000
        connection.close()
    return sample


def collect(requests, input_sha256, endpoint, expected, output, *, timeout=120, max_seconds=3600,
            prefix_cache=False, scope=SCOPE, upstream_commit=UPSTREAM_COMMIT):
    validate_identity_config(expected)
    if type(prefix_cache) is not bool:
        raise ValueError("prefix_cache must be a boolean")
    local_endpoint(endpoint)
    if (not math.isfinite(timeout) or not 0 < timeout <= 300
            or not math.isfinite(max_seconds) or not 0 < max_seconds <= 86400):
        raise ValueError("Invalid bounded time limits")
    workloads, raw = load_workloads(requests, input_sha256)
    if any(set(row["request"]["questions"]) != {"decision"} for row in workloads):
        raise ValueError("Expected one JevBench decision per request")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "requests.json").write_bytes(raw)
    report = {"schema_version": 1, "status": "running", "scope": scope,
              "upstream_commit": upstream_commit, "input_sha256": input_sha256,
              "source_sha256": sha256(Path(__file__).read_bytes()), "expected_identity": expected,
              "endpoint": endpoint, "planned_requests": len(workloads), "started_requests": 0,
              "attempted_requests": 0, "successful_requests": 0, "failed_requests": 0,
              "concurrency": 1, "warmups": 0, "retries": 0, "prefix_cache": prefix_cache,
              "transport": "http_loopback_fresh_connection",
              "latency_note": "One full-response wall time per task, including response validation. Model loading is outside the clock. These are heterogeneous quality-run diagnostics, not a repeated or matched-hardware latency benchmark.",
              "timeout_seconds": timeout, "max_seconds": max_seconds,
              "cost_usd": None, "cost_basis": "local_compute_unmetered_not_free"}
    started = time.monotonic()

    def save():
        report["elapsed_seconds"] = time.monotonic() - started
        report["pending_requests"] = len(workloads) - report["started_requests"]
        report["in_flight_requests"] = report["started_requests"] - report["attempted_requests"]
        temporary = output / "report.json.tmp"
        temporary.write_bytes(json_bytes(report))
        temporary.replace(output / "report.json")

    save()
    try:
        with (output / "samples.jsonl").open("x") as stream, (output / "attempts.jsonl").open("x") as journal:
            for workload in workloads:
                remaining = max_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    report["status"] = "stopped_time_limit"
                    break
                entry = {"request_id": workload["id"], "request_sha256": workload["request_sha256"],
                         "event": "attempt_started", "started_at": datetime.now(timezone.utc).isoformat()}
                journal.write(json.dumps(entry) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                report["started_requests"] += 1
                save()
                sample = attempt(workload, endpoint, expected, min(timeout, remaining), prefix_cache)
                stream.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                report["attempted_requests"] += 1
                report["successful_requests" if sample["success"] else "failed_requests"] += 1
                if sample.get("fatal"):
                    report["status"] = "stopped_fatal"
                    break
                save()
            if report["status"] == "running":
                report["status"] = "complete" if not report["failed_requests"] else "complete_with_request_failures"
    except BaseException as error:
        report["status"], report["error_type"] = "interrupted_or_failed", type(error).__name__
        raise
    finally:
        save()
    return report


def summarize(upstream_path, run_dir):
    upstream = load_upstream(upstream_path)
    run_dir = Path(run_dir)
    report = strict_json((run_dir / "report.json").read_bytes())
    expected = report["expected_identity"]
    validate_identity_config(expected)
    prefix_cache = report.get("prefix_cache", False) is True
    workloads, raw = load_workloads(run_dir / "requests.json", report["input_sha256"])
    if raw != json_bytes(request_document(upstream)) or report["upstream_commit"] != UPSTREAM_COMMIT:
        raise ValueError("Saved requests do not exactly match the pinned public subset")
    samples = [strict_json(line) for line in (run_dir / "samples.jsonl").read_bytes().splitlines()]
    journal = [strict_json(line) for line in (run_dir / "attempts.jsonl").read_bytes().splitlines()]
    ids = [row["id"] for row in workloads]
    if ([row["request_id"] for row in samples] != ids[:len(samples)]
            or [row["request_id"] for row in journal] != ids[:len(journal)]
            or not len(samples) <= len(journal) <= len(samples) + 1):
        raise ValueError("Records must be a unique attempted prefix, with at most one in-flight request")
    actual_counts = {"planned_requests": len(workloads), "started_requests": len(journal),
                     "attempted_requests": len(samples), "successful_requests": sum(row.get("success") is True for row in samples),
                     "failed_requests": sum(row.get("success") is False for row in samples),
                     "pending_requests": len(workloads) - len(journal),
                     "in_flight_requests": len(journal) - len(samples)}
    if report.get("planned_requests") != len(workloads):
        raise ValueError("Report planned count differs from frozen input")
    if report.get("status") in ("complete", "complete_with_request_failures"):
        if any(type(report.get(key)) is not int or report[key] != value for key, value in actual_counts.items()):
            raise ValueError("Completed report counts differ from durable evidence")
        if len(samples) != len(workloads) or actual_counts["in_flight_requests"]:
            raise ValueError("Completed report contains pending or in-flight requests")
        if (report["status"] == "complete") != (actual_counts["failed_requests"] == 0):
            raise ValueError("Completed report status disagrees with its failures")
    for row, workload in zip(journal, workloads):
        if row["event"] != "attempt_started" or row["request_sha256"] != workload["request_sha256"]:
            raise ValueError("Attempt journal differs from frozen input")
    if any(sample.get("fatal") and (index != len(samples) - 1 or len(journal) != len(samples))
           for index, sample in enumerate(samples)):
        raise ValueError("A request was dispatched after a fatal result")
    records = []
    for task, workload, sample in zip(upstream.tasks, workloads, samples):
        if (sample["request_sha256"] != workload["request_sha256"]
                or type(sample["success"]) is not bool or sample.get("probs_source") != "native"
                or sample.get("model") != expected["model"]):
            raise ValueError("Sample does not match the frozen task or model")
        ok = sample["success"]
        probs = None
        if ok:
            raw_response = sample["raw_response"].encode()
            response = strict_json(raw_response)
            if (sha256(raw_response) != sample["raw_response_sha256"]
                    or json_bytes(response) != json_bytes(sample["response"]) or sample["http_status"] != 200):
                raise ValueError("Saved response evidence differs")
            probs = native_probs(workload["request"], response, expected, prefix_cache)
            if json_bytes(probs) != json_bytes(sample["probs_as_returned"]):
                raise ValueError("Saved probabilities differ from the native response")
        scored = upstream.scoring.score_task(probs or {}, task)
        records.append({"task_id": task.id, "ok": ok, "model": expected["model"],
                        "probs_source": "native", "cost_usd": None,
                        "cost_basis": "local_compute_unmetered_not_free",
                        "latency_s": sample["wall_ms"] / 1000, **scored})
    aggregate = upstream.summary.public_export({}, upstream.tasks, records)
    aggregate.update(scope=SCOPE, upstream_commit=UPSTREAM_COMMIT,
                     accuracy_denominator="attempted_scorable_requests",
                     planned_accuracy=aggregate["n_correct"] / len(workloads),
                     dataset_hash=upstream.task_module.dataset_hash(upstream.tasks),
                     input_sha256=report["input_sha256"], expected_identity=expected,
                     started_requests=len(journal), pending_requests=len(workloads) - len(journal),
                     in_flight_requests=len(journal) - len(samples),
                     failed_requests=sum(not row["success"] for row in samples),
                     schema_invalid_requests=sum(not row["valid"] for row in records),
                     per_public_file={tier: upstream.summary.public_export({}, tasks, [
                         row for row in records if row["task_id"] in {task.id for task in tasks}])
                         for tier, tasks in upstream.tiers.items()},
                     protocol={"sum_tolerance_strict": upstream.scoring.SUM_TOL,
                               "sum_tolerance_rounding": upstream.scoring.RENORM_TOL,
                               "argmax_tie_break": "lexicographically_smallest_label",
                               "score_accuracy": "argmax_level_equals_gold_level",
                               "probabilities": "native", "concurrency": 1,
                               "retries": 0, "warmups": 0, "prefix_cache": prefix_cache,
                               "latency_note": report["latency_note"]})
    return aggregate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare")
    preparation.add_argument("--upstream", type=Path, required=True)
    preparation.add_argument("--output", type=Path, required=True)
    collection = commands.add_parser("collect")
    collection.add_argument("--requests", type=Path, required=True)
    collection.add_argument("--input-sha256", required=True)
    collection.add_argument("--endpoint", required=True)
    collection.add_argument("--identity", type=Path, required=True,
                            help="JSON containing the seven pinned Open-Jev identity fields")
    collection.add_argument("--output", type=Path, required=True)
    collection.add_argument("--timeout", type=float, default=120)
    collection.add_argument("--max-seconds", type=float, default=3600)
    collection.add_argument("--prefix-cache", action="store_true",
                            help="Expect a server started with --prefix-cache; recorded in the report so "
                                 "summarize replays with the same setting. Default: off (upstream protocol)")
    summary = commands.add_parser("summarize")
    summary.add_argument("--upstream", type=Path, required=True)
    summary.add_argument("--run-dir", type=Path, required=True)
    summary.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.upstream, args.output)
        print(json.dumps({key: result[key] for key in ("planned_requests", "requests_sha256")}))
    elif args.command == "collect":
        def interrupted(signum, _frame):
            raise KeyboardInterrupt(f"Received signal {signum}")
        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            result = collect(args.requests, args.input_sha256, args.endpoint,
                             strict_json(args.identity.read_bytes()), args.output,
                             timeout=args.timeout, max_seconds=args.max_seconds,
                             prefix_cache=args.prefix_cache)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        print(json.dumps({key: result[key] for key in (
            "status", "planned_requests", "attempted_requests", "failed_requests", "pending_requests")}))
        return 0 if result["status"] == "complete" else 1
    else:
        result = summarize(args.upstream, args.run_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as stream:
            stream.write(json_bytes(result))
        print(json.dumps({key: result[key] for key in ("n_planned", "n_attempted", "n_correct", "accuracy")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
