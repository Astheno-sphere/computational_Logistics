"""A/B/C/D runner: GABench Plan-and-React with typed plans, gate, enforced plans.

Usage (run with GABench's venv, from its repo root so config.yaml/.env
resolve; GABENCH_ROOT may point the harness at the checkout):
    python run_ab.py --arm a --model claude --ids 1,2,3 --rep 1
    python run_ab.py --arm b --model claude --all --rep 1
    python run_ab.py --arm c --model haiku --group defective+control --rep 1
    python run_ab.py --arm d --model haiku --group defective+control --rep 1

Output: results/{model}/arm_{arm}_rep{rep}/rep{rep}.jsonl in the upstream
history format (GABench's evaluation/step_by_step.py runs on it unchanged) plus
a `gate_audit` field recording validation rounds and, for the enforced arms, an
`exec_audit` field recording what the plan actually did.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

AB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AB_DIR))

from _paths import gabench_root, result_file, run_dir  # noqa: E402
from task_groups import task_ids  # noqa: E402

GABENCH_ROOT = gabench_root()
sys.path.insert(0, str(GABENCH_ROOT))

from core.mcp_client import get_mcp_clients  # noqa: E402
from agents.plan_and_react import SolveReactAgent  # noqa: E402
from agents.react import ReactAgent  # noqa: E402
from runners.run_benchmark import load_tasks_from_csv, get_completed_tasks  # noqa: E402

from ab_extension import (  # noqa: E402
    EnforcedExecutor,
    ToolCaller,
    TypedPlanAgent,
    make_compact_solver,
    plan_with_optional_gate,
)

CompactSolver = make_compact_solver(SolveReactAgent)

CSV_PATH = GABENCH_ROOT / "benchmark" / "benchmark.csv"
TOOL_OUTPUT_DIR = GABENCH_ROOT / "output"


def reset_tool_output() -> None:
    """Each task starts from a CLEAN output dir: artifacts from a previous run
    would let the agent 'succeed' by reusing them (observed on the first smoke)."""
    if TOOL_OUTPUT_DIR.exists():
        shutil.rmtree(TOOL_OUTPUT_DIR)
    TOOL_OUTPUT_DIR.mkdir()


def archive_tool_output(dest: Path) -> None:
    """Keep every task's artifacts for the end-to-end evaluation and replay."""
    if TOOL_OUTPUT_DIR.exists():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(TOOL_OUTPUT_DIR), str(dest))


async def run_task(task: dict, model: str, arm: str) -> dict:
    mcp_clients = get_mcp_clients()
    start = datetime.now()
    status, error, history, audit, exec_audit = "success", None, [], None, None
    gate = arm in ("b", "c", "d", "e")
    # arm D adds the data-flow stage to the same gate: an input must exist or be
    # written by an earlier step. That is the one check whose absence stopped 74
    # of 75 enforced runs, so D differs from C by exactly this and nothing else.
    flow = arm in ("d", "e")
    enforced = arm in ("c", "d", "e")
    # arm E = arm D with the tools' full argument documentation in the planner
    # prompt. It answers one question the D run raised: does an enforced plan
    # fail because planning is hard, or because our own prompt compression
    # never told the planner the rules (output_name must end with .tif)?
    full_docs = arm == "e"
    try:
        print("\n--- Planning Phase (typed) ---")
        planner = TypedPlanAgent(mcp_clients=mcp_clients, init_model_name=model,
                                 full_docs=full_docs)
        async with planner:
            audit = await plan_with_optional_gate(
                planner, task["query"], gate=gate, flow=flow
            )
        history.extend(planner.history)

        if enforced:
            # Arms C and D: the validated plan is the trajectory. ReactAgent is
            # used for its tool routing only — the class arms A/B executed
            # through — and its LLM is never called.
            print("\n--- Execution Phase (enforced plan, no LLM) ---")
            runner = ReactAgent(mcp_clients=mcp_clients, init_model_name=model)
            async with runner:
                await runner.load_tools()
                executor = EnforcedExecutor(ToolCaller(runner))
                exec_audit = await executor.run(planner.parsed_steps(), task["query"])
            history.extend(executor.history)
            print(f"\n[exec] {exec_audit['steps_executed']}/{exec_audit['steps_planned']} "
                  f"steps, stop: {exec_audit['stop_reason'] or 'none'}")
        else:
            print("\n--- Solving Phase ---")
            solver = CompactSolver(mcp_clients=mcp_clients, init_model_name=model)
            solver.set_subtasks(planner.subtasks)
            async with solver:
                async for chunk in solver.run(task["query"]):
                    print(chunk, end="", flush=True)
            history.extend(solver.history)
    except Exception as exc:  # noqa: BLE001 — the record must survive any failure
        status, error = "error", f"{type(exc).__name__}: {exc}"
        print(f"\n!!! {error}")
    record = {
        "task_id": str(task["id"]),
        "agent": "plan_and_react_typed",
        "model": model,
        "arm": arm.upper(),
        "gate_audit": audit,
        "exec_audit": exec_audit,
        # `status` says whether the HARNESS completed the task, because that is
        # what upstream's resume logic (get_completed_tasks skips only
        # status=success) and its evaluator dedup key on. A plan that stopped on
        # a tool error is a result of arm C, not a harness failure, so it lands
        # in `plan_status` / `failed_step` instead: marking it status=error
        # would make every resume re-run and re-plan those tasks.
        "status": status,
        "error": error,
        "plan_status": None if exec_audit is None else (
            "stopped" if exec_audit["stop_reason"] else "completed"
        ),
        "failed_step": None if exec_audit is None else exec_audit["stopped_at"],
        "duration_seconds": (datetime.now() - start).total_seconds(),
        "start_time": start.isoformat(),
        "end_time": datetime.now().isoformat(),
        "query": task["query"],
        "history": history,
    }
    return record


