"""Replay saved TREC responses and score against isolated, complete qrels.

No provider calls are made. Public output contains identities, hashes and
metrics, never request/passages/raw responses or replay timing measurements.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from jev.ir_eval import RerankFailure, load_external_holdout, ndcg_at_k, rerank
from scripts import evaluate_trec_provider as runner
from scripts.benchmark_inference_latency import digest

ROOT = Path(__file__).resolve().parents[1]
INPUT_SHA256 = "cc7bc949dbc269dacb61bdb61fc8982db14bc4df3698f9d32f5f1c8b6795eb83"
MANIFEST_SHA256 = {
    "dl19": "84c7cc23ce0f7309a48432c449e7856aeff96f9e2571f1f18cdb405703a6c297",
    "dl20": "494d6f39537b65981ea6707c7ba232e890460ad8f51e86628d2c2a5547288ea4",
}
FINAL_STATUSES = {"complete", "completed_with_query_failures"}
PARTIAL_STATUSES = {"running", "stopped_budget", "stopped_endpoint", "interrupted_or_failed"}
OPEN_QUERY_STATUSES = {"pending", "running", "incomplete_budget", "interrupted"}
CLOSED_QUERY_STATUSES = {"complete", "complete_scalar_only", "failed", "failed_endpoint"}


class AuditError(ValueError):
    pass


class ReplayBoundary(ValueError):
    """No saved response: do not invent a decision to finish a partial query."""


class ReplayEndpoint(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def strict_json(raw):
    def invalid_constant(_):
        raise AuditError("Nonfinite value outside the retained raw-response string")
    return json.loads(raw, parse_constant=invalid_constant)


def _records(raw, key):
    records = [strict_json(line) for line in raw.splitlines() if line.strip()]
    require(all(isinstance(row, dict) and isinstance(row.get(key), str) for row in records), "Invalid raw log record")
    ids = [row[key] for row in records]
    require(len(set(ids)) == len(ids), "Duplicate raw log identity")
    return ids, dict(zip(ids, records))


def _bind_request(request, saved, model, max_output_tokens):
    require(wire(request) == wire(saved["request"]), "Adaptive request content or insertion order differs")
    require(saved["request_sha256"] == digest(request), "Request SHA256 differs")
    payload = (runner.openai_api.payload_for(request, model, max_output_tokens)
               if model != "jev-1.13.0" else {**request, "model": model})
    require(wire(saved["payload"]) == wire(payload) and saved["payload_sha256"] == digest(payload),
            "Saved provider payload differs")
    return payload


def _sample(request, saved, sample, model, max_output_tokens):
    """Check evidence bindings before applying the runner's typed validation."""
    payload = _bind_request(request, saved, model, max_output_tokens)
    require(sample.get("request_id") == saved["id"] and sample.get("request_sha256") == digest(request)
            and sample.get("mode") == model and sample.get("phase") == "measured"
            and type(sample.get("repetition")) is int and sample["repetition"] == 0,
            "Saved sample identity/model/phase differs")
    if "payload_sha256" in sample or (model != "jev-1.13.0" and sample.get("http_status") is not None):
        require(sample.get("payload_sha256") == digest(payload), "Sample payload SHA256 differs")
    if "response" in sample:
        require("raw_response" in sample and strict_json(sample["raw_response"]) == sample["response"],
                "Raw and parsed response differ")
    if sample.get("parsed_response_omitted"):
        require("response" not in sample and isinstance(sample.get("raw_response"), str),
                "Invalid omitted-response evidence")
        # The exact invalid text remains in the private log. It cannot be a usable decision.
        try:
            strict_json(sample["raw_response"])
        except AuditError:
            return None, [], "nonfinite_response"
        raise AuditError("Omitted parsed response has no recorded nonfinite value")
    if runner.endpoint_rejected(sample):
        return None, [], "endpoint"
    if sample.get("http_status") != 200:
        return None, [], "provider_error"
    try:
        if "response" not in sample:
            # Malformed HTTP-200 JSON is a query failure, not a fabricated answer.
            json.loads(sample.get("raw_response", ""))
            raise ValueError("Missing parsed provider response")
        if model == "jev-1.13.0":
            adapted, mass = runner.jev_scores(request, sample)
        else:
            runner.require(sample.get("success") is True, "OpenAI sample failed")
            adapted, mass = runner.categorical_scores(request, sample, model), []
        return adapted, mass, None
    except (ValueError, KeyError, TypeError, AttributeError):
        return None, [], "typed_validation"


