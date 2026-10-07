"""Which geoprocessing stack this machine has, and which one the caller chose.

MapSmith runs on its own engines — GeoPandas, GDAL, rasterio, Whitebox, DuckDB,
all open source — and that is the default. A caller who has ArcGIS Pro installed
can ask for it instead, and then Esri is used for what it does and the open
source stack for what it does not (D-056).

Three things make this more than a switch, and all three are measured rather
than assumed:

* **The available tool set is a property of the machine, not of the product.**
  Which tools a licence reaches depends on its level and on which extensions it
  carries, and both differ between two installations of the same version. So
  what the other stack can do is discovered at runtime, from the installation in
  front of us, rather than baked into a table here. (The counts behind that
  sentence were measured on one licensed machine and stay in this project's
  private notes: a measurement of somebody else's product does not belong in
  this repository, whatever it says.)
* **"Esri does not do it" is three different situations** — no such tool, this
  licence does not include it, or it needs an online service — and they lead a
  reader to three different decisions. They are never collapsed into one word.
* **Nothing is substituted in silence.** When a fallback happens the manifest
  records which engine actually produced the numbers and why the preferred one
  did not. A product that sells provenance and quietly swaps engines is selling
  the opposite.

What that adds up to today is one routed operation, `buffer_layer`: the set that
calls :func:`route` is the set that can be substituted, and everything else runs
on the open source stack whatever the variable says. Said here because the
opposite reading was a real defect — see `engines/esri.py` — and because a
docstring claiming a general property of three-line wiring is how it recurs.

## Why both foreign stacks are subprocesses

QGIS and GRASS are GPL, so MapSmith talks to them through `qgis_process` and
files — never an in-process import (invariant 7). ArcPy turns out to need the
same shape for an unrelated reason: it lives in ArcGIS Pro's own conda
environment, a different interpreter from the one MapSmith runs in, so
`import arcpy` is not available to us even if we wanted it. One discipline, two
reasons, and the same boundary: another process, files on disk, JSON back.
"""

from __future__ import annotations

import functools
import json
import os
import pathlib
import shutil
import subprocess
from typing import Any

#: The two the caller can ask for. `opensource` is the default because it needs
#: no licence and works on every machine MapSmith installs on.
STACKS = ("opensource", "esri")
DEFAULT_STACK = "opensource"

#: Where ArcGIS Pro puts its Python and its tool metadata. Both are read-only
#: here: the metadata costs nothing, and knowing a product is installed is not
#: the same as taking a licence seat.
PRO_ROOT = pathlib.Path(r"C:\Program Files\ArcGIS\Pro")
PRO_PYTHON = PRO_ROOT / "bin" / "Python" / "envs" / "arcgispro-py3" / "python.exe"
PRO_TOOLBOXES = PRO_ROOT / "Resources" / "ArcToolBox" / "toolboxes"

#: `product` in a tool's metadata is the minimum licence LEVEL, not an
#: extension: 100 Basic, 200 Standard, 300 Advanced. Extensions are a separate
#: field, and a tool can need both.
LICENCE_LEVELS = {"100": "Basic", "200": "Standard", "300": "Advanced"}

#: The three reasons a preferred stack cannot run something. Separate on
#: purpose: one is permanent, one is a purchase, and one is a choice the caller
#: may have made deliberately.
NO_SUCH_TOOL = "no_such_tool"
NOT_IN_THIS_LICENCE = "not_in_this_licence"
NEEDS_ONLINE_SERVICE = "needs_online_service"


def requested() -> str:
    """The stack the caller asked for, from `MAPSMITH_STACK`.

    An unknown value is not silently treated as the default: a caller who
    misspells `esri` would otherwise get open source results while believing
    they had asked for something else, which is the quiet kind of wrong.
    """
    asked = (os.environ.get("MAPSMITH_STACK") or DEFAULT_STACK).strip().lower()
    if asked not in STACKS:
        raise ValueError(
            f"MAPSMITH_STACK is {asked!r}; it must be one of {list(STACKS)}. "
            "Leaving it unset selects 'opensource', which needs no licence."
        )
    return asked


