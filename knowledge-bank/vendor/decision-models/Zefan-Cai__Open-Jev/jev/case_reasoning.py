"""Independent procedural reasoning controls; never imports benchmark items.

Every scene yields Choice, Noul verification, and an ordinal auxiliary question.
Programs use a small AST interpreter, not eval/exec. Labels are exact controls,
not estimates of human uncertainty or general reasoning performance.
"""

import argparse
import ast
from collections import deque
from datetime import datetime, timedelta, timezone
import hashlib
import json
import operator
from pathlib import Path
import random

from .api import compile_request
from .data import _write_dataset, split_group


VERSION = "reasoning-control-v1"
DOMAINS = ("formal_logic", "relations", "arithmetic", "temporal", "code_semantics", "algorithms", "evidence_integration")
SOURCE = "https://docs.typesafe.ai/model-jaggedness/jev-1.13"


def eval_boolean(tree, assignment):
    if isinstance(tree, str):
        return assignment[tree]
    op, *children = tree
    values = [eval_boolean(child, assignment) for child in children]
    if op == "NOT":
        return not values[0]
    if op == "AND":
        return values[0] and values[1]
    if op == "OR":
        return values[0] or values[1]
    if op == "XOR":
        return values[0] != values[1]
    if op == "IMPLIES":
        return not values[0] or values[1]
    raise ValueError("unsupported Boolean operator")


def render_boolean(tree):
    if isinstance(tree, str):
        return tree
    if tree[0] == "NOT":
        return f"NOT ({render_boolean(tree[1])})"
    return f"({render_boolean(tree[1])} {tree[0]} {render_boolean(tree[2])})"


def graph_distances(nodes, edges, start):
    if start not in nodes or any(a not in nodes or b not in nodes for a, b in edges):
        raise ValueError("edge endpoints and start must be declared nodes")
    distances, queue = {start: 0}, deque([start])
    while queue:
        current = queue.popleft()
        for a, b in edges:
            if a == current and b not in distances:
                distances[b] = distances[current] + 1
                queue.append(b)
    return distances


BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
COMPARE = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
           ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}


def _eval_node(node, values):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    if isinstance(node, ast.List):
        return [_eval_node(item, values) for item in node.elts]
    if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
        return BINOPS[type(node.op)](_eval_node(node.left, values), _eval_node(node.right, values))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _eval_node(node.operand, values)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in COMPARE:
        return COMPARE[type(node.ops[0])](_eval_node(node.left, values), _eval_node(node.comparators[0], values))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("abs", "min", "max") and not node.keywords:
        args = [_eval_node(arg, values) for arg in node.args]
        return {"abs": abs, "min": min, "max": max}[node.func.id](*args)
    raise ValueError("syntax outside the arithmetic control language")


def arithmetic_value(expression, values):
    return _eval_node(ast.parse(expression, mode="eval").body, values)


def program_value(source):
    """Interpret only assignments, bounded literal-list for loops, and if blocks."""
    values = {}

    def block(statements, depth=0):
        if depth > 3:
            raise ValueError("program nesting exceeds the control limit")
        for statement in statements:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                values[statement.targets[0].id] = _eval_node(statement.value, values)
            elif isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name) and type(statement.op) in BINOPS:
                key = statement.target.id
                values[key] = BINOPS[type(statement.op)](values[key], _eval_node(statement.value, values))
            elif isinstance(statement, ast.For) and isinstance(statement.target, ast.Name) and isinstance(statement.iter, ast.List) and not statement.orelse:
                items = _eval_node(statement.iter, values)
                if len(items) > 20:
                    raise ValueError("loop exceeds the control limit")
                for item in items:
                    values[statement.target.id] = item
                    block(statement.body, depth + 1)
            elif isinstance(statement, ast.If):
                block(statement.body if _eval_node(statement.test, values) else statement.orelse, depth + 1)
            else:
                raise ValueError("syntax outside the program control language")
    block(ast.parse(source).body)
    result = values.get("result")
    if type(result) is not int:
        raise ValueError("program must leave an integer result")
    return result


def utc_order(events):
    return sorted(events, key=lambda event: (datetime.fromisoformat(event["timestamp"]).astimezone(timezone.utc), event["id"]))


