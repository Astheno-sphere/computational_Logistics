"""The Esri backend: ONE operation routed, run in ArcGIS Pro's own Python.

One and not seventy-two, deliberately. What this proves is that the path exists
end to end — stack chosen, licence discovered, tool run, fallback recorded — on
an operation whose equivalence with the open source stack is **measured** rather
than assumed (D-056 point 5). Adding a second is then a table entry, a probe,
and a call to `stacks.route` in the operation.

That last part is the correction. This module used to declare three, and
`available_for` reported all three usable, while `stacks.route` was called from
exactly one place. With the Esri stack requested, `centroid_layer` and
`dissolve_layer` ran on the open source stack and **no manifest note recorded
the substitution** — the one thing this design says never happens quietly, on
the operation where the vendor drops every attribute. A table entry is a promise
that requesting the stack reaches it, so the table now holds only what does, and
`test_every_declared_esri_tool_is_actually_routed` keeps it honest in both
directions.

The measurement of 2026-08-30 covered three, and what it found is more
interesting than a match.
Compared across the two stacks on the same fixture, through the same reader,
into the same container:

    buffer      geometry identical  · ArcGIS adds BUFF_DIST, ORIG_FID
    centroids   geometry identical  · ArcGIS adds ORIG_FID
    dissolve    geometry identical  · ArcGIS adds Id and DROPS every attribute

**The geometry deltas match on all three. The schemas do not match on any of
them**, and the dissolve difference is not cosmetic: a pipeline that dissolves
and then reads a column gets the column on one stack and nothing on the other.
That is silent data loss on substitution, which is the precise failure a
provenance product exists to prevent.

So the measurement does not license a silent swap — it licenses a **recorded**
one, and it is the reason `record.notes` carries the schema delta rather than a
reassuring sentence. The first version of the comparison omitted the column
fields and reported all three as matching; the difference was there all along
and the check was not looking at it.

Two caveats remain, written here rather than discovered later: three pairs are
the easy case, chosen because a method that cannot recognise these recognises
nothing; and a fixture of two squares cannot find geodesic-against-planar
buffers or invalid-geometry handling. Those are Argleton's job.

## The boundary

ArcPy lives in ArcGIS Pro's conda environment, so MapSmith cannot import it:
every call is a subprocess that reads and writes files. That is the same shape
invariant 7 imposes on QGIS for a licensing reason, arrived at here for a
technical one.
"""

from __future__ import annotations

import json
import pathlib
import tempfile
from typing import Any

from .. import readers, stacks, workspace

#: What each operation needs from the Esri side, and what it is called there.
#: The qualified name matters: on a real installation a substantial minority of
#: tools share a bare name with a tool in another toolbox.
#: Keyed by MapSmith's CATALOGUE names, not by convenient ones: the router
#: passes the operation as the catalogue spells it, and a different key here
#: means falling back every time with the wrong reason — "no such tool"
#: instead of the real one. It failed exactly that way once.
TOOLS = {
    "buffer_layer": {"toolbox": "Analysis Tools", "tool": "Buffer"},
}

#: Measured against the open source stack on 2026-08-30 and **not routed**: the
#: operations do not call `stacks.route`, so requesting the Esri stack runs them
#: on the open source one. Kept here as the record of what was measured, and
#: deliberately out of `TOOLS` so that `available_for` cannot report a tool no
#: caller reaches. Wiring one means a `TOOLS` entry, a probe action, and the
#: route call in the operation itself.
MEASURED_NOT_ROUTED = {
    "centroid_layer": {"toolbox": "Data Management Tools", "tool": "FeatureToPoint"},
    "dissolve_layer": {"toolbox": "Data Management Tools", "tool": "Dissolve"},
}

#: Runs inside Pro's Python. It PRODUCES and reports; it does not describe what
#: it produced. Describing is done by MapSmith's own reader, because letting
#: each vendor describe its own output is the thing measured not to work — and
#: because two readers on one file gave two different answers on 2026-08-30.
PROBE = '''
import json, os, sys

try:
    import arcpy
except Exception as failure:
    print(json.dumps({"status": "no_arcpy", "detail": str(failure)[:300]}))
    raise SystemExit(0)

arcpy.env.overwriteOutput = True
request = json.loads(open(sys.argv[1], encoding="utf-8").read())
# A GeoPackage layer, addressed the way ArcPy addresses one: the container path
# plus the layer name. A plain .gpkg path is refused (ERROR 000732), and
# GeoParquet is not readable at all — measured 2026-08-30. The bridge is a
# GeoPackage and deliberately NOT a shapefile, which truncates field names to
# ten characters in silence: `convert_format` refuses to write one for exactly
# that reason, and a back door cannot use what the front door refuses.
source = os.path.join(os.path.abspath(request["input_path"]), request["input_layer"])
# The output container has to exist first: ArcPy writes a layer INTO a
# GeoPackage, it does not make one on the way (ERROR 000210).
container = os.path.abspath(request["output_path"])
arcpy.management.CreateSQLiteDatabase(container, "GEOPACKAGE")
target = os.path.join(container, request["output_layer"])

actions = {
    # The distance in the LAYER'S OWN UNIT, not in metres. Buffer's PLANAR
    # method converts a linear unit into the CRS's unit, so "100 Meters" on a
    # CRS in US survey feet buffers by 328.08 feet while the open source branch
    # buffers by 100 — a 3.28x difference from the same call, with the same
    # sentence in the manifest and every check green. "Unknown" tells Buffer to
    # use the input's own linear unit, which is what MapSmith's parameter means.
    "buffer_layer": lambda: arcpy.analysis.Buffer(
        source, target,
        "%s %s" % (request["distance_meters"], request.get("distance_unit", "Unknown"))),
    "centroid_layer": lambda: arcpy.management.FeatureToPoint(source, target, "CENTROID"),
    "dissolve_layer": lambda: arcpy.management.Dissolve(source, target),
}
try:
    actions[request["operation"]]()
    print(json.dumps({"status": "ok", "output_path": target}))
except Exception as failure:
    message = str(failure)
    # The distinction D-056 point 4 requires. A tier that does not include a
    # tool is not a product that cannot do the thing, and collapsing the two
    # would be the error we corrected once already, made in reverse.
    unlicensed = "not licensed" in message.lower() or "000824" in message
    print(json.dumps({
        "status": "not_in_this_licence" if unlicensed else "failed",
        "detail": message[:300],
    }))
'''

