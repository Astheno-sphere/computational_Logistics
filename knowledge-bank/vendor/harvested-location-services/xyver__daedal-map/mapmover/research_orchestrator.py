"""Research lane orchestrator."""

from __future__ import annotations

import asyncio

from mapmover.orchestrator_specs import OrchestratorSpec, RESEARCH_ORCHESTRATOR_SPEC
from mapmover.progress_bus import ProgressBus, ProgressEvent
from mapmover.research_lane_runtime import run_research_chat
from mapmover.research_orchestrator_runtime import (
    apply_research_runtime_result_cap,
    run_research_orchestrator_sync,
    wrap_research_capped_result_task,
)
from mapmover.runtime.orchestrator_base import BaseOrchestrator
from mapmover.research_prompt import build_research_system_prompt


class ResearchOrchestrator(BaseOrchestrator):
    """Behavior-preserving Research workflow wrapper."""

    def __init__(self, spec: OrchestratorSpec = RESEARCH_ORCHESTRATOR_SPEC):
        super().__init__(spec)

    def apply_runtime_result_cap(
        self,
        result: dict,
        *,
        load_source_metadata_func=None,
    ) -> dict:
        return apply_research_runtime_result_cap(
            result,
            load_source_metadata_func=load_source_metadata_func,
        )

    def build_system_prompt(self, corpus_manifest: dict) -> str:
        return build_research_system_prompt(corpus_manifest)

    async def run(
        self,
        *,
        session_id: str,
        query: str,
        chat_history: list | None,
        research_memory: dict | None,
        force_large_display: bool,
        usage_recorder,
        rescue_usage_recorder,
        catalog_surface: str | None,
    ) -> dict:
        from mapmover.data_loading import load_source_metadata
        return await self.run_catalog_scoped_thread(
            catalog_surface=catalog_surface,
            func=run_research_orchestrator_sync,
            load_source_metadata_func=load_source_metadata,
            run_research_chat_func=run_research_chat,
            session_id=session_id,
            query=query,
            chat_history=chat_history,
            research_memory=research_memory,
            force_large_display=force_large_display,
            usage_recorder=usage_recorder,
            rescue_usage_recorder=rescue_usage_recorder,
            display_warning_policy=self.display_warning_policy(),
            retry_policy=self.retry_policy(),
            system_prompt_builder=self.build_system_prompt,
            system_prompt_block_builder=self.build_system_prompt_blocks,
            llm_selection=self.llm_selection(),
        )

    async def run_with_progress(
        self,
        *,
        session_id: str,
        query: str,
        chat_history: list | None,
        research_memory: dict | None,
        force_large_display: bool,
        usage_recorder,
        rescue_usage_recorder,
        catalog_surface: str | None,
    ) -> tuple[ProgressBus, asyncio.Task]:
        from mapmover.data_loading import load_source_metadata
        bus, raw_task = await self.run_catalog_scoped_thread_with_progress(
            catalog_surface=catalog_surface,
            progress_bus_cls=ProgressBus,
            func=run_research_chat,
            session_id=session_id,
            query=query,
            chat_history=chat_history,
            research_memory=research_memory,
            force_large_display=force_large_display,
            usage_recorder=usage_recorder,
            rescue_usage_recorder=rescue_usage_recorder,
            display_warning_policy=self.display_warning_policy(),
            retry_policy=self.retry_policy(),
            system_prompt_builder=self.build_system_prompt,
            system_prompt_block_builder=self.build_system_prompt_blocks,
            llm_selection=self.llm_selection(),
        )
        return bus, wrap_research_capped_result_task(
            raw_task=raw_task,
            load_source_metadata_func=load_source_metadata,
        )
