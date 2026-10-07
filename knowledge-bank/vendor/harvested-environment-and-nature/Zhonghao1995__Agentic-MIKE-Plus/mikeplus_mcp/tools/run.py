"""Simulation run tool."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_run",
            description=(
                "Run a MIKE+ simulation headless via the MIKE 1D engine. Runs the model's "
                "active simulation unless 'simulation' is given. Returns the result file "
                "paths plus the engine log tail. Needs MIKE+ installed + a valid license. "
                "ALWAYS run on a COPY of the model (mikeplus has no undo)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sqlite": {"type": "string", "description": "Path to the MIKE+ .sqlite to run (use a copy)."},
                    "simulation": {"type": "string", "description": "Optional simulation setup id (msm_Project MUID). Default: the active simulation."},
                    "timeout_s": {"type": "number", "description": "Max seconds to wait for the engine (default 1800)."},
                },
                "required": ["sqlite"],
            },
            handler=lambda a: call_worker(
                "run_worker",
                {"sqlite": a["sqlite"], "simulation": a.get("simulation")},
                timeout=float(a.get("timeout_s", 1800)),
            ),
        )
    ]
