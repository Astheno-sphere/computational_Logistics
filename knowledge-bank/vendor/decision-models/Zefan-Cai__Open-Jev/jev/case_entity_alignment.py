"""Original catalog controls and a four-head entity-alignment request builder."""
import argparse
from collections import Counter
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import random
import re

from .api import compile_request
from .data import SPLITS, _hash, _write_dataset, split_group
from .recipes import entity_alignment, noul

VERSION = "entity-alignment-control-v1"
POLICY_VERSION = "visible-catalog-alignment-v1"
FIELDS = ("name", "manufacturer", "capacity")
HEADS = ("match", "name_agrees", "manufacturer_agrees", "capacity_agrees")
UNITS = {"mL": "1", "L": "1000", "cL": "10"}
SPLIT_POLICY = "all_pairs_and_shared_entities_in_original_family_group; hash_id_splits; reserved_alias_and_policy_wording_ood"
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


def normalized_text(value):
    return " ".join(value.split()).casefold() if isinstance(value,str) else None


def alias_index(table):
    if not isinstance(table,dict) or not table:
        raise ValueError("Alias tables must contain canonical names and explicit aliases")
    result = {}
    for canonical,aliases in table.items():
        if not isinstance(canonical,str) or not canonical.strip() or not isinstance(aliases,list):
            raise ValueError("Invalid canonical name/alias list")
        key = normalized_text(canonical)
        for text in [canonical,*aliases]:
            if not isinstance(text,str) or not text.strip():
                raise ValueError("Aliases must be nonempty strings")
            alias = normalized_text(text)
            if alias in result and result[alias] != key:
                raise ValueError("An alias cannot identify two canonical values")
            result[alias] = key
    return result


def quantity(value, units):
    """Convert a visible positive ASCII decimal string to an exact rational mL value."""
    if not isinstance(value,dict) or set(value) != {"value","unit"}:
        return None
    number,unit = value["value"],value["unit"]
    if not isinstance(number,str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?",number):
        return None
    if not isinstance(unit,str) or unit not in units:
        return None
    result = Fraction(number)*Fraction(units[unit])
    return result if result > 0 else None


def make_policy(name_aliases, manufacturer_aliases, style="catalog"):
    if style not in RULES:
        raise ValueError("policy_style must be catalog or procurement")
    alias_index(name_aliases)
    alias_index(manufacturer_aliases)
    return {"version":POLICY_VERSION,"wording":style,
            "scope":"This is the complete decision policy for these supplied catalog records, not a universal identity guarantee.",
            "identifier_rule":"Identifiers are {namespace,value}. Both must be nonempty strings. Trim outer whitespace but preserve case and internal text. Equal namespaces permit comparison: equal values agree, different values conflict. Missing components or different namespaces give unknown identifier evidence.",
            "text_rule":"For name and manufacturer, collapse whitespace and casefold. Each canonical table key and its listed aliases identify that canonical value. Two recognized equal canonicals agree; two recognized different canonicals conflict. Missing or unlisted text gives unknown evidence, even if two unlisted strings happen to match. No other spelling or punctuation equivalence is assumed.",
            "capacity_rule":"Capacity is {value,unit}. value must be a positive ordinary ASCII decimal string (no sign, exponent or fraction); unit must match the visible table exactly. Multiply the exact rational decimal value by unit_to_mL. Equal known mL values agree; unequal known values conflict. Missing, invalid or unlisted-unit capacity gives unknown evidence. capacity_evidence contains only these exact converted values; no model judgment or rounding is involved.",
            "noul_rule":"Each field Noul asks whether visible evidence establishes agreement. Yes only for agreement; no for conflict OR unknown. No is not a probability of physical inequality.",
            "rules_in_order":list(RULES[style]),"aliases":{"name":copy.deepcopy(name_aliases),"manufacturer":copy.deepcopy(manufacturer_aliases)},
            "unit_to_mL":dict(UNITS),"score_routes":{"0":"different","1":"review","2":"same"}}


def entity_alignment_fields(left, right, *, name_aliases, manufacturer_aliases, policy_style="catalog"):
    """One Score and three evidence Nouls; shared recipe behavior is unchanged."""
    if not isinstance(left,dict) or not isinstance(right,dict):
        raise ValueError("Catalog records must be objects")
    policy = make_policy(name_aliases,manufacturer_aliases,policy_style)
    request = entity_alignment(copy.deepcopy(left),copy.deepcopy(right))
    state = request["state"]
    state["policy"] = policy
    state["capacity_evidence"] = {}
    for side in ("left","right"):
        value = quantity(state[side].get("capacity"),policy["unit_to_mL"])
        state["capacity_evidence"][side] = None if value is None else {"unit":"mL","exact_value":str(value)}
    request["questions"]["match"]["instructions"] = (
        "Apply the complete supplied catalog policy in order to select different, review or same. Do not infer hidden identities."
        if policy_style == "catalog" else
        "Follow the visible procurement protocol and select the stated identity route. Evidence unavailable in these records cannot be invented.")
    for field in FIELDS:
        request["questions"][field+"_agrees"] = noul(
            f"Does the visible evidence establish agreement of {field} under the supplied policy? Answer yes only for established agreement; conflict or unknown evidence means no."
            if policy_style == "catalog" else
            f"Is equality of {field} established by these entries and the disclosed rules? Return yes for established equality, and no for either a known difference or insufficient field evidence.")
    compile_request(**request)
    return request


def identifier_status(left, right):
    values = []
    for record in (left,right):
        item = record.get("identifier")
        if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k].strip() for k in ("namespace","value")):
            return "unknown"
        values.append((item["namespace"].strip(),item["value"].strip()))
    if values[0][0] != values[1][0]:
        return "unknown"
    return "agreement" if values[0][1] == values[1][1] else "conflict"


