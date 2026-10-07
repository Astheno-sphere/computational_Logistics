"""Independently audit original entity controls from final visible inputs on CPU.

No generator oracle is imported. Decimal text is converted to integer ratios;
family specifications and stored reference/evidence fields are never an oracle.
"""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
from fractions import Fraction
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
from jev.recipes import entity_alignment, noul


VERSION = "entity-alignment-control-v1"
FIELDS = ("name", "manufacturer", "capacity")
HEADS = ("match", "name_agrees", "manufacturer_agrees", "capacity_agrees")
RULES = {
    "catalog": [
        "If both identifiers have the same nonempty namespace and different nonempty values, choose different (Score 0).",
        "Otherwise, if any field has a known conflict, choose review (Score 1) when the identifiers agree; choose different (Score 0) when they do not establish agreement.",
        "Otherwise, choose same (Score 2) if the identifiers agree or all three fields establish agreement.",
        "Otherwise choose review (Score 1). Missing or unknown fields alone are not conflicts; agreeing identifiers therefore permit same despite missing fields.",
    ],
    "procurement": [
        "First reject linking with Score 0 (different) when two populated identifier values differ within one identical populated namespace.",
        "Next handle any established attribute conflict: matching identifiers require Score 1 (review); without matching identifiers the result is Score 0 (different).",
        "In the absence of conflicts, assign Score 2 (same) when identifiers match, or when name, manufacturer and capacity are all established equal.",
        "All remaining evidence patterns receive Score 1 (review). An absent or unknown attribute is not a contradiction, so matching identifiers can yield same with incomplete attributes.",
    ],
}
POLICY_TEXT = {
    "version": "visible-catalog-alignment-v1",
    "scope": "This is the complete decision policy for these supplied catalog records, not a universal identity guarantee.",
    "identifier_rule": "Identifiers are {namespace,value}. Both must be nonempty strings. Trim outer whitespace but preserve case and internal text. Equal namespaces permit comparison: equal values agree, different values conflict. Missing components or different namespaces give unknown identifier evidence.",
    "text_rule": "For name and manufacturer, collapse whitespace and casefold. Each canonical table key and its listed aliases identify that canonical value. Two recognized equal canonicals agree; two recognized different canonicals conflict. Missing or unlisted text gives unknown evidence, even if two unlisted strings happen to match. No other spelling or punctuation equivalence is assumed.",
    "capacity_rule": "Capacity is {value,unit}. value must be a positive ordinary ASCII decimal string (no sign, exponent or fraction); unit must match the visible table exactly. Multiply the exact rational decimal value by unit_to_mL. Equal known mL values agree; unequal known values conflict. Missing, invalid or unlisted-unit capacity gives unknown evidence. capacity_evidence contains only these exact converted values; no model judgment or rounding is involved.",
    "noul_rule": "Each field Noul asks whether visible evidence establishes agreement. Yes only for agreement; no for conflict OR unknown. No is not a probability of physical inequality.",
    "score_routes": {"0": "different", "1": "review", "2": "same"},
}
VARIANTS = {"same_identifier_alias_units", "no_identifier_all_fields_agree", "conflicting_identifiers_equal_fields",
            "same_identifier_capacity_conflict", "name_conflict", "manufacturer_conflict", "capacity_conflict",
            "name_missing", "manufacturer_missing", "capacity_missing", "same_identifier_name_missing",
            "different_namespaces_equal_fields", "name_unlisted", "all_fields_missing"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(value):
    return " ".join(value.split()).casefold() if isinstance(value, str) else None


def visible_aliases(table):
    require(isinstance(table, dict) and table, "alias table must be a nonempty object")
    recognized = {}
    for canonical, alternatives in table.items():
        require(isinstance(canonical, str) and canonical.strip() and isinstance(alternatives, list), "invalid alias entry")
        for spelling in [canonical, *alternatives]:
            require(isinstance(spelling, str) and spelling.strip(), "alias must be nonempty text")
            spelling, identity = normalize(spelling), normalize(canonical)
            require(spelling not in recognized or recognized[spelling] == identity, "ambiguous alias")
            recognized[spelling] = identity
    return recognized


def decimal_ratio(value):
    if not isinstance(value, str) or re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value) is None:
        return None
    numerator, denominator = Decimal(value).as_integer_ratio()
    return Fraction(numerator, denominator) if numerator > 0 else None


