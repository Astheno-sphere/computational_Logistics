"""Bounded local benchmark: untrained decision scoring versus generated JSON.

Both paths use the same cached Qwen revision and GPU, loaded serially. No hosted
API or network download is used. Invalid generations never produce a speedup.
"""

import argparse
import gc
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

# Benchmark this checkout even if another editable Open-Jev checkout is installed.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jev.api import compile_request, format_response
from jev.server import strict_json


OUTPUT_CONTRACTS = ("full_typed", "probabilities")
PROBABILITY_TOLERANCE = 1e-6


class InvalidOutput(ValueError):
    def __init__(self, category, message):
        super().__init__(message)
        self.category = category


def validate_response(request, response, tolerance=0.002):
    """Validate coverage, probabilities, and derived fields; allow 3-decimal JSON."""
    if not isinstance(response, dict):
        raise InvalidOutput("schema", "response must be an object")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(request["questions"]):
        raise InvalidOutput("coverage", "answers must cover exactly the requested question IDs")
    records = compile_request(request["state"], request["questions"])
    rows = []
    for record in records:
        answer = answers[record["id"]]
        if not isinstance(answer, dict) or answer.get("type") != record["kind"]:
            raise InvalidOutput("schema", "answer type mismatch")
        fields = {"type", "noul"} if record["kind"] == "noul" else {"type", "probabilities", "confidence", "choice"} if record["kind"] == "choice" else {"type", "probabilities", "confidence", "score", "legend"}
        if fields - set(answer):
            raise InvalidOutput("coverage", "required typed answer fields are missing")
        if set(answer) - fields:
            raise InvalidOutput("schema", "unexpected typed answer fields")
        if record["kind"] == "noul":
            probabilities = [answer["noul"]]
        else:
            if not isinstance(answer["probabilities"], dict) or set(answer["probabilities"]) != set(record["answer_keys"]):
                raise InvalidOutput("coverage", "candidate probabilities do not cover the answer space")
            probabilities = [answer["probabilities"][key] for key in record["answer_keys"]]
        if any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
            raise InvalidOutput("schema", "probabilities must be finite numbers in [0,1]")
        if record["kind"] == "noul":
            rows.append([1 - probabilities[0], probabilities[0]])
        else:
            total = sum(probabilities)
            if abs(total - 1) > tolerance:
                raise InvalidOutput("schema", "probabilities must sum to one")
            rows.append([p / total for p in probabilities])
    canonical = format_response(records, rows)["answers"]
    for key, expected in canonical.items():
        answer = answers[key]
        if expected["type"] == "choice":
            selected = answer["choice"]
            if not isinstance(selected, str) or selected not in expected["probabilities"] or expected["probabilities"][selected] != max(expected["probabilities"].values()):
                raise InvalidOutput("schema", "choice must be a maximum-probability offered candidate")
        if expected["type"] in ("choice", "score"):
            for field in (["confidence", "score"] if expected["type"] == "score" else ["confidence"]):
                value = answer[field]
                if type(value) not in (int, float) or not math.isfinite(value) or abs(value - expected[field]) > tolerance:
                    raise InvalidOutput("schema", f"{field} disagrees with the distribution")
        if expected["type"] == "score" and answer["legend"] != expected["legend"]:
            raise InvalidOutput("schema", "score legend differs from the supplied rubric")
    return response


def validate_probability_mapping(request, response):
    """Validate raw probabilities, then use the decision path's typed formatter."""
    if not isinstance(response, dict):
        raise InvalidOutput("schema", "response must be an object")
    if "probabilities" not in response:
        raise InvalidOutput("coverage", "response requires a probabilities mapping")
    if set(response) != {"probabilities"}:
        raise InvalidOutput("schema", "unexpected top-level probability response fields")
    mappings = response["probabilities"]
    if not isinstance(mappings, dict) or set(mappings) != set(request["questions"]):
        raise InvalidOutput("coverage", "probabilities must cover exactly the requested question IDs")
    records = compile_request(request["state"], request["questions"])
    rows = []
    for record in records:
        mapping = mappings[record["id"]]
        if not isinstance(mapping, dict) or set(mapping) != set(record["answer_keys"]):
            raise InvalidOutput("coverage", "candidate probabilities do not cover the answer space")
        values = [mapping[key] for key in record["answer_keys"]]
        if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise InvalidOutput("schema", "probabilities must be finite numbers in [0,1]")
        if not math.isclose(sum(values), 1.0, rel_tol=PROBABILITY_TOLERANCE, abs_tol=PROBABILITY_TOLERANCE):
            raise InvalidOutput("schema", "probabilities must sum to one")
        rows.append(values)
    # No inferred candidates, repaired JSON, or normalization of invalid inputs.
    # format_response applies only its documented floating-point tolerance.
    return format_response(records, rows)


