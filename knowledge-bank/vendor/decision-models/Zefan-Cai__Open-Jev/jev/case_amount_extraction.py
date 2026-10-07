"""Original two-stage invoice amount controls; candidates never read references."""
import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import re

from .api import compile_request
from .data import SPLITS, _hash, _write_dataset, split_group
from .recipes import choice, noul

VERSION = "amount-extraction-control-v1"
POLICY_VERSION = "visible-invoice-amount-v1"
SPLIT_POLICY = "all_document_and_role_counterfactuals_in_original_family; hash_id_splits; reserved_ledger_layout_and_role_wording_ood"
MARKER = r"(?:USD|EUR|GBP|CAD|\$|€|£|¤)"
NUMBER_CANDIDATE = r"[+-]?[0-9]+(?:[.,][0-9]+)*"
# This intentionally misses narrow-NBSP grouping and surrounding parentheses.
# It can return partial spans. Fullness is checked against the public line grammar.
CANDIDATE_PATTERN = rf"(?<![\w.,])(?:{MARKER}[ \t]?{NUMBER_CANDIDATE}|{NUMBER_CANDIDATE}[ \t]?{MARKER})(?![\w.,])"
ROLE_LABELS = {
    "invoice": {"Subtotal": "subtotal", "Tax": "tax", "Amount due": "due", "Credit balance": "credit", "Shipping estimate": "shipping"},
    "ledger": {"Goods before levy": "subtotal", "Levy": "tax", "Payable now": "due", "Rebate balance": "credit", "Freight estimate": "shipping"},
}
FLOW_LABELS = {
    "invoice": {"charge": "charge", "credit": "credit", "not stated": None},
    "ledger": {"debit": "charge", "rebate": "credit", "unreported": None},
}


def make_policy(locale, layout):
    if locale not in ("US", "EU") or layout not in ROLE_LABELS:
        raise ValueError("Declare locale US or EU and layout invoice or ledger; guessing is not supported")
    return {
        "version": POLICY_VERSION, "locale": locale, "layout": layout,
        "scope": "Controlled invoice fields, not arbitrary document understanding or an authorization to transact.",
        "grammar": "Headers are Number format: <US|EU> and Currency declaration: <USD|EUR|GBP|not stated>. Invoice lines are <role>: <value> | Flow: <flow>. Ledger lines are <role> :: flow=<flow>; value=<value>. A value is the complete text in that slot; not recorded means no value. Unrecognized lines do not supply fields.",
        "roles": copy.deepcopy(ROLE_LABELS[layout]), "flows": copy.deepcopy(FLOW_LABELS[layout]),
        "presence_rule": "target_present means at least one requested-role field is populated, even if its amount format is unsupported. It is independent of candidate recall. Missing roles and not recorded slots are absent. Multiple populated requested-role fields are ambiguous, even if their values are equal.",
        "selection_rule": "Select a candidate only when exactly one requested-role field is populated and a candidate equals its complete value text and both character offsets. Otherwise select none. none never proves target absence. Candidates come from the complete document without access to the query or reference spans.",
        "number_rule": "Use ASCII digits only, with exactly two fractional digits. US uses decimal dot and optional comma groups of three. EU uses decimal comma and optional dot OR narrow no-break-space groups of three, never mixed. Ungrouped integers have no leading zeros except zero. A numeric sign may be + or - immediately before the number. Parentheses around the complete monetary expression imply a negative sign; combining parentheses and a numeric sign is invalid. Values include one visible currency marker, before or after the number. No exponent, rounding, inferred locale or generated digits.",
        "currency_rule": "USD, EUR and GBP identify those currencies; € means EUR and £ means GBP under this declared policy only. $ and ¤ require the supported Currency declaration header. CAD is unsupported and yields review. An explicit supported ISO marker overrides the document declaration. Partial or invalid amounts yield review.",
        "direction_rule": "Use only the flow attached to the complete selected field, through the visible flows table. An absent or unknown flow is unknown, even with a numeric sign. An explicit negative sign or parentheses requires credit; explicit plus requires charge. A sign/flow conflict is unknown and requires review. Unsigned magnitudes can be either credit or charge. direction_known is yes only for a valid complete amount and an established, sign-consistent flow. is_credit is defined only when direction_known is yes; otherwise ignore it and provide no supervised is_credit target.",
        "normalization_rule": "Copy the actual selected candidate. Reject identifiable partial spans using its source offsets and public field grammar, even if a predicted head says known. Parse exact Decimal magnitude. Unknown currency or direction, inconsistent attributes, malformed values or sign conflicts require review. Apply credit negativity exactly once with Decimal.copy_abs/copy_negate; never use context-rounding arithmetic.",
    }


