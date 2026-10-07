"""Shared fixtures, and one rule about the embedding engine.

The rule exists because of a build that went red on 2026-08-29 for a reason that
had nothing to do with this repository: Hugging Face answered 429 to the model
download and six tests failed, four of them because the vector engine could not
be had and two because the numbers they check are produced by whichever engine
was available.

`catalog.search` is built to survive that — it falls back to BM25 and says so in
the `engine` field — so the product behaved correctly and only the tests did not.
A test that asserts what the vector engine does must skip when the vector engine
cannot be had, exactly as it already skips when `model2vec` is not installed.
Someone else's rate limit is not a defect in our code, and a suite that reports
it as one teaches people to ignore red builds.
"""

from __future__ import annotations

import re

import pytest


@pytest.fixture(scope="module")
def vector_engine():
    """The embedding engine, or a skip with the reason.

    Covers both ways it can be absent: the package missing (an install without
    it) and the model not loading (no network, a cold cache, a proxy, a rate
    limit, a workspace refusing the fetch by design since 0.3.0).
    """
    pytest.importorskip("model2vec")
    from mapsmith import retrieval

    try:
        retrieval.embed(["a warm-up query, so the failure happens here"])
    except Exception as failure:  # noqa: BLE001 - any failure to load is a skip
        pytest.skip(f"the embedding model could not be loaded: {failure}")
    return retrieval

def spec_checkout():
    """The published specification files the vendored copies are compared with.

    Published means: at the tag of the version this code declares,
    `v<SPEC_VERSION>`. `MAPSMITH_SPEC_CHECKOUT` names a directory laid out like
    the manifest-spec repository, which CI fills from that tag. Without it, the
    three files are read from a `manifest-spec` checkout beside this one AT THAT
    TAG (`git show`), not from its working tree: the spec's main moves ahead of
    the last draft -- a fix to its reference code, say -- and a comparison with
    main would fail here while CI, reading the tag, passed. Until 2026-10-05 the
    local test read the working tree.

    Neither available is a skip on a developer's disk and a FAILURE where
    `MAPSMITH_REQUIRE_SPEC_CHECKOUT` is set. Until 2026-10-05 the two drift
    tests only skipped, and CI has no sibling checkout, so they had never run
    there -- a guard that could not fail where it mattered.
    """
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    from mapsmith.provenance import SPEC_VERSION

    named = os.environ.get("MAPSMITH_SPEC_CHECKOUT")
    if named and Path(named).is_dir():
        return Path(named)
    sibling = Path(__file__).resolve().parents[2] / "manifest-spec"
    where = f"MAPSMITH_SPEC_CHECKOUT={named}" if named else f"a manifest-spec checkout at {sibling}"
    if not named and (sibling / ".git").exists():
        tag = f"v{SPEC_VERSION}"
        dest = Path(tempfile.mkdtemp(prefix="manifest-spec-"))
        for rel in ("schema/manifest-v1.schema.json", "validator/validate.py",
                    "examples/multi_file_digest.py"):
            shown = subprocess.run(
                ["git", "-C", str(sibling), "show", f"{tag}:{rel}"],
                capture_output=True, check=False,
            )
            if shown.returncode != 0:
                where = f"tag {tag} in {sibling} ({shown.stderr.decode(errors='replace').strip()})"
                break
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_bytes(shown.stdout)
        else:
            return dest
    if os.environ.get("MAPSMITH_REQUIRE_SPEC_CHECKOUT"):
        pytest.fail(f"the published specification is required here and {where} is not available")
    pytest.skip(f"no published specification to compare with: looked for {where}")


# --------------------------------------------------------------------------
# Conformance, shared: moved here on 2026-09-06 when a second test file needed
# it. It lived in `test_verify.py`, and the rule it encodes -- validate against
# BOTH implementations -- is exactly the kind that gets re-implemented halfway
# by whoever needs it next.


def _spec_problems(record: dict) -> list[str]:
    """Every way this record fails the spec, according to BOTH implementations.

    The standalone validator alone is not enough, and until 2026-08-26 it was
    all this file used: the schema is the NORMATIVE implementation, and the two
    had drifted on every recommended field. A CI that says "conforming" using
    the lenient one of two implementations is worse than one that says nothing,
    because it is the sentence a reader trusts.
    """
    import json
    import sys
    from pathlib import Path

    data = Path(__file__).parent / "data"
    sys.path.insert(0, str(data))
    from manifest_spec_validator import problems

    found = list(problems(record))
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - jsonschema is in the test extra
        return found
    schema = json.loads((data / "manifest-v1.schema.json").read_text(encoding="utf-8"))
    checker = jsonschema.Draft202012Validator(schema)
    found += [f"schema: {error.message}" for error in checker.iter_errors(record)]
    return found


def _spec_crs_keys() -> frozenset[str]:
    """The `crs_decisions` keys section 3.7 fixes, read from the normative schema.

    Not restated here. A test that polices a vocabulary against its own copy of
    that vocabulary polices nothing -- and this one exists precisely because two
    operations wrote synonyms of these names for a week without anything
    noticing.
    """
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).parent / "data" / "manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    keys = frozenset(schema["properties"]["crs_decisions"]["properties"])
    assert {"analysis_crs", "reason", "source_crs", "target_crs"} <= keys, sorted(keys)
    return keys

def _spec_transformation_keys() -> frozenset[str]:
    """The keys section 3.7 fixes INSIDE `transformation`, from the same schema.

    A second level, and it needed its own reader because the guards above stop
    at the first: `crs_decisions.transformation` is an object the specification
    defines, so a key of ours in there falls under D-077 rule 3 -- the prefix
    follows the container -- and until 2026-09-07 two of them did not carry it.
    Derived rather than restated, for the reason `_spec_crs_keys` is.
    """
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).parent / "data" / "manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    inner = schema["properties"]["crs_decisions"]["properties"]["transformation"]
    keys = frozenset(inner["properties"])
    assert {"pipeline", "accuracy_m", "is_ballpark"} <= keys, sorted(keys)
    return keys


