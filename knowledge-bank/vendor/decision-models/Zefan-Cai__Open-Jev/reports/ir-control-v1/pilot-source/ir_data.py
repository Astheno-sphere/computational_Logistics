"""Original graded retrieval controls and community-shaped reranker requests."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

from .api import compile_request
from .data import SPLITS, _hash, _write_dataset, split_group

VERSION = "ir-control-v1"
SOURCE_COMMIT = "ac843ed63a302900d76722b83be926fdb84a3936"
SPLIT_POLICY = "whole_system_family_all_query_mode_counterfactuals_and_passages; reserved_brief_wording_ood"
SCORE_LEVELS = [
    "0: About a different system. An incidental quoted query does not change the passage's subject.",
    "1: About the requested system but no applicable current answer: wrong profile, withdrawn guidance, or neither requested value.",
    "2: Current guidance for the requested system and profile provides exactly one of the two requested values.",
    "3: Current guidance for the requested system and profile provides both requested values.",
]
CHOICE_INSTRUCTIONS = "Which passage best answers the query under this relevance rubric? " + " ".join(SCORE_LEVELS)
SOURCE_INTERFACE = "https://github.com/ielab/llm-rankers/blob/" + SOURCE_COMMIT + "/jev/jev_rankers.py"


def pointwise(query, passage, kind="score"):
    if kind == "score":
        questions = {"relevance": {"type": "score", "instructions": "How completely does this passage answer the query?", "criteria": SCORE_LEVELS}}
    elif kind == "noul":
        questions = {"relevant": {"type": "noul", "instructions": "Does this passage provide both requested values from current guidance for exactly the requested system and profile? A withdrawn or different-profile answer does not count."}}
    else:
        raise ValueError("Pointwise kind must be noul or score")
    return {"state": {"query": query, "passage": passage}, "questions": questions}


def pairwise(query, first, second):
    return {"state": {"query": query, "passage_A": first, "passage_B": second}, "questions": {
        "more_relevant": {"type": "choice", "instructions": CHOICE_INSTRUCTIONS,
                          "criteria": {"A": "Passage A", "B": "Passage B"}}}}


def window_request(query, passages, kind="choice"):
    if not 2 <= len(passages) <= 100:
        raise ValueError("A comparison window requires 2 to 100 passages")
    values = {f"P{i + 1}": passage for i, passage in enumerate(passages)}
    if kind == "choice":
        questions = {"most_relevant": {"type": "choice", "instructions": CHOICE_INSTRUCTIONS,
                                       "criteria": {label: None for label in values}}}
    elif kind == "score":
        questions = {f"relevance_{label}": {"type": "score", "instructions": f"How completely does passage {label} answer the query?",
                                           "criteria": SCORE_LEVELS} for label in values}
    else:
        raise ValueError("Window kind must be choice or score")
    return {"state": {"query": query, "passages": values}, "questions": questions}


def _passage(subject, profile, current, retry, delay, quoted_query, ood):
    if ood:
        return (f"Configuration brief for {subject}.\nProfile in scope: {profile}.\n"
                f"Authority: {'active guidance' if current else 'superseded guidance; do not use for current settings'}.\n"
                f"Retry limit: {retry if retry is not None else 'not supplied'} attempts.\n"
                f"Backoff interval: {delay if delay is not None else 'not supplied'} seconds.\n"
                f"Quoted search example only: {quoted_query}")
    return (f"System: {subject}\nProfile: {profile}\nStatus: {'current' if current else 'withdrawn'}\n"
            f"Retry ceiling: {retry if retry is not None else 'not specified'} attempts\n"
            f"Backoff delay: {delay if delay is not None else 'not specified'} seconds\n"
            f"Quoted search example only: {quoted_query}")


def generate(groups=200, seed=42, ood_groups=40):
    if type(groups) is not int or type(ood_groups) is not int or not 1 <= ood_groups < groups:
        raise ValueError("Require groups > ood_groups >= 1")
    queries, cases, records = [], [], []
    for index in range(groups):
        code = _hash([VERSION, seed, index])[:12]
        group = "ir:" + code
        ood = index >= groups - ood_groups
        split = "ood" if ood else split_group(group, seed)
        subject, other = "Relay-" + code, "Relay-" + _hash([code, "other"])[:12]
        profiles = ("burst", "steady") if not ood else ("surge", "balanced")
        family_query = f"For current guidance on {subject} in the {profiles[0]} profile, what are the retry ceiling and backoff delay?"
        retry, delay = 2 + index % 7, 5 + index % 23
        specs = [(subject, profiles[0], True, retry, delay), (subject, profiles[1], True, retry + 1, delay + 2),
                 (subject, profiles[0], True, retry, None), (subject, profiles[1], True, None, delay + 2),
                 (subject, profiles[0], True, None, None), (other, profiles[0], True, retry, delay),
                 (other, profiles[1], True, retry + 1, delay + 2), (subject, profiles[0], False, retry + 3, delay + 4)]
        documents = [{"id": "d-" + _hash([code, i])[:12], "text": _passage(*spec, family_query, ood)} for i, spec in enumerate(specs)]
        for variant, requested in enumerate(profiles):
            query_id = "q-" + _hash([code, variant])[:16]
            query = (f"For current guidance on {subject} in the {requested} profile, what are the retry ceiling and backoff delay?" if not ood else
                     f"Find the active retry ceiling and backoff delay for {subject}, using its {requested} operating profile.")
            grades = {}
            for doc, (entity, profile, current, attempt, seconds) in zip(documents, specs):
                grades[doc["id"]] = (0 if entity != subject else 1 if profile != requested or not current else
                                     1 + int(attempt is not None) + int(seconds is not None))
            ordered = list(documents)
            random.Random(_hash([code, variant, "retrieval"])).shuffle(ordered)
            queries.append({"id": query_id, "group_id": group, "split": split, "query": query,
                            "documents": ordered, "reference_relevance": grades,
                            "source": VERSION, "external_benchmark": False})
            requests = []
            for kind in ("noul", "score"):
                for doc in ordered:
                    requests.append(("pointwise_" + kind, pointwise(query, doc["text"], kind), [doc["id"]]))
            for ids in ([ordered[0], ordered[1]], [ordered[1], ordered[0]]):
                requests.append(("pairwise", pairwise(query, ids[0]["text"], ids[1]["text"]), [doc["id"] for doc in ids]))
            for subset in (ordered[:4], ordered[4:]):
                requests.append(("setwise", window_request(query, [doc["text"] for doc in subset]), [doc["id"] for doc in subset]))
            for kind in ("choice", "score"):
                requests.append(("listwise_" + kind, window_request(query, [doc["text"] for doc in ordered], kind), [doc["id"] for doc in ordered]))
            for position, (method, request, doc_ids) in enumerate(requests):
                case_id = query_id + ":" + str(position)
                case = {"id": case_id, "group_id": group, "split": split, "query_id": query_id,
                        "method": method, "request": request, "document_ids": doc_ids, "record_ids": [],
                        "source": VERSION, "external_benchmark": False}
                for head, compiled in enumerate(compile_request(**request)):
                    if compiled["kind"] == "score":
                        grade = grades[doc_ids[head]]
                        target = [float(level == grade) for level in range(4)]
                    elif compiled["kind"] == "noul":
                        answer = grades[doc_ids[0]] == 3
                        target = [float(not answer), float(answer)]
                    else:
                        values = [grades[doc_id] for doc_id in doc_ids]
                        winners = sum(value == max(values) for value in values)
                        target = [1.0 / winners if value == max(values) else 0.0 for value in values]
                    record_id = case_id + ":" + compiled["id"]
                    metadata = {"family": "evidence", "template_id": VERSION + (":brief_ood" if ood else ":card_id"),
                                "query_id": query_id, "case_id": case_id, "method": method, "question_id": compiled["id"],
                                "entity_ids": [subject, other], "provenance": {"type": "synthetic", "generator_version": VERSION,
                                    "seed": seed, "group_index": index, "variant": variant, "license": "CC0-1.0", "split_policy": SPLIT_POLICY}}
                    if compiled["kind"] == "score":
                        metadata["score_values"] = [0, 1, 2, 3]
                    records.append({"id": record_id, "group_id": group, "split": split, "source": VERSION,
                                    **{key: compiled[key] for key in ("state", "question", "kind", "options")},
                                    "target": target, "metadata": metadata})
                    case["record_ids"].append(record_id)
                cases.append(case)
    return queries, cases, records


def build_dataset(output_dir, groups=200, seed=42, ood_groups=40):
    output = Path(output_dir)
    if output.is_symlink() or output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Choose a new empty IR directory; existing datasets are not overwritten")
    queries, cases, rows = generate(groups, seed, ood_groups)
    manifest = _write_dataset(rows, output, {"type": "synthetic", "generator_version": VERSION, "groups": groups,
        "ood_groups": ood_groups, "seed": seed, "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
        "source_interface": SOURCE_INTERFACE, "source_code_or_examples_imported": False,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    for name, values in (("queries.jsonl", queries), ("cases.jsonl", cases)):
        path = output / name
        path.write_text("".join(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n" for value in values))
        manifest["files_sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest.update(query_count=len(queries), request_case_count=len(cases),
        request_methods=dict(Counter(case["method"] for case in cases)),
        relevance_counts=dict(Counter(str(grade) for query in queries for grade in query["reference_relevance"].values())),
        training_performed=False, model_inference_performed=False, external_trec_downloaded=False, external_trec_evaluated=False,
        scope="Original finite graded-relevance controls; query families and counterfactuals are correlated. Not a TREC reproduction.",
        target_semantics="Score: four-level hard grade. Noul: both requested current values are supplied. Choice: uniform over equally best passages; not measured model uncertainty or full ranking supervision.")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--groups", type=int, default=200)
    parser.add_argument("--ood-groups", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed, args.ood_groups), indent=2))


if __name__ == "__main__":
    main()