def _mass_details_match(saved, replayed, sample):
    """Match exact diagnostics from current or Python <=3.11 float summation.

    CPython 3.12 changed sum(float) to compensated summation. Only these
    derived diagnostics may use legacy arithmetic; strict decisions and raw
    provider values are still checked by the unchanged runner validators.
    """
    if not isinstance(saved, list) or len(saved) != len(replayed):
        return False
    for actual, expected in zip(saved, replayed):
        if (not isinstance(actual, dict) or set(actual) != set(expected)
                or any(type(actual[key]) is not type(value) for key, value in expected.items())):
            return False
    if saved == replayed:
        return True

    def legacy_sum(values):
        total = 0
        for value in values:
            total += value
        return total

    legacy = []
    for detail in replayed:
        probabilities = sample["response"]["answers"][detail["question_id"]]["probabilities"]
        legacy.append({**detail, "mass": legacy_sum(probabilities.values()),
                       "raw_probability_expectation": legacy_sum(int(k) * p for k, p in probabilities.items())})
    return saved == legacy


def _replay(query, claim, requests, samples, model, max_output_tokens):
    ids = claim["request_ids"]
    expected_ids = [f"{query['benchmark']}:{query['id']}:window-{i}" for i in range(len(ids))]
    require(ids == expected_ids and len(ids) <= 9, "Query request order/count differs")
    validations, consumed, unavailable = [], [], []

    def replay(request):
        index = len(consumed)
        if index == len(ids):
            raise ReplayBoundary("No further recorded request")
        identifier = ids[index]
        consumed.append(identifier)
        require(identifier in requests, "Recorded request missing from raw log")
        saved = requests[identifier]
        if identifier not in samples:
            _bind_request(request, saved, model, max_output_tokens)
            unavailable.append(identifier)
            raise ReplayBoundary("Recorded request has no returned sample")
        sample = samples[identifier]
        adapted, mass, error = _sample(request, saved, sample, model, max_output_tokens)
        strict = (not mass if error is None else
                  None if error == "endpoint" or sample.get("http_status") != 200 else False)
        validation = {"request_id": identifier, "http_status": sample.get("http_status"),
                      "transport_success": sample.get("http_status") == 200,
                      "strict_valid": strict, "scalar_usable": error is None}
        if mass:
            validation["strict_probability_mass_failure"] = mass
        validations.append(validation)
        if error == "endpoint":
            raise ReplayEndpoint("Recorded endpoint rejection")
        if error:
            raise ValueError("Recorded provider response is invalid")
        return adapted

    result, failure = None, None
    try:
        result = rerank(query["query"], query["documents"], "listwise_score", replay,
                        request_profile="general-ir-v1", window_size=20, step_size=10, top_k=100,
                        score_rounding_digits=2 if model == "jev-1.13.0" else None)
        trace = result["trace"]
    except RerankFailure as error:
        failure, trace = error.__cause__, error.trace
        if isinstance(failure, AuditError):
            raise failure
    require(consumed == ids, "Replay did not consume every recorded query request")
    windows = [{"request_id": rid, "document_ids": entry["document_ids"]}
               for rid, entry in zip(ids, trace)]
    require(claim["windows"] == windows, "Saved adaptive window document IDs differ")
    require(len(claim["request_validations"]) == len(validations), "Validation count differs from returned samples")
    for expected, saved in zip(validations, claim["request_validations"]):
        require(all(type(saved.get(key)) is type(value) and saved.get(key) == value
                    for key, value in expected.items() if key != "strict_probability_mass_failure"),
                "Saved validation flags differ from raw replay")
        if "strict_probability_mass_failure" in expected:
            require(_mass_details_match(saved.get("strict_probability_mass_failure"),
                                        expected["strict_probability_mass_failure"], samples[expected["request_id"]]),
                    "Saved mass-failure diagnostics differ from raw replay")
        else:
            require(not saved.get("strict_probability_mass_failure"), "Invented mass-only validation failure")

    status, ranking, supplemental = claim["status"], claim["ranking"], claim["supplemental_ranking"]
    candidates = {doc["id"] for doc in query["documents"]}
    for value in (ranking, supplemental):
        if value is not None:
            require(isinstance(value, list) and len(value) == 100 and all(isinstance(x, str) for x in value)
                    and len(set(value)) == 100 and set(value) == candidates, "Ranking is not a full candidate permutation")
    strict = len(validations) == 9 and all(v["strict_valid"] is True for v in validations)
    scalar = len(validations) == 9 and all(v["scalar_usable"] for v in validations)
    if status == "complete":
        require(result is not None and strict and claim["strict_query_valid"] is True
                and ranking == result["ranking"], "Complete query is not supported by strict raw replay")
        require(supplemental == ranking if model == "jev-1.13.0" else supplemental is None,
                "Complete supplemental ranking differs")
    elif status == "complete_scalar_only":
        require(model == "jev-1.13.0" and result is not None and scalar and not strict
                and claim["strict_query_valid"] is False and ranking is None and supplemental == result["ranking"],
                "Scalar-only completion is not supported by raw replay")
    else:
        require(ranking is None and supplemental is None, "Incomplete/failed query contains a ranking")
        if status in ("failed", "failed_endpoint"):
            require(failure is not None and not isinstance(failure, ReplayBoundary)
                    and claim["strict_query_valid"] is False, "Failed query has no actual recorded failure")
            require((status == "failed_endpoint") == isinstance(failure, ReplayEndpoint), "Endpoint failure classification differs")
        elif status == "pending":
            require(not ids and claim["strict_query_valid"] is None, "Pending query has attempted decisions")
        else:
            require(status in OPEN_QUERY_STATUSES and (claim["strict_query_valid"] is None or
                    claim["strict_query_valid"] is False), "Invalid partial query state")
        require(not unavailable or status in OPEN_QUERY_STATUSES, "Closed query has an unreturned sample")
    return validations, unavailable