def amount_candidates(text):
    if not isinstance(text, str):
        raise ValueError("Document must be text")
    return {f"span_{index}": {"text": match.group(), "start": match.start(), "end": match.end()}
            for index, match in enumerate(re.finditer(CANDIDATE_PATTERN, text))}


def document_fields(text, policy):
    """Read only the declared public document grammar and exact source offsets."""
    if not isinstance(policy, dict) or policy != make_policy(policy.get("locale"), policy.get("layout")):
        raise ValueError("Unsupported or altered amount policy")
    locale, layout = policy["locale"], policy["layout"]
    formats = re.findall(r"^Number format: (.*)$", text, re.M)
    declarations = re.findall(r"^Currency declaration: (.*)$", text, re.M)
    if formats != [locale] or len(declarations) != 1 or declarations[0] not in ("USD", "EUR", "GBP", "not stated"):
        raise ValueError("Missing, ambiguous or inconsistent locale/currency declaration")
    pattern = (r"(?P<label>[^:\n]+): (?P<value>[^\n]*?) \| Flow: (?P<flow>[^\n]+)" if layout == "invoice" else
               r"(?P<label>[^:\n]+) :: flow=(?P<flow>[^;\n]+); value=(?P<value>[^\n]*)")
    fields = []
    for match in re.finditer(r"^" + pattern + r"$", text, re.M):
        role = policy["roles"].get(match["label"])
        if role is not None:
            fields.append({"role": role, "flow": match["flow"], "value": match["value"],
                           "start": match.start("value"), "end": match.end("value")})
    return fields, declarations[0]


def parse_money(text, locale):
    """Exact magnitude, explicit sign and marker, or None for unsupported input."""
    if locale not in ("US", "EU") or not isinstance(text, str):
        return None
    parenthesized = text.startswith("(") and text.endswith(")")
    inner = text[1:-1] if parenthesized else text
    prefix = re.fullmatch(rf"(?P<marker>{MARKER})[ \t]?(?P<number>[+-]?[0-9][0-9.,\u202f]*)", inner)
    suffix = re.fullmatch(rf"(?P<number>[+-]?[0-9][0-9.,\u202f]*)[ \t]?(?P<marker>{MARKER})", inner)
    match = prefix or suffix
    if match is None:
        return None
    raw = match["number"]
    sign = raw[0] if raw[0] in "+-" else None
    if parenthesized and sign is not None:
        return None
    unsigned = raw[1:] if sign else raw
    plain = r"(?:0|[1-9][0-9]*)"
    grouped = r"[1-9][0-9]{0,2}(?:,[0-9]{3})+" if locale == "US" else r"(?:[1-9][0-9]{0,2}(?:\.[0-9]{3})+|[1-9][0-9]{0,2}(?:\u202f[0-9]{3})+)"
    decimal_mark = r"\." if locale == "US" else ","
    if not re.fullmatch(rf"(?:{plain}|{grouped}){decimal_mark}[0-9]{{2}}", unsigned):
        return None
    cleaned = unsigned.replace(",", "") if locale == "US" else unsigned.replace(".", "").replace("\u202f", "").replace(",", ".")
    magnitude = Decimal(cleaned)
    return {"magnitude": magnitude, "sign": "-" if parenthesized else sign, "marker": match["marker"]}