def _spec_object_paths() -> dict[str, frozenset[str]]:
    """Every object the schema DESCRIBES, by dotted path, with its property names.

    The point is that this is not a list. `_spec_crs_keys` and
    `_spec_transformation_keys` each read one container, and each was written
    the day a key drifted inside that container -- which is a list of
    containers, maintained by whoever last got bitten. On 2026-09-10 the
    container nobody had got bitten by yet turned out to be `engine`, holding
    an unprefixed `geometry_library` in three engine modules since 2026-09-06.

    So the containers come from the schema. A container the specification gains
    is policed the day it lands, and one it loses stops being policed without
    anybody editing a test.

    Paths are dotted, with `[]` for the items of an array: `engine`,
    `crs_decisions.transformation`, `inputs[]`, `verification[]`. The root is
    the empty string. An object the schema leaves open -- no `properties` at all
    -- gets no entry, which is the honest outcome: there is nothing to check a
    key against, and pretending otherwise is what `additionalProperties: true`
    has been hiding all along.
    """
    import json
    from pathlib import Path

    schema = json.loads(
        (Path(__file__).parent / "data" / "manifest-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    paths: dict[str, frozenset[str]] = {}

    def resolve(node: object) -> object:
        # Local `$ref`s followed, since `1.0.0-draft.6` declares both legs of
        # `crs_decisions.round_trip` as a reference to `transformation`. The walk
        # read `properties` and a reference has none, so it stepped over both
        # legs and nothing checked that a key of ours inside them carries the
        # prefix -- while `docs/manifest-vocabulary.md` says the rule holds
        # there. Found by the `conformita-manifest` review before the draft was
        # tagged, together with the same hole in the specification's own suite.
        if isinstance(node, dict) and isinstance(node.get("$ref"), str):
            target: object = schema
            for step in node["$ref"].removeprefix("#/").split("/"):
                target = target[step]
            return {**target, **{k: v for k, v in node.items() if k != "$ref"}}
        return node

    def walk(node: object, path: str) -> None:
        node = resolve(node)
        if not isinstance(node, dict):
            return
        described = node.get("properties")
        if isinstance(described, dict):
            paths[path] = frozenset(described)
            for name, child in described.items():
                walk(child, f"{path}.{name}" if path else name)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, f"{path}[]")

    walk(schema, "")
    # Anti-vacuity, and on what the derivation must SEE rather than on what it
    # must find: these four are `required` or all but universal in the schema,
    # so a walk that misses them is broken rather than looking at a lean
    # schema. `engine` is named explicitly because it is the one that slipped.
    for expected in (
        "", "engine", "crs_decisions", "verification[]",
        # Reached only through a `$ref`: if the resolver stops working, the legs
        # drop out of the derivation again and this says so.
        "crs_decisions.round_trip.return_transformation",
    ):
        assert expected in paths, (
            f"the schema walk found no described object at {expected!r}: "
            f"it reached {sorted(paths)}. The walk is broken, or the schema "
            "changed shape -- either way this is not a lean schema."
        )
    return paths


#: Objects the specification describes but whose KEYS are nobody's to police,
#: each for a reason rather than by omission. Kept beside the derivation so the
#: exclusions are read together with it.
#:
#: **Neither of these excludes anything today, and saying so is the point.**
#: Both objects have no `properties` at all in the schema, so the derivation
#: above never records them and the guard would skip them anyway. What this does
#: is hold the reasoning, and fire the day the specification describes one
#: property inside either of them.
#:
#: `repairs[]` was the third entry here until 2026-09-10, with its reason
#: written as an open question for the specification. The question was answered
#: -- `1.0.0-draft.5` fixed the shape of a repairs entry -- so the entry is gone
#: and the container is policed like any other. It is worth noticing that the
#: exclusion did its job by being removable: it recorded WHY the container was
#: unwatched, so closing the gap was an edit rather than an archaeology.
SPEC_OBJECTS_NOT_OURS = {
    "parameters": (
        "The parameters the operation ran with. Their names are the "
        "operation's own vocabulary, not extensions of the manifest format, "
        "and the schema describes none of them on purpose."
    ),
    "environment": (
        "Section 3.8 asks for the configuration AS THE ENGINE REPORTS IT, so "
        "the keys are the engine's. D-077 rule 3 cuts the other way here -- "
        "the prefix follows the container, and this container's contents are "
        "not ours to name. It has its own guard, on the shape of a setting."
    ),
}


#: The shape D-077 requires of a `crs_decisions` key that is MapSmith's own.
#: The syntax is the one section 3.6 of the specification makes a MUST for
#: check names; applying it to FIELDS is a MapSmith rule that the specification
#: only recommends (section 3.5 says a producer prefix "does this well", and
#: says it as a SHOULD). Both guards import this so that one rule has one
#: predicate: the first version wrote `startswith` in one and a regex in the
#: other, and they disagreed on `x-mapsmith:Bad Name!`.
_EXTENSION_KEY = re.compile(r"^x-mapsmith:[a-z0-9][a-z0-9_]*$")


#: The shape of a key in `environment` that names a setting rather than one of
#: our readings of it. Section 3.8 asks for the configuration as the ENGINE
#: reports it and its own examples are `PROJ_NETWORK`, the `GDAL_*` variables
#: and `AREA_OR_POINT` — all three of that shape. Derived from the key instead
#: of checked against a list of variable names, which would be a list somebody
#: has to remember to fill in.
_SETTING_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
