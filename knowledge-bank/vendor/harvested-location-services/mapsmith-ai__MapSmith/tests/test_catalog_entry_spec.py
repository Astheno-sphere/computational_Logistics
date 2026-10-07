"""Every catalog entry validates against the published specification.

`docs/catalog-entry-spec.md` says how an operation must be described so an agent
can find it among thousands, and `schema/operation.schema.json` is the normative
form of that. A specification nothing enforces is a document, so this is what
makes it a contract: the entries in this repository are its first conformance
corpus, and a new one cannot land without meeting it.

The schema is deliberately strict about `additionalProperties`. A field nobody
reads is worse than a missing one in a catalogue: it looks like metadata, it
costs the author time to write, and no filter or ranker ever sees it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapsmith import catalog

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "operation.schema.json"
SPEC_PATH = ROOT / "docs" / "catalog-entry-spec.md"


@pytest.fixture(scope="module")
def validator():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(schema)


@pytest.mark.parametrize(
    "op", catalog.OPERATIONS, ids=lambda op: op["name"]
)
def test_entry_matches_the_published_schema(op, validator):
    errors = sorted(validator.iter_errors(op), key=lambda e: list(e.path))
    assert not errors, "\n".join(
        f"{op['name']}: {'.'.join(str(p) for p in e.path) or '(root)'} — {e.message}"
        for e in errors
    )


def test_the_schema_and_the_prose_describe_the_same_fields():
    """A spec whose schema and prose disagree teaches two different things.

    Both are hand-written and they drift; this is the cheapest guard that
    notices. It checks presence, not wording: every property the schema defines
    has to be discussed somewhere in the document.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    prose = SPEC_PATH.read_text(encoding="utf-8")
    undocumented = [
        name
        for name in schema["properties"]
        if f"`{name}`" not in prose and name not in ("name", "status", "tool", "workload")
    ]
    assert not undocumented, (
        f"the schema defines {undocumented} and the specification never mentions them; "
        "a field an author cannot read about is a field they will fill in wrongly"
    )


def test_the_spec_states_the_measurement_that_justifies_the_facets():
    """The argument, not just the rule.

    Every field in this specification is required because something was
    measured. If the numbers go, what is left is somebody's taste — and taste is
    exactly what a spec is supposed to replace.
    """
    prose = SPEC_PATH.read_text(encoding="utf-8")
    # These moved once, on 2026-08-28, when the numbers turned out to have been
    # measured on queries we wrote ourselves. The list is the current measurement,
    # and it includes the ceiling: a spec that states an accuracy without stating
    # what the accuracy is bounded by invites tuning past the point of meaning.
    for number in ("118", "48%", "69%", "68%", "4.4"):
        assert number in prose, (
            f"the specification no longer states {number}, so the facets it requires "
            "have lost the measurement that justifies them"
        )
    assert "10/20 to 10/20" in prose, (
        "the null result on `phrasings` has been dropped from the spec. It is the "
        "part that makes the other numbers believable: a document that only reports "
        "what worked is an advertisement."
    )
    # And the two limits. Dropping either would turn a measurement into a claim.
    assert "not accuracy" in prose or "and not accuracy" in prose, (
        "the spec no longer says these are agreement figures rather than accuracy, "
        "which is the difference between a measured number and an advertised one"
    )
    assert "MUST NOT use `category` to exclude" in prose, (
        "the normative rule that the family orders instead of filtering is gone. It "
        "is the one rule here that prevents a silent wrong answer."
    )


def test_recommended_fields_are_recommended_and_not_quietly_required():
    """`distinguishes` is RECOMMENDED, and the schema must agree with the prose.

    It earns its place inside a crowded family and costs nothing in an empty one,
    so requiring it everywhere would be cargo cult. If it is ever promoted to
    required, this test is where the decision gets made explicitly.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "distinguishes" in schema["properties"]
    assert "distinguishes" not in schema["required"]
    assert "RECOMMENDED" in schema["properties"]["distinguishes"]["description"]
