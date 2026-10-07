"""Independently audit v2 targets by parsing the visible rule strings.

No generator module, authored AST, metadata oracle or inference is imported.
"""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re


TOKEN = re.compile(r'\s*("(?:\\.|[^"\\])*"|\d+|<=|>=|[()\[\],+<>-]|[A-Za-z_][A-Za-z_0-9]*)')
OPERATORS = {("equals",): "eq", ("differs", "from"): "ne", ("<=",): "le", ("<",): "lt",
             (">=",): "ge", (">",): "gt", ("AND",): "and", ("OR",): "or", ("+",): "add",
             ("-",): "sub", ("times",): "mul", ("contains",): "contains", ("is", "a", "member", "of"): "member"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=8192)
def parse_visible_rule(text):
    tokens, offset = [], 0
    while offset < len(text):
        match = TOKEN.match(text, offset)
        require(match is not None, "Unrecognized visible rule syntax")
        tokens.append(match.group(1))
        offset = match.end()
    position = 0

    def take(expected=None):
        nonlocal position
        require(position < len(tokens), "Truncated rule")
        value = tokens[position]
        position += 1
        require(expected is None or value == expected, "Unexpected rule token")
        return value

    def atom():
        current = take()
        if current == "(":
            result = expression()
            take(")")
            return result
        if current == "NOT":
            return ("not", atom())
        if current == "absolute":
            take("value")
            take("of")
            return ("abs", atom())
        if current == "IF":
            antecedent = atom()
            take("THEN")
            return ("implies", antecedent, atom())
        if current == "[":
            values = []
            while position < len(tokens) and tokens[position] != "]":
                value = atom()
                require(value[0] == "literal", "Only literal members allowed")
                values.append(value[1])
                if tokens[position] != "]":
                    take(",")
            take("]")
            return ("literal", values)
        if current in ("true", "false"):
            return ("literal", current == "true")
        if current.startswith('"'):
            return ("literal", json.loads(current))
        if current.isdigit():
            return ("literal", int(current))
        require(current not in {"THEN", "AND", "OR", ")", "]", ","}, "Invalid operand")
        return ("field", current)

    def expression():
        nonlocal position
        left = atom()
        while position < len(tokens) and tokens[position] not in (")", "]", ",", "THEN"):
            found = next(((sequence, name) for sequence, name in OPERATORS.items()
                          if tuple(tokens[position:position + len(sequence)]) == sequence), None)
            require(found is not None, "Unknown visible binary operator")
            sequence, name = found
            position += len(sequence)
            left = (name, left, atom())
        return left

    result = expression()
    require(position == len(tokens), "Unconsumed visible rule tokens")
    return result


def interpret(node, facts):
    op = node[0]
    if op == "literal":
        return node[1]
    if op == "field":
        return facts.get(node[1])
    arguments = [interpret(child, facts) for child in node[1:]]
    if op == "not":
        return {True: False, False: True, None: None}[arguments[0]]
    if op == "and":
        return False if False in arguments else None if None in arguments else True
    if op == "or":
        return True if True in arguments else None if None in arguments else False
    if op == "implies":
        a, b = arguments
        if a is False or b is True:
            return True
        if a is True and b is False:
            return False
        return None
    if None in arguments:
        return None
    a = arguments[0]
    if op == "abs":
        return abs(a)
    b = arguments[1]
    if op == "eq":
        return a == b
    if op == "ne":
        return a != b
    if op == "le":
        return a <= b
    if op == "lt":
        return a < b
    if op == "ge":
        return a >= b
    if op == "gt":
        return a > b
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    if op == "mul":
        return a * b
    if op == "contains":
        return b in a
    if op == "member":
        return a in b
    raise ValueError("Unsupported rule operation")


def read_candidates(state):
    supplied = state["candidates"]
    if isinstance(supplied, list):
        result = {row["candidate"]: row["facts"] for row in supplied}
        require(len(result) == len(supplied), "Duplicate candidate ID")
        return result
    if isinstance(supplied, dict):
        return supplied
    result = {}
    for line in supplied.splitlines():
        name, facts = line.split("\t", 1)
        require(name not in result, "Duplicate candidate ID")
        result[name] = json.loads(facts)
    return result


def independent_decision(row):
    state = row["state"]
    require(len(state["numbered_requirements"]) == 4, "Expected four visible requirements")
    rules = [parse_visible_rule(rule) for rule in state["numbered_requirements"]]
    candidates = read_candidates(state)
    satisfied = {name: [interpret(rule, facts) for rule in rules] for name, facts in candidates.items()}
    require(all(value is None or type(value) is bool for values in satisfied.values() for value in values), "A requirement is not a truth value")
    eligible = [name for name, values in satisfied.items() if values == [True] * 4]
    ranking = re.fullmatch(r"Among fully supported candidates choose the (smallest|largest) ([a-z_]+); if tied choose the lexicographically smallest candidate ID\. If none is fully supported choose abstain\.", state["selection_rule"])
    require(ranking is not None, "Unrecognized visible selection policy")
    direction, field = ranking.groups()
    require(all(type(facts[field]) in (int, float) and math.isfinite(facts[field]) for facts in candidates.values()), "Invalid visible ranking attribute")
    if eligible:
        ranked = sorted(eligible, key=lambda name: (candidates[name][field] if direction == "smallest" else -candidates[name][field], name))
        winner = ranked[0]
    else:
        winner = "abstain"
    probe = None
    if row["kind"] == "choice":
        expected_label = winner
        require(set(row["options"]) == set(candidates) | {"abstain"}, "Choice coverage differs")
    else:
        match = re.match(r"Candidate ([A-Za-z_0-9]+)\. ", row["question"])
        require(match is not None and match.group(1) in candidates, "Missing or invalid visible probe")
        probe = match.group(1)
        if row["kind"] == "noul":
            require(row["options"] == ["no", "yes"], "Binary options out of order")
            expected_label = "yes" if probe in eligible else "no"
        else:
            require(row["kind"] == "score", "Unexpected task kind")
            count = sum(value is True for value in satisfied[probe])
            expected_label = f"Exactly {count} of the 4 numbered requirements are established."
            require(row["options"] == [f"Exactly {value} of the 4 numbered requirements are established." for value in range(5)], "Ordinal scale differs")
    predicted = [float(option == expected_label) for option in row["options"]]
    require(all(type(value) in (int, float) for value in row["target"]) and row["target"] == predicted, "Independent visible-rule target mismatch")
    return {"winner": winner, "eligible": eligible, "satisfied": satisfied, "facts": candidates,
            "rank_direction": direction, "rank_field": field, "probe": probe}


