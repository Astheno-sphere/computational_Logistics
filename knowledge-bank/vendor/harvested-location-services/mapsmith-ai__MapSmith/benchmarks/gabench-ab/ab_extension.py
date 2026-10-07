"""MapSmith x GABench A/B/C extension: typed plans, validation gate, enforced plans.

The three arms share EVERYTHING except one step each:
- arm A: TypedPlanAgent emits a typed plan -> straight to the solver
- arm B: TypedPlanAgent emits a typed plan -> static validation against the
  live tool registry (unknown tool / missing / unknown / mistyped arguments,
  malformed steps) -> on errors the planner receives the machine-readable
  issues and repairs its plan (max 2 rounds) -> solver
- arm C: same plan, same gate as B -> EnforcedExecutor runs the plan exactly as
  written, with no model in the execution loop at all

A->B isolates the gate; B->C isolates who executes. Arm C is the configuration
MapSmith actually ships (`execute_plan`): the validated plan *is* the
trajectory, so a repaired plan cannot be re-improvised away by the solver.

No GABench source file is modified: we subclass and re-wire. Logs keep the
upstream history format so GABench's deterministic evaluator
(evaluation/step_by_step.py) runs unchanged on our .jsonl output.

Run from the GABench repo root (config.yaml/.env resolution).
"""

from __future__ import annotations

import asyncio
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _paths import gabench_root  # noqa: E402

# required=False: the gate's pure functions are importable without the
# checkout (test_gate.py stubs the upstream agent import).
sys.path.insert(0, str(gabench_root(required=False)))

from agents.plan_and_react import PlanAgent  # noqa: E402

TYPED_PLANNER_PROMPT = """
You are a lead geospatial analyst.
Break the user request into a sequence of executable tool calls.

Available tools (name, arguments):
{tools}

Working Protocol:
Use the following format strictly:

Thought: [Analyze the user request and the available tools]
Plan:
```json
[
    {{
        "step_id": 1,
        "tool": "[exact tool name from the list]",
        "arguments": {{"arg_name": "value"}},
        "purpose": "[one line: why this step]"
    }},
    ...
]
```

Constraint Checklist:
1. The plan must be logical and sequential.
2. Every step MUST name one tool from the list and provide its arguments.
3. Use exact argument names as documented. Use file paths produced by
   earlier steps where needed.
4. Output MUST be a strictly valid JSON list wrapped in a markdown code block.

Begin!
"""

REPAIR_MESSAGE = """Your plan failed static validation. Fix ONLY the reported problems and output the full corrected plan in the same JSON format.

Validation errors:
{errors}
"""


FULL_DOC_CHARS = 700


def tool_signature_lines(tools: list[Any], full_docs: bool = False) -> str:
    """Compact per-tool signature lines from the MCP inputSchema.

    The compact form keeps the name, the typed arguments and the FIRST LINE of
    the description. That drops the `Args:` block, which is where the
    per-argument rules live — `output_name: Output filename (must end with
    .tif)` among them — so neither planner nor solver is ever told them. It is
    applied identically to every arm, so comparisons hold, but it is also one
    concrete piece of what an improvising solver recovers from an error message
    and an enforced plan cannot.

    `full_docs=True` keeps the whole description instead (capped), which is what
    the arm measuring "was the planner underinformed?" needs.
    """
    lines = []
    for tool in tools:
        name = getattr(tool, "name", None) or tool.get("name")
        schema = getattr(tool, "inputSchema", None) or tool.get("inputSchema") or {}
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = set(schema.get("required", []) if isinstance(schema, dict) else [])
        args = []
        for arg, spec in props.items():
            kind = spec.get("type", "any") if isinstance(spec, dict) else "any"
            mark = "" if arg in required else "?"
            args.append(f"{arg}{mark}: {kind}")
        desc = (getattr(tool, "description", None) or tool.get("description", "") or "")
        if full_docs:
            desc = " ".join(desc.split())[:FULL_DOC_CHARS]
        else:
            desc = desc.split("Args:")[0].split("Returns:")[0].strip().split("\n")[0][:110]
        lines.append(f"- {name}({', '.join(args)}) — {desc}")
    return "\n".join(lines)


