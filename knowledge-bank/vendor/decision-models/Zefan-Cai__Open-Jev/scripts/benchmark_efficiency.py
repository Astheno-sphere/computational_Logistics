"""Measure explicit inference acceleration, correctness and decision boundaries.

Run as python -m scripts.benchmark_efficiency. Checkpoint measurements include
tokenization and response formatting, but exclude network transport. GPU kernel
fixtures are reported separately and cannot establish whole-model speedups.
"""
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import http.client
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import threading
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    left, right = math.floor(position), math.ceil(position)
    return ordered[left] + (ordered[right] - ordered[left]) * (position - left)


def compare_responses(reference, accelerated, tolerance=1e-4,
                      thresholds=(0.2, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99)):
    """Strict coverage/order, finite distributions, decisions and threshold audit."""
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 1:
        raise ValueError("probability tolerance must be finite and in [0, 1]")
    if not thresholds or any(not math.isfinite(t) or not 0 <= t <= 1 for t in thresholds):
        raise ValueError("thresholds must be nonempty and in [0, 1]")
    left, right = reference["answers"], accelerated["answers"]
    if list(left) != list(right):
        raise ValueError("response question coverage/order differs")
    error, score_error, changes, boundaries = 0.0, 0.0, [], []
    flips = {str(t): {"candidate_probability": 0, "confidence_coverage": 0, "noul_true": 0}
             for t in thresholds}
    for question, a in left.items():
        b = right[question]
        if a["type"] != b["type"]:
            raise ValueError("response question type differs")
        if a["type"] == "noul":
            pa, pb = {"false": 1 - a["noul"], "true": a["noul"]}, {"false": 1 - b["noul"], "true": b["noul"]}
            decision_a, decision_b = a["noul"] >= .5, b["noul"] >= .5
        else:
            pa, pb = a["probabilities"], b["probabilities"]
            decision_a, decision_b = max(pa, key=pa.get), max(pb, key=pb.get)
            if a["type"] == "choice" and (a["choice"] != decision_a or b["choice"] != decision_b):
                raise ValueError("choice does not match first probability argmax")
        if list(pa) != list(pb):
            raise ValueError("response candidate coverage/order differs")
        for values in (pa, pb):
            if (not values or any(not math.isfinite(p) or not 0 <= p <= 1 for p in values.values())
                    or not math.isclose(sum(values.values()), 1, abs_tol=1e-6)):
                raise ValueError("response probability distribution is invalid")
        error = max(error, max(abs(pa[k] - pb[k]) for k in pa))
        if decision_a != decision_b:
            changes.append(question)
        ordered = sorted(pa.values(), reverse=True)
        boundary = {"question": question, "top_two_margin": ordered[0] - ordered[1] if len(ordered) > 1 else 1.0,
                    "min_candidate_threshold_margin": min(abs(p - t) for p in pa.values() for t in thresholds),
                    "min_confidence_threshold_margin": min(abs(max(pa.values()) - t) for t in thresholds)}
        if a["type"] == "noul":
            boundary["binary_decision_margin"] = abs(a["noul"] - .5)
        if a["type"] == "score":
            if not math.isfinite(a["score"]) or not math.isfinite(b["score"]):
                raise ValueError("score expectation must be finite")
            score_error = max(score_error, abs(a["score"] - b["score"]))
        boundaries.append(boundary)
        for threshold in thresholds:
            f = flips[str(threshold)]
            f["candidate_probability"] += sum((pa[k] >= threshold) != (pb[k] >= threshold) for k in pa)
            f["confidence_coverage"] += (max(pa.values()) >= threshold) != (max(pb.values()) >= threshold)
            if a["type"] == "noul":
                f["noul_true"] += (a["noul"] >= threshold) != (b["noul"] >= threshold)
    total_flips = sum(sum(counts.values()) for counts in flips.values())
    usage_equal = reference.get("usage") == accelerated.get("usage")
    return {"passed": error <= tolerance and not changes and not total_flips and usage_equal,
            "max_probability_error": error, "max_score_expectation_error": score_error,
            "changed_decisions": changes, "decision_change_count": len(changes),
            "threshold_flips": flips, "threshold_flip_count": total_flips,
            "boundary_margins": boundaries, "usage_equal": usage_equal,
            "probability_tolerance": tolerance}


def source_hash():
    root = Path(__file__).resolve().parents[1]
    files = [Path(__file__), root / "jev/fast_backend.py", root / "jev/serving.py"]
    files += list((root / "jev/kernels").glob("*.py"))
    files += [p for p in (root / "third_party/open_jev_fast").rglob("*")
              if p.is_file() and p.suffix in (".py", ".cu", ".cpp", ".json")]
    return digest({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)})


