"""Scenario tool (needs MIKE+ + license)."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_set_scenario",
            description=(
                "Activate an EXISTING MIKE+ scenario by name so that mike_run executes it. Verifies "
                "the activation persisted by re-opening the database (errors loudly if not) and "
                "reports, per alternative group, whether the scenario has its own alternative or "
                "shares Base. Does not create scenarios: mikeplus cannot write table edits into a "
                "scenario's own alternatives, so what-if variants must be made on a MODEL COPY "
                "(mike-compare skill). MUTATES the database's active state — use a copy. Needs "
                "MIKE+ + license. List scenarios with mike_model_info first."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sqlite": {"type": "string"},
                    "scenario": {"type": "string", "description": "Scenario name (or id) to activate, e.g. 'Base'."},
                },
                "required": ["sqlite", "scenario"],
            },
            handler=lambda a: call_worker(
                "scenario_worker", {"sqlite": a["sqlite"], "scenario": a["scenario"]}, timeout=300,
            ),
        )
    ]