def build_tool_index(tools: list[Any]) -> dict[str, dict[str, Any]]:
    index = {}
    for tool in tools:
        name = getattr(tool, "name", None) or tool.get("name")
        schema = getattr(tool, "inputSchema", None) or tool.get("inputSchema") or {}
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        required = list(schema.get("required", []) if isinstance(schema, dict) else [])
        index[name] = {"properties": props, "required": required}
    return index


_JSON_TYPES = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def validate_plan_steps(
    steps: list[dict[str, Any]], tool_index: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    """Static validation of a typed plan against the live tool registry.

    Mirrors MapSmith's validate_plan philosophy: stable machine-actionable
    error codes the planner can act on, nothing executed.
    """
    issues: list[dict[str, str]] = []

    def issue(code: str, step: Any, message: str) -> None:
        issues.append({"code": code, "step_id": str(step), "message": message})

    if not isinstance(steps, list) or not steps:
        return [{"code": "EMPTY_PLAN", "step_id": "-", "message": "the plan has no steps"}]
    seen_ids = set()
    for raw in steps:
        if not isinstance(raw, dict):
            issue("MALFORMED_STEP", "-", f"step is not an object: {raw!r}")
            continue
        sid = raw.get("step_id", "-")
        if sid in seen_ids:
            issue("DUPLICATE_STEP_ID", sid, f"step_id {sid} is used more than once")
        seen_ids.add(sid)
        tool = raw.get("tool")
        if not tool:
            issue("MISSING_TOOL", sid, "step has no 'tool' field")
            continue
        if tool not in tool_index:
            close = difflib.get_close_matches(tool, list(tool_index), n=3, cutoff=0.6)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            issue("UNKNOWN_TOOL", sid, f"tool '{tool}' does not exist.{hint}")
            continue
        spec = tool_index[tool]
        arguments = raw.get("arguments")
        if not isinstance(arguments, dict):
            issue("MALFORMED_ARGUMENTS", sid, "'arguments' must be an object")
            continue
        for req in spec["required"]:
            if req not in arguments:
                issue("MISSING_ARGUMENT", sid,
                      f"tool '{tool}': required argument '{req}' is missing")
        for arg, value in arguments.items():
            if spec["properties"] and arg not in spec["properties"]:
                issue("UNKNOWN_ARGUMENT", sid,
                      f"tool '{tool}': unknown argument '{arg}'; "
                      f"declared: {sorted(spec['properties'])}")
                continue
            prop = spec["properties"].get(arg, {})
            expected = _JSON_TYPES.get(prop.get("type"))
            if expected is None:
                continue
            bad_bool = isinstance(value, bool) and bool not in expected
            if bad_bool or not isinstance(value, expected):
                issue("WRONG_TYPE", sid,
                      f"tool '{tool}': argument '{arg}' should be "
                      f"{prop.get('type')}, got {type(value).__name__}")
    return issues


_PATH_SUFFIXES = (
    ".tif", ".tiff", ".geojson", ".json", ".shp", ".gpkg", ".parquet", ".csv",
    ".graphml", ".pkl", ".nc", ".png", ".jpg", ".jpeg", ".kml", ".gpx", ".zip",
    ".las", ".laz", ".txt", ".xlsx",
)


def _looks_like_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    v = value.replace("\\", "/").lower()
    return "/" in v or v.endswith(_PATH_SUFFIXES) or bool(STEP_REFERENCE.match(value))


def _input_path_strings(key: str, value: Any):
    """The values of one argument that name an input dataset.

    Convention read off the benchmark's own reference toolchains: 458 arguments
    across 83 names end in `_path`/`_paths`, and the map-composition tools take
    `layers`, a list of objects carrying the layer's source. Output naming goes
    through `output_name` and is deliberately never treated as an input.

    Inside a layer object the source key is NOT fixed: the reference toolchains
    write `data`, and the planner we run writes `path`. Guessing the key name
    would have made the flow check silently blind to every map step — caught on
    the first live task of the first arm-D run — so anything path-shaped inside
    a layer counts, whatever it is called.
    """
    if key == "layers" and isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                if _looks_like_path(entry):
                    yield entry
            elif isinstance(entry, dict):
                for nested in entry.values():
                    if _looks_like_path(nested):
                        yield nested
        return
    if not key.endswith(("_path", "_paths", "_file", "_files")):
        return
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                yield entry


def _normalize(path: str) -> str:
    return path.replace("\\", "/").lstrip("./").lower()


def _basename(path: str) -> str:
    return _normalize(path).rsplit("/", 1)[-1]


def validate_plan_flow(
    steps: list[dict[str, Any]],
    exists: Callable[[str], bool] | None = None,
    output_dir: str = "output",
) -> list[dict[str, str]]:
    """Does every step read something that exists, or that an earlier step wrote?

    This is the check the name-and-type gate does not do, and the one whose
    absence made the enforced arm stop on 74 of 75 runs: a step declares
    `output_name: "x.tif"`, the next reads `raster_path: "x.tif"`, and the file
    is at `output/x.tif`. An improvising solver recovers by reading the tool's
    reply; an enforced plan cannot. MapSmith's own validator refuses the same
    shapes (UNKNOWN_REFERENCE, FORWARD_REFERENCE, PREFER_REFERENCE, input-file
    existence), so this is that contract transplanted onto GABench.

    Outputs are registered AFTER a step's inputs are checked, which is what
    makes a forward reference an error rather than an accident.
    """
    if exists is None:
        exists = lambda p: Path(p).exists()  # noqa: E731 — injected in tests
    issues: list[dict[str, str]] = []
    produced: dict[str, str] = {}  # basename -> step_id that writes it
    seen_ids: list[str] = []

    for position, raw in enumerate(steps, 1):
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("step_id", position))
        arguments = raw.get("arguments")
        if isinstance(arguments, dict):
            for key, value in arguments.items():
                for path in _input_path_strings(key, value):
                    match = STEP_REFERENCE.match(path)
                    if match:
                        if match.group(1) not in seen_ids:
                            issues.append({
                                "code": "UNKNOWN_REFERENCE", "step_id": sid,
                                "message": f"'{key}' points at {path}, which is not "
                                           "an earlier step",
                            })
                        continue
                    base = _basename(path)
                    if base in produced:
                        expected = f"{output_dir}/{base}"
                        if _normalize(path) != _normalize(expected):
                            issues.append({
                                "code": "PREFER_OUTPUT_PATH", "step_id": sid,
                                "message": f"'{key}' is '{path}', but step "
                                           f"{produced[base]} writes that file into the "
                                           f"output directory: use '{expected}'",
                            })
                        continue
                    if not exists(path):
                        issues.append({
                            "code": "INPUT_NOT_FOUND", "step_id": sid,
                            "message": f"'{key}' is '{path}', which does not exist and "
                                       "is not produced by any earlier step",
                        })
        seen_ids.append(sid)
        if isinstance(arguments, dict):
            name = arguments.get("output_name")
            if isinstance(name, str) and name:
                produced[_basename(name)] = sid
    return issues


