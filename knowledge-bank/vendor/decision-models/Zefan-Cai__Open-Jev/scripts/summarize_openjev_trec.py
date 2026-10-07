"""Audit saved Open-Jev TREC windows and score complete qrels without inference."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from jev.ir_eval import RerankFailure, _answers, load_external_holdout, ndcg_at_k, rerank
from jev.server import strict_json
from scripts import evaluate_openjev_provider as client
from scripts import evaluate_openjev_trec as runner
from scripts import evaluate_trec_provider as input_loader
from scripts.summarize_trec_provider import INPUT_SHA256, MANIFEST_SHA256

ROOT = Path(__file__).resolve().parents[1]
FINAL = {"complete", "completed_with_query_failures"}
PARTIAL = {"stopped_budget", "stopped_fatal", "interrupted_or_failed"}


class AuditError(ValueError):
    pass


class Boundary(ValueError):
    pass


class RecordedFailure(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AuditError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def wire(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def records(raw, key):
    rows = [strict_json(line) for line in raw.splitlines() if line.strip()]
    require(all(isinstance(row, dict) and isinstance(row.get(key), str) for row in rows), "Invalid journal row")
    ids = [row[key] for row in rows]
    require(len(set(ids)) == len(ids), "Duplicate journal identity")
    return ids, dict(zip(ids, rows))


def replay_query(query, claim, requests, samples, expected):
    ids = claim["request_ids"]
    require(ids == [f"{query['benchmark']}:{query['id']}:window-{i}" for i in range(len(ids))]
            and len(ids) <= 9, "Query window IDs differ")
    consumed, failed = [], []

    def replay(request):
        if len(consumed) == len(ids):
            raise Boundary("No further recorded request")
        identifier = ids[len(consumed)]
        consumed.append(identifier)
        saved, sample = requests[identifier], samples[identifier]
        payload = {**request, "model": "open-jev"}
        require(wire(saved["request"]) == wire(request) and saved["request_sha256"] == client.digest(request),
                "Adaptive request content, order or hash differs")
        require(wire(saved["payload"]) == wire(payload) and saved["payload_sha256"] == client.digest(payload),
                "Open-Jev wire payload differs")
        require(sample.get("request_id") == identifier and sample.get("request_sha256") == saved["request_sha256"]
                and sample.get("mode") == expected["model"] and sample.get("phase") == "measured"
                and type(sample.get("repetition")) is int and sample["repetition"] == 0
                and type(sample.get("success")) is bool, "Sample identity or attempt contract differs")
        if "response" in sample:
            require(wire(strict_json(sample["raw_response"])) == wire(sample["response"]), "Raw and parsed response differ")
        mandatory_fatal = (sample.get("http_status") is not None and sample["http_status"] not in (200, 400, 413, 422)) or sample.get("error_type") in {
            "IdentityError", "KeyboardInterrupt", "TimeoutError", "OSError", "ConnectionError", "ConnectionRefusedError",
            "ConnectionResetError", "ConnectionAbortedError", "BrokenPipeError", "HTTPException", "RemoteDisconnected",
            "IncompleteRead", "BadStatusLine"}
        if not sample["success"] and sample.get("http_status") == 200 and "response" in sample:
            try:
                client.validate_response(request, sample["response"], expected)
            except client.IdentityError:
                mandatory_fatal = True
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
        require(not mandatory_fatal or sample.get("fatal") is True, "Mandatory fatal response was treated as nonfatal")
        if not sample["success"]:
            failed.append(sample)
            raise RecordedFailure("Recorded unsuccessful response")
        require(sample.get("http_status") == 200 and not sample.get("fatal"), "Successful sample has an error status")
        try:
            client.validate_response(request, sample["response"], expected)
            _answers(request, sample["response"], score_rounding_digits=None)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise AuditError("Successful response fails strict Open-Jev validation") from error
        return sample["response"]

    result, failure = None, None
    try:
        result = rerank(query["query"], query["documents"], "listwise_score", replay,
                        request_profile="general-ir-v1", window_size=20, step_size=10,
                        top_k=100, score_rounding_digits=None)
        trace = result["trace"]
    except RerankFailure as error:
        failure, trace = error.__cause__, error.trace
        if isinstance(failure, AuditError):
            raise failure
    require(consumed == ids, "Replay did not consume every recorded query window")
    require(claim["windows"] == [{"request_id": rid, "document_ids": entry["document_ids"]}
                                  for rid, entry in zip(ids, trace)], "Adaptive window membership differs")
    status, ranking = claim["status"], claim["ranking"]
    if status == "complete":
        require(result is not None and len(ids) == 9 and ranking == result["ranking"]
                and claim["strict_query_valid"] is True, "Complete ranking is not supported by replay")
        require(len(ranking) == 100 and len(set(ranking)) == 100
                and set(ranking) == {d["id"] for d in query["documents"]}, "Ranking is not a full permutation")
    else:
        require(ranking is None, "Incomplete or failed query contains a ranking")
        if status in ("failed", "failed_fatal"):
            require(isinstance(failure, RecordedFailure) and len(failed) == 1
                    and claim["strict_query_valid"] is False, "Failed query has no recorded failed response")
            require((status == "failed_fatal") == bool(failed[0].get("fatal")), "Fatal query classification differs")
        elif status == "pending":
            require(not ids and claim["strict_query_valid"] is None, "Pending query contains an attempted request")
        else:
            require(status in ("incomplete_budget", "interrupted") and isinstance(failure, Boundary)
                    and (claim["strict_query_valid"] is None or claim["strict_query_valid"] is False), "Invalid incomplete query state")
    return len(ids), sum(samples[rid]["success"] for rid in ids)


def summarize(run_dir, holdout_paths, *, input_sha256=INPUT_SHA256, manifest_sha256=MANIFEST_SHA256):
    run_dir = Path(run_dir)
    paths = {name: run_dir / name for name in ("input.json", "report.json", "requests.jsonl", "samples.jsonl")}
    snapshots = {name: path.read_bytes() for name, path in paths.items()}
    document, raw = input_loader.load_input(paths["input.json"], input_sha256)
    require(raw == snapshots["input.json"], "Input changed while capturing evidence")
    report = strict_json(snapshots["report.json"])
    expected = report["expected_identity"]
    client.validate_identity_config(expected)
    client.local_endpoint(report["endpoint"])
    require(report.get("schema_version") == 1 and report.get("usage") == "evaluation_only"
            and report.get("model") == expected["model"] and report.get("input_sha256") == input_sha256
            and report.get("protocol") == input_loader.PROTOCOL, "Runner report contract differs")
    for key, value in (("qrels_read", False), ("truncation_applied_by_runner", False),
                       ("prefix_cache", False), ("new_accuracy_metrics", False), ("concurrency", 1), ("warmups", 0), ("retries", 0),
                       ("score_rounding_digits", None), ("probability_mass_absolute_tolerance", 1e-6)):
        require(type(report.get(key)) is type(value) and report[key] == value, "Collection protocol differs: " + key)
    source_paths = {"runner": Path(runner.__file__), "client": Path(client.__file__),
                    "input_loader": Path(input_loader.__file__), "reranker": ROOT / "jev/ir_eval.py"}
    source_hashes = {key: sha(path.read_bytes()) for key, path in source_paths.items()}
    require(report.get("source_sha256") == source_hashes, "Collector source or dependency differs")
    status = report["status"]
    require(status in FINAL | PARTIAL, "Collection must be stopped before scoring")
    limits = report["limits"]
    require(type(limits.get("max_requests")) is int and 1 <= limits["max_requests"] <= 873
            and all(type(limits.get(key)) in (int, float) and math.isfinite(limits[key]) and 0 < limits[key] <= cap
                    for key, cap in (("timeout", 300), ("max_seconds", 10800))), "Collection limits differ")
    claims = report["queries"]
    require(len(claims) == 97 and [(q["benchmark"], q["id"]) for q in claims]
            == [(q["benchmark"], q["id"]) for q in document["queries"]], "Full query identities/order differ")
    request_ids, requests = records(snapshots["requests.jsonl"], "id")
    sample_ids, samples = records(snapshots["samples.jsonl"], "request_id")
    require(request_ids == sample_ids == [rid for q in claims for rid in q["request_ids"]],
            "Unsettled, missing or reordered dispatch journal; no scores may be published")
    require(all(type(report[key]) is int for key in ("started_requests", "attempted_requests", "in_flight_requests",
                                                    "successful_requests", "failed_requests", "planned_queries",
                                                    "planned_max_requests", "pending_queries"))
            and report["started_requests"] == report["attempted_requests"] == len(request_ids)
            and report["in_flight_requests"] == 0 and len(request_ids) <= limits["max_requests"]
            and report["planned_queries"] == 97 and report["planned_max_requests"] == 873,
            "Attempt counts or planned coverage differ")
    stopped = False
    for claim in claims:
        require(not stopped or claim["status"] == "pending", "Processed query appears after the serial collection stopped")
        if claim["status"] not in ("complete", "failed"):
            stopped = True
    counts = dict(Counter(q["status"] for q in claims))
    pending = sum(counts.get(name, 0) for name in ("pending", "running", "incomplete_budget", "interrupted"))
    require(report["query_status_counts"] == counts and report["pending_queries"] == pending,
            "Query status aggregates differ")
    fatal_positions = [i for i, rid in enumerate(sample_ids) if samples[rid].get("fatal")]
    require(not fatal_positions or (fatal_positions == [len(sample_ids) - 1] and status == "stopped_fatal"),
            "Requests continued after a fatal response")
    if status == "stopped_fatal":
        require(len(fatal_positions) == 1 and counts.get("failed_fatal", 0) == 1, "Fatal stop lacks its final failed request")
    if status == "stopped_budget":
        require(pending > 0 and not any(counts.get(name) for name in ("failed_fatal", "interrupted")),
                "Budget stop query classification differs")
    if status == "complete":
        require(counts == {"complete": 97}, "Complete collection contains failed or pending queries")
    elif status == "completed_with_query_failures":
        require(set(counts) <= {"complete", "failed"} and counts.get("failed", 0) > 0,
                "Completed-with-failures collection is unfinished")
    successful = 0
    for query, claim in zip(document["queries"], claims):
        _, valid = replay_query(query, claim, requests, samples, expected)
        successful += valid
    require(report["successful_requests"] == successful and report["failed_requests"] == len(samples) - successful,
            "Success/failure counts differ")

    benchmarks, hashes = {}, {name: sha(raw) for name, raw in snapshots.items()}
    for benchmark, count in (("dl19", 43), ("dl20", 54)):
        path = Path(holdout_paths[benchmark])
        require(sha(path.read_bytes()) == manifest_sha256[benchmark], "Frozen external manifest differs")
        holdout = load_external_holdout(path)
        require(holdout["manifest"]["benchmark"] == "TREC-" + benchmark.upper(), "Wrong external benchmark")
        prepared = {q["id"]: q for q in document["queries"] if q["benchmark"] == benchmark}
        require(len(prepared) == count and set(prepared) == set(holdout["queries"]) == set(holdout["qrels"]),
                "Full official qrel query coverage differs")
        for qid, query in prepared.items():
            require([d["id"] for d in query["documents"]]
                    == [d["id"] for d in holdout["queries"][qid]["documents"]], "BM25 input candidate order differs")
        selected = [q for q in claims if q["benchmark"] == benchmark]
        rankings = {q["id"]: q["ranking"] for q in selected if q["status"] == "complete"}
        baseline = {qid: [d["id"] for d in q["documents"]] for qid, q in holdout["queries"].items()}
        benchmarks[benchmark] = {"qrel_query_denominator": count, "strict_complete_queries": len(rankings),
                                 "query_status_counts": dict(Counter(q["status"] for q in selected)),
                                 "primary_strict": ndcg_at_k(rankings, holdout["qrels"], 10),
                                 "downloaded_bm25_baseline": ndcg_at_k(baseline, holdout["qrels"], 10)}
        hashes[benchmark + "/manifest.json"] = sha(path.read_bytes())
        hashes.update({benchmark + "/" + name: value for name, value in holdout["manifest"]["files_sha256"].items()})
    require(all(path.read_bytes() == snapshots[name] for name, path in paths.items()), "Run changed during offline audit")
    finished = status in FINAL
    return {"schema_version": 1, "status": "complete" if finished else "partial", "runner_status": status,
            "model": expected["model"], "expected_identity": expected, "protocol": input_loader.PROTOCOL,
            "query_status_counts": counts, "qrel_query_denominator": 97, "benchmarks": benchmarks,
            "metrics_are_provisional_lower_bounds": not finished,
            "combined_query_weighted": {"primary_strict_ndcg_at_10": sum(b["primary_strict"]["value"] * b["qrel_query_denominator"] for b in benchmarks.values()) / 97},
            "raw_snapshot": {"requests": len(request_ids), "samples": len(sample_ids), "successful_requests": successful,
                             "failed_requests": len(samples) - successful, "in_flight_requests": 0},
            "input_and_raw_sha256": hashes, "replay_source_sha256": {**source_hashes, "scorer": sha(Path(__file__).read_bytes())},
            "limitations": ["Full official qrels and direct grade gains; judgments outside BM25 top100 remain in ideal DCG.",
                            "Only complete strict queries receive primary rankings. Failed/incomplete/pending queries contribute zero to the full43/54query denominator.",
                            "Actual Open-Jev expected Scores, with no rounding or renormalization; exact ties preserve current window order.",
                            "Partial collection metrics are provisional lower bounds, not complete model results.",
                            "Saved BM25 is not a new retrieval run. Raw passages, requests and responses stay private."],
            "new_provider_calls": 0, "qrels_passed_to_inference": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--holdout-root", type=Path, default=ROOT / "runs/external/ir-holdout/prepared")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize(args.run, {name: args.holdout_root / name / "manifest.json" for name in MANIFEST_SHA256})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "model", "runner_status")}))


if __name__ == "__main__":
    main()
