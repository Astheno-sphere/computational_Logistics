"""Lineage manifests for every MapSmith output.

Every operation that writes a dataset also writes ``<output>.provenance.json``
next to it. The manifest is the product's core promise: any result can be
audited and re-run the analysis without an LLM in the loop.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from . import __version__

# The manifest specification this record targets. MapSmith is one
# implementation of that format, not its definition: the spec, its schema, a
# toolchain-free validator and the conformance suite live in their own
# repository, and a CI test validates real MapSmith output against them.
SPEC_VERSION = "1.0.0-draft.10"

#: One `crs_decisions` key for "a secondary input was brought into the analysis
#: CRS", and a structured value rather than a sentence.
#:
#: Written here rather than at the two call sites because there were two names
#: for it — `reference_reprojected` in `snap_layer`, `second_layer_reprojected`
#: in `line_intersections` — which is the defect D-077 removed from the
#: specification's vocabulary, reappearing one level down in our own. The value
#: is a list of `{"argument": ..., "from": ...}`: section 3.7 argues at length
#: that `is_ballpark` is a boolean because a consumer has to branch on it, and
#: `"EPSG:4326 -> EPSG:32632"` is prose in a key for the same reason it should
#: not be. Where it went is already `analysis_crs`, so only where it came from
#: is worth recording.
INPUTS_REPROJECTED = "x-mapsmith:inputs_reprojected"


#: The output was computed in one CRS and written back in the caller's, because
#: the operation needed metres and the caller's data is in degrees. A different
#: fact from `INPUTS_REPROJECTED`: nothing of the caller's moved permanently.
#:
#: A core key of the specification since `1.0.0-draft.6` (D-091), and no longer
#: an extension: until then it was `x-mapsmith:round_trip`, which a producer
#: reading only the specification would have had to reinvent under its own
#: name. The two legs are an operation and its INVERSE, each asked of PROJ --
#: this comment said "the transformation was applied twice" until 2026-09-23,
#: sixteen days after that description was found false and removed from the
#: record itself. The key moved; the sentence beside its definition did not.
ROUND_TRIP = "round_trip"

#: The two `crs_decisions` keys `grid` contributes. Here rather than there so
#: that every extension MapSmith adds to that object is declared in one place.
REGISTRATION_KEY = "x-mapsmith:raster_registration"
REGISTRATION_REASON_KEY = "x-mapsmith:raster_registration_reason"

#: **Every `crs_decisions` key MapSmith adds, with the sentence that says why
#: it is not a synonym of one the specification already has.**
#:
#: D-077 rule 1 forbids inventing a second name for a key section 3.7 already
#: recommends, and the guards derive the rest of that rule from the schema --
#: but they cannot derive THIS half. A prefixed key passes the prefix check
#: whether or not it means what `source_crs` means, so the two synonyms that
#: started all of this (`measurement_crs`, `declared_output_crs`) would have
#: sailed through with an `x-mapsmith:` in front of them.
#:
#: So this is a ratchet on the SET, not a derivation of the judgement: a key
#: that is not here fails the suite until somebody adds it **with the reason**.
#: It does not decide whether a name is a synonym; it makes the decision be
#: written down by the person making it, which is the only mechanism available
#: for a question that is not mechanical.
CRS_EXTENSIONS: dict[str, str] = {
    INPUTS_REPROJECTED: (
        "Not `source_crs`: that says where the OPERATION's coordinates were, and "
        "these are other inputs brought to meet them. The output never was in "
        "the CRS named here."
    ),
    "x-mapsmith:input_crs_discarded": (
        "Not `source_crs`, which the specification defines as the system the "
        "coordinates WERE IN. This operation exists because that declaration is "
        "wrong: a traverse on an assumed grid was never in the CRS its file "
        "claimed, so the spec key would state what the run denies."
    ),
    "x-mapsmith:computed_in": (
        "Not `analysis_crs`, and its absence is the point. The Esri stack buffers "
        "geodesically in the input's own geographic CRS, so no analysis CRS was "
        "chosen; naming one would let a consumer read EPSG:4326 as the CRS a "
        "metric computation happened in."
    ),
    REGISTRATION_KEY: (
        "Cell registration is not a coordinate system, and section 3.7 has no key "
        "for it. Not `environment` either: AREA_OR_POINT is a tag INSIDE the file, "
        "so it is data, and section 3.8 says a producer's reading of it goes in "
        "`crs_decisions` under the producer's own prefixed key."
    ),
    REGISTRATION_REASON_KEY: (
        "Not `reason`, which belongs to the CRS decision and is already taken. Two "
        "different reasons under one key silently replaced each other once, and a "
        "test caught it."
    ),
}


#: Our own keys INSIDE `crs_decisions.transformation`, which is an object the
#: specification defines -- four keys since `1.0.0-draft.4`. D-077 rule 3: the
#: prefix follows the container and not the datum, so a key of ours in there has
#: to say it is ours. The sentence beside each is the part a prefix cannot
#: supply, exactly as in `CRS_EXTENSIONS`: a prefix says whose a key is, never
#: that it is not a renamed version of one the format already has.
#:
#: `better_available_m` was in this list until 2026-09-07 and is not any more --
#: it entered the specification that day, so it belongs to the format and stands
#: unprefixed by right. That is the direction this list is supposed to move in.
TRANSFORMATION_EXTENSIONS: dict[str, str] = {
    "x-mapsmith:chosen_by": (
        "Not `pipeline`, which says WHAT will run: this says WHO picked it, and "
        "it is written only where the answer is `the engine, not MapSmith`. The "
        "specification has no key for agency because it assumes one producer "
        "reporting one choice; here the engine reaches for PROJ on its own and "
        "this module can only report what it will get."
    ),
    "x-mapsmith:default_was_ballpark": (
        "Not `is_ballpark`, and the two are opposites in the same record: this "
        "appears when `is_ballpark` is FALSE precisely because MapSmith declined "
        "the default. Without it the record says the right thing -- a real datum "
        "shift, with its accuracy -- and hides that the library's own choice "
        "would have applied none."
    ),
}

#: **The extension keys MapSmith adds OUTSIDE `verification[]` and
#: `crs_decisions`, one entry per container.**
#:
#: These two were emitted for weeks and appeared in `docs/manifest-vocabulary.md`
#: nowhere, which the generated page could not notice: it derives its sections
#: from the three constants above, and a container absent from that list is a
#: container it never looks in. The page said it listed the vocabulary and
#: listed most of it — the same shape as a guard that cannot fail, wearing a
#: documentation hat.
#:
#: `engine` and `repairs[]` are objects the specification defines (§3.2, §3.4),
#: so a key added to either is an extension under §3.5 and carries the prefix.
#: The rule of D-077 applies here as it does to `crs_decisions`: the sentence
#: has to say why the key is not a synonym of one the format already has.
CONTAINER_EXTENSIONS: dict[str, dict[str, str]] = {
    "engine": {
        "x-mapsmith:geometry_library": (
            "Not `engine.version`, which names the thing that ran: three engines "
            "in this package are thin layers over Shapely, and the version that "
            "decides the geometry is Shapely's, not theirs. Recording only the "
            "wrapper would name a component that cannot explain a change in the "
            "answer."
        ),
    },
    "repairs[]": {
        "x-mapsmith:round": (
            "Which pass of the repair loop produced this entry. Not `action`, "
            "which says what was done: the same action can be applied twice, and "
            "without the round two entries reporting the same fix are "
            "indistinguishable from one entry written twice."
        ),
    },
}


def alignment_decisions(
    analysis_crs: Any,
    reason: str,
    moved: Sequence[tuple[str, Any]] = (),
    *,
    moved_to: Any = None,
) -> dict[str, Any]:
    """`crs_decisions` for an operation that brings its other inputs to one CRS.

    Nine operations in `vector` and several elsewhere do the same three things
    and each did them differently, or not at all. Written once, for the reason
    `readers.py` exists: the same decision in nine copies is nine chances for
    one of them to be missing a branch.

    Three things, and each was wrong somewhere before 2026-09-06:

    * **It is written on both branches.** Most of these built `crs_decisions`
      only when something had to move, so the ordinary manifest was `{}` — and
      a reader cannot tell "computed in the input's CRS" from "nobody recorded
      it". Those are different claims.
    * **It says which input moved**, under `INPUTS_REPROJECTED`, rather than
      leaving the reader to guess from a sentence.
    * **It says how.** `to_crs` reaches for PROJ itself, so the record carries
      what the engine will actually get. Across two datums with no grid on the
      machine that is tens of metres, and `is_ballpark` is the boolean a
      consumer branches on.

    `moved` is `(argument name, the CRS it was in)` for each input that really
    was reprojected. The transformation lands in the specification's own
    `transformation` key when exactly one input moved, and inside each entry
    when several did with different pairs — once, in the place able to hold it,
    rather than twice.

    The other shape — the operation computed somewhere else because it needed
    metres, and wrote its output back in the caller's CRS — is NOT recorded
    here. It is recorded by `record_round_trip`, after the way back has
    actually happened, and the reason is in that function.
    """
    from . import datum

    decisions: dict[str, Any] = {
        "analysis_crs": _crs_label(analysis_crs),
        "reason": reason,
    }
    if not moved:
        return decisions
    entries = [
        {"argument": argument, "from": _crs_label(source)} for argument, source in moved
    ]
    # Where the moved inputs ACTUALLY went, which is not always the analysis
    # CRS. `nearest_join` brings its right layer to the left layer's CRS and
    # only then takes both out to an estimated UTM zone: recording the pair
    # (right, UTM) described a transformation PROJ was never asked for, and
    # on NAD27 it came out `is_ballpark: true` for a run that had applied a
    # seven-metre shift. A manifest accusing an engine of skipping a datum
    # shift it did not skip is the worst direction to be wrong in.
    destination = analysis_crs if moved_to is None else moved_to
    shifts = [datum.default_operation(source, destination) for _, source in moved]
    if len(moved) == 1:
        decisions["transformation"] = shifts[0]
    else:
        for entry, shift in zip(entries, shifts, strict=True):
            entry["transformation"] = shift
    decisions[INPUTS_REPROJECTED] = entries
    return decisions


def record_round_trip(record: Any, analysis_crs: Any, returned_to: Any) -> None:
    """Record a completed round trip — called AFTER the way back has happened.

    An operation that needs metres computes somewhere else and writes its output
    back in the caller's CRS. The trip is not free and the manifest used to say
    nothing about it: `estimate_utm_crs()` answers with a **WGS 84** UTM zone
    whatever the input's datum is (measured 2026-09-06), so buffering a NAD27
    layer crosses a datum on the way out and again on the way back, seven metres
    each way. The two legs largely cancel over one feature, which is why nothing
    ever looked wrong.

    Both legs are recorded, each asked of PROJ on its own pair, because the trip
    is two operations and not one applied twice. Until 2026-09-07 this wrote the
    outbound leg and `"applied_twice": True` — a constant, never computed, and
    an inference: PROJ is free to pick a different operation for the reverse
    pair, and on the README's own example it does, an operation and its inverse.

    **Why it is a function of its own, and called late.** Until 2026-09-23 the
    pair was built inside `alignment_decisions`, which three of the four callers
    invoke *before* the return leg runs — and the return leg runs inside
    `audit_on_failure`. So a `to_crs` that raised on the way back produced a
    manifest asserting a round trip that never completed: the audit trail
    surviving the error, which is invariant 3 working, carrying a claim that had
    become false, which is invariant 3 defeated. `buffer_layer` was the only one
    with the right order and it was right by accident — the Esri branch forced
    the assignment down, not a thought about the error path.

    So the order is now the contract: `alignment_decisions` says where the work
    happened, this says the output came home, and it can only be called where
    that is true.
    """
    from . import datum

    if returned_to is None or _same_crs(returned_to, analysis_crs):
        return
    record.crs_decisions[ROUND_TRIP] = {
        "transformation": datum.default_operation(returned_to, analysis_crs),
        "return_transformation": datum.default_operation(analysis_crs, returned_to),
    }


def _crs_label(crs: Any) -> str:
    from . import verify

    return verify.crs_label(crs)


def _same_crs(a: Any, b: Any) -> bool:
    from . import verify

    return bool(verify.same_crs(a, b))


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_of(path: str | Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


# The data-defining files of a shapefile (spec §3.3, draft.9), each listed
# under its lowercased extension so a renamed shapefile keeps its digest.
# Spatial indexes and `.shp.xml` metadata are not members: a digest that moved
# when an index was rebuilt would report an edit that never touched the data.
SHAPEFILE_MEMBERS = (".shp", ".shx", ".dbf", ".prj", ".cpg")
# What an operating system drops into a folder it displays (spec §3.3).
_NOT_CONTAINER_MEMBERS = ("thumbs.db", "desktop.ini")


def _listing_sha256(members: dict[str, str]) -> str:
    ordered = sorted(members.items(), key=lambda item: item[0].encode("utf-8"))
    return hashlib.sha256(
        "".join(f"{name}\0{sha}\n" for name, sha in ordered).encode("utf-8")
    ).hexdigest()


def _shapefile_member_paths(shp: Path) -> dict[str, Path]:
    """The member files of a shapefile, by extension: one enumeration for the
    digest and for `dataset_size`, so the cap reads what the digest reads."""
    stem = shp.name[: -len(".shp")].lower()
    found: dict[str, Path] = {}
    for candidate in shp.parent.iterdir():
        if not candidate.is_file() or _is_link(candidate):
            continue
        for ext in SHAPEFILE_MEMBERS:
            if candidate.name.lower() == stem + ext:
                if ext in found:
                    raise ValueError(
                        f"two files match the {ext} member of {shp.name}: {found[ext].name} "
                        f"and {candidate.name}; the specification forbids choosing one"
                    )
                found[ext] = candidate
    if ".shp" not in found:
        raise FileNotFoundError(shp)
    return found


def _shapefile_members(shp: Path) -> dict[str, str]:
    return {ext: sha256_of(path) for ext, path in _shapefile_member_paths(shp).items()}


def _is_link(path: Path) -> bool:
    """A symbolic link, or a Windows junction, which `is_symlink()` does not see.

    Spec section 3.3: links are neither members nor followed. A junction is a
    link to a directory in everything but name, and until 0.8.0 the walk below
    followed it: a junction inside a `.gdb` pointing outside the workspace put
    files from there into the digest, and one pointing at a drive root made the
    walk read the drive (0.8.0 audit). The manifest scan already pruned them.
    """
    return path.is_symlink() or path.is_junction()


def _container_member_paths(root: Path) -> dict[str, Path]:
    """The members of a directory container, by the rule of spec section 3.3.

    One enumeration for the digest and for `dataset_size`, which used to walk
    on its own and count hidden files, OS litter and linked members the digest
    leaves out -- harmless to correctness, wrong for the cap it feeds.
    """
    members: dict[str, Path] = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not _is_link(Path(dirpath) / d)]
        for name in files:
            lowered = name.lower()
            if (
                lowered.endswith(".lock")  # never opened: they carry a host name
                or name.startswith(".")
                or lowered in _NOT_CONTAINER_MEMBERS
            ):
                continue
            member = Path(dirpath) / name
            if _is_link(member):
                continue
            members[member.relative_to(root).as_posix()] = member
    return members


def _container_members(root: Path) -> dict[str, str]:
    return {rel: sha256_of(path) for rel, path in _container_member_paths(root).items()}


def dataset_sha256(path: str | Path) -> str:
    """The digest the manifest records for a dataset, by the rule of spec §3.3.

    One file: the SHA-256 of its bytes. A shapefile: the listing of its data
    files, so an edit to the attributes (`.dbf`) or to the CRS (`.prj`) moves
    the digest -- until 0.7.1 only the `.shp` was hashed, and a record kept
    matching a dataset whose attributes had been rewritten -- while a rename
    does not. A directory container (`.gdb`): every regular file under it
    except lock files, hidden files and OS litter. Writers and `get_lineage`
    both call this, so the digest a record states and the digest a walk
    recomputes cannot drift apart.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".gdb" and p.is_dir():
        return _listing_sha256(_container_members(p))
    if suffix == ".shp":
        return _listing_sha256(_shapefile_members(p))
    return sha256_of(p)


