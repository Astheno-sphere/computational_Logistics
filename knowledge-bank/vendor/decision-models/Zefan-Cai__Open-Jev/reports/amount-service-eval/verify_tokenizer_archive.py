"""Audit frozen amount tokenizer capture lineage and length arithmetic offline.

No tokenizer, model, producer oracle, SSH or network is executed. Non-heldout
dataset payloads are never JSON-decoded; their files are only hashed as bytes.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from jev.api import candidate_prompts, compile_request

VERSION = "amount-extraction-control-v1"
PINS = {
    "reports/amount-service-eval/tokenizer-lengths.json": "a7415eb4ec852cdba3b09c9d7d09e34c725ae9f0b0cf1d18b2721754efeb7613",
    "reports/amount-service-eval/tokenizer-lengths-raw.json.gz": "664386be7b0b134676806c241566dd939cbd1fa1161599043bd0b1e0122036cf",
    "reports/amount-service-eval/capture_tokenizer_lengths.py": "862bdb23eab8d1d863befefae8e242542daf8698ef4fd535f014f70af110aab0",
    "reports/amount-service-eval/heldout-preflight.json": "2c146746d55f53a9d72fb8fe8f1b2beea24b2927fa9b2943acd09eeb5eb4cc70",
    "reports/amount-service-eval/verify_heldout.py": "32d26519807239ed3d6867fb7fad212c42b49f74eda20140f1f149f9c6b25e69",
    "reports/contact-service-eval/verify_heldout.py": "e7bcdaa11aa382e8dec2f449a1ec6ffb75e3edea2a8643ad7131d989aec8f861",
}
MODELS = {
    "2b": ["Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"],
    "9b": ["Qwen/Qwen3.5-9B", "c202236235762e1c871ad0ccb60c8ee5ba337b9a"],
    "27b": ["Qwen/Qwen3.8-27B", "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(value, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=sort_keys, allow_nan=False).encode("utf-8")


def digest(value, sort_keys=False):
    return hashlib.sha256(compact(value, sort_keys)).hexdigest()


def verify():
    for name, expected in PINS.items():
        require(sha(ROOT / name) == expected, "Frozen capture/preflight input changed: " + name)
    summary = json.loads((ROOT / "reports/amount-service-eval/tokenizer-lengths.json").read_bytes())
    preflight = json.loads((ROOT / "reports/amount-service-eval/heldout-preflight.json").read_bytes())
    archive_path = ROOT / "reports/amount-service-eval/tokenizer-lengths-raw.json.gz"
    archive = json.loads(gzip.decompress(archive_path.read_bytes()))
    require(set(archive) == {"entries", "result"}, "Unexpected archive envelope")
    require(summary["status"] == "complete", "Capture did not complete")
    require(summary["raw_lengths"] == str(archive_path.relative_to(ROOT)) and
            summary["raw_lengths_sha256"] == sha(archive_path), "Raw archive reference differs")
    require(summary["capture_script_sha256"] == PINS["reports/amount-service-eval/capture_tokenizer_lengths.py"], "Capture source pin differs")
    require(preflight["verified"] and preflight["dataset"] == VERSION and
            preflight["preflight_script_sha256"] == PINS["reports/amount-service-eval/verify_heldout.py"], "Preflight identity differs")
    for name, expected in preflight["pinned_dependencies_sha256"].items():
        require(sha(ROOT / name) == expected, "Previously audited dependency changed: " + name)
    directory = ROOT / "data" / VERSION
    manifest_path = directory / "manifest.json"
    require(sha(manifest_path) == summary["dataset_manifest_sha256"][VERSION] ==
            preflight["pinned_dependencies_sha256"]["data/" + VERSION + "/manifest.json"], "Amount manifest pin differs")
    manifest = json.loads(manifest_path.read_bytes())
    file_hashes = {name: sha(directory / name) for name in manifest["files_sha256"]}
    require(file_hashes == manifest["files_sha256"] == preflight["files_sha256"], "Frozen corpus file bytes differ")
    sources = {name: sha(ROOT / "jev" / name) for name in manifest["configuration"]["source_files_sha256"]}
    require(sources == manifest["configuration"]["source_files_sha256"] == preflight["source_files_sha256"], "Frozen runtime source differs")
    require({"jev/" + name: value for name, value in sources.items()} == summary["source_files_sha256"], "Capture runtime source pins differ")

    reader_path = ROOT / "reports/contact-service-eval/verify_heldout.py"
    spec = importlib.util.spec_from_file_location("amount_archive_prefix_reader", reader_path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    decode_log = {}
    cases = reader.heldout_sidecar(directory / "cases.jsonl", "cases", decode_log)
    require(len(cases) == 864, "Heldout document count differs")
    for split in ("test", "ood"):
        ids = [case["id"] for case in cases if case["split"] == split]
        frozen = preflight["splits"][split]
        require(ids == frozen["case_ids"] and reader.sequence_sha256(ids) == frozen["case_ids_sha256"], "Frozen physical case order differs")

    entries, request_counts, head_counts = [], Counter(), Counter()
    ordered_requests = {split: [] for split in ("test", "ood")}
    undefined_credit_requests = Counter()
    for case in cases:
        selection = case["selection_request"]
        candidates = selection["state"]["candidates"]
        require([item["candidate_id"] for item in case["attributes"]] == list(candidates), "All-candidate B coverage/order differs")
        requests = [("selection", None, selection)]
        for item in case["attributes"]:
            state = item["request"]["state"]
            require(state == {"text": selection["state"]["text"], "policy": selection["state"]["policy"],
                              "selected_id": item["candidate_id"], "selected": candidates[item["candidate_id"]]}, "B is not bound to its actual candidate")
            require(list(item["request"]["questions"]) == ["currency", "direction_known", "is_credit"], "Runtime B must retain every declared head")
            if item["reference"]["is_credit"] is None:
                undefined_credit_requests[case["split"]] += 1
            requests.append(("attributes", item["candidate_id"], item["request"]))
        for stage, candidate, request in requests:
            require(set(request) == {"state", "questions"}, "Model request contains auxiliary top-level fields")
            ordered_requests[case["split"]].append({
                "case_id": case["id"], "family_id": case["family_id"], "group_id": case["group_id"],
                "split": case["split"], "stage": stage, "candidate_id": candidate,
                "request_sha256": digest(request), "canonical_request_sha256": digest(request, True),
            })
            request_counts[VERSION + "/" + case["split"] + "/" + stage] += 1
            for record in compile_request(**request):
                prompts = candidate_prompts(record)
                require(len(prompts) == (1 if record["kind"] == "noul" else len(record["options"])), "Candidate sequence cardinality differs")
                head_counts[stage + "/" + record["id"]] += len(prompts)
                for index, prompt in enumerate(prompts):
                    entries.append({"corpus": VERSION, "split": case["split"], "case_id": case["id"],
                                    "stage": stage, "candidate_id": candidate, "head": record["id"],
                                    "option_index": index, "prompt": prompt})
    for split, requests in ordered_requests.items():
        frozen = preflight["splits"][split]
        require(requests == frozen["ordered_requests"] and digest(requests, True) == frozen["ordered_requests_sha256"], "A/B request payloads/order differ from independent preflight")
        require(undefined_credit_requests[split] == frozen["all_candidate_B_denominators"]["is_credit_undefined"], "Undefined-credit runtime coverage differs")
    require(dict(request_counts) == summary["request_counts"], "Capture request counts differ")
    require(sum(request_counts.values()) == 4860 and len(entries) == summary["candidate_sequences"] == 29700, "Runtime request/sequence total differs")
    require(dict(head_counts) == {"selection/span": 4860, "selection/target_present": 864,
                                 "attributes/currency": 15984, "attributes/direction_known": 3996,
                                 "attributes/is_credit": 3996}, "Runtime sequence counts per head differ")
    identities = [{key: value for key, value in entry.items() if key != "prompt"} for entry in entries]
    require(identities == archive["entries"], "Archived ordered sequence identities differ")
    require(len({compact(item) for item in identities}) == len(identities), "Duplicate sequence identity")
    payload_sha256 = digest({"models": MODELS, "entries": entries})
    require(payload_sha256 == summary["prompt_payload_sha256"], "Exact reconstructed prompt payload differs")

    captured = archive["result"]
    require(list(captured["models"]) == list(summary["models"]) == list(MODELS), "Captured model identities/order differ")
    require(captured["cuda_visible_devices"] == summary["cuda_visible_devices"] == "", "Captured CUDA visibility differs")
    require(captured["transformers"] == summary["transformers"] == "5.10.2", "Captured transformers version differs")
    require(captured["tokenizers"] == summary["tokenizers"] == "0.22.2", "Captured tokenizers version differs")
    require(captured["observed_at"] == summary["observed_at"], "Capture timestamps differ")
    require(summary["full_case_payloads_decoded_by_split"] == {"test": 224, "ood": 640} and
            summary["nonheldout_case_payloads_decoded"] == 0, "Capture-declared case access differs")
    models = {}
    for tag, (model, revision) in MODELS.items():
        raw, saved = captured["models"][tag], summary["models"][tag]
        require([raw["model"], raw["revision"]] == [model, revision], "Captured model or exact revision differs")
        require(raw["tokenizer_class"] == "Qwen2Tokenizer" and
                re.fullmatch(r"[0-9a-f]{64}", raw["chat_template_sha256"]) is not None, "Invalid tokenizer/template identity")
        require(all(raw[key] == saved[key] for key in ("model", "revision", "tokenizer_class", "chat_template_sha256")), "Summary tokenizer identity differs from raw capture")
        lengths = raw["lengths"]
        require(len(lengths) == len(entries) and all(type(value) is int and value > 0 for value in lengths), "Invalid or incomplete raw lengths")
        maximum = max(lengths)
        arithmetic = {"sequences": len(lengths), "minimum": min(lengths), "maximum": maximum,
                      "over_4096": sum(value > 4096 for value in lengths), "over_16384": sum(value > 16384 for value in lengths),
                      "maximum_example": identities[lengths.index(maximum)]}
        require(all(saved[key] == value for key, value in arithmetic.items()), "Summary length arithmetic differs")
        models[tag] = {"model": model, "revision": revision, "tokenizer_class": raw["tokenizer_class"],
                       "chat_template_sha256": raw["chat_template_sha256"], **arithmetic, "lengths_sha256": digest(lengths)}
    require(all(sha(ROOT / name) == expected for name, expected in PINS.items()), "Frozen audit input changed during verification")
    require(all(sha(directory / name) == expected for name, expected in file_hashes.items()), "Dataset bytes changed during verification")
    require("jev.case_amount_extraction" not in sys.modules and "transformers" not in sys.modules and
            "tokenizers" not in sys.modules, "Producer or tokenizer unexpectedly imported")
    return {
        "schema_version": 1, "verified": True, "kind": "independent_amount_tokenizer_archive_audit",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(), "is_model_quality_evidence": False,
        "input_files_sha256": PINS, "verifier_sha256": sha(__file__), "dataset_files_sha256": file_hashes,
        "source_files_sha256": sources, "request_counts": dict(request_counts), "runtime_requests": 4860,
        "heldout_documents": len(cases), "all_actual_candidate_B_requests": 3996,
        "candidate_sequences_per_tokenizer": len(entries), "candidate_sequences_by_head": dict(head_counts),
        "undefined_is_credit_requests_still_rendered": dict(undefined_credit_requests),
        "ordered_identity_sha256": digest(identities),
        "ordered_requests_sha256_by_split": {split: digest(requests, True) for split, requests in ordered_requests.items()},
        "independently_reconstructed_prompt_payload_sha256": payload_sha256, "models": models,
        "this_verifier_decode_log": decode_log,
        "capture_source_observation": {
            "source_sha256": PINS["reports/amount-service-eval/capture_tokenizer_lengths.py"],
            "local_input_access": "The frozen capture source decodes all family metadata for ID routing, then JSON-decodes each case's leading ID and skips non-test/OOD families before full case decoding. Nonheldout case references are not decoded. All split files are only hashed. Only heldout state/questions produce prompts.",
            "B_construction": "Capture calls the frozen amount_attributes builder on every actual candidate. This auditor uses the already audited B sidecar requests and matches the full prompt payload exactly; no producer module is imported here.",
            "execution": "Capture sends the prompt payload by SSH to cached pinned tokenizers. Source requests local_files_only, HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE, empty CUDA visibility, disabled tokenizer parallelism, and one OMP/Rayon thread. It applies a single user-message chat template with add_generation_prompt=True and enable_thinking=False, without truncation. This is source/configuration evidence, not independent process monitoring.",
        },
        "scope": {
            "tokenizer_rerun": False, "model_loaded": False, "SSH_or_network_used": False, "GPU_used": False,
            "producer_oracle_imported": False, "full_corpus_audit_rerun": False,
            "nonheldout_case_payloads_decoded": 0, "family_payloads_decoded_by_this_verifier": 0,
            "split_files_hashed_without_parsing": ["train.jsonl", "calibration.jsonl", "validation.jsonl", "test.jsonl", "ood.jsonl"],
            "independent_token_count_recomputation": False,
            "verified": "Exact frozen request lineage/order, complete runtime head coverage including undefined-credit prompts, exact prompt payload, ordered archive identities, model/revision metadata, capture hashes and recorded length arithmetic.",
            "limitation": "Token counts remain observations from the pinned tokenizer capture; this audit does not independently tokenize or authenticate tokenizer bytes. Every possible B input is a length path, not an A prediction, and no model quality is measured.",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output
    require(not output.exists() and not output.is_symlink() and
            not output.resolve().is_relative_to((ROOT / "data").resolve()), "Choose a new audit output outside immutable data")
    report = verify()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"verified": True, "candidate_sequences_per_tokenizer": report["candidate_sequences_per_tokenizer"],
                      "prompt_payload_sha256": report["independently_reconstructed_prompt_payload_sha256"],
                      "models": report["models"], "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
