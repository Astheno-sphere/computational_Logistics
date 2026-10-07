# -*- coding: utf-8 -*-
"""Dump the live data-tree structure of Grasshopper components, for tree_diagnose.py.

RUN INSIDE RHINO 8 with Grasshopper open (Script Editor, _RunPythonScript, or a Rhino MCP
"execute python" tool). IronPython 2.7 and CPython 3 compatible. Read-only: changes nothing.

    probe()                         -> selected components, or all if none are selected
    probe(names=["Line", "Divide"]) -> components whose nickname or name matches
    probe(path=r"C:/tmp/probe.json")-> also writes the JSON there

For every input and output parameter it records: access (item/list/tree), the input-side flags that
the canvas only shows as tiny icons (graft/flatten = DataMapping, simplify, reverse), upstream
sources, and per branch: path, item count, nulls, value types and a short sample.
NOT TESTED OUTSIDE RHINO: Grasshopper API names are from the Grasshopper SDK (GH_Structure,
IGH_Param.VolatileData / DataMapping / Simplify / Reverse, GH_RuntimeMessageLevel).
"""
import json

import Grasshopper as gh


def _doc():
    canvas = gh.Instances.ActiveCanvas
    if canvas is None or canvas.Document is None:
        raise RuntimeError("No Grasshopper document is open")
    return canvas.Document


def _owner_name(param):
    top = param.Attributes.GetTopLevel.DocObject
    if top is param:
        return param.NickName or param.Name
    return "%s.%s" % (top.NickName or top.Name, param.NickName or param.Name)


def _item_type(x):
    if x is None:
        return "null"
    return getattr(x, "TypeName", None) or type(x).__name__


def _param(p, sample=3):
    vd = p.VolatileData
    branches = []
    for path in vd.Paths:
        items = list(vd.get_Branch(path))
        branches.append({
            "path": str(path),
            "n": len(items),
            "nulls": sum(1 for x in items if x is None),
            "types": sorted(set(_item_type(x) for x in items)),
            "sample": [str(x)[:60] for x in items[:sample]],
        })
    return {
        "name": p.NickName or p.Name,
        "access": str(p.Access).lower(),            # item | list | tree
        "mapping": str(p.DataMapping).lower(),       # none | flatten | graft
        "simplify": bool(p.Simplify),
        "reverse": bool(p.Reverse),
        "sources": [_owner_name(s) for s in p.Sources],
        "branches": branches,
    }


def _messages(obj):
    out = []
    for level in ("Warning", "Error"):
        lv = getattr(gh.Kernel.GH_RuntimeMessageLevel, level)
        for m in obj.RuntimeMessages(lv):
            out.append("%s: %s" % (level.lower(), m))
    return out


def probe(names=None, path=None):
    doc = _doc()
    objs = list(doc.Objects)
    chosen = [o for o in objs if o.Attributes.Selected] if not names else \
             [o for o in objs if (o.NickName in names or o.Name in names)]
    if not chosen:
        chosen = objs
    result = []
    for o in chosen:
        if isinstance(o, gh.Kernel.IGH_Component):
            result.append({
                "component": o.NickName or o.Name, "type": o.Name, "guid": str(o.InstanceGuid),
                "messages": _messages(o),
                "inputs": [_param(p) for p in o.Params.Input],
                "outputs": [_param(p) for p in o.Params.Output],
            })
        elif isinstance(o, gh.Kernel.IGH_Param):
            result.append({"component": o.NickName or o.Name, "type": "param:" + o.Name,
                           "guid": str(o.InstanceGuid), "messages": _messages(o),
                           "inputs": [], "outputs": [_param(o)]})
    text = json.dumps(result, indent=1)
    if path:
        with open(path, "w") as fh:
            fh.write(text)
    return text


if __name__ == "__main__":
    print(probe())
