"""Ray-only proxy for the env router.

Society, agents, and helpers talk to this proxy exactly as they talk to the
in-process ``CodeGenRouter`` (same method names: ``ask``, ``init``, ``step``,
``close``, ``to_workspaces``, ``from_workspaces``, ``set_current_time``,
``set_replay_writer``). The proxy forwards each call to a Ray actor that owns
the real router in a separate process, so env codegen execution (and its
former ``_execute_lock`` serialization) no longer blocks the agent event loop.

In-process ``CodeGenRouter`` instances are **not** Ray-serializable. Examples
and scripts must use :func:`create_env_router_proxy` (or the CLI actor path)
so ``ServiceProxy`` can cross Ray Task boundaries.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


class EnvRouterProxy:
    """Agent/society-facing handle delegating to a Ray env-router actor.

    Unlike the in-process router, the proxy does NOT hold concrete env-module
    instances (they live in the actor's process), so it cannot expose
    ``env_modules``. To keep env-provided skills discoverable from the agent
    side, the proxy carries ``env_skill_dirs`` — the union of every configured
    env module's ``skill_dirs()`` resolved from the registry at construction
    time, each paired with the module's class name (used as the
    ``env:{ClassName}`` namespace). ``AgentBase.discover_skill_sources`` reads
    this attribute in addition to ``env_modules``, so env skills are visible
    regardless of whether the agent sees a real router or this proxy. The
    attribute is plain JSON-serializable data (``list[(str, str)]``), so the
    proxy still crosses the Ray boundary cleanly.
    """

    def __init__(
        self,
        actor_handle: Any,
        *,
        run_dir: Any = None,
        env_module_types: list[str] | None = None,
    ) -> None:
        self._actor = actor_handle
        self.run_dir = run_dir
        self.env_skill_dirs: list[tuple[str, str]] = _resolve_env_skill_dirs(
            env_module_types or []
        )

    def set_current_time(self, t: datetime) -> None:
        """Forward the society clock to the actor (fire-and-forget).

        See :meth:`RouterBase.set_current_time` — this pushes the society's
        current time so env modules observe it during the agent phase.
        """
        self._actor.set_current_time.remote(t)

    def set_replay_writer(self, writer: Any) -> None:
        """Forward a replay writer/proxy to the actor (fire-and-forget).

        The env actor normally receives its replay proxy at construction (so env
        modules and agents share the same replay directory). This method lets a
        caller additionally/alternatively inject a writer after construction; it
        is forwarded to the actor via ``set_replay_writer``. A ``ReplayProxy`` is
        serializable, so it travels across the Ray boundary cleanly.
        """
        self._actor.set_replay_writer.remote(writer)

    async def ask(
        self,
        ctx: dict,
        instruction: str,
        readonly: bool = False,
        template_mode: bool = False,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
    ):
        """Forward an env ask to the actor and await the (ctx, answer) result."""
        return await self._actor.ask.remote(
            ctx, instruction, readonly, template_mode, trace_id, parent_span_id
        )

    async def get_world_description(self) -> str:
        return await self._actor.get_world_description.remote()

    async def init(self, start_datetime: datetime) -> bool:
        return await self._actor.init.remote(start_datetime)

    async def step(self, tick: int, t: datetime) -> None:
        return await self._actor.step.remote(tick, t)

    async def to_workspaces(self) -> None:
        """转发每步 env 状态持久化到 actor。"""
        return await self._actor.to_workspaces.remote()

    async def from_workspaces(self) -> bool:
        """转发 env 状态恢复（resume）到 actor。"""
        return await self._actor.from_workspaces.remote()

    async def close(self) -> None:
        return await self._actor.close.remote()

    def get_token_usages(self) -> dict[str, Any]:
        """Return a snapshot of env-router (coder/summary) token usage."""
        return ray_get_token_usages(self._actor)


def ray_get_token_usages(actor_handle: Any) -> dict[str, Any]:
    """Blocking fetch of token usage from the env actor (driver-side only)."""
    import ray

    return ray.get(actor_handle.get_token_usages.remote())


async def create_env_router_proxy(
    env_module_types: list[str],
    env_kwargs: dict[str, dict[str, Any]] | None = None,
    *,
    run_dir: str | Path | None = None,
    max_concurrency: int | None = None,
    final_summary_enabled: bool = False,
) -> EnvRouterProxy:
    """Create a Ray ``EnvRouterProxy`` for examples / scripts (CLI-compatible).

    Initializes Ray + LLM dispatchers if needed, builds the env actor with the
    same injection pattern as ``society.cli``, and returns a serializable proxy.

    :param env_module_types: Registry keys (usually the env class name).
    :param env_kwargs: Per-type constructor kwargs; defaults to ``{}`` per type.
    :param run_dir: Experiment run directory (env workspaces under ``run_dir/env``).
    :param max_concurrency: Ray actor concurrency. ``None`` chooses
        ``Config.ENV_ACTOR_MAX_CONCURRENCY`` when every module declares
        ``is_concurrency_safe()``, otherwise ``1``.
    :param final_summary_enabled: Forwarded to ``CodeGenRouter``.
    :returns: Serializable :class:`EnvRouterProxy` suitable for ``AgentSociety``.
    """
    from agentsociety2.config import Config
    from agentsociety2.config.llm_dispatcher import (
        build_client_for_role,
        init_dispatchers,
    )
    from agentsociety2.env.env_router_actor import get_env_router_actor_class
    from agentsociety2.registry import get_registered_env_modules

    await init_dispatchers()

    types = list(env_module_types)
    kwargs = dict(env_kwargs or {})
    for t in types:
        kwargs.setdefault(t, {})

    run_dir_path = Path(run_dir).resolve() if run_dir is not None else None
    if run_dir_path is not None and (run_dir_path / "custom").is_dir():
        from agentsociety2.registry import get_registry

        get_registry().set_workspace(run_dir_path)

    type_map = dict(get_registered_env_modules())
    missing = [t for t in types if t not in type_map]
    if missing:
        raise ValueError(
            f"Unknown env module type(s): {missing}. "
            "Register custom classes before calling create_env_router_proxy."
        )

    if max_concurrency is None:
        all_safe = all(type_map[t].is_concurrency_safe() for t in types)
        max_concurrency = Config.ENV_ACTOR_MAX_CONCURRENCY if all_safe else 1
    llm_clients_spec = {
        "coder": build_client_for_role("coder"),
        "default": build_client_for_role("default"),
    }
    actor_cls = get_env_router_actor_class(max_concurrency=max_concurrency)
    actor = actor_cls.remote(
        types,
        kwargs,
        str(run_dir_path) if run_dir_path is not None else None,
        {"final_summary_enabled": final_summary_enabled},
        llm_clients_spec,
        None,
        None,
    )
    return EnvRouterProxy(
        actor,
        run_dir=run_dir_path,
        env_module_types=types,
    )


def _resolve_env_skill_dirs(
    env_module_types: list[str],
) -> list[tuple[str, str]]:
    """Collect ``(module_class_name, skill_dir)`` for the given env module types.

    Resolves each type's class from the global registry and reads its
    ``skill_dirs()``. Failure to resolve a type or read its dirs is logged and
    skipped — discovery must never crash agent construction over a missing
    skill source. Duplicate ``(name, dir)`` pairs are removed.

    :param env_module_types: Registry env-module type keys.
    :returns: Ordered, de-duplicated ``(module_class_name, skill_dir_str)`` pairs.
    """
    if not env_module_types:
        return []
    try:
        from agentsociety2.registry import get_registered_env_modules
    except Exception:  # pragma: no cover - defensive
        return []
    type_map = dict(get_registered_env_modules())
    seen: set[tuple[str, str]] = set()
    result: list[tuple[str, str]] = []
    for module_type in env_module_types:
        env_class = type_map.get(module_type)
        if env_class is None:
            continue
        try:
            skill_dirs = env_class.skill_dirs()
        except Exception:
            continue
        # ``skill_dirs()`` is a classmethod declared on the ``EnvBase``
        # metaclass, so ``type(env_class)`` would yield the metaclass name
        # (``EnvMeta``) — use ``env_class.__name__`` to match the concrete
        # module class name the in-process path produces via
        # ``type(module).__name__`` on instances.
        class_name = env_class.__name__
        for skills_dir in skill_dirs or []:
            pair = (class_name, str(skills_dir))
            if pair[1] and pair not in seen:
                seen.add(pair)
                result.append(pair)
    return result
