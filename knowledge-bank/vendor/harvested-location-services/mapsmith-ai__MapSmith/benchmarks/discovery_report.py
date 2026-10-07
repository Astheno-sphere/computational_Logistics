"""Recompute every discovery number this project publishes, from the data in the repo.

Run it:

    python benchmarks/discovery_report.py

The pages say the numbers can be checked rather than believed. For a while that
was not quite true: the request set was published but the harness that turned it
into percentages was not, so a reader could inspect the queries and had to take
the table on trust. This is that harness.

What it recomputes, all of it from `tests/data/discovery_queries.json` and the
catalog itself, with no network and no model:

* how often the two independent labellers agree with each other — the ceiling;
* how many candidates survive each facet a caller can declare;
* how often our ranking puts the right operation in the top three;
* how often the right operation is in the answer at all.

One published number is NOT reproducible here and the report says so: the 69% for
a model handed the candidates and asked to choose needs that model. Everything
else is arithmetic over files in this repository.

`tests/test_discovery_report.py` runs this and asserts the README agrees with it,
so the two cannot drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from mapsmith import catalog  # noqa: E402

DATA = ROOT / "tests" / "data" / "discovery_queries.json"
NOT_AN_OPERATION = ("none", "ambiguous")


def load() -> list[dict[str, Any]]:
    return json.loads(DATA.read_text(encoding="utf-8"))["queries"]


def accepted_of(query: dict[str, Any]) -> tuple[str, ...]:
    """Every answer a professional would accept for this request.

    The reason this is a set and not a string is the whole finding behind D-062,
    and it came from a working surveyor's answer to one request: *gold
    `transform_by_control_points`, with `ambiguous` defensible as a secondary* —
    a sentence a single field cannot hold.

    Two experienced analysts reach the same result with different tools. Storing
    one answer makes the measurement wrong in both directions: a system that
    picks the other defensible operation is scored as having failed, and the
    figure is then called an accuracy when it is not even an agreement. It is
    the same shape as the `category` defect, where a filter deleted the right
    answer in silence because 4.4 families were plausible per request.

    Order matters: the first is the one the person would choose, and everything
    after it is defensible rather than merely possible. `label_human_also` is
    not "operations that might work" — that list is the catalogue.
    """
    primary = query.get("label_human")
    if not primary:
        model = query.get("label_claude")
        return (model,) if model else ()
    also = [name for name in (query.get("label_human_also") or []) if name != primary]
    return (primary, *also)


def truth_of(query: dict[str, Any]) -> str | None:
    """The label to measure against: the human answer where there is one.

    D-054 is explicit that "there is a right answer" is false for a request two
    experienced analysts would solve with different tools, and that the honest
    name for a figure computed against model labels is *agreement*, not
    accuracy. It also says what would change that: a human who has done the job.

    So where somebody has answered, that answer wins, and every figure below is
    computed against it. Where nobody has, the labeller's own answer stands and
    the figure keeps its old meaning. The two are reported separately by
    `human_coverage` rather than blended into one percentage with two meanings,
    which is the mistake this file has a comment about further down.
    """
    return query.get("label_human") or query.get("label_claude")


def human_coverage(queries: list[dict[str, Any]]) -> dict[str, Any]:
    """How much of the population a person has actually answered.

    Published beside any figure that uses `truth_of`, because a number computed
    against 50 human answers and 105 model ones is neither of the two things a
    reader might take it for, and the only honest fix is to say the mix.
    """
    answered = [q for q in queries if q.get("label_human")]
    overruled = [
        q
        for q in answered
        if q["label_human"] not in (q.get("label_claude"), q.get("label_gemini"))
    ]
    return {
        "requests": len(queries),
        "answered_by_a_person": len(answered),
        "share": round(100 * len(answered) / len(queries)) if queries else 0,
        # The interesting number: requests where BOTH labellers were wrong.
        # Nothing published anywhere has it, because it needs a person.
        "neither_labeller_was_right": len(overruled),
    }


def answerable(queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Requests both labellers placed on an operation that still exists.

    The population every percentage below is computed over, stated once so that
    two numbers in one table can never be over two different denominators —
    which is a mistake this table made for half a day.
    """
    names = {op["name"] for op in catalog.OPERATIONS}
    return [
        q
        for q in queries
        if q.get("label_claude") not in (None, *NOT_AN_OPERATION)
        and q.get("label_gemini") not in (None, *NOT_AN_OPERATION)
        and q["label_claude"] in names
        and q["label_gemini"] in names
    ]


