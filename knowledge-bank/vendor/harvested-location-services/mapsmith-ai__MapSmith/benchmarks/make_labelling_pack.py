"""Write a labelling pack: the catalogue, the requests, and how to answer.

    python benchmarks/make_labelling_pack.py --out ../packs
    python benchmarks/make_labelling_pack.py --out ../packs --only-disagreements

A pack is a self-contained Markdown file somebody — or a model that is not one
of the two already in the file — can read and answer from, with no access to
this repository. It carries the catalogue as it is **today**, which is the point:
the two existing labellers answered on 2026-08-28 against 51 operations, and
there are now 74, so for any request whose right answer is one of the 23 added
since, neither of them could have been right.

Every question gets a short **id**. Answers come back keyed by id rather than by
the text of the request, because the requests run to four hundred characters and
a labeller asked to echo one back will eventually mistype it — and a mistyped
key is an answer silently attached to the wrong question, or to none.

Split into blocks so a pack can be pasted into a chat window without being
truncated at an arbitrary point; `--block` sets how many questions per file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "tests" / "data" / "discovery_queries.json"

sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "benchmarks"))


def question_id(query: str) -> str:
    """A short stable id for a request, derived from its text.

    Derived rather than assigned: a pack regenerated after the file is reordered
    gives every question the same id it had, so an answer sheet written against
    the old pack still applies. An assigned counter would silently renumber.
    """
    return "q" + hashlib.sha256(query.encode("utf-8")).hexdigest()[:8]


def catalogue_table() -> str:
    from mapsmith import catalog

    lines = [
        "| operation | produces | takes | what it is, and what it is not |",
        "|---|---|---|---|",
    ]
    for op in sorted(catalog.OPERATIONS, key=lambda o: o["name"]):
        if op.get("status") != "available":
            continue
        takes = ", ".join(op.get("applicability", {}).get("inputs") or []) or "—"
        # `distinguishes` is the field that says what this is NOT, and it is the
        # one that decides most of these questions. Kept whole rather than
        # truncated: the whole difficulty is telling neighbours apart.
        what = " ".join(
            part.strip()
            for part in (op.get("summary", ""), op.get("distinguishes", ""))
            if part
        )
        lines.append(
            f"| `{op['name']}` | {op.get('produces', '—')} | {takes} | "
            f"{what.replace('|', '/')} |"
        )
    return "\n".join(lines)


INSTRUCTIONS = """\
## What I am asking you to do

Below is the operation catalogue of a GIS tool, and then a list of requests
written the way working people write them — a planner, a surveyor, an analyst,
mid-task, often frustrated. For each request, say which operation you would
reach for.

**Answer with three fields.**

- `label` — the operation you would choose. One name from the catalogue, or
  `none` if no operation in it does the job, or `ambiguous` if the request
  cannot be resolved to an operation at all.
- `also` — a list of the operations that are **also defensible**. Not the ones
  that might work: the catalogue is that list. The ones a competent
  professional could choose instead and not be wrong. Usually empty. `ambiguous`
  may appear here — it is a defensible position about a request, not a failure
  to answer.
- `note` — why. **Required whenever `also` is not empty**, and welcome
  everywhere else. This is the field that makes the answer reusable by somebody
  who is not you: without it, "two answers are equally right" and "I could not
  decide" are the same row.

**What makes this worth doing carefully.** These requests were labelled by two
other models and this is a set where they disagreed, or where nobody has looked.
The interesting cases are the ones where the surface vocabulary points one way
and the workflow points another — "50-foot right-of-way" sounds like a buffer
and may be a coordinate transformation; "show me" sounds like a map and may be
an alignment problem. Say so in the note when you see it: a wrong answer with a
clear reason is more useful here than a right answer with none.

**If the right answer is not in the catalogue**, say `none` and use the note to
say what the operation would have to do. That is a finding about the catalogue,
which is worth as much as a label.

## How to reply

One JSON array, in a single fenced code block, nothing else in it. Use the `id`
of each question — not its text.

```json
[
  {"id": "q1a2b3c4", "label": "transform_by_control_points", "also": ["ambiguous"],
   "note": "the surveyor's workflow is recognisable — reconciling a 1978 plat with today's shots is an alignment between two reference systems. `ambiguous` is defensible because the caller says the control points are missing, which is the input the operation needs."},
  {"id": "q5d6e7f8", "label": "compare_layers", "also": [],
   "note": "the question is what is MISSING between two lists, not what falls inside a boundary."}
]
```

Answer every question in the block. If you are unsure, answer anyway and say so
in the note — an uncertain answer with its reason is data; a skipped question is
not.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="directory to write into")
    parser.add_argument("--block", type=int, default=25, help="questions per file")
    parser.add_argument(
        "--only-disagreements",
        action="store_true",
        help="just the requests the two existing labellers answered differently",
    )
    args = parser.parse_args(argv)

    from mapsmith import catalog

    data = json.loads(QUERIES.read_text(encoding="utf-8"))
    queries = data["queries"]
    if args.only_disagreements:
        queries = [
            q
            for q in queries
            if q.get("label_claude")
            and q.get("label_gemini")
            and q["label_claude"] != q["label_gemini"]
        ]

    args.out.mkdir(parents=True, exist_ok=True)
    blocks = [
        queries[i : i + args.block] for i in range(0, len(queries), args.block)
    ]
    available = sum(1 for op in catalog.OPERATIONS if op.get("status") == "available")

    written = []
    for number, block in enumerate(blocks, start=1):
        parts = [
            f"# Labelling pack {number} of {len(blocks)}",
            "",
            f"{len(block)} requests, out of {len(queries)} in this round. The "
            f"catalogue below is the one in force today: **{available} operations**.",
            "",
            INSTRUCTIONS,
            "",
            "## The catalogue",
            "",
            catalogue_table(),
            "",
            "## The requests",
            "",
        ]
        for q in block:
            parts.append(f"### `{question_id(q['query'])}`")
            parts.append("")
            if q.get("scenario"):
                parts.append(f"*Scenario: {q['scenario']}*")
                parts.append("")
            parts.append("> " + "\n> ".join(textwrap.wrap(q["query"], 92)))
            parts.append("")
        path = args.out / f"labelling-pack-{number:02d}.md"
        path.write_text("\n".join(parts) + "\n", encoding="utf-8")
        written.append((path, len(block)))

    print(f"{len(queries)} request(s), {available} operations in the catalogue")
    for path, count in written:
        print(f"  {path}  ({count} questions, {path.stat().st_size // 1024} KB)")
    print(
        "\nEach file is self-contained: catalogue, instructions and questions. "
        "Answers come back as one JSON array per block, keyed by id.\n"
        "Then: python benchmarks/ingest_answers.py <answers.json> --as <name>"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