def summarize(run_dir, holdout_paths, *, input_sha256=INPUT_SHA256, manifest_sha256=MANIFEST_SHA256):
    run_dir = Path(run_dir)
    paths = {name: run_dir / name for name in ("input.json", "report.json", "requests.jsonl", "samples.jsonl")}
    snapshots = {name: path.read_bytes() for name, path in paths.items()}
    document, input_raw = runner.load_input(paths["input.json"], input_sha256)
    require(input_raw == snapshots["input.json"], "Input changed while reading snapshot")
    report = strict_json(snapshots["report.json"])
    require(report.get("schema_version") == 1 and report.get("usage") == "evaluation_only"
            and report.get("input_sha256") == input_sha256 and report.get("protocol") == runner.PROTOCOL
            and report.get("model") in runner.MODELS and report.get("qrels_read") is False
            and report.get("truncation_applied_by_runner") is False, "Runner report contract differs")
    model = report["model"]
    provider = runner.jev_api if model == "jev-1.13.0" else runner.openai_api
    sources = {"runner": Path(runner.__file__), "provider": Path(provider.__file__),
               "reranker": ROOT / "jev/ir_eval.py", "scorer": Path(__file__)}
    source_hashes = {key: sha(path.read_bytes()) for key, path in sources.items()}
    for field, key in (("source_sha256", "runner"), ("provider_source_sha256", "provider"), ("reranker_source_sha256", "reranker")):
        require(report.get(field) == source_hashes[key], "Replay source differs from recorded runner dependency")
    require(report.get("probability_mass_absolute_tolerance") == 1e-6
            and report.get("score_rounding_digits") == (2 if model == "jev-1.13.0" else None), "Validation tolerances differ")
    supplemental = report.get("supplemental_scalar_analysis", {})
    require(supplemental.get("predeclared") is True and supplemental.get("enabled") is (model == "jev-1.13.0")
            and supplemental.get("score_expectation_absolute_tolerance") == .035, "Supplemental contract differs")
    status = report.get("status")
    require(status in FINAL_STATUSES | PARTIAL_STATUSES, "Unknown runner status")
    claims = report.get("queries", [])
    require(len(claims) == 97 and [(q["benchmark"], q["id"]) for q in claims] ==
            [(q["benchmark"], q["id"]) for q in document["queries"]], "Report query identities/order differ")
    require(all(q["status"] in CLOSED_QUERY_STATUSES | OPEN_QUERY_STATUSES for q in claims), "Unknown query status")
    counts = dict(Counter(q["status"] for q in claims))
    require(report.get("query_status_counts") == counts, "Query status aggregates differ")
    if status == "complete":
        require(counts == {"complete": 97}, "Completed runner has incomplete or failed queries")
    if status == "completed_with_query_failures":
        require(not any(q["status"] in OPEN_QUERY_STATUSES | {"failed_endpoint"} for q in claims)
                and counts != {"complete": 97}, "Completed-with-failures runner is not finished")
    finished = status in FINAL_STATUSES
    request_ids, requests = _records(snapshots["requests.jsonl"], "id")
    sample_ids, samples = _records(snapshots["samples.jsonl"], "request_id")
    reported_ids = [rid for q in claims for rid in q["request_ids"]]
    require(len(set(reported_ids)) == len(reported_ids) and report.get("total_attempts") == len(reported_ids), "Attempt aggregates differ")
    require(request_ids[:len(reported_ids)] == reported_ids, "Raw request sequence differs from report prefix")
    require(sample_ids == request_ids[:len(sample_ids)], "Raw sample order differs or sample has no request")
    if finished:
        require(request_ids == sample_ids == reported_ids, "Final report has missing or unreferenced raw records")
    validations, unavailable = [], []
    for query, claim in zip(document["queries"], claims):
        checked, missing = _replay(query, claim, requests, samples, model, report["limits"]["max_output_tokens"])
        validations.extend(checked)
        unavailable.extend(missing)
    actual_counts = {"http_200": sum(v["transport_success"] for v in validations),
                     "transport_errors": sum(not v["transport_success"] for v in validations),
                     "strict_valid_requests": sum(v["strict_valid"] is True for v in validations),
                     "strict_validation_failures": sum(v["strict_valid"] is False for v in validations),
                     "scalar_usable_requests": sum(v["scalar_usable"] for v in validations),
                     "strict_complete_queries": counts.get("complete", 0),
                     "scalar_complete_queries": counts.get("complete", 0) + counts.get("complete_scalar_only", 0)}
    require(report.get("collection_counts") == actual_counts, "Collection aggregates differ from raw replay")

    benchmarks, input_hashes = {}, {name: sha(raw) for name, raw in snapshots.items()}
    for benchmark, expected_count in (("dl19", 43), ("dl20", 54)):
        path = Path(holdout_paths[benchmark])
        require(sha(path.read_bytes()) == manifest_sha256[benchmark], "Frozen external manifest differs")
        holdout = load_external_holdout(path)
        require(holdout["manifest"]["benchmark"] == "TREC-" + benchmark.upper(), "External benchmark differs")
        prepared = {q["id"]: q for q in document["queries"] if q["benchmark"] == benchmark}
        require(len(prepared) == expected_count and set(prepared) == set(holdout["queries"]) == set(holdout["qrels"]),
                "Full judged query coverage differs")
        for qid, query in prepared.items():
            require([d["id"] for d in query["documents"]] == [d["id"] for d in holdout["queries"][qid]["documents"]],
                    "Input candidate IDs or BM25 order differ from external holdout")
        selected = [q for q in claims if q["benchmark"] == benchmark]
        primary = {q["id"]: q["ranking"] for q in selected if q["status"] == "complete"}
        scalar = {q["id"]: q["supplemental_ranking"] for q in selected
                  if q["status"] in ("complete", "complete_scalar_only")} if model == "jev-1.13.0" else None
        baseline = {qid: [d["id"] for d in q["documents"]] for qid, q in holdout["queries"].items()}
        benchmarks[benchmark] = {"qrel_query_denominator": expected_count, "query_status_counts": dict(Counter(q["status"] for q in selected)),
                                 "strict_complete_queries": len(primary), "scalar_complete_queries": len(scalar) if scalar is not None else None,
                                 "primary_strict": ndcg_at_k(primary, holdout["qrels"], 10),
                                 "supplemental_actual_scalar": ndcg_at_k(scalar, holdout["qrels"], 10) if scalar is not None else None,
                                 "downloaded_bm25_baseline": ndcg_at_k(baseline, holdout["qrels"], 10)}
        input_hashes[f"{benchmark}/manifest.json"] = sha(path.read_bytes())
        for name, expected in holdout["manifest"]["files_sha256"].items():
            input_hashes[f"{benchmark}/{name}"] = expected
    def combined(field):
        return sum(b[field]["value"] * b["qrel_query_denominator"] for b in benchmarks.values()) / 97
    return {"schema_version": 1, "status": "complete" if finished else "partial", "model": model,
            "runner_status": status, "protocol": runner.PROTOCOL, "qrel_query_denominator": 97,
            "metrics_are_provisional_lower_bounds": not finished,
            "interpretation": ("Finished collection; strict failures contribute zero under the predeclared full-qrel metric."
                               if finished else "Partial collection. Missing, pending, ongoing and incomplete queries contribute zero to these provisional lower bounds; these are not complete model results."),
            "query_status_counts": counts, "replayed_collection_counts": actual_counts, "benchmarks": benchmarks,
            "combined_query_weighted": {"primary_strict_ndcg_at_10": combined("primary_strict"),
                                        "supplemental_actual_scalar_ndcg_at_10": combined("supplemental_actual_scalar") if model == "jev-1.13.0" else None,
                                        "downloaded_bm25_ndcg_at_10": combined("downloaded_bm25_baseline")},
            "raw_snapshot": {"reported_attempts": len(reported_ids), "captured_requests": len(request_ids), "captured_samples": len(sample_ids),
                             "unscored_request_tail": len(request_ids) - len(reported_ids),
                             "reported_requests_without_returned_samples": unavailable},
            "input_and_raw_sha256": input_hashes, "replay_source_sha256": source_hashes,
            "limitations": ["Direct qrel grades, not exponential gains. Full official qrels, including judgments outside top100, define ideal DCG.",
                            "Only complete strict queries contribute to primary results. Jev mass-only supplemental rankings stay separate; other failed/incomplete queries contribute zero.",
                            "Adaptive later windows differ by provider even with identical initial candidates. Integer OpenAI grades and Jev expected Scores have different resolution.",
                            "Downloaded BM25 arithmetic is not a rerun of retrieval. No provider call, qrel-guided inference, probability renormalization or replay latency measurement occurred.",
                            "Raw inputs and responses remain private; this summary contains only IDs, hashes, counts and derived metrics."],
            "new_provider_calls": 0, "qrels_passed_to_inference": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--holdout-root", type=Path, default=ROOT / "runs/external/ir-holdout/prepared")
    parser.add_argument("--input-sha256", default=INPUT_SHA256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(args.run, {name: args.holdout_root / name / "manifest.json" for name in MANIFEST_SHA256}, input_sha256=args.input_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "output": str(args.output), "model": result["model"]}))


if __name__ == "__main__":
    main()