def agreement(queries: list[dict[str, Any]]) -> dict[str, Any]:
    """How often the two labellers name the same operation.

    Reported over two populations on purpose. Over everything, agreeing that a
    request is unanswerable counts as agreement, which is true but easy: it
    inflates the figure with the easy half. Over the answerable requests it is
    the number to compare our own results against, because it is measured on the
    same rows.
    """
    both = [q for q in queries if q.get("label_claude") and q.get("label_gemini")]
    same = sum(1 for q in both if q["label_claude"] == q["label_gemini"])
    ans = answerable(queries)
    same_ans = sum(1 for q in ans if q["label_claude"] == q["label_gemini"])
    return {
        "all": (same, len(both)),
        "answerable": (same_ans, len(ans)),
    }


def facets_for(name: str, declare: tuple[str, ...]) -> dict[str, Any]:
    """What a caller who describes their own situation correctly would pass.

    Taken from the true operation's entry, which is not circular: `input_kind` is
    the kind of data they are holding and `produces` is what they want back. It
    models a caller who says those two things accurately, not one who has been
    told the answer.
    """
    op = next(o for o in catalog.OPERATIONS if o["name"] == name)
    out: dict[str, Any] = {}
    if "input_kind" in declare:
        kinds = [k for k in op["applicability"]["inputs"] if k not in ("dataset", "none")]
        if kinds:
            out["input_kind"] = kinds[0]
    if "produces" in declare:
        out["produces"] = op["produces"]
    if "category" in declare:
        out["category"] = op["category"]
    if "dataset_inputs" in declare:
        out["dataset_inputs"] = op["applicability"]["dataset_inputs"]
    if "geometry" in declare and out.get("input_kind") == "vector":
        declared = op["applicability"].get("geometry")
        if declared:
            # The operation takes only these families, so a caller for whom it
            # is the right answer is holding them.
            out["geometry"] = list(declared)
        else:
            # It takes any geometry, and the request does not say which one the
            # caller holds. So the family that leaves the LARGEST set is the one
            # counted: the candidates and delivered columns are the worst case
            # over what the caller could be holding. The found@3 columns are NOT
            # a worst case: the ranking depends on which family survives, and
            # over the family that ranks worst per request BM25's top three
            # holds the answer 56% of the time, not 61% (review, 2026-09-29).
            # Worst by set size is kept because size is what the threshold and
            # the delivered figure are about.
            without = {k: v for k, v in out.items() if k != "geometry"}
            out["geometry"] = max(
                catalog.GEOMETRY_FAMILIES,
                key=lambda family: (len(catalog.applicable(**without, geometry=family)), family),
            )
    return out


#: The order is the order a caller can answer in, easiest first, and the family
#: comes last because it is the only one that is a guess about our taxonomy
#: rather than a fact about their situation — `search` orders on it and does not
#: filter, so its row is what `applicable` would do if asked.
LEVELS: list[tuple[str, tuple[str, ...]]] = [
    ("nothing — words alone", ()),
    ("the input kind", ("input_kind",)),
    ("+ what it should produce", ("input_kind", "produces")),
    ("+ how many datasets", ("input_kind", "produces", "dataset_inputs")),
    ("+ what geometry it holds", ("input_kind", "produces", "dataset_inputs", "geometry")),
    ("+ which family", ("input_kind", "produces", "dataset_inputs", "geometry", "category")),
]

#: The fullest declaration made only of facts about the caller's situation --
#: every level but the family, which is a guess about our taxonomy. The published
#: headline figures are computed here. Named once, because the index was written
#: as a literal in three test files and every new facet moved it (the geometry
#: level, 2026-09-29, is the one that made this a name).
FULLEST = 4