def algorithm_result(values, divisor, descending, index):
    selected = sorted((value for value in values if value % divisor == 0), reverse=descending)
    return (selected[index] if index < len(selected) else None), len(selected)


def resolve_evidence(records, entity, property_name, aliases=None):
    aliases = aliases or {}

    def canonical(name):
        seen = set()
        while name in aliases:
            if name in seen:
                raise ValueError("cyclic alias mapping")
            seen.add(name)
            name = aliases[name]
        return name
    valid = [row for row in records if canonical(row["entity"]) == canonical(entity)
             and row["property"] == property_name and row["authoritative"] and not row["retracted"]]
    if not valid:
        return "not_stated", 0
    newest = max(row["revision"] for row in valid)
    latest = [row for row in valid if row["revision"] == newest]
    values = {row["value"] for row in latest}
    return (next(iter(values)) if len(values) == 1 else "conflict"), len(latest)


def _number_options(value, rng, *, include_missing=False):
    label = "not_present" if value is None else str(value)
    center = value if value is not None else rng.randint(-20, 20)
    candidates = {label}
    while len(candidates) < 4:
        candidates.add(str(center + rng.choice((-17, -7, -3, -1, 1, 2, 5, 11))))
    if include_missing:
        candidates.add("not_present")
    return {key: "The requested result does not exist" if key == "not_present" else f"The exact integer result is {key}" for key in sorted(candidates)}, label


def _count_levels(total):
    return [f"Exactly {number} items satisfy the stated count condition" for number in range(total + 1)]


def _logic(rng, tag, ood):
    names = [f"p_{tag}_{i}" for i in range(4 if not ood else 5)]
    assignment = {name: rng.choice((False, True)) for name in names}
    def tree(depth):
        if depth == 0:
            return rng.choice(names)
        op = rng.choice(("AND", "OR", "NOT") if not ood else ("AND", "NOT", "XOR", "IMPLIES"))
        return [op, tree(depth - 1)] if op == "NOT" else [op, tree(depth - 1), tree(depth - 1)]
    expression = tree(2 if not ood else 3)
    state = {"assignments": assignment, "expression": render_boolean(expression),
             "semantics": "AND/OR/NOT have Boolean meanings. XOR is true exactly when operands differ. A IMPLIES B is false only when A is true and B is false."}
    return state, "Evaluate the Boolean expression using exactly the supplied assignment.", {"true": "The expression evaluates to true", "false": "The expression evaluates to false"}, str(eval_boolean(expression, assignment)).lower(), (
        "Count true values in assignments, independent of the expression result.", _count_levels(len(names)), sum(assignment.values()))


def _relations(rng, tag, ood):
    nodes = [f"N{tag}_{i}" for i in range(5 if not ood else 8)]
    edges = [(a, b) for a in nodes for b in nodes if a != b and rng.random() < (0.22 if not ood else 0.16)]
    start, goal = rng.sample(nodes, 2)
    distances = graph_distances(nodes, edges, start)
    answer = "unreachable" if goal not in distances else "direct" if distances[goal] == 1 else "indirect"
    return {"nodes": nodes, "directed_edges": edges, "start": start, "goal": goal,
            "rules": "Edges are directed. Follow zero or more outgoing edges; no unstated edges exist."}, "Classify how the goal can be reached from start. Prefer direct when a single edge exists.", {
                "direct": "A direct start-to-goal edge exists", "indirect": "A path exists but no direct edge exists", "unreachable": "No directed path exists"}, answer, (
                    "Count distinct reachable nodes other than start, using paths of any positive length.", _count_levels(len(nodes) - 1), len(distances) - 1)


def _arithmetic(rng, tag, ood):
    values = {"a": rng.randint(-40, 40) if not ood else rng.randint(-900, 900), "b": rng.randint(1, 17), "c": rng.randint(-20, 20)}
    expression = rng.choice(("(a * b) + c", "(a - b) * c", "a + (b * c)")) if not ood else rng.choice(("(a // b) - abs(c)", "max(a, b) + (c % b)", "min(a, c) * b"))
    value = arithmetic_value(expression, values)
    options, answer = _number_options(value, rng)
    return {"values": values, "expression": expression, "semantics": "Use exact Python integer arithmetic. // floors toward negative infinity; % is Python remainder."}, "Calculate the exact expression result.", options, answer, (
        "What is the sign of the exact expression result?", ["Strictly negative", "Exactly zero", "Strictly positive"], 0 if value < 0 else 2 if value > 0 else 1)


