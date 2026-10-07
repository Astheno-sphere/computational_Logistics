"""Freeze contact service test/OOD IDs, order and visible-input denominators.

Non-heldout JSONL payloads are never decoded. Sidecar split routing uses only an
anchored ASCII metadata prefix before any full JSON decoding. No model or HTTP.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jev.api import compile_request
from jev.data import SPLITS, validate_records

HELDOUT = ("test", "ood")
PINS = {
    "email": {
        "dataset": "email-selection-control-v1",
        "manifest": "4c18cc791425003c5c8f052ce27ed034dfb54c79ddac24de13f7290ab3b3316c",
        "helper": "72d0b27f84b1d898dc3d49703ae95910e5303b5b6096104961df1ef827c7ebb4",
    },
    "phone": {
        "dataset": "phone-extraction-control-v1",
        "manifest": "1001f1e04795308bf4f68db51076e8e1e1e47802986de54fc33b3b8d33548cfb",
        "helper": "bb934c4bdff11e3cdaf94d54a36dd8257ff4df67db6b76ed3110fcff57abb700",
        "independent_audit": "55d01633df0bd7509caf5f13d90ede380b4d0c13dc90c3cccc43fe2936083b60",
    },
}
IDENTIFIER = rb"[A-Za-z0-9:_-]+"
PREFIXES = {
    "cases": re.compile(rb'\A\{"id":"(?P<id>' + IDENTIFIER + rb')","family_id":"(?P<family_id>' + IDENTIFIER +
                        rb')","group_id":"(?P<group_id>' + IDENTIFIER + rb')","split":"(?P<split>train|calibration|validation|test|ood)",'),
    "families": re.compile(rb'\A\{"id":"(?P<id>' + IDENTIFIER + rb')","group_id":"(?P<group_id>' + IDENTIFIER +
                           rb')","split":"(?P<split>train|calibration|validation|test|ood)",'),
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


def sequence_sha256(values):
    """SHA256 of UTF-8 compact JSON string array, preserving order; no newline."""
    require(isinstance(values, list) and all(isinstance(value, str) for value in values), "ID sequence must be a string list")
    encoded = json.dumps(values, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def heldout_sidecar(path, kind, decode_log):
    """Never pass a non-heldout payload to json.loads, including family sidecars."""
    prefix_counts, decoded_counts, seen_ids, group_splits = Counter(), Counter(), set(), {}
    selected = []
    with Path(path).open("rb") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            # Current frozen serializers put these short ASCII metadata fields
            # first. Changed/reordered/escaped prefixes fail closed, not by
            # falling back to parsing an entire possibly-training JSON object.
            found = PREFIXES[kind].match(line[:512])
            require(found is not None, f"{path.name}:{line_number}: unsupported metadata prefix")
            meta = {key: value.decode("ascii") for key, value in found.groupdict().items()}
            split = meta["split"]
            require(meta["id"] not in seen_ids, f"{path.name}: duplicate metadata ID")
            require(meta["group_id"] not in group_splits or group_splits[meta["group_id"]] == split,
                    f"{path.name}: metadata group crosses splits")
            seen_ids.add(meta["id"])
            group_splits[meta["group_id"]] = split
            prefix_counts[split] += 1
            if split not in HELDOUT:
                continue
            record = json.loads(line)
            decoded_counts[split] += 1
            require(all(record[key] == value for key, value in meta.items()), "decoded metadata disagrees with byte prefix")
            selected.append(record)
    decode_log[kind + ".jsonl"] = {
        "prefix_routed_lines_by_split": {split: prefix_counts[split] for split in SPLITS},
        "full_payloads_decoded_by_split": {split: decoded_counts[split] for split in SPLITS},
        "non_heldout_payloads_decoded": sum(decoded_counts[split] for split in SPLITS if split not in HELDOUT),
    }
    return selected


def load_helper(kind, pin):
    path = ROOT / "reports" / pin["dataset"] / "verify.py"
    require(sha256(path) == pin["helper"], "reviewed visible-input helper hash differs")
    spec = importlib.util.spec_from_file_location("contact_preflight_" + kind, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def dataset_preflight(kind, data_root):
    pin = PINS[kind]
    directory = data_root / pin["dataset"]
    manifest_path = directory / "manifest.json"
    require(sha256(manifest_path) == pin["manifest"], "frozen " + kind + " manifest hash differs")
    manifest = json.loads(manifest_path.read_bytes())
    file_names = [split + ".jsonl" for split in SPLITS] + ["families.jsonl", "cases.jsonl"]
    file_hashes = {name: sha256(directory / name) for name in file_names}
    require(file_hashes == manifest["files_sha256"], "frozen dataset file hashes differ")
    sources = {name: sha256(ROOT / "jev" / name) for name in manifest["configuration"]["source_files_sha256"]}
    require(sources == manifest["configuration"]["source_files_sha256"], "frozen producer/API source hashes differ")
    helper, helper_path = load_helper(kind, pin)
    audited_reference_source = None
    if kind == "phone":
        audit_path = ROOT / "reports" / pin["dataset"] / "independent-audit.json"
        require(sha256(audit_path) == pin["independent_audit"], "reviewed phone reference audit hash differs")
        audited_reference_source = {"path": str(audit_path.relative_to(ROOT)), "sha256": pin["independent_audit"]}
    decode_log = {}
    cases = heldout_sidecar(directory / "cases.jsonl", "cases", decode_log)
    families = heldout_sidecar(directory / "families.jsonl", "families", decode_log)
    family_by_id = {family["id"]: family for family in families}
    by_family = defaultdict(list)
    cases_by_split = {split: [] for split in HELDOUT}
    expected_by_split = {split: [] for split in HELDOUT}
    denominators = {split: Counter() for split in HELDOUT}
    reference_formatting = {split: Counter() for split in HELDOUT}
    reference_review_reasons = {split: Counter() for split in HELDOUT}
    for case in cases:
        split = case["split"]
        require(case["family_id"] in family_by_id, "heldout case has no heldout family")
        family = family_by_id[case["family_id"]]
        require(all(case[key] == family[key] for key in ("group_id", "split", "template_id")), "heldout case/family linkage differs")
        request = case["request"] if kind == "email" else case["selection_request"]
        visible = helper.selection(request["state"])
        saved = case["reference"] if kind == "email" else case["selection_reference"]
        require(saved == visible, "heldout selection reference differs from reviewed visible-input reconstruction")
        reason = visible["reason"]
        require(reason in ("recalled", "candidate_miss", "target_absent", "ambiguous_target"), "unexpected heldout denominator class")
        denominators[split][reason] += 1
        omissions = []

        def associate(stage, actual_request, candidate_id=None):
            for compiled in compile_request(**actual_request):
                head = compiled["id"]
                if len(compiled["options"]) == 1:
                    omissions.append({"head": head, "reason": "forced_single_candidate"} if kind == "email" else
                                     {"stage": stage, "head": head, "reason": "forced_single_candidate"})
                    continue
                row_id = case["id"] + ":" + head if kind == "email" else f"{case['id']}:{stage}:{candidate_id or 'request'}:{head}"
                head_key = head if kind == "email" else stage + "/" + head
                expected_by_split[split].append({"id": row_id, "case_id": case["id"], "family_id": case["family_id"],
                                                "group_id": case["group_id"], "head": head_key, "question_id": head,
                                                "stage": stage, "candidate_id": candidate_id, "compiled": compiled,
                                                "selection_answer": visible[head] if stage == "selection" else None})

        associate("selection", request)
        if kind == "phone":
            candidates = request["state"]["candidates"]
            require([item["candidate_id"] for item in case["attributes"]] == list(candidates), "heldout B does not cover actual A candidates")
            for item in case["attributes"]:
                state = item["request"]["state"]
                candidate_id = item["candidate_id"]
                require(state == {"text": request["state"]["text"], "policy": request["state"]["policy"],
                                  "selected_id": candidate_id, "selected": candidates[candidate_id]}, "heldout B candidate binding differs")
                associate("attributes", item["request"], candidate_id)
                if reason == "recalled" and candidate_id == visible["span"]:
                    # These semantic B references were checked in the pinned
                    # independent audit. Reuse them only for fixed denominators;
                    # never substitute a reference decision for model output.
                    normal = helper.normalized(state, item["reference"])
                    require(normal == item["normalized_reference"], "heldout normalized reference linkage differs")
                    require(normal["status"] in ("formatted", "review"), "unexpected reference normalization status")
                    reference_formatting[split][normal["status"]] += 1
                    if normal["status"] == "review":
                        reference_review_reasons[split][normal["reason"]] += 1
                        reference_formatting[split]["region_" + item["reference"]["region"]] += 1
                    elif normal["valid"] is False:
                        reference_formatting[split]["formatted_but_metadata_invalid"] += 1
        require(case["omitted_supervision"] == omissions, "heldout singleton omission differs")
        cases_by_split[split].append(case)
        by_family[case["family_id"]].append(case["id"])
    for family in families:
        require(family["case_ids"] == by_family[family["id"]], "heldout family case index differs")
    split_reports, all_heldout_rows = {}, []
    for split in HELDOUT:
        path = directory / (split + ".jsonl")
        rows = []
        with path.open("rb") as stream:
            for line in stream:
                if line.strip():
                    row = json.loads(line)
                    require(row["split"] == split, "heldout row is in wrong split file")
                    rows.append(row)
        decode_log[split + ".jsonl"] = {"full_payloads_decoded": len(rows), "split": split}
        expected = expected_by_split[split]
        require(len(rows) == len(expected) == manifest["counts"][split], "heldout typed-record count differs")
        heads = defaultdict(list)
        for row, linked in zip(rows, expected):
            require(row["id"] == linked["id"] and row["group_id"] == linked["group_id"] and row["source"] == pin["dataset"],
                    "heldout typed-record identity/order differs from cases")
            require(all(row[key] == linked["compiled"][key] for key in ("state", "question", "kind", "options")), "heldout typed record differs from associated request")
            metadata = row["metadata"]
            require(metadata["case_id"] == linked["case_id"] and metadata["document_family_id"] == linked["family_id"] and
                    metadata["question_id"] == linked["question_id"], "heldout typed-record metadata linkage differs")
            if kind == "phone":
                require(metadata["stage"] == linked["stage"] and metadata["candidate_id"] == linked["candidate_id"], "heldout phone stage/candidate linkage differs")
            if linked["stage"] == "selection":
                answer = str(linked["selection_answer"]).lower() if row["kind"] == "noul" else linked["selection_answer"]
                require(row["target"] == [float(key == answer) for key in linked["compiled"]["answer_keys"]], "heldout A target differs from visible-input reference")
            heads[linked["head"]].append(row["id"])
        case_ids = [case["id"] for case in cases_by_split[split]]
        group_ids = list(dict.fromkeys(case["group_id"] for case in cases_by_split[split]))
        family_ids = list(dict.fromkeys(case["family_id"] for case in cases_by_split[split]))
        counts = denominators[split]
        require(sum(counts.values()) == len(case_ids), "denominators do not cover every heldout document")
        fixed_denominators = {"unique_present": counts["recalled"] + counts["candidate_miss"],
                              "unique_present_recalled": counts["recalled"], "unique_present_missed": counts["candidate_miss"],
                              "absent": counts["target_absent"], "ambiguous": counts["ambiguous_target"],
                              "target_present_documents": counts["recalled"] + counts["candidate_miss"] + counts["ambiguous_target"]}
        if kind == "email":
            fixed_denominators["unique_present_recalled_reference_copyable"] = counts["recalled"]
        else:
            formatting = reference_formatting[split]
            require(formatting["formatted"] + formatting["review"] == counts["recalled"], "reference statuses omit recalled targets")
            require(formatting["region_unknown"] + formatting["region_review"] == formatting["review"], "reference review regions differ")
            fixed_denominators.update({"unique_present_recalled_reference_formattable": formatting["formatted"],
                                      "unique_present_recalled_reference_review": formatting["review"],
                                      "reference_review_region_unknown": formatting["region_unknown"],
                                      "reference_review_region_review": formatting["region_review"],
                                      "reference_formattable_but_metadata_invalid": formatting["formatted_but_metadata_invalid"]})
        row_ids = [row["id"] for row in rows]
        split_reports[split] = {
            "documents": len(case_ids), "groups": len(group_ids),
            "denominators": fixed_denominators,
            "case_ids": case_ids, "case_ids_sha256": sequence_sha256(case_ids),
            "group_ids": group_ids, "group_ids_sha256": sequence_sha256(group_ids),
            "family_ids": family_ids, "family_ids_sha256": sequence_sha256(family_ids),
            "typed_records": len(rows), "typed_record_ids": row_ids, "typed_record_ids_sha256": sequence_sha256(row_ids),
            "heads": {head: {"records": len(ids), "record_ids": ids, "record_ids_sha256": sequence_sha256(ids)} for head, ids in sorted(heads.items())},
        }
        if kind == "phone":
            split_reports[split]["reference_review_reasons"] = dict(sorted(reference_review_reasons[split].items()))
        all_heldout_rows.extend(rows)
    schema = validate_records(all_heldout_rows)
    require(set(split_reports["test"]["group_ids"]).isdisjoint(split_reports["ood"]["group_ids"]), "heldout groups overlap")
    require(all(sha256(directory / name) == digest for name, digest in file_hashes.items()) and sha256(manifest_path) == pin["manifest"], "frozen input changed during preflight")
    return {"dataset": pin["dataset"], "manifest_sha256": pin["manifest"], "files_sha256": file_hashes,
            "source_files_sha256": sources, "reused_helper": {"path": str(helper_path.relative_to(ROOT)), "sha256": pin["helper"],
                "functions": ["selection", "fields and candidate scanner called by selection"] + (["normalized, using audited sidecar B references only"] if kind == "phone" else []),
                "full_corpus_verify_called": False},
            "reference_formatting_denominator_source": audited_reference_source,
            "payload_access": {"sidecar_decode_log": decode_log,
                "split_files_hashed_without_parsing": [split + ".jsonl" for split in SPLITS if split not in HELDOUT],
                "non_heldout_targets_parsed": False, "phone_B_semantic_targets_recomputed": False},
            "heldout_schema_summary": schema, "splits": split_reports}


def verify(data_root):
    results = {kind: dataset_preflight(kind, Path(data_root)) for kind in PINS}
    return {"verified": True, "kind": "frozen_contact_heldout_input_preflight", "splits": list(HELDOUT),
            "sequence_hash_algorithm": "SHA256 of UTF-8 json.dumps(ID_string_list, ensure_ascii=False, separators=(',', ':'), allow_nan=False); no trailing newline. No sorting or Unicode normalization.",
            "ordering": {"case_ids": "Original cases.jsonl line order, filtered by the exact prefix split.",
                         "group_ids_and_family_ids": "First appearance in that split's case sequence, deduplicated without sorting.",
                         "typed_record_ids": "Original split JSONL line order, required to equal case-order request compilation, excluding declared singleton omissions.",
                         "per_head_record_ids": "Original split JSONL order filtered to that head."},
            "datasets": results, "preflight_script_sha256": sha256(__file__),
            "scope": {"model_inference_performed": False, "http_calls_performed": False, "phone_metadata_library_loaded": "phonenumbers" in sys.modules,
                      "benchmark_or_JF100_read": False, "producer_oracles_imported": False, "non_heldout_payloads_json_decoded": False,
                      "sample_selection": "All frozen test/OOD case IDs; no target-based subsampling.",
                      "reference_denominators": "A presence/recall is reconstructed from visible inputs. Phone formatting/review counts reuse pinned independently audited B sidecar references only for the actual recalled target; B semantic targets are not recomputed here. Unknown/conflict/invalid review samples and candidate misses remain in total unique_present. Correct review is a guard result, not extraction success. These reference criteria fix denominators only and never replace model predictions.",
                      "purpose": "Fix input IDs, order and denominators only. This is not prediction, service correctness or model performance evidence."}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--output", type=Path, help="New report file outside the input data root")
    args = parser.parse_args(argv)
    if args.output:
        require(not args.output.is_symlink(), "report output must not be a symlink")
        data_root, output = args.data_root.resolve(), args.output.resolve()
        require(output != data_root and data_root not in output.parents, "report output must be outside the input data root")
        require(not args.output.exists(), "report output already exists")
    report = verify(args.data_root)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    # Keep console output aggregate-only; the artifact contains complete ID lists.
    print(json.dumps({"verified": report["verified"], "preflight_script_sha256": report["preflight_script_sha256"],
                      "datasets": {kind: {split: {key: values[key] for key in ("documents", "groups", "denominators", "case_ids_sha256", "typed_records", "typed_record_ids_sha256")}
                                          for split, values in result["splits"].items()} for kind, result in report["datasets"].items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