def reference(request):
    """Controlled reference from visible records/policy; no family identity lookup."""
    state = request["state"]
    left,right,policy = state["left"],state["right"],state["policy"]
    evidence = {}
    for field in FIELDS:
        if field == "capacity":
            a,b = (quantity(record.get(field),policy["unit_to_mL"]) for record in (left,right))
        else:
            lookup = alias_index(policy["aliases"][field])
            a,b = (lookup.get(normalized_text(record.get(field))) for record in (left,right))
        evidence[field] = "unknown" if a is None or b is None else "agreement" if a == b else "conflict"
    identifier = identifier_status(left,right)
    if identifier == "conflict":
        match = 0
    elif "conflict" in evidence.values():
        match = 1 if identifier == "agreement" else 0
    elif identifier == "agreement" or all(value == "agreement" for value in evidence.values()):
        match = 2
    else:
        match = 1
    return {"match":match,**{field+"_agrees":evidence[field] == "agreement" for field in FIELDS}},evidence,identifier


def family_spec(group, rng, ood):
    code = _hash([group,"vocabulary"])[:10]
    color = rng.choice(("Amber","Indigo","Silver","Teal","Ochre"))
    tree = rng.choice(("Alder","Larch","Poplar","Willow","Cedar"))
    if ood:
        names = [f"Container {code} / {color}",f"Container {code} / {color} wide"]
        name_aliases = {names[0]:[f"{code}:{color}:vessel"],names[1]:[f"{code}:{color}:wide vessel"]}
        makers = [f"{code} Factory Group {tree}",f"{code} Factory Group {tree} East"]
        manufacturer_aliases = {makers[0]:[f"{tree}, maker {code}"],makers[1]:[f"{tree} East, maker {code}"]}
    else:
        names = [f"{color} Flask {code}",f"{color} Flask Wide {code}"]
        name_aliases = {names[0]:[f"{color}-{code} flask"],names[1]:[f"{color}-{code} wide flask"]}
        makers = [f"{tree} Instruments {code}",f"{tree} East Instruments {code}"]
        manufacturer_aliases = {makers[0]:[f"{tree} Instr. {code}"],makers[1]:[f"{tree} East Instr. {code}"]}
    capacity = rng.choice((250,500,750,1000,1250,1500,1750))
    identifiers = ["SKU-"+_hash([group,i])[:14] for i in range(3)]
    return {"names":names,"manufacturers":makers,"name_aliases":name_aliases,"manufacturer_aliases":manufacturer_aliases,
            "capacity_mL":capacity,"identifiers":identifiers,"unknown_name":f"Uncatalogued vessel {code}"}


