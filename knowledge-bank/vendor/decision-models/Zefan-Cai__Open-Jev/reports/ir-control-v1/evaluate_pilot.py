"""Replay recorded Jev decisions for the frozen six-query original IR holdout.

No network calls or surrogate responses. Partial pairwise/setwise probes do not
contain the adaptive comparisons needed to reconstruct a complete heap run.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import compile_request
from jev.data import read_jsonl
from jev.ir_eval import RerankFailure, ndcg_at_k, rerank
from verify import verify

PILOT_SHA256 = "beb827c63486e776d6d1abc0d178f557394dbebe57de72523ff4c3112f17d73b"
RANKING_METHODS = ("pointwise_noul", "pointwise_score", "listwise_choice", "listwise_score")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evaluate(pilot, run):
    require(sha(pilot / "manifest.json") == PILOT_SHA256, "Frozen pilot manifest differs")
    audit = verify(pilot)
    queries = {q["id"]: q for q in read_jsonl(pilot / "queries.jsonl") if q["split"] in ("test", "ood")}
    cases = {"ir-pilot-" + c["id"]: c for c in read_jsonl(pilot / "cases.jsonl") if c["query_id"] in queries}
    workloads = json.loads((run / "requests.json").read_text())["workloads"]
    require(len(workloads) == len(cases) == 132, "Expected exactly 132 frozen pilot request cases")
    require(len(queries) == 6 and len({q["group_id"] for q in queries.values()}) == 3, "Pilot holdout family coverage differs")
    require(len({w["id"] for w in workloads}) == len(workloads) and {w["id"] for w in workloads} == set(cases), "Request IDs differ")
    request_hashes = {}
    for work in workloads:
        require(work["request"] == cases[work["id"]]["request"], "Provider request differs from frozen case")
        request_hashes[work["id"]] = digest(work["request"])
        require(work["request_sha256"] == request_hashes[work["id"]], "Request hash differs")
    recorded = list(read_jsonl(run / "samples.jsonl"))
    require(len(recorded) == len(cases) and len({s["request_id"] for s in recorded}) == len(recorded), "Missing or repeated provider sample")
    require({s["request_id"] for s in recorded} == set(cases), "Provider sample IDs differ")
    samples, mass_failures, score_differences = {}, [], Counter()
    for sample in recorded:
        identifier = sample["request_id"]
        require(sample["request_sha256"] == request_hashes[identifier], "Sample/request identity differs")
        require(sample["phase"] == "measured" and sample["repetition"] == 0, "Unexpected run phase or repetition")
        require(sample["http_status"] == 200, "This frozen run is expected to contain 132 HTTP 200 responses")
        require(json.loads(sample["raw_response"]) == sample["response"], "Raw and parsed response differ")
        require(set(sample["response"]["answers"]) == set(cases[identifier]["request"]["questions"]), "Typed answer coverage differs")
        samples[identifier] = sample
        for question, answer in sample["response"]["answers"].items():
            if "probabilities" in answer:
                mass = sum(answer["probabilities"].values())
                if not math.isclose(mass, 1., rel_tol=0, abs_tol=1e-6):
                    mass_failures.append({"request_id": identifier, "question_id": question, "mass": mass})
                if answer["type"] == "score":
                    expected = sum(int(level) * p for level, p in answer["probabilities"].items())
                    score_differences[round(answer["score"] - expected, 6)] += 1
    qrels = {qid: query["reference_relevance"] for qid, query in queries.items()}

    def metrics(rankings):
        return {"ndcg_at_10": ndcg_at_k(rankings, qrels, 10),
                "best_passage_at_1": sum(bool(rankings.get(qid)) and judgments[rankings[qid][0]] == max(judgments.values())
                                          for qid, judgments in qrels.items()) / len(qrels)}

    methods = {}
    for method in RANKING_METHODS:
        rankings, details = {}, {}
        for qid, query in queries.items():
            available = {request_hashes[rid]: rid for rid, case in cases.items() if case["query_id"] == qid and case["method"] == method}
            consumed = []

            def replay(request):
                key = digest(request)
                require(key in available, "Algorithm asked for an unrecorded request; no oracle fallback is allowed")
                identifier = available[key]
                require(identifier not in consumed, "Algorithm repeated an unrecorded adaptive request")
                consumed.append(identifier)
                return samples[identifier]["response"]

            try:
                result = rerank(query["query"], query["documents"], method, replay, score_rounding_digits=2)
                require(len(consumed) == len(available), "Algorithm did not consume all requests for this method")
                rankings[qid] = result["ranking"]
                details[qid] = {"status": "complete", "ranking": result["ranking"],
                                "ranked_grades": [qrels[qid][doc] for doc in result["ranking"]], "recorded_request_ids": consumed}
            except RerankFailure as error:
                details[qid] = {"status": "failed_strict_validation", "reason": str(error.__cause__), "recorded_request_ids_attempted": consumed}
        methods[method] = {"completed_queries": len(rankings), "query_denominator": len(queries),
                           **metrics(rankings), "queries": details}

    # Supplemental observation, explicitly bypassing probability validation:
    # scalar Score fields can still be sorted without repairing their vectors.
    scalar_observations = {}
    for method in ("pointwise_score", "listwise_score"):
        rankings = {}
        for qid, query in queries.items():
            scalar = {}
            for identifier, case in cases.items():
                if case["query_id"] != qid or case["method"] != method:
                    continue
                heads = compile_request(**case["request"])
                for doc, head in zip(case["document_ids"], heads):
                    value = samples[identifier]["response"]["answers"][head["id"]]["score"]
                    require(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 3, "Invalid raw scalar Score")
                    scalar[doc] = value
            initial = [doc["id"] for doc in query["documents"]]
            require(set(scalar) == set(initial), "Incomplete raw scalar coverage")
            rankings[qid] = sorted(initial, key=lambda doc: -scalar[doc])
        scalar_observations[method] = {**metrics(rankings), "rankings": rankings}

    files = {"pilot_manifest": pilot / "manifest.json", "pilot_queries": pilot / "queries.jsonl",
             "pilot_cases": pilot / "cases.jsonl", "provider_requests": run / "requests.json", "provider_samples": run / "samples.jsonl",
             "evaluator": Path(__file__), "reranker": ROOT / "jev/ir_eval.py", "independent_auditor": Path(__file__).with_name("verify.py")}
    return {"schema_version": 1, "status": "recorded_provider_decisions_evaluated", "provider": sorted({s["mode"] for s in recorded}),
            "scope": "Frozen original ir-control-v1-pilot test/OOD only; six queries, three correlated system families, eight candidates per query. Not TREC or a benchmark comparison.",
            "new_network_calls": 0, "qrels_passed_to_reranker": False, "responses_normalized_or_replaced": False,
            "http_requests_recorded": len(recorded), "http_200": len(recorded),
            "typed_answers": sum(len(s["response"]["answers"]) for s in recorded),
            "query_count": len(queries), "group_count": len({q["group_id"] for q in queries.values()}),
            "queries_by_split": dict(Counter(q["split"] for q in queries.values())), "candidate_count_per_query": 8,
            "replay_policy": {"ranking_signal": "Returned scalar noul/score or Choice probability; stable descending ordering.",
                              "probability_mass_absolute_tolerance": 1e-6, "score_rounding_digits": 2,
                              "score_expectation_absolute_tolerance": 0.035,
                              "rounding_bound": "(1 + sum(levels)) * 0.5 * 10^-2; scalar and probability entries independently rounded to two decimals.",
                              "failed_query_policy": "No ranking; zero nDCG contribution with all six qrel queries retained in denominator.",
                              "latency": "Replay CPU timings are not reported as provider or reranking query latency."},
            "probability_mass_failures": mass_failures,
            "score_minus_rounded_probability_expectation_histogram": {str(k): v for k, v in sorted(score_differences.items())},
            "strict_probability_mass_results": methods,
            "raw_scalar_score_observations": {"status": "supplemental_not_strict_protocol_success",
                                               "policy": "Sort finite raw scalar Scores as returned. Does not validate or normalize their probability vectors.",
                                               "methods": scalar_observations},
            "unsupported_full_ranking_from_fixed_probe": {"pairwise": "Only the first two candidates in both orders were probed; adaptive binary-heap comparisons are missing.",
                                                         "setwise": "Only two four-candidate local choices were probed; adaptive 10-child heap comparisons are missing."},
            "input_order_baseline": {"description": "Deterministically shuffled synthetic candidates, not BM25.",
                                     **metrics({qid: [doc["id"] for doc in query["documents"]] for qid, query in queries.items()})},
            "independent_body_audit_status": audit["status"],
            "files": {key: {"path": str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path.resolve()),
                            "sha256": sha(path)} for key, path in files.items()},
            "external_trec_downloaded": False, "external_trec_evaluated": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=ROOT / "data/ir-control-v1-pilot")
    parser.add_argument("--run", type=Path, default=ROOT / "runs/provider-comparison-20260920/jev-ir-pilot")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/ir-control-v1/jev-pilot-ranking.json")
    args = parser.parse_args()
    result = evaluate(args.pilot, args.run)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "query_count": result["query_count"],
                      "strict": {method: {"queries": value["completed_queries"], "ndcg_at_10": value["ndcg_at_10"]["value"]}
                                 for method, value in result["strict_probability_mass_results"].items()},
                      "mass_failures": result["probability_mass_failures"]}, indent=2))


if __name__ == "__main__":
    main()