def exact_capacity(item, units):
    if not isinstance(item, dict) or set(item) != {"value", "unit"}:
        return None
    if not isinstance(item["unit"], str) or item["unit"] not in units:
        return None
    value = decimal_ratio(item["value"])
    return None if value is None else value * decimal_ratio(units[item["unit"]])


def identifier(record):
    value = record.get("identifier")
    if not isinstance(value, dict):
        return None
    parts = [value.get(name) for name in ("namespace", "value")]
    return tuple(part.strip() for part in parts) if all(isinstance(part, str) and part.strip() for part in parts) else None


def validate_policy(policy):
    require(isinstance(policy, dict) and set(policy) == set(POLICY_TEXT) |
            {"wording", "rules_in_order", "aliases", "unit_to_mL"}, "policy fields differ")
    require(all(policy[key] == value for key, value in POLICY_TEXT.items()), "unsupported policy text")
    require(policy["wording"] in RULES and policy["rules_in_order"] == RULES[policy["wording"]], "unsupported ordered rules")
    require(isinstance(policy["aliases"], dict) and set(policy["aliases"]) == {"name", "manufacturer"}, "alias fields differ")
    indexes = {field: visible_aliases(policy["aliases"][field]) for field in ("name", "manufacturer")}
    require(isinstance(policy["unit_to_mL"], dict) and policy["unit_to_mL"], "unit table must be a nonempty object")
    require(all(isinstance(unit, str) and unit and decimal_ratio(value) is not None
                for unit, value in policy["unit_to_mL"].items()), "unit factors must be positive decimal strings")
    return indexes


def derive(state):
    """Compute four targets from the visible policy and records only."""
    require(isinstance(state, dict) and set(state) == {"left", "right", "policy", "capacity_evidence"}, "state fields differ")
    policy, left, right = state["policy"], state["left"], state["right"]
    indexes = validate_policy(policy)
    require(all(isinstance(record, dict) and set(record) <= {"identifier", *FIELDS} for record in (left, right)),
            "unexpected catalog record fields")
    converted = [exact_capacity(record.get("capacity"), policy["unit_to_mL"]) for record in (left, right)]
    expected_capacity = {side: None if value is None else {"unit": "mL", "exact_value": str(value)}
                         for side, value in zip(("left", "right"), converted)}
    require(state["capacity_evidence"] == expected_capacity, "capacity_evidence differs from exact visible conversion")
    evidence = {}
    for field in FIELDS:
        values = converted if field == "capacity" else [indexes[field].get(normalize(record.get(field))) for record in (left, right)]
        evidence[field] = "unknown" if None in values else "agreement" if values[0] == values[1] else "conflict"
    a, b = identifier(left), identifier(right)
    id_status = "unknown" if a is None or b is None or a[0] != b[0] else "agreement" if a[1] == b[1] else "conflict"
    conflicts = sum(value == "conflict" for value in evidence.values())
    agreements = sum(value == "agreement" for value in evidence.values())
    # A decision table expressed independently of the generator's reference branches.
    if id_status == "conflict":
        score = 0
    elif conflicts:
        score = {"agreement": 1, "unknown": 0}[id_status]
    else:
        score = 2 if id_status == "agreement" or agreements == 3 else 1
    return {"match": score, **{field + "_agrees": evidence[field] == "agreement" for field in FIELDS}}, evidence, id_status


def expected_request(state):
    style = state["policy"]["wording"]
    request = entity_alignment(state["left"], state["right"])
    request["state"] = state
    request["questions"]["match"]["instructions"] = (
        "Apply the complete supplied catalog policy in order to select different, review or same. Do not infer hidden identities."
        if style == "catalog" else
        "Follow the visible procurement protocol and select the stated identity route. Evidence unavailable in these records cannot be invented.")
    for field in FIELDS:
        request["questions"][field + "_agrees"] = noul(
            f"Does the visible evidence establish agreement of {field} under the supplied policy? Answer yes only for established agreement; conflict or unknown evidence means no."
            if style == "catalog" else
            f"Is equality of {field} established by these entries and the disclosed rules? Return yes for established equality, and no for either a known difference or insufficient field evidence.")
    return request


