"""Model inspection tool."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_model_info",
            description=(
                "Open a MIKE+ .sqlite model and report the active simulation/scenario/model, "
                "unit system, the list of simulation setups (msm_Project), scenarios, and "
                "element counts (nodes/links/catchments). Read-only. Needs MIKE+ + license."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sqlite": {"type": "string", "description": "Path to the MIKE+ .sqlite model database."}
                },
                "required": ["sqlite"],
            },
            handler=lambda a: call_worker("model_worker", {"sqlite": a["sqlite"]}, timeout=300),
        )
    ]
