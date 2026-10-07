"""Recheck retained latency evidence using only the Python standard library.

No model, GPU, network, benchmark validator, or training data is accessed.
The recorded Git revision must be available in the local repository.
"""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED = {
    "2b": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    "9b": ("Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"),
    "27b": ("Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"),
}
ERRORS = []
CHECKS = 0


def check(value, label):
    global CHECKS
    CHECKS += 1
    if not value:
        ERRORS.append(label)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(commit, path):
    return subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{path}"])


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"nonfinite JSON constant {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def near(left, right):
    return (type(left) in (int, float) and math.isfinite(left)
            and math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12))


def answer_keys(question):
    return (["false", "true"] if question["type"] == "noul" else
            list(question["criteria"]) if question["type"] == "choice" else
            [str(index) for index in range(len(question["criteria"]))])


def probability_rows(mappings, questions, label):
    check(set(mappings) == set(questions), label + "/question coverage")
    result = {}
    for key, question in questions.items():
        mapping = mappings[key]
        keys = answer_keys(question)
        check(isinstance(mapping, dict) and set(mapping) == set(keys), label + f"/{key}/candidate coverage")
        values = [mapping[name] for name in keys]
        check(all(type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
                  for value in values), label + f"/{key}/numeric range")
        total = sum(values)
        check(math.isclose(total, 1, abs_tol=1e-6, rel_tol=1e-6), label + f"/{key}/simplex")
        result[key] = [value / total for value in values]
    return result


def typed_answers(response, questions, label, expected_rows=None):
    answers = response["answers"]
    check(set(answers) == set(questions), label + "/typed coverage")
    mappings = {}
    for key, question in questions.items():
        answer = answers[key]
        kind = question["type"]
        check(answer["type"] == kind, label + f"/{key}/type")
        fields = ({"type", "noul"} if kind == "noul" else
                  {"type", "probabilities", "choice", "confidence"} if kind == "choice" else
                  {"type", "probabilities", "score", "confidence", "legend"})
        check(set(answer) == fields, label + f"/{key}/fields")
        mappings[key] = ({"false": 1 - answer["noul"], "true": answer["noul"]}
                         if kind == "noul" else answer["probabilities"])
    rows = probability_rows(mappings, questions, label + "/typed probabilities")
    for key, question in questions.items():
        kind, values, answer = question["type"], rows[key], answers[key]
        if expected_rows is not None:
            check(all(near(left, right) for left, right in zip(values, expected_rows[key])),
                  label + f"/{key}/raw-to-typed values")
        if kind == "noul":
            check(near(answer["noul"], values[1]), label + f"/{key}/Noul")
            continue
        count = len(values)
        if kind == "choice":
            keys = answer_keys(question)
            check(answer["choice"] == keys[max(range(count), key=values.__getitem__)], label + f"/{key}/argmax")
            confidence = 1 if count == 1 else (max(values) - 1 / count) / (1 - 1 / count)
        else:
            check(near(answer["score"], sum(index * value for index, value in enumerate(values))),
                  label + f"/{key}/Score")
            check(answer["legend"] == {str(index): value for index, value in enumerate(question["criteria"])},
                  label + f"/{key}/legend")
            mode = max(range(count), key=values.__getitem__)
            distance = sum(value * abs(index - mode) for index, value in enumerate(values))
            uniform_distance = sum(abs(index - (count - 1) / 2) for index in range(count)) / count
            confidence = max(0, 1 - distance / uniform_distance)
        check(near(answer["confidence"], confidence), label + f"/{key}/confidence")