def expected_split(group, seed):
    encoded = json.dumps([seed, group], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    bucket = int(hashlib.sha256(encoded).hexdigest()[:16], 16) % 10000
    return next(split for boundary, split in ((8000, "train"), (8500, "calibration"), (9000, "validation"), (10000, "test"))
                if bucket < boundary)


def verify(directory):
    directory = Path(directory)
    names = [split + ".jsonl" for split in SPLITS] + ["families.jsonl", "cases.jsonl"]
    hashes = {name: sha256(directory / name) for name in [*names, "manifest.json"]}
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == 1, "unsupported manifest schema")
    require(manifest["files_sha256"] == {name: hashes[name] for name in names}, "manifest file hashes differ")
    require(manifest["sha256"] == {split: hashes[split + ".jsonl"] for split in SPLITS}, "manifest split hashes differ")
    require(manifest["model_input_fields"] == ["state", "question", "kind", "options"], "model input fields differ")
    config = manifest["configuration"]
    require(config["generator_version"] == VERSION and type(config["seed"]) is int, "generator configuration differs")
    sources = {name: sha256(ROOT / "jev" / name) for name in ("case_entity_alignment.py", "recipes.py", "api.py", "data.py")}
    require(config["source_files_sha256"] == sources, "generator/runtime source hashes differ")
    families = list(read_jsonl(directory / "families.jsonl"))
    cases = list(read_jsonl(directory / "cases.jsonl"))
    records = []
    for split in SPLITS:
        found = list(read_jsonl(directory / (split + ".jsonl")))
        require(all(row.get("split") == split for row in found), "record in wrong split file")
        records.extend(found)
    summary = validate_records(records)
    require(manifest["summary"] == summary, "manifest schema summary differs")
    require(manifest["counts"] == {split: sum(row["split"] == split for row in records) for split in SPLITS}, "manifest counts differ")
    require(len(families) == config["groups"] == manifest["family_count"], "family count differs")
    require(sum(family["split"] == "ood" for family in families) == config["ood_groups"], "OOD family count differs")
    owners, family_by_id, groups = {}, {}, set()

    def own(key, family_id):
        require(key not in owners or owners[key] == family_id, "alias, visible text or identifier shared across families")
        owners[key] = family_id

    for family in families:
        require(set(family) == {"id", "group_id", "split", "template_id", "spec", "policy", "case_ids", "provenance"}, "family fields differ")
        require(all(isinstance(family[key], str) and family[key] for key in ("id", "group_id", "template_id")), "invalid family identity")
        require(family["id"] not in family_by_id and family["group_id"] not in groups, "duplicate family/group")
        require(family["split"] in SPLITS, "unknown family split")
        indexes = validate_policy(family["policy"])
        style = "procurement" if family["split"] == "ood" else "catalog"
        require(family["policy"]["wording"] == style, "OOD policy wording leaked")
        require(family["template_id"] == VERSION + ("/procurement-ood" if style == "procurement" else "/catalog-id"), "template identity differs")
        if family["split"] != "ood":
            require(family["split"] == expected_split(family["group_id"], config["seed"]), "family group split differs")
        provenance = family["provenance"]
        require(provenance.get("type") == "synthetic" and provenance.get("license") == "CC0-1.0" and
                provenance.get("generator_version") == VERSION and provenance.get("seed") == config["seed"], "family provenance differs")
        for field, index in indexes.items():
            for spelling in index:
                own((field, spelling), family["id"])
        family_by_id[family["id"]] = family
        groups.add(family["group_id"])
    rows = {row["id"]: row for row in records}
    used, case_ids = set(), set()
    family_cases = defaultdict(list)
    heads, routes = Counter(), Counter()
    field_counts = {field: Counter() for field in FIELDS}
    for case in cases:
        prefix = f"case {case.get('id')}: "
        require(set(case) == {"id", "family_id", "group_id", "split", "template_id", "variant", "request", "reference", "field_evidence", "identifier_evidence"}, prefix + "case fields differ")
        require(isinstance(case["id"], str) and case["id"] and case["id"] not in case_ids, prefix + "invalid/duplicate case ID")
        require(case["family_id"] in family_by_id, prefix + "unknown family")
        family = family_by_id[case["family_id"]]
        require(all(case[key] == family[key] for key in ("group_id", "split", "template_id")), prefix + "family linkage differs")
        require(case["variant"] in VARIANTS, prefix + "unknown variant")
        state = case["request"]["state"]
        require(state["policy"] == family["policy"], prefix + "visible family policy differs")
        answers, evidence, id_status = derive(state)
        require(set(case["reference"]) == set(HEADS) and type(case["reference"]["match"]) is int and
                all(type(case["reference"][head]) is bool for head in HEADS[1:]), prefix + "reference types differ")
        require(case["reference"] == answers, prefix + "reference differs from visible inputs")
        require(case["field_evidence"] == evidence and case["identifier_evidence"] == id_status, prefix + "stored evidence differs")
        require(case["request"] == expected_request(state) and list(case["request"]["questions"]) == list(HEADS), prefix + "four-head request changed")
        for side in ("left", "right"):
            record = state[side]
            identity = identifier(record)
            if identity is not None:
                own(("identifier", *identity), family["id"])
            for field in ("name", "manufacturer"):
                text = normalize(record.get(field))
                if text:
                    own((field, text), family["id"])
        for compiled in compile_request(**case["request"]):
            head = compiled["id"]
            row_id = case["id"] + ":" + head
            require(row_id in rows and row_id not in used, prefix + "missing/repeated typed record")
            row = rows[row_id]
            require(all(row[key] == case[key] for key in ("group_id", "split")) and row["source"] == VERSION, prefix + "typed record linkage differs")
            require(all(row[key] == compiled[key] for key in ("state", "question", "kind", "options")), prefix + "typed record differs from request")
            target = [float(index == answers[head]) for index in range(3 if head == "match" else 2)]
            require(row["target"] == target, prefix + "target differs from visible inputs")
            metadata = row["metadata"]
            require(metadata.get("question_id") == head and metadata.get("case_id") == case["id"] and
                    metadata.get("catalog_family_id") == family["id"] and metadata.get("variant") == case["variant"], prefix + "record metadata linkage differs")
            require(metadata["provenance"].get("license") == "CC0-1.0", prefix + "typed record data license differs")
            used.add(row_id)
            heads[head] += 1
        for field, status in evidence.items():
            field_counts[field][status] += 1
        routes[str(answers["match"])] += 1
        family_cases[family["id"]].append(case)
        case_ids.add(case["id"])
    require(used == set(rows), "orphan typed records")
    for family in families:
        found = family_cases[family["id"]]
        require(len(found) == 14 and {case["variant"] for case in found} == VARIANTS, "family variant coverage differs")
        require(family["case_ids"] == [case["id"] for case in found], "family case index differs")
    require(manifest["case_count"] == len(cases) and manifest["typed_record_count"] == len(records), "manifest case/record counts differ")
    require(manifest["head_counts"] == dict(heads) and manifest["route_counts"] == dict(routes), "manifest head/route counts differ")
    require(manifest["field_evidence_counts"] == field_counts, "manifest field evidence counts differ")
    require(all(sha256(directory / name) == digest for name, digest in hashes.items()), "dataset changed during verification")
    return {"verified": True, "generator_version": VERSION, "families": len(families), "cases": len(cases),
            "typed_records": len(records), "head_counts": dict(heads), "route_counts": dict(routes),
            "field_evidence_counts": field_counts, "schema_summary": summary,
            "files_sha256": hashes, "source_files_sha256": sources, "verifier_sha256": sha256(__file__),
            "test_file_sha256": sha256(ROOT / "tests/test_entity_alignment_control.py"),
            "scope": {"generator_oracle_used": False, "family_spec_used_as_oracle": False,
                      "stored_case_evidence_used_as_oracle": False, "model_or_tokenizer_loaded": False,
                      "external_or_official_examples_read": False, "capacity_arithmetic": "Decimal integer ratios and exact rational multiplication"}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="New report file outside the input data directory")
    args = parser.parse_args(argv)
    if args.output:
        require(not args.output.is_symlink(), "report output must not be a symlink")
        data_root, output = args.data.resolve(), args.output.resolve()
        require(output != data_root and data_root not in output.parents, "report output must be outside the input data directory")
        require(not args.output.exists(), "report output already exists")
    report = verify(args.data)
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
