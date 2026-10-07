"""Model import tool (needs MIKE+ + license)."""
from .._types import ToolDef
from ..runtime.worker import call_worker


def get_tools():
    return [
        ToolDef(
            name="mike_import_swmm",
            description=(
                "Create a NEW MIKE+ .sqlite model by importing an EPA SWMM .inp (kind='swmm', "
                "default) or an EPANET .inp (kind='epanet') through mikeplus. This is the bridge "
                "from an INP builder (e.g. SWMMCanada) into MIKE+: import, then mike_model_info -> "
                "mike_run. Returns element counts and the simulation setups found. Refuses to "
                "overwrite unless overwrite=true. Needs MIKE+ + license."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "inp": {"type": "string", "description": "Path to the SWMM or EPANET .inp."},
                    "out_sqlite": {"type": "string", "description": "Path of the new MIKE+ .sqlite to create."},
                    "kind": {"type": "string", "enum": ["swmm", "epanet"], "description": "Input format (default 'swmm')."},
                    "overwrite": {"type": "boolean", "description": "Replace out_sqlite if it exists (default false)."},
                    "srid": {"type": "integer", "description": "Optional EPSG code for the new database."},
                    "projection": {"type": "string", "description": "Optional projection WKT string."},
                },
                "required": ["inp", "out_sqlite"],
            },
            handler=lambda a: call_worker(
                "import_worker",
                {"inp": a["inp"], "out_sqlite": a["out_sqlite"], "kind": a.get("kind", "swmm"),
                 "overwrite": a.get("overwrite", False), "srid": a.get("srid"),
                 "projection": a.get("projection")},
                timeout=900,
            ),
        )
    ]
