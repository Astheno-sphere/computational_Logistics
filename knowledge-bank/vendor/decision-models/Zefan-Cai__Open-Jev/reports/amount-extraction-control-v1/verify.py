"""CPU audit of original two-stage amount controls from final text and offsets.

The generator is never imported. Candidate scanning, field parsing, exact cents,
references and normalization are independently reconstructed from visible input.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
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

VERSION = "amount-extraction-control-v1"
ROLES = {
    "invoice": {"Subtotal": "subtotal", "Tax": "tax", "Amount due": "due", "Credit balance": "credit", "Shipping estimate": "shipping"},
    "ledger": {"Goods before levy": "subtotal", "Levy": "tax", "Payable now": "due", "Rebate balance": "credit", "Freight estimate": "shipping"},
}
FLOWS = {"invoice": {"charge": "charge", "credit": "credit", "not stated": None},
         "ledger": {"debit": "charge", "rebate": "credit", "unreported": None}}
POLICY = {
    "version": "visible-invoice-amount-v1",
    "scope": "Controlled invoice fields, not arbitrary document understanding or an authorization to transact.",
    "grammar": "Headers are Number format: <US|EU> and Currency declaration: <USD|EUR|GBP|not stated>. Invoice lines are <role>: <value> | Flow: <flow>. Ledger lines are <role> :: flow=<flow>; value=<value>. A value is the complete text in that slot; not recorded means no value. Unrecognized lines do not supply fields.",
    "presence_rule": "target_present means at least one requested-role field is populated, even if its amount format is unsupported. It is independent of candidate recall. Missing roles and not recorded slots are absent. Multiple populated requested-role fields are ambiguous, even if their values are equal.",
    "selection_rule": "Select a candidate only when exactly one requested-role field is populated and a candidate equals its complete value text and both character offsets. Otherwise select none. none never proves target absence. Candidates come from the complete document without access to the query or reference spans.",
    "number_rule": "Use ASCII digits only, with exactly two fractional digits. US uses decimal dot and optional comma groups of three. EU uses decimal comma and optional dot OR narrow no-break-space groups of three, never mixed. Ungrouped integers have no leading zeros except zero. A numeric sign may be + or - immediately before the number. Parentheses around the complete monetary expression imply a negative sign; combining parentheses and a numeric sign is invalid. Values include one visible currency marker, before or after the number. No exponent, rounding, inferred locale or generated digits.",
    "currency_rule": "USD, EUR and GBP identify those currencies; € means EUR and £ means GBP under this declared policy only. $ and ¤ require the supported Currency declaration header. CAD is unsupported and yields review. An explicit supported ISO marker overrides the document declaration. Partial or invalid amounts yield review.",
    "direction_rule": "Use only the flow attached to the complete selected field, through the visible flows table. An absent or unknown flow is unknown, even with a numeric sign. An explicit negative sign or parentheses requires credit; explicit plus requires charge. A sign/flow conflict is unknown and requires review. Unsigned magnitudes can be either credit or charge. direction_known is yes only for a valid complete amount and an established, sign-consistent flow. is_credit is defined only when direction_known is yes; otherwise ignore it and provide no supervised is_credit target.",
    "normalization_rule": "Copy the actual selected candidate. Reject identifiable partial spans using its source offsets and public field grammar, even if a predicted head says known. Parse exact Decimal magnitude. Unknown currency or direction, inconsistent attributes, malformed values or sign conflicts require review. Apply credit negativity exactly once with Decimal.copy_abs/copy_negate; never use context-rounding arithmetic.",
}
VARIANTS = {"due_charge", "due_credit", "other_role", "due_absent", "due_unrecorded", "eu_space_miss",
            "unknown_currency", "unknown_direction", "negative_credit", "negative_charge_conflict",
            "positive_credit_conflict", "parentheses_credit", "ambiguous_due", "repeated_value", "no_candidates", "long_exact_decimal"}
MARKERS = ("USD", "EUR", "GBP", "CAD", "$", "€", "£", "¤")
# Boundaries and nonoverlap are checked separately rather than reusing the producer regex.
TOKEN = re.compile(r"(?:USD|EUR|GBP|CAD|[$€£¤])[ \t]?[+-]?[0-9]+(?:[.,][0-9]+)*|[+-]?[0-9]+(?:[.,][0-9]+)*[ \t]?(?:USD|EUR|GBP|CAD|[$€£¤])")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidates(text):
    require(isinstance(text, str), "document must be text")
    found, position = {}, 0
    blocked = lambda char: char.isalnum() or char in "_.,"
    while position < len(text):
        matched = TOKEN.match(text, position) if position == 0 or not blocked(text[position - 1]) else None
        if matched and (matched.end() == len(text) or not blocked(text[matched.end()])):
            found[f"span_{len(found)}"] = {"text": matched.group(), "start": position, "end": matched.end()}
            position = matched.end()
        else:
            position += 1
    return found


def policy_check(policy):
    require(isinstance(policy, dict) and set(policy) == set(POLICY) | {"locale", "layout", "roles", "flows"}, "policy fields differ")
    require(all(policy[key] == value for key, value in POLICY.items()), "unsupported policy text")
    require(policy["locale"] in ("US", "EU") and policy["layout"] in ROLES, "locale/layout must be explicit")
    require(policy["roles"] == ROLES[policy["layout"]] and policy["flows"] == FLOWS[policy["layout"]], "visible role/flow table differs")


def fields(text, policy):
    policy_check(policy)
    lines = text.split("\n")
    formats = [line[len("Number format: "):] for line in lines if line.startswith("Number format: ")]
    declarations = [line[len("Currency declaration: "):] for line in lines if line.startswith("Currency declaration: ")]
    require(formats == [policy["locale"]] and len(declarations) == 1 and declarations[0] in ("USD", "EUR", "GBP", "not stated"),
            "missing, duplicate or inconsistent declarations")
    result, offset = [], 0
    for line in lines:
        for label, role in policy["roles"].items():
            if policy["layout"] == "invoice":
                prefix = label + ": "
                if not line.startswith(prefix):
                    continue
                value, separator, flow = line[len(prefix):].partition(" | Flow: ")
                start = offset + len(prefix)
                if not separator or not flow:
                    continue
            else:
                prefix = label + " :: flow="
                if not line.startswith(prefix):
                    continue
                flow, separator, value = line[len(prefix):].partition("; value=")
                if not separator or not flow or ";" in flow:
                    continue
                start = offset + len(prefix) + len(flow) + len(separator)
            result.append({"role": role, "flow": flow, "value": value, "start": start, "end": start + len(value)})
        offset += len(line) + 1
    return result, declarations[0]


def money(text, locale):
    """Parse the public monetary grammar to exact integer cents, without rounding."""
    if locale not in ("US", "EU") or not isinstance(text, str):
        return None
    parentheses = text.startswith("(") and text.endswith(")")
    core = text[1:-1] if parentheses else text
    marker, number = None, None
    for token in MARKERS:
        if core.startswith(token):
            marker, number = token, core[len(token):]
            number = number[1:] if number[:1] in (" ", "\t") else number
            break
        if core.endswith(token):
            marker, number = token, core[:-len(token)]
            number = number[:-1] if number[-1:] in (" ", "\t") else number
            break
    if marker is None or not number:
        return None
    sign = number[0] if number[0] in "+-" else None
    if parentheses and sign:
        return None
    number = number[1:] if sign else number
    decimal_mark = "." if locale == "US" else ","
    parts = number.rsplit(decimal_mark, 1)
    ascii_digits = lambda value: bool(value) and all("0" <= char <= "9" for char in value)
    if len(parts) != 2 or len(parts[1]) != 2 or not ascii_digits(parts[1]):
        return None
    integer, fraction = parts
    separators = [char for char in (",",) if char in integer] if locale == "US" else [char for char in (".", "\u202f") if char in integer]
    if len(separators) > 1:
        return None
    groups = integer.split(separators[0]) if separators else [integer]
    if not all(ascii_digits(group) for group in groups):
        return None
    if separators:
        if not 1 <= len(groups[0]) <= 3 or groups[0][0] == "0" or any(len(group) != 3 for group in groups[1:]):
            return None
    elif len(integer) > 1 and integer[0] == "0":
        return None
    cents = int("".join(groups)) * 100 + int(fraction)
    return {"cents": cents, "marker": marker, "sign": "-" if parentheses else sign,
            "magnitude_decimal": str(cents // 100) + "." + str(cents % 100).zfill(2)}


def selection(state):
    require(set(state) == {"text", "requested_role", "policy", "candidates"}, "selection state fields differ")
    slots, _ = fields(state["text"], state["policy"])
    require(state["requested_role"] in state["policy"]["roles"].values(), "requested role is undeclared")
    actual = candidates(state["text"])
    require(len(actual) <= 254 and actual == state["candidates"], "candidate extraction differs")
    targets = [{"text": slot["value"], "start": slot["start"], "end": slot["end"]} for slot in slots
               if slot["role"] == state["requested_role"] and slot["value"] not in ("", "not recorded")]
    selected, recalled = "none", None
    if len(targets) == 1:
        matches = [key for key, value in actual.items() if value == targets[0]]
        selected = matches[0] if matches else "none"
        recalled = bool(matches)
    reason = ("target_absent" if not targets else "ambiguous_target" if len(targets) > 1
              else "recalled" if recalled else "candidate_miss")
    return {"span": selected, "target_present": bool(targets), "target_spans": targets,
            "candidate_recalled": recalled, "reason": reason}


def attributes(state):
    require(set(state) == {"text", "policy", "selected_id", "selected"}, "attribute state fields differ")
    require(candidates(state["text"]).get(state["selected_id"]) == state["selected"], "selected candidate binding differs")
    slots, declaration = fields(state["text"], state["policy"])
    span = state["selected"]
    full = [slot for slot in slots if (slot["start"], slot["end"], slot["value"]) == (span["start"], span["end"], span["text"])]
    parsed = money(span["text"], state["policy"]["locale"]) if full else None
    currency, direction, sign = "review", None, None
    if parsed:
        marker, sign = parsed["marker"], parsed["sign"]
        currency = {"USD": "USD", "EUR": "EUR", "GBP": "GBP", "€": "EUR", "£": "GBP"}.get(marker, "review")
        if marker in ("$", "¤") and declaration in ("USD", "EUR", "GBP"):
            currency = declaration
        direction = state["policy"]["flows"].get(full[0]["flow"])
        if sign in ("+", "-") and direction != {"+": "charge", "-": "credit"}[sign]:
            direction = None
    return {"currency": currency, "direction_known": direction is not None,
            "is_credit": None if direction is None else direction == "credit", "complete_field": bool(full),
            "valid_amount": parsed is not None, "magnitude_decimal": parsed["magnitude_decimal"] if parsed else None,
            "explicit_sign": sign}


def normalized(state, currency, direction_known, is_credit=None):
    visible = attributes(state)
    reason = ("partial_or_unbound_candidate" if not visible["complete_field"] else
              "invalid_amount_format" if not visible["valid_amount"] else
              "currency_requires_review" if currency == "review" or visible["currency"] == "review" or currency != visible["currency"] else
              "direction_requires_review" if not direction_known or not visible["direction_known"] or is_credit is None or is_credit != visible["is_credit"] else None)
    if reason:
        return {"status": "review", "reason": reason, "selected": state["selected"], "currency": None, "amount": None}
    value = visible["magnitude_decimal"]
    nonzero = any(char in "123456789" for char in value)
    return {"status": "ready", "reason": None, "selected": state["selected"], "currency": currency,
            "amount": ("-" if is_credit and nonzero else "") + value}


def expected_request(state, stage):
    if stage == "selection":
        criteria = {key: json.dumps(span, ensure_ascii=False) for key, span in state["candidates"].items()}
        criteria["none"] = "No unique complete candidate answers the requested role; this does not establish absence."
        questions = {"span": choice("Select the complete verbatim amount span for the requested role under the visible policy.", criteria),
                     "target_present": noul("Does at least one requested-role field contain a populated value, independently of whether the regex recalled it? Apply the visible presence rule.")}
    else:
        questions = {"currency": choice("For the actual selected complete amount, identify a supported currency; otherwise review.",
                                        {"USD": "US dollars under the supplied policy", "EUR": "Euros under the supplied policy", "GBP": "Pounds sterling under the supplied policy", "review": "Currency unsupported, unknown, or selected amount partial/invalid"}),
                     "direction_known": noul("Is the actual selected amount complete and valid, with an explicit attached flow consistent with any sign? Apply the visible direction rule."),
                     "is_credit": noul("Conditional on direction_known being yes, is the attached flow credit? This head is undefined and must be ignored when direction_known is no.")}
    return {"state": state, "questions": questions}


def expected_split(group, seed):
    encoded = json.dumps([seed, group], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    bucket = int(hashlib.sha256(encoded).hexdigest()[:16], 16) % 10000
    return next(split for boundary, split in ((8000, "train"), (8500, "calibration"), (9000, "validation"), (10000, "test")) if bucket < boundary)


def verify(directory):
    directory = Path(directory)
    names = [split + ".jsonl" for split in SPLITS] + ["families.jsonl", "cases.jsonl"]
    hashes = {name: sha256(directory / name) for name in [*names, "manifest.json"]}
    manifest = json.loads((directory / "manifest.json").read_text())
    require(manifest["schema_version"] == 1 and manifest["files_sha256"] == {name: hashes[name] for name in names}, "manifest file hashes differ")
    require(manifest["model_input_fields"] == ["state", "question", "kind", "options"], "model input fields differ")
    config = manifest["configuration"]
    require(config["generator_version"] == VERSION and type(config["seed"]) is int, "generator configuration differs")
    source_hashes = {name: sha256(ROOT / "jev" / name) for name in ("case_amount_extraction.py", "recipes.py", "api.py", "data.py")}
    require(config["source_files_sha256"] == source_hashes, "generator/runtime source hashes differ")
    families, cases = list(read_jsonl(directory / "families.jsonl")), list(read_jsonl(directory / "cases.jsonl"))
    records = []
    for split in SPLITS:
        found = list(read_jsonl(directory / (split + ".jsonl")))
        require(all(row.get("split") == split for row in found), "record in wrong split file")
        records.extend(found)
    summary = validate_records(records)
    require(manifest["summary"] == summary, "manifest schema summary differs")
    require(manifest["counts"] == {split: sum(row["split"] == split for row in records) for split in SPLITS}, "manifest split counts differ")
    require(len(families) == config["groups"] == manifest["family_count"], "family count differs")
    require(sum(family["split"] == "ood" for family in families) == config["ood_groups"], "OOD family count differs")
    by_family, groups = {}, set()
    for family in families:
        require(set(family) == {"id", "group_id", "split", "template_id", "case_ids", "provenance"}, "family fields differ")
        require(family["id"] not in by_family and family["group_id"] not in groups, "duplicate family/group")
        require(family["split"] in SPLITS, "unknown family split")
        if family["split"] != "ood":
            require(family["split"] == expected_split(family["group_id"], config["seed"]), "family group split differs")
        provenance = family["provenance"]
        require(provenance.get("type") == "synthetic" and provenance.get("license") == "CC0-1.0" and provenance.get("generator_version") == VERSION and provenance.get("seed") == config["seed"], "family provenance differs")
        by_family[family["id"]] = family
        groups.add(family["group_id"])
    row_index = {row["id"]: row for row in records}
    used, case_ids, seen_text = set(), set(), set()
    family_cases, invoice_owner = defaultdict(list), {}
    head_counts, reasons, omissions = Counter(), Counter(), Counter()
    currency_counts, known_counts, normalization_counts = Counter(), Counter(), Counter()
    field_orders, recalled_ids = Counter(), Counter()
    attribute_total = 0
    for case in cases:
        require(set(case) == {"id", "family_id", "group_id", "split", "template_id", "variant", "selection_request", "selection_reference", "attributes", "omitted_supervision"}, "case fields differ")
        require(case["id"] not in case_ids and case["family_id"] in by_family, "duplicate case/unknown family")
        family = by_family[case["family_id"]]
        require(all(case[key] == family[key] for key in ("group_id", "split", "template_id")), "family linkage differs")
        state = case["selection_request"]["state"]
        require(state["text"] not in seen_text, "duplicate document text")
        layout = "ledger" if case["split"] == "ood" else "invoice"
        require(state["policy"]["layout"] == layout, "OOD layout leaked")
        require(case["template_id"] == VERSION + ("/ledger-suffix-ood" if layout == "ledger" else "/invoice-prefix-id"), "template identity differs")
        title = re.fullmatch(r"(?:Invoice|Settlement ledger) ([0-9a-f]{12})-([0-9a-f]{8})", state["text"].split("\n", 1)[0])
        require(title is not None, "invalid original document identity")
        code = title.group(1)
        require(code not in invoice_owner or invoice_owner[code] == family["id"], "invoice identity crosses family groups")
        invoice_owner[code] = family["id"]
        expected_selection = selection(state)
        require(case["selection_reference"] == expected_selection, "selection reference differs from visible text/offsets")
        reasons[expected_selection["reason"]] += 1
        visible_fields, _ = fields(state["text"], state["policy"])
        field_orders[tuple(field["role"] for field in visible_fields)] += 1
        if expected_selection["reason"] == "recalled":
            recalled_ids[expected_selection["span"]] += 1
        expected_omissions = []

        def check_rows(stage, request, reference, candidate_id=None):
            require(request == expected_request(request["state"], stage), "runtime request differs")
            for compiled in compile_request(**request):
                head = compiled["id"]
                omission = "forced_single_candidate" if len(compiled["options"]) == 1 else "undefined_direction" if reference[head] is None else None
                if omission:
                    expected_omissions.append({"stage": stage, "candidate_id": candidate_id, "head": head, "reason": omission})
                    continue
                row_id = f"{case['id']}:{stage}:{candidate_id or 'request'}:{head}"
                require(row_id in row_index and row_id not in used, "missing/repeated typed record")
                row = row_index[row_id]
                require(all(row[key] == case[key] for key in ("group_id", "split")) and row["source"] == VERSION, "typed record linkage differs")
                require(all(row[key] == compiled[key] for key in ("state", "question", "kind", "options")), "typed record differs from actual request")
                target_key = str(reference[head]).lower() if compiled["kind"] == "noul" else reference[head]
                require(row["target"] == [float(key == target_key) for key in compiled["answer_keys"]], "target differs from visible inputs")
                metadata = row["metadata"]
                require(all(metadata.get(key) == value for key, value in {"stage": stage, "question_id": head, "case_id": case["id"], "document_family_id": family["id"], "candidate_id": candidate_id, "variant": case["variant"], "conditional_on_actual_candidate": stage == "attributes"}.items()), "metadata linkage differs")
                require(metadata["provenance"].get("license") == "CC0-1.0", "typed record data license differs")
                head_counts[stage + "/" + head] += 1
                used.add(row_id)

        check_rows("selection", case["selection_request"], expected_selection)
        require([item["candidate_id"] for item in case["attributes"]] == list(state["candidates"]), "B does not cover all actual A candidates exactly once")
        for item in case["attributes"]:
            require(set(item) == {"candidate_id", "request", "reference", "normalized_reference"}, "attribute sidecar fields differ")
            selected = item["request"]["state"]
            require(selected == {"text": state["text"], "policy": state["policy"], "selected_id": item["candidate_id"], "selected": state["candidates"][item["candidate_id"]]}, "B is not bound to actual A candidate")
            reference = attributes(selected)
            require(item["reference"] == reference, "attribute reference differs from visible inputs")
            normal = normalized(selected, **{key: reference[key] for key in ("currency", "direction_known", "is_credit")})
            require(item["normalized_reference"] == normal, "normalization differs from exact visible amount")
            check_rows("attributes", item["request"], reference, item["candidate_id"])
            currency_counts[reference["currency"]] += 1
            known_counts[str(reference["direction_known"]).lower()] += 1
            normalization_counts[normal["status"]] += 1
            attribute_total += 1
        require(case["omitted_supervision"] == expected_omissions, "omitted supervision differs; undefined heads must have no target")
        omissions.update(item["reason"] for item in expected_omissions)
        family_cases[family["id"]].append(case)
        case_ids.add(case["id"])
        seen_text.add(state["text"])
    require(used == set(row_index), "orphan typed record or supervised undefined head")
    for family in families:
        found = family_cases[family["id"]]
        require(len(found) == 16 and {case["variant"] for case in found} == VARIANTS, "family variant coverage differs")
        require(family["case_ids"] == [case["id"] for case in found], "family case index differs")
    recalled, missed = reasons["recalled"], reasons["candidate_miss"]
    recall = {"denominator": "documents with exactly one populated requested-role field", "recalled": recalled, "missed": missed,
              "eligible": recalled + missed, "fraction": f"{recalled}/{recalled + missed}", "rate": recalled / (recalled + missed) if recalled + missed else None,
              "ambiguous_documents_excluded": reasons["ambiguous_target"], "absent_documents_excluded": reasons["target_absent"]}
    attr_counts = {"currency": dict(currency_counts), "direction_known": dict(known_counts), "normalized_status": dict(normalization_counts)}
    order_diversity = {"field_order_count": len(field_orders), "recalled_target_candidate_ids": dict(recalled_ids),
                       "ordering_rule": "Shuffle complete field lines once using family and opaque document nonce; no query, gold target or label-based permutation selection."}
    for key, value in {"document_count": len(cases), "typed_record_count": len(records), "candidate_count": attribute_total,
                       "head_counts": dict(head_counts), "selection_reference_counts": dict(reasons), "candidate_recall": recall,
                       "attribute_reference_counts": attr_counts, "omitted_supervision_counts": dict(omissions),
                       "observed_order_diversity": order_diversity}.items():
        require(manifest[key] == value, "manifest aggregate differs: " + key)
    require(all(sha256(directory / name) == value for name, value in hashes.items()), "dataset changed during verification")
    return {"verified": True, "families": len(families), "documents": len(cases), "typed_records": len(records),
            "candidate_count": attribute_total, "candidate_recall": recall, "head_counts": dict(head_counts),
            "selection_reference_counts": dict(reasons), "attribute_reference_counts": attr_counts, "omitted_supervision_counts": dict(omissions),
            "observed_order_diversity": order_diversity,
            "schema_summary": summary, "files_sha256": hashes, "source_files_sha256": source_hashes,
            "verifier_sha256": sha256(__file__), "test_file_sha256": sha256(ROOT / "tests/test_amount_extraction_control.py"),
            "scope": {"generator_oracle_used": False, "hidden_spec_used_as_oracle": False, "model_inference_performed": False,
                      "external_or_official_examples_read": False, "normalization_arithmetic": "exact integer cents",
                      "candidate_recall_is_model_selection_accuracy": False, "attributes_conditioned_on": "every actual regex candidate"}}


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
    report = verify(args.data)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