def validate_generation(request, text, output_contract="full_typed"):
    if output_contract not in OUTPUT_CONTRACTS:
        raise ValueError("unknown output contract")
    try:
        response = strict_json(text)
    except (ValueError, TypeError) as error:
        raise InvalidOutput("parse", str(error)) from error
    if output_contract == "probabilities":
        return validate_probability_mapping(request, response)
    return validate_response(request, response)


def generation_prompt(request, output_contract="full_typed"):
    """The entire original state and question definitions occur in both paths."""
    if output_contract not in OUTPUT_CONTRACTS:
        raise ValueError("unknown output contract")
    if output_contract == "probabilities":
        templates = {record["id"]: {key: "<probability>" for key in record["answer_keys"]}
                     for record in compile_request(request["state"], request["questions"])}
        return (
            "Evaluate the supplied state against EVERY supplied question independently. "
            "Return only one JSON object with a probabilities mapping, without Markdown, explanations, or thinking text. "
            "Use exactly the question IDs and all candidate IDs shown in the template. "
            "Each question maps directly to its complete candidate-to-probability mapping. "
            "Every probability must be a finite JSON number in [0,1], not a string or boolean. "
            "Each distribution must sum to 1 within 0.000001; do not return unnormalized scores. "
            "Noul requires both false and true probabilities, with true meaning yes. "
            "Do not emit type, choice, score, confidence, legend, or any other derived fields. "
            "Software computes the final typed answers from these probabilities. "
            "Replace all template placeholders with valid numbers.\n\n"
            "Original state and questions:\n" + json.dumps(request, ensure_ascii=False, allow_nan=False)
            + "\n\nRequired response shape:\n" + json.dumps({"probabilities": templates}, ensure_ascii=False)
        )
    templates = {}
    for record in compile_request(request["state"], request["questions"]):
        if record["kind"] == "noul":
            answer = {"type": "noul", "noul": "<P(yes), number in [0,1]>"}
        else:
            answer = {"type": record["kind"], "probabilities": {key: "<probability>" for key in record["answer_keys"]}, "confidence": "<derived number>"}
            if record["kind"] == "choice":
                answer["choice"] = "<highest-probability candidate ID>"
            else:
                answer.update(score="<sum of level index times probability>", legend=record["legend"])
        templates[record["id"]] = answer
    return (
        "Evaluate the supplied state against EVERY supplied question independently. "
        "Return only one JSON object with an answers mapping, without Markdown, explanations, or thinking text. "
        "Use the exact question IDs and all candidate IDs. Return every probability, not just the winner. "
        "Probabilities must be numbers in [0,1] and each distribution must sum to 1. "
        "For Choice, choice is an argmax. Choice confidence is 1 for one candidate; otherwise "
        "(max_probability - 1/K)/(1 - 1/K), where K is the candidate count. "
        "For Score, score=sum(i*p_i). Let m be the first argmax index, "
        "D=sum(p_i*abs(i-m)), U=sum(abs(i-(K-1)/2))/K. Score confidence=max(0,1-D/U). "
        "Copy each Score legend exactly. Noul has only type and noul. "
        "Use at least three decimal places where needed. Replace all template placeholders with valid values.\n\n"
        "Original state and questions:\n" + json.dumps(request, ensure_ascii=False, allow_nan=False)
        + "\n\nRequired response shape:\n" + json.dumps({"answers": templates}, ensure_ascii=False)
    )


def summarize(trials):
    valid = [row["elapsed_seconds"] for row in trials if row["status"] == "valid"]
    failures = {kind: sum(row.get("failure_category") == kind for row in trials)
                for kind in ("parse", "coverage", "schema", "runtime")}
    return {"attempts": len(trials), "valid": len(valid), "failures": failures,
            "median_seconds_all_attempts": statistics.median(row["elapsed_seconds"] for row in trials),
            "median_seconds_valid": statistics.median(valid) if valid else None}


def comparable_ratio(decision_summary, generation_summary):
    if not all(summary["attempts"] >= 3 and summary["valid"] == summary["attempts"] for summary in (decision_summary, generation_summary)):
        return None
    return generation_summary["median_seconds_valid"] / decision_summary["median_seconds_valid"]