def amount_selection(text, requested_role, *, locale, layout="invoice"):
    policy = make_policy(locale, layout)
    if requested_role not in policy["roles"].values():
        raise ValueError("Requested role must be declared in the visible policy")
    document_fields(text, policy)
    candidates = amount_candidates(text)
    if len(candidates) > 254:
        raise ValueError("More than 254 candidates plus none; explicitly select a section first")
    criteria = {key: json.dumps(span, ensure_ascii=False) for key, span in candidates.items()}
    criteria["none"] = "No unique complete candidate answers the requested role; this does not establish absence."
    request = {"state": {"text": text, "requested_role": requested_role, "policy": policy, "candidates": candidates},
               "questions": {"span": choice("Select the complete verbatim amount span for the requested role under the visible policy.", criteria),
                             "target_present": noul("Does at least one requested-role field contain a populated value, independently of whether the regex recalled it? Apply the visible presence rule.")}}
    compile_request(**request)
    return request


def amount_attributes(selection_request, selected_id):
    """Build B for an actual A candidate, never a supplied reference span."""
    state = selection_request["state"]
    candidates = amount_candidates(state["text"])
    if candidates != state["candidates"]:
        raise ValueError("Selection candidates do not match the original text")
    if selected_id == "none":
        return None
    if selected_id not in candidates:
        raise ValueError("Selected ID is not an actual candidate")
    request = {"state": {"text": state["text"], "policy": copy.deepcopy(state["policy"]),
                         "selected_id": selected_id, "selected": copy.deepcopy(candidates[selected_id])},
               "questions": {
                   "currency": choice("For the actual selected complete amount, identify a supported currency; otherwise review.",
                                      {"USD": "US dollars under the supplied policy", "EUR": "Euros under the supplied policy", "GBP": "Pounds sterling under the supplied policy", "review": "Currency unsupported, unknown, or selected amount partial/invalid"}),
                   "direction_known": noul("Is the actual selected amount complete and valid, with an explicit attached flow consistent with any sign? Apply the visible direction rule."),
                   "is_credit": noul("Conditional on direction_known being yes, is the attached flow credit? This head is undefined and must be ignored when direction_known is no."),
               }}
    compile_request(**request)
    return request


def selection_reference(request):
    state = request["state"]
    fields, _ = document_fields(state["text"], state["policy"])
    targets = [{"text": field["value"], "start": field["start"], "end": field["end"]}
               for field in fields if field["role"] == state["requested_role"] and field["value"] not in ("", "not recorded")]
    selected, recalled = "none", None
    if len(targets) == 1:
        selected = next((key for key, span in state["candidates"].items() if span == targets[0]), "none")
        recalled = selected != "none"
    reason = "target_absent" if not targets else "ambiguous_target" if len(targets) > 1 else "recalled" if recalled else "candidate_miss"
    return {"span": selected, "target_present": bool(targets), "target_spans": targets,
            "candidate_recalled": recalled, "reason": reason}


def inspect_candidate(request):
    """Inspect the actual candidate and its source field; no target/query is read."""
    state = request["state"]
    candidates = amount_candidates(state["text"])
    if candidates.get(state["selected_id"]) != state["selected"]:
        raise ValueError("Selected candidate binding differs from original text")
    fields, declaration = document_fields(state["text"], state["policy"])
    selected = state["selected"]
    field = next((item for item in fields if item["start"] == selected["start"] and item["end"] == selected["end"] and item["value"] == selected["text"]), None)
    parsed = parse_money(selected["text"], state["policy"]["locale"]) if field is not None else None
    currency, flow, sign = "review", None, None
    if parsed is not None:
        marker, sign = parsed["marker"], parsed["sign"]
        currency = {"USD": "USD", "EUR": "EUR", "GBP": "GBP", "€": "EUR", "£": "GBP"}.get(marker, "review")
        if marker in ("$", "¤") and declaration in ("USD", "EUR", "GBP"):
            currency = declaration
        flow = state["policy"]["flows"].get(field["flow"])
        if (sign == "-" and flow != "credit") or (sign == "+" and flow != "charge"):
            flow = None
    known = flow is not None
    return {"currency": currency, "direction_known": known, "is_credit": None if not known else flow == "credit",
            "complete_field": field is not None, "valid_amount": parsed is not None,
            "magnitude_decimal": None if parsed is None else format(parsed["magnitude"], "f"),
            "explicit_sign": sign}