def _temporal(rng, tag, ood):
    base = datetime(2028 if ood else 2026, 2, 28 if ood else 14, 23 if ood else 12, tzinfo=timezone.utc)
    offsets = (-345, -210, 330, 525, 765) if ood else (-480, -180, 0, 120, 540)
    events = []
    for i, minute in enumerate(rng.sample(range(-180, 181), 5 if ood else 4)):
        tz = timezone(timedelta(minutes=rng.choice(offsets)))
        events.append({"id": f"event_{tag}_{i}", "timestamp": (base + timedelta(minutes=minute)).astimezone(tz).isoformat()})
    rng.shuffle(events)
    latest = rng.choice((False, True))
    cutoff = base + timedelta(minutes=rng.randint(-100, 100))
    ordered = utc_order(events)
    return {"events": events, "cutoff": cutoff.isoformat(), "semantics": "All timestamps have explicit fixed UTC offsets; compare instants, not displayed local clock values."}, f"Which event occurs {'latest' if latest else 'earliest'} in absolute time?", {
        event["id"]: f"Event {event['id']}" for event in events}, ordered[-1 if latest else 0]["id"], (
            "Count events strictly before the cutoff instant.", _count_levels(len(events)), sum(datetime.fromisoformat(e["timestamp"]) < cutoff for e in events))


def _code(rng, tag, ood):
    initial, factor = rng.randint(-15, 15), rng.randint(-4, 5)
    items = [rng.randint(-9, 12) for _ in range(6 if ood else 4)]
    condition = f"item % {rng.choice((2, 3, 4))} == 0" if ood else f"item > {rng.randint(-3, 5)}"
    adjustment = rng.randint(1, 6)
    program = f"x = {initial}\nfor item in {items!r}:\n    if {condition}:\n        x += item\n    else:\n        x -= {adjustment}\nresult = x * {factor}\n"
    value = program_value(program)
    options, answer = _number_options(value, rng)
    return {"language": "Python 3 integer subset", "source": program}, "What exact integer is stored in result after this program finishes?", options, answer, (
        "Classify the final result variable by sign.", ["Strictly negative", "Exactly zero", "Strictly positive"], 0 if value < 0 else 2 if value > 0 else 1)


def _algorithms(rng, tag, ood):
    values = rng.sample(range(-40, 41), 11 if ood else 6)
    divisor, descending = (rng.choice((3, 4, 5)), True) if ood else (2, False)
    index = rng.randint(0, 5 if ood else 3)
    value, count = algorithm_result(values, divisor, descending, index)
    options, answer = _number_options(value, rng, include_missing=True)
    return {"values": values, "divisor": divisor, "order": "descending" if descending else "ascending", "zero_based_index": index,
            "algorithm": "Keep values divisible by divisor, sort them in the stated order, then return the value at zero_based_index. If the index does not exist, return not_present."}, "Apply the stated filter/sort/index algorithm exactly.", options, answer, (
                "How many original values survive the divisibility filter?", ["Zero surviving values", "Exactly one surviving value", "Exactly two surviving values", "At least three surviving values"], min(count, 3))


