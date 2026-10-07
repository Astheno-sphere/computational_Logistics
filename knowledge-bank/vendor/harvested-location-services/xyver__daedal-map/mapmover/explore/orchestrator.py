"""Explore lane orchestrator."""

from __future__ import annotations

import asyncio

from mapmover.explore.explore_followups import compact_followup_message
from mapmover.explore.explore_request_context import apply_resolved_location_override
from mapmover.explore.explore_runtime import (
    finalize_explore_order_result,
    preprocess_explore_request,
)
from mapmover.orchestrator_specs import EXPLORE_ORCHESTRATOR_SPEC, OrchestratorSpec
from mapmover.runtime.orchestrator_base import BaseOrchestrator
from mapmover.runtime.orchestrator_helper_runtime import (
    apply_runtime_result_cap_to_payload_result,
    maybe_build_explainer_chat_response,
)
from mapmover.runtime.orchestrator_policy import (
    DEFAULT_EXPLORE_COMPLEXITY_POLICY,
)
from mapmover.runtime.postprocess_contracts import get_display_items
from mapmover.runtime.postprocess_runtime import run_postprocess_order as postprocess_order
from mapmover.explore_prompt import build_explore_system_prompt
from mapmover.runtime.warning_policy import DEFAULT_METRIC_WARNING_POLICY
from mapmover.order_taker import interpret_request
from mapmover.explore.preprocessor_runtime import preprocess_query
from mapmover.progress_bus import ProgressBus, ProgressEvent

class ExploreOrchestrator(BaseOrchestrator):
    """Behavior-preserving Explore workflow wrapper."""

    def __init__(self, spec: OrchestratorSpec = EXPLORE_ORCHESTRATOR_SPEC):
        super().__init__(spec)

    def preprocess(
        self,
        *,
        query: str,
        viewport,
        active_overlays,
        cache_stats,
        saved_order_names,
        time_state,
        loaded_data,
        resolved_location,
        selected_popup=None,
    ) -> dict:
        return preprocess_explore_request(
            query=query,
            viewport=viewport,
            active_overlays=active_overlays,
            cache_stats=cache_stats,
            saved_order_names=saved_order_names,
            time_state=time_state,
            loaded_data=loaded_data,
            resolved_location=resolved_location,
            selected_popup=selected_popup,
            preprocess_query_func=preprocess_query,
            apply_resolved_location_override_func=apply_resolved_location_override,
        )

    async def interpret(
        self,
        *,
        query: str,
        chat_history: list,
        hints: dict,
        usage_recorder,
        catalog_surface: str | None,
    ) -> dict:
        return await self.run_catalog_scoped_thread(
            catalog_surface=catalog_surface,
            func=interpret_request,
            user_query=query,
            chat_history=chat_history,
            hints=hints,
            usage_recorder=usage_recorder,
            system_prompt_builder=self.build_system_prompt,
            system_prompt_block_builder=self.build_system_prompt_blocks,
            llm_selection=self.llm_selection(),
        )

    async def interpret_with_progress(
        self,
        *,
        query: str,
        chat_history: list,
        hints: dict,
        usage_recorder,
        catalog_surface: str | None,
    ) -> tuple[ProgressBus, asyncio.Task]:
        return await self.run_catalog_scoped_thread_with_progress(
            catalog_surface=catalog_surface,
            progress_bus_cls=ProgressBus,
            func=interpret_request,
            user_query=query,
            chat_history=chat_history,
            hints=hints,
            usage_recorder=usage_recorder,
            system_prompt_builder=self.build_system_prompt,
            system_prompt_block_builder=self.build_system_prompt_blocks,
            llm_selection=self.llm_selection(),
        )

    def finalize_order(
        self,
        *,
        result: dict,
        hints: dict,
        force_metrics: bool,
        build_clarify_response_func,
        build_metric_warning_response_func,
        build_order_response_func,
    ) -> tuple[str, dict]:
        return finalize_explore_order_result(
            result=result,
            hints=hints,
            force_metrics=force_metrics,
            metric_warning_policy=self.metric_warning_policy(),
            postprocess_order_func=postprocess_order,
            get_display_items_func=get_display_items,
            build_clarify_response_func=build_clarify_response_func,
            build_metric_warning_response_func=build_metric_warning_response_func,
            build_order_response_func=build_order_response_func,
            complexity_policy=self.complexity_policy(),
        )

    def metric_warning_policy(self):
        return DEFAULT_METRIC_WARNING_POLICY

    def complexity_policy(self):
        return DEFAULT_EXPLORE_COMPLEXITY_POLICY

    def build_system_prompt(self, catalog: dict, conversions: dict) -> str:
        return build_explore_system_prompt(catalog, conversions)

    def compact_followup(self, message: str) -> str:
        return compact_followup_message(message)

    def maybe_build_explainer_response(
        self,
        *,
        query: str,
        hints: dict | None,
        build_chat_response_func,
        auth_user: dict | None = None,
        load_source_metadata_func=None,
        load_source_reference_func=None,
    ) -> dict | None:
        return maybe_build_explainer_chat_response(
            query=query,
            hints=hints,
            build_chat_response_func=build_chat_response_func,
            auth_user=auth_user,
            load_source_metadata_func=load_source_metadata_func,
            load_source_reference_func=load_source_reference_func,
            lane="explore",
        )

    def apply_runtime_result_cap(
        self,
        result: dict,
        *,
        confirmed_order: dict | None = None,
        load_source_metadata_func=None,
    ) -> dict:
        return apply_runtime_result_cap_to_payload_result(
            result,
            confirmed_order=confirmed_order,
            load_source_metadata_func=load_source_metadata_func,
        )