def make_compact_solver(solve_cls):
    """Factory: a solver whose system prompt embeds compact tool signatures
    instead of the raw tool objects (148k chars -> ~26k, the observed cost
    driver at ~$1.70/task). Applied to BOTH arms: identical change, the gate
    stays the only experimental variable. Declared in the write-up.
    """
    class _Compact(solve_cls):
        async def run(self, input):  # noqa: A002 - upstream signature
            if not self.history:
                if not self.tools:
                    await self.load_tools()
                self.sys_prompt = self.sys_prompt.format(
                    tools=tool_signature_lines(self.tools), subtasks=self.subtasks
                )
                self.history.append(
                    {"role": "system",
                     "content": [{"type": "text", "text": self.sys_prompt}]}
                )
            self.history.append(
                {"role": "user", "content": [{"type": "text", "text": input}]}
            )
            async for chunk in super()._run_loop():
                yield chunk

    return _Compact


class TypedPlanAgent(PlanAgent):
    """PlanAgent that emits typed steps (tool + arguments) instead of prose.

    `full_docs=True` gives the planner the tools' complete descriptions instead
    of one truncated line. It is a separate arm, not a default: changing it
    would change every arm at once and break comparability with the runs
    already paid for.
    """

    def __init__(self, mcp_clients=None, init_model_name: str = "gpt-4o",
                 full_docs: bool = False):
        super().__init__(mcp_clients, init_model_name, sys_prompt=TYPED_PLANNER_PROMPT)
        self.tool_index: dict[str, dict[str, Any]] = {}
        self.full_docs = full_docs

    async def run(self, input: str) -> AsyncGenerator[str, None]:
        if not self.history:
            await self.load_tools()
            self.tool_index = build_tool_index(self.tools)
            self.sys_prompt = self.sys_prompt.format(
                tools=tool_signature_lines(self.tools, full_docs=self.full_docs)
            )
            self.history.append(
                {"role": "system", "content": [{"type": "text", "text": self.sys_prompt}]}
            )
        self.history.append(
            {"role": "user", "content": [{"type": "text", "text": input}]}
        )
        response_text = ""
        async for chunk in self.llm.async_stream_generate(prompt="", history=self.history):
            response_text += chunk
            yield chunk
        self.history.append(
            {"role": "assistant", "content": [{"type": "text", "text": response_text}]}
        )
        match = re.search(r"```json\s*(\[.*?\])\s*```", response_text, re.DOTALL)
        if not match:
            match = re.search(r"(\[.*\])", response_text, re.DOTALL)
        self.subtasks = match.group(1) if match else ""

    def parsed_steps(self) -> list[dict[str, Any]] | None:
        try:
            steps = json.loads(self.subtasks)
        except (json.JSONDecodeError, TypeError):
            return None
        return steps if isinstance(steps, list) else None


