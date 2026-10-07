"""Run frozen, input-only TREC listwise Score requests without reading qrels.

Each provider runs sequentially, with fresh HTTP connections and no retries.
Raw responses and failed/pending queries are retained; this runner computes no
accuracy. Use a new output directory for every bounded run.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

from jev.ir_eval import RerankFailure, rerank
from scripts import benchmark_jev_api_latency as jev_api
from scripts import benchmark_openai_api as openai_api
from scripts.benchmark_inference_latency import digest

PROTOCOL = {"method": "listwise_score", "request_profile": "general-ir-v1",
            "window_size": 20, "step_size": 10, "top_k": 100,
            "tokenizer": "cl100k_base", "query_max_tokens": 32, "passage_max_tokens": 128}
MODELS = ("jev-1.13.0", "gpt-5.6-luna", "gpt-6-astra")
STOP_HTTP = {400, 401, 403, 404, 429, 503, 529}
STOP_CODES = {"rate_limit_exceeded", "insufficient_quota", "invalid_api_key", "authentication_error",
              "permission_denied", "server_overloaded", "overloaded_error"}


class StopRun(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def load_input(path, expected_sha256):
    raw = Path(path).read_bytes()
    require(sha(raw) == expected_sha256, "Frozen input SHA256 differs")
    document = json.loads(raw)
    require(set(document) == {"schema_version", "usage", "protocol", "queries"} and
            document["schema_version"] == 1 and document["usage"] == "evaluation_only" and
            document["protocol"] == PROTOCOL, "Input-only schema or fixed protocol differs")
    queries = document["queries"]
    require(isinstance(queries, list) and len(queries) == 97, "Expected all 97 frozen queries")
    identities, benchmarks = set(), Counter()
    for query in queries:
        require(set(query) == {"benchmark", "id", "query", "documents"}, "Query contains unexpected metadata")
        require(all(isinstance(query[k], str) and query[k].strip() for k in ("benchmark", "id", "query")),
                "Invalid query identity or text")
        identity = query["benchmark"], query["id"]
        require(identity not in identities, "Duplicate query identity")
        identities.add(identity)
        benchmarks[query["benchmark"]] += 1
        documents = query["documents"]
        require(isinstance(documents, list) and len(documents) == 100, "Expected 100 candidates per query")
        document_ids = set()
        for passage in documents:
            require(set(passage) == {"id", "text"} and all(isinstance(v, str) and v.strip() for v in passage.values()),
                    "Passage contains unexpected metadata or invalid values")
            require(passage["id"] not in document_ids, "Duplicate candidate identity")
            document_ids.add(passage["id"])
    require(dict(benchmarks) == {"dl19": 43, "dl20": 54}, "DL19/DL20 query coverage differs")
    return document, raw


def endpoint_rejected(sample):
    if sample.get("http_status") in STOP_HTTP:
        return True
    response = sample.get("response")
    if not isinstance(response, dict):
        try:
            response = json.loads(sample.get("raw_response", ""))
        except (ValueError, TypeError):
            response = {}
    error = response.get("error", {}) if isinstance(response, dict) else {}
    return isinstance(error, dict) and any(str(error.get(k, "")).lower() in STOP_CODES for k in ("code", "type"))


def categorical_scores(request, sample, model):
    """Adapt actual integer levels only; never manufacture probability vectors."""
    decisions = openai_api.validate(request, sample["response"], model)
    saved = sample.get("decisions")
    require(isinstance(saved, dict) and set(saved) == set(decisions) and
            all(type(saved[qid]) is int and saved[qid] == value for qid, value in decisions.items()),
            "Saved and raw categorical decisions differ")
    return {"answers": {qid: {"type": "score", "score": value} for qid, value in decisions.items()}}


def jev_scores(request, sample):
    """Retain strict failures while allowing declared mass-only scalar analysis."""
    response = sample["response"]
    try:
        jev_api.validate(request, response, "jev-1.13.0")
    except ValueError as error:
        require(str(error) == "probabilities do not sum to one" and
                sample.get("error") == str(error) and sample.get("success") is False,
                "Jev error is not eligible for supplemental scalar analysis")
    require(response["model"] == "jev-1.13.0" and set(response["answers"]) == set(request["questions"]),
            "Jev model or question coverage differs")
    usage = response.get("usage", {})
    require(type(usage.get("input_tokens")) is int and usage["input_tokens"] >= 0, "Missing token usage")
    mass_failures, scalars = [], {}
    for qid, question in request["questions"].items():
        answer = response["answers"][qid]
        require(question["type"] == answer.get("type") == "score", "Expected Score answers only")
        probabilities = answer.get("probabilities")
        require(isinstance(probabilities, dict) and set(probabilities) == {"0", "1", "2", "3"}, "Score probability keys differ")
        require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities.values()),
                "Invalid Score probability")
        mass = sum(probabilities.values())
        require(mass > 0, "Nonpositive probability mass")
        scalar = answer.get("score")
        require(type(scalar) in (int, float) and math.isfinite(scalar) and 0 <= scalar <= 3, "Invalid raw Score scalar")
        expected = sum(int(level) * p for level, p in probabilities.items())
        require(math.isclose(scalar, expected, rel_tol=0, abs_tol=.035 + 1e-12), "Score differs from its probability expectation")
        if not math.isclose(mass, 1, rel_tol=0, abs_tol=1e-6):
            mass_failures.append({"question_id": qid, "mass": mass, "score": scalar,
                                  "raw_probability_expectation": expected})
        scalars[qid] = {"type": "score", "score": scalar}
    if mass_failures:
        require(sample.get("error") == "probabilities do not sum to one" and sample.get("success") is False,
                "Mass failure does not match the recorded Jev validation error")
        return {"answers": scalars}, mass_failures
    require(sample.get("success") is True, sample.get("error", "Jev request failed"))
    return response, []


def run(input_path, input_sha256, output, model, key, *, max_requests=873, timeout=60,
        max_seconds=10800, cost_limit_usd=80, max_output_tokens=2048, attempt_fn=None, clock=time.monotonic):
    require(model in MODELS and isinstance(key, str) and key.strip(), "Supported model and API key required")
    require(type(max_requests) is int and 1 <= max_requests <= 873 and
            math.isfinite(timeout) and 0 < timeout <= 60 and math.isfinite(max_seconds) and 0 < max_seconds <= 10800 and
            math.isfinite(cost_limit_usd) and 0 < cost_limit_usd <= 80 and
            type(max_output_tokens) is int and 128 <= max_output_tokens <= 2048, "Invalid bounded limits")
    document, raw_input = load_input(input_path, input_sha256)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "input.json").write_bytes(raw_input)
    is_openai = model in openai_api.MODEL_SETTINGS
    provider = openai_api if is_openai else jev_api
    attempt_fn = attempt_fn or provider.attempt
    started = clock()
    report = {"schema_version": 1, "usage": "evaluation_only", "status": "running", "model": model,
              "created_at": datetime.now(timezone.utc).isoformat(), "input_sha256": input_sha256,
              "protocol": PROTOCOL, "score_rounding_digits": None if is_openai else 2,
              "probability_mass_absolute_tolerance": 1e-6, "new_accuracy_metrics": False,
              "supplemental_scalar_analysis": {
                  "predeclared": True, "enabled": not is_openai,
                  "eligible_error": "HTTP 200 with the exact recorded Jev probability-mass error only; model, keys, types, finite ranges, positive mass and usage must validate.",
                  "score_expectation_absolute_tolerance": .035,
                  "policy": "Keep raw vectors unchanged. Continue adaptive windows using the actual scalar Score. Mark the query strictly invalid, omit its primary ranking, and save a separate supplemental ranking. Other errors fail the query.",
                  "strict_failure_metric_policy": "Downstream primary metrics must retain these qrel queries with zero contribution; never promote the supplemental ranking."},
              "qrels_read": False, "retries": 0, "concurrency": 1,
              "truncation_applied_by_runner": False,
              "truncation_policy": "Preserve the SHA-bound prepared token-prefix decode exactly; re-encoding a decoded prefix can exceed its original token count.",
              "limits": {"max_requests": max_requests, "timeout": timeout, "max_seconds": max_seconds,
                         "cost_limit_usd": cost_limit_usd if is_openai else None,
                         "max_output_tokens": max_output_tokens if is_openai else None},
              "cost_kind": "observed_usage_standard_list_estimate_not_invoice" if is_openai else "not_estimated",
              "cost_policy": ("Before each call, stop if the known usage-based estimate has reached its cap. The final call can cross the cap; unknown-cost calls are counted separately."
                              if is_openai else "Jev pricing is not estimated. Null cost fields do not mean free requests; raw token usage is retained."),
              "total_attempts": 0, "known_estimated_cost_usd": 0.0 if is_openai else None, "unknown_cost_requests": [],
              "source_sha256": sha(Path(__file__).read_bytes()),
              "provider_source_sha256": sha(Path(provider.__file__).read_bytes()),
              "reranker_source_sha256": sha(Path(__file__).resolve().parents[1].joinpath("jev/ir_eval.py").read_bytes()),
              "queries": [{"benchmark": q["benchmark"], "id": q["id"], "status": "pending", "ranking": None,
                           "supplemental_ranking": None, "strict_query_valid": None,
                           "request_ids": [], "call_wall_ms": [], "request_validations": [], "windows": []}
                          for q in document["queries"]]}
    if is_openai:
        report["model_settings"] = openai_api.MODEL_SETTINGS[model]

    def save_report():
        report["elapsed_seconds"] = clock() - started
        report["query_status_counts"] = dict(Counter(q["status"] for q in report["queries"]))
        validations = [v for q in report["queries"] for v in q["request_validations"]]
        report["collection_counts"] = {
            "http_200": sum(v["transport_success"] for v in validations),
            "transport_errors": sum(not v["transport_success"] for v in validations),
            "strict_valid_requests": sum(v["strict_valid"] is True for v in validations),
            "strict_validation_failures": sum(v["strict_valid"] is False for v in validations),
            "scalar_usable_requests": sum(v["scalar_usable"] for v in validations),
            "strict_complete_queries": sum(q["status"] == "complete" for q in report["queries"]),
            "scalar_complete_queries": sum(q["status"] in ("complete", "complete_scalar_only") for q in report["queries"])}
        temporary = output / "report.json.tmp"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary.replace(output / "report.json")

    def append(stream, value):
        stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())

    def check_budget():
        reason = ("request_budget" if report["total_attempts"] >= max_requests else
                  "time_budget" if clock() - started >= max_seconds else
                  "cost_budget" if is_openai and report["known_estimated_cost_usd"] >= cost_limit_usd else None)
        if reason:
            report["status"], report["stop_reason"] = "stopped_budget", reason
            raise StopRun(reason)

    save_report()
    try:
        with (output / "requests.jsonl").open("x") as requests, (output / "samples.jsonl").open("x") as samples:
            for query, result in zip(document["queries"], report["queries"]):
                result["status"] = "running"
                query_started = clock()

                def predict(request):
                    check_budget()
                    require(len(result["request_ids"]) < 9, "Unexpected tenth window for this query")
                    identifier = f"{query['benchmark']}:{query['id']}:window-{len(result['request_ids'])}"
                    workload = {"id": identifier, "request": request, "request_sha256": digest(request)}
                    payload = (openai_api.payload_for(request, model, max_output_tokens) if is_openai else
                               {**request, "model": model})
                    append(requests, {**workload, "payload": payload, "payload_sha256": digest(payload)})
                    result["request_ids"].append(identifier)
                    report["total_attempts"] += 1
                    attempt_started = clock()
                    try:
                        kwargs = {"max_output_tokens": max_output_tokens} if is_openai else {}
                        remaining = max_seconds - (attempt_started - started)
                        sample = attempt_fn(workload, key, model, "measured", 0, min(timeout, remaining), **kwargs)
                    except Exception as error:
                        sample = {"request_id": identifier, "request_sha256": workload["request_sha256"], "mode": model,
                                  "phase": "measured", "repetition": 0, "success": False,
                                  "error_type": type(error).__name__, "error": str(error).replace(key, "[REDACTED]"),
                                  "wall_ms": (clock() - attempt_started) * 1000}
                    stored_sample = sample
                    try:
                        json.dumps(sample, allow_nan=False)
                    except ValueError:
                        # Invalid provider numeric output must not erase its raw response.
                        stored_sample = {k: v for k, v in sample.items() if k not in ("response", "decisions", "estimated_cost_usd")}
                        stored_sample["parsed_response_omitted"] = "Nonfinite parsed JSON value; exact raw_response retained for audit."
                    append(samples, stored_sample)
                    result["call_wall_ms"].append(sample.get("wall_ms"))
                    validation = {"request_id": identifier, "http_status": sample.get("http_status"),
                                  "transport_success": sample.get("http_status") == 200,
                                  "strict_valid": None, "scalar_usable": False}
                    result["request_validations"].append(validation)
                    if is_openai:
                        try:
                            response = sample.get("response")
                            cost = openai_api.cost_estimate(response.get("usage") if isinstance(response, dict) else None, model)
                        except (TypeError, ValueError, KeyError):
                            cost = None
                        if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
                            report["known_estimated_cost_usd"] += cost
                        else:
                            report["unknown_cost_requests"].append(identifier)
                    if endpoint_rejected(sample):
                        report["status"], report["stop_reason"] = "stopped_endpoint", f"provider_rejection:{sample.get('http_status')}"
                        raise StopRun(report["stop_reason"])
                    try:
                        require(sample.get("request_id") == identifier and sample.get("request_sha256") == workload["request_sha256"] and
                                sample.get("mode") == model and sample.get("phase") == "measured" and sample.get("repetition") == 0,
                                "Provider sample identity differs")
                        require(sample.get("http_status") == 200, sample.get("error", "Provider request failed"))
                        validation["strict_valid"] = False
                        require(json.loads(sample["raw_response"]) == sample["response"], "Raw and parsed response differ")
                        if is_openai:
                            require(sample.get("success") is True, sample.get("error", "OpenAI request failed"))
                            adapted, mass_failures = categorical_scores(request, sample, model), []
                        else:
                            adapted, mass_failures = jev_scores(request, sample)
                        validation["strict_valid"], validation["scalar_usable"] = not mass_failures, True
                        if mass_failures:
                            validation["strict_probability_mass_failure"] = mass_failures
                        return adapted
                    except Exception as error:
                        validation["error_type"], validation["error"] = type(error).__name__, str(error).replace(key, "[REDACTED]")
                        raise

                trace = []
                try:
                    ranked = rerank(query["query"], query["documents"], "listwise_score", predict,
                                    request_profile="general-ir-v1", window_size=20, step_size=10, top_k=100,
                                    score_rounding_digits=None if is_openai else 2)
                    require(len(result["request_ids"]) == 9, "Completed query did not consume nine windows")
                    strict = all(v["strict_valid"] is True for v in result["request_validations"])
                    result["strict_query_valid"] = strict
                    result["status"] = "complete" if strict else "complete_scalar_only"
                    result["ranking"] = ranked["ranking"] if strict else None
                    result["supplemental_ranking"] = ranked["ranking"] if not is_openai else None
                    trace = ranked["trace"]
                except RerankFailure as error:
                    trace = error.trace
                    cause = error.__cause__
                    result["error_type"] = type(cause).__name__
                    result["error"] = str(cause).replace(key, "[REDACTED]")
                    if isinstance(cause, OSError):
                        raise
                    if isinstance(cause, StopRun):
                        result["status"] = ("failed_endpoint" if report["status"] == "stopped_endpoint" else
                                            "incomplete_budget" if result["request_ids"] else "pending")
                    else:
                        result["status"] = "failed"
                    if result["status"] != "pending":
                        result["strict_query_valid"] = False
                finally:
                    result["query_wall_seconds"] = clock() - query_started
                    result["windows"] = [{"request_id": rid, "document_ids": entry["document_ids"]}
                                         for rid, entry in zip(result["request_ids"], trace)]
                    save_report()
                if report["status"] != "running":
                    break
            if report["status"] == "running":
                report["status"] = "complete" if all(q["status"] == "complete" for q in report["queries"]) else "completed_with_query_failures"
    except BaseException as error:
        report["status"], report["error_type"] = "interrupted_or_failed", type(error).__name__
        for query in report["queries"]:
            if query["status"] == "running":
                query["status"] = "interrupted"
        raise
    finally:
        report["unknown_cost_request_count"] = len(report["unknown_cost_requests"]) if is_openai else None
        save_report()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--max-requests", type=int, default=873)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-seconds", type=float, default=10800)
    parser.add_argument("--cost-limit-usd", type=float, default=80)
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    args = parser.parse_args()
    environment = "TYPESAFE_API_KEY" if args.model == "jev-1.13.0" else "OPENAI_API_KEY"
    key = os.environ.get(environment, "").strip()
    if not key:
        parser.error(environment + " required; no request sent")
    result = run(args.input, args.input_sha256, args.output, args.model, key, max_requests=args.max_requests,
                 timeout=args.timeout, max_seconds=args.max_seconds, cost_limit_usd=args.cost_limit_usd,
                 max_output_tokens=args.max_output_tokens)
    print(json.dumps({"status": result["status"], "total_attempts": result["total_attempts"],
                      "queries": result["query_status_counts"], "output": str(args.output)}))
    return 0 if result["status"] in ("complete", "completed_with_query_failures") else 2


if __name__ == "__main__":
    raise SystemExit(main())
