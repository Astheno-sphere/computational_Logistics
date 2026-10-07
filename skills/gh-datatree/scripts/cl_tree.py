#!/usr/bin/env python3
"""A pure-Python model of Grasshopper data trees, for reasoning, teaching and debugging outside Rhino.

A tree is an ordered map path -> branch (list of items). A path is a tuple of ints, written {0;1;2}.
Operations follow Grasshopper's components (Flatten, Graft, Simplify, Trim Tree, Shift Paths,
Path Mapper, Flip Matrix) and its rule for pairing up inputs ("data matching").

Matching rules (repeat the last branch, then the last item) follow Issa, "Essential Algorithms and
Data Structures for Computational Design in Grasshopper", 2nd ed., McNeel 2024, section 3_3
(CC BY-SA 3.0 US; in knowledge-bank/books/). Two details the book leaves open are marked VERIFY and
should be confirmed with a live probe (gh_tree_probe.py) when it matters:
  - which input's paths the outputs inherit when inputs differ,
  - whether Simplify also removes shared indices in the middle of paths.
Runs on CPython 3 and IronPython 2.7 (no f-strings, no type hints).
"""
import re
from collections import OrderedDict


def fmt(path):
    return "{" + ";".join(str(i) for i in path) + "}"


def parse(text):
    """'{0;1;2}' or '0;1;2' -> (0, 1, 2)."""
    t = text.strip().strip("{}").strip()
    return tuple(int(x) for x in t.split(";")) if t else ()


class Tree(object):
    def __init__(self, branches=None):
        self.b = OrderedDict()
        for p, items in (branches.items() if isinstance(branches, dict) else (branches or [])):
            self.b[tuple(p)] = list(items)

    # ---- construction ---------------------------------------------------------------------------
    @classmethod
    def from_list(cls, items, base=(0,)):
        return cls([(tuple(base), items)])

    @classmethod
    def from_nested(cls, nested, base=()):
        """Nested Python lists -> tree, like ghpythonlib.treehelpers.list_to_tree:
        [[a, b], [c]] -> {0}: a b, {1}: c. Leaves at any depth become items of their parent path."""
        t = cls()

        def walk(node, path):
            if isinstance(node, (list, tuple)) and any(isinstance(x, (list, tuple)) for x in node):
                for i, child in enumerate(node):
                    walk(child, path + (i,))
            else:
                t.b.setdefault(path, []).extend(node if isinstance(node, (list, tuple)) else [node])
        walk(nested, tuple(base))
        return t

    def to_nested(self):
        return [list(v) for v in self.b.values()]

    # ---- inspection ------------------------------------------------------------------------------
    @property
    def paths(self):
        return list(self.b.keys())

    def branch_count(self):
        return len(self.b)

    def item_count(self):
        return sum(len(v) for v in self.b.values())

    def depths(self):
        return sorted(set(len(p) for p in self.b))

    def topology(self, limit=12):
        """Like Grasshopper's TopologyDescription: one line per branch with its item count."""
        lines = ["Paths: %d, items: %d, depths: %s" % (self.branch_count(), self.item_count(), self.depths())]
        for i, (p, v) in enumerate(self.b.items()):
            if i == limit:
                lines.append("... %d more branches" % (len(self.b) - limit))
                break
            lines.append("  %s (N = %d)" % (fmt(p), len(v)))
        return "\n".join(lines)

    def __eq__(self, other):
        return isinstance(other, Tree) and list(self.b.items()) == list(other.b.items())

    def __repr__(self):
        return "Tree(%s)" % ", ".join("%s:%r" % (fmt(p), v) for p, v in self.b.items())

    # ---- structure operations ---------------------------------------------------------------------
    def flatten(self, base=(0,)):
        return Tree([(tuple(base), [x for v in self.b.values() for x in v])])

    def graft(self):
        """Every item gets its own branch: {A} item i -> {A;i}. Empty branches stay as they are."""
        out = Tree()
        for p, v in self.b.items():
            if not v:
                out.b[p] = []
            for i, x in enumerate(v):
                out.b[p + (i,)] = [x]
        return out

    def simplify(self):
        """Remove the leading and trailing indices that every path shares, which is how paths pile up
        through a chain of components (Issa, Essential Algorithms and Data Structures, 2nd ed., 3_5_7;
        CC BY-SA 3.0). Each path keeps at least one index. VERIFY: whether Grasshopper also drops
        shared indices in the middle of paths; probe a live tree before relying on that case."""
        ps = self.paths
        if len(ps) < 2:
            return Tree(self.b)
        shortest = min(len(p) for p in ps)
        lead = 0
        while lead < shortest - 1 and len(set(p[lead] for p in ps)) == 1:
            lead += 1
        trail = 0
        while lead + trail < shortest - 1 and len(set(p[len(p) - 1 - trail] for p in ps)) == 1:
            trail += 1
        return self._remap(lambda p: p[lead:len(p) - trail])

    def trim(self, depth=1):
        """Trim Tree: drop the last `depth` indices; branches that collide are merged in order."""
        return self._remap(lambda p: p[:max(0, len(p) - depth)] or (0,))

    def shift(self, offset):
        """Shift Paths: offset < 0 drops indices from the end (merging), offset > 0 from the start."""
        if offset < 0:
            return self.trim(-offset)
        return self._remap(lambda p: p[offset:] or (0,))

    def flip(self):
        """Flip Matrix: item i of branch b -> branch {i}, position b. Ragged input leaves gaps; they
        are filled with None, which Grasshopper shows as <null>."""
        width = max([len(v) for v in self.b.values()] or [0])
        out = Tree()
        for i in range(width):
            out.b[(i,)] = [v[i] if i < len(v) else None for v in self.b.values()]
        return out

    def path_mapper(self, source, target):
        """Path Mapper lexical masks, e.g. '{A;B}(i)' -> '{B;A}', '{A;B}' -> '{A}', '{A}(i)' -> '{i}'.
        Variables are letters; (i) is the item index; integers in the target are literals."""
        src = re.match(r"^\{([^}]*)\}\s*(\((\w+)\))?$", source.replace(" ", ""))
        dst = re.match(r"^\{([^}]*)\}$", target.replace(" ", ""))
        if not src or not dst:
            raise ValueError("masks look like {A;B}(i) -> {B;A}")
        names = [x for x in src.group(1).split(";") if x]
        idx_name = src.group(3)
        out_terms = [x for x in dst.group(1).split(";") if x]
        out = Tree()
        for p, v in self.b.items():
            if len(p) != len(names):
                raise ValueError("path %s does not fit mask %s" % (fmt(p), source))
            env = dict(zip(names, p))

            def target_path(i):
                env[idx_name] = i
                return tuple(int(t) if t.isdigit() else env[t] for t in out_terms)
            if not v and idx_name not in out_terms:
                out.b.setdefault(target_path(0), [])       # keep empty branches when not per-item
            for i, x in enumerate(v):
                out.b.setdefault(target_path(i), []).append(x)
        return out

    def _remap(self, f):
        out = Tree()
        for p, v in self.b.items():
            out.b.setdefault(tuple(f(p)), []).extend(v)
        return out