def normalize_amount(attributes_request, *, currency, direction_known, is_credit=None):
    """Normalize actual B input; no query, reference offset, family or gold is read."""
    if currency not in ("USD", "EUR", "GBP", "review") or type(direction_known) is not bool or (is_credit is not None and type(is_credit) is not bool):
        raise ValueError("Supply discrete currency/direction decisions; thresholds are not selected here")
    # These checks use the actual source and public grammar, not corpus annotations.
    visible = inspect_candidate(attributes_request)
    selected = copy.deepcopy(attributes_request["state"]["selected"])
    reason = None
    if not visible["complete_field"]:
        reason = "partial_or_unbound_candidate"
    elif not visible["valid_amount"]:
        reason = "invalid_amount_format"
    elif currency == "review" or visible["currency"] == "review" or currency != visible["currency"]:
        reason = "currency_requires_review"
    elif not direction_known or not visible["direction_known"] or is_credit is None or is_credit != visible["is_credit"]:
        reason = "direction_requires_review"
    if reason:
        return {"status": "review", "reason": reason, "selected": selected, "currency": None, "amount": None}
    value = Decimal(visible["magnitude_decimal"]).copy_abs()
    if is_credit and not value.is_zero():
        value = value.copy_negate()
    return {"status": "ready", "reason": None, "selected": selected, "currency": currency, "amount": format(value, "f")}


def format_amount(cents, locale, marker, *, suffix=False, grouping="standard", sign=None, parentheses=False):
    whole, fraction = divmod(cents, 100)
    integer = f"{whole:,}"
    if locale == "EU":
        integer = integer.replace(",", "\u202f" if grouping == "space" else ".")
    number = (sign or "") + integer + ("." if locale == "US" else ",") + f"{fraction:02d}"
    result = number + " " + marker if suffix else marker + " " + number
    return "(" + result + ")" if parentheses else result


def render_document(invoice_id, locale, layout, declaration, fields):
    labels = {role: label for label, role in ROLE_LABELS[layout].items()}
    flows = {flow: label for label, flow in FLOW_LABELS[layout].items()}
    lines = [f"Invoice {invoice_id}" if layout == "invoice" else f"Settlement ledger {invoice_id}",
             f"Number format: {locale}", f"Currency declaration: {declaration}"]
    for role, value, flow in fields:
        lines.append(f"{labels[role]}: {value} | Flow: {flows[flow]}" if layout == "invoice" else
                     f"{labels[role]} :: flow={flows[flow]}; value={value}")
    return "\n".join(lines)


def family_documents(group, index, ood):
    code = _hash([group, "invoice"])[:12]
    cents = 125001 + int(_hash([group, "amount"])[0:6], 16) % 800000
    base_locale = "US" if index % 2 == 0 else "EU"
    layout = "ledger" if ood else "invoice"
    variants = ("due_charge", "due_credit", "other_role", "due_absent", "due_unrecorded", "eu_space_miss",
                "unknown_currency", "unknown_direction", "negative_credit", "negative_charge_conflict",
                "positive_credit_conflict", "parentheses_credit", "ambiguous_due", "repeated_value", "no_candidates", "long_exact_decimal")
    for variant in variants:
        locale = "EU" if variant == "eu_space_miss" else base_locale
        marker = "EUR" if variant == "eu_space_miss" else ("USD", "EUR", "GBP")[index % 3]
        declaration = marker
        def amount(value, **kwargs):
            return format_amount(value, locale, marker, suffix=ood, **kwargs)
        fields = [["subtotal", amount(cents-700), "charge"], ["tax", amount(700), "charge"],
                  ["due", amount(cents), "charge"], ["credit", amount(2222), "credit"],
                  ["shipping", amount(1300), "charge"]]
        role = "due"
        if variant == "due_credit":
            fields[2][1] = format_amount(cents, locale, {"USD": "$", "EUR": "€", "GBP": "£"}[marker], suffix=ood)
            fields[2][2] = "credit"
        elif variant == "other_role":
            role = ("subtotal", "tax", "credit")[index % 3]
        elif variant == "due_absent":
            fields.pop(2)
        elif variant == "due_unrecorded":
            fields[2][1] = "not recorded"
        elif variant == "eu_space_miss":
            fields[2][1] = amount(cents, grouping="space")
        elif variant == "unknown_currency":
            declaration = "not stated"
            fields[2][1] = format_amount(cents, locale, "¤" if index % 2 else "CAD", suffix=ood)
        elif variant == "unknown_direction":
            fields[2][2] = None
        elif variant in ("negative_credit", "negative_charge_conflict", "positive_credit_conflict"):
            fields[2][1] = amount(cents, sign="+" if variant == "positive_credit_conflict" else "-")
            fields[2][2] = "charge" if variant == "negative_charge_conflict" else "credit"
        elif variant == "parentheses_credit":
            fields[2][1] = amount(cents, parentheses=True)
            fields[2][2] = "credit"
        elif variant == "ambiguous_due":
            fields.append(["due", amount(cents+100), "charge"])
        elif variant == "repeated_value":
            fields[0][1] = fields[2][1]
        elif variant == "no_candidates":
            fields = [[item[0], "not recorded", None] for item in fields]
        elif variant == "long_exact_decimal":
            fields[2][1] = amount(12345678901234567890123456789012+index)
            fields[2][2] = "credit"
        invoice_id = f"{code}-{_hash([group, variant])[:8]}"
        random.Random(int(_hash([group, invoice_id, "field-order"]), 16)).shuffle(fields)
        yield variant, render_document(invoice_id, locale, layout, declaration, fields), role, locale, layout


