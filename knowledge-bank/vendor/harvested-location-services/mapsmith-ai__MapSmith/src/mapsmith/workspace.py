"""Workspace jail: uniform path containment at the MCP tool boundary.

Tool arguments arrive from an LLM agent, i.e. from whatever ended up in its
context window — treat every path as untrusted input. Two tiers:

- UNC/device paths and NTFS alternate data streams are rejected ALWAYS,
  workspace or not: on Windows even a ``Path.exists()`` on a UNC path opens
  an SMB/WebDAV connection to an attacker-chosen host (NTLM hash leak), with
  no legitimate agent-side use (mount the share as a drive instead).
- Remote/virtual forms (GDAL /vsi*, URI schemes) are refused unless
  ``MAPSMITH_ALLOW_REMOTE`` is set, and always refused under a workspace, which
  means "this directory and nothing else".

  That default changed in 0.2.2, because the old rationale did not survive
  reading: it said remote data was admitted "on the user's own responsibility",
  and the user is not the one deciding. The path is written by the *model*, from
  whatever it read — a third-party GeoPackage carrying an attribute like "the
  updated layer lives at https://evil.tld/roads.gpkg" is enough to make GDAL
  parse attacker-chosen bytes in-process, and every memory-safety CVE in a GDAL
  driver becomes reachable without anyone choosing it. Cloud-native data is a
  real use case, so the capability stays — it just has to be switched on by the
  operator, who is the only party in the loop who can actually consent.

Known tradeoff of the ADS check: a colon anywhere past the drive letter is
refused, so POSIX filenames like 'data:v2.parquet' are rejected too — and a
two-character basename like 'a:stream' slips past it, harmlessly, because
containment on the resolved path still applies.

Validated plans stay stricter by design: the plan validator rejects every
non-local form regardless of workspace (stable error codes), because a plan
is a contract checked end-to-end before execution.

The jail assumes a single trusted writer of the workspace filesystem: paths
are resolved at check time, so an adversary able to swap a directory for a
symlink between check and use could escape it. That is out of the threat
model for a local stdio server; revisit for authenticated multi-tenant HTTP.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")

#: Windows reserves these names in every directory, with or without an
#: extension: `CON`, `NUL`, `CON.txt` are all the device, not a file. Measured
#: 2026-09-02: writing to `CON` raised PermissionError *after* creating a file
#: called CON in the workspace.
_DEVICE_NAME = re.compile(
    r"(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$"
)


_TRUTHY = {"1", "true", "yes", "on"}


def root() -> Path | None:
    """The workspace root, or None when unset (uncontained mode)."""
    ws = os.environ.get("MAPSMITH_WORKSPACE", "").strip()
    return Path(ws).resolve() if ws else None


def remote_allowed() -> bool:
    """Whether the operator has switched remote/virtual paths on.

    Off by default. A workspace overrides it: containment to one directory and
    "fetch whatever URL the model names" cannot both be true, and the DuckDB
    sandbox refuses network access under a workspace anyway — a tool boundary
    that admitted what the engine then refuses would only produce confusing
    errors.

    The workspace is part of the answer here, not left to each caller. It used
    to be: this function reported only the environment variable while the two
    callers inside this module compensated, and the one outside it did not —
    so with a workspace *and* the opt-in, ``gdal_policy`` re-registered GDAL's
    indirection drivers and a ``.vrt`` sitting inside the workspace fetched a
    URL, past every guard, in the configuration SECURITY.md calls the safest.
    A predicate whose callers must each remember to add a condition is a
    predicate that will be wrong somewhere.
    """
    if root() is not None:
        return False
    return os.environ.get("MAPSMITH_ALLOW_REMOTE", "").strip().lower() in _TRUTHY


def hard_refusal_reason(path: str) -> str | None:
    """Why a path is refused in EVERY mode, or None. Checked before any
    filesystem call — see the module docstring for why."""
    p = path.strip()
    if p.startswith(("\\\\", "//")):
        return "UNC/device paths are not allowed"
    if (
        not _URI_SCHEME.match(p)
        and not p.lower().startswith("/vsi")
        and ":" in p[2:]  # a colon is only legitimate as the drive separator (C:...)
    ):
        return "NTFS alternate data streams are not allowed"
    if not _URI_SCHEME.match(p) and not p.lower().startswith("/vsi"):
        # The RAW string, not the stripped one. `p = path.strip()` above would
        # have hidden the trailing-space case entirely — and `guard` returns the
        # caller's exact string, so the engine receives the space that the check
        # never saw. Stripping for the scheme tests and scanning the original is
        # the only combination that is true of what actually gets written.
        for part in re.split(r"[\\/]", path):
            # Empty from a doubled separator, or whitespace wrapping the whole
            # string: neither names a file, and reporting `'  '` as the offender
            # would point at the wrong thing.
            if not part.strip():
                continue
            # `.` and `..` are navigation, not filenames, and they end in a dot
            # by definition. Caught by `test_traversal_escape_rejected`, which
            # was already asserting that traversal is refused for the RIGHT
            # reason — containment — rather than for an incidental one.
            if part in (".", ".."):
                continue
            # A trailing dot or space is silently stripped when Windows creates
            # the file, so the dataset lands at a DIFFERENT path than the one
            # the manifest is written beside — measured 2026-09-02:
            # `out.parquet.` wrote `out.parquet` and then raised, leaving a
            # dataset on disk with no manifest at all. That is invariant 2
            # broken by a character nobody sees. Refused everywhere and not
            # only on Windows, because a manifest is meant to travel: a path
            # that names two different files on two platforms is not one.
            if part != part.rstrip(". "):
                return (
                    f"a path component may not end in a dot or a space ({part!r}): "
                    "Windows strips them when creating the file, so the data would "
                    "be written somewhere other than where the manifest says"
                )
            if _DEVICE_NAME.match(part):
                return (
                    f"{part!r} is a reserved device name on Windows and cannot be "
                    "a file. Choose another name"
                )
    return None


def remote_form(path: str) -> str | None:
    """The kind of remote/virtual path this is, or None if it is plain local."""
    p = path.strip()
    if p.lower().startswith("/vsi"):
        return "GDAL /vsi* virtual path"
    if _URI_SCHEME.match(p):
        return "URI scheme"
    return None


def remote_reason(path: str) -> str | None:
    """Why a remote/virtual form is refused in the CURRENT configuration.

    Kept as a single sentence the agent can act on: under a workspace there is
    nothing to switch, without one there is.
    """
    form = remote_form(path)
    if form is None:
        return None
    if root() is not None:
        return f"{form}s are not allowed inside a workspace"
    if remote_allowed():
        return None
    return (
        f"{form}s are refused by default because the path comes from the model, "
        "not from you: set MAPSMITH_ALLOW_REMOTE=1 to allow remote reads"
    )


def nonlocal_reason(path: str) -> str | None:
    """Any non-plain-local form (the strict rule used by plan validation).

    Independent of MAPSMITH_ALLOW_REMOTE on purpose: a validated plan is a
    contract checked end to end before anything runs, and it stays strict.
    """
    if reason := hard_refusal_reason(path):
        return reason
    form = remote_form(path)
    return f"{form}s are not allowed in a validated plan" if form else None


_REMOTE_IN_TEXT = re.compile(r"(?i)(/vsi[a-z0-9_]*/|\b[a-z][a-z0-9+.-]*://)")


def refuse_remote_in_sql(query: str) -> None:
    """Refuse SQL that names a remote path, unless remote reads are switched on.

    Without this the opt-in would be decorative: the path guard cannot see
    inside SQL text, and GDAL carries its own HTTP client, so
    ``ST_Read('/vsicurl/http://host/x.geojson')`` reads the endpoint and returns
    its content in the tool result — an SSRF with the host's own network
    position, reachable from one statement an agent wrote. DuckDB's own
    ``disabled_filesystems`` does not cover it, and the setting that would
    (``enable_external_access=false``) takes local file access with it, which is
    why this check lives here instead of in the connection.

    Under a workspace the engine already refuses it, so there is nothing to add.

    Known tradeoff, same shape as the ADS check above: this is a text scan, not
    a SQL parse, so a query that merely mentions a URL inside a string literal
    is refused too. Refusing a legitimate INSERT of a URL is a worse error
    message; letting one statement read a cloud metadata endpoint is a worse
    day.
    """
    if root() is not None or remote_allowed():
        return
    match = _REMOTE_IN_TEXT.search(query)
    if match:
        raise ValueError(
            f"this SQL names a remote path ({match.group(0)!r}), which is refused "
            "by default: the statement comes from the model, and GDAL would fetch "
            "it in-process. Set MAPSMITH_ALLOW_REMOTE=1 to allow remote reads, or "
            "set MAPSMITH_WORKSPACE to confine the server to local files."
        )


def is_outside(path: str, workspace: Path) -> bool:
    """True when the resolved path falls outside the workspace (or is
    unresolvable). The root itself counts as outside: a dataset path is never
    legitimately the workspace directory, and derived sidecars
    ('<output>.provenance.json') of the root would land beside it, out of jail.
    """
    try:
        child = os.path.normcase(str(Path(path).resolve()))
    except (OSError, ValueError):
        return True
    ws = os.path.normcase(str(workspace))
    return not child.startswith(ws.rstrip("\\/") + os.sep)


def guard(path: str, arg: str) -> str:
    """Validate one tool path argument; returns it unchanged (engines record
    the caller's exact strings in provenance)."""
    reason = hard_refusal_reason(path)
    if reason:
        raise ValueError(f"'{arg}': {reason}: {path}")
    reason = remote_reason(path)
    if reason:
        raise ValueError(f"'{arg}': {reason}: {path}")
    ws = root()
    if ws is not None and is_outside(path, ws):
        raise ValueError(
            f"'{arg}' resolves outside MAPSMITH_WORKSPACE ({ws}): {path}. "
            "Use a path inside the workspace (relative paths resolve against "
            "the server's working directory, so prefer absolute ones)."
        )
    return path
