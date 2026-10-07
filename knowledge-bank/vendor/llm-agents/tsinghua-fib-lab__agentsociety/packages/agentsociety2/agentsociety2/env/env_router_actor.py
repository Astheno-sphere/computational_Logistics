"""Ray actor owning the CodeGenRouter (env router).

Moving the env router into a dedicated Ray actor takes env codegen execution
(and its former ``_execute_lock`` serialization) off the agents' event loop.
A single Ray actor processes one method at a time (FIFO), which provides the
same mutual exclusion the lock did, but in a separate process/loop.

The actor is built from a serializable spec (env-module types + kwargs +
codegen kwargs). LLM is **injected** as serializable :class:`LLMClient` handles
(coder + default) carrying connection parameters; each actor process builds its
own litellm Router on first use. Replay is injected as a serializable
:class:`ReplayProxy`. The actor never self-creates central runtime services, so
there is no Ray-in-Ray (D8).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

# Module-level cache for the Ray actor class, keyed by max_concurrency. ``import
# ray`` is deferred so importing this module never requires Ray.
_cached_env_actor_classes: dict[int, Any] = {}


def get_env_router_actor_class(max_concurrency: int = 1) -> Any:
    """Return (creating once per max_concurrency) the Ray env-router actor class.

    :param max_concurrency: Ray actor concurrency. ``1`` serializes ask calls
        (default when any env module is not concurrency-safe); ``>1`` allows
        parallel async ask calls only when all env modules declare
        ``is_concurrency_safe()``.
    :returns: A Ray actor class (``@ray.remote(max_concurrency=...)``).
    """
    if max_concurrency in _cached_env_actor_classes:
        return _cached_env_actor_classes[max_concurrency]

    import ray  # deferred import

    class EnvRouterActor:
        """Owns a CodeGenRouter; lifecycle + ask methods run on its own loop."""

        def __init__(
            self,
            env_module_types: list[str],
            env_kwargs: dict[str, dict[str, Any]],
            run_dir: str | None,
            codegen_kwargs: dict[str, Any] | None,
            llm_clients_spec: dict[str, Any] | None = None,
            replay_proxy: Any = None,
            trace_proxy: Any = None,
        ) -> None:
            """Create the env router inside the actor process.

            :param env_module_types: Serializable env-module type keys.
            :param env_kwargs: Per-type constructor kwargs.
            :param run_dir: Run directory (assigned to ``router.run_dir``).
            :param codegen_kwargs: CodeGenRouter kwargs
                (e.g. ``final_summary_enabled``).
            :param llm_clients_spec: Optional dict with ``coder`` / ``default``
                keys, each a serialized :class:`LLMClient`. When ``None``, the
                router falls back to the per-process dispatcher client factory.
            :param replay_proxy: Optional :class:`ReplayProxy` for shared
                sharded JSONL replay. When ``None`` / disabled, env replay is off.
            :param trace_proxy: Optional :class:`TraceProxy` for env-side
                ``llm.completion`` spans. When ``None``, env LLM calls are untraced.
            """
            from agentsociety2.env.router_codegen import CodeGenRouter
            from agentsociety2.registry import get_registered_env_modules, get_registry

            if run_dir is not None:
                custom_root = Path(run_dir)
                if (custom_root / "custom").is_dir():
                    get_registry().set_workspace(custom_root)

            env_type_map = dict(get_registered_env_modules())
            env_modules = []
            for module_type in env_module_types:
                env_class = env_type_map[module_type]
                env_modules.append(env_class(**env_kwargs.get(module_type, {})))

            self._router = CodeGenRouter(
                env_modules=env_modules,
                replay_writer=None,
                llm_clients_spec=llm_clients_spec,
                **(codegen_kwargs or {}),
            )
            if run_dir is not None:
                self._router.run_dir = run_dir
                # 模块状态只存在于本 actor 进程，故在此绑定各模块到
                # ``<run_dir>/env/<module_type>``，供 RouterBase.init 恢复、
                # society 每步 to_workspace。
                self._router.bind_env_workspaces(
                    Path(run_dir) / "env", env_module_types
                )
            # Shared replay proxy: when set, env modules and agents append to
            # the same replay directory through process-local ReplaySink objects.
            self._replay_proxy = replay_proxy
            # Trace proxy: when set, env-side LLM calls emit spans via this
            # actor's own local ShardedAppendSink (same trace store as agents,
            # distributed — no central actor).
            self._trace_proxy = trace_proxy
            if trace_proxy is not None:
                from agentsociety2.trace import build_local_sink

                sink = build_local_sink(trace_proxy)
                if sink is not None:
                    self._router.set_trace_sink(sink)

        async def init(self, start_datetime: datetime) -> bool:
            if self._replay_proxy is not None:
                self._router.set_replay_writer(self._replay_proxy)
            # RouterBase.init 会先跑各模块 init() 再恢复 checkpoint（resume）。
            return await self._router.init(start_datetime)

        async def to_workspaces(self) -> None:
            """把各 env 模块状态写入 workspace（每步）。"""
            await self._router.to_workspaces()

        async def from_workspaces(self) -> bool:
            """从 workspace 恢复 env 模块状态（resume）。"""
            return await self._router.from_workspaces()

        def set_current_time(self, t: datetime) -> None:
            self._router.set_current_time(t)

        def set_replay_writer(self, writer: Any) -> None:
            """Inject a replay writer/proxy into the router (and its modules).

            ``writer`` is typically a serializable :class:`ReplayProxy`. Also
            stored on ``self._replay_proxy`` so :meth:`init` routes env replay
            to the shared replay directory.
            """
            self._replay_proxy = writer
            self._router.set_replay_writer(writer)

        async def ask(
            self,
            ctx: dict,
            instruction: str,
            readonly: bool = False,
            template_mode: bool = False,
            trace_id: str | None = None,
            parent_span_id: str | None = None,
        ):
            return await self._router.ask(
                ctx,
                instruction,
                readonly=readonly,
                template_mode=template_mode,
                trace_id=trace_id,
                parent_span_id=parent_span_id,
            )

        async def get_world_description(self) -> str:
            return await self._router.get_world_description()

        def get_token_usages(self) -> dict[str, Any]:
            getter = getattr(self._router, "get_token_usages", None)
            if getter is None:
                return {}
            return getter()

        async def step(self, tick: int, t: datetime) -> None:
            await self._router.step(tick, t)

        async def close(self) -> None:
            await self._router.close()

    # Apply Ray with max_concurrency (>1 allows parallel async ask calls; only
    # safe when all env modules declare is_concurrency_safe()).
    actor_cls = ray.remote(max_concurrency=max_concurrency)(EnvRouterActor)
    _cached_env_actor_classes[max_concurrency] = actor_cls
    return actor_cls
