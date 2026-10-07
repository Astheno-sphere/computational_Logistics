"""Stateless Ray Tasks for batched agent execution.

The driver (``AgentSociety``) holds ONLY agent records (specs/ids) — never
agent objects. Every tick it chunks the id list and submits one
:func:`step_agent_batch` Ray Task per chunk. Each task:

- reads agent workspaces from local disk (``<workspace_root>/agent_<id:04d>``),
- reconstructs agents via ``cls.from_workspace(ws, service_proxy)``,
- runs ``agent.step(tick, t)``, persists via ``agent.to_workspace(ws)``,
- returns a LIGHTWEIGHT summary list (no agent objects cross the process
  boundary → keeps the Ray object store healthy).

Parallelism comes from TWO layers: (1) MANY tasks scheduled across Ray
workers (the driver chunks ids and submits one task per chunk), and (2)
agents WITHIN a task run concurrently via ``asyncio.gather`` — each agent is
LLM-bound (a chain of awaited LLM/tool calls), so overlapping them lets the
shared AdaptiveSemaphore fan LLM requests out to the API. Global LLM
concurrency is gated by the dispatcher's semaphore, so per-batch fan-out is
safe. Critically, tasks never call ``ray.init`` / ``get_dispatcher``
directly — they consume the injected ``service_proxy`` handles to avoid
Ray-in-Ray.

``create_agents_batch`` writes the initial workspaces for a batch of specs
without instantiating agents in the driver process.

``query_agent_task`` is a generic single-agent op dispatcher for low-volume
external queries (ask/intervene/questionnaire/dump). The driver reconstructs
target agents LOCALLY for such queries (simpler, workspaces are on the same
disk); this task is provided for completeness but is not on the hot path.

Implementation note: Ray (2.x) does not allow ``@ray.remote`` directly on an
``async def`` regular task. Each public task is therefore a thin SYNC wrapper
that drives an internal async coroutine via ``asyncio.run``. The async core
keeps the agent contract (``from_workspace`` / ``step`` / ``to_workspace`` are
coroutines) unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from agentsociety2.agent.service_proxy import ServiceProxy

_F = TypeVar("_F", bound=Callable[..., Any])


def _ray_remote(fn: _F) -> _F:
    try:
        import ray
    except ImportError:
        return fn
    return ray.remote(fn)  # type: ignore[return-value]


__all__ = [
    "create_agents_batch",
    "query_agent_task",
    "questionnaire_agent_batch",
    "step_agent_batch",
]


def _resolve_agent_class(
    agent_class_name: str, workspace_root: str | None = None
) -> Any:
    """Resolve an agent class by name via the module registry.

    Done inside each task (not in the driver) so the class object never
    crosses the Ray boundary.

    :param agent_class_name: Registered agent class name (e.g. ``"PersonAgent"``).
    :param workspace_root: Agent workspace root (``run_dir/agents``). When the
        parent ``run_dir`` contains ``custom/``, that workspace is scanned so
        custom agent classes are visible on this worker.
    :returns: The agent class.
    :raises ValueError: If the class is not registered.
    """
    if workspace_root:
        run_dir = Path(workspace_root).resolve().parent
        if (run_dir / "custom").is_dir():
            from agentsociety2.registry import get_registry

            get_registry().set_workspace(run_dir)

    from agentsociety2.registry import get_agent_module_class

    cls = get_agent_module_class(agent_class_name)
    if cls is None:
        # Fall back to a direct attribute lookup on the agent package in case
        # the class is registered under a different type id than its __name__.
        try:
            from agentsociety2 import agent as _agent_mod

            cls = getattr(_agent_mod, agent_class_name, None)
        except Exception:
            cls = None
    if cls is None:
        raise ValueError(
            f"Agent class '{agent_class_name}' not found in registry; "
            "ensure the module is discovered before submitting tasks."
        )
    return cls


def _workspace_for(workspace_root: str, agent_id: int) -> Path:
    """Return the canonical per-agent workspace path.

    Matches the scheme used by ``AgentSociety`` and ``PersonAgent``:
    ``<workspace_root>/agent_<id:04d>``.
    """
    return Path(workspace_root) / f"agent_{int(agent_id):04d}"


# ---------------------------------------------------------------------------
# Async cores (testable in-process, driven by the sync Ray wrappers below)
# ---------------------------------------------------------------------------
async def _step_agent_batch_async(
    agent_ids: list[int],
    workspace_root: str,
    agent_class_name: str,
    tick: int,
    t: datetime,
    service_proxy: ServiceProxy,
) -> list[dict]:
    cls = _resolve_agent_class(agent_class_name, workspace_root)

    async def _step_one(aid: int) -> dict:
        ws = _workspace_for(workspace_root, aid)
        try:
            agent = await cls.from_workspace(ws, service_proxy)
            summary = await agent.step(tick, t)
            await agent.to_workspace(ws)
            try:
                await agent.close()
            except Exception:
                logging.getLogger(__name__).debug(
                    "Error closing agent %s", aid, exc_info=True
                )
            return {"id": aid, "ok": True, "summary": summary}
        except Exception as e:
            return {"id": aid, "ok": False, "error": repr(e)}

    # Run all agents in the batch CONCURRENTLY. Each agent is LLM-bound — its
    # step() is a sequence of `await`-ed LLM/tool calls — so overlapping them
    # lets the shared AdaptiveSemaphore fan LLM requests out to the API rather
    # than serializing the whole batch behind one agent. Global LLM concurrency
    # is still gated by the dispatcher's semaphore; per-agent workspaces and the
    # injected service_proxy are concurrency-safe, so there is no shared mutable
    # state to protect. gather() preserves input order in the returned list.
    return await asyncio.gather(*[_step_one(aid) for aid in agent_ids])


async def _create_agents_batch_async(
    items: list[dict],
    workspace_root: str,
    agent_class_name: str,
) -> int:
    cls = _resolve_agent_class(agent_class_name, workspace_root)
    for it in items:
        ws = _workspace_for(workspace_root, int(it["id"]))
        cls.create(ws, it["profile"], it["config"])
    return len(items)


async def _questionnaire_agent_batch_async(
    agent_ids: list[int],
    workspace_root: str,
    agent_class_name: str,
    questionnaire: Any,
    t: datetime,
    step_count: int,
    service_proxy: ServiceProxy,
) -> list[dict]:
    """Run a full questionnaire for every agent in the batch (concurrent).

    Mirrors ``_step_agent_batch_async``: each agent is reconstructed from its
    workspace, runs the WHOLE questionnaire (all questions), persists back via
    ``to_workspace``. Agents run CONCURRENTLY via ``asyncio.gather`` — each
    ``agent.ask`` is LLM-bound, so overlapping them lets the shared
    AdaptiveSemaphore fan requests out. Failures are isolated per agent (one
    bad agent never aborts the whole batch), matching ``step_agent_batch``.

    Returns one dict per agent::

        {"id": int, "ok": True, "result": <AgentQuestionnaireResult dump>}
        {"id": int, "ok": False, "error": str}
    """
    from agentsociety2.society.questionnaire import QuestionnaireRunner

    cls = _resolve_agent_class(agent_class_name, workspace_root)
    runner = QuestionnaireRunner()

    async def _run_one(aid: int) -> dict:
        ws = _workspace_for(workspace_root, aid)
        try:
            agent = await cls.from_workspace(ws, service_proxy)
            try:
                resp = await runner.run(
                    questionnaire,
                    [agent],
                    t=t,
                    step_count=step_count,
                    target_agent_ids=[aid],
                )
            finally:
                # Persist any agent state mutations back to the workspace
                # (the driver no longer holds the agent object).
                try:
                    await agent.to_workspace(ws)
                except Exception:
                    logging.getLogger(__name__).debug(
                        "Error persisting agent %s to workspace", aid, exc_info=True
                    )
            try:
                await agent.close()
            except Exception:
                logging.getLogger(__name__).debug(
                    "Error closing agent %s after query", aid, exc_info=True
                )
            per_agent = resp.responses[0] if resp.responses else None
            return {
                "id": aid,
                "ok": True,
                "result": per_agent.model_dump(mode="json") if per_agent else None,
            }
        except Exception as e:
            return {"id": aid, "ok": False, "error": repr(e)}

    return await asyncio.gather(*[_run_one(aid) for aid in agent_ids])


async def _query_agent_task_async(
    agent_id: int,
    workspace_root: str,
    agent_class_name: str,
    op: str,
    payload: dict,
    service_proxy: ServiceProxy,
) -> dict:
    import json

    cls = _resolve_agent_class(agent_class_name, workspace_root)
    ws = _workspace_for(workspace_root, agent_id)

    if op == "dump":
        agent_json_path = ws / "AGENT.json"
        if agent_json_path.exists():
            return {
                "agent_json": json.loads(agent_json_path.read_text(encoding="utf-8"))
            }
        return {"agent_json": None}

    agent = await cls.from_workspace(ws, service_proxy)
    try:
        if op in ("ask", "intervene"):
            message = str(payload.get("message", ""))
            readonly = bool(payload.get("readonly", op == "ask"))
            t_iso = payload.get("t")
            t_val: datetime | None
            if isinstance(t_iso, str) and t_iso:
                try:
                    t_val = datetime.fromisoformat(t_iso)
                except ValueError:
                    t_val = None
            else:
                t_val = None
            answer = await agent.ask(message, readonly=readonly, t=t_val)
            await agent.to_workspace(ws)
            return {"answer": answer}
        raise ValueError(f"Unsupported query op: {op!r}")
    finally:
        try:
            await agent.close()
        except Exception:
            logging.getLogger(__name__).debug(
                "Error closing agent after query", exc_info=True
            )


# ---------------------------------------------------------------------------
# Public Ray Tasks (sync wrappers — Ray 2.x forbids `@ray.remote` on async def)
# ---------------------------------------------------------------------------
@_ray_remote
def step_agent_batch(
    agent_ids: list[int],
    workspace_root: str,
    agent_class_name: str,
    tick: int,
    t: datetime,
    service_proxy: ServiceProxy,
) -> list[dict]:
    """Run one ``step`` for every agent id in the batch.

    For each id: ``from_workspace`` → ``step`` → ``to_workspace``. Agents in a
    batch run CONCURRENTLY via ``asyncio.gather`` — each is LLM-bound (a chain
    of awaited LLM/tool calls), so overlapping them lets the shared
    AdaptiveSemaphore fan LLM requests out to the API. Global LLM concurrency
    is gated by the dispatcher's semaphore. Additional parallelism across the
    population comes from the driver submitting multiple such tasks.

    Args:
        agent_ids: Agent ids in this batch.
        workspace_root: Directory holding ``agent_<id:04d>`` workspaces.
        agent_class_name: Registered agent class name.
        tick: Tick span (seconds) for this step.
        t: Current simulation time.
        service_proxy: Shared service handles (env / llm / trace / replay).
            Injected — never re-created inside the task.

    Returns:
        A list of per-agent result dicts::

            {"id": int, "ok": True, "summary": str}
            {"id": int, "ok": False, "error": str}

        Only lightweight summaries cross back to the driver — no agent objects.
        Also carries this task process's token-usage delta back to the driver
        (``token_stats``) so the driver can aggregate it across all batches.
    """
    results = asyncio.run(
        _step_agent_batch_async(
            agent_ids, workspace_root, agent_class_name, tick, t, service_proxy
        )
    )
    # Drain this task's LLM clients' token stats (a delta since the last drain)
    # and return them alongside the per-agent results — no actor, no extra RPC.
    return {"results": results, "token_stats": service_proxy.take_token_stats()}


@_ray_remote
def create_agents_batch(
    items: list[dict],
    workspace_root: str,
    agent_class_name: str,
) -> int:
    """Create initial workspaces for a batch of agent specs.

    For each spec ``{"id", "profile", "config"}`` calls ``cls.create(ws,
    profile, config)``. The driver never instantiates agent objects —
    workspaces are written here, agents are reconstructed on demand.

    Args:
        items: List of ``{"id": int, "profile": dict, "config": dict}``.
        workspace_root: Directory to create ``agent_<id:04d>`` under.
        agent_class_name: Registered agent class name.

    Returns:
        Number of agent workspaces created.
    """
    return asyncio.run(
        _create_agents_batch_async(items, workspace_root, agent_class_name)
    )


@_ray_remote
def query_agent_task(
    agent_id: int,
    workspace_root: str,
    agent_class_name: str,
    op: str,
    payload: dict,
    service_proxy: ServiceProxy,
) -> dict:
    """Generic single-agent query/mutation task (low-volume external ops).

    Reconstructs one agent via ``from_workspace``, dispatches ``op``, then
    persists via ``to_workspace``. Supported ops:

    - ``"ask"``: ``payload = {"message": str, "readonly": bool, "t": iso}``
        → ``{"answer": str}``
    - ``"intervene"``: alias for ``ask`` with ``readonly=False``.
    - ``"dump"``: read ``AGENT.json`` → ``{"agent_json": dict}``

    The driver currently answers queries by reconstructing agents LOCALLY (the
    workspaces live on the same disk), so this task is kept for callers that
    prefer to offload reconstruction to a worker.

    Args:
        agent_id: Target agent id.
        workspace_root: Directory holding the agent workspace.
        agent_class_name: Registered agent class name.
        op: Operation name (``ask`` / ``intervene`` / ``dump``).
        payload: Op-specific arguments.
        service_proxy: Shared service handles.

    Returns:
        Op result dict.
    """
    return asyncio.run(
        _query_agent_task_async(
            agent_id, workspace_root, agent_class_name, op, payload, service_proxy
        )
    )


@_ray_remote
def questionnaire_agent_batch(
    agent_ids: list[int],
    workspace_root: str,
    agent_class_name: str,
    questionnaire: Any,
    t: datetime,
    step_count: int,
    service_proxy: ServiceProxy,
) -> dict:
    """Run a full questionnaire for every agent in the batch.

    Parallel to ``step_agent_batch`` but for external surveys instead of
    simulation ticks. For each id: ``from_workspace`` → run the whole
    questionnaire (all questions, readonly asks) → ``to_workspace``. Agents in a
    batch run CONCURRENTLY via ``asyncio.gather`` (each ``ask`` is LLM-bound).
    Cross-population parallelism comes from the driver submitting multiple such
    tasks — exactly like ``step``.

    Args:
        agent_ids: Agent ids in this batch.
        workspace_root: Directory holding ``agent_<id:04d>`` workspaces.
        agent_class_name: Registered agent class name.
        questionnaire: ``Questionnaire`` model (serializable across Ray).
        t: Current simulation time (authoritative for agent reasoning).
        step_count: Current simulation step count.
        service_proxy: Shared service handles (env / llm / trace / replay).
            Injected — never re-created inside the task.

    Returns:
        ``{"results": [...], "token_stats": <delta>}`` where each result is::

            {"id": int, "ok": True, "result": <AgentQuestionnaireResult dump>}
            {"id": int, "ok": False, "error": str}

        ``token_stats`` carries this process's token-usage delta back to the
        driver for aggregation (no actor, no extra RPC).
    """
    results = asyncio.run(
        _questionnaire_agent_batch_async(
            agent_ids,
            workspace_root,
            agent_class_name,
            questionnaire,
            t,
            step_count,
            service_proxy,
        )
    )
    return {"results": results, "token_stats": service_proxy.take_token_stats()}
