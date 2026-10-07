"""Independently audit the frozen workflow corpus using visible prose only.

The generator is never imported or executed. AST literals supply the declared
reporting vocabulary, not a label function. This file implements its own policy,
evidence-channel, label and split checks. Standard library only.
"""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


SPLITS = ["train", "calibration", "validation", "test", "ood"]
CARD_SPLITS = ["train"] * 6 + ["calibration", "validation", "test", "ood"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())


def load_contract(path):
    wanted = {"APPROVAL_CARDS", "CMS_CARDS", "APPROVAL_OPTIONS", "CMS_OPTIONS",
              "APPROVAL_QUESTION", "APPROVAL_NOUL", "CMS_QUESTION", "EXCEPTION", "NO_EXCEPTION"}
    constants = {}
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in wanted:
                constants[name] = ast.literal_eval(node.value)
    if set(constants) != wanted:
        raise ValueError("Reporting contract literals are incomplete")
    phrases, approval, cms, family_splits = {}, {}, {}, {}
    for i, (name, operation, first, second) in enumerate(constants["APPROVAL_CARDS"]):
        family = "approval/" + name
        approval[first[0], second[0]] = family
        family_splits[family] = CARD_SPLITS[i]
        for condition, affirmative, negative in (first, second):
            phrases[condition] = (affirmative, negative)
    for i, (name, rules) in enumerate(constants["CMS_CARDS"]):
        family = "cms/" + name
        cms[tuple(sorted((tag, condition) for tag, condition, _, _ in rules))] = family
        family_splits[family] = CARD_SPLITS[i]
        for tag, condition, affirmative, negative in rules:
            phrases[condition] = (affirmative, negative)
    return {**constants, "phrases": phrases, "approval_families": approval,
            "cms_families": cms, "family_splits": family_splits}


def observe(document, condition, contract):
    affirmative, negative = contract["phrases"][condition]
    signatures = set()
    current_yes, current_no = False, False
    for line in document.splitlines():
        channel = "current"
        for prefix in ("Quoted comment", "Archive", "Hypothesis", "Withdrawn announcement"):
            if line.startswith(prefix + ":"):
                channel = prefix
                break
        for name, sentence in (("yes", affirmative), ("no", negative)):
            if sentence not in line:
                continue
            signatures.add((channel, name))
            if channel == "current":
                current_yes |= name == "yes"
                current_no |= name == "no"
            elif channel == "Withdrawn announcement" and name == "yes":
                current_no = True
    truth = 1 if current_yes and not current_no else 0 if current_no and not current_yes else None
    return truth, sorted(signatures)


def interpret(state, question, kind, options, contract):
    if set(state) == {"policy", "request", "operations_log"}:
        domain = "approval"
        policy = state["policy"]
        match = re.search(r"^Covered operation: (.+?)\. Require (.+?) and (.+?)\. The operation may touch at most (\d+) ([^.]+)\.", policy)
        if not match:
            raise ValueError("Cannot parse visible approval scope and requirements")
        operation, first, second, limit, units = match.groups()
        family = contract["approval_families"][first, second]
        a, evidence_a = observe(state["operations_log"], first, contract)
        b, evidence_b = observe(state["operations_log"], second, contract)
        trusted_log = [line for line in state["operations_log"].splitlines()
                       if not line.startswith(("Quoted comment:", "Archive:", "Hypothesis:"))]
        authorization = any(contract["EXCEPTION"] in line for line in trusted_log)
        disputed = any(contract["NO_EXCEPTION"] in line for line in trusted_log)
        request = state["request"].partition(" Applicant comment:")[0]
        negated = request.startswith("Please do not " + operation + ".")
        covered = request.startswith("Please " + operation + ".") or negated
        amounts = re.findall(r"This change touches ([0-9]+) " + re.escape(units) + r"\.", request)
        count = int(amounts[0]) if len(amounts) == 1 else None
        remaining = (1 if authorization and not disputed else a, b)
        if negated:
            outcome = contract["APPROVAL_OPTIONS"][1]
        elif not covered or count is None:
            outcome = contract["APPROVAL_OPTIONS"][2]
        elif count > int(limit) or 0 in remaining:
            outcome = contract["APPROVAL_OPTIONS"][1]
        elif None in remaining:
            outcome = contract["APPROVAL_OPTIONS"][2]
        else:
            outcome = contract["APPROVAL_OPTIONS"][0]
        if kind == "choice" and question == contract["APPROVAL_QUESTION"]:
            answer = outcome
        elif kind == "noul" and question == contract["APPROVAL_NOUL"]:
            answer = "yes" if outcome == contract["APPROVAL_OPTIONS"][0] else "no"
        else:
            raise ValueError("Unknown approval question")
        signature = [family, int(limit), count, covered, negated, evidence_a, evidence_b,
                     authorization, disputed, " Applicant comment:" in state["request"]]
        truth_state = None
    elif set(state) == {"editorial_policy", "article"}:
        domain = "cms"
        rules = []
        for line in state["editorial_policy"].splitlines()[1:]:
            match = re.fullmatch(r'Apply "([^"]+)" only when the article establishes (.+)\.', line)
            if not match:
                raise ValueError("Cannot parse visible tag rule")
            rules.append(match.groups())
        family = contract["cms_families"][tuple(sorted(rules))]
        truth, signature = {}, []
        for tag, condition in sorted(rules):
            value, evidence = observe(state["article"], condition, contract)
            truth[tag] = value
            signature.append([tag, condition, evidence])
        if any(value is None for value in truth.values()):
            outcome = contract["CMS_OPTIONS"][2]
        elif any(value == 1 for value in truth.values()):
            outcome = contract["CMS_OPTIONS"][0]
        else:
            outcome = contract["CMS_OPTIONS"][1]
        if kind == "choice" and question == contract["CMS_QUESTION"]:
            answer = outcome
        elif kind == "noul":
            match = re.fullmatch(r'Is the tag "([^"]+)" justified by the article under the editorial policy\? Answer yes only for affirmative support; unresolved evidence is not sufficient\.', question)
            if not match or match[1] not in truth:
                raise ValueError("Unknown CMS question")
            answer = "yes" if truth[match[1]] == 1 else "no"
        else:
            raise ValueError("Unknown CMS decision question")
        truth_state = digest(truth)
    else:
        raise ValueError("State is not the prose-only workflow contract")
    if not all(isinstance(value, str) for value in state.values()) or answer not in options:
        raise ValueError("Invalid prose/candidate contract")
    return {"target": [float(candidate == answer) for candidate in options], "domain": domain,
            "family": family, "semantic_signature": digest(signature), "truth_state": truth_state,
            "outcome": outcome}


