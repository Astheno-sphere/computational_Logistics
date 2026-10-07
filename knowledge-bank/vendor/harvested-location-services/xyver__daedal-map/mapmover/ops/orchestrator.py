"""Ops lane orchestrator."""

from __future__ import annotations

from mapmover.ops_prompt import build_ops_system_prompt
from mapmover.ops_orchestrator_runtime import run_ops_chat
from mapmover.ops_watch_runtime import preload_ops_watch_scope
from mapmover.orchestrator_specs import OPS_ORCHESTRATOR_SPEC, OrchestratorSpec
from mapmover.progress_bus import ProgressEvent
from mapmover.runtime.orchestrator_base import BaseOrchestrator


class OpsOrchestrator(BaseOrchestrator):
    """Behavior-preserving Ops shell on top of the shared runtime spine."""

    def __init__(self, spec: OrchestratorSpec = OPS_ORCHESTRATOR_SPEC):
        super().__init__(spec)

    def preprocess(
        self,
        *,
        query: str,
        watch_context: dict | None = None,
    ) -> dict:
        return preload_ops_watch_scope(query=query, watch_context=watch_context)

    def build_system_prompt(
        self,
        watch_context: dict | None = None,
        hints: dict | None = None,
    ) -> str:
        return build_ops_system_prompt(watch_context=watch_context, hints=hints)

    async def run(
        self,
        *,
        query: str,
        chat_history: list | None,
        watch: dict,
        effective_feeds: list[str],
        usage_recorder,
        catalog_surface: str | None,
        cache,
        selected_popup: dict | None = None,
    ) -> dict:
        return await self.run_catalog_scoped_thread(
            catalog_surface=catalog_surface,
            func=run_ops_chat,
            query=query,
            chat_history=chat_history,
            watch=watch,
            effective_feeds=effective_feeds,
            ops_orchestrator=self,
            usage_recorder=usage_recorder,
            cache=cache,
            selected_popup=selected_popup,
        )