def audit(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    groups = defaultdict(dict)
    counts, ranks, probes, probe_levels, target_positions, languages, parameters = Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), defaultdict(set)
    files = {}
    for split in ("train", "calibration", "validation", "test", "ood"):
        path = directory / (split + ".jsonl")
        checksum = sha(path.read_bytes())
        require(checksum == manifest["files_sha256"][path.name], "Frozen file checksum differs")
        files[path.name] = checksum
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                result = independent_decision(row)
                require(row["split"] == split, "Split filename differs")
                counts[row["kind"]] += 1
                ranks[result["rank_direction"] + "/" + result["rank_field"]] += 1
                languages[row["metadata"]["language"]] += 1
                parameters[row["state"]["policy_name"]].add(json.dumps(row["state"]["request_parameters"], sort_keys=True))
                if result["probe"] is not None:
                    probes[str(list(result["facts"]).index(result["probe"]))] += 1
                    probe_levels[str(sum(value is True for value in result["satisfied"][result["probe"]]))] += 1
                else:
                    target_positions[str(row["target"].index(1.))] += 1
                    variant = row["metadata"]["provenance"]["variant"]
                    require(variant not in groups[row["group_id"]], "Duplicate choice variant")
                    groups[row["group_id"]][variant] = {"decision": result, "split": split,
                        "common_state": {k: v for k, v in row["state"].items() if k != "candidates"},
                        "declared_change": row["metadata"]["counterfactual"]}
    edges = 0
    for variants in groups.values():
        require(set(variants) == set(range(4)), "Incomplete four-context scenario")
        require(len({row["split"] for row in variants.values()}) == 1, "Counterfactual split leakage")
        require(len({row["decision"]["winner"] for row in variants.values()}) == 4, "Counterfactual winners must all differ")
        require([len(variants[i]["decision"]["eligible"]) for i in range(4)] == [2, 1, 3, 0], "Counterfactual admissibility pattern differs")
        for child, parent in ((1, 0), (2, 0), (3, 1)):
            first, second = variants[parent], variants[child]
            require(first["common_state"] == second["common_state"], "A non-candidate field changed in a counterfactual")
            before, after = first["decision"]["facts"], second["decision"]["facts"]
            require(set(before) == set(after), "Counterfactual changed candidate IDs")
            changes = []
            for name in before:
                require(set(before[name]) == set(after[name]), "Counterfactual changed field schema")
                changes.extend((name, field) for field in before[name] if before[name][field] != after[name][field])
            declared = second["declared_change"]
            require(declared["parent_variant"] == parent and changes == [(declared["candidate"], declared["field"])], "Counterfactual changed more than its one declared fact")
            edges += 1
    return {"schema_version": 1, "status": "passed", "method": "Independent tokenizer/parser of visible rule text, independent three-valued evaluation, visible ranking/probe parsing; no generator module or AST imported.",
            "auditor_sha256": sha(Path(__file__).read_bytes()), "generator_sha256": manifest["configuration"]["generator_sha256"],
            "manifest_sha256": sha((directory / "manifest.json").read_bytes()), "files_sha256": files,
            "rows_verified": sum(counts.values()), "task_kinds": dict(counts), "source_scenarios_verified": len(groups),
            "single_fact_counterfactual_edges_verified": edges, "eligible_candidate_counts_by_variant": [2, 1, 3, 0],
            "ranking_direction_and_field_counts": dict(sorted(ranks.items())), "probe_display_position_counts": dict(sorted(probes.items())),
            "probe_established_requirement_counts": dict(sorted(probe_levels.items())), "choice_target_position_counts": dict(sorted(target_positions.items())),
            "language_counts": dict(languages), "distinct_parameter_configurations_per_policy": {k: len(v) for k, v in sorted(parameters.items())},
            "checks": {"all_targets_agree_with_independent_visible_rule_interpreter": True,
                "all_groups_have_four_different_decisions": True, "counterfactuals_change_one_visible_fact_only": True,
                "parameters_and_rules_fixed_within_each_counterfactual_group": True, "ordinal_and_binary_options_correct": True,
                "all_counterfactual_groups_stay_in_one_split": True}, "model_inference_performed": False, "external_api_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.data_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("status", "rows_verified", "source_scenarios_verified", "single_fact_counterfactual_edges_verified")}))


if __name__ == "__main__":
    main()
