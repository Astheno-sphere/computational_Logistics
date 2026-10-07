"""Parameter read/modify tools (the 'edit the model' capability)."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_get_values",
            description=(
                "Read parameter values from a MIKE+ table (e.g. msm_Link, msm_Node, "
                "msm_Catchment) for the given columns and optional element MUIDs. Read-only. "
                "Needs MIKE+ + license. Use this to identify current parameter values."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sqlite": {"type": "string"},
                    "table": {"type": "string", "description": "Table name, e.g. 'msm_Link', 'msm_Node', 'msm_Catchment'."},
                    "columns": {"type": "array", "items": {"type": "string"}, "description": "Columns to read, e.g. ['Diameter','Manning']. Omit for all."},
                    "muids": {"type": "array", "items": {"type": "string"}, "description": "Optional element ids to filter."},
                },
                "required": ["sqlite", "table"],
            },
            handler=lambda a: call_worker(
                "params_worker",
                {"action": "get", "sqlite": a["sqlite"], "table": a["table"],
                 "columns": a.get("columns"), "muids": a.get("muids")},
                timeout=300,
            ),
        ),
        ToolDef(
            name="mike_set_values",
            description=(
                "Set parameter values in a MIKE+ table for specific element MUIDs (e.g. change a "
                "pipe Diameter or Manning roughness). Returns before/after for the affected rows. "
                "MUTATES the database — ALWAYS use a copy. Needs MIKE+ + license. Pass 'muids' to "
                "scope the change; set all=true only when you intend to change every row."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sqlite": {"type": "string"},
                    "table": {"type": "string"},
                    "values": {"type": "object", "description": "Column-value pairs to set, e.g. {\"Diameter\": 0.4}."},
                    "muids": {"type": "array", "items": {"type": "string"}, "description": "Element ids to update."},
                    "all": {"type": "boolean", "description": "Update ALL rows (only if muids omitted). Use with care."},
                },
                "required": ["sqlite", "table", "values"],
            },
            handler=lambda a: call_worker(
                "params_worker",
                {"action": "set", "sqlite": a["sqlite"], "table": a["table"],
                 "values": a["values"], "muids": a.get("muids"), "all": a.get("all", False)},
                timeout=300,
            ),
        ),
    ]