def pairs(spec, ood):
    base = {"identifier":{"namespace":"stockroom","value":spec["identifiers"][0]},"name":spec["names"][0],
            "manufacturer":spec["manufacturers"][0],"capacity":{"value":str(spec["capacity_mL"]),"unit":"mL"}}
    alias = copy.deepcopy(base)
    alias["name"] = spec["name_aliases"][base["name"]][0]
    alias["manufacturer"] = spec["manufacturer_aliases"][base["manufacturer"]][0]
    # Integer arithmetic formats terminating decimal strings, never binary floats.
    divisor,unit = (10,"cL") if ood else (1000,"L")
    whole,remainder = divmod(spec["capacity_mL"],divisor)
    value = str(whole) if remainder == 0 else f"{whole}.{remainder:0{len(str(divisor))-1}d}".rstrip("0")
    alias["capacity"] = {"value":value,"unit":unit}
    yield "same_identifier_alias_units",copy.deepcopy(base),copy.deepcopy(alias)
    left,right = copy.deepcopy(base),copy.deepcopy(alias)
    left["identifier"] = right["identifier"] = None
    yield "no_identifier_all_fields_agree",copy.deepcopy(left),copy.deepcopy(right)
    changed = copy.deepcopy(alias)
    changed["identifier"]["value"] = spec["identifiers"][1]
    yield "conflicting_identifiers_equal_fields",copy.deepcopy(base),changed
    changed = copy.deepcopy(alias)
    changed["capacity"] = {"value":str(spec["capacity_mL"]+1),"unit":"mL"}
    yield "same_identifier_capacity_conflict",copy.deepcopy(base),changed
    for field,value in (("name",spec["names"][1]),("manufacturer",spec["manufacturers"][1]),
                        ("capacity",{"value":str(spec["capacity_mL"]+1),"unit":"mL"})):
        changed = copy.deepcopy(right)
        changed[field] = value
        yield field+"_conflict",copy.deepcopy(left),changed
    for field in FIELDS:
        changed = copy.deepcopy(right)
        changed[field] = None
        yield field+"_missing",copy.deepcopy(left),changed
    changed = copy.deepcopy(alias)
    changed["name"] = None
    yield "same_identifier_name_missing",copy.deepcopy(base),changed
    changed = copy.deepcopy(alias)
    changed["identifier"] = {"namespace":"supplier","value":spec["identifiers"][2]}
    yield "different_namespaces_equal_fields",copy.deepcopy(base),changed
    changed = copy.deepcopy(right)
    changed["name"] = spec["unknown_name"]
    yield "name_unlisted",copy.deepcopy(left),changed
    yield "all_fields_missing",copy.deepcopy(left),{key:None for key in base}


