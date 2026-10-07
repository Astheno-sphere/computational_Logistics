"""Plotting tools (house style: Arial 12, ticks inward, SI, no title). No license."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_plot_rain_flow",
            description=(
                "Render a stacked two-panel rainfall-runoff figure (rain inverted on top, flow "
                "on bottom) in the house style. Flow comes from a .res1d element; rainfall "
                "optional from a .dfs0. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "element": {"type": "string", "description": "Reach/link or node id for the flow series."},
                    "quantity": {"type": "string", "description": "Flow quantity (default 'Discharge')."},
                    "rain_dfs0": {"type": "string", "description": "Optional rainfall .dfs0 for the top panel."},
                    "out_png": {"type": "string", "description": "Output PNG path."},
                },
                "required": ["res1d", "element", "out_png"],
            },
            handler=lambda a: call_worker(
                "plot_worker",
                {
                    "action": "rain_flow",
                    "res1d": a["res1d"],
                    "element": a["element"],
                    "quantity": a.get("quantity", "Discharge"),
                    "rain_dfs0": a.get("rain_dfs0"),
                    "out_png": a["out_png"],
                },
                timeout=600,
            ),
        ),
        ToolDef(
            name="mike_plot_timeseries",
            description=(
                "Render a single-panel time-series plot (a quantity at an element) in the house "
                "style. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "quantity": {"type": "string"},
                    "element": {"type": "string"},
                    "out_png": {"type": "string"},
                },
                "required": ["res1d", "quantity", "element", "out_png"],
            },
            handler=lambda a: call_worker(
                "plot_worker",
                {
                    "action": "timeseries",
                    "res1d": a["res1d"],
                    "quantity": a["quantity"],
                    "element": a["element"],
                    "out_png": a["out_png"],
                },
                timeout=600,
            ),
        ),
        ToolDef(
            name="mike_plot_network",
            description=(
                "Render a network layout map of a MIKE+ model from a .res1d — reaches/pipes as "
                "lines, nodes as points, equal-aspect, house style. Good for an overview figure. "
                "No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "out_png": {"type": "string"},
                },
                "required": ["res1d", "out_png"],
            },
            handler=lambda a: call_worker(
                "plot_worker",
                {"action": "network", "res1d": a["res1d"], "out_png": a["out_png"]},
                timeout=600,
            ),
        ),
        ToolDef(
            name="mike_plot_compare",
            description=(
                "Overlay the same series from two MIKE+ .res1d results (A = baseline dashed grey, "
                "B = scenario solid) in the house style; optional inverted hyetograph on top from a "
                ".dfs0. Use after an edit/scenario re-run to show the effect. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d_a": {"type": "string", "description": "Baseline .res1d."},
                    "res1d_b": {"type": "string", "description": "Scenario .res1d."},
                    "quantity": {"type": "string", "description": "Default 'Discharge'."},
                    "element": {"type": "string", "description": "Reach/link or node id."},
                    "out_png": {"type": "string"},
                    "label_a": {"type": "string", "description": "Legend name for A (default 'baseline')."},
                    "label_b": {"type": "string", "description": "Legend name for B (default 'scenario')."},
                    "rain_dfs0": {"type": "string", "description": "Optional rainfall .dfs0 for the top panel."},
                    "skip_hours": {"type": "number", "description": "Exclude the first N hours (warm-up)."},
                },
                "required": ["res1d_a", "res1d_b", "element", "out_png"],
            },
            handler=lambda a: call_worker(
                "plot_worker",
                {"action": "compare", "res1d": a["res1d_a"], "res1d_b": a["res1d_b"],
                 "quantity": a.get("quantity", "Discharge"), "element": a["element"],
                 "out_png": a["out_png"], "label_a": a.get("label_a"), "label_b": a.get("label_b"),
                 "rain_dfs0": a.get("rain_dfs0"), "skip_hours": a.get("skip_hours")},
                timeout=900,
            ),
        ),
        ToolDef(
            name="mike_plot_profile",
            description=(
                "Longitudinal profile along a chain of reaches/pipes from a MIKE+ .res1d: bed/invert, "
                "pipe crown, ground level and the MAX water level envelope vs chainage, with node "
                "boundaries marked. Give the ordered reach ids, or from_node + to_node and the "
                "chain is found automatically. Returns the max level and min freeboard. No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "res1d": {"type": "string"},
                    "reaches": {"type": "array", "items": {"type": "string"}, "description": "Ordered reach/link ids, upstream to downstream."},
                    "from_node": {"type": "string", "description": "Start node id (used with to_node when 'reaches' is omitted)."},
                    "to_node": {"type": "string", "description": "End node id."},
                    "out_png": {"type": "string"},
                    "skip_hours": {"type": "number", "description": "Exclude the first N hours (warm-up) from the max envelope."},
                },
                "required": ["res1d", "out_png"],
            },
            handler=lambda a: call_worker(
                "plot_worker",
                {"action": "profile", "res1d": a["res1d"], "reaches": a.get("reaches"),
                 "from_node": a.get("from_node"), "to_node": a.get("to_node"),
                 "out_png": a["out_png"], "skip_hours": a.get("skip_hours")},
                timeout=900,
            ),
        ),
    ]
