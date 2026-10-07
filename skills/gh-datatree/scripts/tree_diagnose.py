#!/usr/bin/env python3
"""Diagnose Grasshopper data-tree problems from a gh_tree_probe.py dump.

    python tree_diagnose.py probe.json            # Markdown report
    python tree_diagnose.py probe.json --json     # machine-readable findings

Each finding has a code, severity, the evidence (paths and counts) and the smallest usual fix.
The predictions use cl_tree.match; where the live output disagrees with the prediction, that is
reported too, because then the component uses list/tree access or the model needs checking.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cl_tree import Tree, fmt, match, parse  # noqa: E402


def to_tree(param):
    """Probe branches -> Tree with placeholder items (counts are what matter for structure)."""
    return Tree([(parse(b["path"]), [None if i < b.get("nulls", 0) else i for i in range(b["n"])])
                 for b in param["branches"]])


def effective(param, tree):
    """Apply the input-side flags in Grasshopper's order: mapping (flatten/graft), then simplify, reverse."""
    if param.get("mapping") == "flatten":
        tree = tree.flatten()
    elif param.get("mapping") == "graft":
        tree = tree.graft()
    if param.get("simplify"):
        tree = tree.simplify()
    return tree


def diagnose_component(c):
    f = []
    add = lambda code, sev, msg, fix: f.append({"component": c["component"], "code": code, "severity": sev,
                                                 "message": msg, "fix": fix})
    for m in c.get("messages", []):
        add("RUNTIME", "error" if m.startswith("error") else "warning", m,
            "Fix the upstream input named in the message first; tree advice below may be a consequence.")
    ins = [p for p in c.get("inputs", []) if p["branches"]]
    trees = {p["name"]: effective(p, to_tree(p)) for p in ins}
    for p in c.get("inputs", []):
        flags = [x for x in (p.get("mapping") if p.get("mapping") not in (None, "none") else None,
                             "simplify" if p.get("simplify") else None, "reverse" if p.get("reverse") else None) if x]
        if flags:
            add("PARAM_FLAGS", "info", "Input '%s' has hidden flags: %s." % (p["name"], ", ".join(flags)),
                "These are the small icons on the input. Make sure they are intended; they change pairing.")
        nulls = sum(b.get("nulls", 0) for b in p["branches"])
        empty = sum(1 for b in p["branches"] if b["n"] == 0)
        if nulls or empty:
            add("NULLS", "warning", "Input '%s' has %d null items and %d empty branches (from %s)."
                % (p["name"], nulls, empty, ", ".join(p.get("sources") or ["nothing"])),
                "An upstream component failed for those items. Probe the source; use Clean Tree only after.")
    if len(trees) < 2:
        return f
    access = dict((p["name"], p.get("access", "item")) for p in ins)
    item_in = [n for n in trees if access.get(n, "item") == "item"]
    counts = dict((n, trees[n].branch_count()) for n in trees)
    multi = [n for n in item_in if counts[n] > 1]
    if len(set(counts[n] for n in multi)) > 1:
        add("BRANCH_MISMATCH", "warning",
            "Branch counts differ: %s. Branches pair by order; the shorter inputs repeat their last branch."
            % ", ".join("%s=%d" % (n, counts[n]) for n in multi),
            "Make the structures correspond (same number of branches), e.g. Graft/Flatten one side, or "
            "regroup with Path Mapper. If one side should apply to all, give it a single branch.")
    depths = dict((n, trees[n].depths()) for n in multi)
    if len(set(tuple(d) for d in depths.values())) > 1:
        add("DEPTH_MISMATCH", "info",
            "Path depths differ: %s. Grasshopper ignores path names when pairing, so this is only a hint "
            "that the inputs come from differently nested sources." % ", ".join("%s=%s" % kv for kv in depths.items()),
            "Simplify both inputs (right-click > Simplify) so paths read the same, then check pairing.")
    pred = match(trees, access)
    biggest = max(t.item_count() for t in trees.values())
    if pred["iterations"] > 4 * max(1, biggest):
        add("CROSS_PRODUCT", "warning",
            "Predicted %d iterations from inputs of at most %d items: an input is probably grafted against "
            "a flat list (every branch meets every item)." % (pred["iterations"], biggest),
            "If you wanted one-to-one pairs, remove the Graft (or Flatten the grafted side). If you wanted "
            "all combinations, this is right; use Cross Reference to make it explicit.")
    for t in trees.values():
        if any(d >= 4 for d in t.depths()):
            add("DEEP_PATHS", "info", "Paths are %d levels deep, e.g. %s." % (max(t.depths()), ", ".join(fmt(p) for p in t.paths[:2])),
                "Each component adds a level when it outputs lists. Simplify or Shift Paths (-1) before joining "
                "with other data, or use Trim Tree.")
            break
    for out in c.get("outputs", []):
        if out["branches"] and len(out["branches"]) != pred["branches"]:
            add("PREDICTION_DIFFERS", "info",
                "Output '%s' has %d branches; item-access pairing predicts %d. The component may use "
                "list/tree access or add its own levels." % (out["name"], len(out["branches"]), pred["branches"]),
                "Read the output paths in the probe; adjust downstream with Trim Tree or Path Mapper.")
    return f


def diagnose(dump):
    return [x for c in dump for x in diagnose_component(c)]


def report(findings):
    if not findings:
        return "No data-tree problems found in the probed components."
    order = {"error": 0, "warning": 1, "info": 2}
    lines = ["# Data-tree diagnosis", ""]
    for x in sorted(findings, key=lambda x: (order[x["severity"]], x["component"])):
        lines += ["- **%s** `%s` (%s): %s" % (x["severity"].upper(), x["code"], x["component"], x["message"]),
                  "  - Fix: %s" % x["fix"]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("probe")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    with open(a.probe) as fh:
        findings = diagnose(json.load(fh))
    print(json.dumps(findings, indent=1) if a.json else report(findings))


if __name__ == "__main__":
    main()
