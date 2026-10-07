"""Independently recalculate categorical rankings and direct-grade nDCG."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    results = json.loads((HERE / "results.json").read_text())
    pilot = ROOT / "data/ir-control-v1-pilot"
    queries = {q["id"]: q for q in lines(pilot / "queries.jsonl") if q["split"] in ("test", "ood")}
    cases = {"ir-pilot-" + c["id"]: c for c in lines(pilot / "cases.jsonl") if c["query_id"] in queries}
    require(len(queries) == 6 and set(results["providers"]) == {"gpt-5.6-luna", "gpt-6-astra"}, "Report scope differs")
    for file in results["files"].values():
        require(sha(ROOT / file["path"]) == file["sha256"], "Report source hash differs")
    checked, ranking_count, decision_count = [], 0, 0
    for model, provider in results["providers"].items():
        require(set(provider["methods"]) == {"pointwise_noul", "pointwise_score", "listwise_score"}, "Ranking method coverage differs")
        for file in provider["files"].values():
            require(sha(ROOT / file["path"]) == file["sha256"], "Provider source hash differs")
        samples = {s["request_id"]: s for s in lines(ROOT / provider["files"]["samples.jsonl"]["path"])}
        for method, values in provider["methods"].items():
            per_query, correct_first = {}, 0
            for qid, query in queries.items():
                predicted = {}
                used = []
                for rid, case in cases.items():
                    if case["query_id"] != qid or case["method"] != method:
                        continue
                    used.append(rid)
                    raw = json.loads(samples[rid]["raw_response"])
                    texts = [part["text"] for item in raw["output"] if item["type"] == "message"
                             for part in item["content"] if part["type"] == "output_text"]
                    require(len(texts) == 1, "Expected exactly one categorical response")
                    answers = json.loads(texts[0])["answers"]
                    question_ids = (["relevant"] if method == "pointwise_noul" else ["relevance"]
                                    if method == "pointwise_score" else [f"relevance_P{i+1}" for i in range(8)])
                    require(set(answers) == set(question_ids), "Raw question coverage differs")
                    for document, question in zip(case["document_ids"], question_ids):
                        value = answers[question]
                        require((type(value) is bool if method == "pointwise_noul" else
                                 type(value) is int and 0 <= value <= 3), "Invalid categorical signal")
                        require(document not in predicted, "Duplicate candidate")
                        predicted[document] = value
                        decision_count += 1
                initial = [d["id"] for d in query["documents"]]
                ordered = [d for _, _, d in sorted((-int(predicted[d]), index, d) for index, d in enumerate(initial))]
                detail = values["queries"][qid]
                require(detail["ranking"] == ordered and detail["input_order"] == initial and
                        detail["returned_categorical_signals"] == predicted and set(used) == set(detail["recorded_request_ids"]),
                        "Published ranking or signals differ from independently decoded responses")
                grades = query["reference_relevance"]
                actual = math.fsum(grades[d] / math.log2(i + 2) for i, d in enumerate(ordered[:10]))
                ideal = math.fsum(g / math.log2(i + 2) for i, g in enumerate(sorted(grades.values(), reverse=True)[:10]))
                per_query[qid] = actual / ideal
                correct_first += grades[ordered[0]] == max(grades.values())
                ranking_count += 1
                require(math.isclose(per_query[qid], values["ndcg_at_10"]["per_query"][qid], rel_tol=0, abs_tol=1e-12),
                        "Per-query nDCG differs")
            mean = math.fsum(per_query.values()) / len(queries)
            require(math.isclose(mean, values["ndcg_at_10"]["value"], rel_tol=0, abs_tol=1e-12), "Mean nDCG differs")
            require(correct_first / len(queries) == values["best_passage_at_1"], "Best passage metric differs")
            checked.append({"model": model, "method": method, "queries": len(queries), "ndcg_at_10": mean,
                            "best_passage_at_1": correct_first / len(queries)})
    result = {"status": "passed", "independent_rankings_checked": ranking_count,
              "raw_output_decisions_used": decision_count, "metric_absolute_tolerance": 1e-12,
              "checks": ["All evaluator input hashes match", "Raw API output decoded without importing primary evaluator or adapter",
                         "Stable sorting recomputed with explicit original input position", "Direct-grade nDCG recomputed using math.fsum",
                         "Every per-query and aggregate metric agrees"],
              "methods": checked, "results_sha256": sha(HERE / "results.json"), "verifier_sha256": sha(Path(__file__))}
    (HERE / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
