"""Deterministic, auditable data for typed decisions; standard library only.

Run ``python -m jev.data --help`` for dataset generation, import and validation.
Only state, question, kind and options belong in the model input.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Iterable


VERSION = "synthetic-v1"
SPLITS = ("train", "calibration", "validation", "test", "ood")
FAMILIES = ("policy", "routing", "evidence", "rubric")
REQUIRED = {"id", "group_id", "split", "source", "state", "question", "kind",
            "options", "target", "metadata"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def split_group(group_id: str, seed: int = 42, source_train: bool = False) -> str:
    """Assign whole groups, independently of labels and input iteration order."""
    bucket = int(_hash([seed, group_id])[:16], 16) % 10000
    boundaries = ((8000, "train"), (9000, "calibration"), (10000, "validation")) if source_train else (
        (8000, "train"), (8500, "calibration"), (9000, "validation"), (10000, "test"))
    return next(name for upper, name in boundaries if bucket < upper)


def _policy(rng: random.Random, entity: str, ood: bool) -> tuple:
    minimum_income = rng.randint(120, 240) * 1000 if ood else rng.randint(25, 80) * 1000
    minimum_age = rng.randint(18, 25)
    debt_limit = rng.choice([2000, 2500, 3000, 3500, 4000])
    state = {
        "applicant": entity,
        "age_years": minimum_age + rng.choice([-1, 0, 1, 10]),
        "annual_income_usd": minimum_income + rng.choice([-1000, -1, 0, 1, 1000]),
        "debt_ratio_basis_points": debt_limit + rng.choice([-100, -1, 0, 1, 100]),
        "fraud_flag": rng.random() < 0.15,
        "policy": {"minimum_age_years": minimum_age, "minimum_income_usd": minimum_income,
                   "maximum_debt_ratio_basis_points": debt_limit,
                   "rules_in_order": [
                       "If fraud_flag is true OR age_years < minimum_age_years, return ineligible.",
                       "Otherwise, if annual_income_usd >= minimum_income_usd AND debt_ratio_basis_points <= maximum_debt_ratio_basis_points, return eligible.",
                       "Otherwise return manual review."]},
    }
    answer = policy_answer(state)
    return state, ["eligible", "manual review", "ineligible"], answer, "eligible"


def policy_answer(state: dict) -> str:
    policy = state["policy"]
    if state["fraud_flag"] or state["age_years"] < policy["minimum_age_years"]:
        return "ineligible"
    if (state["annual_income_usd"] >= policy["minimum_income_usd"]
            and state["debt_ratio_basis_points"] <= policy["maximum_debt_ratio_basis_points"]):
        return "eligible"
    return "manual review"


def _routing(rng: random.Random, entity: str, ood: bool) -> tuple:
    threshold = rng.randint(1000, 4000) if ood else rng.randint(20, 200)
    state = {
        "ticket": entity,
        "unauthorized_access": rng.random() < 0.2,
        "service_unavailable": rng.random() < 0.5,
        "affected_users": max(0, threshold + rng.choice([-10, -1, 0, 1, 50])),
        "topic": rng.choice(["invoice", "refund", "payment", "how-to", "account", "feature"]),
        "routing_policy": {"incident_user_threshold": threshold,
                           "rules_in_order": [
                               "If unauthorized_access is true, route to security.",
                               "Otherwise, if service_unavailable is true AND affected_users >= incident_user_threshold, route to incident.",
                               "Otherwise, if topic is invoice, refund, or payment, route to billing.",
                               "Otherwise route to general support."]},
    }
    options = ["security", "incident", "billing", "general support"]
    answer = routing_answer(state)
    candidate = answer if rng.random() < 0.5 else rng.choice([x for x in options if x != answer])
    return state, options, answer, candidate


def routing_answer(state: dict) -> str:
    if state["unauthorized_access"]:
        return "security"
    if state["service_unavailable"] and state["affected_users"] >= state["routing_policy"]["incident_user_threshold"]:
        return "incident"
    if state["topic"] in ("invoice", "refund", "payment"):
        return "billing"
    return "general support"


def _evidence(rng: random.Random, entity: str, ood: bool) -> tuple:
    relations = ["connected_to", "assigned_to", "located_in"] if ood else ["member_of", "owns", "visits"]
    truth_values = [True] * 4 + [False] * 4
    rng.shuffle(truth_values)
    facts = [{"subject": entity + "-" + str(i), "relation": rng.choice(relations),
              "object": "Object-" + entity + "-" + str(rng.randrange(4)), "truth": truth_values[i]}
             for i in range(8)]
    answer = rng.choice(["entailed", "contradicted", "unknown"])
    if answer == "unknown":
        fact = rng.choice(facts)
        query = {k: v for k, v in fact.items() if k != "truth"}
        query["relation"] = rng.choice([relation for relation in relations if relation != fact["relation"]])
    else:
        fact = rng.choice([f for f in facts if f["truth"] == (answer == "entailed")])
        query = {k: v for k, v in fact.items() if k != "truth"}
    rng.shuffle(facts)
    state = {"facts": facts, "query": query,
             "evidence_rules": [
                 "Match the complete subject, relation and object exactly.",
                 "A matching fact with truth=true entails the query; truth=false contradicts it.",
                 "If no fact matches, the query is unknown. Missing facts are not false facts."]}
    return state, ["entailed", "contradicted", "unknown"], evidence_answer(state), "entailed"


def evidence_answer(state: dict) -> str:
    for fact in state["facts"]:
        if all(fact[key] == value for key, value in state["query"].items()):
            return "entailed" if fact["truth"] else "contradicted"
    return "unknown"


def _rubric(rng: random.Random, entity: str, ood: bool) -> tuple:
    check_total = 100 if ood else 10
    minimum_checks = rng.randint(check_total // 2, check_total)
    minimum_coverage = rng.randint(2, 6)
    maximum_latency = rng.randint(60, 120) if ood else rng.randint(2, 10)
    desired_points = rng.randrange(5)
    passes = [True] * desired_points + [False] * (4 - desired_points)
    rng.shuffle(passes)
    state = {
        "submission": entity,
        "correct_checks": minimum_checks + rng.choice([0, 1]) if passes[0] else minimum_checks - rng.choice([1, 2]),
        "covered_requirements": minimum_coverage + rng.choice([0, 1]) if passes[1] else minimum_coverage - rng.choice([1, 2]),
        "latency_seconds": maximum_latency - rng.choice([0, 1]) if passes[2] else maximum_latency + rng.choice([1, 2]),
        "safety_violations": 0 if passes[3] else rng.randint(1, 3),
        "rubric": {"minimum_correct_checks": minimum_checks, "minimum_covered_requirements": minimum_coverage,
                   "maximum_latency_seconds": maximum_latency,
                   "instructions": "Add one point for each satisfied condition: correct_checks >= minimum_correct_checks; covered_requirements >= minimum_covered_requirements; latency_seconds <= maximum_latency_seconds; safety_violations == 0. The final score is the sum, from 0 through 4."},
    }
    options = [f"Exactly {points} of the four conditions in the supplied rubric are satisfied."
               for points in range(5)]
    return state, options, options[rubric_answer(state)], None


def rubric_answer(state: dict) -> int:
    rubric = state["rubric"]
    return sum((state["correct_checks"] >= rubric["minimum_correct_checks"],
                state["covered_requirements"] >= rubric["minimum_covered_requirements"],
                state["latency_seconds"] <= rubric["maximum_latency_seconds"],
                state["safety_violations"] == 0))


def synthetic_records(groups: int = 6000, seed: int = 42, ood_groups: int | None = None) -> Iterable[dict]:
    """Yield one record per group, plus a paraphrase for every fifth group."""
    if groups < 1 or (ood_groups is not None and ood_groups < 0):
        raise ValueError("groups must be positive and ood_groups nonnegative")
    if ood_groups is None:
        ood_groups = max(4, math.ceil(groups / 10))
    generators = (_policy, _routing, _evidence, _rubric)
    questions = {
        "choice": ["Which option follows from the stated rules?", "Apply the given rules and select one outcome."],
        "noul": ["Do the stated rules establish the outcome '{candidate}'?", "Under these rules, is the outcome '{candidate}' established?"],
        "score": ["What score does the stated rubric assign?", "Calculate the total rubric score for this submission."],
    }
    ood_questions = {
        "choice": ["Return the decision licensed by this specification.", "Resolve this case according to the supplied specification."],
        "noul": ["Is '{candidate}' warranted by this specification?", "Does applying the specification warrant '{candidate}'?"],
        "score": ["Evaluate all four conditions and identify their point total.", "Determine the ordinal grade by summing the satisfied criteria."],
    }
    for ood, count in ((False, groups), (True, ood_groups)):
        for index in range(count):
            family_index = index % len(FAMILIES)
            family = FAMILIES[family_index]
            group = f"{VERSION}:{seed}:{'ood' if ood else 'id'}:{index}"
            rng = random.Random(int(_hash(group), 16))
            entity = ("Novel-" if ood else "Case-") + _hash([group, "entity"])[:16]
            state, options, answer, candidate = generators[family_index](rng, entity, ood)
            kind = "score" if family == "rubric" else ("choice" if (index // 4) % 2 == 0 else "noul")
            if kind == "noul":
                answer, options = ("yes" if answer == candidate else "no"), ["no", "yes"]
            split = "ood" if ood else split_group(group, seed)
            for variant in range(2 if index % 5 == 0 else 1):
                row_options = list(options)
                if kind == "choice":
                    rng.shuffle(row_options)
                template_id = f"{'ood' if ood else 'id'}:{kind}:{variant}"
                metadata = {"family": family, "entity_ids": [entity], "template_id": template_id,
                            "target_basis": "deterministic_explicit_rules",
                            "provenance": {"type": "synthetic", "generator_version": VERSION,
                                           "seed": seed, "group_index": index, "variant": variant,
                                           "license": "CC0-1.0", "split_policy": "ood_holdout_v1" if ood else "group_sha256_v1"}}
                if kind == "score":
                    metadata["score_values"] = [0, 1, 2, 3, 4]
                yield {"id": f"{group}:v{variant}", "group_id": group, "split": split,
                       "source": f"{VERSION}/{family}", "state": state,
                       "question": (ood_questions if ood else questions)[kind][variant].format(candidate=candidate),
                       "kind": kind, "options": row_options,
                       "target": [float(option == answer) for option in row_options], "metadata": metadata}


def read_jsonl(path: str | Path) -> Iterable[dict]:
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: record must be an object")
            yield row


def read_split_directory(path: str | Path) -> Iterable[dict]:
    """Read only standard split files, checking every row against its filename.

    Auxiliary workflow files are ignored. Schema/probability/leakage checks are
    performed by passing this iterator to ``validate_records``.
    """
    directory = Path(path)
    if not directory.is_dir():
        raise ValueError(f"not a dataset directory: {directory}")
    for split in SPLITS:
        source = directory / f"{split}.jsonl"
        if not source.exists():
            continue
        for row in read_jsonl(source):
            if row.get("split") != split:
                raise ValueError(f"{source}: row {row.get('id', '?')} has split {row.get('split')!r}, expected {split!r}")
            yield row


def input_fingerprint(row: dict) -> str:
    # Option shuffling must not disguise an identical input across splits.
    return _hash({"state": row["state"], "question": " ".join(row["question"].split()),
                  "kind": row["kind"], "options": sorted(row["options"])})


def validate_records(records: Iterable[dict]) -> dict:
    ids, groups, inputs, entity_splits, template_splits = set(), {}, {}, {}, {}
    context_splits = {}
    counts, kinds, families, sources = Counter(), Counter(), Counter(), Counter()
    for line, row in enumerate(records, 1):
        prefix = f"record {line} ({row.get('id', '?')}): "

        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(prefix + message)

        require(set(row) == REQUIRED, f"expected exactly the schema fields {sorted(REQUIRED)}")
        require(all(isinstance(row[k], str) and row[k].strip() for k in ("id", "group_id", "source", "question")), "identifiers, source and question must be nonempty strings")
        require(row["id"] not in ids, "duplicate id")
        require(row["split"] in SPLITS, "unknown split")
        require(row["kind"] in ("choice", "noul", "score"), "unknown kind")
        require(isinstance(row["state"], (dict, str)) and bool(row["state"]), "state must be a nonempty object or string")
        require(isinstance(row["options"], list) and len(row["options"]) >= 2, "options must contain at least two labels")
        require(all(isinstance(x, str) and x.strip() for x in row["options"]), "options must be nonempty strings")
        require(len(set(row["options"])) == len(row["options"]), "duplicate option")
        require(row["kind"] != "noul" or row["options"] == ["no", "yes"], "noul options must be ['no', 'yes']")
        target = row["target"]
        require(isinstance(target, list) and len(target) == len(row["options"]), "target length must match options")
        require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in target), "target probabilities must be finite numbers in [0, 1]")
        require(math.isclose(sum(target), 1.0, rel_tol=0, abs_tol=1e-8), "target must sum to one")
        metadata = row["metadata"]
        require(isinstance(metadata, dict), "metadata must be an object")
        provenance = metadata.get("provenance", {})
        require(isinstance(provenance, dict) and provenance.get("type") in ("synthetic", "import"), "metadata provenance.type must be synthetic or import")
        require(isinstance(provenance.get("license"), str) and bool(provenance["license"]), "provenance license is required")
        require(bool(provenance.get("split_policy")), "provenance split_policy is required")
        if provenance["type"] == "synthetic":
            require(all(k in provenance for k in ("generator_version", "seed", "group_index", "variant")), "incomplete synthetic provenance")
            require(metadata.get("family") in FAMILIES and bool(metadata.get("template_id")), "synthetic family and template_id are required")
        else:
            require(all(provenance.get(k) for k in ("input_sha256", "source_url", "original_id")), "incomplete import provenance")
        if row["kind"] == "score":
            values = metadata.get("score_values")
            require(isinstance(values, list) and len(values) == len(target), "score_values must align with ordered options")
            require(all(type(x) in (int, float) and math.isfinite(x) for x in values), "score_values must be finite numeric values")
            require(all(a < b for a, b in zip(values, values[1:])), "score_values must be strictly increasing")
        group, split = row["group_id"], row["split"]
        require(group not in groups or groups[group] == split, "group appears in multiple splits")
        context = _hash({"state": row["state"], "question": " ".join(row["question"].split()),
                         "kind": row["kind"]})
        require(context not in context_splits or context_splits[context] == split,
                "duplicate input appears across splits (same state/question/kind, regardless of options)")
        fingerprint = input_fingerprint(row)
        target_by_label = {label: probability for label, probability in zip(row["options"], target)}
        if fingerprint in inputs:
            previous_split, previous_target = inputs[fingerprint]
            require(previous_split == split, "duplicate input appears across splits")
            require(previous_target == target_by_label, "identical input has conflicting targets")
        for entity in metadata.get("entity_ids", []):
            if provenance["type"] == "synthetic":
                require(entity not in entity_splits or entity_splits[entity] == split, "synthetic entity appears across splits")
                entity_splits[entity] = split
        template_id = metadata.get("template_id")
        if template_id:
            old = template_splits.setdefault(template_id, set())
            require(not (split == "ood" and old - {"ood"}) and not (split != "ood" and "ood" in old), "OOD template overlaps an in-distribution template")
            old.add(split)
        ids.add(row["id"])
        groups[group] = split
        context_splits[context] = split
        inputs[fingerprint] = split, target_by_label
        counts[split] += 1
        kinds[row["kind"]] += 1
        families[metadata.get("family", "import")] += 1
        sources[row["source"]] += 1
    if not ids:
        raise ValueError("dataset is empty")
    return {"records": len(ids), "groups": len(groups), "unique_inputs": len(inputs),
            "splits": dict(sorted(counts.items())), "kinds": dict(sorted(kinds.items())),
            "families": dict(sorted(families.items())), "sources": dict(sorted(sources.items()))}


def _write_dataset(records: list[dict], output_dir: str | Path, configuration: dict) -> dict:
    summary = validate_records(records)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    checksums = {}
    for split in SPLITS:
        path = output / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for row in records:
                if row["split"] == split:
                    handle.write(_json(row) + "\n")
        checksums[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"schema_version": 1, "configuration": configuration, "summary": summary,
                "files_sha256": checksums,
                "model_input_fields": ["state", "question", "kind", "options"]}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def build_dataset(output_dir: str | Path, groups: int = 6000, seed: int = 42,
                  ood_groups: int | None = None) -> dict:
    return _write_dataset(list(synthetic_records(groups, seed, ood_groups)), output_dir,
                          {"type": "synthetic", "generator_version": VERSION,
                           "groups": groups, "ood_groups": ood_groups if ood_groups is not None else max(4, math.ceil(groups / 10)), "seed": seed})


def import_classification(input_path: str | Path, output_dir: str | Path, *, labels: list[str],
                          question: str, source: str, source_url: str, license_name: str,
                          kind: str = "choice", text_field: str = "text", label_field: str = "label",
                          group_field: str = "group_id", split_field: str = "split", seed: int = 42) -> dict:
    """Convert hard classification labels; preserve declared evaluation splits."""
    if kind not in ("choice", "noul", "score"):
        raise ValueError("kind must be choice, noul or score")
    if len(labels) < 2 or len(set(labels)) != len(labels) or not all(labels):
        raise ValueError("labels must contain at least two distinct nonempty labels")
    if kind == "noul" and len(labels) != 2:
        raise ValueError("noul requires two source labels in no, yes order")
    if not all(x.strip() for x in (question, source, source_url, license_name)):
        raise ValueError("question, source, source_url and license must be specified")
    path = Path(input_path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    options = ["no", "yes"] if kind == "noul" else list(labels)
    records = []
    for index, raw in enumerate(read_jsonl(path)):
        if not isinstance(raw.get(text_field), str) or not raw[text_field].strip():
            raise ValueError(f"input row {index + 1}: {text_field} must be nonempty text")
        label = str(raw.get(label_field))
        if label not in labels:
            raise ValueError(f"input row {index + 1}: unknown label {label!r}")
        state = {"text": raw[text_field]}
        group_key = str(raw[group_field]) if raw.get(group_field) is not None else _hash(" ".join(raw[text_field].split()))
        group_id = f"import:{source}:{_hash(group_key)[:24]}"
        declared_split = raw.get(split_field)
        if declared_split is None:
            split = split_group(group_id, seed)
        elif declared_split == "train":
            split = split_group(group_id, seed, source_train=True)
        elif declared_split in SPLITS:
            split = declared_split
        else:
            raise ValueError(f"input row {index + 1}: unrecognized source split {declared_split!r}")
        row_options = list(options)
        if kind == "choice":
            random.Random(int(_hash([seed, group_id, index]), 16)).shuffle(row_options)
        target_label = options[labels.index(label)]
        provenance = {"type": "import", "input_sha256": digest, "source_url": source_url,
                      "license": license_name, "original_id": str(raw.get("id", index + 1)),
                      "original_split": declared_split, "original_label": label,
                      "split_policy": "preserve_eval_group_sha256_v1", "seed": seed}
        metadata = {"target_basis": "source_hard_label", "provenance": provenance}
        if kind == "score":
            metadata["score_values"] = list(range(len(options)))
        records.append({"id": f"import:{source}:{digest[:12]}:{index}", "group_id": group_id,
                        "split": split, "source": source, "state": state, "question": question,
                        "kind": kind, "options": row_options,
                        "target": [float(option == target_label) for option in row_options], "metadata": metadata})
    return _write_dataset(records, output_dir, {"type": "import", "source": source,
                                               "input_sha256": digest, "labels": labels, "kind": kind, "seed": seed})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="generate deterministic rule-based examples")
    build.add_argument("--output-dir", required=True, type=Path)
    build.add_argument("--groups", type=int, default=6000)
    build.add_argument("--ood-groups", type=int)
    build.add_argument("--seed", type=int, default=42)
    validate = commands.add_parser("validate", help="validate one JSONL or all splits in a directory")
    validate.add_argument("path", type=Path)
    importer = commands.add_parser("import-jsonl", help="convert text/label JSONL, retaining official evaluation splits")
    importer.add_argument("--input", required=True, type=Path)
    importer.add_argument("--output-dir", required=True, type=Path)
    importer.add_argument("--labels", required=True, nargs="+")
    importer.add_argument("--question", required=True)
    importer.add_argument("--kind", choices=("choice", "noul", "score"), default="choice")
    importer.add_argument("--source", required=True)
    importer.add_argument("--source-url", required=True)
    importer.add_argument("--license", required=True, dest="license_name")
    importer.add_argument("--text-field", default="text")
    importer.add_argument("--label-field", default="label")
    importer.add_argument("--group-field", default="group_id")
    importer.add_argument("--split-field", default="split")
    importer.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_dataset(args.output_dir, args.groups, args.seed, args.ood_groups)
        elif args.command == "validate":
            records = read_split_directory(args.path) if args.path.is_dir() else read_jsonl(args.path)
            result = validate_records(records)
        else:
            values = vars(args).copy()
            values.pop("command")
            values["input_path"] = values.pop("input")
            result = import_classification(**values)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
