"""Audit original citation controls from rendered text, without model inference.

This verifier never imports the generator. Eligibility is recomputed by parsing
the complete source grammar and enumerating truth-changing completions of every
unknown field. Auxiliary document specifications are not an oracle.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jev.api import compile_request
from jev.data import SPLITS, read_jsonl, validate_records
from jev.recipes import citation_check


VERSION = "citation-control-v1"
LABELS = ("supported", "contradicted", "insufficient")
RID = r"R-[0-9a-f]{12}"
DAY = r"[0-9]{4}-[0-9]{2}-[0-9]{2}"
AMOUNT = r"(?:USD [0-9]+|not recorded)"
RECORDED_DAY = rf"(?:{DAY}|not recorded)"
VISITOR = r"(?:yes|no|not recorded)"
ID_RULE = (r'Subject to Section 2, the label "qualifies" applies exactly when the amount '
           rf'is no more than USD ([0-9]+) and the request date is on or after ({DAY})\.')
ID_EXCEPTION = ("Visitor status yes disqualifies a request even when both conditions in Section 1 hold. "
                "Visitor status no does not trigger this exception. These are the complete eligibility "
                "rules; an unrecorded field stays unknown.")
OOD_RULE = ('The decision "qualifies" is assigned if and only if both boundaries hold, '
            'except for the exclusion in B.')
OOD_EXCEPTION = ("A visitor value of yes rules out qualification; no leaves the boundary rules in effect. "
                 "Only these rules determine eligibility. Missing entries remain unknown.")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def match(pattern, value, description):
    found = re.fullmatch(pattern, value)
    require(found is not None, f"unrecognized {description}")
    return found.groups()


def parse_source(text):
    """Consume every source line; unsupported or extra rules fail closed."""
    require(isinstance(text, str), "source must be text")
    lines = text.splitlines()
    require(bool(lines), "empty source")
    if lines[0].startswith("Policy: "):
        require(len(lines) == 16, "ID source must contain exactly 16 lines")
        match(r"Policy: \S.*", lines[0], "policy title")
        for index, expected in ((1, "Section 1 — Eligibility"), (3, "Section 2 — Exception"),
                                (4, ID_EXCEPTION), (5, "Section 3 — Register"),
                                (12, "Section 4 — Charges"),
                                (13, "Delivery charges are not covered by this voucher."),
                                (14, "Section 5 — Unrelated notice")):
            require(lines[index] == expected, f"unexpected ID source line {index + 1}")
        cap, start = match(ID_RULE, lines[2], "ID eligibility rule")
        registers = lines[6:12]
        row_pattern = rf"Request ({RID}): amount ({AMOUNT}); request date ({RECORDED_DAY}); visitor status ({VISITOR})\."
        template = "id"
    else:
        require(len(lines) == 17, "OOD source must contain exactly 17 lines")
        match(r"Operations note: \S.*", lines[0], "operations title")
        for index, expected in ((1, "A. Boundaries"), (3, OOD_RULE), (4, "B. Exclusion"),
                                (5, OOD_EXCEPTION), (6, "C. Register"), (13, "D. Costs"),
                                (14, "The voucher covers no delivery charges."),
                                (15, "E. Unrelated notice")):
            require(lines[index] == expected, f"unexpected OOD source line {index + 1}")
        start, cap = match(rf"The earliest qualifying request date is ({DAY}), inclusive\. "
                           r"The amount ceiling is USD ([0-9]+), inclusive\.", lines[2], "OOD boundaries")
        registers = lines[7:13]
        row_pattern = rf"({RID}) \| requested amount: ({AMOUNT}) \| dated: ({RECORDED_DAY}) \| visitor: ({VISITOR})"
        template = "ood"
    notice_day, _ = match(rf"A printing notice dated ({DAY}) lists a budget of USD ([0-9]+)\. "
                         r"This budget concerns posters, not vouchers\.", lines[-1], "unrelated notice")
    date.fromisoformat(notice_day)
    requests = {}
    for line in registers:
        rid, amount, requested, visitor = match(row_pattern, line, "register entry")
        require(rid not in requests, "duplicate request in source")
        requests[rid] = {
            "amount": None if amount == "not recorded" else int(amount[4:]),
            "date": None if requested == "not recorded" else date.fromisoformat(requested),
            "visitor": None if visitor == "not recorded" else visitor,
        }
    return {"cap": int(cap), "start": date.fromisoformat(start), "requests": requests,
            "template": template}


def semantic_label(source, claim):
    """Return entailment under all completions of facts in the rendered source."""
    document = parse_source(source)
    if claim in ("The voucher covers delivery charges.", "The voucher does not cover delivery charges."):
        return "contradicted" if claim == "The voucher covers delivery charges." else "supported"
    require(isinstance(claim, str), "claim must be text")
    rid, negative = match(rf"Request ({RID}) (qualifies|does not qualify) for the voucher\.",
                          claim, "eligibility claim")
    require(rid in document["requests"], "claim refers to an absent request")
    fact = document["requests"][rid]
    cap, start = document["cap"], document["start"]
    # Representatives cover every truth value of <=, >=, and the yes/no exception.
    amounts = [fact["amount"]] if fact["amount"] is not None else [0, cap, cap + 1]
    days = [fact["date"]] if fact["date"] is not None else [start - timedelta(days=1), start, start + timedelta(days=1)]
    visitors = [fact["visitor"]] if fact["visitor"] is not None else ["yes", "no"]
    outcomes = set()
    for amount, day, visitor in product(amounts, days, visitors):
        qualifies = amount <= cap and day >= start and visitor == "no"
        outcomes.add(not qualifies if negative == "does not qualify" else qualifies)
    return "supported" if outcomes == {True} else "contradicted" if outcomes == {False} else "insufficient"


def normalize_quote(value):
    text = value.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"}))
    return " ".join(text.split())


def quote_status(source, quote):
    if quote is None:
        return "not_requested"
    require(isinstance(quote, str) and bool(quote.strip()), "quote must be nonempty text or null")
    if quote in source:
        return "exact"
    if normalize_quote(quote) in normalize_quote(source):
        return "normalized"
    return "quote_not_found"


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def group_split(group_id, seed):
    encoded = json.dumps([seed, group_id], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    bucket = int(hashlib.sha256(encoded).hexdigest()[:16], 16) % 10000
    return next(split for boundary, split in ((8000, "train"), (8500, "calibration"),
                                              (9000, "validation"), (10000, "test")) if bucket < boundary)


def verify(directory):
    directory = Path(directory)
    names = [f"{split}.jsonl" for split in SPLITS] + ["documents.jsonl", "cases.jsonl"]
    digests = {name: sha256(directory / name) for name in [*names, "manifest.json"]}
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == 1, "unsupported manifest schema")
    require(manifest["files_sha256"] == {name: digests[name] for name in names}, "manifest file hashes differ")
    require(manifest["sha256"] == {split: digests[f"{split}.jsonl"] for split in SPLITS}, "manifest split hashes differ")
    require(manifest["model_input_fields"] == ["state", "question", "kind", "options"], "model input fields differ")
    configuration = manifest["configuration"]
    require(configuration["generator_version"] == VERSION, "unexpected generator version")
    require(type(configuration["seed"]) is int, "seed must be an integer")
    source_hashes = {name: sha256(ROOT / "jev" / name) for name in ("case_citation.py", "recipes.py", "api.py", "data.py")}
    require(configuration["source_files_sha256"] == source_hashes, "generator/runtime source hashes differ")
    documents = list(read_jsonl(directory / "documents.jsonl"))
    cases = list(read_jsonl(directory / "cases.jsonl"))
    records = []
    for split in SPLITS:
        for row in read_jsonl(directory / f"{split}.jsonl"):
            require(row.get("split") == split, "record in wrong split file")
            records.append(row)
    summary = validate_records(records)
    require(summary == manifest["summary"], "manifest schema summary differs")
    require(manifest["counts"] == {split: sum(row["split"] == split for row in records) for split in SPLITS},
            "manifest row counts differ")
    rows = {row["id"]: row for row in records}
    require(len(documents) == configuration["groups"] == manifest["document_count"], "document count differs")
    require(sum(doc["split"] == "ood" for doc in documents) == configuration["ood_groups"], "OOD document count differs")
    docs, groups, parsed = {}, {}, {}
    text_splits, request_owners = {}, {}
    for doc in documents:
        require(set(doc) == {"id", "group_id", "split", "text", "template_id", "spec", "provenance"},
                "document fields differ")
        require(all(isinstance(doc[key], str) and doc[key] for key in ("id", "group_id", "template_id")),
                "document identities must be nonempty text")
        require(doc["id"] not in docs, "duplicate document ID")
        require(doc["group_id"] not in groups, "multiple documents share a group")
        require(doc["split"] in SPLITS, "unknown document split")
        source = parse_source(doc["text"])
        require((source["template"] == "ood") == (doc["split"] == "ood"), "OOD source template leaked")
        if doc["split"] != "ood":
            require(doc["split"] == group_split(doc["group_id"], configuration["seed"]), "document group split differs")
        require(doc["text"] not in text_splits, "duplicate source document")
        for rid in source["requests"]:
            require(rid not in request_owners, "request identity reused across documents")
            request_owners[rid] = doc["id"]
        provenance = doc["provenance"]
        require(provenance.get("type") == "synthetic" and provenance.get("license") == "CC0-1.0",
                "document provenance must identify original CC0 synthetic text")
        require(provenance.get("generator_version") == VERSION and provenance.get("seed") == configuration["seed"],
                "document provenance configuration differs")
        docs[doc["id"]], groups[doc["group_id"]], parsed[doc["id"]] = doc, doc["split"], source
        text_splits[doc["text"]] = doc["split"]
    used_rows, case_ids = set(), set()
    label_counts, quote_counts, gate_counts = Counter(), Counter(), Counter()
    by_split = {split: Counter() for split in SPLITS}
    doc_cases = defaultdict(list)
    label_by_quote = defaultdict(Counter)
    for case in cases:
        prefix = f"case {case.get('id')}: "
        base_keys = {"id", "group_id", "split", "doc_id", "template_id", "case_kind", "quote_mode", "request",
                     "gate", "semantic_record_id"}
        require(case.get("doc_id") in docs, prefix + "unknown document")
        doc = docs[case["doc_id"]]
        require(case.get("id") not in case_ids, prefix + "duplicate case ID")
        require(all(case[key] == doc[key] for key in ("group_id", "split", "template_id")), prefix + "document linkage differs")
        require(isinstance(case["id"], str) and case["id"], prefix + "missing case ID")
        gated = case["request"] is None
        require(set(case) == base_keys | ({"input"} if gated else {"reference_relation"}), prefix + "case fields differ")
        state = case["input"] if gated else case["request"]["state"]
        require(set(state) == {"claim", "source", "quote"}, prefix + "unexpected model state fields")
        require(state["source"] == doc["text"], prefix + "rendered source differs from document")
        status = quote_status(state["source"], state["quote"])
        if status != "quote_not_found":
            expected_mode = "context_only" if status == "not_requested" else status
            require(case["quote_mode"] == expected_mode, prefix + "quote mode differs from final quotation")
        else:
            require(case["quote_mode"] in ("reworded_not_found", "extended_not_found"), prefix + "unknown absent-quote mode")
            require(case["case_kind"] == "quote_not_found", prefix + "absent-quote case kind differs")
        if status == "not_requested":
            expected_gate = {"status": "context_only"}
        elif status == "quote_not_found":
            expected_gate = {"status": "quote_not_found"}
        else:
            source, quote = normalize_quote(state["source"]), normalize_quote(state["quote"])
            start = source.index(quote)
            expected_gate = {"status": "located", "normalized_start": start, "normalized_end": start + len(quote)}
        require(case["gate"] == expected_gate, prefix + "quote gate differs")
        require(gated == (status == "quote_not_found"), prefix + "semantic request escaped quote gate")
        if gated:
            require(case["semantic_record_id"] is None, prefix + "absent quote has a semantic record")
        else:
            require(case["request"] == citation_check(**state), prefix + "citation recipe changed")
            record_id = case["semantic_record_id"]
            require(record_id in rows and record_id not in used_rows, prefix + "missing or repeated semantic record")
            row = rows[record_id]
            require(all(row[key] == case[key] for key in ("group_id", "split")), prefix + "semantic group/split differs")
            require(row["source"] == VERSION, prefix + "semantic source differs")
            compiled, = compile_request(**case["request"])
            require(all(row[key] == compiled[key] for key in ("state", "question", "kind", "options")),
                    prefix + "semantic record differs from compiled request")
            label = semantic_label(state["source"], state["claim"])
            require(case["reference_relation"] == label, prefix + "reference relation differs from rendered text")
            expected_target = [float(answer == label) for answer in compiled["answer_keys"]]
            require(row["target"] == expected_target, prefix + "semantic target differs from rendered text")
            require(row["metadata"].get("provenance", {}).get("license") == "CC0-1.0", prefix + "semantic data license differs")
            used_rows.add(record_id)
            label_counts[label] += 1
            label_by_quote[status][label] += 1
            by_split[case["split"]][label] += 1
        quote_counts[case["quote_mode"]] += 1
        gate_counts[case["gate"]["status"]] += 1
        doc_cases[doc["id"]].append(case)
        case_ids.add(case["id"])
    require(used_rows == set(rows), "orphan semantic records exist")
    for doc_id, doc in docs.items():
        found = doc_cases[doc_id]
        semantic = [case for case in found if case["request"] is not None]
        require(len(found) == 22 and len(semantic) == 20, "each document must have 20 semantic and 2 gated cases")
        require(Counter(case["reference_relation"] for case in semantic) ==
                {"supported": 7, "contradicted": 7, "insufficient": 6}, "per-document label balance differs")
        claims = {f"Request {rid} {phrase} for the voucher." for rid in parsed[doc_id]["requests"]
                  for phrase in ("qualifies", "does not qualify")}
        claims.update(("The voucher covers delivery charges.", "The voucher does not cover delivery charges."))
        require({case["request"]["state"]["claim"] for case in semantic} == claims, "document claim coverage differs")
        require({case["quote_mode"] for case in found if case["request"] is None} ==
                {"reworded_not_found", "extended_not_found"}, "absent-quote mutation coverage differs")
        modes_by_claim, labels_by_claim = defaultdict(set), {}
        for case in semantic:
            state = case["request"]["state"]
            modes_by_claim[state["claim"]].add(quote_status(state["source"], state["quote"]))
            labels_by_claim[state["claim"]] = case["reference_relation"]
        for label in LABELS:
            require(any(modes_by_claim[claim] == {"not_requested", "exact", "normalized"}
                        for claim in claims if labels_by_claim[claim] == label),
                    "a semantic label lacks a claim covered in all three quote modes")
        requests = [json.dumps(case["request"], sort_keys=True, ensure_ascii=False) for case in semantic]
        require(len(set(requests)) == len(requests), "duplicate semantic requests")
    require(manifest["total_case_count"] == len(cases), "manifest case count differs")
    require(manifest["semantic_case_count"] == len(records), "manifest semantic count differs")
    require(manifest["quote_not_found_count"] == gate_counts["quote_not_found"], "manifest absent-quote count differs")
    require(manifest["label_counts"] == dict(label_counts), "manifest label counts differ")
    require(manifest["quote_mode_counts"] == dict(quote_counts), "manifest quote-mode counts differ")
    require(all(sha256(directory / name) == digest for name, digest in digests.items()), "dataset changed during verification")
    return {"verified": True, "generator_version": VERSION, "verification": "CPU rendered-text parsing and completion enumeration",
            "documents": len(documents), "cases": len(cases), "semantic_records": len(records),
            "label_counts": dict(label_counts), "quote_mode_counts": dict(quote_counts), "gate_counts": dict(gate_counts),
            "labels_by_quote_status": {key: dict(value) for key, value in sorted(label_by_quote.items())},
            "labels_by_split": {key: dict(value) for key, value in by_split.items()}, "schema_summary": summary,
            "documents_by_split": {split: sum(doc["split"] == split for doc in documents) for split in SPLITS},
            "files_sha256": digests, "source_files_sha256": source_hashes, "verifier_sha256": sha256(__file__),
            "test_file_sha256": sha256(ROOT / "tests/test_citation_control.py"),
            "scope": {"generator_label_function_used": False, "auxiliary_spec_used_as_oracle": False,
                      "model_or_tokenizer_loaded": False, "external_or_official_examples_read": False}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="New report file outside the input data directory")
    args = parser.parse_args(argv)
    if args.output:
        require(not args.output.is_symlink(), "report output must not be a symlink")
        data_root, output_path = args.data.resolve(), args.output.resolve()
        require(output_path != data_root and data_root not in output_path.parents,
                "report output must be outside the input data directory")
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