async def plan_with_optional_gate(
    planner: TypedPlanAgent, query: str, gate: bool, max_repairs: int = 2,
    flow: bool = False
) -> dict[str, Any]:
    """Run the planner; with gate=True, validate and feed errors back.

    `flow=True` adds the data-flow check (arm D): on top of names and types, an
    input must exist or be written by an earlier step. It is a second gate
    stage, not a different one, so arm D differs from arm C by exactly this
    check and nothing else.

    Returns audit info: rounds, issues per round, and the final plan string.
    """
    audit: dict[str, Any] = {"gate": gate, "flow": flow, "rounds": []}
    async for chunk in planner.run(query):
        print(chunk, end="", flush=True)
    for round_no in range(max_repairs + 1):
        steps = planner.parsed_steps()
        if steps is None:
            issues = [{"code": "UNPARSABLE_PLAN", "step_id": "-",
                       "message": "the plan is not a valid JSON list"}]
        else:
            issues = validate_plan_steps(steps, planner.tool_index)
            if flow and not issues:
                # only once names and types hold: a flow complaint about a step
                # whose tool does not exist would be noise
                issues = validate_plan_flow(steps)
        audit["rounds"].append({"round": round_no, "issues": issues})
        if not gate or not issues or round_no == max_repairs:
            break
        print(f"\n--- Validation round {round_no}: {len(issues)} issue(s), repairing ---")
        errors_text = "\n".join(
            f"- [{i['code']}] step {i['step_id']}: {i['message']}" for i in issues
        )
        async for chunk in planner.run(REPAIR_MESSAGE.format(errors=errors_text)):
            print(chunk, end="", flush=True)
    audit["final_plan"] = planner.subtasks
    audit["final_issue_count"] = len(audit["rounds"][-1]["issues"])
    return audit


# --------------------------------------------------------------------------
# Arm C: the plan is the trajectory
# --------------------------------------------------------------------------

# '$3', '$step3', '$step_3' all name step_id 3. MapSmith's own plans use
# '$<step_id>' (plans/models.py REFERENCE); the typed planner here emits literal
# paths, so references are supported but never required.
STEP_REFERENCE = re.compile(r"^\$(?:step[_-]?)?([A-Za-z0-9_]{1,32})$")

_OBSERVATION = "Observation: "

# A failed tool does NOT raise in GABench's stdio mode: its client adapter
# (core/mcp_client.StdioClientAdapter.call_tool) rebuilds the reply as an object
# carrying only the joined text and drops the protocol's isError flag entirely,
# so the exception surfaces as a perfectly successful result whose text happens
# to be an error message. The ReAct solver gets away with it — the model reads
# the text — but an executor that only catches exceptions would record a plan
# where every step failed as "3/3 steps, no errors". That is exactly the silent
# wrong answer this project exists to refuse, and it was caught by the first
# real smoke test rather than by reasoning. These are the prefixes actually
# produced: FastMCP's server-side wrapper, the MCP SDK's variant, and the
# adapter's own timeout reply. test_enforced.py pins them.
_TOOL_OBSERVATIONES = (
    "Error calling tool",
    "Error executing tool",
    "An error occurred while calling tool",
    "Error:",
)


