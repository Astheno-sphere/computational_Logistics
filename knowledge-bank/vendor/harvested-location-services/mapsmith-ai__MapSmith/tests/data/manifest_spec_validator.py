"""Vendored, unmodified, from mapsmith-ai/manifest-spec `validator/validate.py`.

A copy and not a dependency: the point of the standalone validator is that
checking a record needs no toolchain, and a test that pip-installs the spec
repository to prove it would be testing something else. The conformance agent
diffs this against upstream; drift is a finding, not a merge.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Section 3.6: the closed core of check names. A producer performing one of
# these checks uses this name for it; anything else carries an `x-<producer>:`
# prefix. Kept as a literal list rather than derived from the schema, because
# this validator exists to be an INDEPENDENT implementation — two copies of one
# mistake agree with each other perfectly.
CORE_CHECK_NAMES = frozenset({
    "crs_present",
    "crs_matches",
    "geometry_valid",
    "feature_count_exact",
    "feature_count_bounded",
    "row_count_exact",
    "result_not_empty",
    "extent_within_expected",
    "shape_preserved",
    "values_in_expected_range",
    "input_crs_present",
    "input_not_empty",
    "inputs_share_crs",
    "inputs_may_intersect",
    "geometry_types",
})
EXTENSION_CHECK_NAME = re.compile(r"^x-[a-z0-9][a-z0-9_-]*:[a-z0-9][a-z0-9_]*$")
#: The keys of `crs_decisions` that section 3.7 defines. Any other key is an
#: extension and uses the grammar above (since 1.0.0-draft.7).
CRS_DECISION_KEYS = frozenset(
    {"analysis_crs", "reason", "source_crs", "target_crs", "transformation", "round_trip"}
)
#: And inside the objects section 3.7 and 3.4 define (since 1.0.0-draft.8): a
#: transformation, the round trip that holds two of them, and a repair entry.
TRANSFORMATION_KEYS = frozenset({"pipeline", "accuracy_m", "is_ballpark", "better_available_m"})
ROUND_TRIP_KEYS = frozenset({"transformation", "return_transformation"})
REPAIR_KEYS = frozenset({"action", "check", "error", "resolved"})


def _check_extension_keys(
    out: list[str], obj: dict, defined: frozenset, where: str, section: str
) -> None:
    """Every key the specification does not define carries the producer's prefix.

    `fullmatch`, not `match`: Python's `$` also matches before a final newline,
    so `x-vendor:name\\n` passed here and in Python's jsonschema while an
    ECMA-262 validator -- the semantics JSON Schema prescribes -- rejected it.
    """
    for key in obj:
        if key not in defined and not EXTENSION_CHECK_NAME.fullmatch(key):
            out.append(
                f"`{where}.{key}` is neither a key section {section} defines nor "
                "an extension named `x-<producer>:<name>`; every other key carries "
                "the producer's prefix"
            )


SPEC_VERSION = re.compile(r"^1\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$")


def _optional(
    out: list[str], where: dict, field: str, kinds: type | tuple, label: str = ""
) -> bool:
    """A field that is not required but IS typed. Absent is fine; wrong is not.

    RECOMMENDED is not the same as unchecked, and until 2026-08-26 here it was:
    this file looked only at the required fields, so a record carrying
    `producer` as a string, or `crs_decisions.analysis_crs` as a number, passed
    here and failed against the schema. Twelve mutations out of fifteen
    disagreed that way — which made the claim at the top of this file, two
    implementations kept in agreement, false about its own subject.
    """
    if field not in where:
        return False
    if not isinstance(where[field], kinds):
        prefix = f"{label}." if label else ""
        out.append(f"`{prefix}{field}` has the wrong type")
        return False
    return True


def _check_transformation(out: list[str], shift: dict, where: str) -> None:
    """One transformation object, wherever section 3.7 puts one.

    A function since 1.0.0-draft.6, when `round_trip` added two more places
    that hold the same shape. Until then this was inline under
    `crs_decisions.transformation`; copying it twice would have given the
    three copies three chances to disagree with the schema, and the one time
    this file has disagreed with it already is recorded just below.
    """
    _check_extension_keys(out, shift, TRANSFORMATION_KEYS, where, "3.7")
    # `pipeline` is NULLABLE, like `source_crs` and `accuracy_m`: PROJ does not
    # always give a pipeline string for a transformation it performed. This used
    # to be `_optional(..., str)`, the only nullable field in this file written
    # the non-nullable way, and the schema said `["string", "null"]` -- so the
    # two implementations disagreed, and section 3 says the schema wins.
    #
    # The record that exposed it is not exotic: a reprojection from EPSG:4267 to
    # EPSG:4326, which is the NAD27-to-WGS84 pair section 3.7 uses as its
    # headline example. The conformance suite did not see it for two reasons,
    # both now closed: it mutated `crs_decisions.transformation` as a container
    # and never descended into the three keys draft.3 added, and it only ever
    # checked that both implementations REJECT a bad value, never that both
    # ACCEPT a permitted one -- and null on a nullable field is exactly that case.
    if shift.get("pipeline") is not None and not isinstance(shift["pipeline"], str):
        out.append(f"`{where}.pipeline` must be a string or null")
    _optional(out, shift, "is_ballpark", bool, where)
    accuracy = shift.get("accuracy_m")
    # `isinstance(True, int)` is True in Python, and a boolean accuracy is not a
    # number in JSON: the two implementations must agree on that.
    if accuracy is not None and (
        isinstance(accuracy, bool) or not isinstance(accuracy, (int, float))
    ):
        out.append(f"`{where}.accuracy_m` must be a number or null")
    # New in 1.0.0-draft.4, and the reason it exists is in section 3.7: it is the
    # only field that tells "no operation exists for this pair" apart from "one
    # does and this machine has not got the grid".
    better = shift.get("better_available_m")
    if better is not None and (
        isinstance(better, bool) or not isinstance(better, (int, float))
    ):
        out.append(f"`{where}.better_available_m` must be a number or null")


def problems(record: object) -> list[str]:
    """Every way this record fails to conform, in schema order. Empty = conforming."""
    out: list[str] = []
    if not isinstance(record, dict):
        return ["the manifest must be a JSON object"]

    def need(field: str, kinds: type | tuple, where: dict = record, label: str = "") -> bool:
        prefix = f"{label}." if label else ""
        if field not in where:
            out.append(f"missing required field `{prefix}{field}`")
            return False
        if not isinstance(where[field], kinds):
            out.append(f"`{prefix}{field}` has the wrong type")
            return False
        return True

    if need("spec_version", str) and not SPEC_VERSION.fullmatch(record["spec_version"]):
        out.append(
            "`spec_version` must be semantic-versioned 1.x.y "
            f"(got {record['spec_version']!r})"
        )
    if need("operation", str) and not record["operation"]:
        out.append("`operation` must not be empty")
    need("parameters", dict)

    if need("inputs", list):
        for n, item in enumerate(record["inputs"]):
            label = f"inputs[{n}]"
            if not isinstance(item, dict):
                out.append(f"`{label}` must be an object")
                continue
            if need("path", str, item, label):
                if not item["path"]:
                    out.append(f"`{label}.path` must not be empty")
                if "\\" in item["path"]:
                    out.append(
                        f"`{label}.path` carries a backslash: paths use `/` as the only "
                        "separator on every platform, or two manifests for the same run "
                        "differ in a field that describes nothing about the computation"
                    )
            if need("sha256", str, item, label) and not SHA256.fullmatch(item["sha256"]):
                out.append(f"`{label}.sha256` must be 64 lowercase hex characters")
            # `argument` since 1.0.0-draft.10: the role of this input, by name,
            # because the order of `inputs` is not significant.
            for field in ("crs", "layer", "argument"):
                if item.get(field) is not None and not isinstance(item[field], str):
                    out.append(f"`{label}.{field}` must be a string or null")
            # Since 1.0.0-draft.10: section 3.8 narrowed to one input.
            if _optional(out, item, "environment", dict, label):
                for key, value in item["environment"].items():
                    if not isinstance(value, str):
                        out.append(
                            f"`{label}.environment.{key}` must be a string: section 3.8 "
                            "records configuration as it was set, not as a parsed value"
                        )

    if need("engine", dict):
        for field in ("name", "version"):
            if need(field, str, record["engine"], "engine") and not record["engine"][field]:
                out.append(f"`engine.{field}` must not be empty")

    if need("verification", list):
        if not record["verification"]:
            out.append(
                "`verification` must hold at least one check: a manifest with no checks "
                "at all is a log entry wearing a manifest's clothes"
            )
        for n, check in enumerate(record["verification"]):
            label = f"verification[{n}]"
            if not isinstance(check, dict):
                out.append(f"`{label}` must be an object")
                continue
            if need("name", str, check, label):
                name = check["name"]
                if not name:
                    out.append(f"`{label}.name` must not be empty")
                elif name not in CORE_CHECK_NAMES and not EXTENSION_CHECK_NAME.fullmatch(name):
                    out.append(
                        f"`{label}.name` is {name!r}, which is neither a core check "
                        "name (section 3.6) nor an extension named "
                        "`x-<producer>:<name>`. An unconstrained vocabulary makes two "
                        "records incomparable, which is the point of having a format."
                    )
            need("passed", bool, check, label)
            need("detail", str, check, label)
            _optional(out, check, "critical", bool, label)
            for field in ("hint", "argument"):
                if check.get(field) is not None and not isinstance(check[field], str):
                    out.append(f"`{label}.{field}` must be a string or null")

    if "output" in record:
        out_field = record["output"]
        if not isinstance(out_field, dict):
            out.append("`output` must be an object")
        else:
            if need("path", str, out_field, "output"):
                if not out_field["path"]:
                    out.append("`output.path` must not be empty")
                if "\\" in out_field["path"]:
                    out.append("`output.path` carries a backslash: paths use `/` as the "
                               "only separator on every platform")
            if need("sha256", str, out_field, "output") and not SHA256.fullmatch(
                out_field["sha256"]
            ):
                out.append("`output.sha256` must be 64 lowercase hex characters")
            # New in 1.0.0-draft.4. Section 3.7 had pointed here since draft.2
            # for the output CRS, and there was nowhere here to point at.
            crs = out_field.get("crs")
            if crs is not None and not isinstance(crs, str):
                out.append("`output.crs` must be a string or null")
            # New in 1.0.0-draft.9: the layer a container record describes.
            layer = out_field.get("layer")
            if layer is not None and not isinstance(layer, str):
                out.append("`output.layer` must be a string or null")

    # The RECOMMENDED fields of section 3.4. Optional to emit, typed once
    # emitted: a consumer that finds `notes` holding a bare string instead of a
    # list has to guess, and guessing is what this format exists to remove.
    if _optional(out, record, "crs_decisions", dict):
        decisions = record["crs_decisions"]
        for field in ("analysis_crs", "reason"):
            # A specific message rather than the generic "wrong type": these
            # two are prose a reader checks, and saying so helps whoever emits.
            if field in decisions and not isinstance(decisions[field], str):
                out.append(f"`crs_decisions.{field}` must be a string")
        for field in ("source_crs", "target_crs"):
            if decisions.get(field) is not None and not isinstance(decisions[field], str):
                out.append(f"`crs_decisions.{field}` must be a string or null")
        # Section 3.7: the other values are deliberately NOT all strings. Before
        # draft.3 they were, and the cost was that "was this a ballpark
        # transformation?" could only be answered in prose -- which is what
        # section 7 faults other formats for.
        if _optional(out, decisions, "transformation", dict, "crs_decisions"):
            _check_transformation(out, decisions["transformation"], "crs_decisions.transformation")
        # New in 1.0.0-draft.6. Two legs of the same shape as `transformation`,
        # each checked by the same code: a second copy of the checks above
        # would be a second chance for the two to drift, and the one place
        # this file has already drifted from the schema was a nullable field
        # written the non-nullable way (see `_check_transformation`).
        if _optional(out, decisions, "round_trip", dict, "crs_decisions"):
            trip = decisions["round_trip"]
            _check_extension_keys(out, trip, ROUND_TRIP_KEYS, "crs_decisions.round_trip", "3.7")
            for leg in ("transformation", "return_transformation"):
                if leg not in trip:
                    out.append(
                        f"`crs_decisions.round_trip` is missing `{leg}`: section 3.7 "
                        "records both legs, each as the engine reported it for its "
                        "direction, and neither may be derived from the other"
                    )
                elif _optional(out, trip, leg, dict, "crs_decisions.round_trip"):
                    _check_transformation(out, trip[leg], f"crs_decisions.round_trip.{leg}")
        # The fact has one name since draft.6. A prefixed key for it is the
        # reference implementation's own old name, and the likeliest way a
        # producer gets this wrong is by not migrating -- so that is the case
        # checked. It is a proxy for "the same fact under another name", which
        # no program can recognise in general, and it is stated as one.
        # The same grammar as the schema's `patternProperties`, and not a looser
        # one: `startswith("x-") and endswith(":round_trip")` also caught
        # `x-a:b:round_trip` and `x-:round_trip`, which the schema accepts, so the
        # two implementations disagreed on two spellings -- found by the
        # `conformita-manifest` review before draft.6 was tagged. Section 3 says
        # the schema wins, so this follows it.
        # New in 1.0.0-draft.7: the keys this section does not define carry the
        # producer's prefix, in the grammar of an extension check name. Until
        # then section 3.7 permitted them "under the extension rule above",
        # which could be read as either 3.5 (a SHOULD with no syntax) or 3.6 (a
        # MUST with one), and a third-party emitter reading only the prose would
        # not have produced the prefix.
        _check_extension_keys(out, decisions, CRS_DECISION_KEYS, "crs_decisions", "3.7")
        for key in decisions:
            if re.fullmatch(r"x-[^:]+:round_trip", key):
                out.append(
                    f"`crs_decisions.{key}` records a CRS round trip under an "
                    "extension name; since 1.0.0-draft.6 section 3.7 names it "
                    "`round_trip`, and a core fact under a prefixed name does not "
                    "conform"
                )
    if _optional(out, record, "environment", dict):
        for key, value in record["environment"].items():
            if not isinstance(value, str):
                out.append(
                    f"`environment.{key}` must be a string: section 3.8 records configuration "
                    "as the engine reports it, not as a parsed value"
                )
    if _optional(out, record, "notes", list):
        for n, note in enumerate(record["notes"]):
            if not isinstance(note, str):
                out.append(f"`notes[{n}]` must be a string")
    if _optional(out, record, "repairs", list):
        for n, repair in enumerate(record["repairs"]):
            if not isinstance(repair, dict):
                out.append(f"`repairs[{n}]` must be an object")
                continue
            _check_extension_keys(out, repair, REPAIR_KEYS, f"repairs[{n}]", "3.4")
            # The shape of an entry, new in 1.0.0-draft.5. Until then this
            # branch checked that a repair was an object and stopped, so two
            # producers disclosing the same repair could share no key and both
            # conform -- which is disclosure a consumer cannot read.
            #
            # The mutation tests did exercise the field, through the maximal
            # record. What no `conformance/` fixture carried was a `repairs`
            # field at all, and those are the files a third-party implementer
            # reads: the one part of the format with no worked example was the
            # one part with no described shape.
            if "action" not in repair:
                out.append(
                    f"missing required field `repairs[{n}].action`: an entry "
                    "that does not say what was done discloses nothing. Null "
                    "is conforming and means a repair was attempted and "
                    "achieved nothing, with `error` saying why; absent cannot "
                    "be told apart from a producer that recorded none."
                )
            for field, kinds in (
                ("check", (str, type(None))),
                ("action", (str, type(None))),
                ("error", (str, type(None))),
                ("resolved", bool),
            ):
                if field in repair and not isinstance(repair[field], kinds):
                    out.append(f"`repairs[{n}].{field}` has the wrong type")
    _optional(out, record, "parameters_redacted", bool)
    if _optional(out, record, "producer", dict):
        for field in ("name", "version"):
            _optional(out, record["producer"], field, str, "producer")

    stamps = {}
    for field in ("started_at", "finished_at"):
        if need(field, str) and not TIMESTAMP.fullmatch(record[field]):
            out.append(f"`{field}` must be RFC 3339 in UTC, ending in `Z`")
        elif field in record and isinstance(record[field], str):
            stamps[field] = record[field]
    if len(stamps) == 2 and stamps["finished_at"] < stamps["started_at"]:
        # String comparison is correct here BECAUSE the format is fixed-width
        # UTC: that is one of the reasons the spec requires it.
        out.append("`finished_at` precedes `started_at`")

    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    failed = False
    for name in argv:
        try:
            record = json.loads(Path(name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{name}: unreadable ({exc})")
            failed = True
            continue
        found = problems(record)
        for reason in found:
            print(f"{name}: {reason}")
        if found:
            failed = True
        else:
            print(f"{name}: conforming")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
