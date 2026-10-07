---
name: gh-datatree
description: Reason about, build and debug Grasshopper data trees (paths, branches, graft, flatten, simplify, trim, shift, path mapper, flip, data matching). Use when a Grasshopper definition gives too many or too few results, wrong pairing, nulls or deep paths, when writing GhPython/C# that reads or outputs trees, or when turning routes and other nested data into trees for Rhino.
---

# gh-datatree

Data trees are where most Grasshopper definitions go wrong. This skill gives Claude a tested model of
tree semantics, a probe that reads live trees from Rhino, and a diagnoser that names the bug and the fix.

## Files
- `scripts/cl_tree.py`: pure-Python tree model (CPython 3 and IronPython 2.7). `Tree`, `flatten`, `graft`,
  `simplify`, `trim`, `shift`, `flip`, `path_mapper("{A;B}(i)", "{B;A}")`, `match(inputs, access)` to predict
  pairing and iteration counts, `routes_to_tree(plan, coords)` for vrp-solve output.
- `scripts/gh_tree_probe.py`: **run inside Rhino 8**. Read-only dump of selected (or named) components:
  access, hidden input flags (graft/flatten/simplify/reverse), sources, and per branch path, count, nulls, types.
- `scripts/tree_diagnose.py probe.json`: findings with evidence and the smallest usual fix:
  `CROSS_PRODUCT`, `BRANCH_MISMATCH`, `DEPTH_MISMATCH`, `NULLS`, `PARAM_FLAGS`, `DEEP_PATHS`, `RUNTIME`,
  `PREDICTION_DIFFERS`.
- `reference/datatrees.md`: the concepts and recipes in our own words, with links to McNeel's guides.

## Workflow
1. **Probe, don't guess.** With Rhino MCP connected, run `gh_tree_probe.probe(names=[...])` on the suspect
   component and its direct upstream. Without MCP, ask the user to paste a Panel or Param Viewer showing paths.
2. Run `tree_diagnose.py` on the dump. Read errors and warnings before info.
3. Explain with paths: "A has 5 branches {0;0}..{0;4} of 1 item, B has 1 branch {0} of 5 items, so every
   branch of A meets all of B: 25 lines."
4. Propose the **smallest** change (one Graft/Flatten/Simplify toggle or one Path Mapper), and say what the
   output paths will become using `cl_tree`.
5. Re-probe after the change and confirm counts. Never declare a tree fixed without re-probing.

## Rules
- Pairing is by **branch order, not path names**. Same-looking paths do not guarantee correct pairing.
- Prefer Simplify on inputs before structural surgery; prefer Path Mapper over chains of Shift/Trim.
- `match` and `simplify` carry VERIFY notes in the code: where the live probe disagrees, the probe wins.
- The probe and Rhino API calls are not tested outside Rhino; the model and diagnoser are (`tests/`).