async def main() -> None:
    parser = argparse.ArgumentParser(description="MapSmith x GABench A/B/C runner")
    parser.add_argument("--arm", choices=["a", "b", "c", "d", "e"], required=True,
                        help="a = typed plan only, b = plan + validation gate, "
                             "c = plan + gate, executed as written (no LLM), "
                             "d = plan + gate + data-flow check, executed as written, "
                             "e = d with the tools' full argument docs in the plan prompt")
    parser.add_argument("--model", required=True, help="model key from config.yaml")
    parser.add_argument("--ids", help="comma-separated task IDs")
    parser.add_argument("--group", help="frozen task group from task_groups.py: "
                                        "defective, control, or defective+control")
    parser.add_argument("--all", action="store_true", help="run every task in the CSV")
    parser.add_argument("--rep", type=int, default=1, help="repetition index")
    args = parser.parse_args()

    tasks = load_tasks_from_csv(CSV_PATH)
    if args.ids:
        wanted = {t.strip() for t in args.ids.split(",")}
    elif args.group:
        wanted = set(task_ids(args.group))
    elif args.all:
        wanted = None
    else:
        parser.error("pass --ids, --group or --all")
    if wanted is not None:
        tasks = [t for t in tasks if str(t["id"]) in wanted]
        missing = wanted - {str(t["id"]) for t in tasks}
        if missing:
            parser.error(f"no such task IDs in the benchmark: {sorted(missing)}")
    if not tasks:
        print("no matching tasks")
        return

    out = run_dir(args.model, args.arm, args.rep)
    out.mkdir(parents=True, exist_ok=True)
    results = result_file(args.model, args.arm, args.rep)
    done = get_completed_tasks(results)
    print(f"=== arm {args.arm.upper()} | model {args.model} | rep {args.rep} "
          f"| tasks {len(tasks)} | already done {len(done)} ===")
    print(f"=== results -> {results} ===")

    for i, task in enumerate(tasks, 1):
        if str(task["id"]) in done:
            print(f"[{i}/{len(tasks)}] task {task['id']} SKIPPED (done)")
            continue
        print(f"\n[{i}/{len(tasks)}] task {task['id']}")
        reset_tool_output()
        record = await run_task(task, args.model, arm=args.arm)
        archive_tool_output(out / "artifacts" / f"task_{task['id']}")
        with open(results, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        print(f"\n[saved] task {task['id']}: {record['status']} "
              f"({record['duration_seconds']:.0f}s)")


if __name__ == "__main__":
    asyncio.run(main())