def available_for(operation: str) -> tuple[bool, str, str]:
    """Can the Esri stack run this here? Returns (yes, reason, detail).

    Answered from metadata on disk, so asking costs nothing. `reason` is one of
    the three constants in `stacks`, never a single word for all of them.
    """
    if operation not in TOOLS:
        return False, stacks.NO_SUCH_TOOL, "MapSmith has no Esri binding for it yet"
    if not stacks.installed()["esri"]["available"]:
        return False, stacks.NO_SUCH_TOOL, "ArcGIS Pro is not installed on this machine"

    wanted = TOOLS[operation]
    key = f"{wanted['toolbox']}/{wanted['tool']}"
    entry = stacks.esri_inventory()["tools"].get(key)
    if entry is None:
        return False, stacks.NO_SUCH_TOOL, f"{key} is not in this installation"
    if entry["extensions"]:
        # The metadata says an extension is required. Whether this licence has
        # it is only knowable by taking a seat, so the honest answer here is
        # "ask the engine", and the engine's refusal is what gets recorded.
        return True, "", f"{key} declares extensions {entry['extensions']}"
    return True, "", f"{key}, {entry['level']} level, no extension required"


def run(operation: str, source: Any, arguments: dict[str, Any],
        timeout: int = 900) -> dict[str, Any]:
    """Run one operation on the Esri stack, and hand back a GeoDataFrame.

    The frame, not a path: the caller writes the real output with MapSmith's own
    writer, so the canonical format stays canonical and the verification runs
    over a file MapSmith produced. It also enforces the rule the fingerprint
    work learned the hard way — one reader. Letting each engine describe its own
    output is what does not work, and reading it with two readers gave two
    different answers on the same file.

    Never raises for a licence refusal: that is an outcome to act on, and an
    exception would make it indistinguishable from a crash.
    """
    # Inside the workspace when there is one, exactly as the other subprocess
    # engine does it. The bridge file is a COPY of the caller's layer, so a
    # system temp directory would put their data outside the boundary
    # SECURITY.md promises -- with no path argument anywhere for the jail at
    # the MCP boundary to catch, because MapSmith chose this path itself.
    root = workspace.root()
    with tempfile.TemporaryDirectory(
        prefix="mapsmith-esri-", dir=str(root) if root else None
    ) as workdir:
        area = pathlib.Path(workdir)
        source_file, target_file = area / "in.gpkg", area / "out.gpkg"
        source.to_file(source_file, driver="GPKG", layer="data")

        probe_file = area / "probe.py"
        probe_file.write_text(PROBE, encoding="utf-8")
        request_file = area / "request.json"
        request_file.write_text(json.dumps({
            "operation": operation,
            "input_path": str(source_file), "input_layer": "main.data",
            "output_path": str(target_file), "output_layer": "result",
            **arguments,
        }), encoding="utf-8")

        # `cwd` inside the same scratch the bridge already built: anything
        # ArcPy writes relative to its working directory then lands inside
        # the workspace with the rest, instead of wherever the server was
        # started from.
        done = stacks.esri_run(
            str(probe_file), [str(request_file)], timeout=timeout, cwd=str(area)
        )
        lines = [r for r in (done.stdout or "").strip().splitlines() if r.strip()]
        if not lines:
            return {"status": "failed", "detail": (done.stderr or "no output")[-300:]}
        try:
            outcome = json.loads(lines[-1])
        except ValueError:
            return {"status": "failed", "detail": lines[-1][:300]}
        if outcome.get("status") != "ok":
            return outcome
        # Through the one reader, not `gpd.read_file`: that is the discipline
        # from #28, and it counts double here — what the fingerprint work
        # learned is that one file read by two readers gives two answers.
        outcome["frame"] = readers.read_named_layer(str(target_file), "result")
        return outcome


def engine_info() -> dict[str, Any]:
    """What produced the numbers, for the manifest.

    The version comes from the installation on disk rather than from a string
    we keep here: a record that names a version MapSmith guessed is worse than
    one that says it does not know.
    """
    version = None
    marker = stacks.PRO_ROOT / "bin" / "ArcGISPro.exe"
    if marker.exists():
        version = _version_from_install()
    return {"name": "ArcGIS Pro", "version": version or "unknown"}


def _version_from_install() -> str | None:
    for candidate in (stacks.PRO_ROOT / "Resources" / "Version" / "Version.json",):
        if candidate.exists():
            try:
                return json.loads(candidate.read_text(encoding="utf-8")).get("Version")
            except (OSError, ValueError):
                return None
    return None
