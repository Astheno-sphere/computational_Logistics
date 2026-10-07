"""Audit fictional phone controls, exact digits, and raw/canonical split overlap.

No producer helper is imported. Pinned phonenumbers metadata is a consistency
check, not independent validity evidence. E.164 digits are assembled separately.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jev.api import compile_request
from jev.data import SPLITS, read_jsonl, validate_records
from jev.recipes import choice, noul

VERSION = "phone-extraction-control-v1"
LIBRARY_VERSION = "9.0.14"
REGIONS = ("US", "CA", "GB")
CALLING_CODES = {"US": "1", "CA": "1", "GB": "44"}
ROLES = {"card": {"Mobile": "mobile", "Billing": "billing", "Support": "support"},
         "message": {"On-call contact": "mobile", "Accounts contact": "billing", "Help desk": "support"}}
POLICY = {
    "version": "explicit-field-region-ascii-phone-v1", "supported_regions": list(REGIONS), "library": "phonenumbers==9.0.14",
    "scope": "Fictional contact controls, not a claim of real identity, number assignment, mobile line type or reachability. Do not dial.",
    "grammar": "Card fields: <role>: <phone> | Region: <region>. Message fields: <role> :: phone=<phone>; region=<region>. The region suffix may be omitted. Region is an explicit field-local ISO region declaration, never a document default. Unrecognized lines are not fields. not recorded or an empty phone value means absent.",
    "presence_rule": "A populated requested-role phone slot is present even if malformed or unrecalled. Multiple populated fields for that role are ambiguous, even if identical. Missing roles and not recorded slots are absent.",
    "selection_rule": "Select only a candidate exactly equal to the unique populated requested-role slot in text and both Python character offsets. Otherwise none. none does not establish absence. Scan all document text without the query or reference spans.",
    "region_rule": "For an actual complete candidate, use only its field's explicit US/CA/GB declaration. Missing, blank or not stated is unknown; comma-separated, unsupported or conflicting declarations require review. Calling codes +1 and +44 are shared: never infer a country from them. Reject disagreement with the parsed calling code or a different region identified by pinned library metadata; unresolved metadata does not override an explicit declaration. Invalid syntax, impossible length or implicit digit repair requires review. This policy does not prove physical location or ownership.",
    "format_rule": "ASCII digits only, optional leading +, single ASCII space/dot/hyphen between digit groups. No parentheses, extensions, vanity letters, Unicode digits/separators, IDD prefixes or inferred digits. International digits must equal E.164 digits after removing separators. National digits must equal the pinned library NATIONAL digits; thus unrequested trunk-prefix repair is rejected. Offsets are Unicode character positions, not UTF-8 bytes.",
    "normalization_rule": "Normalize only the actual B candidate and a matching supported region decision. Refuse unknown, conflicts, partial spans, unsupported formatting, impossible numbers and digit repair. Also refuse metadata IS_POSSIBLE_LOCAL_ONLY: a locally plausible phone missing its area code is incomplete for E.164 even when possible=true. E.164 formatting may be returned when globally possible=true and valid=false: formatting is distinct from metadata validity and both are distinct from routability. Record possible, valid and valid_for_region separately. Routability is always unverified. No calls or identity lookups occur.",
}
PHONE = re.compile(r"(?<![\w+])(?:\+)?[0-9](?:[0-9 .()\t-]*[0-9])?(?!\w)")
VARIANTS = {"international", "national", "other_role", "missing_role", "unrecorded", "no_candidates", "unknown_region",
            "missing_region_suffix", "region_conflict", "ambiguous_region", "unsupported_region", "duplicate_target", "repeated_value",
            "extension_partial", "unicode_space_miss", "parenthesized_partial", "impossible_length", "international_digit_repair",
            "malformed_format", "unrelated_note"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digits(value):
    return "".join(char for char in value if "0" <= char <= "9")


def candidates(text):
    require(isinstance(text, str), "document must be text")
    found = [match for match in PHONE.finditer(text) if len(digits(match.group())) >= 7]
    return {f"span_{index}": {"text": match.group(), "start": match.start(), "end": match.end()} for index, match in enumerate(found)}


def fields(text, policy):
    require(isinstance(text, str) and isinstance(policy, dict), "invalid document/policy")
    require(set(policy) == set(POLICY) | {"layout", "roles"} and all(policy[key] == value for key, value in POLICY.items()), "unsupported policy")
    require(policy["layout"] in ROLES and policy["roles"] == ROLES[policy["layout"]], "unsupported role/layout mapping")
    result, offset = [], 0
    for line in text.split("\n"):
        for label, role in policy["roles"].items():
            prefix = label + (": " if policy["layout"] == "card" else " :: phone=")
            if not line.startswith(prefix):
                continue
            delimiter = " | Region: " if policy["layout"] == "card" else "; region="
            value, separator, region = line[len(prefix):].partition(delimiter)
            start = offset + len(prefix)
            result.append({"role": role, "value": value, "region": region if separator else None, "start": start, "end": start + len(value)})
        offset += len(line) + 1
    return result


def format_supported(value):
    if not isinstance(value, str):
        return False
    value = value[1:] if value.startswith("+") else value
    groups = re.split(r"[ .-]", value)
    return bool(groups) and all(group and all("0" <= char <= "9" for char in group) for group in groups)


def independent_e164(raw, region):
    """Assemble digits from an explicit region; never copy a producer/library E164."""
    if not format_supported(raw) or region not in CALLING_CODES:
        return None
    number = digits(raw)
    if raw.startswith("+"):
        code = CALLING_CODES[region]
        if not number.startswith(code):
            return None
        national = number[len(code):]
    elif region in ("US", "CA"):
        national = number
    else:
        if not number.startswith("0"):
            return None
        national = number[1:]
    # This original corpus uses ten-digit US/CA national numbers and the UK
    # ten-digit NSN formats. Local-only NANP fragments never become full E.164.
    if len(national) != 10 or national.startswith("0"):
        return None
    return "+" + CALLING_CODES[region] + national


def selection(state):
    require(set(state) == {"text", "requested_role", "policy", "candidates"}, "selection state fields differ")
    parsed = fields(state["text"], state["policy"])
    require(state["requested_role"] in state["policy"]["roles"].values(), "undeclared requested role")
    actual = candidates(state["text"])
    require(actual == state["candidates"] and len(actual) <= 254, "candidate extraction differs")
    targets = [{"text": item["value"], "start": item["start"], "end": item["end"]} for item in parsed
               if item["role"] == state["requested_role"] and item["value"] not in ("", "not recorded")]
    selected, recalled = "none", None
    if len(targets) == 1:
        matches = [key for key, value in actual.items() if value == targets[0]]
        selected, recalled = (matches[0] if matches else "none"), bool(matches)
    reason = "target_absent" if not targets else "ambiguous_target" if len(targets) > 1 else "recalled" if recalled else "candidate_miss"
    return {"span": selected, "target_present": bool(targets), "target_spans": targets, "candidate_recalled": recalled, "reason": reason}


def inspect(state, library):
    require(set(state) == {"text", "policy", "selected_id", "selected"}, "attribute state fields differ")
    require(candidates(state["text"]).get(state["selected_id"]) == state["selected"], "selected candidate binding differs")
    parsed = fields(state["text"], state["policy"])
    span = state["selected"]
    full = [field for field in parsed if (field["value"], field["start"], field["end"]) == (span["text"], span["start"], span["end"])]
    declared = full[0]["region"] if full else None
    result = {"region": "review", "reason": None, "complete_field": bool(full), "format_supported": format_supported(span["text"]),
              "declared_region": declared, "possible": None, "valid": None, "valid_for_region": None, "metadata_region": None,
              "e164": None, "routable": "unverified", "library_version": LIBRARY_VERSION}
    if not full:
        result["reason"] = "partial_or_unbound_candidate"
    elif not result["format_supported"]:
        result["reason"] = "unsupported_format"
    elif declared in (None, "", "not stated"):
        result.update(region="unknown", reason="region_missing")
    elif declared not in REGIONS:
        result["reason"] = "unsupported_or_ambiguous_region"
    else:
        try:
            number = library.parse(span["text"], declared)
        except library.NumberParseException:
            result["reason"] = "parse_failure"
            return result
        result.update(possible=library.is_possible_number(number), valid=library.is_valid_number(number),
                      valid_for_region=library.is_valid_number_for_region(number, declared), metadata_region=library.region_code_for_number(number))
        # These observations share the producer's metadata and are explicitly
        # reported as consistency only, including its digit-preservation guard.
        metadata_e164 = library.format_number(number, library.PhoneNumberFormat.E164)
        preserved = metadata_e164[1:] if span["text"].startswith("+") else digits(library.format_number(number, library.PhoneNumberFormat.NATIONAL))
        if str(number.country_code) != CALLING_CODES[declared] or result["metadata_region"] not in (None, declared):
            result["reason"] = "region_phone_conflict"
        elif library.is_possible_number_with_reason(number) == library.ValidationResult.IS_POSSIBLE_LOCAL_ONLY:
            result["reason"] = "local_only_number_missing_area_code"
        elif not result["possible"]:
            result["reason"] = "impossible_number"
        elif digits(span["text"]) != preserved or number.extension:
            result["reason"] = "implicit_digit_repair"
        elif re.fullmatch(r"\+[1-9][0-9]{1,14}", metadata_e164) is None:
            result["reason"] = "not_e164_shape"
        else:
            independent = independent_e164(span["text"], declared)
            require(independent is not None, "accepted phone outside independently supported complete corpus formats")
            require(independent == metadata_e164, "independent raw-digit E164 disagrees with metadata formatter")
            result.update(region=declared, e164=independent)
    return result


def normalized(state, reference):
    ready = reference["region"] in REGIONS
    return {"status": "formatted" if ready else "review", "reason": None if ready else reference["reason"] or "region_decision_mismatch",
            "selected": state["selected"], "region": reference["region"] if ready else None, "e164": reference["e164"] if ready else None,
            **{key: reference[key] for key in ("format_supported", "possible", "valid", "valid_for_region")},
            "routable": "unverified", "library_version": LIBRARY_VERSION}


def expected_request(state, stage):
    if stage == "selection":
        criteria = {key: json.dumps(span, ensure_ascii=False) for key, span in state["candidates"].items()}
        criteria["none"] = "No unique complete candidate for the requested role; this does not prove absence."
        questions = {"span": choice("Select the exact complete phone span for the requested role under the visible policy.", criteria),
                     "target_present": noul("Is at least one requested-role phone slot populated, independently of candidate recall, format or region?")}
    else:
        questions = {"region": choice("Identify the supported region from the actual complete candidate's field and visible policy; missing evidence is unknown, conflict or unsupported input is review.",
                                    {"US": "Explicit United States field declaration consistent with the phone", "CA": "Explicit Canada field declaration consistent with the phone",
                                     "GB": "Explicit United Kingdom field declaration consistent with the phone", "unknown": "Missing, blank or not stated region declaration",
                                     "review": "Partial/invalid candidate, unsupported or conflicting region, impossible length or implicit digit repair"})}
    return {"state": state, "questions": questions}


def expected_split(group, seed):
    encoded = json.dumps([seed, group], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    bucket = int(hashlib.sha256(encoded).hexdigest()[:16], 16) % 10000
    return next(split for boundary, split in ((8000, "train"), (8500, "calibration"), (9000, "validation"), (10000, "test")) if bucket < boundary)


def overlap(occurrences, denominator):
    families, splits, counts = defaultdict(set), defaultdict(set), Counter()
    split_values = {split: set() for split in SPLITS}
    split_counts = Counter()
    for value, family, split in occurrences:
        families[value].add(family)
        splits[value].add(split)
        counts[value] += 1
        split_values[split].add(value)
        split_counts[split] += 1
    return {"denominator": denominator, "occurrences": len(occurrences), "unique_values": len(counts),
            "distinct_family_value_pairs": sum(len(value) for value in families.values()),
            "values_reused_across_families": sum(len(value) > 1 for value in families.values()),
            "values_reused_across_splits": sum(len(value) > 1 for value in splits.values()),
            "occurrences_of_values_reused_across_splits": sum(counts[value] for value in counts if len(splits[value]) > 1),
            "maximum_families_per_value": max((len(value) for value in families.values()), default=0),
            "occurrences_by_split": {split: split_counts[split] for split in SPLITS},
            "unique_values_by_split": {split: len(split_values[split]) for split in SPLITS},
            "split_pair_intersections": {first + "__" + second: len(split_values[first] & split_values[second]) for first, second in combinations(SPLITS, 2)}}


def verify(directory):
    import phonenumbers as library
    require(library.__version__ == LIBRARY_VERSION, "phonenumbers version differs")
    directory = Path(directory)
    names = [split + ".jsonl" for split in SPLITS] + ["families.jsonl", "cases.jsonl"]
    hashes = {name: sha256(directory / name) for name in [*names, "manifest.json"]}
    manifest = json.loads((directory / "manifest.json").read_text())
    require(manifest["schema_version"] == 1 and manifest["files_sha256"] == {name: hashes[name] for name in names}, "manifest file hashes differ")
    require(manifest["model_input_fields"] == ["state", "question", "kind", "options"], "model input fields differ")
    config = manifest["configuration"]
    require(config["generator_version"] == VERSION and type(config["seed"]) is int and config["library_version"] == LIBRARY_VERSION, "generator configuration differs")
    sources = {name: sha256(ROOT / "jev" / name) for name in ("case_phone_extraction.py", "recipes.py", "api.py", "data.py")}
    require(config["source_files_sha256"] == sources, "generator/runtime source hashes differ")
    families, cases = list(read_jsonl(directory / "families.jsonl")), list(read_jsonl(directory / "cases.jsonl"))
    records = []
    for split in SPLITS:
        found = list(read_jsonl(directory / (split + ".jsonl")))
        require(all(row.get("split") == split for row in found), "record in wrong split file")
        records.extend(found)
    summary = validate_records(records)
    require(manifest["summary"] == summary and manifest["counts"] == {split: sum(row["split"] == split for row in records) for split in SPLITS}, "manifest summary/counts differ")
    require(len(families) == config["groups"] == manifest["family_count"] and sum(family["split"] == "ood" for family in families) == config["ood_groups"], "family counts differ")
    by_family, groups = {}, set()
    for family in families:
        require(set(family) == {"id", "group_id", "split", "template_id", "case_ids", "provenance"}, "family fields differ")
        require(family["id"] not in by_family and family["group_id"] not in groups and family["split"] in SPLITS, "invalid/duplicate family")
        if family["split"] != "ood":
            require(family["split"] == expected_split(family["group_id"], config["seed"]), "family group split differs")
        provenance = family["provenance"]
        require(provenance.get("type") == "synthetic" and provenance.get("license") == "CC0-1.0" and provenance.get("generator_version") == VERSION and provenance.get("seed") == config["seed"], "family provenance differs")
        by_family[family["id"]] = family
        groups.add(family["group_id"])
    indexed, used, case_ids, documents, document_ids = {row["id"]: row for row in records}, set(), set(), set(), set()
    by_case_family = defaultdict(list)
    heads, reasons, omissions, regions, normal_statuses, recalled_ids = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    orders, candidate_count, formatted_invalid = set(), 0, 0
    raw_occurrences, canonical_occurrences, canonical_spellings = [], [], defaultdict(set)
    attribute_reasons = Counter()
    for case in cases:
        require(set(case) == {"id", "family_id", "group_id", "split", "template_id", "variant", "selection_request", "selection_reference", "attributes", "omitted_supervision"}, "case fields differ")
        require(case["id"] not in case_ids and case["family_id"] in by_family, "duplicate case/unknown family")
        family = by_family[case["family_id"]]
        require(all(case[key] == family[key] for key in ("group_id", "split", "template_id")), "family linkage differs")
        state = case["selection_request"]["state"]
        require(state["text"] not in documents, "duplicate document text")
        layout = "message" if case["split"] == "ood" else "card"
        require(state["policy"]["layout"] == layout and case["template_id"] == VERSION + ("/message-ood" if layout == "message" else "/card-id"), "OOD layout/template differs")
        title = re.fullmatch(r"Fictional contact ([0-9a-f]{20}); demonstration only; do not dial\.", state["text"].split("\n", 1)[0])
        require(title is not None and title.group(1) not in document_ids, "invalid/duplicate opaque document identity")
        parsed = fields(state["text"], state["policy"])
        raw_occurrences.extend((field["value"], family["id"], case["split"]) for field in parsed if field["value"] not in ("", "not recorded"))
        reference = selection(state)
        require(case["selection_reference"] == reference, "selection reference differs from visible text/offsets")
        expected_omissions = []

        def check_rows(stage, request, answers, candidate_id=None):
            require(request == expected_request(request["state"], stage), "runtime request differs")
            for compiled in compile_request(**request):
                head = compiled["id"]
                if len(compiled["options"]) == 1:
                    expected_omissions.append({"stage": stage, "head": head, "reason": "forced_single_candidate"})
                    continue
                row_id = f"{case['id']}:{stage}:{candidate_id or 'request'}:{head}"
                require(row_id in indexed and row_id not in used, "missing/repeated typed record")
                row = indexed[row_id]
                require(all(row[key] == case[key] for key in ("group_id", "split")) and row["source"] == VERSION, "typed record linkage differs")
                require(all(row[key] == compiled[key] for key in ("state", "question", "kind", "options")), "typed record differs from actual request")
                answer = str(answers[head]).lower() if compiled["kind"] == "noul" else answers[head]
                require(row["target"] == [float(key == answer) for key in compiled["answer_keys"]], "target differs from visible inputs and disclosed metadata checks")
                metadata = row["metadata"]
                require(all(metadata.get(key) == value for key, value in {"stage": stage, "question_id": head, "case_id": case["id"], "document_family_id": family["id"], "candidate_id": candidate_id, "variant": case["variant"], "conditional_on_actual_candidate": stage == "attributes"}.items()), "metadata linkage differs")
                require(metadata["provenance"].get("license") == "CC0-1.0", "typed record data license differs")
                used.add(row_id)
                heads[stage + "/" + head] += 1

        check_rows("selection", case["selection_request"], reference)
        require([item["candidate_id"] for item in case["attributes"]] == list(state["candidates"]), "B does not cover all actual A candidates exactly once")
        for item in case["attributes"]:
            require(set(item) == {"candidate_id", "request", "reference", "normalized_reference"}, "attribute sidecar fields differ")
            selected = item["request"]["state"]
            require(selected == {"text": state["text"], "policy": state["policy"], "selected_id": item["candidate_id"], "selected": state["candidates"][item["candidate_id"]]}, "B is not bound to actual A candidate")
            attr = inspect(selected, library)
            require(item["reference"] == attr, "attribute reference differs from independently parsed input or shared metadata consistency")
            normal = normalized(selected, attr)
            require(item["normalized_reference"] == normal, "normalized reference differs from independent E164 digits/metadata consistency")
            check_rows("attributes", item["request"], attr, item["candidate_id"])
            regions[attr["region"]] += 1
            normal_statuses[normal["status"]] += 1
            attribute_reasons[attr["reason"] or "formatted"] += 1
            formatted_invalid += normal["status"] == "formatted" and attr["valid"] is False
            if normal["status"] == "formatted":
                canonical_occurrences.append((normal["e164"], family["id"], case["split"]))
                canonical_spellings[normal["e164"]].add(selected["selected"]["text"])
            candidate_count += 1
        require(case["omitted_supervision"] == expected_omissions, "omitted supervision differs")
        omissions.update(item["reason"] for item in expected_omissions)
        reasons[reference["reason"]] += 1
        if reference["reason"] == "recalled":
            recalled_ids[reference["span"]] += 1
        orders.add(tuple(field["role"] for field in parsed))
        by_case_family[family["id"]].append(case)
        documents.add(state["text"])
        document_ids.add(title.group(1))
        case_ids.add(case["id"])
    require(used == set(indexed), "orphan typed records")
    for family in families:
        found = by_case_family[family["id"]]
        require(len(found) == 20 and {case["variant"] for case in found} == VARIANTS, "family variant coverage differs")
        require(family["case_ids"] == [case["id"] for case in found], "family case index differs")
    recalled, missed = reasons["recalled"], reasons["candidate_miss"]
    recall = {"denominator": "documents with exactly one populated requested-role field", "recalled": recalled, "missed": missed,
              "eligible": recalled + missed, "rate": recalled / (recalled + missed) if recalled + missed else None,
              "ambiguous_documents_excluded": reasons["ambiguous_target"], "absent_documents_excluded": reasons["target_absent"]}
    attr_counts = {"region": dict(regions), "normalized_status": dict(normal_statuses), "formatted_but_metadata_invalid": formatted_invalid}
    diversity = {"field_order_count": len(orders), "recalled_target_candidate_ids": dict(recalled_ids),
                 "ordering_rule": "One shuffle of complete fields using opaque document nonce; no target/label-dependent order selection."}
    aggregates = {"document_count": len(cases), "typed_record_count": len(records), "candidate_count": candidate_count,
                  "head_counts": dict(heads), "selection_reference_counts": dict(reasons), "candidate_recall": recall,
                  "attribute_reference_counts": attr_counts, "omitted_supervision_counts": dict(omissions), "observed_order_diversity": diversity}
    for key, value in aggregates.items():
        require(manifest[key] == value, "manifest aggregate differs: " + key)
    require(all(sha256(directory / name) == value for name, value in hashes.items()), "dataset changed during verification")
    return {"verified": True, "family_count": len(families), **aggregates, "attribute_reason_counts": dict(attribute_reasons),
            "number_overlap": {"raw_slot_strings": overlap(raw_occurrences, "Every recognized populated phone slot; excludes blank/not recorded and unrelated notes, includes unsupported formats and regions."),
                               "independently_formatted_e164": overlap(canonical_occurrences, "Every actual B candidate independently accepted for E.164 formatting under the visible policy; includes distractors and repeated fields, excludes review candidates."),
                               "canonical_values_with_multiple_raw_spellings": sum(len(values) > 1 for values in canonical_spellings.values()),
                               "raw_and_canonical_are_distinct_units": True, "number_level_holdout": False,
                               "unseen_number_generalization_supported": False,
                               "limitation": "The finite fictional phone pool intentionally repeats across document families and splits. Group separation is at document-family level, not number identity. Raw strings and canonical E.164 are different overlap units."},
            "schema_summary": summary, "files_sha256": hashes, "source_files_sha256": sources, "verifier_sha256": sha256(__file__),
            "producer_test_sha256": sha256(ROOT / "tests/test_phone_extraction_control.py"),
            "scope": {"producer_helpers_imported": False, "model_inference_performed": False, "external_or_official_examples_read": False,
                      "library": "phonenumbers==" + library.__version__,
                      "independent_checks": ["public field grammar", "candidate scan and source offsets", "role/presence", "actual-candidate binding", "digit assembly for this corpus's US/CA/GB complete formats", "raw and canonical split overlap"],
                      "shared_metadata_consistency_only": ["parse outcome", "country code", "metadata_region", "possible and local-only reason", "valid", "valid_for_region", "NATIONAL digit-preservation guard", "comparison against metadata E164 formatter"],
                      "independent_number_validity_established": False, "routability": "unverified",
                      "producer_tests_rerun_by_this_audit": False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="New report file outside the input data directory")
    args = parser.parse_args(argv)
    if args.output:
        require(not args.output.is_symlink(), "report output must not be a symlink")
        root, output = args.data.resolve(), args.output.resolve()
        require(output != root and root not in output.parents, "report output must be outside the input data directory")
        require(not args.output.exists(), "report output already exists")
    result = verify(args.data)
    rendered = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
