"""Take the answers out of the browser and put them in the repository.

The dashboard's fifth panel asks the fifty requests where the two model
labellers disagreed, and D-054 says those are the ones that need somebody who
has done the job: with two labellers agreeing only 70% of the time, "agreement
with model labels" is the honest name for the published figure and *accuracy* is
not. A human answer is the only thing that changes that.

Until now answering did nothing. The answers live in the page's `localStorage`,
there is a button that shows them as JSON, and **nothing in this repository read
that JSON** — `discovery_queries.json` has carried a `label_human` field, empty
in all 155 requests, since the field was added. So the chain existed in two
pieces out of three, and the missing piece was the one that made the work worth
doing. Fifty questions answered into a browser tab are fifty answers somebody
will lose.

    python benchmarks/ingest_answers.py answers.json          # what would change
    python benchmarks/ingest_answers.py answers.json --write   # change it

Matching is on the **text of the request**, never its position: the dashboard
stores answers that way for the same reason, and a file that reordered its rows
would otherwise silently reassign every answer to the wrong request.

An answer that names something that is not an operation is refused rather than
stored. `none` is an answer — it means no operation applies, which is a finding
about the catalogue — and it is spelled the way `discovery_report` already
spells it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "tests" / "data" / "discovery_queries.json"

# Same two lines as `dashboard.py`: `benchmarks/` is a directory of scripts and
# not a package, deliberately — each one runs on its own with no install step.
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))


def question_id(query: str) -> str:
    """The same short id `make_labelling_pack.py` writes. Derived, not assigned."""
    import hashlib

    return "q" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:8]


def _existing_queries() -> list[dict[str, Any]]:
    return json.loads(QUERIES.read_text(encoding="utf-8"))["queries"]


def known_labels() -> set[str]:
    """Every string an answer may be: an operation name, or one of the non-answers."""
    import discovery_report

    from mapsmith import catalog

    return {op["name"] for op in catalog.OPERATIONS} | set(
        discovery_report.NOT_AN_OPERATION
    )


def load_answers(path: Path) -> dict[str, dict[str, Any]]:
    """`{request text: {chose, also, note}}` from the dashboard's export.

    The export carries `query`, `label_human`, and optionally
    `label_human_also` and `label_human_note`. Anything else in it — the model
    labels, the scenario, what actually ran — is the dashboard's own record and
    not ours to copy: this file's job is to add the human answer to a request
    that already exists, not to invent requests.

    **The note is required wherever a second answer is given** (D-062). If two
    operations are both defensible, the reason is the only thing that makes the
    row reusable by somebody who is not the person who answered — and without it
    a reader cannot tell "these two are equally right" from "I could not decide".
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("rows") or raw.get("queries") or []
    # A pack answered elsewhere keys its rows by `id` and calls the fields
    # `label`/`also`/`note`; the dashboard keys by `query` and calls them
    # `label_human*`. Both are accepted, because insisting on one shape would
    # mean asking whoever answered to reformat by hand — which is where the
    # typos come from.
    by_id = {question_id(q["query"]): q["query"] for q in _existing_queries()}
    answers: dict[str, dict[str, Any]] = {}
    for row in rows:
        query = row.get("query") or by_id.get((row.get("id") or "").strip())
        label = row.get("label_human") or row.get("label")
        if not query or not label:
            continue
        also = [
            name
            for name in (row.get("label_human_also") or row.get("also") or [])
            if name and name != label
        ]
        note = (row.get("label_human_note") or row.get("note") or "").strip()
        if also and not note:
            raise SystemExit(
                f"this request has more than one acceptable answer and no note:\n"
                f"  {query[:80]}\n"
                f"  {label}, and also {also}\n"
                "Say why both are defensible. Two answers without a reason cannot "
                "be told apart from an answer nobody could decide."
            )
        given = {"chose": label, "also": also, "note": note}
        if query in answers and answers[query] != given:
            raise SystemExit(
                f"the export answers this request twice, differently:\n"
                f"  {query[:80]}\n"
                f"  {answers[query]} and {given}\n"
                "Decide which one is right in the page and export again."
            )
        answers[query] = given
    return answers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("answers", type=Path, help="the JSON the dashboard exports")
    parser.add_argument(
        "--write", action="store_true", help="write them into discovery_queries.json"
    )
    parser.add_argument(
        "--as",
        dest="labeller",
        default="human",
        help="who answered: 'human' (the default, and the only answers any "
        "published figure is measured against) or a model's name, written to "
        "`label_<name>` instead",
    )
    args = parser.parse_args(argv)
    # A third model's answers are a third model's answers. Writing them into
    # `label_human` would make a published figure claim a provenance it does not
    # have — on a project whose whole subject is provenance — so the field is
    # named after whoever gave it, and only `human` reaches the measurement.
    field = "label_human" if args.labeller == "human" else f"label_{args.labeller}"

    answers = load_answers(args.answers)
    if not answers:
        print("nothing answered in that export.")
        return 0

    allowed = known_labels()
    unknown = sorted(
        {
            name
            for given in answers.values()
            for name in (given["chose"], *given["also"])
            if name not in allowed
        }
    )
    if unknown:
        print(
            f"these answers name nothing the catalogue has: {unknown}\n"
            "An answer is an operation name, or `none` when no operation applies.",
            file=sys.stderr,
        )
        return 2

    data = json.loads(QUERIES.read_text(encoding="utf-8"))
    queries = data["queries"]
    by_text = {q["query"]: q for q in queries}

    absent = sorted(text for text in answers if text not in by_text)
    if absent:
        print(
            f"{len(absent)} answered request(s) are not in discovery_queries.json. "
            "Matching is on the text of the request, so a request whose wording "
            "changed after the page was generated cannot be paired — regenerate "
            "the dashboard and answer again:",
            file=sys.stderr,
        )
        for text in absent[:5]:
            print(f"  {text[:78]}", file=sys.stderr)
        return 2

    added, changed, rephrased, same, multiple = [], [], [], 0, 0
    for text, given in answers.items():
        entry = by_text[text]
        label, also, note = given["chose"], given["also"], given["note"]
        before = entry.get(field)
        before_also = entry.get(f"{field}_also") or []
        before_note = entry.get(f"{field}_note") or ""
        # The NOTE is part of what "the same" means. It was left out, so
        # re-ingesting the same answers with rewritten reasons reported "already
        # the same" and silently replaced all fifty of them — a message
        # asserting nothing had changed while something had, which is the exact
        # class of defect this repository spent a day removing. It happened to
        # be an improvement (the second pass carried the author's own wording
        # instead of a transcription), and that is not a reason to keep a
        # message that cannot tell the two apart.
        if before == label and before_also == also and before_note == note:
            same += 1
        elif before == label and before_also == also:
            rephrased.append(text)
        elif before:
            changed.append((text, before, label))
        else:
            added.append((text, label))
        entry[field] = label
        # Written only when there is something to say, so a reader can tell a
        # request with one clear answer from one where somebody weighed two.
        if also:
            entry[f"{field}_also"] = also
            multiple += 1
        else:
            entry.pop(f"{field}_also", None)
        if note:
            entry[f"{field}_note"] = note
        else:
            entry.pop(f"{field}_note", None)

    print(f"{len(answers)} answer(s) in the export")
    print(
        f"  {len(added)} new, {len(changed)} changed, {len(rephrased)} same answer "
        f"with a different reason, {same} identical"
    )
    if multiple:
        print(
            f"  {multiple} of them accept more than one operation, each with the "
            f"reason why (D-062)"
        )
    for text, label in added[:8]:
        extra = answers[text]["also"]
        tail = f"  (also: {', '.join(extra)})" if extra else ""
        print(f"  + {label:28s} {text[:56]}{tail}")
    for text, before, label in changed:
        # Always listed in full: changing an answer already recorded is a
        # decision, and it should not scroll past.
        print(f"  ~ {before} -> {label}   {text[:60]}")

    others = {"label_claude", "label_gemini"} - {field}
    agreeing = sum(
        1
        for q in queries
        if q.get(field)
        and ({q[field], *(q.get(f"{field}_also") or [])} & {q.get(k) for k in others})
    )
    answered = sum(1 for q in queries if q.get(field))
    if answered:
        who = "human" if field == "label_human" else args.labeller
        print(
            f"\nof {answered} {who} answer(s), {agreeing} agree with at least one "
            f"of the two original labellers ({agreeing / answered:.0%}). The rest "
            f"are requests where both of those were wrong — the number no "
            f"published figure has."
        )
        if field != "label_human":
            print(
                f"Written to `{field}`, NOT `label_human`: no published figure is "
                f"measured against it. It is a third opinion, and unlike the "
                f"original two it was given against today's catalogue."
            )

    if not args.write:
        print("\nnothing written. Pass --write to change discovery_queries.json.")
        return 0

    QUERIES.write_text(
        json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"\nwritten to {QUERIES.relative_to(ROOT)}")
    print(
        "Now: `python benchmarks/discovery_report.py` recomputes every published "
        "figure against the human answers where they exist, and "
        "`python -m pytest tests/test_published_figures.py` says which pages have "
        "gone stale."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