def main():
    transfer = strict_json((HERE / "transfer.json").read_text())
    for name, expected in transfer["files"].items():
        raw = (HERE / name).read_bytes()
        check(len(raw) == expected["bytes"] and digest(raw) == expected["sha256"], f"transfer/{name}")
    check(transfer["source_unchanged_during_transfer"] is True, "transfer/source stable")
    manifest = strict_json((HERE / "manifest.json").read_text())
    commit = manifest["commit"]
    check(manifest["status"] == "complete" and manifest["output_contract"] == "probabilities", "manifest/completion contract")
    check(manifest["gpu"] == 3 and manifest["resource_policy"]["expected_hostname"] == "kwade5342000001",
          "manifest/authorized host GPU")
    check(digest(git_bytes(commit, "state/auto_research/resource_policy.json")) == manifest["resource_policy"]["sha256"],
          "manifest/resource policy hash")
    source_request = git_bytes(commit, "examples/community/drone.json")
    supplied = strict_json(source_request)
    request = {"state": supplied["state"], "questions": supplied["questions"]}
    payload_hash = digest(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode())
    check([run["tag"] for run in manifest["runs"]] == list(EXPECTED), "manifest/model order")
    gpu_uuids, rows, previous_end, shared_runtime = set(), [], None, None
    for run in manifest["runs"]:
        tag = run["tag"]
        report = strict_json((HERE / f"{tag}.json").read_text())
        model, revision = EXPECTED[tag]
        check(report["status"] == "complete" and run["exit_code"] == 0, tag + "/completion")
        check((report["model"], report["revision"]) == (model, revision), tag + "/base model identity")
        check(report["cached_snapshot"].endswith("/" + revision), tag + "/cached revision")
        check(report["repo_commit"] == commit, tag + "/code identity")
        check(report["benchmark"] == "no_training_vs_autoregressive_probability_mapping"
              and report["output_contract"] == "probabilities", tag + "/contract identity")
        for path, expected_hash in report["source_sha256"].items():
            check(digest(git_bytes(commit, path)) == expected_hash, tag + "/source/" + path)
        check(report["request"] == request, tag + "/same original request")
        check(report["request_file_sha256"] == digest(source_request), tag + "/request file hash")
        check(report["request_payload_sha256"] == payload_hash, tag + "/request payload hash")
        expected_config = {"repeats": 3, "batch_size": 32, "output_contract": "probabilities",
                           "max_input_tokens": 4096, "max_new_tokens": 2048, "do_sample": False,
                           "enable_thinking": False, "temperature_decision": 1, "lora_rank": 0,
                           "validation_tolerance": 1e-6, "derived_fields": "shared_jev.api.format_response",
                           "warmups_per_path": 1, "load_order": ["decision", "generation"],
                           "network": "offline_cached_files_only"}
        check(report["configuration"] == expected_config, tag + "/configuration")
        runtime = (report["runtime"], report["python"], report["cuda"], report["gpu"], report["attention"], report["dtype"])
        shared_runtime = runtime if shared_runtime is None else shared_runtime
        check(runtime == shared_runtime, tag + "/shared runtime hardware")
        command = run["command"]
        for flag, expected in (("--model", model), ("--revision", revision), ("--output-contract", "probabilities"),
                               ("--request", "examples/community/drone.json"), ("--device", "cuda:0"),
                               ("--repeats", "3"), ("--batch-size", "32"),
                               ("--max-input-tokens", "4096"), ("--max-new-tokens", "2048")):
            check(command.count(flag) == 1 and command[command.index(flag) + 1] == expected, tag + "/command/" + flag)
        check(command[command.index("--output") + 1] == transfer["source_root"] + f"/{tag}.json", tag + "/output identity")
        check(run["foreign_process_samples"] == [], tag + "/foreign process samples")
        for phase in ("preflight", "postflight"):
            snapshot = run[phase]
            gpu_uuids.add(snapshot["uuid"])
            check(snapshot["physical_gpu"] == 3 and snapshot["name"] == report["gpu"], tag + "/" + phase + "/device")
            check(snapshot["compute_processes"] == [] and snapshot["memory_used_mib"] == 0
                  and snapshot["utilization_percent"] == 0, tag + "/" + phase + "/idle")
        start, end = (datetime.fromisoformat(run[field]) for field in ("started_at", "ended_at"))
        check(start < end and (previous_end is None or start >= previous_end), tag + "/serial execution")
        previous_end = end
        for mode, method in (("decision", "independent_candidate_yes_minus_no"),
                             ("generation", "autoregressive_probability_mapping_json")):
            block = report[mode]
            check(block["method"] == method, tag + "/" + mode + "/method")
            check([trial["repeat"] for trial in block["trials"]] == [0, 1, 2], tag + "/" + mode + "/repeat coverage")
            all_trials = [block["warmup_excluded"], *block["trials"]]
            check(all_trials[0]["repeat"] == "warmup", tag + "/" + mode + "/excluded warmup")
            for trial in all_trials:
                label = f"{tag}/{mode}/{trial['repeat']}"
                check(trial["status"] == "valid", label + "/status")
                check(math.isfinite(trial["elapsed_seconds"]) and trial["elapsed_seconds"] > 0, label + "/elapsed")
                raw_rows = None
                if mode == "generation":
                    raw = strict_json(trial["parsed_text_candidate"])
                    check(set(raw) == {"probabilities"}, label + "/raw root")
                    raw_rows = probability_rows(raw["probabilities"], request["questions"], label + "/raw")
                    decoded = trial["raw_generation"].replace("<|im_end|>", "").replace("<|endoftext|>", "")
                    check(decoded == trial["parsed_text_candidate"], label + "/raw text preservation")
                    check(len(trial["generated_token_ids"]) == trial["output_tokens"]
                          and all(type(token) is int for token in trial["generated_token_ids"]), label + "/token evidence")
                    check(trial["hit_output_limit"] is False and trial["output_tokens"] < 2048, label + "/not truncated")
                else:
                    check(trial["output_tokens"] == 0 and trial["candidate_sequences"] == 7, label + "/decision sequence count")
                    check(trial["response"]["model"] == model
                          and trial["response"]["metadata"]["method"] == "pretrained_yes_minus_no_no_training"
                          and trial["response"]["metadata"]["temperature"] == 1, label + "/decision identity")
                typed_answers(trial["response"], request["questions"], label, raw_rows)
                actual_bytes = len(json.dumps(trial["response"], ensure_ascii=False, allow_nan=False).encode())
                check(actual_bytes == trial["serialized_response_bytes"], label + "/serialized bytes")
            median = statistics.median(trial["elapsed_seconds"] for trial in block["trials"])
            summary = block["summary"]
            check(summary["attempts"] == summary["valid"] == 3 and all(value == 0 for value in summary["failures"].values()), tag + "/" + mode + "/counts")
            check(near(summary["median_seconds_all_attempts"], median) and near(summary["median_seconds_valid"], median), tag + "/" + mode + "/median")
        decision_median = statistics.median(trial["elapsed_seconds"] for trial in report["decision"]["trials"])
        generation_median = statistics.median(trial["elapsed_seconds"] for trial in report["generation"]["trials"])
        check(near(report["generation_over_decision_latency_ratio"], generation_median / decision_median), tag + "/ratio")
        rows.append({"tag": tag, "model": model, "revision": revision, "valid_decision": 3, "valid_generation": 3,
                     "decision_median_seconds": decision_median, "generation_median_seconds": generation_median,
                     "generation_over_decision_ratio": generation_median / decision_median,
                     "decision_input_tokens": sorted({trial["input_tokens"] for trial in report["decision"]["trials"]}),
                     "generation_input_tokens": sorted({trial["input_tokens"] for trial in report["generation"]["trials"]}),
                     "generation_output_tokens": sorted({trial["output_tokens"] for trial in report["generation"]["trials"]}),
                     "identical_generation_repeats": len({trial["parsed_text_candidate"] for trial in report["generation"]["trials"]}) == 1,
                     "foreign_process_sample_count": len(run["foreign_process_samples"])})
    check(len(gpu_uuids) == 1, "same physical GPU across models")
    audit = {"status": "passed" if not ERRORS else "failed", "audited_at_utc": datetime.now(timezone.utc).isoformat(),
             "audit_script_sha256": digest(Path(__file__).read_bytes()), "checks": CHECKS, "errors": ERRORS,
             "method": "independent standard-library revalidation; no benchmark validator import or model rerun",
             "commit": commit, "request_file_sha256": digest(source_request), "request_payload_sha256": payload_hash,
             "gpu_uuids": sorted(gpu_uuids), "models": rows,
             "limits": ["One tiny synthetic three-question workload; three repeats are not independent workload samples.",
                        "No semantic gold or calibration/quality equivalence evaluation.",
                        "Foreign-process polling is sampled, not continuous; empty foreign-sample arrays do not prove exclusivity between polls.",
                        "Token IDs and raw/decoded text are retained and checked for consistency; tokenization and model execution were not rerun.",
                        "Checkpoint weight tensors were not independently reloaded or hashed; pinned model/config/source identities were checked."]}
    (HERE / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))
    return 1 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
