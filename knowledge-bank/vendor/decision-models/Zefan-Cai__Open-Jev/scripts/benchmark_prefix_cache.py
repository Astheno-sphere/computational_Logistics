"""Bounded local checkpoint A/B: identical requests and batch size, cache off/on.

Run from the repository with python -m scripts.benchmark_prefix_cache. This
loads one checkpoint locally; it does not submit jobs or connect to any cluster.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import statistics
import tempfile
import time


def compare_answers(uncached, cached, probability_tolerance):
    left, right = uncached["answers"], cached["answers"]
    ids_equal = list(left) == list(right)
    kinds_equal, candidate_ids_equal, argmax_equal = True, True, True
    maximum_probability_error, maximum_score_error = 0.0, 0.0
    changed_decisions = []
    for question_id in left.keys() & right.keys():
        a, b = left[question_id], right[question_id]
        if a["type"] != b["type"]:
            kinds_equal = False
            continue
        if a["type"] == "noul":
            pa, pb = {"false": 1 - a["noul"], "true": a["noul"]}, {"false": 1 - b["noul"], "true": b["noul"]}
        else:
            pa, pb = a["probabilities"], b["probabilities"]
        if list(pa) != list(pb):
            candidate_ids_equal = False
            continue
        for probabilities in (pa, pb):
            if (any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities.values())
                    or not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6)):
                raise ValueError("invalid response probabilities")
        maximum_probability_error = max(maximum_probability_error, max(abs(pa[key] - pb[key]) for key in pa))
        same = max(pa, key=pa.get) == max(pb, key=pb.get)
        if a["type"] == "noul":
            same = (a["noul"] >= 0.5) == (b["noul"] >= 0.5)
        elif a["type"] == "choice":
            same = same and a["choice"] == b["choice"]
        if not same:
            argmax_equal = False
            changed_decisions.append(question_id)
        if a["type"] == "score":
            maximum_score_error = max(maximum_score_error, abs(a["score"] - b["score"]))
    usage_equal = uncached["usage"] == cached["usage"]
    passed = (ids_equal and kinds_equal and candidate_ids_equal and argmax_equal and usage_equal
              and maximum_probability_error <= probability_tolerance)
    return {"passed": passed, "question_ids_equal": ids_equal, "question_types_equal": kinds_equal,
            "candidate_ids_equal": candidate_ids_equal, "argmax_equal": argmax_equal,
            "usage_equal": usage_equal, "changed_decisions": sorted(changed_decisions),
            "max_probability_error": maximum_probability_error, "max_score_error": maximum_score_error}


def benchmark(predictor, requests, *, repetitions=2, warmup=1, probability_tolerance=1e-4):
    """Measure the real Predictor paths while sharing exactly one loaded model."""
    import torch

    if not 1 <= len(requests) <= 8 or not 1 <= repetitions <= 20 or not 0 <= warmup <= 5:
        raise ValueError("requires 1-8 requests, 1-20 repetitions, and 0-5 warmup passes")
    if not math.isfinite(probability_tolerance) or not 0 <= probability_tolerance <= 1:
        raise ValueError("probability tolerance must be finite and in [0, 1]")
    model = predictor.scorer.model
    device = torch.device(model.device_name)
    if device.type not in ("cpu", "cuda"):
        raise ValueError("benchmark supports CPU and CUDA devices")
    original_mode = predictor.prefix_cache
    samples, comparisons, answers = [], [], {}

    def run(request, enabled, measured):
        predictor.prefix_cache = enabled
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        if not measured:
            predictor.predict(request)
            return None
        observed = {"forward_calls": 0, "processed_input_tokens": 0}

        def count_tokens(module, args, kwargs):
            observed["forward_calls"] += 1
            observed["processed_input_tokens"] += kwargs["input_ids"].numel()

        handle = model.backbone.register_forward_pre_hook(count_tokens, with_kwargs=True)
        memory = None
        try:
            if device.type == "cuda":
                torch.cuda.reset_peak_memory_stats(device)
                memory = {"baseline_allocated": torch.cuda.memory_allocated(device),
                          "baseline_reserved": torch.cuda.memory_reserved(device)}
            start = time.perf_counter()
            response = predictor.predict(request)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            elapsed = time.perf_counter() - start
            if memory is not None:
                memory.update(peak_allocated=torch.cuda.max_memory_allocated(device),
                              peak_reserved=torch.cuda.max_memory_reserved(device))
                memory["additional_peak_allocated"] = memory["peak_allocated"] - memory["baseline_allocated"]
        finally:
            handle.remove()
        sample = {"mode": "cached" if enabled else "uncached", "wall_seconds": elapsed,
                  "logical_input_tokens": response["usage"]["input_tokens"],
                  **observed, "cuda_memory_bytes": memory,
                  "cache_stats": response["metadata"]["prefix_cache"]}
        return response, sample

    try:
        for iteration in range(warmup):
            for index, request in enumerate(requests):
                for enabled in ((False, True) if (iteration + index) % 2 == 0 else (True, False)):
                    run(request, enabled, False)
        for repetition in range(repetitions):
            for index, request in enumerate(requests):
                pair = {}
                for order, enabled in enumerate((False, True) if (repetition + index) % 2 == 0 else (True, False)):
                    response, sample = run(request, enabled, True)
                    sample.update(request_index=index, repetition=repetition, order_in_pair=order)
                    samples.append(sample)
                    pair[sample["mode"]] = response
                check = compare_answers(pair["uncached"], pair["cached"], probability_tolerance)
                check["question_ids_equal"] &= list(pair["cached"]["answers"]) == list(request["questions"])
                check["passed"] &= check["question_ids_equal"]
                comparisons.append({"request_index": index, "repetition": repetition, **check})
                answers[str(index)] = {mode: response["answers"] for mode, response in pair.items()}
    finally:
        predictor.prefix_cache = original_mode
    summaries = []
    for index in range(len(requests)):
        medians = {mode: statistics.median(sample["wall_seconds"] for sample in samples
                                          if sample["request_index"] == index and sample["mode"] == mode)
                   for mode in ("uncached", "cached")}
        summaries.append({"request_index": index, "median_seconds": medians,
                          "uncached_over_cached": medians["uncached"] / medians["cached"]})
    return {"status": "passed" if all(check["passed"] for check in comparisons) else "parity_failed",
            "model": predictor.model_name, "method": predictor.method, "provenance": predictor.provenance,
            "device": str(device), "batch_size": predictor.batch_size, "repetitions": repetitions,
            "warmup_passes_per_mode": warmup, "probability_tolerance": probability_tolerance,
            "samples": samples, "comparisons": comparisons, "request_summaries": summaries,
            "last_answers_by_request_and_mode": answers,
            "scope": "Same checkpoint and Predictor, including tokenization/formatting, excluding model load and HTTP.",
            "measurement_notes": [
                "Cached/uncached execution order alternates within each request across repetitions.",
                "Processed input tokens are independently counted from backbone input shapes, including uncached padding.",
                "Timing includes a lightweight shape-counting forward hook in both modes.",
                "CUDA synchronizes before/after each measured call and resets peak memory before each call.",
                "CUDA allocator reservations persist between modes; both baseline and peak are reported. CPU memory is not measured.",
                "Parity requires matching IDs/types/usage, distribution error within tolerance, and matching decisions; Noul uses p >= 0.5.",
                "Score expected-value differences are reported; the acceptance threshold applies to probabilities and argmax, not absolute Score error.",
                "Token reuse does not guarantee wall-time or memory savings. Evaluate parity before enabling caching.",
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--request", type=Path, action="append", required=True, help="Repeat for up to 8 JSON requests")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--max-probability-error", type=float, default=1e-4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (not 1 <= len(args.request) <= 8 or not 1 <= args.repetitions <= 20
            or not 0 <= args.warmup <= 5 or not 1 <= args.batch_size <= 256):
        parser.error("limits: 1-8 requests, 1-20 repetitions, 0-5 warmups, batch size 1-256")
    if not math.isfinite(args.max_probability_error) or not 0 <= args.max_probability_error <= 1:
        parser.error("max probability error must be finite and in [0, 1]")
    if args.max_length is not None and args.max_length < 1:
        parser.error("max length must be positive")
    output = args.output.resolve()
    if (output.exists() or output in {path.resolve() for path in args.request}
            or output.is_relative_to(args.checkpoint.resolve())):
        parser.error("output must be a new path outside the checkpoint and input request files")
    from jev.api import compile_request
    from jev.server import strict_json
    from jev.serving import load_predictor

    requests, sources = [], []
    for path in args.request:
        if path.stat().st_size > 4 * 1024 * 1024:
            parser.error("request must be at most 4 MiB")
        raw = path.read_bytes()
        request = strict_json(raw)
        compile_request(request["state"], request["questions"])
        requests.append(request)
        sources.append({"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=args.output.parent):
        pass  # Fail before loading model weights if the destination cannot be written.
    predictor = load_predictor(checkpoint=args.checkpoint, device=args.device, max_length=args.max_length,
                               batch_size=args.batch_size, prefix_cache=False)
    report = benchmark(predictor, requests, repetitions=args.repetitions, warmup=args.warmup,
                       probability_tolerance=args.max_probability_error)
    report.update(created_at=datetime.now(timezone.utc).isoformat(), request_sources=sources,
                  runtime={"python": platform.python_version(), "platform": platform.platform(),
                           **{name: importlib.metadata.version(name) for name in ("torch", "transformers", "peft")}})
    with args.output.open("x") as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": report["status"], "output": str(args.output.resolve()),
                      "request_summaries": report["request_summaries"]}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
