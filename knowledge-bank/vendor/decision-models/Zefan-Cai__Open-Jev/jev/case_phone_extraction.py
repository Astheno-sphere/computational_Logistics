"""Original fictional phone controls: actual-span selection, region, E.164 formatting."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random
import re

from .api import compile_request
from .data import SPLITS, _hash, _write_dataset, split_group
from .recipes import choice, noul

VERSION = "phone-extraction-control-v1"
LIBRARY_VERSION = "9.0.14"
POLICY_VERSION = "explicit-field-region-ascii-phone-v1"
SPLIT_POLICY = "complete_document_family_same_split; hash_id_splits; message_layout_and_role_labels_reserved_ood"
REGIONS = ("US", "CA", "GB")
ROLE_LABELS = {
    "card": {"Mobile": "mobile", "Billing": "billing", "Support": "support"},
    "message": {"On-call contact": "mobile", "Accounts contact": "billing", "Help desk": "support"},
}
# Scan text only, never query/labels. Filter short digit fragments after scanning.
# Outer parentheses, extensions and Unicode separators may leave partial/missed spans.
CANDIDATE_PATTERN = r"(?<![\w+])\+?[0-9](?:[0-9 ()\t.\-]*[0-9])?(?!\w)"
FORMAT_PATTERN = r"\+?[0-9]+(?:[ .\-][0-9]+)*"


def make_policy(layout="card"):
    if layout not in ROLE_LABELS:
        raise ValueError("Supported public layouts are card and message")
    return {
        "version": POLICY_VERSION, "layout": layout, "roles": copy.deepcopy(ROLE_LABELS[layout]),
        "supported_regions": list(REGIONS), "library": "phonenumbers==" + LIBRARY_VERSION,
        "scope": "Fictional contact controls, not a claim of real identity, number assignment, mobile line type or reachability. Do not dial.",
        "grammar": "Card fields: <role>: <phone> | Region: <region>. Message fields: <role> :: phone=<phone>; region=<region>. The region suffix may be omitted. Region is an explicit field-local ISO region declaration, never a document default. Unrecognized lines are not fields. not recorded or an empty phone value means absent.",
        "presence_rule": "A populated requested-role phone slot is present even if malformed or unrecalled. Multiple populated fields for that role are ambiguous, even if identical. Missing roles and not recorded slots are absent.",
        "selection_rule": "Select only a candidate exactly equal to the unique populated requested-role slot in text and both Python character offsets. Otherwise none. none does not establish absence. Scan all document text without the query or reference spans.",
        "region_rule": "For an actual complete candidate, use only its field's explicit US/CA/GB declaration. Missing, blank or not stated is unknown; comma-separated, unsupported or conflicting declarations require review. Calling codes +1 and +44 are shared: never infer a country from them. Reject disagreement with the parsed calling code or a different region identified by pinned library metadata; unresolved metadata does not override an explicit declaration. Invalid syntax, impossible length or implicit digit repair requires review. This policy does not prove physical location or ownership.",
        "format_rule": "ASCII digits only, optional leading +, single ASCII space/dot/hyphen between digit groups. No parentheses, extensions, vanity letters, Unicode digits/separators, IDD prefixes or inferred digits. International digits must equal E.164 digits after removing separators. National digits must equal the pinned library NATIONAL digits; thus unrequested trunk-prefix repair is rejected. Offsets are Unicode character positions, not UTF-8 bytes.",
        "normalization_rule": "Normalize only the actual B candidate and a matching supported region decision. Refuse unknown, conflicts, partial spans, unsupported formatting, impossible numbers and digit repair. Also refuse metadata IS_POSSIBLE_LOCAL_ONLY: a locally plausible phone missing its area code is incomplete for E.164 even when possible=true. E.164 formatting may be returned when globally possible=true and valid=false: formatting is distinct from metadata validity and both are distinct from routability. Record possible, valid and valid_for_region separately. Routability is always unverified. No calls or identity lookups occur.",
    }


def phone_candidates(text):
    if not isinstance(text, str):
        raise ValueError("Document must be text")
    spans = [match for match in re.finditer(CANDIDATE_PATTERN, text)
             if sum(char in "0123456789" for char in match.group()) >= 7]
    return {f"span_{index}": {"text": match.group(), "start": match.start(), "end": match.end()}
            for index, match in enumerate(spans)}


def document_fields(text, policy):
    if not isinstance(policy, dict) or policy != make_policy(policy.get("layout")):
        raise ValueError("Unsupported or altered phone policy")
    pattern = (r"(?P<label>[^:\n]+): (?P<value>[^\n]*?)(?: \| Region: (?P<region>[^\n]*))?" if policy["layout"] == "card" else
               r"(?P<label>[^:\n]+) :: phone=(?P<value>[^\n]*?)(?:; region=(?P<region>[^\n]*))?")
    fields = []
    for match in re.finditer(r"^" + pattern + r"$", text, re.M):
        role = policy["roles"].get(match["label"])
        if role is not None:
            fields.append({"role": role, "value": match["value"], "region": match["region"],
                           "start": match.start("value"), "end": match.end("value")})
    return fields


def phone_selection(text, requested_role, *, layout="card"):
    policy = make_policy(layout)
    if requested_role not in policy["roles"].values():
        raise ValueError("Requested role must occur in the supplied policy")
    candidates = phone_candidates(text)
    if len(candidates) > 254:
        raise ValueError("More than 254 candidates plus none; select a section explicitly")
    criteria = {key: json.dumps(span, ensure_ascii=False) for key, span in candidates.items()}
    criteria["none"] = "No unique complete candidate for the requested role; this does not prove absence."
    request = {"state": {"text": text, "requested_role": requested_role, "policy": policy, "candidates": candidates},
               "questions": {"span": choice("Select the exact complete phone span for the requested role under the visible policy.", criteria),
                             "target_present": noul("Is at least one requested-role phone slot populated, independently of candidate recall, format or region?")}}
    compile_request(**request)
    return request


def phone_attributes(selection_request, selected_id):
    """B always binds the actual selected A candidate, without query or gold."""
    state = selection_request["state"]
    candidates = phone_candidates(state["text"])
    if state["candidates"] != candidates:
        raise ValueError("Selection candidates differ from the source text")
    document_fields(state["text"], state["policy"])
    if selected_id == "none":
        return None
    if selected_id not in candidates:
        raise ValueError("Selected ID is not an actual candidate")
    request = {"state": {"text": state["text"], "policy": copy.deepcopy(state["policy"]),
                         "selected_id": selected_id, "selected": copy.deepcopy(candidates[selected_id])},
               "questions": {"region": choice("Identify the supported region from the actual complete candidate's field and visible policy; missing evidence is unknown, conflict or unsupported input is review.",
                   {"US": "Explicit United States field declaration consistent with the phone", "CA": "Explicit Canada field declaration consistent with the phone",
                    "GB": "Explicit United Kingdom field declaration consistent with the phone", "unknown": "Missing, blank or not stated region declaration",
                    "review": "Partial/invalid candidate, unsupported or conflicting region, impossible length or implicit digit repair"})}}
    compile_request(**request)
    return request


def selection_reference(request):
    state = request["state"]
    if phone_candidates(state["text"]) != state["candidates"]:
        raise ValueError("Candidate binding differs from the original text")
    targets = [{"text": item["value"], "start": item["start"], "end": item["end"]}
               for item in document_fields(state["text"], state["policy"])
               if item["role"] == state["requested_role"] and item["value"] not in ("", "not recorded")]
    selected, recalled = "none", None
    if len(targets) == 1:
        selected = next((key for key, span in state["candidates"].items() if span == targets[0]), "none")
        recalled = selected != "none"
    reason = "target_absent" if not targets else "ambiguous_target" if len(targets) > 1 else "recalled" if recalled else "candidate_miss"
    return {"span": selected, "target_present": bool(targets), "target_spans": targets,
            "candidate_recalled": recalled, "reason": reason}


def phone_library():
    try:
        import phonenumbers
    except ImportError as error:
        raise RuntimeError("Phone inspection/normalization requires the optional extra: pip install '.[phone]'") from error
    if phonenumbers.__version__ != LIBRARY_VERSION:
        raise RuntimeError("This contract requires phonenumbers==" + LIBRARY_VERSION)
    return phonenumbers


def inspect_candidate(request):
    """Read only actual source span, public field grammar and pinned metadata."""
    state = request["state"]
    if phone_candidates(state["text"]).get(state["selected_id"]) != state["selected"]:
        raise ValueError("Selected candidate differs from source text/character offsets")
    fields = document_fields(state["text"], state["policy"])
    span = state["selected"]
    field = next((item for item in fields if (item["value"], item["start"], item["end"]) == (span["text"], span["start"], span["end"])), None)
    result = {"region": "review", "reason": None, "complete_field": field is not None,
              "format_supported": bool(re.fullmatch(FORMAT_PATTERN, span["text"])),
              "declared_region": None if field is None else field["region"],
              "possible": None, "valid": None, "valid_for_region": None, "metadata_region": None,
              "e164": None, "routable": "unverified", "library_version": LIBRARY_VERSION}
    if field is None:
        result["reason"] = "partial_or_unbound_candidate"
    elif not result["format_supported"]:
        result["reason"] = "unsupported_format"
    elif field["region"] in (None, "", "not stated"):
        result.update(region="unknown", reason="region_missing")
    elif field["region"] not in REGIONS:
        result["reason"] = "unsupported_or_ambiguous_region"
    else:
        library = phone_library()
        region = field["region"]
        try:
            number = library.parse(span["text"], region)
        except library.NumberParseException:
            result["reason"] = "parse_failure"
            return result
        possible = library.is_possible_number(number)
        metadata_region = library.region_code_for_number(number)
        e164 = library.format_number(number, library.PhoneNumberFormat.E164)
        result.update(possible=possible, valid=library.is_valid_number(number),
                      valid_for_region=library.is_valid_number_for_region(number, region), metadata_region=metadata_region)
        original_digits = re.sub(r"[^0-9]", "", span["text"])
        expected_digits = e164[1:] if span["text"].startswith("+") else re.sub(r"[^0-9]", "", library.format_number(number, library.PhoneNumberFormat.NATIONAL))
        if number.country_code != library.country_code_for_region(region) or (metadata_region is not None and metadata_region != region):
            result["reason"] = "region_phone_conflict"
        elif library.is_possible_number_with_reason(number) == library.ValidationResult.IS_POSSIBLE_LOCAL_ONLY:
            result["reason"] = "local_only_number_missing_area_code"
        elif not possible:
            result["reason"] = "impossible_number"
        elif original_digits != expected_digits or number.extension:
            result["reason"] = "implicit_digit_repair"
        elif not re.fullmatch(r"\+[1-9][0-9]{1,14}", e164):
            result["reason"] = "not_e164_shape"
        else:
            result.update(region=region, e164=e164)
    return result


def normalize_phone(attributes_request, *, region):
    """Normalize actual B input; do not repair A with a reference candidate."""
    if region not in (*REGIONS, "unknown", "review"):
        raise ValueError("Supply a discrete supported region, unknown or review; no probability threshold is chosen here")
    visible = inspect_candidate(attributes_request)
    ready = region in REGIONS and region == visible["region"]
    return {"status": "formatted" if ready else "review", "reason": None if ready else visible["reason"] or "region_decision_mismatch",
            "selected": copy.deepcopy(attributes_request["state"]["selected"]),
            "region": region if ready else None, "e164": visible["e164"] if ready else None,
            "format_supported": visible["format_supported"], "possible": visible["possible"],
            "valid": visible["valid"], "valid_for_region": visible["valid_for_region"],
            "routable": "unverified", "library_version": LIBRARY_VERSION}


def fictional_number(region, nonce, *, national=False):
    """Reserved example styles only; never claim assignment or reachability."""
    if region == "GB":
        tail = f"{nonce % 1000:03d}"
        return ("07700 900" if national else "+44 7700 900") + tail
    area = {"US": "202", "CA": "416"}[region]
    return ("" if national else "+1 ") + area + "-555-" + f"{100 + nonce % 100:04d}"


def family_documents(group, index, ood):
    layout = "message" if ood else "card"
    labels = {role: label for label, role in ROLE_LABELS[layout].items()}
    region = REGIONS[index % len(REGIONS)]
    nonce = int(_hash([group, "phone"])[0:8], 16)
    variants = ("international", "national", "other_role", "missing_role", "unrecorded", "no_candidates",
                "unknown_region", "missing_region_suffix", "region_conflict", "ambiguous_region", "unsupported_region",
                "duplicate_target", "repeated_value", "extension_partial", "unicode_space_miss", "parenthesized_partial",
                "impossible_length", "international_digit_repair", "malformed_format", "unrelated_note")
    for variant in variants:
        fields = [[role, fictional_number(r, nonce + ordinal * 17), r]
                  for ordinal, (role, r) in enumerate(zip(("mobile", "billing", "support"), (region, REGIONS[(index+1)%3], REGIONS[(index+2)%3])))]
        role = "mobile"
        if variant == "national":
            fields[0][1] = fictional_number(region, nonce, national=True)
        elif variant == "other_role":
            role = "billing" if index % 2 else "support"
        elif variant == "missing_role":
            fields.pop(0)
        elif variant == "unrecorded":
            fields[0][1] = "not recorded"
        elif variant == "no_candidates":
            fields = [[r, "not recorded", None] for r, _, _ in fields]
        elif variant == "unknown_region":
            fields[0][2] = "not stated"
        elif variant == "missing_region_suffix":
            fields[0][2] = None
        elif variant == "region_conflict":
            fields[0][2] = REGIONS[(index+1)%3]
        elif variant == "ambiguous_region":
            fields[0][2] = "US,CA"
        elif variant == "unsupported_region":
            fields[0][2] = "FR"
        elif variant == "duplicate_target":
            fields.append(["mobile", fictional_number(region, nonce+1), region])
        elif variant == "repeated_value":
            fields[1][1:3] = fields[0][1:3]
        elif variant == "extension_partial":
            fields[0][1] += " ext. 42"
        elif variant == "unicode_space_miss":
            fields[0][1] = fictional_number("GB", nonce).replace(" ", "\u202f")
            fields[0][2] = "GB"
        elif variant == "parenthesized_partial":
            fields[0][1] = "(" + fields[0][1] + ")"
        elif variant == "impossible_length":
            fields[0][1] = fictional_number("US", nonce)[:-2]
            fields[0][2] = "US"
        elif variant == "international_digit_repair":
            fields[0][1] = fictional_number("GB", nonce).replace("+44 ", "+44 0")
            fields[0][2] = "GB"
        elif variant == "malformed_format":
            fields[0][1] = fields[0][1].replace(" ", "--", 1)
        document_id = _hash([group, variant, "document"])[0:20]
        random.Random(int(_hash([group, document_id, "field-order"]), 16)).shuffle(fields)
        lines = ["Fictional contact " + document_id + "; demonstration only; do not dial.", "Memo: café / 联系卡; all contacts are invented."]
        if variant == "unrelated_note":
            lines.append("Archived note: " + fictional_number("US", nonce+2))
        for field_role, value, declaration in fields:
            line = f"{labels[field_role]}: {value}" if layout == "card" else f"{labels[field_role]} :: phone={value}"
            if declaration is not None:
                line += f" | Region: {declaration}" if layout == "card" else f"; region={declaration}"
            lines.append(line)
        yield variant, "\n".join(lines), role, layout


def generate(groups=200, seed=42, ood_groups=40):
    if type(groups) is not int or groups < 2 or type(seed) is not int or type(ood_groups) is not int or not 0 <= ood_groups < groups:
        raise ValueError("Use integer groups >=2, seed and 0 <= ood_groups < groups")
    phone_library()
    families, cases, rows = [], [], []
    for index in range(groups):
        ood = index >= groups-ood_groups
        group = f"{VERSION}:{seed}:{'ood' if ood else 'id'}:{index}"
        family_id = "document-family-" + _hash(group)[:20]
        split = "ood" if ood else split_group(group, seed)
        template = f"{VERSION}/{'message-ood' if ood else 'card-id'}"
        provenance = {"type": "synthetic", "generator_version": VERSION, "seed": seed, "group_index": index,
                      "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
                      "source_relation": "original_fictional_contacts; no_external_examples_benchmarks_or_model_outputs"}
        case_ids = []
        for variant_index, (variant, text, role, layout) in enumerate(family_documents(group, index, ood)):
            case_id = "phone-case-" + _hash([group, variant])[:24]
            request = phone_selection(text, role, layout=layout)
            ref = selection_reference(request)
            case = {"id": case_id, "family_id": family_id, "group_id": group, "split": split, "template_id": template,
                    "variant": variant, "selection_request": request, "selection_reference": ref, "attributes": [], "omitted_supervision": []}
            def add_rows(stage, stage_request, targets, candidate_id=None):
                for compiled in compile_request(**stage_request):
                    head = compiled["id"]
                    if len(compiled["options"]) < 2:
                        case["omitted_supervision"].append({"stage": stage, "head": head, "reason": "forced_single_candidate"})
                        continue
                    target_key = str(targets[head]).lower() if compiled["kind"] == "noul" else targets[head]
                    target = [float(key == target_key) for key in compiled["answer_keys"]]
                    metadata = {"family": "evidence", "template_id": template, "case_name": "phone_extraction", "stage": stage,
                                "question_id": head, "case_id": case_id, "document_family_id": family_id,
                                "entity_ids": [family_id], "candidate_id": candidate_id, "variant": variant,
                                "conditional_on_actual_candidate": stage == "attributes",
                                "target_basis": "Visible source field and public policy, with pinned phone metadata; not model output or confidence.",
                                "provenance": {**provenance, "variant": variant_index}}
                    rows.append({"id": f"{case_id}:{stage}:{candidate_id or 'request'}:{head}", "group_id": group,
                                 "split": split, "source": VERSION, "state": compiled["state"], "question": compiled["question"],
                                 "kind": compiled["kind"], "options": compiled["options"], "target": target, "metadata": metadata})
            add_rows("selection", request, ref)
            for candidate_id in request["state"]["candidates"]:
                attributes = phone_attributes(request, candidate_id)
                attribute_ref = inspect_candidate(attributes)
                case["attributes"].append({"candidate_id": candidate_id, "request": attributes, "reference": attribute_ref,
                                           "normalized_reference": normalize_phone(attributes, region=attribute_ref["region"])})
                add_rows("attributes", attributes, attribute_ref, candidate_id)
            cases.append(case)
            case_ids.append(case_id)
        families.append({"id": family_id, "group_id": group, "split": split, "template_id": template,
                         "case_ids": case_ids, "provenance": {**provenance, "variant": 0}})
    return families, cases, rows


def build_dataset(output_dir, groups=200, seed=42, ood_groups=40):
    output = Path(output_dir)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Choose a new empty phone-extraction output; existing corpora are never overwritten")
    families, cases, rows = generate(groups, seed, ood_groups)
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION, "groups": groups,
        "ood_groups": ood_groups, "seed": seed, "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
        "library_version": LIBRARY_VERSION, "candidate_extractor": {"pattern": CANDIDATE_PATTERN, "minimum_ascii_digits": 7,
            "reads_query_or_gold": False, "offset_unit": "Python Unicode characters", "known_limits": "Extensions, outer parentheses and Unicode separators may produce partial/missed candidates, retained without repair."},
        "source_files_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in ("case_phone_extraction.py", "recipes.py", "api.py", "data.py")}})
    for name, values in (("families.jsonl", families), ("cases.jsonl", cases)):
        path = output/name
        path.write_text("".join(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+"\n" for value in values))
        manifest["files_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    reasons = Counter(case["selection_reference"]["reason"] for case in cases)
    attributes = [item for case in cases for item in case["attributes"]]
    recalled, missed = reasons["recalled"], reasons["candidate_miss"]
    orders = {tuple(field["role"] for field in document_fields(case["selection_request"]["state"]["text"], case["selection_request"]["state"]["policy"])) for case in cases}
    manifest.update(family_count=len(families), document_count=len(cases), typed_record_count=len(rows), candidate_count=len(attributes),
        head_counts=dict(Counter(row["metadata"]["stage"]+"/"+row["metadata"]["question_id"] for row in rows)),
        selection_reference_counts=dict(reasons), candidate_recall={"denominator": "documents with exactly one populated requested-role field",
            "recalled": recalled, "missed": missed, "eligible": recalled+missed, "rate": recalled/(recalled+missed) if recalled+missed else None,
            "ambiguous_documents_excluded": reasons["ambiguous_target"], "absent_documents_excluded": reasons["target_absent"]},
        attribute_reference_counts={"region": dict(Counter(item["reference"]["region"] for item in attributes)),
            "normalized_status": dict(Counter(item["normalized_reference"]["status"] for item in attributes)),
            "formatted_but_metadata_invalid": sum(item["normalized_reference"]["status"] == "formatted" and item["reference"]["valid"] is False for item in attributes)},
        omitted_supervision_counts=dict(Counter(item["reason"] for case in cases for item in case["omitted_supervision"])),
        observed_order_diversity={"field_order_count": len(orders), "recalled_target_candidate_ids": dict(Counter(case["selection_reference"]["span"] for case in cases if case["selection_reference"]["reason"] == "recalled")),
            "ordering_rule": "One shuffle of complete fields using opaque document nonce; no target/label-dependent order selection."},
        counts={split: sum(row["split"] == split for row in rows) for split in SPLITS},
        training_performed=False, model_inference_performed=False, frozen_training_datasets_modified=False,
        conditional_attributes_note="B covers all actual candidates including distractors and partials; reference-candidate results are not end-to-end model metrics.")
    (output/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--groups", type=int, default=200)
    parser.add_argument("--ood-groups", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed, args.ood_groups), indent=2))


if __name__ == "__main__":
    main()
