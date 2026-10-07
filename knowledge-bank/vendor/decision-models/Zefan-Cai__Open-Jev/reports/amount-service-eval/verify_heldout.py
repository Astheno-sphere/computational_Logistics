"""Read-only heldout amount request/denominator preflight; no producer oracle.

Only test/OOD targets are decoded. B references are reused from an existing,
hash-pinned independent audit, not regenerated or used as model predictions.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import compile_request
from jev.data import validate_records

VERSION = "amount-extraction-control-v1"
SPLITS = ("train", "calibration", "validation", "test", "ood")
HELDOUT = ("test", "ood")
PINS = {
    "data/amount-extraction-control-v1/manifest.json": "6f89f81336ac36505c563193da27fca2155fa566175451854f0ac410979ea80b",
    "reports/amount-extraction-control-v1/verify.py": "dc4727e62791af8b8ac2776358868c2f1f6ed810387ecae00e6d5087e39aef24",
    "reports/amount-extraction-control-v1/independent-audit.json": "ed9f0aaf9f1c40fde1379d4655f40b1199b621ea204cc853b00fec2581fd2e22",
    "reports/contact-service-eval/verify_heldout.py": "e7bcdaa11aa382e8dec2f449a1ec6ffb75e3edea2a8643ad7131d989aec8f861",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def encoded(value, sort_keys=False):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=sort_keys, allow_nan=False).encode()


def digest(value, sort_keys=False):
    return hashlib.sha256(encoded(value, sort_keys)).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def verify(data_root):
    for path, expected in PINS.items():
        require(sha256(ROOT / path) == expected, "Pinned preflight dependency changed: " + path)
    directory = data_root / VERSION
    manifest = json.loads((directory / "manifest.json").read_bytes())
    require(sha256(directory / "manifest.json") == PINS["data/amount-extraction-control-v1/manifest.json"], "Frozen amount manifest differs")
    input_hashes = {name: sha256(directory / name) for name in manifest["files_sha256"]}
    require(input_hashes == manifest["files_sha256"], "Frozen corpus file differs")
    sources = {name: sha256(ROOT / "jev" / name) for name in manifest["configuration"]["source_files_sha256"]}
    require(sources == manifest["configuration"]["source_files_sha256"], "Frozen producer/API/recipe source differs")
    previous = json.loads((ROOT / "reports/amount-extraction-control-v1/independent-audit.json").read_bytes())
    require(previous["verified"] and previous["source_files_sha256"] == sources and
            all(previous["files_sha256"][name] == value for name, value in input_hashes.items()), "Existing independent audit pins differ")
    prefix = module("amount_heldout_prefix", ROOT / "reports/contact-service-eval/verify_heldout.py")
    helper = module("amount_visible_inputs", ROOT / "reports/amount-extraction-control-v1/verify.py")
    decode_log = {}
    families = prefix.heldout_sidecar(directory / "families.jsonl", "families", decode_log)
    cases = prefix.heldout_sidecar(directory / "cases.jsonl", "cases", decode_log)
    family_index = {row["id"]: row for row in families}
    family_cases = defaultdict(list)
    expected_rows = {split: [] for split in HELDOUT}
    expected_omissions = {split: Counter() for split in HELDOUT}
    requests = {split: [] for split in HELDOUT}
    denominators = {split: Counter() for split in HELDOUT}
    attributes = {split: Counter() for split in HELDOUT}
    head_counts = {split: Counter() for split in HELDOUT}
    expected_ids = set()

    for case in cases:
        split = case["split"]
        family = family_index[case["family_id"]]
        require(all(case[key] == family[key] for key in ("group_id", "split", "template_id")), "Case/family linkage differs")
        request = case["selection_request"]
        reference = helper.selection(request["state"])
        require(reference == case["selection_reference"], "Selection differs from independent visible text/offset reconstruction")
        reason = reference["reason"]
        denominators[split][reason] += 1
        denominators[split]["target_present_documents"] += int(reference["target_present"])
        denominators[split]["unique_present"] += int(len(reference["target_spans"]) == 1)
        omissions = []

        def associate(stage, current, ref, candidate=None):
            require(current == helper.expected_request(current["state"], stage), "Visible runtime request schema differs")
            requests[split].append({"case_id": case["id"], "family_id": case["family_id"], "group_id": case["group_id"],
                "split": split, "stage": stage, "candidate_id": candidate,
                "request_sha256": digest(current), "canonical_request_sha256": digest(current, True)})
            for compiled in compile_request(**current):
                head = compiled["id"]
                omitted = "forced_single_candidate" if len(compiled["options"]) == 1 else "undefined_direction" if ref[head] is None else None
                if omitted:
                    omissions.append({"stage": stage, "candidate_id": candidate, "head": head, "reason": omitted})
                    expected_omissions[split][omitted] += 1
                    continue
                row_id = f"{case['id']}:{stage}:{candidate or 'request'}:{head}"
                require(row_id not in expected_ids, "Duplicate expected typed row")
                expected_ids.add(row_id)
                target_key = str(ref[head]).lower() if compiled["kind"] == "noul" else ref[head]
                expected_rows[split].append({"id": row_id, "case_id": case["id"], "family_id": case["family_id"],
                    "group_id": case["group_id"], "stage": stage, "candidate_id": candidate, "head": head,
                    "compiled": compiled, "target": [float(key == target_key) for key in compiled["answer_keys"]]})
                head_counts[split][stage + "/" + head] += 1

        associate("selection", request, reference)
        candidates = request["state"]["candidates"]
        require([row["candidate_id"] for row in case["attributes"]] == list(candidates), "All-candidate B coverage/order differs")
        for row in case["attributes"]:
            candidate = row["candidate_id"]
            state, ref, normal = row["request"]["state"], row["reference"], row["normalized_reference"]
            require(state == {"text": request["state"]["text"], "policy": request["state"]["policy"],
                              "selected_id": candidate, "selected": candidates[candidate]}, "B bound to a different candidate")
            require(type(ref["direction_known"]) is bool and
                    ((type(ref["is_credit"]) is bool) if ref["direction_known"] else ref["is_credit"] is None),
                    "Defined is_credit must follow reference direction_known")
            require(normal["status"] in ("ready", "review"), "Unexpected normalizer reference status")
            require((normal["amount"] is not None and normal["currency"] is not None) if normal["status"] == "ready" else
                    (normal["amount"] is None and normal["currency"] is None), "Reference ready/review value schema differs")
            # B semantic labels/normalization were established by the hash-pinned
            # previous independent audit. Reuse these sealed sidecars only for
            # preregistered denominators and typed-row alignment, not predictions.
            associate("attributes", row["request"], ref, candidate)
            count = attributes[split]
            count["all_possible_actual_candidate_B"] += 1
            count["is_credit_defined" if ref["direction_known"] else "is_credit_undefined"] += 1
            count["reference_" + normal["status"]] += 1
            count["complete_field" if ref["complete_field"] else "partial_candidate"] += 1
            count["currency:" + ref["currency"]] += 1
            count["review_reason:" + (normal["reason"] or "none")] += 1
            if reason == "recalled" and candidate == reference["span"]:
                denominators[split]["unique_present_recalled_reference_" + normal["status"]] += 1
                denominators[split]["unique_present_recalled_is_credit_defined" if ref["direction_known"] else
                                    "unique_present_recalled_is_credit_undefined"] += 1
        require(case["omitted_supervision"] == omissions, "Undefined/forced typed supervision differs")
        family_cases[case["family_id"]].append(case["id"])

    require(set(family_cases) == set(family_index), "Heldout family missing complete cases")
    for family in families:
        require(family["case_ids"] == family_cases[family["id"]], "Family case IDs/order differ")
    split_reports, all_rows = {}, []
    for split in HELDOUT:
        with (directory / (split + ".jsonl")).open("rb") as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        require(len(rows) == len(expected_rows[split]), "Heldout typed row count differs")
        require([row["id"] for row in rows] == [row["id"] for row in expected_rows[split]], "Heldout typed record order differs")
        for actual, expected in zip(rows, expected_rows[split]):
            require(actual["split"] == split and actual["source"] == VERSION and actual["group_id"] == expected["group_id"], "Typed row source/split differs")
            require(all(actual[key] == expected["compiled"][key] for key in ("state", "question", "kind", "options")), "Typed input differs from actual A/B request")
            require(actual["target"] == expected["target"], "Typed target differs from frozen independently audited sidecar")
            require(all(actual["metadata"][key] == expected[source] for key, source in
                        (("case_id", "case_id"), ("document_family_id", "family_id"), ("stage", "stage"),
                         ("question_id", "head"), ("candidate_id", "candidate_id"))), "Typed candidate/head metadata differs")
        decode_log[split + ".jsonl"] = {"full_payloads_decoded": len(rows), "split": split}
        found_cases = [case for case in cases if case["split"] == split]
        found_families = [family for family in families if family["split"] == split]
        ids = {"case_ids": [case["id"] for case in found_cases], "family_ids": [family["id"] for family in found_families],
               "group_ids": [family["group_id"] for family in found_families], "typed_record_ids": [row["id"] for row in rows]}
        counts = denominators[split]
        require(counts["unique_present"] == counts["recalled"] + counts["candidate_miss"], "Unique denominator mismatch")
        require(counts["recalled"] == counts["unique_present_recalled_reference_ready"] + counts["unique_present_recalled_reference_review"], "Ready/review recalled strata mismatch")
        require(attributes[split]["is_credit_defined"] == head_counts[split]["attributes/is_credit"], "Defined is_credit typed denominator mismatch")
        require(attributes[split]["is_credit_undefined"] == expected_omissions[split]["undefined_direction"], "Undefined is_credit omission mismatch")
        split_reports[split] = {"documents": len(found_cases), "families": len(found_families), "typed_records": len(rows),
            "denominators": dict(counts), "all_candidate_B_denominators": dict(attributes[split]),
            "typed_head_counts": dict(head_counts[split]), "omitted_supervision_counts": dict(expected_omissions[split]),
            **ids, **{key + "_sha256": prefix.sequence_sha256(value) for key, value in ids.items()},
            "ordered_requests": requests[split], "ordered_requests_sha256": digest(requests[split], True),
            "request_counts": dict(Counter(row["stage"] for row in requests[split]))}
        all_rows.extend(rows)
    schema = validate_records(all_rows)
    require(all(sha256(directory / name) == expected for name, expected in input_hashes.items()), "Frozen inputs changed during preflight")
    return {"kind": "independent_amount_service_heldout_preflight", "verified": True, "dataset": VERSION,
            "preflight_script_sha256": sha256(__file__), "pinned_dependencies_sha256": PINS,
            "files_sha256": input_hashes, "source_files_sha256": sources, "splits": split_reports,
            "heldout_schema_summary": schema, "ordering": "Physical frozen case/family/typed file order; requests traverse each case A then every B in original candidate mapping order.",
            "hash_algorithm": "ID arrays: compact UTF-8 JSON string arrays, no key sorting/newline. request_sha256: compact JSON preserving original mapping order. canonical_request_sha256 and ordered_requests_sha256: sorted JSON keys, no newline.",
            "payload_access": {"nonheldout_case_or_family_targets_decoded": 0, "decode_log": decode_log,
                               "split_files_hashed_without_parsing": ["train.jsonl", "calibration.jsonl", "validation.jsonl"]},
            "scope": {"producer_oracle_used": False, "full_previous_audit_rerun": False, "model_or_HTTP_performed": False,
                      "external_benchmark_read": False, "independent_selection_reconstructed": True,
                      "B_semantic_references_recomputed": False,
                      "B_reference_source": "Existing hash-pinned independent amount audit and its exact sealed case sidecars; reused for denominators and typed-row linkage only.",
                      "denominator_warning": "All-possible-candidate B counts are conditional task coverage. Actual A-selection denominators depend on future outputs; requested-target E2E remains fixed to every unique target, including misses/errors/review."}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists() and not args.output.is_symlink() and not args.output.resolve().is_relative_to(args.data_root.resolve()),
            "Choose a new report path outside immutable data")
    result = verify(args.data_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"verified": True, "documents": sum(s["documents"] for s in result["splits"].values()),
                      "typed_records": result["heldout_schema_summary"]["records"],
                      "nonheldout_targets_decoded": 0, "splits": {key: {name: value[name] for name in
                      ("documents", "families", "typed_records", "denominators", "all_candidate_B_denominators")}
                      for key, value in result["splits"].items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