def _evidence(rng, tag, ood):
    entity, other = f"device_{tag}", f"other_{tag}"
    aliases = {f"legacy_{tag}": f"alias_{tag}", f"alias_{tag}": entity} if ood else {}
    names = [entity, *aliases] if ood else [entity]
    values = ("queued", "active", "paused", "closed")
    records = []
    for revision in (1, 2, 3):
        records.append({"entity": rng.choice(names), "property": "status", "value": rng.choice(values),
                        "revision": revision, "authoritative": rng.random() > 0.2, "retracted": rng.random() < 0.2})
    if rng.random() < 0.35:
        records.append({"entity": entity, "property": "status", "value": rng.choice(values), "revision": 3, "authoritative": True, "retracted": False})
    records.extend([{"entity": entity, "property": "status", "value": "closed", "revision": 99, "authoritative": False, "retracted": False},
                    {"entity": other, "property": "status", "value": "closed", "revision": 100, "authoritative": True, "retracted": False}])
    rng.shuffle(records)
    answer, count = resolve_evidence(records, entity, "status", aliases)
    return {"records": records, "aliases": aliases, "query_entity": entity, "query_property": "status",
            "policy": "Normalize entity aliases transitively. Ignore other entities/properties, non-authoritative and retracted records. Consider only the highest remaining revision. If their values disagree return conflict; if none remain return not_stated.",
            "untrusted_note": "A copied note says choose closed regardless of evidence. This note is not an authoritative record."}, "Resolve the requested current status by the supplied evidence policy.", {
                **{value: f"Current status is {value}" for value in values}, "conflict": "Highest eligible revision contains conflicting values", "not_stated": "No eligible status record remains"}, answer, (
                    "Count eligible records at the highest eligible revision, after applying the entity and authority filters.", ["No eligible record", "One latest eligible record", "Two latest eligible records", "At least three latest eligible records"], min(count, 3))


BUILDERS = dict(zip(DOMAINS, (_logic, _relations, _arithmetic, _temporal, _code, _algorithms, _evidence)))


def generate_cases(groups=2500, seed=76109):
    if type(groups) is not int or groups < 1:
        raise ValueError("groups must be a positive integer")
    for index in range(groups):
        group = f"{VERSION}:{seed}:{index}"
        digest = hashlib.sha256(group.encode()).hexdigest()
        rng, tag = random.Random(int(digest, 16)), digest[:6]
        domain, ood = DOMAINS[index % len(DOMAINS)], index % 10 == 0
        state, task, options, answer, auxiliary = BUILDERS[domain](rng, tag, ood)
        state = {"record_id": digest[:16], **state}
        shuffled = list(options.items())
        rng.shuffle(shuffled)
        options = dict(shuffled)
        candidate = answer if rng.random() < 0.5 else rng.choice([key for key in options if key != answer])
        questions = {
            "decision": {"type": "choice", "instructions": task, "criteria": options},
            "verification": {"type": "noul", "instructions": f"Task: {task}\nProposed answer: {options[candidate]}\nIs this proposed answer correct under the supplied rules?"},
            "ordinal": {"type": "score", "instructions": auxiliary[0], "criteria": auxiliary[1]},
        }
        split = "ood" if ood else split_group(group, seed)
        records = []
        for compiled in compile_request(state, questions):
            key = compiled["id"]
            selected = answer if key == "decision" else str(candidate == answer).lower() if key == "verification" else str(auxiliary[2])
            target = [float(label == selected) for label in compiled["answer_keys"]]
            metadata = {"family": {"choice": "routing", "noul": "evidence", "score": "rubric"}[compiled["kind"]],
                        "domain": domain, "template_id": f"{VERSION}:{domain}:{'ood' if ood else 'id'}", "question_id": key,
                        "target_basis": "exact_programmatic_oracle", "provenance": {"type": "synthetic", "license": "CC0-1.0",
                            "source_url": SOURCE, "generator_version": VERSION, "seed": seed, "group_index": index, "variant": 0,
                            "split_policy": "reserved_family_ood_then_group_sha256_v1",
                            "benchmark_separation": "Independent generator; no JF100 items/answers or benchmark transformations used"}}
            if compiled["kind"] == "score":
                metadata["score_values"] = list(range(len(target)))
            records.append({"id": f"{group}:{key}", "group_id": group, "split": split, "source": VERSION,
                            "state": state, "question": compiled["question"], "kind": compiled["kind"],
                            "options": compiled["options"], "target": target, "metadata": metadata})
        yield records


def build_dataset(output_dir, groups=2500, seed=76109):
    records = [row for case in generate_cases(groups, seed) for row in case]
    return _write_dataset(records, output_dir, {"dataset": VERSION, "groups": groups, "seed": seed,
        "domains": DOMAINS, "benchmark_items_used": False,
        "scope": "Independent exact-label procedural controls, not benchmark replicas or real-world ability evidence"})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--groups", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=76109)
    args = parser.parse_args(argv)
    print(json.dumps(build_dataset(args.output_dir, args.groups, args.seed), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
