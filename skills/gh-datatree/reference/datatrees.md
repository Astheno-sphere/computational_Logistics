# Grasshopper data trees: concepts and recipes

Written for this project in our own words. Authoritative sources (read them there; they are not copied
into this repo because they carry no open license):
- McNeel, "The Why and How of Data Trees" and "Grasshopper data trees and Python" on developer.rhino3d.com
- Grasshopper SDK: `GH_Structure<T>`, `DataTree<T>`, `GH_Path`, `IGH_Param.DataMapping`
- `ghpythonlib.treehelpers` (Giulio Piacentino), shipped with Rhino
- Open code in the knowledge bank: `compas_ghpython/sets.py` (MIT), `ladybug_rhino/grasshopper.py` (AGPL)

## The model
- A **tree** is an ordered list of **branches**. Each branch has a **path** `{a;b;c}` and a list of **items**.
- A path is an address, like folder names. Each component that outputs a list per input item adds one index.
- **Access** decides what a component receives per run: *item* (one item), *list* (a whole branch), *tree*.

## How components pair inputs (data matching)
1. Branches are paired **by position**: first with first, second with second. Path names are ignored.
2. If one input has fewer branches, its **last branch repeats** (longest list).
3. Inside a branch pair, item inputs pair item by item, again repeating the last item.
4. Outputs take their paths from the input with the most branches.

Consequences:
- A single-branch input is applied to every branch of the other input (often what you want).
- A grafted input (N branches of 1) against a flat input (1 branch of N) gives N x N results.
- Two inputs with 3 and 5 branches: branches 4 and 5 reuse branch 3 of the first input, usually a bug.

## Operations
| Operation | Effect | Typical use |
|---|---|---|
| Flatten | all items into `{0}` | forget structure, e.g. before sorting all points |
| Graft | each item into its own branch `{..;i}` | make one-to-many pairing per item |
| Simplify | drop indices every path shares | clean paths before combining two sources |
| Trim Tree (n) | drop last n indices, merging | undo levels added by list-output components |
| Shift Paths (-1 / +1) | drop from end / start | same as trim, or drop a root index |
| Path Mapper | rewrite paths with masks `{A;B}(i) -> {B;A}` | regroup, transpose, graft by rule |
| Flip Matrix | item i of each branch into branch i | rows to columns |

## Logistics recipes (this project)
- **One polyline per vehicle**: vrp-solve plan -> `routes_to_tree` -> tree `{v}` of points ->
  Polyline (item access on a list input). Do not flatten: all routes would join into one curve.
- **Stops per vehicle with attributes**: keep `{v}` for stops and the same `{v}` for labels and arrival
  times; same branch count on every input means one-to-one pairing.
- **Every depot to every client** (all pairs): graft depots, keep clients flat. The N x M result is intended
  here; say so in the definition.
- **After Divide Curve on many routes**: outputs gain a level `{v;0}`; Simplify or Trim before matching
  against `{v}` data.