# ---- how a component pairs its inputs -----------------------------------------------------------
def match(inputs, access=None):
    """Predict the iterations of a component whose inputs are `inputs` (name -> Tree).
    access: name -> 'item' | 'list' | 'tree' (default 'item').
    Grasshopper pairs branches by their ORDER, not by their path names, repeating the last branch of
    shorter inputs (longest list). Within a branch pair, item-access inputs pair item by item, again
    repeating the last item. List-access inputs receive the whole branch per iteration.
    Output paths come from the input with the most branches (ties: the first). VERIFY with a probe.
    Returns dict with branch pairs, iteration count and the master input."""
    access = access or {}
    names = list(inputs)
    trees = [inputs[n] for n in names]
    n_br = max(t.branch_count() for t in trees)
    master = names[[t.branch_count() for t in trees].index(n_br)]
    plan, iterations = [], 0
    for b in range(n_br):
        branches = {}
        for n, t in zip(names, trees):
            ps = t.paths
            p = ps[min(b, len(ps) - 1)]
            branches[n] = (p, t.b[p])
        item_inputs = [n for n in names if access.get(n, "item") == "item"]
        n_it = max([len(branches[n][1]) for n in item_inputs] or [1])
        if any(len(branches[n][1]) == 0 for n in item_inputs):
            n_it = 0                                   # an empty item input skips the branch
        iterations += n_it
        plan.append({"out_path": fmt(inputs[master].paths[b]), "iterations": n_it,
                     "uses": dict((n, fmt(branches[n][0])) for n in names)})
    return {"master": master, "branches": n_br, "iterations": iterations, "plan": plan}


# ---- interlink: logistics plans as trees ---------------------------------------------------------
def routes_to_tree(plan, coords):
    """A vrp-solve plan (one result dict) -> tree {vehicle} of (x, y) points along each route, the
    layout Grasshopper wants for one polyline per vehicle. coords: node id -> (x, y)."""
    t = Tree()
    for v, r in enumerate(plan["routes"]):
        t.b[(v,)] = [coords[n] for n in r["node_path"]]
    return t


if __name__ == "__main__":
    demo = Tree.from_nested([[1, 2, 3], [4, 5]])
    print(demo.topology())
    print("graft:", demo.graft())
    print("flip:", demo.flip())
