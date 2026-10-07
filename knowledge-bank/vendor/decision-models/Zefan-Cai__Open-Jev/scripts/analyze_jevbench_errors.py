"""Summarize development errors without copying benchmark text or gold answers."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def analyze(report, outcomes=None):
    raw = Path(report).read_bytes()
    aggregate = json.loads(raw)
    families = []
    for name, result in aggregate["per_family"].items():
        n, correct = result["n_planned"], result["n_correct"]
        families.append({"family": name, "n": n, "correct": correct, "errors": n - correct,
                         "accuracy": correct / n if n else None})
    result = {"schema_version": 1, "scope": "231 public JevBench decisions used as development feedback; not sealed evaluation",
              "model": aggregate["model"], "checkpoint": aggregate["checkpoint"], "aggregate_sha256": hashlib.sha256(raw).hexdigest(),
              "errors_by_family": sorted(families, key=lambda x: (-x["errors"], x["family"])),
              "raw_error_analysis": "not_available" if outcomes is None else "supplied_outcomes",
              "original_control_families": ["timeline", "state_tracking", "authorization", "negation", "numeric_candidates", "policy_distractors"],
              "restriction": "Aggregate family names inform new original scenarios. No benchmark text, labels, or sealed material is copied into training."}
    if outcomes:
        records = [json.loads(line) for line in Path(outcomes).read_text().splitlines() if line.strip()]
        # Accept explicit booleans only, never guess correctness from missing fields.
        if any(type(x.get("correct")) is not bool for x in records):
            raise ValueError("Each outcome must supply an explicit correctness boolean")
        result["raw_outcomes_sha256"] = hashlib.sha256(Path(outcomes).read_bytes()).hexdigest()
        result["raw_error_counts"] = dict(Counter(x.get("family", "unclassified") for x in records if not x["correct"]))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="reports/new27b-jevbench-20260922/report.json")
    parser.add_argument("--outcomes")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(analyze(args.report, args.outcomes), stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
