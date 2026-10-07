"""Compare serial questions versus one fan-out request on the same loaded model."""
import argparse
import json
from pathlib import Path
import statistics
import time

from jev.client import Client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8791/v1/systemone")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    request, client = json.loads(args.request.read_text()), Client(args.endpoint)
    client.ask(request["state"], request["questions"])  # warmup, not timed
    timings = {"serial": [], "fanout": []}
    maximum_probability_difference, model = 0.0, None
    for repetition in range(args.repeats):
        responses = {}
        for mode in (("serial", "fanout") if repetition % 2 == 0 else ("fanout", "serial")):
            start = time.perf_counter()
            if mode == "serial":
                answers = {}
                for key, question in request["questions"].items():
                    result = client.ask(request["state"], {key: question})
                    answers.update(result["answers"])
                responses[mode] = answers
            else:
                result = client.ask(request["state"], request["questions"])
                responses[mode] = result["answers"]
            model = result["model"]
            timings[mode].append(time.perf_counter() - start)
        for key, serial in responses["serial"].items():
            fanout = responses["fanout"][key]
            fields = ["noul"] if serial["type"] == "noul" else list(serial["probabilities"])
            a = serial if serial["type"] == "noul" else serial["probabilities"]
            b = fanout if serial["type"] == "noul" else fanout["probabilities"]
            maximum_probability_difference = max(maximum_probability_difference,
                                                  max(abs(a[f] - b[f]) for f in fields))
    medians = {mode: statistics.median(values) for mode, values in timings.items()}
    report = {"model": model, "method": result.get("metadata", {}).get("method"),
              "question_count": len(request["questions"]), "repeats": args.repeats,
              "timings_seconds": timings, "median_seconds": medians,
              "serial_over_fanout": medians["serial"] / medians["fanout"],
              "max_probability_difference": maximum_probability_difference,
              "scope": "Same Open-Jev scorer; HTTP end-to-end; no generative or proprietary Jev comparator."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