def _qgis_process() -> str | None:
    """`qgis_process`, if this machine has one.

    Looked up on PATH first so a caller can point at the build they mean, then
    in the usual install locations. Never imported: invariant 7.
    """
    for name in ("qgis_process", "qgis_process-qgis-ltr", "qgis_process-qgis"):
        found = shutil.which(name)
        if found:
            return found
    for root in sorted(pathlib.Path(r"C:\Program Files").glob("QGIS *"), reverse=True):
        for name in ("qgis_process-qgis-ltr.bat", "qgis_process-qgis.bat"):
            candidate = root / "bin" / name
            if candidate.exists():
                return str(candidate)
    return None


@functools.lru_cache(maxsize=1)
def installed() -> dict[str, Any]:
    """What is on this machine, without taking a licence.

    Deliberately cheap: a path check and, for Esri, reading files the installer
    left on disk. Whether a licence is actually *available* is a separate and
    more expensive question — see :func:`esri_capabilities`.
    """
    qgis = _qgis_process()
    return {
        "opensource": {
            "available": True,  # MapSmith's own engines ship with it
            "qgis_process": qgis,
            "qgis": bool(qgis),
        },
        "esri": {
            "available": PRO_PYTHON.exists() and PRO_TOOLBOXES.exists(),
            "python": str(PRO_PYTHON) if PRO_PYTHON.exists() else None,
            "toolboxes": str(PRO_TOOLBOXES) if PRO_TOOLBOXES.exists() else None,
        },
    }