def generate(groups=200, seed=42, ood_groups=None):
    if type(groups) is not int or groups < 2 or type(seed) is not int:
        raise ValueError("groups must be an integer >=2 and seed must be an integer")
    ood_groups = max(1,groups//5) if ood_groups is None else ood_groups
    if type(ood_groups) is not int or not 0 <= ood_groups < groups:
        raise ValueError("ood_groups must be an integer in [0,groups)")
    families,cases,rows = [],[],[]
    for index in range(groups):
        ood = index >= groups-ood_groups
        group = f"{VERSION}:{seed}:{'ood' if ood else 'id'}:{index}"
        rng = random.Random(int(_hash(group),16))
        spec = family_spec(group,rng,ood)
        split = "ood" if ood else split_group(group,seed)
        template = f"{VERSION}/{'procurement-ood' if ood else 'catalog-id'}"
        family_id = "family-"+_hash(group)[:20]
        provenance = {"type":"synthetic","generator_version":VERSION,"seed":seed,"group_index":index,"variant":0,
                      "license":"CC0-1.0","split_policy":SPLIT_POLICY,
                      "source_relation":"original_catalog_records_aliases_and_policy; no_external_examples_or_results"}
        family_cases = []
        for variant,(name,left,right) in enumerate(pairs(spec,ood)):
            request = entity_alignment_fields(left,right,name_aliases=spec["name_aliases"],
                manufacturer_aliases=spec["manufacturer_aliases"],policy_style="procurement" if ood else "catalog")
            answers,evidence,identifier = reference(request)
            case_id = f"{family_id}:pair:{variant}"
            case = {"id":case_id,"family_id":family_id,"group_id":group,"split":split,"template_id":template,
                    "variant":name,"request":request,"reference":answers,"field_evidence":evidence,"identifier_evidence":identifier}
            cases.append(case)
            family_cases.append(case_id)
            for compiled in compile_request(**request):
                key = compiled["id"]
                target = [float(i == answers[key]) for i in range(3)] if key == "match" else [float(not answers[key]),float(answers[key])]
                metadata = {"family":"evidence","template_id":template,"case_name":"entity_alignment_fields","question_id":key,
                            "case_id":case_id,"catalog_family_id":family_id,"entity_ids":[family_id],"variant":name,
                            "target_basis":"Declared visible-evidence catalog policy; hard reference decisions, not model confidence.",
                            "provenance":{**provenance,"variant":variant}}
                if key == "match":
                    metadata["score_values"] = [0,1,2]
                rows.append({"id":case_id+":"+key,"group_id":group,"split":split,"source":VERSION,
                             "state":compiled["state"],"question":compiled["question"],"kind":compiled["kind"],
                             "options":compiled["options"],"target":target,"metadata":metadata})
        families.append({"id":family_id,"group_id":group,"split":split,"template_id":template,
                         "spec":spec,"policy":cases[-1]["request"]["state"]["policy"],"case_ids":family_cases,"provenance":provenance})
    return families,cases,rows


def build_dataset(output_dir, groups=200, seed=42, ood_groups=None):
    output = Path(output_dir)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Choose a new empty entity-alignment directory; existing corpora are never overwritten")
    families,cases,rows = generate(groups,seed,ood_groups)
    manifest = _write_dataset(rows,output,{"type":"synthetic","generator_version":VERSION,"groups":groups,
        "ood_groups":sum(f["split"] == "ood" for f in families),"seed":seed,"license":"CC0-1.0",
        "runtime_builder":"jev.case_entity_alignment.entity_alignment_fields","split_policy":SPLIT_POLICY,
        "source_files_sha256":{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                               for name in ("case_entity_alignment.py","recipes.py","api.py","data.py")}})
    for name,values in (("families.jsonl",families),("cases.jsonl",cases)):
        path = output/name
        path.write_text("".join(json.dumps(value,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n" for value in values))
        manifest["files_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.update(counts={split:sum(r["split"] == split for r in rows) for split in SPLITS},
                    sha256={split:manifest["files_sha256"][split+".jsonl"] for split in SPLITS},family_count=len(families),
                    case_count=len(cases),typed_record_count=len(rows),head_counts=dict(Counter(r["metadata"]["question_id"] for r in rows)),
                    route_counts=dict(Counter(str(case["reference"]["match"]) for case in cases)),
                    field_evidence_counts={field:dict(Counter(case["field_evidence"][field] for case in cases)) for field in FIELDS},
                    training_performed=False,model_inference_performed=False,frozen_training_datasets_modified=False,
                    intended_scope="Original catalog linking policy with name/manufacturer/capacity evidence; not universal identity resolution or graph merging.")
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--groups",type=int,default=200,help="Total family groups, including OOD")
    parser.add_argument("--ood-groups",type=int)
    parser.add_argument("--seed",type=int,default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir,args.groups,args.seed,args.ood_groups),indent=2))


if __name__ == "__main__":
    main()