def audit(data_dir, generator):
    data_dir, generator = Path(data_dir), Path(generator)
    manifest_bytes = (data_dir / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    generator_hash = sha(generator.read_bytes())
    if generator_hash != manifest["configuration"]["generator_sha256"]:
        raise ValueError("Generator differs from manifest-bound reporting contract")
    contract = load_contract(generator)
    rows, mismatches, groups, families = 0, 0, {}, {}
    by_split, by_source, outcomes = Counter(), Counter(), Counter()
    semantic_contexts, semantic_groups, truth_states = defaultdict(set), defaultdict(set), set()
    signatures = {}
    file_hashes = {}
    for split in SPLITS:
        filename = split + ".jsonl"
        raw = (data_dir / filename).read_bytes()
        file_hashes[filename] = sha(raw)
        if file_hashes[filename] != manifest["files_sha256"][filename]:
            raise ValueError("Split hash mismatch: " + filename)
        for line in raw.splitlines():
            row = json.loads(line)
            predicted = interpret(row["state"], row["question"], row["kind"], row["options"], contract)
            rows += 1
            mismatches += predicted["target"] != row["target"]
            if row["split"] != split or contract["family_splits"][predicted["family"]] != split:
                raise ValueError("Visible rule card is in the wrong split")
            if row["metadata"]["scenario_family"] != predicted["family"]:
                raise ValueError("Metadata family disagrees with visible policy")
            if row["source"] != "community-workflow-v3/" + predicted["domain"]:
                raise ValueError("Source disagrees with visible task")
            for registry, key in ((groups, row["group_id"]), (families, predicted["family"])):
                if key in registry and registry[key] != split:
                    raise ValueError("Scenario or family crosses splits")
                registry[key] = split
            signature = predicted["semantic_signature"]
            if signature in signatures and signatures[signature] != row["group_id"]:
                raise ValueError("Normalized semantic context repeats in a different scenario")
            signatures[signature] = row["group_id"]
            semantic_contexts[predicted["domain"]].add(signature)
            if row["metadata"]["variant"] == 0:
                semantic_groups[predicted["domain"]].add(signature)
            if predicted["truth_state"] is not None:
                truth_states.add(predicted["truth_state"])
            by_split[split] += 1
            by_source[row["source"]] += 1
            if row["kind"] == "choice":
                outcomes[predicted["domain"] + "/" + predicted["outcome"]] += 1
    if mismatches or rows != manifest["summary"]["records"]:
        raise ValueError(f"Audit failed: {mismatches} mismatches over {rows} rows")
    return {"schema_version": 1, "rows_audited": rows, "target_mismatches": mismatches,
        "manifest_sha256": sha(manifest_bytes), "generator_sha256": generator_hash,
        "audit_script_sha256": sha(Path(__file__).read_bytes()), "files_sha256": file_hashes,
        "split_counts": dict(by_split), "source_counts": dict(by_source),
        "rule_families_inferred_from_visible_policy": len(families), "source_scenarios": len(groups),
        "semantic_scenarios_by_domain": {key: len(value) for key, value in semantic_groups.items()},
        "semantic_contexts_by_domain": {key: len(value) for key, value in semantic_contexts.items()},
        "cms_authoritative_truth_states": len(truth_states), "choice_outcomes": dict(outcomes),
        "independence": "No generator import/execution or oracle call. Vocabulary read as AST literals; labels, evidence channels, family/split checks and semantic signatures independently implemented here.",
        "limits": "Shared authored vocabulary and a finite reporting grammar; not independent human annotation or an unrestricted semantic benchmark."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--generator", type=Path, default=Path(__file__).resolve().parents[2] / "jev/community_workflow_v3.py")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit(args.data_dir, args.generator)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
