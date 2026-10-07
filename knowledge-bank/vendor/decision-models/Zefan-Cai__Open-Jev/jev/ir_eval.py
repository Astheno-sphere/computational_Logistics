"""Executable typed reranking and isolated graded-relevance evaluation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

from .api import compile_request
from .ir_data import pairwise, pointwise, window_request

METHODS = ("pointwise_noul", "pointwise_score", "pairwise", "setwise", "listwise_choice", "listwise_score")
GENERAL_LEVELS = ["Unrelated to the query.", "On the query's topic but does not answer it.",
                  "Provides useful information that partially answers the query.", "Directly and comprehensively answers the query."]


class RerankFailure(ValueError):
    def __init__(self, message, trace):
        super().__init__(message)
        self.trace = trace


def _request(query, texts, mode, profile):
    if profile == "original-control-v1":
        if mode.startswith("pointwise_"):
            return pointwise(query, texts[0], mode.removeprefix("pointwise_"))
        if mode == "pairwise":
            return pairwise(query, texts[0], texts[1])
        return window_request(query, texts, "score" if mode == "listwise_score" else "choice")
    if profile != "general-ir-v1":
        raise ValueError("Unknown request profile")
    if mode.startswith("pointwise_"):
        state = {"query": query, "passage": texts[0]}
        questions = ({"relevant": {"type": "noul", "instructions": "Does the passage contain information that answers the query?"}} if mode.endswith("noul") else
                     {"relevance": {"type": "score", "instructions": "How relevant is the passage to the query?", "criteria": GENERAL_LEVELS}})
    elif mode == "pairwise":
        state = {"query": query, "passage_A": texts[0], "passage_B": texts[1]}
        questions = {"more_relevant": {"type": "choice", "instructions": "Which passage provides more useful information for answering the query?",
                                        "criteria": {"A": "Passage A", "B": "Passage B"}}}
    else:
        state = {"query": query, "passages": {f"P{i+1}": text for i, text in enumerate(texts)}}
        questions = ({f"relevance_{label}": {"type": "score", "instructions": f"How relevant is passage {label} to the query?", "criteria": GENERAL_LEVELS}
                      for label in state["passages"]} if mode == "listwise_score" else
                     {"most_relevant": {"type": "choice", "instructions": "Which passage is most useful for answering the query?", "criteria": {label: None for label in state["passages"]}}})
    return {"state": state, "questions": questions}


def _number(value, lower, upper):
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError("Invalid typed numeric answer")
    return float(value)


def _answers(request, response, score_rounding_digits=None):
    if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
        raise ValueError("Missing typed answers")
    compiled = compile_request(**request)
    if set(response["answers"]) != {row["id"] for row in compiled}:
        raise ValueError("Question/answer coverage differs")
    result = {}
    for row in compiled:
        answer = response["answers"][row["id"]]
        if answer.get("type") != row["kind"]:
            raise ValueError("Answer type differs")
        if row["kind"] == "noul":
            result[row["id"]] = _number(answer.get("noul"), 0, 1)
        elif row["kind"] == "score":
            value = _number(answer.get("score"), 0, len(row["options"]) - 1)
            if "probabilities" in answer:
                probs = _distribution(answer["probabilities"], row["answer_keys"])
                # A provider may round the scalar and each probability separately.
                # Bound their combined error; probability mass remains strict.
                tolerance = (1e-6 if score_rounding_digits is None else
                             0.5 * 10 ** (-score_rounding_digits) * (1 + sum(range(len(probs)))) + 1e-12)
                if not math.isclose(value, sum(i * p for i, p in enumerate(probs)), rel_tol=0, abs_tol=tolerance):
                    raise ValueError("Score differs from its probability expectation")
            result[row["id"]] = value
        else:
            result[row["id"]] = _distribution(answer.get("probabilities"), row["answer_keys"])
    return result


def _distribution(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("Choice probability keys differ")
    probabilities = [_number(value[key], 0, 1) for key in keys]
    if not math.isclose(sum(probabilities), 1.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Choice probabilities do not sum to one")
    return probabilities


def rerank(query, documents, method, predict, *, top_k=10, window_size=20, step_size=10, children=10,
           request_profile="original-control-v1", score_rounding_digits=None):
    """Run actual callback decisions; no qrels or synthetic oracle are consulted."""
    if method not in METHODS or not isinstance(query, str) or not query.strip():
        raise ValueError("Unknown method or empty query")
    if request_profile not in ("original-control-v1", "general-ir-v1"):
        raise ValueError("Unknown request profile")
    if score_rounding_digits is not None and (type(score_rounding_digits) is not int or not 0 <= score_rounding_digits <= 12):
        raise ValueError("Score rounding digits must be an integer from zero to twelve, or None for exact checks")
    if not 1 <= len(documents) <= 100 or any(not isinstance(doc, dict) or not isinstance(doc.get("id"), str) or not doc["id"] or not isinstance(doc.get("text"), str) or not doc["text"].strip() for doc in documents):
        raise ValueError("Provide one to one hundred identified passages")
    if len({doc["id"] for doc in documents}) != len(documents):
        raise ValueError("Duplicate document ID")
    if type(top_k) is not int or top_k < 1 or type(children) is not int or not 2 <= children <= 99:
        raise ValueError("Invalid top_k or heap fanout")
    if type(window_size) is not int or type(step_size) is not int or not 2 <= window_size <= 100 or not 1 <= step_size <= window_size:
        raise ValueError("Invalid listwise window or step")
    trace, initial = [], {doc["id"]: i for i, doc in enumerate(documents)}
    start = time.perf_counter()

    def ask(subset, mode):
        request = _request(query, [doc["text"] for doc in subset], mode, request_profile)
        entry = {"request": request, "document_ids": [doc["id"] for doc in subset], "response": None}
        trace.append(entry)
        started = time.perf_counter()
        try:
            entry["response"] = predict(request)
            entry["callback_seconds"] = time.perf_counter() - started
            return _answers(request, entry["response"], score_rounding_digits)
        except Exception as error:
            entry.setdefault("callback_seconds", time.perf_counter() - started)
            entry["error_type"] = type(error).__name__
            raise RerankFailure("Reranking callback or typed-answer validation failed", trace) from error

    ranked = list(documents)
    if len(ranked) > 1 and method.startswith("pointwise_"):
        scores = [next(iter(ask([doc], method).values())) for doc in ranked]
        ranked = [ranked[i] for i in sorted(range(len(ranked)), key=lambda i: (-scores[i], i))]
    elif len(ranked) > 1 and method in ("pairwise", "setwise"):
        heap, chosen = list(ranked), []

        def better(first, second):
            original = ask([first, second], "pairwise")["more_relevant"][0]
            reverse = ask([second, first], "pairwise")["more_relevant"][0]
            preference = (original + 1.0 - reverse) / 2.0
            return initial[first["id"]] < initial[second["id"]] if math.isclose(preference, 0.5, abs_tol=1e-12) else preference > 0.5

        fanout = 2 if method == "pairwise" else children

        def sift(index):
            while fanout * index + 1 < len(heap):
                positions = [index] + list(range(fanout * index + 1, min(fanout * index + fanout + 1, len(heap))))
                if method == "pairwise":
                    best = index
                    for candidate in positions[1:]:
                        if better(heap[candidate], heap[best]):
                            best = candidate
                else:
                    probabilities = ask([heap[pos] for pos in positions], "setwise")["most_relevant"]
                    best = positions[max(range(len(positions)), key=lambda i: probabilities[i])]
                if best == index:
                    return
                heap[index], heap[best] = heap[best], heap[index]
                index = best

        for index in range((len(heap) - 2) // fanout, -1, -1):
            sift(index)
        for _ in range(min(top_k, len(heap))):
            chosen.append(heap[0])
            last = heap.pop()
            if heap:
                heap[0] = last
                sift(0)
        selected = {doc["id"] for doc in chosen}
        ranked = chosen + [doc for doc in documents if doc["id"] not in selected]
    elif len(ranked) > 1:
        end = len(ranked)
        while end > 1:
            beginning = max(0, end - window_size)
            subset = ranked[beginning:end]
            answers = ask(subset, method)
            scores = answers["most_relevant"] if method == "listwise_choice" else [answers[f"relevance_P{i+1}"] for i in range(len(subset))]
            ranked[beginning:end] = [subset[i] for i in sorted(range(len(subset)), key=lambda i: (-scores[i], i))]
            if beginning == 0:
                break
            end -= step_size
    return {"method": method, "request_profile": request_profile, "ranking": [doc["id"] for doc in ranked],
            "score_rounding_digits": score_rounding_digits, "probability_mass_tolerance": 1e-6,
            "reranked_depth": min(top_k, len(ranked)) if method in ("pairwise", "setwise") else len(ranked),
            "requests": len(trace), "query_wall_seconds": time.perf_counter() - start,
            "callback_seconds": [entry["callback_seconds"] for entry in trace], "trace": trace,
            "tie_rule": "Original input order for pointwise and exact pairwise ties; current window order for listwise/setwise ties."}


def ndcg_at_k(rankings, qrels, k=10):
    if type(k) is not int or k < 1 or not isinstance(qrels, dict) or not qrels:
        raise ValueError("A positive cutoff and nonempty qrels are required")
    values = {}
    for query_id, judgments in qrels.items():
        if not judgments or any(type(grade) is not int or not -1 <= grade <= 3 for grade in judgments.values()):
            raise ValueError("Expected explicit integer grades from zero to three, or minus one for unjudged")
        run = rankings.get(query_id, [])
        if len(run) != len(set(run)):
            raise ValueError("Duplicate document in ranking")
        # trec_eval ndcg_cut uses the qrel value directly, not 2**grade - 1.
        gains = [max(0, judgments.get(doc, 0)) for doc in run[:k]]
        ideal = sorted((max(0, grade) for grade in judgments.values()), reverse=True)[:k]
        dcg = sum(gain / math.log2(i + 2) for i, gain in enumerate(gains))
        denominator = sum(gain / math.log2(i + 2) for i, gain in enumerate(ideal))
        values[query_id] = dcg / denominator if denominator else 0.0
    return {"metric": f"nDCG@{k}", "value": sum(values.values()) / len(values), "per_query": values,
            "qrel_query_denominator": len(values), "missing_run_queries": sorted(set(qrels) - set(rankings)),
            "unjudged_gain": 0, "gain": "qrel grade, matching trec_eval ndcg_cut", "ignored_run_queries_without_qrels": sorted(set(rankings) - set(qrels))}


def load_external_holdout(manifest_path):
    """Read only prepared, hashed TREC evaluation files; never emit training rows."""
    path = Path(manifest_path).resolve()
    training_root = (Path(__file__).resolve().parents[1] / "data").resolve()
    if path.is_relative_to(training_root):
        raise ValueError("External TREC holdout must live outside the training data tree")
    manifest = json.loads(path.read_text())
    if manifest.get("usage") != "evaluation_only" or manifest.get("benchmark") not in ("TREC-DL19", "TREC-DL20"):
        raise ValueError("Expected an explicitly isolated external evaluation manifest")
    if manifest.get("retriever") != {"name": "BM25", "top_k": 100, "k1": 0.9, "b": 0.4}:
        raise ValueError("Expected declared BM25 top-100 settings")
    if set(manifest.get("files_sha256", {})) != {"candidates.jsonl", "qrels.txt"}:
        raise ValueError("Expected candidates.jsonl and qrels.txt with SHA-256")
    for name, digest in manifest["files_sha256"].items():
        artifact = (path.parent / name).resolve()
        if artifact.is_relative_to(training_root) or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
            raise ValueError("Holdout artifact location or checksum differs")
    queries = {}
    for line in (path.parent / "candidates.jsonl").read_text().splitlines():
        row = json.loads(line)
        if set(row) != {"id", "query", "documents"} or not isinstance(row["id"], str) or not row["id"] or row["id"] in queries or not isinstance(row["query"], str) or not row["query"].strip():
            raise ValueError("Invalid holdout query")
        docs = row["documents"]
        if len(docs) != 100 or len({doc["id"] for doc in docs}) != 100:
            raise ValueError("Every holdout query must contain exactly 100 unique BM25 candidates")
        for rank, doc in enumerate(docs, 1):
            if set(doc) != {"id", "text", "bm25_rank", "bm25_score"} or not isinstance(doc["id"], str) or not doc["id"] or type(doc["bm25_rank"]) is not int or doc["bm25_rank"] != rank or not isinstance(doc["text"], str) or not doc["text"].strip():
                raise ValueError("Invalid ranked holdout candidate")
            _number(doc["bm25_score"], -1e20, 1e20)
        queries[row["id"]] = row
    qrels = {}
    for line in (path.parent / "qrels.txt").read_text().splitlines():
        query_id, _, document_id, grade = line.split()
        grade = int(grade)
        if not -1 <= grade <= 3 or document_id in qrels.setdefault(query_id, {}):
            raise ValueError("Invalid or duplicate external qrel")
        qrels[query_id][document_id] = grade
    if not queries or not qrels:
        raise ValueError("Empty external holdout")
    return {"manifest": manifest, "queries": queries, "qrels": qrels, "usage": "evaluation_only",
            "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "missing_candidate_queries": sorted(set(qrels) - set(queries))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-holdout", required=True, type=Path)
    args = parser.parse_args()
    result = load_external_holdout(args.check_holdout)
    print(json.dumps({"status": "verified_inputs_only", "usage": result["usage"], "benchmark": result["manifest"]["benchmark"],
                      "query_count": len(result["queries"]), "qrel_query_count": len(result["qrels"]),
                      "manifest_sha256": result["manifest_sha256"], "model_evaluation_performed": False}, indent=2))


if __name__ == "__main__":
    main()
