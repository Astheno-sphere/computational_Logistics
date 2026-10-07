"""Every name MapSmith puts in a manifest that the specification does not define.

Run it:

    python benchmarks/manifest_vocabulary.py --write

Writes `docs/manifest-vocabulary.md`. In `benchmarks/` because that is where
this repository keeps the scripts that recompute what it publishes, not because
this is a benchmark.

## Why the page exists

Section 3.6 of the manifest specification makes `verification[].name` a closed
core plus extensions named `x-<producer>:<name>`, so that a consumer can branch
on it. MapSmith obeys that everywhere. But obeying it produces a vocabulary of
its own, and until 2026-09-06 **that vocabulary existed nowhere outside the
source** — a consumer branching on a check name had to read the engines to learn
what names there are, which makes mechanical only half of the thing section 3.6
set out to make mechanical.

## Why it is generated

A hand-written list of sixty names is worth what whoever last remembered to
update it was worth. The names are read from the source with `ast`, including
the ones on branches no test reaches — which is most of the interesting ones,
since a check that only fires on a defect is exactly the check nobody's fixture
triggers.

Two derivations of the same set now exist: this one and the vocabulary sweep in
`tests/test_verify.py`, which polices rather than lists. A test asserts they
agree. Two copies of one rule is how the rule quietly becomes two rules.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "mapsmith"
PAGE = ROOT / "docs" / "manifest-vocabulary.md"

#: The two names that describe the RUN rather than the output, and the reason
#: they are called out separately on the page. Every other check is a
#: proposition about the dataset — `every_point_lies_on_its_line` — while these
#: two answer "did this system verify anything at all?", which is a question a
#: consumer has to be able to ask *before* it knows what else to look for.
ABOUT_THE_RUN = {
    "x-mapsmith:operation_completed": (
        "The engine finished. Recorded as a failed check when it did not, so a "
        "crash leaves a conforming manifest saying what went wrong instead of a "
        "dataset with no record beside it."
    ),
    "x-mapsmith:verification_present": (
        "Nothing looked at the output. It exists because the specification "
        "requires a record for every dataset written and requires at least one "
        "check in it; the absence of verification is itself recorded as a failed "
        "check rather than papered over. No shipped operation emits it, and a "
        "test fails if one starts to."
    ),
}


def check_names() -> dict[str, str]:
    """Every `Check` name written in the source, mapped to the module writing it.

    Literals, module-level constants and module-level tables of literals, which
    is the same reading `tests/test_verify.py` does when it polices the
    vocabulary — deliberately, so that the two can be compared.
    """
    found: dict[str, str] = {}
    for module in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        constants: dict[str, str] = {}
        tables: dict[str, list[str]] = {}
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants[target.id] = node.value.value
            elif isinstance(node.value, ast.Dict):
                values = node.value.values
                if values and all(
                    isinstance(v, ast.Constant) and isinstance(v.value, str)
                    for v in values
                ):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            tables[target.id] = [v.value for v in values]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            callee = node.func
            name = (
                callee.attr if isinstance(callee, ast.Attribute)
                else getattr(callee, "id", None)
            )
            if name != "Check":
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.setdefault(first.value, module.stem)
            elif isinstance(first, ast.Name) and first.id in constants:
                found.setdefault(constants[first.id], module.stem)
            elif isinstance(first, ast.Subscript) and isinstance(first.value, ast.Name):
                for literal in tables.get(first.value.id, []):
                    found.setdefault(literal, module.stem)
    return found


def repair_check_names() -> tuple[dict[str, str], int]:
    """Names written into `repairs[].check`, and how many sites name one at runtime.

    A repair says which check it was made for. When the repair happens to the
    INPUT, before anything is verified, that name belongs to no entry of
    `verification[]` and appears nowhere else in the source -- so a consumer who
    meets it in a manifest has nothing to look it up in. That is the exact
    failure this page exists to prevent, one field over.

    It recognises the ENTRY, not the key, and that is the correction of
    2026-09-09. Looking for any dictionary with a `"check"` key and a constant
    value was wrong in both directions at once: it could not see the entries
    built at runtime (`verify.py` writes `"check": check.name`, a name and not a
    literal) and it would have listed a dictionary of *warnings* written in the
    same shape as though it were a repair. The answer was right by accident,
    there being exactly one name of this kind. A repairs entry says at least
    which check and what was done, so `check` and `action` together are the
    shape, and a warning has neither.

    The dynamic sites are counted rather than resolved: their names come from a
    `Check`, so they are already in the check vocabulary above, and pretending to
    read them from the source would be inventing. The count exists so that a
    caller can tell "no dynamic sites" from "the sweep stopped seeing them".
    """
    found: dict[str, str] = {}
    dynamic = 0
    for module in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = {
                k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }
            if not {"check", "action"} <= keys:
                continue
            for key, value in zip(node.keys, node.values, strict=False):
                if not (isinstance(key, ast.Constant) and key.value == "check"):
                    continue
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    found.setdefault(value.value, module.stem)
                else:
                    dynamic += 1
    return found, dynamic


def page() -> str:
    """The page, from the source. No number in it is typed by hand."""
    sys.path.insert(0, str(ROOT / "src"))
    from mapsmith.grid import DERIVED_ENVIRONMENT, GEOREF_VARIABLES
    from mapsmith.provenance import (
        CONTAINER_EXTENSIONS,
        CRS_EXTENSIONS,
        SPEC_VERSION,
        TRANSFORMATION_EXTENSIONS,
    )

    names = check_names()
    repaired, _dynamic = repair_check_names()
    repairs_only = {
        name: module for name, module in repaired.items() if name not in names
    }
    ours = {n: m for n, m in sorted(names.items()) if n.startswith("x-mapsmith:")}
    core = sorted(n for n in names if not n.startswith("x-mapsmith:"))
    run = {n: m for n, m in ours.items() if n in ABOUT_THE_RUN}
    output = {n: m for n, m in ours.items() if n not in ABOUT_THE_RUN}

    lines = [
        "<!-- generated by benchmarks/manifest_vocabulary.py; do not edit -->",
        "",
        "# The names MapSmith writes into a manifest",
        "",
        f"Against `{SPEC_VERSION}` of the "
        "[manifest specification](https://github.com/mapsmith-ai/manifest-spec).",
        "",
        "Section 3.6 of that specification makes `verification[].name` a closed core",
        "plus extensions spelled `x-<producer>:<name>`, so a consumer can branch on it",
        "rather than parse prose. That works only if the extensions are written down",
        "somewhere: a vocabulary you have to read the engines to learn is half a",
        "vocabulary. This page is generated from the source, including the names on",
        "branches no test reaches — which is most of the interesting ones, because a",
        "check that fires only on a defect is the one no fixture triggers.",
        "",
        "## Two names to know before the others",
        "",
        "Every other check below is a proposition about the **output**. These two are",
        "about the **run**, and a consumer needs them first: they are how you ask",
        "whether this system verified anything at all.",
        "",
        "| name | what it says |",
        "|---|---|",
    ]
    for name in sorted(run):
        lines.append(f"| `{name}` | {ABOUT_THE_RUN[name]} |")

    lines += [
        "",
        f"## Extension check names ({len(output)})",
        "",
        "Each is a proposition about the dataset that was written. A failed one is",
        "recorded, never suppressed — the audit trail has to survive the error it",
        "documents.",
        "",
        "| name | written by |",
        "|---|---|",
    ]
    lines += [f"| `{name}` | `{module}` |" for name, module in sorted(output.items())]

    lines += [
        "",
        f"## Core check names in use ({len(core)})",
        "",
        "Defined by section 3.6, not by MapSmith. Listed so the page is the whole",
        "vocabulary a reader will meet, not only our half of it.",
        "",
        "".join(f"`{name}` · " for name in core).rstrip(" ·"),
        "",
        f"## Names that appear only in `repairs[].check` ({len(repairs_only)})",
        "",
        "A repair entry says which check it was made for. When the repair is made to",
        "the **input**, before anything has been verified, that name belongs to no",
        "entry of `verification[]` — so a reader who meets it in a manifest has",
        "nowhere to look it up. Listed here for that reason, and marked so nobody",
        "reads them as check results.",
        "",
        "| name | written by |",
        "|---|---|",
    ]
    lines += [f"| `{name}` | `{module}` |" for name, module in sorted(repairs_only.items())]

    lines += [
        "",
        f"## Extension fields in `environment` ({len(DERIVED_ENVIRONMENT)})",
        "",
        "Section 3.8 asks for the configuration **as the engine reports it**, and its",
        "examples are `PROJ_NETWORK` and the `GDAL_*` variables. So a",
        "real setting keeps the engine's own spelling and anything MapSmith worked out",
        "carries the prefix. Inside one object the difference is visible without a",
        "lookup: an UPPER_SNAKE key is a setting, a prefixed one is our reading of it.",
        "",
        "These answer the first of the two silent-error classes this product exists",
        "for — *which georeferencing produced these numbers* — so a page that listed",
        "only `crs_decisions` was missing the half that makes its own case.",
        "",
        "| key | what it claims |",
        "|---|---|",
    ]
    lines += [
        f"| `x-mapsmith:{key}` | {why} |"
        for key, why in sorted(DERIVED_ENVIRONMENT.items())
    ]

    lines += [
        "",
        "The settings read straight from the engine, unprefixed because they are its",
        "words and not ours: "
        + "".join(f"`{name}` · " for name in sorted(GEOREF_VARIABLES)).rstrip(" ·")
        + ".",
        "",
        f"## Extension fields in `crs_decisions` ({len(CRS_EXTENSIONS)})",
        "",
        "Section 3.7 recommends the keys of that object, and since draft.7 every other",
        "key MUST be named `x-<producer>:<name>`. These are",
        "MapSmith's, and each one carries the reason it is **not** a synonym of a key",
        "the specification already has — because a prefix cannot answer that question,",
        "and two keys that started as synonyms are why this list exists.",
        "",
        "| key | why it is not a synonym |",
        "|---|---|",
    ]
    lines += [
        f"| `{key}` | {why} |" for key, why in sorted(CRS_EXTENSIONS.items())
    ]

    lines += [
        "",
        f"## Extension fields inside `crs_decisions.transformation` "
        f"({len(TRANSFORMATION_EXTENSIONS)})",
        "",
        "One level further down, and it is the same rule read again: the prefix follows",
        "the container. `transformation` is an object section 3.7 defines — four keys",
        "since `1.0.0-draft.4` — so a key of ours in there has to say so, and so is",
        "`round_trip` since `1.0.0-draft.6`, whose two legs have that same shape. A key",
        "of ours inside an entry of `x-mapsmith:inputs_reprojected` does not need the",
        "prefix, because that whole object is already ours: the difference is the",
        "container, never the datum.",
        "",
        "This paragraph used `x-mapsmith:round_trip` as its example of a container that",
        "is ours until 2026-09-23, when the key entered the specification. The example",
        "changed sides; the rule did not.",
        "",
        "| key | why it is not one section 3.7 already has |",
        "|---|---|",
    ]
    lines += [
        f"| `{key}` | {why} |"
        for key, why in sorted(TRANSFORMATION_EXTENSIONS.items())
    ]

    total = sum(len(keys) for keys in CONTAINER_EXTENSIONS.values())
    lines += [
        "",
        f"## Extension fields in the other containers ({total})",
        "",
        "The three sections above cover `verification[]`, `crs_decisions` and the",
        "`transformation` inside it. They are not every object a manifest has, and",
        "until 2026-09-13 the difference was invisible: this page derived its sections",
        "from three lists, so a key added to a fourth container was documented nowhere",
        "and nothing said so. Two had been shipping that way. The containers are named",
        "here so that adding a fifth is a change to this table rather than a silence.",
        "",
        "| container | key | why it is not one the format already has |",
        "|---|---|---|",
    ]
    lines += [
        f"| `{container}` | `{key}` | {why} |"
        for container, keys in sorted(CONTAINER_EXTENSIONS.items())
        for key, why in sorted(keys.items())
    ]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write docs/manifest-vocabulary.md")
    written = page()
    if parser.parse_args().write:
        PAGE.write_text(written, encoding="utf-8", newline="\n")
        print(f"written: {PAGE}")
    else:
        print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
