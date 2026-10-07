"""Independently check the frozen Jev TREC scores without importing its scorer.

Uses direct stable window sorting and math.fsum DCG. No API, GPU, reranker,
provider adapter, or benchmark scorer is invoked. Output contains no passages.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/provider-trec-20260920/jev-1.13.0"
SUMMARY = RUN.parent / "jev-listwise-summary.json"
HOLDOUT = ROOT / "runs/external/ir-holdout/prepared"
INPUT_SHA = "cc7bc949dbc269dacb61bdb61fc8982db14bc4df3698f9d32f5f1c8b6795eb83"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def left_fold(values):
    total = 0.0
    for value in values:
        total += value
    return total


def verify():
    summary, report, document = read(SUMMARY), read(RUN / "report.json"), read(RUN / "input.json")
    require(sha(RUN / "input.json") == INPUT_SHA == report["input_sha256"], "Frozen input differs")
    require(summary["status"] == "complete" and report["status"] == "completed_with_query_failures", "Run is not final")
    require(summary["model"] == report["model"] == "jev-1.13.0", "Model differs")
    for name in ("input.json", "report.json", "requests.jsonl", "samples.jsonl"):
        require(sha(RUN / name) == summary["input_and_raw_sha256"][name], "Summary raw-file binding differs")
    requests, samples = lines(RUN / "requests.jsonl"), lines(RUN / "samples.jsonl")
    require(len(requests) == len(samples) == 873 and len(document["queries"]) == len(report["queries"]) == 97,
            "Frozen run coverage differs")
    require(len({r["id"] for r in requests}) == len({s["request_id"] for s in samples}) == 873, "Duplicate request")
    sample_index, mass_requests, mass_heads, heads = 0, 0, 0, 0
    diagnostic_algorithms = Counter()
    max_diagnostic_drift = 0.0
    rankings, strict_rankings, query_status = {}, {}, Counter()
    for query, claim in zip(document["queries"], report["queries"]):
        identity = query["benchmark"], query["id"]
        require(identity == (claim["benchmark"], claim["id"]), "Query identity differs")
        ordered = list(query["documents"])
        strict_query = True
        end = 100
        for index in range(9):
            beginning = max(0, end - 20)
            window = ordered[beginning:end]
            saved, sample = requests[sample_index], samples[sample_index]
            sample_index += 1
            identifier = f"{query['benchmark']}:{query['id']}:window-{index}"
            request = saved["request"]
            require(saved["id"] == sample["request_id"] == claim["request_ids"][index] == identifier, "Request order differs")
            require(saved["request_sha256"] == sample["request_sha256"] == digest(request), "Request hash differs")
            require(saved["payload"] == {**request, "model": "jev-1.13.0"} and
                    saved["payload_sha256"] == digest(saved["payload"]), "Payload binding differs")
            require(request["state"] == {"query": query["query"], "passages": {f"P{i+1}": doc["text"] for i, doc in enumerate(window)}},
                    "Actual later window differs from independently sorted candidates")
            require(claim["windows"][index] == {"request_id": identifier, "document_ids": [d["id"] for d in window]},
                    "Saved window IDs differ")
            require(sample["http_status"] == 200 and sample["mode"] == "jev-1.13.0" and sample["phase"] == "measured" and
                    type(sample["repetition"]) is int and sample["repetition"] == 0, "Unexpected HTTP result or phase")
            response = json.loads(sample["raw_response"])
            require(response == sample["response"] and response["model"] == "jev-1.13.0", "Raw response differs")
            answer_ids = [f"relevance_P{i+1}" for i in range(20)]
            require(set(response["answers"]) == set(request["questions"]) == set(answer_ids), "Score head coverage differs")
            scores, failures = [], []
            for qid in answer_ids:
                answer = response["answers"][qid]
                probabilities = answer["probabilities"]
                require(answer["type"] == "score" and set(probabilities) == {"0", "1", "2", "3"}, "Score type/levels differ")
                require(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in probabilities.values()), "Invalid probability")
                score = answer["score"]
                require(type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 3, "Invalid scalar")
                mass = math.fsum(probabilities.values())
                expectation = math.fsum(int(level) * p for level, p in probabilities.items())
                require(mass > 0 and math.isclose(score, expectation, rel_tol=0, abs_tol=.035 + 1e-12), "Invalid mass or expectation")
                if not math.isclose(mass, 1, rel_tol=0, abs_tol=1e-6):
                    failures.append(qid)
                scores.append(score)
                heads += 1
            validation = claim["request_validations"][index]
            require(validation["transport_success"] is True and validation["scalar_usable"] is True and
                    validation["strict_valid"] is (not failures), "Saved strict/scalar flags differ")
            if failures:
                strict_query = False
                mass_requests += 1
                mass_heads += len(failures)
                require(sample["success"] is False and sample["error"] == "probabilities do not sum to one", "Supplemental eligibility differs")
                details = validation["strict_probability_mass_failure"]
                require([d["question_id"] for d in details] == failures, "Mass diagnostic identity/order differs")
                for detail in details:
                    answer = response["answers"][detail["question_id"]]
                    probs = answer["probabilities"]
                    saved_pair = detail["mass"], detail["raw_probability_expectation"]
                    current = sum(probs.values()), sum(int(k) * p for k, p in probs.items())
                    legacy = left_fold(probs.values()), left_fold(int(k) * p for k, p in probs.items())
                    require(detail["score"] == answer["score"] and saved_pair in (current, legacy), "Diagnostic is not exact current/legacy arithmetic")
                    diagnostic_algorithms["both" if saved_pair == current == legacy else "current_only" if saved_pair == current else "legacy_only"] += 1
                    max_diagnostic_drift = max(max_diagnostic_drift, *(abs(a - b) for a, b in zip(saved_pair, current)))
            else:
                require(sample["success"] is True, "Strict-valid response was not successful")
            ordered[beginning:end] = [window[i] for i in sorted(range(20), key=lambda i: (-scores[i], i))]
            end -= 10
        ranking = [d["id"] for d in ordered]
        require(claim["strict_query_valid"] is strict_query and claim["supplemental_ranking"] == ranking, "Whole-query validity/ranking differs")
        require(claim["ranking"] == (ranking if strict_query else None), "Primary ranking promotes a strict failure")
        require(claim["status"] == ("complete" if strict_query else "complete_scalar_only"), "Query status differs")
        rankings[identity] = ranking
        if strict_query:
            strict_rankings[identity] = ranking
        query_status[claim["status"]] += 1
    require(dict(query_status) == summary["query_status_counts"], "Summary query counts differ")
    counts = {"http_200": sample_index, "transport_errors": 0, "strict_valid_requests": sample_index - mass_requests,
              "strict_validation_failures": mass_requests, "scalar_usable_requests": sample_index,
              "strict_complete_queries": len(strict_rankings), "scalar_complete_queries": len(rankings)}
    require(counts == report["collection_counts"] == summary["replayed_collection_counts"], "Collection counters differ")
    benchmarks = {}
    metric_error = 0.0
    for benchmark, count in (("dl19", 43), ("dl20", 54)):
        directory = HOLDOUT / benchmark
        manifest = read(directory / "manifest.json")
        require(sha(directory / "manifest.json") == summary["input_and_raw_sha256"][f"{benchmark}/manifest.json"], "Manifest binding differs")
        for name, expected in manifest["files_sha256"].items():
            require(sha(directory / name) == expected == summary["input_and_raw_sha256"][f"{benchmark}/{name}"], "External data hash differs")
        qrels = defaultdict(dict)
        for line in (directory / "qrels.txt").read_text().splitlines():
            qid, _, doc, grade = line.split()
            require(doc not in qrels[qid], "Duplicate qrel")
            qrels[qid][doc] = int(grade)
        require(len(qrels) == count and set(qrels) == {qid for b, qid in rankings if b == benchmark}, "Full qrel denominator differs")
        candidate_rows = {q["id"]: q for q in lines(directory / "candidates.jsonl")}
        values = {"primary_strict": {}, "supplemental_actual_scalar": {}, "downloaded_bm25_baseline": {}}
        for qid, judgments in qrels.items():
            ideal = math.fsum(g / math.log2(i + 2) for i, g in enumerate(sorted((max(g, 0) for g in judgments.values()), reverse=True)[:10]))
            selected = {"primary_strict": strict_rankings.get((benchmark, qid), []),
                        "supplemental_actual_scalar": rankings[benchmark, qid],
                        "downloaded_bm25_baseline": [d["id"] for d in candidate_rows[qid]["documents"]]}
            for method, ranking in selected.items():
                value = math.fsum(max(0, judgments.get(doc, 0)) / math.log2(i + 2) for i, doc in enumerate(ranking[:10])) / ideal if ideal else 0.0
                values[method][qid] = value
                delta = abs(value - summary["benchmarks"][benchmark][method]["per_query"][qid])
                require(delta <= 1e-12, "Per-query nDCG differs")
                metric_error = max(metric_error, delta)
        means = {method: math.fsum(rows.values()) / count for method, rows in values.items()}
        require(all(abs(value - summary["benchmarks"][benchmark][method]["value"]) <= 1e-12 for method, value in means.items()), "Mean nDCG differs")
        benchmarks[benchmark] = {"qrel_query_denominator": count, "qrel_rows": sum(map(len, qrels.values())),
                                 "strict_complete_queries": sum(b == benchmark for b, _ in strict_rankings),
                                 "scalar_complete_queries": count, **means}
    combined = {output: math.fsum(row[method] * row["qrel_query_denominator"] for row in benchmarks.values()) / 97
                for method, output in (("primary_strict", "primary_strict_ndcg_at_10"),
                                       ("supplemental_actual_scalar", "supplemental_actual_scalar_ndcg_at_10"),
                                       ("downloaded_bm25_baseline", "downloaded_bm25_ndcg_at_10"))}
    require(all(abs(value - summary["combined_query_weighted"][name]) <= 1e-12 for name, value in combined.items()),
            "Combined weighted nDCG differs")
    return {"schema_version": 1, "status": "passed", "provider": "jev-1.13.0", "new_api_calls": 0, "new_gpu_inference": False,
            "independence": "Does not import the runner, provider adapter, reranker or scorer. Independently sorts actual raw scalar window outputs and computes direct-grade DCG with math.fsum.",
            "requests_checked": 873, "score_heads_checked": heads, "query_count": 97,
            "strict_probability_mass_failed_requests": mass_requests, "strict_probability_mass_failed_heads": mass_heads,
            "query_status_counts": dict(query_status), "benchmarks": benchmarks, "combined_query_weighted": combined,
            "maximum_per_query_ndcg_difference": metric_error, "ndcg_audit_absolute_tolerance": 1e-12,
            "mass_diagnostic_arithmetic": {"entries_by_exact_match": dict(diagnostic_algorithms),
                                           "maximum_current_recomputation_difference": max_diagnostic_drift,
                                           "finding": "Saved diagnostic pairs are exact legacy left-fold results. No response, scalar, ranking, strict flag or validation tolerance changed."},
            "protocol_tolerances_unchanged": {"probability_mass_absolute": 1e-6, "score_expectation_absolute": .035},
            "summary_sha256": sha(SUMMARY), "auditor_sha256": sha(Path(__file__)),
            "input_and_raw_sha256": summary["input_and_raw_sha256"],
            "limitations": ["Primary nDCG includes zero contribution from the 66 strict-invalid queries; supplemental scalar nDCG remains a separate analysis.",
                            "This confirms saved-run arithmetic and evidence consistency, not provider superiority or replicated author settings.",
                            "Raw passages, requests and responses are not included in this public audit."]}


if __name__ == "__main__":
    result = verify()
    output = Path(__file__).with_name("jev-result-independent-audit.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(output), "status": result["status"], "benchmarks": result["benchmarks"],
                      "mass_diagnostic_arithmetic": result["mass_diagnostic_arithmetic"]}, indent=2))