def generate(groups=200, seed=42, ood_groups=40):
    if type(groups) is not int or groups < 2 or type(seed) is not int or type(ood_groups) is not int or not 0 <= ood_groups < groups:
        raise ValueError("Use integer groups >=2, seed, and 0 <= ood_groups < groups")
    families, cases, rows = [], [], []
    for index in range(groups):
        ood = index >= groups-ood_groups
        group = f"{VERSION}:{seed}:{'ood' if ood else 'id'}:{index}"
        family_id = "document-family-"+_hash(group)[:20]
        split = "ood" if ood else split_group(group, seed)
        template = f"{VERSION}/{'ledger-suffix-ood' if ood else 'invoice-prefix-id'}"
        provenance = {"type": "synthetic", "generator_version": VERSION, "seed": seed, "group_index": index,
                      "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
                      "source_relation": "original_invoice_documents; no_external_examples_or_model_outputs"}
        case_ids = []
        for variant_index, (variant, text, role, locale, layout) in enumerate(family_documents(group, index, ood)):
            case_id = f"{family_id}:document:{variant_index}"
            request = amount_selection(text, role, locale=locale, layout=layout)
            ref = selection_reference(request)
            case = {"id": case_id, "family_id": family_id, "group_id": group, "split": split, "template_id": template,
                    "variant": variant, "selection_request": request, "selection_reference": ref, "attributes": [],
                    "omitted_supervision": []}
            def add_rows(stage, stage_request, targets, candidate_id=None):
                for compiled in compile_request(**stage_request):
                    head = compiled["id"]
                    omission = "forced_single_candidate" if len(compiled["options"]) < 2 else "undefined_direction" if targets[head] is None else None
                    if omission:
                        case["omitted_supervision"].append({"stage": stage, "candidate_id": candidate_id, "head": head, "reason": omission})
                        continue
                    keys = compiled["answer_keys"]
                    target_key = str(targets[head]).lower() if compiled["kind"] == "noul" else targets[head]
                    target = [float(key == target_key) for key in keys]
                    metadata = {"family": "evidence", "template_id": template, "case_name": "amount_extraction", "stage": stage,
                                "question_id": head, "case_id": case_id, "document_family_id": family_id,
                                "entity_ids": [family_id], "candidate_id": candidate_id, "variant": variant,
                                "conditional_on_actual_candidate": stage == "attributes",
                                "target_basis": "Visible document and policy reference; not a model prediction or confidence.",
                                "provenance": {**provenance, "variant": variant_index}}
                    rows.append({"id": f"{case_id}:{stage}:{candidate_id or 'request'}:{head}", "group_id": group,
                                 "split": split, "source": VERSION, "state": compiled["state"], "question": compiled["question"],
                                 "kind": compiled["kind"], "options": compiled["options"], "target": target, "metadata": metadata})
            add_rows("selection", request, {key: ref[key] for key in ("span", "target_present")})
            for candidate_id in request["state"]["candidates"]:
                attributes = amount_attributes(request, candidate_id)
                attribute_ref = inspect_candidate(attributes)
                normalized = normalize_amount(attributes, **{key: attribute_ref[key] for key in ("currency", "direction_known", "is_credit")})
                case["attributes"].append({"candidate_id": candidate_id, "request": attributes, "reference": attribute_ref,
                                           "normalized_reference": normalized})
                add_rows("attributes", attributes, attribute_ref, candidate_id)
            cases.append(case)
            case_ids.append(case_id)
        families.append({"id": family_id, "group_id": group, "split": split, "template_id": template,
                         "case_ids": case_ids, "provenance": {**provenance, "variant": 0}})
    return families, cases, rows


