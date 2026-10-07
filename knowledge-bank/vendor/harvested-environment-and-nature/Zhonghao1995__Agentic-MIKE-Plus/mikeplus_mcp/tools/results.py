"""Result-reading tools (no license needed)."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_results_list",
            description=(
                "List what is inside a MIKE+ .res1d: quantities (WaterLevel/Discharge/...), "
                "element counts (nodes/reaches/structures/catchments) with sample ids, and the "
                "time range. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {"res1d": {"type": "string", "description": "Path to a .res1d file."}},
                "required": ["res1d"],
            },
            handler=lambda a: call_worker("results_worker", {"action": "list", "res1d": a["res1d"]}, timeout=300),
        ),
        ToolDef(
            name="mike_results_summary",
            description=(
                "Per-quantity peak summary (peak value, element, chainage, time) from a MIKE+ "
                ".res1d. No license needed. NOTE: this is the GLOBAL max over the whole run, which "
                "can fall in the warm-up/initial-condition period (a base-flow value near t=0) "
                "rather than the storm peak — pass skip_hours to exclude an initial window and "
                "always check peak_time."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "quantities": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional subset, e.g. ['Discharge','WaterLevel'].",
                    },
                    "skip_hours": {
                        "type": "number",
                        "description": "Exclude the first N hours (warm-up) before finding peaks.",
                    },
                },
                "required": ["res1d"],
            },
            handler=lambda a: call_worker(
                "results_worker",
                {"action": "summary", "res1d": a["res1d"],
                 "quantities": a.get("quantities"), "skip_hours": a.get("skip_hours")},
                timeout=600,
            ),
        ),
        ToolDef(
            name="mike_results_read",
            description=(
                "Extract one time series (a quantity at an element) from a MIKE+ .res1d as "
                "times+values (downsampled to max_points). No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "quantity": {"type": "string", "description": "e.g. 'Discharge' or 'WaterLevel'."},
                    "element": {"type": "string", "description": "Element id (node id, or reach/link id, optionally with chainage)."},
                    "max_points": {"type": "integer", "description": "Cap on returned points (default 5000)."},
                },
                "required": ["res1d", "quantity", "element"],
            },
            handler=lambda a: call_worker(
                "results_worker",
                {
                    "action": "read",
                    "res1d": a["res1d"],
                    "quantity": a["quantity"],
                    "element": a["element"],
                    "max_points": a.get("max_points", 5000),
                },
                timeout=600,
            ),
        ),
        ToolDef(
            name="mike_results_compare",
            description=(
                "Compare two MIKE+ .res1d results (A = baseline, B = scenario) for one quantity. "
                "With 'element': delta peak (value/%/time shift), delta volume for flows, RMSE/NSE "
                "of B vs A. Without 'element': peak change for EVERY element of that quantity, "
                "ranked by |delta| (answers 'where did my edit matter?'). No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d_a": {"type": "string", "description": "Baseline .res1d."},
                    "res1d_b": {"type": "string", "description": "Scenario .res1d."},
                    "quantity": {"type": "string", "description": "e.g. 'Discharge' or 'WaterLevel'."},
                    "element": {"type": "string", "description": "Element id for a single-series comparison; omit to rank all elements."},
                    "skip_hours": {"type": "number", "description": "Exclude the first N hours (warm-up) from both results."},
                    "top_n": {"type": "integer", "description": "How many elements to return in ranked mode (default 10)."},
                    "label_a": {"type": "string", "description": "Name for A (default 'baseline')."},
                    "label_b": {"type": "string", "description": "Name for B (default 'scenario')."},
                },
                "required": ["res1d_a", "res1d_b", "quantity"],
            },
            handler=lambda a: call_worker(
                "results_worker",
                {"action": "compare", "res1d_a": a["res1d_a"], "res1d_b": a["res1d_b"],
                 "quantity": a["quantity"], "element": a.get("element"),
                 "skip_hours": a.get("skip_hours"), "top_n": a.get("top_n"),
                 "label_a": a.get("label_a"), "label_b": a.get("label_b")},
                timeout=900,
            ),
        ),
        ToolDef(
            name="mike_results_flooding",
            description=(
                "Which nodes flood? Peak water level vs ground level for every node in a MIKE+ "
                ".res1d: flooded nodes ranked by exceedance (with peak time and type), how many "
                "exceed the critical level, and the nodes closest to flooding. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "skip_hours": {"type": "number", "description": "Exclude the first N hours (warm-up)."},
                    "top_n": {"type": "integer", "description": "Max flooded nodes to list (default 20)."},
                    "include_outlets": {"type": "boolean", "description": "Also assess Outlet nodes (default false: their level is the boundary, not flooding)."},
                },
                "required": ["res1d"],
            },
            handler=lambda a: call_worker(
                "results_worker",
                {"action": "flooding", "res1d": a["res1d"],
                 "skip_hours": a.get("skip_hours"), "top_n": a.get("top_n"),
                 "include_outlets": a.get("include_outlets", False)},
                timeout=600,
            ),
        ),
    ]