@functools.lru_cache(maxsize=1)
def esri_inventory() -> dict[str, Any]:
    """Every installed tool with the licence level and extensions it needs.

    Read from the metadata the installer wrote to disk. No import of the
    scripting module, no licence seat, no geoprocessing, no online service —
    the same footing as reading the documentation.
    """
    if not installed()["esri"]["available"]:
        return {"tools": {}, "count": 0}
    tools: dict[str, dict[str, Any]] = {}
    for toolbox_dir in PRO_TOOLBOXES.glob("*.tbx"):
        for area in toolbox_dir.glob("*.tool"):
            content = area / "tool.content"
            if not content.exists():
                continue
            try:
                data = json.loads(content.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            # QUALIFIED key. The bare tool name loses a large minority of the
            # installed tools, because the same name exists in several
            # toolboxes, and a dictionary collapses them
            # without a word. It is also how the scripting module addresses
            # them — toolbox plus name, never the name alone.
            tools[f"{toolbox_dir.stem}/{area.stem}"] = {
                "toolbox": toolbox_dir.stem,
                "name": area.stem,
                "level": LICENCE_LEVELS.get(data.get("product", "100"), "Basic"),
                "extensions": data.get("extensions") or [],
            }
    return {"tools": tools, "count": len(tools)}


def describe() -> dict[str, Any]:
    """What to tell the caller when a session opens.

    The point of saying it at the start rather than at the first failure: a
    caller who asked for Esri on a machine without it should learn that before
    they plan five steps around it.
    """
    present = installed()
    chosen = requested()
    report = {
        "requested": chosen,
        "opensource": {"available": True, "qgis": present["opensource"]["qgis"]},
        "esri": {"available": present["esri"]["available"]},
    }
    if chosen == "esri" and not present["esri"]["available"]:
        report["warning"] = (
            "MAPSMITH_STACK=esri, and ArcGIS Pro was not found on this machine. "
            "MapSmith does not ship it: it calls what is installed, with your "
            "licence. Every operation will run on the open source stack, and each "
            "manifest will record that it did."
        )
    elif chosen == "esri":
        inventory = esri_inventory()
        report["esri"]["tools_installed"] = inventory["count"]
        # What is ROUTED, not what was measured: the table of measured pairs and
        # the set of operations that consult the router came apart once, and the
        # caller was told about a route two of them did not take. Read from the
        # engine so this sentence cannot drift from the wiring again.
        from .engines import esri as esri_engine

        routed = sorted(esri_engine.TOOLS)
        report["esri"]["routed_operations"] = routed
        report["esri"]["note"] = (
            f"{len(routed)} operation(s) consult this stack today "
            f"({', '.join(routed)}); every other operation runs on the open "
            "source stack whatever MAPSMITH_STACK says. For the routed ones, "
            "how many actually run depends on your licence level and "
            "extensions, which is a property of this machine rather than of the "
            "product — and whatever cannot run falls back to the open source "
            "stack with the substitution named in the manifest."
        )
    if not present["opensource"]["qgis"]:
        report["opensource"]["note"] = (
            "qgis_process was not found, so QGIS algorithms are unavailable. "
            "MapSmith's own engines are unaffected."
        )
    return report


def fallback_note(operation: str, reason: str, detail: str = "") -> str:
    """The sentence that goes in the manifest when a substitution happened.

    Written here and not at each call site so that every fallback reads the
    same, and so that the three reasons cannot quietly become one.
    """
    explanation = {
        NO_SUCH_TOOL: "the preferred stack has no tool for this operation",
        NOT_IN_THIS_LICENCE: (
            "the preferred stack has a tool for this, and this licence does not "
            "include it — which is a fact about the licence, not about the product"
        ),
        NEEDS_ONLINE_SERVICE: (
            "the preferred stack can do this only through an online service, and "
            "MapSmith runs local geoprocessing only"
        ),
    }.get(reason, reason)
    tail = f" ({detail})" if detail else ""
    return (
        f"{operation} ran on the open source stack although 'esri' was requested: "
        f"{explanation}{tail}. The numbers in this record were produced by the "
        "engine named in `engine`, not by the one that was asked for."
    )


def esri_run(
    script: str,
    arguments: list[str],
    timeout: int = 900,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run a script inside ArcGIS Pro's Python.

    A subprocess for two independent reasons, and it is worth knowing both:
    ArcPy lives in Pro's own conda environment, so `import arcpy` is not
    available to the interpreter MapSmith runs in; and keeping foreign engines
    behind a process boundary is already the rule for the GPL ones.

    **`cwd` is not decoration.** A child inherits the parent's working
    directory, and an engine that writes a scratch file relative to it puts
    that file wherever the server happened to be started -- outside the
    workspace SECURITY.md says nothing writes outside of. That is exactly
    how `contour_lines` leaked four files for a release before anyone
    noticed, and Whitebox is in-process while this is a process boundary,
    which makes it easier to get wrong and impossible to see. The caller
    passes the scratch directory it already made inside the workspace.
    """
    if not installed()["esri"]["available"]:
        raise RuntimeError(
            "ArcGIS Pro was not found on this machine. MapSmith calls what is "
            "installed with your licence; it does not ship or redistribute it."
        )
    return subprocess.run(
        [str(PRO_PYTHON), script, *arguments],
        capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace", check=False, cwd=cwd,
    )


def route(operation: str) -> dict[str, Any]:
    """Which stack runs this operation, and what the record has to say about it.

    Always returns a decision — never raises — because "the preferred stack
    cannot do this" is an ordinary outcome that the caller acts on, not a
    failure. Raising would make a licence refusal indistinguishable from a
    crash, and those want opposite responses.

    The `note` is present only when a substitution actually happened. A record
    that carried a fallback sentence on every operation would train its reader
    to skip the line, which is the same as not writing it.
    """
    chosen = requested()
    if chosen == "opensource":
        return {"stack": "opensource", "substituted": False}

    from .engines import esri  # imported here: it reads Pro's metadata

    usable, reason, detail = esri.available_for(operation)
    if usable:
        return {"stack": "esri", "substituted": False, "detail": detail}
    return {
        "stack": "opensource",
        "substituted": True,
        "reason": reason,
        "detail": detail,
        "note": fallback_note(operation, reason, detail),
    }