def shapefile_digests(shp: str | Path) -> tuple[str, str]:
    """A shapefile's digest under both rules, reading each member once.

    `(sha256 of the .shp alone, the listing digest of section 3.3)`: the first
    is what records before draft.9 state, the second what records since do.
    """
    members = _shapefile_members(Path(shp))
    return members[".shp"], _listing_sha256(members)


def dataset_size(path: str | Path) -> int:
    """How many bytes `dataset_sha256(path)` reads, so a caller can cap it."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".gdb" and p.is_dir():
        return sum(path.stat().st_size for path in _container_member_paths(p).values())
    if suffix == ".shp":
        return sum(path.stat().st_size for path in _shapefile_member_paths(p).values())
    return p.stat().st_size


def declares_listing_rule(record: dict[str, Any]) -> bool:
    """Whether a record's digests follow §3.3's listing rule (draft.9 and later).

    Records from earlier drafts -- every record MapSmith wrote up to 0.7.1 --
    digested a shapefile as its `.shp` alone. Comparing them against the
    listing would accuse unchanged data of having been edited.

    "Later" is SemVer precedence, as section 3.3 says: `draft.10` follows
    `draft.9`, every release follows every draft, and so does a pre-release of
    a later version (`1.1.0-draft.1`). A version that is not SemVer, or no
    version at all, is read under the old rule: nothing written under the new
    one lacks it.
    """
    match = _SEMVER.fullmatch(str(record.get("spec_version") or ""))
    if not match:
        return False
    core = tuple(int(part) for part in match.group(1, 2, 3))
    if core != (1, 0, 0):
        return core > (1, 0, 0)
    if match.group(4) is None:
        return True
    ids = match.group(4).split(".")
    if any(part.isdigit() and len(part) > 1 and part[0] == "0" for part in ids):
        return False  # SemVer forbids leading zeros in a numeric identifier
    return _prerelease_key(ids) >= _prerelease_key(["draft", "9"])


_SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?"
)


def _prerelease_key(ids: list[str]) -> list[tuple[int, int, str]]:
    # SemVer 11.4: numeric identifiers compare numerically and rank below
    # alphanumeric ones; a shorter list ranks below a longer one it prefixes,
    # which is how Python already compares lists.
    return [(0, int(part), "") if part.isdigit() else (1, 0, part) for part in ids]


def record_digest(path: str | Path, record: dict[str, Any]) -> str:
    """The digest of `path` under the rule the record was written with."""
    if Path(path).suffix.lower() == ".shp" and not declares_listing_rule(record):
        return sha256_of(path)
    return dataset_sha256(path)


REDACTED = "<redacted>"
_QUOTED_REDACTED = f"'{REDACTED}'"

# Names that carry a credential in the SQL dialects, map literals and URIs
# MapSmith touches: DuckDB secrets (CREATE SECRET ... KEY_ID '...'), httpfs/S3
# settings, ATTACH ... (PASSWORD '...'), signed-URL query parameters, and
# generic API tokens. Matched as the SUFFIX of a longer identifier too, because
# `s3_secret_access_key` ends in one of these and a plain word boundary misses
# it (an underscore is a word character).
_SECRET_NAMES = (
    "secret", "secret_access_key", "session_token", "password", "passwd", "pwd",
    "passphrase", "key_id", "access_key_id", "token", "api_key", "apikey",
    "auth", "authorization", "bearer", "client_secret", "private_key",
    "connection_string", "conninfo", "credential", "credentials", "sas",
    "signature",
    # Azure's shared-access signature spells it `sig`, and the Planetary
    # Computer hands out exactly that form: `?sv=...&sig=...&se=...`. Its AWS
    # equivalent (`X-Amz-Signature`) was already covered, so the same signed URL
    # was redacted from one cloud and printed in clear from the other. Safe to
    # add because every rule below anchors the name — on a query parameter it
    # must be followed by `=`, and `?design=` ends in `ign`, not `sig`.
    "sig",
)
# `api_key` and `x-api-key` are the same name. The list is written with
# underscores because that is how SQL spells it, and an HTTP header spells it
# with hyphens — so `x_api_key` was masked and `x-api-key` went through
# untouched. Each underscore accepts either separator.
_NAMES = "|".join(name.replace("_", "[-_]") for name in _SECRET_NAMES)

#: A whole identifier that names a credential: an optional prefix ending in a
#: separator, then one of the names above, and nothing of the identifier after
#: it. Written once because the key matcher and the assignment matcher have to
#: agree — they did not, and the disagreement was visible inside a single
#: record.
#:
#: The left boundary carries as much weight as the right. Without it `.search`
#: finds `sas` in the middle of `arkansas`, and a column named after the state
#: comes back `<redacted>`.
#:
#: **A trailing component is allowed, and leaving it out was a regression.** The
#: fix that stopped masking `sig_figs` and `token_count` required the name to be
#: the END of the identifier, which quietly stopped masking `secret_key`,
#: `aws_secret_key`, `secretkey`, `private_key_pem`, `token_value` and
#: `gcp_service_account_key` -- measured in a pre-release audit on 2026-09-21.
#: The commit that narrowed it said "measured against 31 real credential names,
#: every credential still masked", and `secret_key` was not among the 31: the
#: guard was true of the sample and false of the rule. What actually separates
#: `sig_figs` from `secret_key` is not position -- it is that `figs` and `count`
#: are ordinary words while what follows a credential word here is another
#: credential word or a format. So the suffix is allowed only from a small list,
#: which is the distinction the earlier fix was reaching for.
_TRAILING = r"(?:[_.\-]?(?:key|keys|value|values|pem|der|jwt|base64|b64))*"
_KEY_NAME = (
    r"(?<![A-Za-z0-9_.\-])(?:[A-Za-z0-9_.\-]*[_.\-])?(?:" + _NAMES + r")" + _TRAILING
)

# A gap between a name and its value: whitespace, a block comment, a line
# comment. An audit hid a secret behind `SECRET /* c */ 'shh'`, which the first
# version of this matcher walked straight past.
_GAP = r"(?:\s|/\*.*?\*/|--[^\n]*(?:\n|$))+"

# Every spelling of a string literal these dialects allow, because getting this
# wrong is not a miss but a corruption: on `SECRET E'shh\'x'` the first version
# paired the quotes one argument off, redacted the WRONG value and kept the
# secret — a manifest both misleading and leaky.
_VALUE = (
    r"(?P<v>"
    r"[Ee]'(?:\\.|''|[^'\\])*'"                    # E'...' with backslash escapes
    r"|'(?:''|[^'])*'"                             # '...' with doubled quotes
    r'|"(?:""|[^"])*"'
    r"|\$(?P<tag>[A-Za-z0-9_]*)\$.*?\$(?P=tag)\$"  # $$...$$ and $tag$...$tag$
    # Bare token, masked only after `=`. It must stop at `&` and at a quote, or
    # a signed URL loses everything after its credential parameter *and* its
    # closing quote — `?X-Amz-Signature=abc&y=1'` came back as
    # `?X-Amz-Signature=<redacted>`, destroying the rest of the URL and leaving
    # SQL that no longer parses. Unquoted SQL values never contain either.
    r"|[^\s,;)'\"&]+"
    r")"
)

# `(?:GAP)?` and not `GAP?`: _GAP already ends in `+`, so appending `?` makes it
# `+?` — a LAZY quantifier that still requires one character — and `token='x'`
# with no space stopped matching at all. Caught by the test that had covered
# that exact form since the first version.
_OPTIONAL_GAP = "(?:" + _GAP + ")?"

#: A dictionary key that names a credential. Same vocabulary as the assignment
#: scanner, and the same restraint: bare `key` is deliberately NOT in the list,
#: because `sort_key`, `primary_key` and `key` itself are ordinary field names,
#: and a redaction that fires on those teaches its reader to distrust the mask.
#:
#: **The name must END with the credential word**, and until 2026-09-06 it did
#: not: the word could sit anywhere with a separator on each side, so `sig_figs`,
#: `token_count`, `signature_file` and `signature_field` were all masked. Two of
#: those are GIS vocabulary — a spectral signature file is a real thing, and the
#: day MapSmith ships supervised classification the manifest would hide the name
#: of the training file and raise `parameters_redacted` on a record no secret
#: ever passed through. Masking `sig_figs: 4` also changed the value's JSON type
#: from a number to a string.
#:
#: Worse than either: the assignment scanner already required the suffix, so one
#: name got two answers in one record — `sig_figs = 4` inside a note went
#: through, `{"sig_figs": 4}` in parameters came back redacted. A mask that
#: answers differently about the same word is a mask its reader stops believing,
#: which is the whole asset being protected here.
_SECRET_KEY = re.compile(r"^" + _KEY_NAME + r"$", re.IGNORECASE)

# Same name shape as the key matcher, from the same definition, so the two
# cannot drift apart again. Measured on 2026-09-06 against 31 real credential
# names and 23 ordinary ones: every credential still masked, every ordinary name
# left alone, and `arkansas='x'` — which the old form redacted — left alone too.
_SECRET_ASSIGNMENT = re.compile(
    r"(?is)(?P<name>" + _KEY_NAME + r")\b"
    r"(?P<sep>" + _OPTIONAL_GAP + r"(?::=|=)" + _OPTIONAL_GAP + r"|" + _GAP + r")"
    + _VALUE
)

# `MAP{'Authorization': 'Bearer x'}` and its JSON-shaped equivalents: here the
# credential name is a quoted KEY, not an identifier, so the rule above never
# sees it. This is the syntax an audit found in the one secret type MapSmith's
# sandbox can actually construct.
_QUOTED_PAIR = re.compile(
    r"(?is)(?P<key>['\"][A-Za-z0-9_.\-]*(?:" + _NAMES + r")['\"]\s*:\s*)"
    r"(?P<v>'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")"
)

# userinfo in a URI: scheme://user:password@host
_URI_PASSWORD = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^\s:/@]+):([^\s@/]+)@")

# A signed URL carries its credential in the query string, and that reaches a
# manifest through `inputs[].path` rather than through SQL text.
_URI_QUERY = re.compile(
    r"(?i)([?&][A-Za-z0-9_.\-]*(?:" + _NAMES + r")=)([^&\s'\"]+)"
)


def _mask_assignment(match: re.Match) -> str:
    """Redact a credential value, but only where it really is one.

    Requires the value to be quoted (in any spelling above) or introduced by
    `=`, which covers every syntax MapSmith can meet while leaving
    `CREATE SECRET my_bucket (...)` readable — the secret's *name* is not a
    credential, and hiding it would cost the reader the one detail that says
    which statement ran.

    A quoted value is replaced by a QUOTED placeholder. A bare `<redacted>`
    where a string literal used to be leaves a statement that no longer parses,
    and a manifest people are invited to attach to a bug report should survive
    being pasted back into a client.
    """
    name, separator, value = match.group("name"), match.group("sep"), match.group("v")
    if value[:1] in "'\"$" or value[:2].lower() == "e'":
        return f"{name}{separator}{_QUOTED_REDACTED}"
    if "=" in separator:
        return f"{name}{separator}{REDACTED}"
    return match.group(0)


def redact_secrets(value: Any) -> Any:
    """Mask credential values inside anything recorded in a manifest.

    A provenance manifest is meant to be shared — attached to a review, a bug
    report, a paper — which is exactly why a credential must never reach one
    (issue #18).

    This is deliberately the *second* line of defence. SQL that configures a
    credential is refused before it runs (`sql_policy`), because redaction is a
    text scan without a parser and an adversarial audit escaped it four ways in
    minutes. What is left for this function is everything that reaches a
    manifest without being SQL at all: a signed URL in an input path, a
    connection string passed as a tool argument.

    The name is kept and only the value is masked, so the record still shows
    what ran; `parameters_redacted` on the record says it happened, because a
    manifest that quietly differs from what executed would be a worse bug than
    the leak. Applied to every ProvenanceRecord and every job-ledger row rather
    than at the call sites: a redaction a future engine can forget is not a
    redaction.

    Known limits, stated rather than implied: detection is name-based, so a
    secret passed as a bare positional value with no recognisable name is not
    detected, and neither is a URI that percent-encodes the colon of its own
    userinfo (`user%3Apass@host`).
    """
    if isinstance(value, str):
        masked = _URI_PASSWORD.sub(rf"\1:{REDACTED}@", value)
        masked = _URI_QUERY.sub(rf"\1{REDACTED}", masked)
        masked = _QUOTED_PAIR.sub(rf"\g<key>{_QUOTED_REDACTED}", masked)
        return _SECRET_ASSIGNMENT.sub(_mask_assignment, masked)
    if isinstance(value, dict):
        # The KEY is a name too. `{"AWS_SECRET_ACCESS_KEY": "AKIA..."}` used to
        # pass through untouched, because the scanner looks for `name=value`
        # INSIDE a string and here the name is not inside the string — it is
        # the key. The gap belongs to every dict a manifest carries, and
        # `environment` is simply the field that makes it obvious, holding
        # environment variables by definition.
        return {
            k: REDACTED if _SECRET_KEY.search(str(k)) else redact_secrets(v)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact_secrets(v) for v in value)
    return value


@dataclass
class InputRecord:
    path: str
    sha256: str
    crs: str | None = None
    # Which layer was read, for containers holding more than one. The spec asks
    # for it in exactly these words: "without it, an auditor holding a
    # five-layer container and this record cannot tell which layer produced the
    # numbers." Since #29 MapSmith knows the answer — it refuses containers
    # with no chosen layer — so leaving the field empty was recording ignorance
    # it no longer had.
    layer: str | None = None
    # Which argument of the operation read this input (spec draft.10,
    # `inputs[].argument`). The order of `inputs` is not significant, so for an
    # operation that reads two datasets in two roles this is the only place the
    # role survives: swapping values and weights changes every number and left
    # two records differing only in file names. Set where an operation reads
    # more than one dataset, with the name `verification[].argument` uses for
    # the same input; omitted from the record when unset.
    argument: str | None = None

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        crs: str | None = None,
        layer: str | None = None,
        argument: str | None = None,
    ) -> InputRecord:
        if layer is None:
            layer = _only_layer(path)
        return cls(
            path=posix_path(path),
            sha256=dataset_sha256(path),
            crs=crs,
            layer=layer,
            argument=argument,
        )


def _only_layer(path: str | Path) -> str | None:
    """The layer a reader took from a single-layer directory container, else None.

    A container's digest identifies the container, not the layer (spec section
    6, draft.9), and a record for a layer of it says which. An operation handed
    a single-layer `.gdb` reads its only layer without being told the name, and
    used to record no layer: the lineage walk then met a record for that very
    layer and stopped with "records claim this container's digest, but for
    other layers" -- false, it was the layer read (0.8.0 review). A multi-layer
    container without a chosen layer is refused before this runs (issue #29).
    """
    p = Path(path)
    if p.suffix.lower() != ".gdb" or not p.is_dir():
        return None
    from . import readers

    layers = readers.gpkg_layers(str(p))
    return layers[0] if layers and len(layers) == 1 else None


def posix_path(path: str | Path) -> str:
    """The path as the manifest records it: `/` as separator, on every host.

    A lineage record exists to be held next to someone else's. Storing
    ``str(path)`` gave a backslash path on Windows and a forward-slash one
    elsewhere, for the same run on the same bytes, so two correct manifests
    differed in a field that describes nothing about the computation, and any
    consumer keying on the path had two entries for one file (#30).

    Only the separator is normalised, and only on a host that has one:
    ``PurePath`` is ``PureWindowsPath`` on Windows and ``PurePosixPath``
    elsewhere, so a backslash arriving on Linux is left alone — there it is a
    legal character in a filename, and rewriting it would corrupt a real path.
    That is the right shape anyway: the normalisation happens on the only host
    that can produce the problem.

    The path is otherwise recorded as it was given. Rewriting an absolute path
    to a relative one, or the reverse, would misstate what actually ran.

    A URI is left exactly as given. `PurePath` collapses `//`, so
    `https://user:pw@host/x` came out as `https:/user:pw@host/x` -- and the
    redaction of credentials in a URI looks for `://`, so the password would
    have stayed in the record (found in the 0.7.0 audit; not reachable while
    remote paths are refused, which is why it was only ever latent).
    """
    text = str(path)
    if "://" in text:
        return text
    return PurePath(text).as_posix()


@dataclass
class ProvenanceRecord:
    operation: str
    parameters: dict[str, Any]
    inputs: list[InputRecord]
    # First among the defaulted fields on purpose: a reader meeting the record
    # needs the format version before anything else means anything.
    spec_version: str = SPEC_VERSION
    # `Any` and not `str`: since 2026-09-06 one value is a list of objects
    # (`x-mapsmith:inputs_reprojected`), and section 3.7 permits that on
    # purpose -- only `analysis_crs` and `reason` are strings there, because
    # the question a consumer most needs answered (`is_ballpark`) has to be a
    # boolean it can branch on. The annotation said `str` for a day.
    crs_decisions: dict[str, Any] = field(default_factory=dict)
    engine: dict[str, str] = field(default_factory=dict)
    verification: list[dict[str, Any]] = field(default_factory=list)
    # deterministic repair attempts (issue #3): empty unless something was fixed
    repairs: list[dict[str, Any]] = field(default_factory=list)
    # disclosures about how the inputs were handled before the engine saw them
    notes: list[str] = field(default_factory=list)
    # Section 3.8 of the specification: the configuration that influenced the
    # result and lives neither in the data nor in the call — a georeferencing
    # source, a GDAL variable that changes how a file is read, the presence of
    # a datum grid on this machine.
    #
    # It exists because `parameters` holds what the caller asked for and
    # `engine` holds what computed it, and neither holds the state of the
    # machine — which can change the number. The same thousand-metre square
    # measures 1,000,530.603 m2 or exactly 1,000,000 depending on a project
    # setting that appears in no argument and no output.
    #
    # **What goes in it is what a producer KNOWS influenced the result, never a
    # dump of the environment.** A record that listed forty variables would
    # bury the one that mattered, and the reader would learn to skip the field.
    # Empty or absent claims nothing, exactly like an absent `crs_decisions`.
    #
    # Argleton trap 030 is the measurement that made this concrete rather than
    # theoretical: a GeoTIFF and the `.aux.xml` beside it declare different
    # georeferencing, GDAL prefers the sidecar by documented design, and until
    # this field existed nothing in a MapSmith manifest could say which of the
    # two produced the number.
    environment: dict[str, str] = field(default_factory=dict)
    # `producer` is the spec's field for "the software that emitted this
    # record, as distinct from the engine that computed the result", and it is
    # now the only place MapSmith's version appears. A `mapsmith_version` of our
    # own invention sat beside it until 2026-09-09, unprefixed, at the top level
    # of the record -- where every neighbour belongs to the specification, so it
    # read as one of them. Two copies of one fact, and the one a stranger should
    # use was the other one. Kept for a while because manifests already on disk
    # carry it; removed because those files still carry it either way, and the
    # only thing the field decided was what we write from now on.
    producer: dict[str, str] = field(
        default_factory=lambda: {"name": "mapsmith", "version": __version__}
    )
    started_at: str = field(default_factory=_utcnow)
    finished_at: str | None = None
    # Set when redaction changed anything in this record — parameters, CRS
    # decisions, notes or an input path. The name predates the other three
    # fields being covered and is kept on purpose: manifests already published
    # carry it, and readers key on it. A manifest that silently differs from
    # what ran would be worse than the leak it prevents.
    parameters_redacted: bool = False

    def __post_init__(self) -> None:
        self._redact()

    def _redact(self) -> None:
        """Mask credentials in every field that can carry one. Idempotent.

        Not only `parameters`: a signed URL reaches a manifest as an input
        path, and a CRS decision or a note quotes the argument it was made
        about. Redacting one field and publishing the others would be a
        redaction in name only.

        Run at construction AND again in `write_for`, which is the single point
        where a manifest becomes a file. Construction alone was not enough and
        the gap was invisible: no engine passes `crs_decisions` or `notes` to
        the constructor — every one of them assigns after — so those two fields
        were never actually redacted on any shipped path, while SECURITY.md
        said they were. The test that covered them passed both as constructor
        arguments, a shape no caller uses: green, and proving nothing.

        Redacting twice costs nothing because masking an already-masked value
        is a no-op, and it means a field added later is covered without anyone
        having to remember this method exists.
        """
        safe_params = redact_secrets(self.parameters)
        safe_decisions = redact_secrets(self.crs_decisions)
        safe_notes = redact_secrets(self.notes)
        # An environment variable carries a credential as readily as a path
        # does — `AWS_SECRET_ACCESS_KEY` is an environment variable — so the
        # field joins the others here rather than being remembered later.
        safe_environment = redact_secrets(self.environment)
        safe_paths = [redact_secrets(i.path) for i in self.inputs]
        safe_layers = [
            redact_secrets(i.layer) if i.layer is not None else None for i in self.inputs
        ]
        safe_verification = redact_secrets(self.verification)
        safe_repairs = redact_secrets(self.repairs)
        changed = (
            safe_params != self.parameters
            or safe_decisions != self.crs_decisions
            or safe_notes != self.notes
            or safe_paths != [i.path for i in self.inputs]
            or safe_layers != [i.layer for i in self.inputs]
            or safe_verification != self.verification
            or safe_repairs != self.repairs
            or safe_environment != self.environment
        )
        self.parameters = safe_params
        self.crs_decisions = safe_decisions
        self.notes = safe_notes
        self.verification = safe_verification
        self.repairs = safe_repairs
        self.environment = safe_environment
        for record, path, layer in zip(self.inputs, safe_paths, safe_layers, strict=True):
            record.path = path
            record.layer = layer
        if changed:
            self.parameters_redacted = True

    def _record_environment(self) -> None:
        """Fill `environment` from the inputs, for anything that changed the answer.

        Today that means one thing: a raster georeferenced twice, where GDAL's
        documented preference for a `.aux.xml` sidecar decides the numbers and
        nothing else in the record could say so (Argleton trap 030).

        Costs a `stat` per input in the ordinary case — the sidecar check is a
        file-existence test that returns nothing when there is no second source.
        Anything already set by the operation is kept: an engine that knows
        something about its own environment knows it better than this does.
        """
        from . import grid

        # With one input its facts go on the record's `environment`, as they
        # always have. With several, each file's facts go on its own entry,
        # `inputs[].environment` (spec draft.10), and only process settings stay
        # on the record. Until 2026-09-25 every input's facts were merged into
        # one flat object: a weights raster with a sidecar beside values without
        # one produced `georeferencing_source: internal` next to the weights'
        # sidecar name, two statements about two files read as one (found by
        # the `conformita-manifest` review).
        self._input_environment: dict[int, dict[str, str]] = {}
        for index, entry in enumerate(self.inputs):
            try:
                found = grid.manifest_environment(entry.path)
            except Exception:  # noqa: BLE001, S112 — see below
                # An input that is not a raster has nothing to disambiguate, and
                # a failure to LOOK is not a finding. Swallowing cannot hide a
                # defect here: nothing downstream reads a value this did not set.
                continue
            if not found:
                continue
            if len(self.inputs) == 1:
                # One input: its facts are the run's, and the record is the
                # one every single-input manifest has always carried.
                for key, value in found.items():
                    self.environment.setdefault(key, value)
                continue
            # Several inputs (spec draft.10, section 3.8): a process setting --
            # unprefixed, the GDAL variables -- is a fact of the run and goes on
            # the record once; a fact MapSmith read off THIS file (`x-mapsmith:`)
            # goes on this input, the first one included. Until 2026-09-28 the
            # first input's file facts sat on the record, which the format reads
            # as true of every input, since the order of `inputs` means nothing
            # (found by the `conformita-manifest` review of draft.10).
            for key, value in found.items():
                if not key.startswith("x-mapsmith:"):
                    self.environment.setdefault(key, value)
            found = {k: v for k, v in found.items() if k.startswith("x-mapsmith:")}
            if found:
                safe = redact_secrets(found)
                # Said on the record, as every other redaction is: a manifest
                # that masked a value without saying so reads as the value.
                if safe != found:
                    self.parameters_redacted = True
                self._input_environment[index] = safe

    def add_verification(self, checks: list[Any]) -> ProvenanceRecord:
        """Attach deterministic check results (objects with .as_dict())."""
        self.verification.extend(c.as_dict() for c in checks)
        return self

    def add_repairs(self, attempts: list[dict[str, Any]]) -> ProvenanceRecord:
        """Attach deterministic repair attempts (see verify.repair_and_reverify)."""
        self.repairs.extend(attempts)
        return self

    def finish(self) -> ProvenanceRecord:
        self.finished_at = _utcnow()
        return self

    def write_for(self, output_path: str | Path, *, with_output_digest: bool = True) -> Path:
        """Write the manifest next to the output it describes.

        The record carries the OUTPUT's digest too, computed here — the one
        moment the final bytes certainly exist (verification and any repair
        have already run). Without it a consumer cannot check that the sidecar
        describes the bytes next to it, and the record could not become the
        predicate of an in-toto attestation, whose subject requires a digest.

        There are TWO ways a record ends up without `output`, and the flag is
        the rarer one. The common way is the condition a few lines down: the
        file does not exist, because the engine died before writing it. The
        flag, `with_output_digest=False`, has exactly one caller —
        `verify.audit_on_failure`, and there it is a retry: the digest is
        attempted first and dropped only if hashing raises. Hashing is the only
        part of this method that reads a file the crashed engine may still hold
        open, so it is the part most likely to raise — and section 3.1 says a
        manifest MUST be written even then.

        Section 6 of the specification is the other side of this: a walk that
        resolves a chain by digest will meet records of runs that did not
        finish, including one written after a PARTIAL write, whose digest is of
        partial bytes and is perfectly accurate. That is why the walker there is
        required to read `verification[]` and not just follow digests. A
        record without `output` is valid (the schema allows its absence) and
        useless only for checking bytes; a record that was never written is
        useless for everything.
        """
        # Section 3.8, filled here for the same reason redaction runs here: this
        # is the single point where a manifest becomes a file. `verify.audited`
        # looked like the place — it is where the invariants are made
        # unmissable — and it is not: seventeen writers of fifty-seven build their
        # record by hand, and they are concentrated in raster, which is exactly
        # where georeferencing decides the numbers. A hook a quarter of the
        # writers bypass is not a hook.
        #
        # And the same sentence is why the empty-verification case is caught
        # here. The specification wants two things that met in one place and
        # got one at the other's expense: §3 requires at least one check ("a
        # manifest with no checks at all is a log entry wearing a manifest's
        # clothes") and §4 requires a record for every dataset written.
        # `verify.audited` closed that on its own path on 2026-09-05 by
        # recording the absence as a failed check — but those seventeen writers
        # never reach it, and `verify.enforce([])` does not raise, so a caller
        # was handed `success` beside a manifest BOTH implementations reject.
        # That is strictly worse than what `audited` used to do, which was at
        # least loud.
        #
        # Appending rather than raising, and the direction is the whole point:
        # raising here would recreate the defect one level down, because the
        # dataset is already on disk by the time any manifest is written. What
        # stops this from becoming a quiet excuse is not politeness, it is
        # `test_no_shipped_operation_reaches_the_absent_verification_fallback`:
        # if a real operation ever lands here, the suite goes red rather than
        # shipping a manifest whose only content is "nobody looked".
        if not self.verification:
            from .verify import verification_absent

            self.verification = [verification_absent(self.operation).as_dict()]
        self._record_environment()
        self._redact()
        record = asdict(self)
        if with_output_digest and Path(output_path).exists():
            # After `inputs`, where a reader expects it; through the same
            # redaction as everything else, because an output path can carry a
            # signed URL exactly like an input path can.
            #
            # `crs` since 1.0.0-draft.4 of the specification, and it is written
            # HERE for the same reason the digest is: this is the one moment the
            # final bytes certainly exist. Section 3.7 has said since draft.2
            # that the output CRS belongs in `output`, and until draft.4 there
            # was nowhere here to put it -- so this producer had put it in
            # `crs_decisions`, under `x-mapsmith:round_trip.output_crs`, where
            # the code writing it had not yet written the file. That made it
            # false on every path that failed in between, and in the worst case
            # it described a stale output left by an earlier run whose digest
            # this method then computed. Removed on 2026-09-07; this is the same
            # fact stated from the only place that can state it truthfully.
            #
            # And it is what the FILE declares, not what the operation intended:
            # `expect_crs` is already the subject of `crs_matches`, so a second
            # copy of the expectation would add nothing a consumer could not
            # already read. This is the other side of that comparison.
            from .verify import UNKNOWN_CRS, probe_crs

            found = probe_crs(str(output_path))
            try:
                digest = dataset_sha256(output_path)
            except ValueError as exc:
                # Two files match one shapefile member (`out.dbf` beside
                # `out.DBF`): section 3.3 forbids recording a digest, and
                # raising here would leave the dataset without its manifest.
                record.setdefault("notes", []).append(
                    redact_secrets(f"output digest not recorded: {exc}")
                )
                digest = None
            fields = {"path": posix_path(output_path), "sha256": digest}
            if found != UNKNOWN_CRS:
                # OMITTED and not null when unknown, deliberately. The schema
                # allows null, and null would be the stronger statement -- "we
                # looked, and this file declares no CRS". `probe_crs` cannot
                # support it: it answers `unknown` both for a file that declares
                # none and for one it failed to read, and the specification says
                # a producer that cannot compute this SHOULD omit it rather than
                # predict it. Writing null would turn "we could not tell" into
                # "there is none", which is the class of defect this format
                # exists to remove.
                fields["crs"] = found
            entry = redact_secrets(fields)
            if digest is not None:
                record = {}
                for key, value in asdict(self).items():
                    record[key] = value
                    if key == "inputs":
                        record["output"] = entry
        # Added only where there is something to say, so that a record with a
        # single raster -- every one written before 2026-09-25 -- is unchanged.
        for index, found in getattr(self, "_input_environment", {}).items():
            # `environment` on the input since spec draft.10; until then this was
            # `x-mapsmith:environment`, a key only a reader of MapSmith knew.
            record["inputs"][index]["environment"] = found
        # Unset roles are omitted, not written as null: a single-input record is
        # unchanged, and null would claim the operation named no argument.
        for entry in record["inputs"]:
            if entry.get("argument") is None:
                entry.pop("argument", None)
        manifest_path = Path(f"{output_path}.provenance.json")
        manifest_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return manifest_path


def read_provenance(output_path: str | Path) -> dict[str, Any]:
    """Read the lineage manifest of a MapSmith output, if present."""
    manifest_path = Path(f"{output_path}.provenance.json")
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"No provenance manifest found for {output_path}. "
            "Either it was not produced by MapSmith or the manifest was moved."
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))
