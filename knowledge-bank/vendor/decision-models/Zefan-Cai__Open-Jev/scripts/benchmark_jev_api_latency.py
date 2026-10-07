"""Measure the official Jev API on the exact saved Open-Jev latency workloads.

Run on the same client as the local HTTP benchmark. Requires TYPESAFE_API_KEY;
no credentials are saved, no retries occur, and rejected calls are not inference.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import platform
import time

from scripts.benchmark_inference_latency import digest, summarize

HOST = "api.typesafe.ai"
ENDPOINT = "/v1/systemone"


def validate(request, response, model):
    if not isinstance(response, dict) or response.get("model") != model:
        raise ValueError("unexpected returned model")
    answers = response.get("answers", {})
    if set(answers) != set(request["questions"]):
        raise ValueError("answer coverage differs")
    for key, question in request["questions"].items():
        answer = answers[key]
        if answer.get("type") != question["type"]:
            raise ValueError("answer type differs")
        if question["type"] == "noul":
            values = [answer["noul"]]
        else:
            probabilities = answer["probabilities"]
            expected = question["criteria"]
            if question["type"] == "score":
                expected = {str(i) for i in range(len(expected))}
            if set(probabilities) != set(expected):
                raise ValueError("candidate coverage differs")
            values = list(probabilities.values())
            if not math.isclose(sum(values), 1, abs_tol=1e-6):
                raise ValueError("probabilities do not sum to one")
            if question["type"] == "choice":
                chosen = answer.get("choice")
                if chosen not in probabilities or probabilities[chosen] != max(values):
                    raise ValueError("selected choice is not a maximum")
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
            raise ValueError("invalid probability")
    usage = response.get("usage", {})
    if not isinstance(usage.get("input_tokens"), int) or usage["input_tokens"] < 0:
        raise ValueError("missing token usage")


def attempt(workload, key, model, phase, repetition, timeout):
    sample = {"request_id": workload["id"], "request_sha256": workload["request_sha256"],
              "transport": "https_remote_fresh_connection", "mode": model, "phase": phase,
              "repetition": repetition, "success": False,
              "started_at": datetime.now(timezone.utc).isoformat()}
    connection = None
    started = time.perf_counter()
    try:
        # Only add the top-level model; preserve state/questions and their key order.
        body = {**workload["request"], "model": model}
        payload = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        connection = http.client.HTTPSConnection(HOST, timeout=timeout)
        connection.request("POST", ENDPOINT, payload,
                           {"Content-Type": "application/json", "Authorization": "Bearer " + key})
        received = connection.getresponse()
        sample["http_status"] = received.status
        raw = received.read()
        sample["raw_response"] = raw.decode("utf-8", errors="replace").replace(key, "[REDACTED]")
        sample["response_bytes"] = len(raw)
        if received.status != 200:
            raise ValueError(f"HTTP {received.status}; not a successful inference")
        response = json.loads(sample["raw_response"])
        sample["response"] = response
        validate(workload["request"], response, model)
        sample["success"] = True
    except Exception as error:
        sample["error_type"] = type(error).__name__
        sample["error"] = str(error).replace(key, "[REDACTED]")
    finally:
        sample["wall_ms"] = (time.perf_counter() - started) * 1000
        if connection:
            connection.close()
    return sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", default="jev-1.13.0")
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-seconds", type=float, default=900)
    parser.add_argument("--workload", action="append", help="Optional exact IDs; default all saved workloads")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 200 or not 0 <= args.warmup <= 10 or not 1 <= args.timeout <= 120 or not 1 <= args.max_seconds <= 86400:
        parser.error("invalid bounded arguments")
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        parser.error("TYPESAFE_API_KEY is required; no request has been sent")
    document = json.loads(args.requests.read_bytes())
    workloads = document["workloads"]
    if args.workload:
        if set(args.workload) - {row["id"] for row in workloads}:
            parser.error("unknown workload ID")
        workloads = [row for row in workloads if row["id"] in args.workload]
    if not workloads or len({row['id'] for row in workloads}) != len(workloads):
        parser.error("requires saved workloads with unique IDs")
    for row in workloads:
        if row["request_sha256"] != digest(row["request"]):
            parser.error("saved request checksum mismatch")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "requests.json").write_text(json.dumps({"schema_version": 1, "workloads": workloads}, ensure_ascii=False, indent=2) + "\n")
    report = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
              "endpoint": f"https://{HOST}{ENDPOINT}", "model": args.model,
              "client_hostname": platform.node(), "python": platform.python_version(),
              "configuration": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "scope": "Same saved request text; fresh DNS/TCP/TLS connection per attempt, full response and validation included. Concurrency one; no retries. Network and backend differ from loopback Open-Jev; no matched-hardware speedup claim.",
              "percentile_method": "Linear interpolation on successful measured attempts only; all failures and warmups retained.",
              "workload_manifest_sha256": digest(workloads),
              "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "status": "running"}
    samples = []
    started = time.monotonic()
    try:
        with (args.output / "samples.jsonl").open("x") as stream:
            stop = False
            for workload in workloads:
                for i in range(args.warmup + args.repetitions):
                    if time.monotonic() - started >= args.max_seconds:
                        report["status"], stop = "budget_exhausted", True
                        break
                    phase = "warmup" if i < args.warmup else "measured"
                    row = attempt(workload, key, args.model, phase, i if phase == "warmup" else i - args.warmup, args.timeout)
                    samples.append(row)
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                    stream.flush()
                    # Do not hammer an endpoint after auth, rate-limit or overload rejection.
                    if row.get("http_status") in (401, 403, 429, 529):
                        report["status"], stop = "endpoint_rejected", True
                        break
                if stop:
                    break
            if report["status"] == "running":
                report["status"] = "passed" if all(row["success"] for row in samples) else "request_errors"
    except BaseException as error:
        report["status"], report["error_type"] = "interrupted_or_failed", type(error).__name__
        raise
    finally:
        report.update(summaries=summarize(samples), total_attempts=len(samples),
                      warmup_attempts=sum(row["phase"] == "warmup" for row in samples),
                      measured_attempts=sum(row["phase"] == "measured" for row in samples),
                      errors_including_warmup=sum(not row["success"] for row in samples),
                      elapsed_seconds=time.monotonic() - started)
        (args.output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "output": str(args.output)}))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