def environment(device):
    import torch
    packages = {}
    for package in ("torch", "transformers", "peft", "triton", "flash-linear-attention", "safetensors"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    info = {"python": platform.python_version(), "platform": platform.platform(),
            "packages": packages, "device": str(device), "cuda_runtime": torch.version.cuda,
            "source_sha256": source_hash()}
    if device.type == "cuda":
        props = torch.cuda.get_device_properties(device)
        info.update(gpu=props.name, compute_capability=list(torch.cuda.get_device_capability(device)),
                    gpu_total_bytes=props.total_memory,
                    tf32_matmul=torch.backends.cuda.matmul.allow_tf32,
                    tf32_cudnn=torch.backends.cudnn.allow_tf32)
        try:
            info["cuda_driver"] = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                text=True, timeout=10).splitlines()[0].strip()
        except (OSError, subprocess.SubprocessError, IndexError):
            info["cuda_driver"] = None
        nvcc = str(Path(os.environ["CUDA_HOME"]) / "bin/nvcc") if os.environ.get("CUDA_HOME") else "nvcc"
        try:
            info["cuda_compiler"] = subprocess.check_output([nvcc, "--version"], text=True, timeout=10).strip()
        except (OSError, subprocess.SubprocessError):
            info["cuda_compiler"] = None
    try:
        info["git_commit"] = subprocess.check_output(
            ["git", "-C", str(Path(__file__).resolve().parents[1]), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        info["git_commit"] = None
    info["environment_sha256"] = digest(info)
    return info


def memory(device):
    import torch
    if device.type != "cuda":
        return None
    free, total = torch.cuda.mem_get_info(device)
    return {"allocated_bytes": torch.cuda.memory_allocated(device),
            "reserved_bytes": torch.cuda.memory_reserved(device),
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(device),
            "device_used_bytes_including_context_and_other_processes": total - free}


def sync(device):
    if device.type == "cuda":
        import torch
        torch.cuda.synchronize(device)


def timed(call, device):
    sync(device)
    start = time.perf_counter()
    output = call()
    sync(device)
    return output, (time.perf_counter() - start) * 1000


def summarize(times, candidates, questions):
    seconds = sum(times) / 1000
    return {"warm_p50_ms": percentile(times, .5), "warm_p95_ms": percentile(times, .95),
            "warm_min_ms": min(times), "warm_max_ms": max(times),
            "requests_per_second": len(times) / seconds,
            "decisions_per_second": questions * len(times) / seconds,
            "candidate_sequences_per_second": candidates * len(times) / seconds,
            "iterations": len(times)}


def independent_fixture_suite():
    """Original deterministic scaling and policy-boundary inputs, not benchmark training data.

    Policy values straddle 0.2/0.8; actual model probability margins are measured
    rather than assumed to match those policy values.
    """
    workloads = []
    for name, repeats, candidates in (("short", 0, 2), ("medium", 32, 8), ("long", 128, 16)):
        state = {"permitted_route": "route_00", "risk": .199999, "support": .800001,
                 "policy": "Approve only if risk <= 0.2 and support >= 0.8; otherwise human review.",
                 "audit_trail": "The route remains stationary while a reviewer checks the evidence. " * repeats}
        questions = {
            "route": {"type": "choice", "instructions": "Which route is explicitly permitted?",
                      "criteria": {f"route_{i:02}": f"Select route number {i:02}." for i in range(candidates)}},
            "approve": {"type": "noul", "instructions": "Does this state satisfy both approval policy limits?",
                        "criteria": {"true": "Both numerical limits are satisfied.", "false": "One or both limits fail."}},
            "review": {"type": "score", "instructions": "How many of the two approval limits fail?",
                       "criteria": ["No limit fails.", "Exactly one limit fails.", "Both limits fail."]}}
        workloads.append({"id": f"independent-{name}-choice-{candidates}",
                          "scope": "deterministic original synthetic scaling input",
                          "request": {"state": state, "questions": questions}})
    for field, threshold in (("risk", .2), ("support", .8)):
        for side, delta in (("below", -1e-6), ("above", 1e-6)):
            state = {"risk": .1, "support": .9,
                     "policy": "Approve only if risk <= 0.2 and support >= 0.8; otherwise human review."}
            state[field] = threshold + delta
            request = {"state": state, "questions": {
                "approval_gate": {"type": "noul", "instructions": "Do both numerical limits in the policy hold?",
                                  "criteria": {"true": "Approve.", "false": "Send for human review."}}}}
            workloads.append({"id": f"independent-policy-{field}-{side}",
                              "scope": "policy boundary, not a claim of near-threshold model probability",
                              "policy_threshold": threshold, "request": request})
    return workloads


def loopback_http_benchmark(predictor, request, device, *, iterations, warmup,
                            reference_response, tolerance):
    """Local HTTP serialization/socket/service timings on an already loaded model."""
    from jev.server import make_server, strict_json

    class SynchronizedPredictor:
        model_name, method = predictor.model_name, predictor.method

        def predict(self, value):
            sync(device)
            response = predictor.predict(value)
            sync(device)
            return response

    server = make_server(SynchronizedPredictor(), "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    payload = json.dumps(request, ensure_ascii=False, allow_nan=False).encode()

    def call():
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=120)
        try:
            connection.request("POST", "/v1/systemone", payload, {"Content-Type": "application/json"})
            response = connection.getresponse()
            body = response.read()
            if response.status != 200:
                raise RuntimeError(f"loopback HTTP inference returned status {response.status}")
            return strict_json(body)
        finally:
            connection.close()

    try:
        cold, first_ms = timed(call, device)
        checks = [compare_responses(reference_response, cold, tolerance)]
        for _ in range(warmup):
            call()
        times = []
        for _ in range(iterations):
            response, elapsed = timed(call, device)
            times.append(elapsed)
            checks.append(compare_responses(reference_response, response, tolerance))
        candidates = cold["metadata"]["candidate_sequences"]
        return {"scope": "loopback HTTP on an already warmed model; fresh TCP connection per request, concurrency one",
                "first_observed_http_warm_model_ms": first_ms,
                "warm_samples_ms": times, **summarize(times, candidates, len(request["questions"])),
                "parity_checks": checks, "parity_passed": all(c["passed"] for c in checks)}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def kernel_benchmark(device, *, iterations=50, warmup=5, tolerance=1e-4):
    import torch
    from jev.kernels.final_score import final_rms_head, reference_final_rms_head
    from jev.metrics import softmax
    if device.type != "cuda":
        raise ValueError("kernel performance measurements require CUDA; run CPU correctness tests separately")
    cases = []
    for hidden_size in (2048, 4096, 5120):
        for state_tokens, candidates in ((128, 2), (512, 8), (1024, 32)):
            generator = torch.Generator(device=device).manual_seed(20261002)
            hidden = torch.randn(candidates * state_tokens, hidden_size, generator=generator,
                                 device=device, dtype=torch.bfloat16)
            delta = torch.randn(hidden.shape, generator=generator, device=device,
                                dtype=hidden.dtype) * .25
            rows = torch.arange(candidates, device=device) * state_tokens + state_tokens - 1
            norm = torch.randn(hidden_size, generator=generator, device=device) * .01
            head = torch.randn(1, hidden_size, generator=generator, device=device) * .003
            bias = torch.zeros(1, device=device)
            calls = {"torch_reference_tail": lambda: reference_final_rms_head(
                hidden, rows, norm, head, bias, delta=delta, validate_rows=False),
                "triton_fused_tail": lambda: final_rms_head(hidden, rows, norm, head, bias, delta=delta)}
            outputs, cold, samples = {}, {}, {key: [] for key in calls}
            torch.cuda.reset_peak_memory_stats(device)
            for key, call in calls.items():
                outputs[key], cold[key] = timed(call, device)
            for _ in range(warmup):
                for call in calls.values():
                    call()
            for repeat in range(iterations):
                order = list(calls) if repeat % 2 == 0 else list(calls)[::-1]
                for key in order:
                    outputs[key], elapsed = timed(calls[key], device)
                    samples[key].append(elapsed)
            a, b = outputs["torch_reference_tail"].float().cpu().tolist(), outputs["triton_fused_tail"].float().cpu().tolist()
            if any(not math.isfinite(v) for v in a + b):
                raise RuntimeError("kernel returned non-finite logits")
            pa, pb = softmax(a), softmax(b)
            ref = {"answers": {"decision": {"type": "choice", "probabilities": dict(enumerate(pa)),
                                            "choice": max(range(candidates), key=pa.__getitem__)}}}
            out = {"answers": {"decision": {"type": "choice", "probabilities": dict(enumerate(pb)),
                                            "choice": max(range(candidates), key=pb.__getitem__)}}}
            parity = compare_responses(ref, out, tolerance)
            cases.append({"hidden_size": hidden_size, "state_tokens": state_tokens, "candidates": candidates,
                          "fixture": "seeded BF16 random activations, not a model evaluation",
                          "cold_first_observed_call_ms": cold, "samples_ms": samples,
                          "metrics": {key: summarize(values, candidates, 1) for key, values in samples.items()},
                          "max_logit_error": max(abs(x - y) for x, y in zip(a, b)),
                          "parity": parity, "cuda_memory": memory(device)})
            del hidden, delta, rows, norm, head, bias, outputs, calls
            gc.collect()
            torch.cuda.empty_cache()
    return {"measurement_scope": "isolated final-row operator; random fixtures, no Qwen model loaded",
            "cases": cases, "status": "passed" if all(c["parity"]["passed"] for c in cases) else "parity_failed"}


def model_benchmark(checkpoint, requests, backends, device, *, iterations, warmup,
                    tolerance, batch_size, reference=None, fused_final_head=True,
                    include_http=True, progress=None):
    import torch
    from jev.api import candidate_prompts, compile_request
    from jev.serving import load_predictor
    records = [compile_request(req["state"], req["questions"]) for req in requests]
    report = progress if progress is not None else {}
    report.update(measurement_scope="Predictor and separately identified loopback HTTP timings",
                  request_sha256=[digest(r) for r in requests], batch_size=batch_size,
                  backends={}, comparisons=[])
    reference_rows = None
    if reference:
        saved = json.loads(Path(reference).read_text())
        if saved["model_benchmark"]["request_sha256"] != report["request_sha256"]:
            raise ValueError("reference benchmark request hashes differ")
        if saved["model_benchmark"].get("batch_size") != batch_size:
            raise ValueError("reference benchmark batch size differs or is unspecified")
        reference_rows = saved["model_benchmark"]["backends"]["torch"]
    for backend in backends:
        torch.cuda.reset_peak_memory_stats(device)
        sync(device)
        loaded = time.perf_counter()
        predictor = load_predictor(checkpoint=checkpoint, device=str(device), batch_size=batch_size,
                                   backend=backend, fused_final_head=fused_final_head)
        sync(device)
        load_ms = (time.perf_counter() - loaded) * 1000
        loaded_memory = memory(device)
        if backend != "torch" and reference_rows:
            if (reference_rows["provenance"]["checkpoint_sha256"] != predictor.provenance["checkpoint_sha256"]
                    or reference_rows["provenance"]["max_length"] != predictor.provenance["max_length"]):
                raise ValueError("reference checkpoint hash/context limit differs")
        outcomes = []
        current = {"cold_model_load_checksum_compile_ms": load_ms, "resident_cuda_memory_after_load": loaded_memory,
                   "provenance": predictor.provenance, "requests": outcomes}
        report["backends"][backend] = current
        for index, (request, recs) in enumerate(zip(requests, records)):
            torch.cuda.reset_peak_memory_stats(device)
            cold, cold_ms = timed(lambda: predictor.predict(request), device)
            prompts = [predictor.scorer.model.tokenizer.apply_chat_template(
                [{"role": "user", "content": p}], tokenize=False,
                add_generation_prompt=True, enable_thinking=False)
                for r in recs for p in candidate_prompts(r)]
            lengths = list(map(len, predictor.scorer.model.tokenizer(prompts, padding=False, truncation=False)["input_ids"]))
            state = request["state"] if isinstance(request["state"], str) else json.dumps(request["state"], ensure_ascii=False, sort_keys=True)
            state_tokens = len(predictor.scorer.model.tokenizer(state, truncation=False)["input_ids"])
            for _ in range(warmup):
                predictor.predict(request)
            times, answers = [], []
            for _ in range(iterations):
                answer, elapsed = timed(lambda: predictor.predict(request), device)
                answers.append(answer)
                times.append(elapsed)
            stable = [compare_responses(cold, answer, tolerance) for answer in answers]
            if backend != "torch" and reference_rows:
                ref = reference_rows["requests"][index]["response"]
                for repetition, answer in enumerate([cold] + answers):
                    report["comparisons"].append({"backend": backend, "request_index": index,
                                                   "phase": "cold" if repetition == 0 else "warm",
                                                   "repetition": repetition - 1,
                                                   **compare_responses(ref, answer, tolerance)})
            outcomes.append({"request_index": index, "request_sha256": report["request_sha256"][index],
                             "state_utf8_bytes": len(state.encode()), "state_tokens": state_tokens,
                             "candidate_lengths": lengths, "candidate_sequences": len(lengths),
                             "question_count": len(recs), "cold_first_observed_request_ms": cold_ms,
                             "warm_samples_ms": times, **summarize(times, len(lengths), len(recs)),
                             "stability_passed": all(s["passed"] for s in stable),
                             "stability_checks": stable, "response": cold, "cuda_memory": memory(device)})
            if include_http:
                reference_response = reference_rows["requests"][index]["response"] if backend != "torch" and reference_rows else cold
                http_report = loopback_http_benchmark(
                    predictor, request, device, iterations=iterations, warmup=warmup,
                    reference_response=reference_response, tolerance=tolerance)
                outcomes[-1]["loopback_http"] = http_report
        if backend == "torch":
            reference_rows = current
        del predictor
        gc.collect()
        torch.cuda.empty_cache()
    all_stable = all(r["stability_passed"] and r.get("loopback_http", {}).get("parity_passed", True)
                     for b in report["backends"].values() for r in b["requests"])
    parity_ok = bool(report["comparisons"]) and all(c["passed"] for c in report["comparisons"])
    report["status"] = "passed" if all_stable and parity_ok else "baseline_only" if backends == ["torch"] else "parity_failed_or_missing_reference"
    report["notes"] = ["Models are loaded sequentially and released between backends; measurements are not interleaved across models.",
                       "Cold calls are the first observed calls in this process; disk, JIT and Hub caches may already be warm.",
                       "Allocator peaks include cold request and warm iterations; reserved memory persists within a backend.",
                       "No speedup is accepted if probability, decision, threshold or usage parity fails."]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--request", type=Path, action="append")
    parser.add_argument("--backend", choices=("all", "torch", "triton-tail", "fast-cuda"), default="all")
    parser.add_argument("--kernel-only", action="store_true")
    parser.add_argument("--fixture-suite", action="store_true", help="Add seven original scaling/policy-boundary requests")
    parser.add_argument("--http", action=argparse.BooleanOptionalAction, default=True,
                        help="Measure local HTTP separately from in-process calls")
    parser.add_argument("--reference", type=Path, help="Previously recorded torch report with identical request/checkpoint hashes")
    parser.add_argument("--fused-final-head", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-probability-error", type=float, default=1e-4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.iterations <= 1000 or not 0 <= args.warmup <= 100:
        parser.error("output must be new; iterations 1-1000 and warmup 0-100")
    if not args.kernel_only and (not args.checkpoint or not (args.request or args.fixture_suite)):
        parser.error("checkpoint benchmark requires --checkpoint and at least one --request")
    if not math.isfinite(args.max_probability_error) or not 0 <= args.max_probability_error <= 1:
        parser.error("probability tolerance must be finite and in [0, 1]")
    import torch
    device = torch.device(args.device)
    if device.type != "cuda" or not torch.cuda.is_available():
        parser.error("performance benchmark requires CUDA; CPU fixtures are correctness tests")
    torch.cuda.set_device(device)
    report = {"schema_version": 1, "started_at": datetime.now(timezone.utc).isoformat(),
              "environment": environment(device), "performance_measured": True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    failed = False
    try:
        if args.kernel_only:
            report["kernel_benchmark"] = kernel_benchmark(device, iterations=args.iterations,
                                                          warmup=args.warmup, tolerance=args.max_probability_error)
            failed = report["kernel_benchmark"]["status"] != "passed"
        else:
            from jev.server import strict_json
            requests = [strict_json(path.read_bytes()) for path in args.request or []]
            if args.fixture_suite:
                suite = independent_fixture_suite()
                report["independent_fixture_suite"] = suite
                requests.extend(w["request"] for w in suite)
            backends = ["torch", "triton-tail", "fast-cuda"] if args.backend == "all" else [args.backend]
            report["model_benchmark"] = {}
            model_benchmark(
                args.checkpoint, requests, backends, device, iterations=args.iterations,
                warmup=args.warmup, tolerance=args.max_probability_error, batch_size=args.batch_size,
                reference=args.reference, fused_final_head=args.fused_final_head,
                include_http=args.http, progress=report["model_benchmark"])
            failed = report["model_benchmark"]["status"] not in ("passed", "baseline_only")
    except Exception as error:
        report.update(status="failed", error_type=type(error).__name__, error=str(error))
        failed = True
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["report_sha256"] = digest(report)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output), "status": "failed" if failed else "recorded"}))
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
