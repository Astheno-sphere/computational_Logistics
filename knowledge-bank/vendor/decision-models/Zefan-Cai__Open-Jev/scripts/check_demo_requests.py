"""Run committed examples against a real service and retain all responses.

This is interface/inference coverage, not a semantic accuracy benchmark.
"""
import argparse
import json
from pathlib import Path
import time

from jev.api import compile_request, format_response
from jev.client import Client


def validate_answer(request, response):
    records = compile_request(request["state"], request["questions"])
    probabilities = []
    for record in records:
        answer = response["answers"][record["id"]]
        if answer["type"] != record["kind"]:
            raise ValueError("answer type mismatch")
        if record["kind"] == "noul":
            probabilities.append([1 - answer["noul"], answer["noul"]])
        else:
            if set(answer["probabilities"]) != set(record["answer_keys"]):
                raise ValueError("answer candidates mismatch")
            probabilities.append([answer["probabilities"][key] for key in record["answer_keys"]])
    expected = format_response(records, probabilities)["answers"]
    for key, answer in expected.items():
        actual = response["answers"][key]
        if answer["type"] == "choice" and answer["choice"] != actual["choice"]:
            raise ValueError("chosen action differs from maximum probability")
        if answer["type"] == "score" and abs(answer["score"] - actual["score"]) > 1e-6:
            raise ValueError("score differs from expected level")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--examples", type=Path, default=Path("examples"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    client, results, skipped = Client(args.endpoint), [], []
    with args.output.open("w") as handle:
        for path in sorted(args.examples.rglob("*.json")):
            request = json.loads(path.read_text())
            if not isinstance(request, dict) or not {"state", "questions"} <= request.keys():
                skipped.append(str(path))
                continue
            start = time.perf_counter()
            row = {"example": str(path), "question_count": len(request["questions"])}
            try:
                response = client.ask(request["state"], request["questions"])
                validate_answer(request, response)
                row.update(status="passed", response=response)
            except Exception as error:
                row.update(status="failed", error=str(error))
            row["elapsed_seconds"] = time.perf_counter() - start
            results.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            print(json.dumps({k: row[k] for k in ("example", "status", "elapsed_seconds")}), flush=True)
    summary = {"check": "real_model_interface_smoke_not_accuracy", "requests": len(results),
               "passed": sum(r["status"] == "passed" for r in results), "skipped_nonrequests": skipped,
               "output": str(args.output)}
    args.output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    if not results or any(r["status"] != "passed" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