def ablation(queries: list[dict[str, Any]], engine: str = "lexical") -> list[dict[str, Any]]:
    """One row per facet level: candidates left, ranked in the top three, delivered.

    `engine` is NAMED and never left to the default, and that is a correction.
    The default is `auto`, which is the embedding engine where its model loads
    and BM25 where it does not — so a table computed with it is a table about
    what the machine could download. On 2026-08-29 a CI run met a 429 from
    Hugging Face and recomputed the published row as 28% where the page said
    18%: not a flaky test, a number that had never been reproducible on a
    machine without the model, published under a sentence promising it could be
    checked.

    So the report gives both columns. They differ in a way worth seeing anyway:
    BM25 is the better ranker while the candidate set is large, and the
    embedding engine only overtakes it once the facets have narrowed.

    `delivered` is not an accuracy: below the choose threshold every survivor is
    handed to the caller, so it measures whether the narrowing ever drops the
    answer. That it does not is the property the design rests on.
    """
    rows = []
    for label, declare in LEVELS:
        left, top3, delivered = [], 0, 0
        for q in queries:
            # Every answer a person would accept, not one (D-062). The facets
            # come from the one they would CHOOSE — a request has one shape,
            # whatever tool you reach for — while the hit is counted against the
            # whole set, because a system that answers the other defensible
            # operation has not failed.
            accepted = accepted_of(q)
            if not accepted:
                continue
            truth = accepted[0]
            facets = facets_for(truth, declare)
            left.append(len(catalog.applicable(**facets)))
            answer = catalog.search(q["query"], limit=3, engine=engine, **facets)
            names = [entry["name"] for entry in catalog.entries(answer)]
            top3 += any(name in accepted for name in names[:3])
            delivered += any(name in accepted for name in names)
        n = len(queries)
        rows.append(
            {
                "declared": label,
                "candidates": round(sum(left) / n),
                "found_at_3": round(100 * top3 / n),
                "delivered": round(100 * delivered / n),
            }
        )
    return rows


def main() -> int:
    queries = load()
    ans = answerable(queries)
    agree = agreement(queries)

    print(f"source: {DATA.relative_to(ROOT)}")
    print(f"catalog: {len(catalog.OPERATIONS)} operations\n")

    same_all, n_all = agree["all"]
    same_ans, n_ans = agree["answerable"]
    print("THE CEILING — how often two independent labellers agree with each other")
    print(f"  over all {n_all} requests          {same_all}/{n_all} = {100 * same_all / n_all:.0f}%")
    print(f"  over the {n_ans} answerable ones    {same_ans}/{n_ans} = "
          f"{100 * same_ans / n_ans:.0f}%   <- the one to compare against")
    print("  (the first counts agreeing that a request is unanswerable, which is")
    print("   true and easy; the second is measured on the same rows as the rest)\n")

    print(f"NARROWING AND RANKING — over those {len(ans)} requests")
    lexical = ablation(ans, engine="lexical")
    try:
        vector = ablation(ans, engine="vector")
    except Exception as failure:  # noqa: BLE001 - no model, no column
        vector = None
        print(f"  (the embedding engine could not be loaded: {failure})")
    print(f"  {'what the caller declares':<28}{'candidates':>11}"
          f"{'BM25 @3':>9}{'vector @3':>11}{'delivered':>11}")
    for index, row in enumerate(lexical):
        other = f"{vector[index]['found_at_3']:>10}%" if vector else f"{'—':>11}"
        print(f"  {row['declared']:<28}{row['candidates']:>11}"
              f"{row['found_at_3']:>8}%{other}{row['delivered']:>10}%")
    print("\n  Both rankers, because the shipped default picks between them by whether a")
    print("  model loads — so a single column would be a measurement of the machine.")
    print("  'delivered' is not an accuracy figure: below the choose threshold every")
    print("  survivor is handed over, so it says whether narrowing ever drops the answer.")

    print("\nNOT COMPUTED HERE: how well a model chooses among the candidates needs a")
    print("model. Its choices are in benchmarks/choice_at_scale.json, and")
    print("`python benchmarks/choice_at_scale.py score` recomputes those figures from")
    print("them. Everything above is arithmetic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
