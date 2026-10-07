"""Standalone closed-form test of the validation gate (no GABench deps)."""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
# stub the GABench import so only the pure functions load
sys.modules["agents"] = types.ModuleType("agents")
sys.modules["agents.plan_and_react"] = types.ModuleType("agents.plan_and_react")
sys.modules["agents.plan_and_react"].PlanAgent = object

from ab_extension import validate_plan_steps  # noqa: E402

INDEX = {
    "buffer_vector": {
        "properties": {
            "input_path": {"type": "string"},
            "distance": {"type": "number"},
            "output_path": {"type": "string"},
        },
        "required": ["input_path", "distance", "output_path"],
    },
    "clip_vector": {
        "properties": {
            "input_path": {"type": "string"},
            "mask_path": {"type": "string"},
            "output_path": {"type": "string"},
        },
        "required": ["input_path", "mask_path", "output_path"],
    },
}

broken = [
    {"step_id": 1, "tool": "bufer_vector", "arguments": {}},  # typo -> UNKNOWN_TOOL
    {"step_id": 1, "tool": "buffer_vector",  # duplicate id
     "arguments": {"input_path": "a.shp", "distance": "cinquecento",  # WRONG_TYPE
                   "output_path": "b.shp", "sorpresa": 1}},  # UNKNOWN_ARGUMENT
    {"step_id": 2, "tool": "clip_vector",  # mask_path missing -> MISSING_ARGUMENT
     "arguments": {"input_path": "b.shp", "output_path": "c.shp"}},
]
issues = validate_plan_steps(broken, INDEX)
for i in issues:
    print(f"[{i['code']}] step {i['step_id']}: {i['message'][:80]}")
codes = sorted({i["code"] for i in issues})
assert codes == ["DUPLICATE_STEP_ID", "MISSING_ARGUMENT", "UNKNOWN_ARGUMENT",
                 "UNKNOWN_TOOL", "WRONG_TYPE"], codes

good = [
    {"step_id": 1, "tool": "buffer_vector",
     "arguments": {"input_path": "a.shp", "distance": 500, "output_path": "b.shp"}},
    {"step_id": 2, "tool": "clip_vector",
     "arguments": {"input_path": "b.shp", "mask_path": "m.shp", "output_path": "c.shp"}},
]
assert validate_plan_steps(good, INDEX) == []
assert validate_plan_steps([], INDEX)[0]["code"] == "EMPTY_PLAN"
print()
print("GATE OK: correct codes on the broken plans, zero false positives on the good plan")
