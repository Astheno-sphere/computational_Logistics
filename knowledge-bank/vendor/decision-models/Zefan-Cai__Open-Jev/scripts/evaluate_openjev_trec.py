"""Collect frozen TREC rerankings from an owned, uncached Open-Jev server.

No model or server is started here, and no qrels or API keys are read. Each
dispatch is journaled before it is sent. Use a fresh output directory; an
interrupted bundle must be audited, never silently resumed or overwritten.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time

from jev import ir_eval
from scripts import evaluate_openjev_provider as client
from scripts import evaluate_trec_provider as input_loader

PROTOCOL = input_loader.PROTOCOL
INPUT_SHA256 = "cc7bc949dbc269dacb61bdb61fc8982db14bc4df3698f9d32f5f1c8b6795eb83"
OPEN_QUERY_STATUSES = {"pending", "running", "incomplete_budget", "interrupted"}


class BudgetStop(ValueError):
    pass


class FatalRequest(ValueError):
    pass


class FailedRequest(ValueError):
    pass


def source_hashes():
    return {name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for name, path in (
        ("runner", __file__), ("client", client.__file__),
        ("input_loader", input_loader.__file__), ("reranker", ir_eval.__file__))}


def validate_sample(workload, sample, expected):
    """Recheck the client envelope and actual response before persisting success."""
    if (sample.get("request_id") != workload["id"] or sample.get("request_sha256") != workload["request_sha256"] or
            sample.get("mode") != expected["model"] or sample.get("phase") != "measured" or
            type(sample.get("repetition")) is not int or sample["repetition"] != 0 or
            type(sample.get("success")) is not bool):
        raise client.IdentityError("Returned sample identity differs from the dispatched request")
    if sample["success"]:
        raw_value = client.strict_json(sample["raw_response"])
        raw_wire = json.dumps(raw_value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        parsed_wire = json.dumps(sample["response"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if sample.get("http_status") != 200 or raw_wire != parsed_wire:
            raise ValueError("Successful sample does not match its HTTP response")
        client.validate_response(workload["request"], sample["response"], expected)
        # The reranker also enforces exact scalar bounds. Validate its actual
        # adapter before recording success, including values within the shared
        # client's expectation tolerance but outside the legal Score range.
        ir_eval._answers(workload["request"], sample["response"], score_rounding_digits=None)


def run(input_path, input_sha256, endpoint, expected, output, *, max_requests=873,
        timeout=300, max_seconds=10800, attempt_fn=None, clock=time.monotonic):
    client.validate_identity_config(expected)
    client.local_endpoint(endpoint)
    if (type(max_requests) is not int or not 1 <= max_requests <= 873 or
            not math.isfinite(timeout) or not 0 < timeout <= 300 or
            not math.isfinite(max_seconds) or not 0 < max_seconds <= 10800):
        raise ValueError("Invalid bounded TREC collection limits")
    document, raw_input = input_loader.load_input(input_path, input_sha256)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "input.json").write_bytes(raw_input)
    attempt_fn = attempt_fn or client.attempt
    started = clock()
    report = {"schema_version": 1, "usage": "evaluation_only", "status": "running",
              "created_at": datetime.now(timezone.utc).isoformat(), "model": expected["model"],
              "expected_identity": expected, "endpoint": endpoint, "input_sha256": input_sha256,
              "protocol": PROTOCOL, "source_sha256": source_hashes(), "score_rounding_digits": None,
              "probability_mass_absolute_tolerance": 1e-6, "qrels_read": False,
              "truncation_applied_by_runner": False, "new_accuracy_metrics": False,
              "concurrency": 1, "warmups": 0, "retries": 0, "prefix_cache": False,
              "attempt_journal": "requests.jsonl", "planned_queries": 97, "planned_max_requests": 873,
              "started_requests": 0, "attempted_requests": 0, "in_flight_requests": 0,
              "successful_requests": 0, "failed_requests": 0, "pending_queries": 97,
              "limits": {"max_requests": max_requests, "timeout": timeout, "max_seconds": max_seconds},
              "scope": "Frozen initial BM25 top100 and actual, adaptive Score windows. No qrels, new truncation, probability renormalization or scalar rounding. Failed queries have no ranking; missing queries stay pending. Raw passages, requests and responses are private evaluation evidence. One-attempt wall times are not a repeated latency benchmark.",
              "queries": [{"benchmark": q["benchmark"], "id": q["id"], "status": "pending",
                           "request_ids": [], "ranking": None, "windows": [], "strict_query_valid": None,
                           "call_wall_ms": []} for q in document["queries"]]}

    def save():
        report["elapsed_seconds"] = clock() - started
        report["in_flight_requests"] = report["started_requests"] - report["attempted_requests"]
        report["pending_queries"] = sum(q["status"] in OPEN_QUERY_STATUSES for q in report["queries"])
        report["query_status_counts"] = dict(Counter(q["status"] for q in report["queries"]))
        temporary = output / "report.json.tmp"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary.replace(output / "report.json")

    def append(stream, value):
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

    def check_budget():
        reason = ("request_budget" if report["started_requests"] >= max_requests else
                  "time_budget" if clock() - started >= max_seconds else None)
        if reason:
            report["status"], report["stop_reason"] = "stopped_budget", reason
            raise BudgetStop(reason)

    save()
    try:
        with (output / "requests.jsonl").open("x") as journal, (output / "samples.jsonl").open("x") as samples:
            for query, result in zip(document["queries"], report["queries"]):
                result["status"] = "running"
                trace = []

                def predict(request):
                    check_budget()
                    if len(result["request_ids"]) >= 9:
                        raise RuntimeError("Unexpected tenth window for a frozen TREC query")
                    identifier = f"{query['benchmark']}:{query['id']}:window-{len(result['request_ids'])}"
                    workload = {"id": identifier, "request": request, "request_sha256": client.digest(request)}
                    payload = {**request, "model": "open-jev"}
                    stamp = datetime.now(timezone.utc).isoformat()
                    # This fsynced request is also the dispatch journal. A
                    # SIGKILL can leave it unmatched; that outcome is unknown.
                    append(journal, {**workload, "payload": payload, "payload_sha256": client.digest(payload),
                                     "started_at": stamp})
                    result["request_ids"].append(identifier)
                    report["started_requests"] += 1
                    save()
                    call_started = clock()
                    try:
                        remaining = max_seconds - (call_started - started)
                        if remaining <= 0:
                            raise TimeoutError("Time budget expired after dispatch journaling, before HTTP send")
                        sample = attempt_fn(workload, endpoint, expected, min(timeout, remaining))
                    except (Exception, KeyboardInterrupt) as error:
                        sample = {"request_id": identifier, "request_sha256": workload["request_sha256"],
                                  "mode": expected["model"], "phase": "measured", "repetition": 0,
                                  "transport": "http_loopback_fresh_connection", "started_at": stamp,
                                  "success": False, "fatal": True, "error_type": type(error).__name__,
                                  "error": str(error), "wall_ms": (clock() - call_started) * 1000}
                    try:
                        validate_sample(workload, sample, expected)
                    except (ValueError, KeyError, TypeError) as error:
                        sample.update(success=False, error_type=type(error).__name__, error=str(error))
                        if isinstance(error, client.IdentityError):
                            sample["fatal"] = True
                    if sample.get("http_status") is not None and sample["http_status"] not in (200, 400, 413, 422):
                        sample["fatal"] = True
                    append(samples, sample)
                    report["attempted_requests"] += 1
                    report["successful_requests" if sample["success"] else "failed_requests"] += 1
                    result["call_wall_ms"].append(sample["wall_ms"])
                    if sample.get("fatal"):
                        report["status"] = "stopped_fatal"
                    save()
                    if sample.get("fatal"):
                        raise FatalRequest(sample.get("error", "Fatal local service failure"))
                    if not sample["success"]:
                        raise FailedRequest(sample.get("error", "Invalid local service response"))
                    return sample["response"]

                try:
                    ranked = ir_eval.rerank(query["query"], query["documents"], "listwise_score", predict,
                                            request_profile="general-ir-v1", window_size=20, step_size=10,
                                            top_k=100, score_rounding_digits=None)
                    trace = ranked["trace"]
                    if len(result["request_ids"]) != 9:
                        raise RuntimeError("Complete TREC query must consume exactly nine windows")
                    result.update(status="complete", ranking=ranked["ranking"], strict_query_valid=True)
                except ir_eval.RerankFailure as error:
                    trace, cause = error.trace, error.__cause__
                    result["error_type"], result["error"] = type(cause).__name__, str(cause)
                    if isinstance(cause, BudgetStop):
                        result["status"] = "incomplete_budget" if result["request_ids"] else "pending"
                        result["strict_query_valid"] = False if result["request_ids"] else None
                    elif isinstance(cause, (FatalRequest, FailedRequest)):
                        result.update(status="failed_fatal" if isinstance(cause, FatalRequest) else "failed",
                                      strict_query_valid=False)
                    else:
                        raise cause
                finally:
                    result["windows"] = [{"request_id": rid, "document_ids": entry["document_ids"]}
                                         for rid, entry in zip(result["request_ids"], trace)]
                    save()
                if report["status"] != "running":
                    break
            if report["status"] == "running":
                report["status"] = ("complete" if all(q["status"] == "complete" for q in report["queries"])
                                    else "completed_with_query_failures")
    except BaseException as error:
        report["status"], report["error_type"] = "interrupted_or_failed", type(error).__name__
        for query in report["queries"]:
            if query["status"] == "running":
                query.update(status="interrupted", strict_query_valid=False if query["request_ids"] else None)
        raise
    finally:
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
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
    parser.add_argument("--max-requests", type=int, default=873)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--max-seconds", type=float, default=10800)
    args = parser.parse_args()
    expected = {key: getattr(args, "expected_" + key) for key in (
        "model", "method", "base_revision", "checkpoint_sha256", "temperature", "code_commit", "max_length")}

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Received signal {signum}")

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        report = run(args.input, args.input_sha256, args.endpoint, expected, args.output,
                     max_requests=args.max_requests, timeout=args.timeout, max_seconds=args.max_seconds)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({key: report[key] for key in (
        "status", "started_requests", "attempted_requests", "in_flight_requests", "pending_queries", "query_status_counts")}))
    return 0 if report["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
