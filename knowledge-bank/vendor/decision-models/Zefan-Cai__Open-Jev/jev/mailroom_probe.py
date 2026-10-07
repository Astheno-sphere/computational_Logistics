"""Export audited holdout requests, or score actual saved API responses.

This module never creates surrogate model answers and does not access an inbox.
The saved workloads run with scripts.benchmark_jev_api_latency.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from .mailroom_audit import parse_visible, verify


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def holdout_cases(directory):
    verify(directory)
    return [case for line in (Path(directory) / "cases.jsonl").read_text().splitlines()
            if (case := json.loads(line))["split"] in ("test", "ood")]


def export(directory):
    cases = holdout_cases(directory)
    if not cases:
        raise ValueError("No held-out cases in this mailroom corpus")
    return {"schema_version": 1, "source": "mailroom-control-v1", "model_inference_performed": False,
            "scope": "All test/OOD requests; all eleven questions. No confidence-based routing labels. One measured call per request is a semantic smoke test, not a latency estimate.",
            "workloads": [{"id": case["id"], "kind": "mailroom_probe", "request": case["request"],
                           "request_sha256": digest(case["request"])} for case in cases]}


def _decision(question, answer):
    if answer.get("type") != question["type"]:
        raise ValueError("Typed answer differs")
    if question["type"] == "noul":
        value = answer.get("noul")
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("Invalid Noul probability")
        return None if value == .5 else value > .5
    probs = answer.get("probabilities")
    if not isinstance(probs, dict) or set(probs) != set(question["criteria"]):
        raise ValueError("Choice probability keys differ")
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in probs.values()):
        raise ValueError("Invalid Choice probability")
    if not math.isclose(sum(probs.values()), 1, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Choice probability mass differs")
    choice = answer.get("choice")
    if choice not in probs or probs[choice] != max(probs.values()):
        raise ValueError("Choice does not select a probability maximum")
    return choice


def evaluate(directory, samples_path):
    cases = {case["id"]: case for case in holdout_cases(directory)}
    samples = [json.loads(line) for line in Path(samples_path).read_text().splitlines()]
    if len(samples) != len(cases) or {sample["request_id"] for sample in samples} != set(cases):
        raise ValueError("Expected exactly one actual sample per held-out request")
    details, by_question, by_language = [], {}, {}
    expected, valid, correct, successful = 0, 0, 0, 0
    for sample in samples:
        case = cases[sample["request_id"]]
        if sample["request_sha256"] != digest(case["request"]) or sample["phase"] != "measured" or sample["repetition"] != 0:
            raise ValueError("Sample identity, phase or repetition differs")
        labels = parse_visible(case["request"])["labels"]
        expected += len(labels)
        result = {"id": case["id"], "language": case["language"], "split": case["split"], "success": False,
                  "category_masked": "category" not in labels, "decisions": []}
        try:
            if sample.get("success") is not True or sample.get("http_status") != 200:
                raise ValueError("Recorded request failed")
            response = sample["response"]
            if json.loads(sample["raw_response"]) != response or set(response["answers"]) != set(case["request"]["questions"]):
                raise ValueError("Raw response or answer coverage differs")
            decisions = {qid: _decision(question, response["answers"][qid]) for qid, question in case["request"]["questions"].items()}
            result["success"] = True
            successful += 1
            for qid, target in labels.items():
                decision = decisions[qid]
                good = decision == target
                valid += 1
                correct += good
                result["decisions"].append({"question_id": qid, "reference": target, "decision": decision, "correct": good})
                for container, key in ((by_question, qid), (by_language, case["language"])):
                    counter = container.setdefault(key, Counter())
                    counter["valid_answers"] += 1
                    counter["correct"] += good
        except (ValueError, KeyError, TypeError) as error:
            result["error"] = str(error)
        details.append(result)
    return {"model_inference_performed": True, "samples_sha256": hashlib.sha256(Path(samples_path).read_bytes()).hexdigest(),
            "requests": len(samples), "successful_typed_requests": successful, "failed_or_invalid_requests": len(samples) - successful,
            "expected_supervised_answers": expected, "valid_answers": valid, "correct": correct,
            "accuracy_on_valid_answers": correct / valid if valid else None,
            "accuracy_including_failed_requests": correct / expected if expected else None,
            "by_question": by_question, "by_language": by_language, "cases": details,
            "scope": "Original finite-grammar holdout only; per-question classification, not end-to-end mail automation. No labels from confidence, routing thresholds, fallback, or offline stubs.",
            "noul_decision_rule": "p(true)>0.5; exact 0.5 is unresolved and scored incorrect. Gold remains the independent visible-text semantic label."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=Path, help="Actual benchmark samples.jsonl; omit to export requests only")
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.data.resolve()):
        parser.error("Use a new output path outside the sealed corpus")
    result = evaluate(args.data, args.samples) if args.samples else export(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "model_inference_performed": result["model_inference_performed"],
                      "requests": result.get("requests", len(result.get("workloads", [])))}))


if __name__ == "__main__":
    main()
