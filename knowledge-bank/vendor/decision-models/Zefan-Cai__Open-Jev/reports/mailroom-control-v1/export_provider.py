"""Bind provider-independent mailroom gold to the frozen 87-request probe."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jev.api import compile_request
from jev.mailroom_audit import parse_visible, sha, verify
from jev.mailroom_probe import digest


def build(data, requests, output):
    data, requests, output = Path(data), Path(requests), Path(output)
    audit = verify(data)
    if output.exists():
        raise ValueError("Choose a new provider output directory")
    raw_requests = requests.read_bytes()
    workloads = json.loads(raw_requests)["workloads"]
    cases = {case["id"]: case for line in (data / "cases.jsonl").read_text().splitlines()
             if (case := json.loads(line))["split"] in ("test", "ood")}
    records = {row["id"]: row for split in ("test", "ood")
               for line in (data / (split + ".jsonl")).read_text().splitlines() if (row := json.loads(line))}
    if len(workloads) != len(cases) or {work["id"] for work in workloads} != set(cases):
        raise ValueError("Frozen request coverage differs from audited holdout")
    golds, masked = [], []
    for work in workloads:
        case = cases[work["id"]]
        if work["request"] != case["request"] or work["request_sha256"] != digest(case["request"]):
            raise ValueError("Frozen provider request differs from audited case")
        labels = parse_visible(work["request"])["labels"]
        row_ids = iter(case["record_ids"])
        for compiled in compile_request(**work["request"]):
            qid = compiled["id"]
            if qid not in labels:
                masked.append({"request_id": work["id"], "question_id": qid, "reason": case["masked_questions"][qid]})
                continue
            row = records[next(row_ids)]
            answer = str(labels[qid]).lower() if compiled["kind"] == "noul" else labels[qid]
            target = [float(key == answer) for key in compiled["answer_keys"]]
            if row["target"] != target:
                raise ValueError("Stored target differs from body-derived provider gold")
            golds.append({"request_id": work["id"], "question_id": qid, "record_id": row["id"],
                          "kind": compiled["kind"], "target": target, "answer_keys": compiled["answer_keys"],
                          "source": "mailroom/" + qid, "language": case["language"], "split": case["split"],
                          "group_id": case["group_id"], "request_sha256": work["request_sha256"], "row_sha256": digest(row)})
    output.mkdir(parents=True)
    (output / "requests.json").write_bytes(raw_requests)
    (output / "gold.json").write_text(json.dumps({"schema_version": 1, "rows": golds}, ensure_ascii=False, indent=2) + "\n")
    manifest = {"schema_version": 1, "source_manifest_sha256": audit["manifest_sha256"],
                "requests": len(workloads), "runtime_questions": sum(len(work["request"]["questions"]) for work in workloads),
                "decisions": len(golds), "masked_questions": masked, "only_test_and_ood": True,
                "request_source_file": "reports/mailroom-control-v1/probe-requests.json",
                "request_source_sha256": hashlib.sha256(raw_requests).hexdigest(),
                "scope": "Original finite-grammar mailroom controls. Gold independently derived from visible email; no model/threshold/fallback labels. Cross-provider Noul classification follows the common runner's argmax(false,true), including false for exact ties. The standalone mailroom evaluator instead marks exact ties unresolved; do not conflate the reports.",
                "files": {name: sha(output / name) for name in ("gold.json", "requests.json")}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--requests", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build(args.data, args.requests, args.output)
    print(json.dumps({key: manifest[key] for key in ("requests", "runtime_questions", "decisions", "request_source_sha256")}))


if __name__ == "__main__":
    main()