def build_dataset(output_dir, groups=200, seed=42, ood_groups=40):
    output = Path(output_dir)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Choose a new empty amount-extraction directory; existing corpora are never overwritten")
    families, cases, rows = generate(groups, seed, ood_groups)
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION, "groups": groups,
        "ood_groups": ood_groups, "seed": seed, "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
        "candidate_extractor": {"name": "jev.case_amount_extraction.amount_candidates", "pattern": CANDIDATE_PATTERN,
                                "reads_query_or_gold": False, "known_limits": "Narrow-NBSP grouping and outer parentheses can yield partial candidates; exact recall is measured without replacement."},
        "source_files_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                for name in ("case_amount_extraction.py", "recipes.py", "api.py", "data.py")}})
    for name, values in (("families.jsonl", families), ("cases.jsonl", cases)):
        path = output/name
        path.write_text("".join(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)+"\n" for value in values))
        manifest["files_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    reasons = Counter(case["selection_reference"]["reason"] for case in cases)
    recalled, missed = reasons["recalled"], reasons["candidate_miss"]
    attributes = [item for case in cases for item in case["attributes"]]
    omissions = Counter(item["reason"] for case in cases for item in case["omitted_supervision"])
    field_orders = Counter(tuple(field["role"] for field in document_fields(case["selection_request"]["state"]["text"],
                                                                          case["selection_request"]["state"]["policy"])[0]) for case in cases)
    manifest.update(family_count=len(families), document_count=len(cases), typed_record_count=len(rows),
        candidate_count=len(attributes), head_counts=dict(Counter(row["metadata"]["stage"]+"/"+row["metadata"]["question_id"] for row in rows)),
        selection_reference_counts=dict(reasons),
        candidate_recall={"denominator": "documents with exactly one populated requested-role field", "recalled": recalled,
                          "missed": missed, "eligible": recalled+missed, "fraction": f"{recalled}/{recalled+missed}",
                          "rate": recalled/(recalled+missed) if recalled+missed else None,
                          "ambiguous_documents_excluded": reasons["ambiguous_target"], "absent_documents_excluded": reasons["target_absent"]},
        attribute_reference_counts={"currency": dict(Counter(item["reference"]["currency"] for item in attributes)),
                                    "direction_known": dict(Counter(str(item["reference"]["direction_known"]).lower() for item in attributes)),
                                    "normalized_status": dict(Counter(item["normalized_reference"]["status"] for item in attributes))},
        omitted_supervision_counts=dict(omissions),
        observed_order_diversity={"field_order_count": len(field_orders),
                                  "recalled_target_candidate_ids": dict(Counter(case["selection_reference"]["span"] for case in cases if case["selection_reference"]["reason"] == "recalled")),
                                  "ordering_rule": "Shuffle complete field lines once using family and opaque document nonce; no query, gold target or label-based permutation selection."},
        counts={split: sum(row["split"] == split for row in rows) for split in SPLITS},
        training_performed=False, model_inference_performed=False, frozen_training_datasets_modified=False,
        conditional_attributes_note="All actual candidates receive B requests, including distractors/partials; only defined is_credit heads receive targets. These are conditional reference tasks, not end-to-end model results.")
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
