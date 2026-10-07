"""Independent relevance audit for original IR bodies; no generator imports."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from jev.api import compile_request
from jev.data import SPLITS, read_jsonl, split_group, validate_records

VERSION = "ir-control-v1"
LEVELS = [
    "0: About a different system. An incidental quoted query does not change the passage's subject.",
    "1: About the requested system but no applicable current answer: wrong profile, withdrawn guidance, or neither requested value.",
    "2: Current guidance for the requested system and profile provides exactly one of the two requested values.",
    "3: Current guidance for the requested system and profile provides both requested values.",
]
SELECT = "Which passage best answers the query under this relevance rubric? " + " ".join(LEVELS)
METHODS = {"pointwise_noul": 8, "pointwise_score": 8, "pairwise": 2, "setwise": 2, "listwise_choice": 1, "listwise_score": 1}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_query(query):
    patterns = [r"For current guidance on (Relay-[0-9a-f]{12}) in the (burst|steady) profile, what are the retry ceiling and backoff delay\?",
                r"Find the active retry ceiling and backoff delay for (Relay-[0-9a-f]{12}), using its (surge|balanced) operating profile\."]
    for ood, pattern in enumerate(patterns):
        match = re.fullmatch(pattern, query)
        if match:
            return {"system": match[1], "profile": match[2], "ood": bool(ood)}
    raise ValueError("Unknown query grammar")


def parse_passage(passage):
    patterns = [
        r"System: (Relay-[0-9a-f]{12})\nProfile: (burst|steady)\nStatus: (current|withdrawn)\nRetry ceiling: ([0-9]+|not specified) attempts\nBackoff delay: ([0-9]+|not specified) seconds\nQuoted search example only: ([^\n]+)",
        r"Configuration brief for (Relay-[0-9a-f]{12})\.\nProfile in scope: (surge|balanced)\.\nAuthority: (active guidance|superseded guidance; do not use for current settings)\.\nRetry limit: ([0-9]+|not supplied) attempts\.\nBackoff interval: ([0-9]+|not supplied) seconds\.\nQuoted search example only: ([^\n]+)",
    ]
    for ood, pattern in enumerate(patterns):
        match = re.fullmatch(pattern, passage)
        if match:
            return {"system": match[1], "profile": match[2], "current": match[3] in ("current", "active guidance"),
                    "retry_given": match[4].isdigit(), "delay_given": match[5].isdigit(), "ood": bool(ood)}
    raise ValueError("Unknown passage grammar")


def relevance(query, passage):
    need, document = parse_query(query), parse_passage(passage)
    if need["system"] != document["system"]:
        return 0
    if need["profile"] != document["profile"] or not document["current"]:
        return 1
    supplied = int(document["retry_given"]) + int(document["delay_given"])
    return 3 if supplied == 2 else 2 if supplied == 1 else 1


def expected_request(method, query, passages):
    if method == "pointwise_noul":
        return {"state": {"query": query, "passage": passages[0]}, "questions": {"relevant": {"type": "noul",
            "instructions": "Does this passage provide both requested values from current guidance for exactly the requested system and profile? A withdrawn or different-profile answer does not count."}}}
    if method == "pointwise_score":
        return {"state": {"query": query, "passage": passages[0]}, "questions": {"relevance": {"type": "score",
            "instructions": "How completely does this passage answer the query?", "criteria": LEVELS}}}
    if method == "pairwise":
        return {"state": {"query": query, "passage_A": passages[0], "passage_B": passages[1]}, "questions": {
            "more_relevant": {"type": "choice", "instructions": SELECT, "criteria": {"A": "Passage A", "B": "Passage B"}}}}
    values = {f"P{i+1}": passage for i, passage in enumerate(passages)}
    if method in ("setwise", "listwise_choice"):
        questions = {"most_relevant": {"type": "choice", "instructions": SELECT, "criteria": {key: None for key in values}}}
    else:
        require(method == "listwise_score", "Unknown method")
        questions = {f"relevance_{key}": {"type": "score", "instructions": f"How completely does passage {key} answer the query?", "criteria": LEVELS} for key in values}
    return {"state": {"query": query, "passages": values}, "questions": questions}


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    require(set(manifest["files_sha256"]) == {s + ".jsonl" for s in SPLITS} | {"queries.jsonl", "cases.jsonl"}, "Unexpected corpus file set")
    for name, digest in manifest["files_sha256"].items():
        require(sha(directory / name) == digest, "File hash differs: " + name)
    source_paths = [ROOT / "jev/ir_data.py", ROOT / "reports/ir-control-v1/pilot-source/ir_data.py"]
    require(manifest["configuration"]["generator_sha256"] in {sha(path) for path in source_paths if path.is_file()}, "Generator changed without a preserved source snapshot")
    rows = [row for split in SPLITS for row in read_jsonl(directory / (split + ".jsonl"))]
    summary = validate_records(rows)
    require(summary == manifest["summary"], "Summary differs")
    require(summary["groups"] == manifest["configuration"]["groups"] and summary["records"] == 58 * summary["groups"], "Configured family size differs")
    for row in rows:
        index = row["metadata"]["provenance"]["group_index"]
        expected_split = "ood" if index % 10 >= 8 else split_group(row["group_id"], manifest["configuration"]["seed"])
        require(row["split"] == expected_split, "Stable family split assignment differs")
    by_id = {row["id"]: row for row in rows}
    queries = list(read_jsonl(directory / "queries.jsonl"))
    by_query, groups, grade_counts = {}, defaultdict(list), Counter()
    for query in queries:
        require(query["id"] not in by_query, "Duplicate query ID")
        require(query["source"] == VERSION and query["external_benchmark"] is False, "External query in original corpus")
        need = parse_query(query["query"])
        require(query["group_id"] == "ir:" + need["system"][6:], "Query system crosses groups")
        require(need["ood"] == (query["split"] == "ood"), "OOD query grammar crossed split boundary")
        documents = {doc["id"]: doc["text"] for doc in query["documents"]}
        require(len(documents) == 8 == len(query["documents"]), "Expected eight unique documents")
        require(all(parse_passage(text)["ood"] == need["ood"] for text in documents.values()), "Passage layout leaked across OOD boundary")
        grades = {doc_id: relevance(query["query"], text) for doc_id, text in documents.items()}
        require(grades == query["reference_relevance"], "Reference relevance differs from visible query/passage")
        grade_counts.update(str(grade) for grade in grades.values())
        by_query[query["id"]] = query, documents, grades
        groups[query["group_id"]].append(query)
    for family in groups.values():
        require(len(family) == 2 and len({q["split"] for q in family}) == 1, "Query counterfactual family leaked or incomplete")
        require({d["id"]: d["text"] for d in family[0]["documents"]} == {d["id"]: d["text"] for d in family[1]["documents"]}, "Counterfactual documents differ")
        require(parse_query(family[0]["query"])["profile"] != parse_query(family[1]["query"])["profile"], "Missing profile counterfactual")
    cases = list(read_jsonl(directory / "cases.jsonl"))
    used, methods, query_methods = set(), Counter(), defaultdict(Counter)
    for case in cases:
        query, documents, grades = by_query[case["query_id"]]
        require(case["group_id"] == query["group_id"] and case["split"] == query["split"], "Case linkage differs")
        require(case["source"] == VERSION and case["external_benchmark"] is False, "External case in original corpus")
        method, doc_ids = case["method"], case["document_ids"]
        require(len(doc_ids) == len(set(doc_ids)) and set(doc_ids) <= set(documents), "Invalid candidate identity")
        expected_size = 1 if method.startswith("pointwise_") else 2 if method == "pairwise" else 4 if method == "setwise" else 8
        require(len(doc_ids) == expected_size, "Candidate count differs")
        expected = expected_request(method, query["query"], [documents[key] for key in doc_ids])
        require(case["request"] == expected, "Runtime request differs from source contract")
        compiled = compile_request(**case["request"])
        require(len(compiled) == len(case["record_ids"]), "Question coverage differs")
        for head, (item, record_id) in enumerate(zip(compiled, case["record_ids"])):
            require(record_id in by_id and record_id not in used, "Missing or repeated row")
            row = by_id[record_id]
            require(all(row[field] == item[field] for field in ("state", "question", "kind", "options")), "Compiled row differs")
            require(row["group_id"] == case["group_id"] and row["split"] == case["split"], "Row linkage differs")
            if item["kind"] == "score":
                target = [float(level == grades[doc_ids[head]]) for level in range(4)]
            elif item["kind"] == "noul":
                yes = grades[doc_ids[0]] == 3
                target = [float(not yes), float(yes)]
            else:
                values = [grades[key] for key in doc_ids]
                count = values.count(max(values))
                target = [1.0 / count if grade == max(values) else 0.0 for grade in values]
            require(row["target"] == target, "Target differs from body-derived relevance")
            used.add(record_id)
        methods[method] += 1
        query_methods[case["query_id"]][method] += 1
    require(used == set(by_id), "Orphan training row")
    require(all(dict(counts) == METHODS for counts in query_methods.values()), "Incomplete per-query protocol cases")
    require(len(queries) == manifest["query_count"] and len(cases) == manifest["request_case_count"], "Corpus counts differ")
    require(dict(methods) == manifest["request_methods"] and dict(grade_counts) == manifest["relevance_counts"], "Category summary differs")
    require(manifest["training_performed"] is False and manifest["model_inference_performed"] is False and manifest["external_trec_downloaded"] is False and manifest["external_trec_evaluated"] is False, "Unverified experiment claim")
    return {"status": "passed", "summary": summary, "queries": len(queries), "request_cases": len(cases), "families": len(groups),
            "request_methods": dict(methods), "body_derived_relevance_counts": dict(grade_counts),
            "manifest_sha256": sha(directory / "manifest.json"), "generator_imported": False,
            "reference_metadata_used_to_derive_labels": False, "external_trec_downloaded": False, "external_trec_evaluated": False,
            "model_inference_performed": False, "scope": "Original finite relevance grammar only; not real-world relevance judgments or reproduced TREC metrics."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
