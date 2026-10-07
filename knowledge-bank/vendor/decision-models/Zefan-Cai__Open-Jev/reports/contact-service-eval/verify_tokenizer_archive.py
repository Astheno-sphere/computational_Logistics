"""Offline input-lineage and arithmetic check of the captured tokenizer archive.

No tokenizer, model, producer oracle, network or non-heldout case JSON is loaded.
The captured token counts are checked for consistency, not independently rerun.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from jev.api import candidate_prompts, compile_request

PINS = {
    "reports/contact-service-eval/tokenizer-lengths.json": "d23b1caefc8035706c02c94916bd64e057241b450833b4e0677f41840565e6aa",
    "reports/contact-service-eval/tokenizer-lengths-raw.json.gz": "b602c182dbac1a2c611fa91b8045af3c80f51c3564bb1a2293dc7d6e4bd43fff",
    "reports/contact-service-eval/capture_tokenizer_lengths.py": "af7311df60970566c230377548ac39c8f3dc45ef024c27e7145b27563c47893e",
    "reports/contact-service-eval/verify_heldout.py": "e7bcdaa11aa382e8dec2f449a1ec6ffb75e3edea2a8643ad7131d989aec8f861",
}
CORPORA = ("email-selection-control-v1", "phone-extraction-control-v1")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def verify():
    for name, expected in PINS.items():
        require(sha(ROOT/name) == expected, "Pinned capture/helper input changed: "+name)
    summary = json.loads((ROOT/"reports/contact-service-eval/tokenizer-lengths.json").read_bytes())
    archive_path = ROOT/"reports/contact-service-eval/tokenizer-lengths-raw.json.gz"
    archive = json.loads(gzip.decompress(archive_path.read_bytes()))
    require(set(archive) == {"entries", "result"}, "Unexpected archive payload")
    require(summary["raw_lengths_sha256"] == summary["tracked_raw_lengths"]["sha256"] == sha(archive_path), "Archive references disagree")
    require(summary["capture_script_sha256"] == PINS["reports/contact-service-eval/capture_tokenizer_lengths.py"], "Capture source pin disagrees")
    spec = importlib.util.spec_from_file_location("independent_heldout_prefix_reader", ROOT/"reports/contact-service-eval/verify_heldout.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    entries, request_counts, decode_logs, corpus_inputs = [], Counter(), {}, {}
    for corpus in CORPORA:
        folder = ROOT/"data"/corpus
        manifest_path = folder/"manifest.json"
        require(sha(manifest_path) == summary["dataset_manifest_sha256"][corpus], "Corpus manifest pin differs")
        manifest = json.loads(manifest_path.read_bytes())
        require(sha(folder/"cases.jsonl") == manifest["files_sha256"]["cases.jsonl"], "Case bytes differ")
        for name, expected in manifest["configuration"]["source_files_sha256"].items():
            require(sha(ROOT/"jev"/name) == expected == summary["source_files_sha256"]["jev/"+name], "Pinned runtime source differs")
        decode_log = {}
        cases = reader.heldout_sidecar(folder/"cases.jsonl", "cases", decode_log)
        decode_logs[corpus] = decode_log
        corpus_inputs[corpus] = {"manifest_sha256": sha(manifest_path), "cases_sha256": sha(folder/"cases.jsonl"), "heldout_documents": len(cases)}
        for case in cases:
            a_request = case["request"] if corpus.startswith("email") else case["selection_request"]
            requests = [("selection", None, a_request)]
            if corpus.startswith("phone"):
                expected_ids = list(a_request["state"]["candidates"])
                require([item["candidate_id"] for item in case["attributes"]] == expected_ids, "All-candidate B order differs")
                for item in case["attributes"]:
                    actual = item["request"]
                    require(actual["state"] == {"text": a_request["state"]["text"], "policy": a_request["state"]["policy"],
                                                "selected_id": item["candidate_id"], "selected": a_request["state"]["candidates"][item["candidate_id"]]},
                            "B input is not bound to its actual candidate")
                    requests.append(("attributes", item["candidate_id"], actual))
            for stage, candidate_id, request in requests:
                require(set(request) == {"state", "questions"}, "Model request contains auxiliary fields")
                request_counts[corpus+"/"+case["split"]+"/"+stage] += 1
                for record in compile_request(**request):
                    for index, prompt in enumerate(candidate_prompts(record)):
                        entries.append({"corpus": corpus, "split": case["split"], "case_id": case["id"], "stage": stage,
                                        "candidate_id": candidate_id, "head": record["id"], "option_index": index, "prompt": prompt})
    identities = [{key: value for key, value in entry.items() if key != "prompt"} for entry in entries]
    require(identities == archive["entries"], "Archive case/stage/head/option identities or order differ")
    require(len({compact(item) for item in identities}) == len(identities), "Duplicate candidate-sequence identity")
    models = {tag: [summary["models"][tag]["model"], summary["models"][tag]["revision"]] for tag in ("2b", "9b", "27b")}
    payload_hash = hashlib.sha256(compact({"models": models, "entries": entries})).hexdigest()
    require(payload_hash == summary["prompt_payload_sha256"], "Reconstructed label-free prompt payload hash differs")
    require(dict(request_counts) == summary["request_counts"], "Request counts differ")
    require(len(entries) == summary["candidate_sequences"], "Sequence count differs")
    result = archive["result"]
    require(result["cuda_visible_devices"] == summary["cuda_visible_devices"] == "", "Captured CUDA visibility differs")
    model_reports = {}
    for tag, raw in result["models"].items():
        saved = summary["models"][tag]
        require(all(raw[key] == saved[key] for key in ("model", "revision", "tokenizer_class", "chat_template_sha256")), "Tokenizer identity differs")
        lengths = raw["lengths"]
        require(len(lengths) == len(identities) and all(type(value) is int and value > 0 for value in lengths), "Invalid or incomplete lengths")
        maximum = max(lengths)
        calculated = {"sequences": len(lengths), "minimum": min(lengths), "maximum": maximum,
                      "over_4096": sum(value > 4096 for value in lengths), "over_16384": sum(value > 16384 for value in lengths),
                      "maximum_example": identities[lengths.index(maximum)]}
        require(all(saved[key] == value for key, value in calculated.items()), "Saved length arithmetic differs")
        model_reports[tag] = {**calculated, "lengths_sha256": hashlib.sha256(compact(lengths)).hexdigest()}
    require(set(model_reports) == set(models), "Missing or unexpected model tokenizer capture")
    return {"schema_version": 1, "verified": True, "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            "input_files_sha256": PINS, "verifier_sha256": sha(__file__), "corpus_inputs": corpus_inputs,
            "request_counts": dict(request_counts), "candidate_sequences_per_tokenizer": len(entries),
            "ordered_identity_sha256": hashlib.sha256(compact(identities)).hexdigest(),
            "independently_reconstructed_prompt_payload_sha256": payload_hash, "models": model_reports,
            "this_verifier_decode_log": decode_logs,
            "capture_source_observation": "The preserved capture source json.loads-decoded every case line locally before split filtering, including training reference fields. Those references were not used to select or render prompts. Only heldout A and every heldout actual-candidate B request are in the reconstructed payload and archive. This verifier filters bytes before full case decoding.",
            "scope": {"tokenizer_rerun": False, "model_loaded": False, "http_or_network_used": False, "gpu_used": False,
                      "producer_oracle_imported": False, "independent_token_count_recomputation": False,
                      "verified": "Frozen request lineage, exact prompt payload, complete ordered sequence identities, recorded length arithmetic and capture/helper hashes.",
                      "limitation": "Token lengths remain observations from the pinned tokenizer capture; this offline audit does not independently run tokenization or prove model quality. All possible B inputs are length paths, not A predictions."}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    output = args.output
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to((ROOT/"data").resolve()):
        raise ValueError("Choose a new audit report outside frozen data")
    report = verify()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"verified": True, "candidate_sequences_per_tokenizer": report["candidate_sequences_per_tokenizer"],
                      "prompt_payload_sha256": report["independently_reconstructed_prompt_payload_sha256"], "output": str(output)}))


if __name__ == "__main__":
    main()