def _timed_trial(torch, device, operation, request, index, *, output_contract="full_typed"):
    torch.cuda.synchronize(device)
    torch.cuda.reset_peak_memory_stats(device)
    start = time.perf_counter()
    row = {"repeat": index}
    try:
        result, details = operation()
        row.update(details)
        if isinstance(result, str):
            response = validate_generation(request, result, output_contract)
        else:
            response = validate_response(request, result)
        # Include software assembly/serialization and validation in both timings.
        row["serialized_response_bytes"] = len(json.dumps(response, ensure_ascii=False, allow_nan=False).encode())
        row.update(status="valid", response=response)
    except InvalidOutput as error:
        row.update(status="invalid", failure_category=error.category, error=str(error))
    except Exception as error:
        row.update(status="error", failure_category="runtime", error=f"{type(error).__name__}: {error}")
    torch.cuda.synchronize(device)
    row.update(elapsed_seconds=time.perf_counter() - start,
               peak_allocated_bytes=torch.cuda.max_memory_allocated(device),
               peak_reserved_bytes=torch.cuda.max_memory_reserved(device))
    return row


def _decision_trials(args, request, torch):
    from jev.model import DecisionModel
    from jev.serving import Predictor, TorchScorer
    model = DecisionModel(args.model, args.revision, device=args.device, lora_rank=0, max_length=args.max_input_tokens).eval()
    predictor = Predictor(TorchScorer(model), model_name=args.model, temperature=1, batch_size=args.batch_size,
                          method="pretrained_yes_minus_no_no_training")

    def operation():
        response = predictor.predict(request)
        return response, {"input_tokens": response["usage"]["input_tokens"], "output_tokens": 0,
                          "candidate_sequences": response["metadata"]["candidate_sequences"]}

    warmup = _timed_trial(torch, args.device, operation, request, "warmup")
    trials = [_timed_trial(torch, args.device, operation, request, i) for i in range(args.repeats)]
    return {"method": "independent_candidate_yes_minus_no", "warmup_excluded": warmup,
            "trials": trials, "summary": summarize(trials)}


def _generation_trials(args, request, torch):
    from transformers import AutoModelForImageTextToText, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model, revision=args.revision, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForImageTextToText.from_pretrained(args.model, revision=args.revision,
                local_files_only=True, torch_dtype=torch.bfloat16, attn_implementation="sdpa",
                device_map={"": args.device}).eval()

    def operation():
        prompt = tokenizer.apply_chat_template([{"role": "user", "content": generation_prompt(request, args.output_contract)}],
                    tokenize=False, add_generation_prompt=True, enable_thinking=False)
        encoded = tokenizer(prompt, return_tensors="pt", truncation=False)
        input_tokens = encoded["input_ids"].shape[1]
        if input_tokens > args.max_input_tokens:
            raise ValueError(f"Generation input {input_tokens} exceeds max_input_tokens={args.max_input_tokens}; no truncation")
        encoded = {key: value.to(args.device) for key, value in encoded.items()}
        with torch.inference_mode():
            output = model.generate(**encoded, do_sample=False, use_cache=True,
                         max_new_tokens=args.max_new_tokens, pad_token_id=tokenizer.pad_token_id)
        ids = output[0, input_tokens:].cpu().tolist()
        text = tokenizer.decode(ids, skip_special_tokens=True)
        return text, {"input_tokens": input_tokens, "output_tokens": len(ids),
                      "hit_output_limit": len(ids) >= args.max_new_tokens,
                      "raw_generation": tokenizer.decode(ids, skip_special_tokens=False),
                      "parsed_text_candidate": text, "generated_token_ids": ids}

    warmup = _timed_trial(torch, args.device, operation, request, "warmup", output_contract=args.output_contract)
    trials = [_timed_trial(torch, args.device, operation, request, i, output_contract=args.output_contract)
              for i in range(args.repeats)]
    return {"method": "autoregressive_full_probability_json" if args.output_contract == "full_typed" else "autoregressive_probability_mapping_json",
            "warmup_excluded": warmup, "generation_prompt": generation_prompt(request, args.output_contract),
            "trials": trials, "summary": summarize(trials)}


