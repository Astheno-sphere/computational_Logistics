"""Audit and replay saved OpenAI categorical decisions on the frozen IR pilot.

No API calls. Boolean Noul and integer Score outputs are sorted as returned;
categorical Choice winners cannot reconstruct a full ranking.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "reports/ir-control-v1"))
from jev.api import compile_request
from jev.data import read_jsonl
from jev.ir_eval import ndcg_at_k, rerank
from scripts.benchmark_openai_api import MODEL_SETTINGS, payload_for, validate
from scripts.benchmark_inference_latency import digest
from verify import verify

PILOT_SHA256 = "beb827c63486e776d6d1abc0d178f557394dbebe57de72523ff4c3112f17d73b"
METHODS = ("pointwise_noul", "pointwise_score", "listwise_score")
MODELS = ("gpt-5.6-luna", "gpt-6-astra")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def file_record(path):
    return {"path": str(path.absolute().relative_to(ROOT)), "sha256": sha(path)}


def evaluate_model(model, queries, cases, suite, qrels):
    run = ROOT / "runs/provider-comparison-20260920" / f"openai-{model}-ir-pilot-v1"
    audit_path = ROOT / "reports/provider-comparison-20260920" / f"openai-{model}-ir-pilot-audit.json"
    audit, report = read(audit_path), read(run / "report.json")
    require(audit["status"] == report["status"] == "passed", "Provider run or prior audit did not pass")
    require(audit["model"] == report["model"] == model, "Provider model differs")
    require(sha(ROOT / "scripts/benchmark_openai_api.py") == audit["source_sha256"] == report["source_sha256"],
            "Original API adapter source differs")
    for name in ("requests.json", "payloads.json", "samples.jsonl", "report.json"):
        require(sha(run / name) == audit["raw_file_sha256"][name], "Raw audited file differs: " + name)
    for name, expected in suite["files"].items():
        require(sha(ROOT / "data/provider-ir-pilot-v1" / name) == expected, "Frozen provider suite differs")
    require(audit["gold_sha256"] == suite["files"]["gold.json"], "Prior quality audit used different gold")
    require(sha(run / "requests.json") == suite["files"]["requests.json"], "Run requests differ from frozen suite")
    workloads = read(run / "requests.json")["workloads"]
    require(digest(workloads) == audit["workload_manifest_sha256"] == report["workload_manifest_sha256"],
            "Workload manifest identity differs")
    require(len(workloads) == 132 and len({w["id"] for w in workloads}) == 132 and
            {w["id"] for w in workloads} == set(cases), "Request coverage differs")
    payload_rows = read(run / "payloads.json")
    require(len(payload_rows) == 132 and len({p["id"] for p in payload_rows}) == 132 and
            {p["id"] for p in payload_rows} == set(cases), "Payload coverage differs")
    payloads = {p["id"]: p["payload"] for p in payload_rows}
    request_hashes = {}
    for workload in workloads:
        identifier, request = workload["id"], workload["request"]
        require(request == cases[identifier]["request"], "Provider request differs from frozen pilot")
        request_hashes[identifier] = digest(request)
        require(workload["request_sha256"] == request_hashes[identifier], "Request hash differs")
        require(payloads[identifier] == payload_for(request, model, report["configuration"]["max_output_tokens"]),
                "Actual payload differs from original adapter contract")
        require(json.loads(payloads[identifier]["input"]) == request and set(request) == {"state", "questions"},
                "Payload input contains something other than frozen state/questions")
    recorded = list(read_jsonl(run / "samples.jsonl"))
    require(len(recorded) == 132 and len({s["request_id"] for s in recorded}) == 132 and
            {s["request_id"] for s in recorded} == set(cases), "Missing or duplicate provider sample")
    samples = {}
    for sample in recorded:
        identifier = sample["request_id"]
        require(sample["phase"] == "measured" and sample["repetition"] == 0 and
                sample["success"] is True and sample["http_status"] == 200 and sample["mode"] == model,
                "Unexpected sample phase, repetition, success, status, or model")
        require(sample["request_sha256"] == request_hashes[identifier] and
                sample["payload_sha256"] == digest(payloads[identifier]), "Sample identity differs")
        require(json.loads(sample["raw_response"]) == sample["response"], "Raw and parsed responses differ")
        response = sample["response"]
        require(response["reasoning"]["effort"] == MODEL_SETTINGS[model]["reasoning"], "Reasoning setting differs")
        require(validate(cases[identifier]["request"], response, model) == sample["decisions"],
                "Saved decisions differ from validated raw categorical output")
        samples[identifier] = sample

    methods = {}
    used_requests = set()
    for method in METHODS:
        rankings, details = {}, {}
        for qid, query in queries.items():
            available = {request_hashes[rid]: rid for rid, case in cases.items()
                         if case["query_id"] == qid and case["method"] == method}
            expected_requests = 8 if method.startswith("pointwise_") else 1
            require(len(available) == expected_requests, "Incomplete frozen ranking requests")
            consumed, signals = [], {}

            def replay(request):
                key = digest(request)
                require(key in available, "Reranker requested an unrecorded request")
                identifier = available[key]
                require(identifier not in consumed, "Reranker repeated an unrecorded request")
                consumed.append(identifier)
                heads = compile_request(**request)
                documents = cases[identifier]["document_ids"]
                require(len(heads) == len(documents), "Decision/document coverage differs")
                answers = {}
                for document, head in zip(documents, heads):
                    value = samples[identifier]["decisions"][head["id"]]
                    require(document not in signals, "Duplicate document decision")
                    signals[document] = value
                    # This changes only the scalar envelope expected by rerank.
                    # Boolean false/true becomes ordering keys 0/1, not probability.
                    kind = head["kind"]
                    require(kind in ("noul", "score"), "Unsupported categorical ranking head")
                    answers[head["id"]] = {"type": kind, kind: int(value)}
                return {"answers": answers}

            result = rerank(query["query"], query["documents"], method, replay)
            initial = [d["id"] for d in query["documents"]]
            require(len(consumed) == len(available) and set(signals) == set(initial), "Incomplete ranking coverage")
            independent_order = sorted(initial, key=lambda document: -int(signals[document]))
            require(result["ranking"] == independent_order, "Reranker differs from stable categorical sorting")
            rankings[qid] = result["ranking"]
            used_requests.update(consumed)
            counts = Counter(signals.values())
            details[qid] = {"status": "complete", "split": query["split"], "group_id": query["group_id"],
                            "ranking": result["ranking"], "ranked_grades": [qrels[qid][d] for d in result["ranking"]],
                            "input_order": initial, "returned_categorical_signals": signals,
                            "distinct_signals": len(counts), "tied_document_pairs": sum(n * (n - 1) // 2 for n in counts.values()),
                            "recorded_request_ids": consumed}
        methods[method] = {"completed_queries": len(rankings), "query_denominator": len(queries),
                           "http_requests_used": sum(len(q["recorded_request_ids"]) for q in details.values()),
                           "document_decisions_used": sum(len(q["returned_categorical_signals"]) for q in details.values()),
                           "ndcg_at_10": ndcg_at_k(rankings, qrels, 10),
                           "best_passage_at_1": sum(qrels[qid][ranking[0]] == max(qrels[qid].values())
                                                    for qid, ranking in rankings.items()) / len(qrels),
                           "queries": details}
    return {"model": model, "reasoning_effort": MODEL_SETTINGS[model]["reasoning"], "status": "passed",
            "http_requests_audited": len(recorded), "typed_decisions_audited": sum(len(s["decisions"]) for s in recorded),
            "http_requests_used_for_full_rankings": len(used_requests), "methods": methods,
            "files": {name: file_record(run / name) for name in ("requests.json", "payloads.json", "samples.jsonl", "report.json")} |
                     {"prior_quality_audit": file_record(audit_path)}}


def evaluate():
    pilot = ROOT / "data/ir-control-v1-pilot"
    require(sha(pilot / "manifest.json") == PILOT_SHA256, "Frozen pilot manifest differs")
    body_audit = verify(pilot)
    suite = read(ROOT / "data/provider-ir-pilot-v1/manifest.json")
    require(suite["source_manifest_sha256"] == PILOT_SHA256 and suite["requests"] == 132 and
            suite["decisions"] == 174 and suite["only_test_and_ood"] is True, "Provider suite source differs")
    queries = {q["id"]: q for q in read_jsonl(pilot / "queries.jsonl") if q["split"] in ("test", "ood")}
    cases = {"ir-pilot-" + c["id"]: c for c in read_jsonl(pilot / "cases.jsonl") if c["query_id"] in queries}
    require(len(queries) == 6 and len({q["group_id"] for q in queries.values()}) == 3 and len(cases) == 132,
            "Expected six queries, three families, and 132 requests")
    qrels = {qid: query["reference_relevance"] for qid, query in queries.items()}
    providers = {model: evaluate_model(model, queries, cases, suite, qrels) for model in MODELS}
    files = {"pilot_manifest": pilot / "manifest.json", "pilot_queries": pilot / "queries.jsonl",
             "pilot_cases": pilot / "cases.jsonl", "provider_manifest": ROOT / "data/provider-ir-pilot-v1/manifest.json",
             "provider_gold": ROOT / "data/provider-ir-pilot-v1/gold.json", "evaluator": Path(__file__),
             "reranker": ROOT / "jev/ir_eval.py", "request_generator": ROOT / "jev/ir_data.py",
             "request_compiler": ROOT / "jev/api.py", "openai_adapter": ROOT / "scripts/benchmark_openai_api.py",
             "independent_body_auditor": ROOT / "reports/ir-control-v1/verify.py"}
    return {"schema_version": 1, "status": "passed", "new_network_calls": 0, "new_gpu_inference": False,
            "scope": "Frozen original IR pilot test/OOD: six queries from three correlated synthetic families, eight candidates per query. Not TREC or a broad IR benchmark.",
            "query_count": 6, "group_count": 3, "candidate_count_per_query": 8,
            "queries_by_split": dict(Counter(q["split"] for q in queries.values())),
            "body_audit_status": body_audit["status"], "providers": providers,
            "ranking_policy": {"signal": "Actual categorical Boolean Noul or integer 0..3 Score outputs.",
                               "tie_rule": "Stable original candidate input order; listwise has one eight-document window.",
                               "noul_interpretation": "true ranks above false; 0/1 are ordering keys, not estimated probabilities.",
                               "qrels_passed_to_reranker": False, "probability_vectors_fabricated": False,
                               "responses_normalized_or_replaced": False,
                               "metric_gain": "Direct qrel grades, matching trec_eval ndcg_cut; no exponential gain.",
                               "missing_query_policy": "All six qrel queries retained in nDCG denominator; this replay has complete coverage.",
                               "latency": "CPU replay timings are omitted; not a new provider latency measurement."},
            "unsupported_full_ranking_from_fixed_probe": {
                "listwise_choice": "Only one winning candidate was returned; remaining candidate order is unobserved.",
                "pairwise": "Only two local comparisons were recorded; adaptive heap comparisons are missing.",
                "setwise": "Only two local four-candidate choices were recorded; adaptive heap comparisons are missing."},
            "limitations": ["Categorical Noul cannot distinguish the relevance grades of false candidates; graded nDCG depends on input-order ties even when every Boolean is correct.",
                            "OpenAI categorical Score and Jev scalar expected Score or Noul probabilities have different ranking resolution. These replays do not establish overall provider superiority.",
                            "No new requests, full TREC evaluation, candidate permutations, or repeated trials were performed."],
            "input_order_baseline": {"description": "Deterministically shuffled synthetic candidates, not BM25.",
                                     "ndcg_at_10": ndcg_at_k({qid: [d["id"] for d in q["documents"]] for qid, q in queries.items()}, qrels, 10)},
            "files": {name: file_record(path) for name, path in files.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("results.json"))
    args = parser.parse_args()
    result = evaluate()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({model: {method: {"ndcg_at_10": values["ndcg_at_10"]["value"],
                                      "best_passage_at_1": values["best_passage_at_1"],
                                      "completed_queries": values["completed_queries"]}
                              for method, values in provider["methods"].items()}
                      for model, provider in result["providers"].items()}, indent=2))


if __name__ == "__main__":
    main()