def tool_reply_failed(text: str) -> bool:
    """Whether an observation is a tool failure dressed as a result."""
    body = text[len(_OBSERVATION):] if text.startswith(_OBSERVATION) else text
    return body.lstrip().startswith(_TOOL_OBSERVATIONES)


def format_action(name: str, arguments: dict[str, Any], thought: str = "") -> str:
    """One assistant turn in the format GABench's evaluator can read back.

    Hard constraint, verified in evaluation/step_by_step.py (extract_tool_calls,
    mode 'react'): predicted calls are recovered ONLY from assistant messages
    matching `(?m)^Action:\\s*(\\{.*\\})` with DOTALL, decoded as JSON with
    'name' and 'arguments' keys. DOTALL makes `.*` greedy across newlines, so
    the JSON goes on ONE line and the Action line goes LAST — anything after it
    containing a brace would be swallowed into the match and break the decode.
    Get this wrong and the whole arm reports zero tool calls: not an error, just
    every metric at zero. That is what test_enforced.py exists to prevent.
    """
    thought = " ".join(str(thought).split()) or "executing the validated plan"
    return f"Thought: {thought}\nAction: {json.dumps({'name': name, 'arguments': arguments})}"


def produced_path(arguments: dict[str, Any], data: Any) -> str | None:
    """What a finished step left on disk, for later steps to point at.

    Preferred source is the tool's own reply (GABench tools return
    {'output_path': './output/<name>'}); the plan's `output_name` is the
    fallback, since that is the only output-naming argument in the toolbox and
    the tools resolve it against config.yaml's output_dir.
    """
    if isinstance(data, str):
        # stdio transport hands back the JSON text of the tool's dict, not the dict
        try:
            data = json.loads(data)
        except ValueError:
            data = None
    if isinstance(data, dict):
        for key in ("output_path", "output", "path"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
    name = arguments.get("output_name")
    return f"output/{name}" if isinstance(name, str) and name else None


def resolve_references(
    arguments: dict[str, Any], produced: dict[str, str]
) -> tuple[dict[str, Any], list[str]]:
    """Substitute '$stepN' with the path step N actually produced.

    Resolution uses what the earlier step *returned*, not what the plan said it
    would write — same rule as MapSmith's executor, and the difference matters
    when a tool normalizes the path it was given. Unresolved references are
    reported instead of being passed through as a literal '$3': arm C does not
    improvise, so a plan that cannot be resolved is a plan that does not run.
    """
    missing: list[str] = []

    def one(value: Any) -> Any:
        if isinstance(value, str):
            match = STEP_REFERENCE.match(value)
            if match:
                target = match.group(1)
                if target in produced:
                    return produced[target]
                missing.append(value)
        elif isinstance(value, list):
            return [one(item) for item in value]
        return value

    return {key: one(value) for key, value in arguments.items()}, missing


class ToolCaller:
    """Calls GABench's MCP tools the way its ReAct solver does.

    Same routing table, same observation strings, so arm C's logs are
    comparable to A/B's turn for turn. Two deliberate differences:
    it reports success as a value instead of a string an agent has to read, and
    it returns the tool's structured reply so step references can resolve
    against what actually happened. The timeout is upstream's own
    `tool_timeout` (BaseAgent.call_tool uses it; the ReAct override drops it) —
    without it a single hung tool stalls an unattended overnight run, and a
    stall is not a measurement.
    """

    def __init__(self, agent: Any, timeout: float | None = 300.0) -> None:
        self.agent = agent
        self.timeout = timeout

    async def __call__(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str, Any]:
        routes = getattr(self.agent, "tool_routes", {})
        if name not in routes:
            return False, f"{_OBSERVATION}Error: Tool {name} not found.", None
        url, client = routes[name]
        try:
            if getattr(self.agent, "connected", False):
                result = await asyncio.wait_for(
                    client.call_tool(name, arguments), timeout=self.timeout
                )
            else:
                async with client:
                    result = await asyncio.wait_for(
                        client.call_tool(name, arguments), timeout=self.timeout
                    )
        except asyncio.TimeoutError:
            return False, f"{_OBSERVATION}Error: Tool {name} timed out.", None
        except Exception as exc:  # noqa: BLE001 — upstream catches everything here too
            return (
                False,
                f"{_OBSERVATION}An error occurred while calling tool {name} "
                f"from {url}: {exc}",
                None,
            )
        data = getattr(result, "data", None)
        text = f"{_OBSERVATION}{data}"
        # protocol truth where the transport preserves it, the text otherwise
        flagged = getattr(result, "isError", getattr(result, "is_error", None))
        failed = bool(flagged) if flagged is not None else tool_reply_failed(text)
        return not failed, text, None if failed else data


class EnforcedExecutor:
    """Arm C: run the validated plan exactly as written. No LLM in the loop.

    This is MapSmith's `execute_plan` contract transplanted onto GABench: steps
    in list order, references resolved from real outputs, and a stop at the
    first failure with everything up to it kept. There is no repair and no
    improvisation — that is the whole point of the arm, and it cuts both ways:
    a plan the gate could not fix (an unparsable plan, a tool that does not
    exist) executes zero steps and scores zero, where the ReAct solver would
    have improvised its way to a partial score. The audit records exactly that,
    because it is a real property of enforcing plans, not a harness failure.
    """

    def __init__(
        self,
        call: Callable[[str, dict[str, Any]], Awaitable[tuple[bool, str, Any]]],
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        self.call = call
        self.history: list[dict[str, Any]] = [] if history is None else history

    def _say(self, role: str, text: str) -> None:
        self.history.append({"role": role, "content": [{"type": "text", "text": text}]})

    async def run(self, steps: Any, query: str = "") -> dict[str, Any]:
        audit: dict[str, Any] = {
            "steps_planned": len(steps) if isinstance(steps, list) else 0,
            "steps_executed": 0,
            "calls": [],
            "stopped_at": None,
            "stop_reason": None,
        }
        if query:
            self._say("user", query)
        if not isinstance(steps, list) or not steps:
            audit["stop_reason"] = "no_plan"
            self._say("assistant", "Final Answer: no executable plan was produced.")
            return audit

        produced: dict[str, str] = {}
        for position, raw in enumerate(steps, 1):
            if not isinstance(raw, dict):
                audit["stopped_at"], audit["stop_reason"] = str(position), "malformed_step"
                break
            if not raw.get("tool"):
                audit["stopped_at"] = str(raw.get("step_id", position))
                audit["stop_reason"] = "malformed_step"
                break
            step_id = str(raw.get("step_id", position))
            tool = str(raw["tool"])
            planned = raw.get("arguments")
            if not isinstance(planned, dict):
                audit["stopped_at"], audit["stop_reason"] = step_id, "malformed_step"
                break
            arguments, missing = resolve_references(planned, produced)
            if missing:
                audit["stopped_at"], audit["stop_reason"] = step_id, "unresolved_reference"
                audit["calls"].append(
                    {"step_id": step_id, "tool": tool, "arguments": arguments,
                     "ok": False, "unresolved": missing}
                )
                self._say(
                    "assistant",
                    f"Final Answer: step {step_id} points at {', '.join(missing)}, "
                    "which no earlier step produced.",
                )
                return audit

            # the Action message comes BEFORE the call and carries the arguments
            # actually passed, so the evaluated trajectory is the executed one
            self._say(
                "assistant",
                format_action(
                    tool, arguments, f"step {step_id} of the validated plan: "
                    f"{raw.get('purpose', tool)}"
                ),
            )
            ok, observation, data = await self.call(tool, arguments)
            self._say("user", observation)
            audit["calls"].append(
                {"step_id": step_id, "tool": tool, "arguments": arguments, "ok": ok}
            )
            audit["steps_executed"] += 1
            if not ok:
                audit["stopped_at"], audit["stop_reason"] = step_id, "tool_error"
                audit["error"] = observation[:500]
                self._say(
                    "assistant",
                    f"Final Answer: execution stopped at step {step_id}; "
                    f"the plan is enforced, so it is not repaired here.",
                )
                return audit
            path = produced_path(arguments, data)
            if path:
                produced[step_id] = path

        if audit["stop_reason"] == "malformed_step":
            self._say(
                "assistant",
                f"Final Answer: step {audit['stopped_at']} is not an executable "
                "step; execution stopped.",
            )
            return audit
        self._say(
            "assistant",
            f"Final Answer: executed all {audit['steps_executed']} planned steps.",
        )
        return audit