def _revision():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--output-contract", choices=OUTPUT_CONTRACTS, default="full_typed")
    parser.add_argument("--model", default="Qwen/Qwen3.5-2B")
    parser.add_argument("--revision", default="15852e8c16360a2fea060d615a32b45270f8a8fc")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-input-tokens", type=int, default=4096)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; choose a fresh file to preserve previous attempts")
    if args.repeats < 3 or min(args.batch_size, args.max_input_tokens, args.max_new_tokens) < 1 or args.max_new_tokens > 8192:
        parser.error("use at least 3 repeats, positive limits, and at most 8192 generated tokens")
    if len(args.revision) != 40 or any(c not in "0123456789abcdef" for c in args.revision.lower()):
        parser.error("revision must be a pinned 40-character commit hash")
    raw_request = args.request.read_bytes()
    supplied = strict_json(raw_request)
    request = {"state": supplied["state"], "questions": supplied["questions"]}
    compile_request(**request)
    # Set before importing HF/transformers: DecisionModel exposes no local-files flag.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import torch
    from huggingface_hub import snapshot_download
    cached_snapshot = snapshot_download(args.model, revision=args.revision, local_files_only=True)
    if not args.device.startswith("cuda") or not torch.cuda.is_available():
        parser.error("this comparison requires one CUDA GPU shared by both serial paths")
    torch.cuda.set_device(args.device)
    torch.manual_seed(42)
    versions = {}
    for name in ("torch", "transformers", "accelerate", "huggingface-hub"):
        versions[name] = importlib.metadata.version(name)
    root = Path(__file__).resolve().parents[1]
    files = [Path(__file__), *(root / "jev" / name for name in ("model.py", "api.py", "serving.py", "metrics.py"))]
    report = {
        "benchmark": "no_training_vs_autoregressive_full_probabilities" if args.output_contract == "full_typed" else "no_training_vs_autoregressive_probability_mapping",
        "output_contract": args.output_contract, "status": "running",
        "model": args.model, "revision": args.revision, "cached_snapshot": cached_snapshot,
        "device": args.device, "gpu": torch.cuda.get_device_name(args.device),
        "dtype": "bf16 backbone; float32 decision readout", "attention": "sdpa",
        "runtime": versions, "python": platform.python_version(), "cuda": torch.version.cuda,
        "repo_commit": _revision(), "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        "request_file_sha256": hashlib.sha256(raw_request).hexdigest(),
        "request_payload_sha256": hashlib.sha256(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        "request": request, "configuration": {"repeats": args.repeats, "batch_size": args.batch_size,
             "output_contract": args.output_contract,
             "max_input_tokens": args.max_input_tokens, "max_new_tokens": args.max_new_tokens,
             "do_sample": False, "enable_thinking": False, "temperature_decision": 1,
             "lora_rank": 0, "validation_tolerance": 0.002 if args.output_contract == "full_typed" else PROBABILITY_TOLERANCE,
             "derived_fields": "generated_and_validated" if args.output_contract == "full_typed" else "shared_jev.api.format_response",
             "warmups_per_path": 1,
             "load_order": ["decision", "generation"], "network": "offline_cached_files_only"},
        "scope": ("Generation emits full typed JSON including derived fields. " if args.output_contract == "full_typed" else
                  "Generation emits only complete normalized probability maps; shared format_response software derives final Choice, Noul, Score, confidence, and legend. This is a separate contract from full_typed, not repaired earlier output. ") +
                 "Same original state/questions and full final typed probability answers. Local Python end-to-end, including formatting/tokenization, GPU inference, output processing and validation; model load and warmup excluded. Paths use different prompts and execution mechanisms. No task-accuracy, Jev-parity, calibration, or Harsha KV-broadcast claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_reserved = False

    def save():
        nonlocal output_reserved
        with args.output.open("w" if output_reserved else "x") as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        output_reserved = True

    save()
    for name, run in (("decision", _decision_trials), ("generation", _generation_trials)):
        print(json.dumps({"path": name, "status": "loading_cached_model"}), flush=True)
        try:
            report[name] = run(args, request, torch)
        except Exception as error:
            report.update(status="failed", failure=f"{name}: {type(error).__name__}: {error}")
            save()
            raise
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.synchronize(args.device)
        save()
        print(json.dumps({"path": name, **report[name]["summary"]}), flush=True)
    report.update(status="complete", generation_over_decision_latency_ratio=comparable_ratio(report["decision"]["summary"], report["generation"]["summary"]))
    if report["generation_over_decision_latency_ratio"] is None:
        report["ratio_unavailable_reason"] = "At least one timed attempt failed full output validation; no successful-output speedup is reported."
    save()
    print(json.dumps({"output": str(args.output), "generation_over_decision_latency_ratio": report["generation_over_decision_latency_ratio"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
