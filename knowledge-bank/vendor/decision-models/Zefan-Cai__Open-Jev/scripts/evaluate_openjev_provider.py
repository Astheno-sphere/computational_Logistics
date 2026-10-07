"""Collect one uncached Open-Jev response per frozen provider workload.

The caller owns the local server and GPU lease. This client never starts a
model, reads gold, retries a request, or changes a frozen input or old output.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import signal
import time
from urllib.parse import urlsplit

from jev.api import compile_request
from jev.server import strict_json
from scripts.benchmark_inference_latency import digest
from scripts.benchmark_jev_api_latency import validate as validate_probabilities


class IdentityError(ValueError):
    pass


def load_workloads(path, expected_sha256):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Frozen request file checksum differs")
    document = strict_json(raw)
    workloads = document["workloads"]
    if document.get("schema_version") != 1 or not isinstance(workloads, list) or not workloads:
        raise ValueError("Expected a nonempty schema-version-1 workload list")
    seen = set()
    for workload in workloads:
        identifier, request = workload["id"], workload["request"]
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("Workload IDs must be nonempty and unique")
        seen.add(identifier)
        if not isinstance(request, dict) or set(request) != {"state", "questions"}:
            raise ValueError("Inference input must contain only state and questions")
        if digest(request) != workload["request_sha256"]:
            raise ValueError("Saved request checksum differs")
        compile_request(request["state"], request["questions"])
    return workloads, raw


def validate_identity_config(expected):
    if (set(expected) != {"model", "method", "base_revision", "checkpoint_sha256",
                         "temperature", "code_commit", "max_length"}
            or expected["method"] != "lora_decision_head"
            or not isinstance(expected["model"], str) or not expected["model"]
            or any(not isinstance(expected[key], str) or re.fullmatch(pattern, expected[key]) is None
                   for key, pattern in (("base_revision", r"[0-9a-f]{40}"),
                                        ("code_commit", r"[0-9a-f]{40}"),
                                        ("checkpoint_sha256", r"[0-9a-f]{64}")))
            or type(expected["temperature"]) not in (int, float)
            or not math.isfinite(expected["temperature"]) or expected["temperature"] <= 0
            or type(expected["max_length"]) is not int or expected["max_length"] < 1):
        raise ValueError("A complete pinned Open-Jev identity is required")


def local_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or parsed.port is None
            or parsed.path not in ("/v1/systemone", "/v1/inference")):
        raise ValueError("Use the owned loopback HTTP server, with an explicit port")
    return parsed


def validate_response(request, response, expected):
    if not isinstance(response, dict) or not isinstance(response.get("metadata"), dict):
        raise IdentityError("Service response is missing its identity metadata")
    metadata = response.get("metadata", {})
    actual = {"model": response.get("model"),
              **{key: metadata.get(key) for key in expected if key != "model"}}
    if (actual != expected or type(metadata.get("max_length")) is not int
            or type(metadata.get("temperature")) not in (int, float)
            or not isinstance(metadata.get("prefix_cache"), dict)
            or metadata["prefix_cache"].get("enabled") is not False):
        raise IdentityError("Service identity differs or prefix caching is not disabled")
    validate_probabilities(request, response, expected["model"])
    if type(response["usage"]["input_tokens"]) is not int:
        raise ValueError("Token usage must be an integer")
    for record in compile_request(request["state"], request["questions"]):
        answer = response["answers"][record["id"]]
        if record["kind"] == "noul":
            continue
        values = answer["probabilities"]
        if list(values) != record["answer_keys"]:
            raise ValueError("Candidate order differs")
        if record["kind"] == "choice":
            if answer["choice"] != max(values, key=values.__getitem__):
                raise ValueError("Choice does not follow first-maximum tie breaking")
        else:
            score = answer.get("score")
            expectation = sum(i * values[key] for i, key in enumerate(record["answer_keys"]))
            if (type(score) not in (int, float) or not math.isfinite(score)
                    or not math.isclose(score, expectation, rel_tol=0, abs_tol=1e-8)):
                raise ValueError("Score differs from its probability expectation")


def attempt(workload, endpoint, expected, timeout):
    parsed = local_endpoint(endpoint)
    sample = {"request_id": workload["id"], "request_sha256": workload["request_sha256"],
              "mode": expected["model"], "phase": "measured", "repetition": 0,
              "transport": "http_loopback_fresh_connection", "success": False,
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
        sample["response_bytes"] = len(raw)
        if received.status != 200:
            sample["fatal"] = received.status not in (400, 413, 422)
            raise ValueError(f"HTTP {received.status}; not a successful inference")
        response = strict_json(raw)
        json.dumps(response, allow_nan=False)  # Reject overflow such as 1e999; retain exact raw bytes.
        sample["response"] = response
        validate_response(workload["request"], response, expected)
        sample["success"] = True
    except (Exception, KeyboardInterrupt) as error:
        sample["error_type"], sample["error"] = type(error).__name__, str(error)
        if isinstance(error, (IdentityError, OSError, http.client.HTTPException, KeyboardInterrupt)):
            # A timed-out/disconnected handler may still be computing. Stop here
            # and let the owning lifecycle shut its server down before any stage.
            sample["fatal"] = True
    finally:
        sample["wall_ms"] = (time.perf_counter() - started) * 1000
        connection.close()
    return sample


def run(requests, input_sha256, endpoint, expected, output, *, timeout=300,
        max_seconds=86400):
    validate_identity_config(expected)
    local_endpoint(endpoint)
    if (not math.isfinite(timeout) or not 0 < timeout <= 300
            or not math.isfinite(max_seconds) or not 0 < max_seconds <= 86400):
        raise ValueError("Invalid bounded time limits")
    workloads, raw = load_workloads(requests, input_sha256)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "requests.json").write_bytes(raw)
    report = {"schema_version": 1, "status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
              "expected_identity": expected, "endpoint": endpoint, "input_sha256": input_sha256,
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "planned_requests": len(workloads), "attempted_requests": 0, "successful_requests": 0,
              "failed_requests": 0, "pending_requests": len(workloads),
              "started_requests": 0, "in_flight_requests": 0, "attempt_journal": "attempts.jsonl",
              "concurrency": 1, "warmups": 0, "retries": 0, "prefix_cache": False,
              "timeout_seconds": timeout, "max_seconds": max_seconds,
              "scope": "Quality collection on identical frozen inputs; gold is never loaded. Full response wall times are diagnostic, not a repeated latency benchmark. Failed requests remain failed; unattempted requests remain pending. Raw bundles may contain restricted source material and must not be published wholesale."}
    started = time.monotonic()

    def save():
        report["elapsed_seconds"] = time.monotonic() - started
        report["pending_requests"] = len(workloads) - report["started_requests"]
        report["in_flight_requests"] = report["started_requests"] - report["attempted_requests"]
        temporary = output / "report.json.tmp"
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        temporary.replace(output / "report.json")

    save()
    try:
        with (output / "samples.jsonl").open("x") as stream, (output / "attempts.jsonl").open("x") as journal:
            for workload in workloads:
                remaining = max_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    report["status"] = "stopped_budget"
                    break
                # The journal also survives an uncatchable kill. A dangling
                # dispatch is an unknown outcome, never an unattempted request.
                entry = {"event": "attempt_started", "request_id": workload["id"],
                         "request_sha256": workload["request_sha256"],
                         "started_at": datetime.now(timezone.utc).isoformat()}
                journal.write(json.dumps(entry) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                report["started_requests"] += 1
                save()
                sample = attempt(workload, endpoint, expected, min(timeout, remaining))
                stream.write(json.dumps(sample, ensure_ascii=False, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                report["attempted_requests"] += 1
                report["successful_requests" if sample["success"] else "failed_requests"] += 1
                if sample.get("fatal"):
                    report["status"] = "stopped_fatal"
                    save()
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--expected-method", required=True)
    parser.add_argument("--expected-base-revision", required=True)
    parser.add_argument("--expected-checkpoint-sha256", required=True)
    parser.add_argument("--expected-temperature", type=float, required=True)
    parser.add_argument("--expected-code-commit", required=True)
    parser.add_argument("--expected-max-length", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-seconds", type=float, default=86400)
    args = parser.parse_args()
    expected = {key: getattr(args, "expected_" + key) for key in (
        "model", "method", "base_revision", "checkpoint_sha256", "temperature", "code_commit", "max_length")}
    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Received signal {signum}")

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        report = run(args.requests, args.input_sha256, args.endpoint, expected,
                     args.output, timeout=args.timeout, max_seconds=args.max_seconds)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({key: report[key] for key in (
        "status", "planned_requests", "attempted_requests", "successful_requests", "failed_requests", "pending_requests")}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
