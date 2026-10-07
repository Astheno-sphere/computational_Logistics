"""How well a model chooses among the candidates, as the set grows.

    python benchmarks/choice_at_scale.py score           # the published figures, from the data file
    python benchmarks/choice_at_scale.py build OUT_DIR   # the packs a chooser reads, at this catalog

This is the measurement behind `catalog.CHOOSABLE`, the size up to which
`list_operations` hands over every candidate instead of a ranked shortlist.
Handing over more is only free if the caller still chooses well among more, and
that is a property of the model doing the choosing, not of this catalog.

The design, and why each part is there:

* **Every request at three set sizes, 30, 40 and 50.** Each set starts from what
  the fullest declaration delivers for that request and is filled up with the
  operations the ranker scores closest to the request's words: the hardest
  distractors there are, because they are the ones a larger threshold would
  actually add. A request whose delivered set is already larger keeps it.
* **The same request compared with itself** at 30 and at the larger size. The
  sets are nested, so the only difference is the candidates added, and the
  loss is counted per request, not across buckets holding different requests.
* **Each item carries only its own candidates, in full** (name, category,
  summary, `distinguishes`), in the ranker's order, which is only a hint. So
  the text a chooser has to read grows with the set, which is the cost a larger
  threshold imposes. (A first run, the same day, showed every chooser the whole
  catalogue once and each item's names only: that held the reading constant
  across sizes and measured nothing about it. It also had no set between 35
  and 40. It is not the data behind the threshold.)
* **No chooser sees a request twice**: one chooser per size and quarter of the
  requests. One that had picked from 30 would pick the same from 40.
* **The prompt is `PROMPT` below, verbatim.**

A choice is right when it is one of the operations a person would accept for
the request (`discovery_report.accepted_of`: the first label and any second
defensible one), not the single label the earlier 69% figure was scored against.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))

import discovery_report as dr

DATA = HERE / "choice_at_scale.json"
SIZES = (30, 40, 50)
QUARTERS = 4
SEED = 20260929
FULL = 3  # discovery_report.LEVELS index: the fullest declaration a caller knows

PROMPT = """You are acting as an AI agent that uses a GIS toolkit. For each item in the
file below you must pick the ONE operation that best serves the user's request,
from that item's candidates only.

Read exactly one file: {path}. It is long: read all of it, in several reads
with an offset if your reader stops early, before answering. Do NOT open, list
or search any other file or directory, and do not use the web: the measurement
is only valid if you decide from what is in that file. Each item has an `id`,
the user's `request`, and
`candidates`: the operations you may choose from for that item, each with its
name, category, summary and, where present, `distinguishes` (what separates it
from its neighbours), listed in a ranker's order that is only a hint.

For every item choose the single best candidate for what the user actually
needs. If none of that item's candidates can serve the request, answer "none".
Judge each item on its own.

Reply with ONLY a JSON object mapping every item id to the chosen name, covering
all items, with no other text."""


def _requests() -> list[dict]:
    return dr.answerable(dr.load())


def _entry(op: dict) -> dict:
    e = {"name": op["name"], "category": op["category"], "summary": op["summary"]}
    if op.get("distinguishes"):
        e["distinguishes"] = op["distinguishes"]
    return e


def candidate_sets(query: dict) -> dict[int, list[str]]:
    """The nested sets shown for one request, ordered as a hint."""
    from mapsmith import catalog

    facets = dr.facets_for(dr.accepted_of(query)[0], dr.LEVELS[FULL][1])
    delivered = [op["name"] for op in catalog.applicable(**facets)]
    # The ranker's order over the whole catalogue: the fill comes from the top
    # of it, and every set is shown in it.
    ranked = [e["name"] for e in catalog.entries(
        catalog.search(query["query"], limit=len(catalog.OPERATIONS), engine="lexical")
    )]
    ranked += [op["name"] for op in catalog.OPERATIONS if op["name"] not in ranked]
    sets = {}
    for size in SIZES:
        chosen = set(delivered)
        for name in ranked:
            if len(chosen) >= size:
                break
            chosen.add(name)
        sets[size] = [n for n in ranked if n in chosen]
    return sets


def build(out_dir: Path) -> None:
    from mapsmith import catalog

    out_dir.mkdir(parents=True, exist_ok=True)
    by_name = {op["name"]: op for op in catalog.OPERATIONS}
    queries = _requests()
    order = list(range(len(queries)))
    random.Random(SEED).shuffle(order)
    step = math.ceil(len(order) / QUARTERS)
    quarters = [order[i : i + step] for i in range(0, len(order), step)]
    shown = {}
    for si, size in enumerate(SIZES):
        for qi, quarter in enumerate(quarters):
            # Rotate so that each chooser holds one size per quarter and the
            # three sizes of one request land with three different choosers.
            items = []
            for index in quarter:
                names = candidate_sets(queries[index])[size]
                item_id = f"S{size}-q{index}"
                items.append({
                    "id": item_id,
                    "request": queries[index]["query"],
                    "candidates": [_entry(by_name[n]) for n in names],
                })
                shown[item_id] = {"size": size, "query_index": index, "candidates": names}
            path = out_dir / f"pack_S{size}_{qi}.json"
            path.write_text(json.dumps({"items": items}, ensure_ascii=False, indent=0),
                            encoding="utf-8")
            print(path, len(items))
        del si
    (out_dir / "shown.json").write_text(json.dumps(shown, ensure_ascii=False), encoding="utf-8")


def score() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    queries = _requests()
    right: dict[int, dict[int, bool]] = {}
    shown_size: dict[int, dict[int, int]] = {}
    for item in data["items"]:
        hit = item["chosen"] in dr.accepted_of(queries[item["query_index"]])
        right.setdefault(item["query_index"], {})[item["condition"]] = hit
        shown_size.setdefault(item["query_index"], {})[item["condition"]] = len(item["candidates"])
    by_size = {
        size: round(100 * sum(r[size] for r in right.values()) / len(right), 1) for size in SIZES
    }
    paired = {}
    for size in SIZES[1:]:
        rows = [(r[SIZES[0]], r[size]) for q, r in right.items()
                if shown_size[q][size] > shown_size[q][SIZES[0]]]
        small = sum(a for a, _ in rows)
        large = sum(b for _, b in rows)
        paired[size] = {
            "pairs": len(rows),
            "right_at_30": round(100 * small / len(rows), 1),
            "right_larger": round(100 * large / len(rows), 1),
            "loss_points": round(100 * (small - large) / len(rows), 1),
            "only_at_30": sum(a and not b for a, b in rows),
            "only_larger": sum(b and not a for a, b in rows),
        }
    return {"model": data["model"], "requests": len(right), "right_by_size": by_size,
            "paired": paired}


def main(argv: list[str]) -> int:
    if argv and argv[0] == "build":
        build(Path(argv[1]) if len(argv) > 1 else HERE / "choice_packs")
        return 0
    result = score()
    print(f"model: {result['model']}, {result['requests']} requests")
    for size, pct in result["right_by_size"].items():
        print(f"  right choice with {size} candidates: {pct:5.1f}%")
    for size, row in result["paired"].items():
        print(f"  same request, 30 vs {size}: {row['pairs']} pairs, {row['right_at_30']}% -> "
              f"{row['right_larger']}% (loss {row['loss_points']:+.1f} points; right only at 30: "
              f"{row['only_at_30']}, only at {size}: {row['only_larger']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
