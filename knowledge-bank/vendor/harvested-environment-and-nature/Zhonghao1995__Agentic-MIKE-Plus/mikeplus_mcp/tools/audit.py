"""Provenance manifest tool (pure Python, runs in-process; no license, no DHI imports)."""
import json
from pathlib import Path

from .._types import ToolDef
from ..contracts import manifest as mf


def _write_manifest(a: dict) -> dict:
    try:
        from importlib.metadata import version
        pkg_version = version("mikeplus-mcp")
    except Exception:
        pkg_version = None
    doc = mf.build_manifest(
        case=a.get("case"), model=a.get("model"), inputs=a.get("inputs"),
        results=a.get("results"), figures=a.get("figures"), run=a.get("run"),
        edits=a.get("edits"), tool_calls=a.get("tool_calls"), notes=a.get("notes"),
        version=pkg_version,
    )
    out = Path(a["out_json"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    missing = mf.missing_files(doc)
    return {"ok": True, "manifest": str(out), "missing_files": missing,
            "n_files": len(doc["inputs"]) + len(doc["results"]) + len(doc["figures"]) + (1 if doc["model"] else 0),
            "run_status": doc["run"].get("status"), "created_utc": doc["created_utc"]}


def get_tools():
    return [
        ToolDef(
            name="mike_manifest_write",
            description=(
                "Write a provenance manifest (JSON) for one modelling step: the model + input + "
                "result + figure files each with a sha256, the mike_run QA status, the edits made, "
                "the tool calls, and free notes. Call it at the end of a run so the run can be "
                "audited or re-compared later. Reports any referenced file that is missing. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "out_json": {"type": "string", "description": "Where to write the manifest (e.g. runs/<case>/manifest.json)."},
                    "case": {"type": "string", "description": "Short case name."},
                    "model": {"type": "string", "description": "The .sqlite that was run (the copy)."},
                    "inputs": {"type": "array", "items": {"type": "string"}, "description": "Input files (rain .dfs0, hotstart, ...)."},
                    "results": {"type": "array", "items": {"type": "string"}, "description": "Result files (.res1d) from mike_run."},
                    "figures": {"type": "array", "items": {"type": "string"}, "description": "PNG figures produced."},
                    "run": {"type": "object", "description": "The mike_run return value (its QA fields are kept)."},
                    "edits": {"type": "array", "items": {"type": "object"}, "description": "mike_set_values returns, or {table, muids, values} records."},
                    "tool_calls": {"type": "array", "items": {"type": "object"}, "description": "Ordered {tool, args, ok} records."},
                    "notes": {"type": "string", "description": "Free-text notes / the plain-language goal."},
                },
                "required": ["out_json"],
            },
            handler=_write_manifest,
        )
    ]
