"""Original contextual citation controls; CPU-only generation, no model calls."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import random
import re

from .api import compile_request
from .data import SPLITS, _hash, _write_dataset, split_group
from .recipes import citation_check

VERSION = "citation-control-v1"
QUOTE_MODES = ("context_only", "exact", "normalized")
SPLIT_POLICY = "whole_original_document_group; independent_id_hash_splits; reserved_operations_wording_ood"
_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"})


def normalize_quote(text):
    """Only normalize Unicode quotation marks and whitespace; preserve wording/case."""
    if not isinstance(text, str):
        raise ValueError("Citation text must be a string")
    return re.sub(r"\s+", " ", text.translate(_QUOTES)).strip()


def locate_quote(source, quote):
    """Return a deterministic gate, never a semantic label or model confidence."""
    if quote is None:
        return {"status": "context_only"}
    normalized = normalize_quote(quote)
    if not normalized:
        raise ValueError("An empty quote is not a supplied quotation")
    start = normalize_quote(source).find(normalized)
    if start < 0:
        return {"status": "quote_not_found"}
    # Offsets refer to normalized text, not byte/character positions in the source.
    return {"status": "located", "normalized_start": start, "normalized_end": start+len(normalized)}


def eligibility(request, maximum, start):
    """Derive truth from explicit facts before rendering; missing values stay unknown."""
    amount, date, visitor = request["amount"], request["date"], request["visitor"]
    if visitor is True or (amount is not None and amount > maximum) or (date is not None and date < start):
        return False
    if amount is None or date is None or visitor is None:
        return None
    return True


def relation(truth, positive):
    if truth is None:
        return "insufficient"
    return "supported" if truth == positive else "contradicted"


def document_spec(group, rng):
    maximum = rng.randrange(80, 601, 5)
    start = datetime.date(2027, 1, 1) + datetime.timedelta(days=rng.randrange(600))
    iso = lambda offset: (start+datetime.timedelta(days=offset)).isoformat()
    facts = [
        ("boundary", maximum, iso(0), False),
        ("amount_above", maximum+1, iso(1), False),
        ("date_before", maximum-1, iso(-1), False),
        ("visitor_exception", maximum-1, iso(1), True),
        ("unknown_date", maximum-1, None, False),
        ("unknown_visitor", maximum-1, iso(1), None),
    ]
    requests = [{"id": "R-"+_hash([group, rng.getrandbits(128)])[:12], "case_kind": kind,
                 "amount": amount, "date": date, "visitor": visitor} for kind,amount,date,visitor in facts]
    rng.shuffle(requests)
    program = rng.choice(("Maple", "Cedar", "Birch", "Linden", "Willow"))+" "+rng.choice(("Workshop", "Studio", "Office", "Lab"))+" "+_hash([group,"program"])[:8]
    return {"program": program, "maximum": maximum, "start": iso(0), "requests": requests,
            "notice_date": iso(60), "printing_budget": maximum+200}


def render_document(spec, ood):
    maximum, start = spec["maximum"], spec["start"]
    if ood:
        quote = 'The decision "qualifies" is assigned if and only if both boundaries hold, except for the exclusion in B.'
        text = [f"Operations note: {spec['program']}", "A. Boundaries",
                f"The earliest qualifying request date is {start}, inclusive. The amount ceiling is USD {maximum}, inclusive.",
                quote, "B. Exclusion",
                "A visitor value of yes rules out qualification; no leaves the boundary rules in effect. Only these rules determine eligibility. Missing entries remain unknown.",
                "C. Register"]
    else:
        quote = f'Subject to Section 2, the label "qualifies" applies exactly when the amount is no more than USD {maximum} and the request date is on or after {start}.'
        text = [f"Policy: {spec['program']}", "Section 1 — Eligibility", quote, "Section 2 — Exception",
                "Visitor status yes disqualifies a request even when both conditions in Section 1 hold. Visitor status no does not trigger this exception. These are the complete eligibility rules; an unrecorded field stays unknown.",
                "Section 3 — Register"]
    for request in spec["requests"]:
        amount = "not recorded" if request["amount"] is None else f"USD {request['amount']}"
        date = request["date"] or "not recorded"
        visitor = "not recorded" if request["visitor"] is None else "yes" if request["visitor"] else "no"
        text.append(f"{request['id']} | requested amount: {amount} | dated: {date} | visitor: {visitor}" if ood else
                    f"Request {request['id']}: amount {amount}; request date {date}; visitor status {visitor}.")
    text.extend(["D. Costs" if ood else "Section 4 — Charges",
                 "The voucher covers no delivery charges." if ood else "Delivery charges are not covered by this voucher.",
                 "E. Unrelated notice" if ood else "Section 5 — Unrelated notice",
                 f"A printing notice dated {spec['notice_date']} lists a budget of USD {spec['printing_budget']}. This budget concerns posters, not vouchers."])
    return "\n".join(text), quote


def claims(spec):
    """Labels use fact values before either source or claim strings are rendered."""
    result = []
    for request in spec["requests"]:
        truth = eligibility(request, spec["maximum"], spec["start"])
        for positive in (True, False):
            label = relation(truth, positive)
            claim = f"Request {request['id']} qualifies for the voucher." if positive else f"Request {request['id']} does not qualify for the voucher."
            result.append((claim, label, request["case_kind"], positive))
    result.extend([("The voucher covers delivery charges.", relation(False, True), "delivery_charges", True),
                   ("The voucher does not cover delivery charges.", relation(False, False), "delivery_charges", False)])
    return result


def generate(groups=200, seed=42, ood_groups=None):
    """groups is the total original-document count, including dedicated OOD groups."""
    if type(groups) is not int or groups < 2 or type(seed) is not int:
        raise ValueError("groups must be an integer >=2 and seed must be an integer")
    ood_groups = max(1, groups//5) if ood_groups is None else ood_groups
    if type(ood_groups) is not int or not 0 <= ood_groups < groups:
        raise ValueError("ood_groups must be an integer in [0, groups)")
    documents, cases, records = [], [], []
    for index in range(groups):
        ood = index >= groups-ood_groups
        group = f"{VERSION}:{seed}:{'ood' if ood else 'id'}:{index}"
        rng = random.Random(int(_hash(group),16))
        spec = document_spec(group,rng)
        original_claims = claims(spec)
        text, exact_quote = render_document(spec,ood)
        split = "ood" if ood else split_group(group,seed)
        template = f"{VERSION}/{'operations-ood' if ood else 'policy-id'}"
        provenance = {"type":"synthetic", "generator_version":VERSION, "seed":seed, "group_index":index,
                      "variant":0, "license":"CC0-1.0", "split_policy":SPLIT_POLICY,
                      "source_relation":"original_documents_facts_and_claims; no_external_examples_or_results_used"}
        doc_id = "doc-"+_hash(group)[:20]
        documents.append({"id":doc_id,"group_id":group,"split":split,"text":text,
                          "template_id":template,"spec":spec,"provenance":provenance})
        case_index = 0
        for claim_index,(claim,label,kind,positive) in enumerate(original_claims):
            modes = QUOTE_MODES if positive and kind in ("boundary","visitor_exception","unknown_visitor") else (QUOTE_MODES[(index+claim_index)%3],)
            for mode in modes:
                quote = None if mode == "context_only" else exact_quote
                if mode == "normalized":
                    # Typography and whitespace change; every quoted word remains unchanged.
                    quote = exact_quote.replace('"qualifies"','“qualifies”').replace(" ","  \n ")
                request = citation_check(claim,text,quote)
                gate = locate_quote(text,quote)
                if gate["status"] == "quote_not_found":
                    raise ValueError("Semantic case unexpectedly has an absent quotation")
                compiled, = compile_request(**request)
                case_id = f"{doc_id}:case:{case_index}"
                record_id = case_id+":support"
                case = {"id":case_id,"group_id":group,"split":split,"doc_id":doc_id,"template_id":template,
                        "case_kind":kind,"quote_mode":mode,"request":request,"gate":gate,
                        "semantic_record_id":record_id,"reference_relation":label}
                cases.append(case)
                records.append({"id":record_id,"group_id":group,"split":split,"source":VERSION,
                                "state":compiled["state"],"question":compiled["question"],"kind":compiled["kind"],
                                "options":compiled["options"],"target":[float(key == label) for key in compiled["answer_keys"]],
                                "metadata":{"family":"evidence","template_id":template,"case_name":"contextual_citation",
                                            "question_id":"support","case_id":case_id,"document_id":doc_id,
                                            "case_kind":kind,"quote_mode":mode,"entity_ids":[doc_id],
                                            "target_basis":"Exact relation under original complete policy and visible request facts; not model confidence.",
                                            "provenance":{**provenance,"variant":case_index}}})
                case_index += 1
        for mode,quote in (("reworded_not_found",exact_quote.replace('"qualifies"','"always qualifies"')),
                           ("extended_not_found",exact_quote+" Automatic processing takes exactly one hour.")):
            state = {"claim":original_claims[0][0],"source":text,"quote":quote}
            gate = locate_quote(text,quote)
            if gate != {"status":"quote_not_found"}:
                raise ValueError("Absent-quote control unexpectedly occurs in source")
            cases.append({"id":f"{doc_id}:case:{case_index}","group_id":group,"split":split,"doc_id":doc_id,
                          "template_id":template,"case_kind":"quote_not_found","quote_mode":mode,
                          "input":state,"request":None,"gate":gate,"semantic_record_id":None})
            case_index += 1
    return documents,cases,records


def build_dataset(output_dir, groups=200, seed=42, ood_groups=None):
    output = Path(output_dir)
    if output.is_symlink() or (output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("Choose a new empty citation dataset directory; existing corpora are never overwritten")
    documents,cases,records = generate(groups,seed,ood_groups)
    manifest = _write_dataset(records,output,{"type":"synthetic","generator_version":VERSION,
        "groups":groups,"ood_groups":sum(d["split"] == "ood" for d in documents),"seed":seed,"license":"CC0-1.0",
        "runtime_builder":"jev.recipes.citation_check","split_policy":SPLIT_POLICY,
        "source_files_sha256":{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                               for name in ("case_citation.py","recipes.py","api.py","data.py")}})
    for name,values in (("documents.jsonl",documents),("cases.jsonl",cases)):
        path = output/name
        # Preserve recipe criteria insertion order for exact compile_request round trips.
        path.write_text("".join(json.dumps(value,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n" for value in values))
        manifest["files_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.update(counts={split:sum(r["split"] == split for r in records) for split in SPLITS},
                    sha256={split:manifest["files_sha256"][split+".jsonl"] for split in SPLITS},
                    document_count=len(documents),total_case_count=len(cases),semantic_case_count=len(records),
                    quote_not_found_count=sum(case["gate"]["status"] == "quote_not_found" for case in cases),
                    label_counts=dict(Counter(case["reference_relation"] for case in cases if "reference_relation" in case)),
                    quote_mode_counts=dict(Counter(case["quote_mode"] for case in cases)),
                    intended_scope="Original controlled-policy citation decisions; wording OOD only; no arbitrary factual-verification claim.",
                    training_performed=False,model_inference_performed=False,
                    frozen_training_datasets_modified=False)
    (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",required=True,type=Path)
    parser.add_argument("--groups",type=int,default=200,help="Total original document groups, including OOD")
    parser.add_argument("--ood-groups",type=int,help="Default: one fifth of total groups")
    parser.add_argument("--seed",type=int,default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir,args.groups,args.seed,args.ood_groups),indent=2))


if __name__ == "__main__":
    main()
