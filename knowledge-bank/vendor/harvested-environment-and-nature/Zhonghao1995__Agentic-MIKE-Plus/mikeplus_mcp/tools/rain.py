"""Rainfall input tool (no license needed)."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_rain_to_dfs0",
            description=(
                "Turn a timestamped rainfall CSV (design storm, gauge record) into a MIKE+ "
                "rainfall .dfs0 (Rainfall Intensity, mm/h, mean-step-backward: the same shape as "
                "DHI's example rain files). Accepts intensity (mm/h) or depth per step (mm, "
                "converted). Verifies the file reads back and reports total depth / peak. Point a "
                "model's rainfall boundary at the result, or pass it to the plot tools as rain_dfs0. "
                "No license needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "csv": {"type": "string", "description": "CSV with a time column and a value column."},
                    "out_dfs0": {"type": "string", "description": "Output .dfs0 path."},
                    "time_col": {"type": "string", "description": "Time column name (default: first column)."},
                    "value_col": {"type": "string", "description": "Value column name (default: second column)."},
                    "unit": {"type": "string", "description": "'mm/h' (intensity, default) or 'mm' (depth per step)."},
                    "item_name": {"type": "string", "description": "dfs0 item name (default 'Rainfall')."},
                },
                "required": ["csv", "out_dfs0"],
            },
            handler=lambda a: call_worker(
                "rain_worker",
                {"csv": a["csv"], "out_dfs0": a["out_dfs0"], "time_col": a.get("time_col"),
                 "value_col": a.get("value_col"), "unit": a.get("unit"),
                 "item_name": a.get("item_name")},
                timeout=300,
            ),
        )
    ]
