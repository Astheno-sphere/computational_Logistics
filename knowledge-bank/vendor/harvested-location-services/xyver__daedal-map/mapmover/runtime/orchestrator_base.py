"""Shared base behavior for lane orchestrators."""

from __future__ import annotations

from mapmover.orchestrator_specs import OrchestratorSpec
from mapmover.progress_bus import ProgressEvent
from mapmover.runtime.llm_policy import build_provider_client, resolve_lane_llm_selection
from mapmover.runtime.orchestrator_threading import (
    run_catalog_scoped_to_thread,
    run_catalog_scoped_to_thread_with_progress,
)
from mapmover.runtime.prompt_runtime import build_cached_system_prompt_blocks
from mapmover.runtime.warning_policy import DEFAULT_DISPLAY_WARNING_POLICY


class BaseOrchestrator:
    """Shared runtime behavior that should not drift across lane orchestrators."""

    heartbeat_policy_value = None
    display_warning_policy_value = DEFAULT_DISPLAY_WARNING_POLICY

    def __init__(self, spec: OrchestratorSpec):
        self.spec = spec

    def heartbeat(self, idle_count: int) -> ProgressEvent:
        from mapmover.runtime.orchestrator_policy import build_heartbeat_event

        return build_heartbeat_event(
            idle_count=idle_count,
            policy=self.heartbeat_policy(),
            progress_event_cls=ProgressEvent,
        )

    def build_system_prompt_blocks(self, prompt_text: str) -> list[dict]:
        return build_cached_system_prompt_blocks(prompt_text)

    def display_warning_policy(self):
        return self.spec.display_warning_policy_obj or self.display_warning_policy_value

    def heartbeat_policy(self):
        return self.spec.heartbeat_policy_obj or self.heartbeat_policy_value

    def retry_policy(self):
        return self.spec.retry_policy_obj

    async def run_catalog_scoped_thread(
        self,
        *,
        catalog_surface: str | None,
        func,
        **kwargs,
    ):
        return await run_catalog_scoped_to_thread(
            catalog_surface=catalog_surface,
            func=func,
            **kwargs,
        )

    async def run_catalog_scoped_thread_with_progress(
        self,
        *,
        catalog_surface: str | None,
        progress_bus_cls,
        func,
        **kwargs,
    ):
        return await run_catalog_scoped_to_thread_with_progress(
            catalog_surface=catalog_surface,
            progress_bus_cls=progress_bus_cls,
            func=func,
            **kwargs,
        )

    def llm_selection(self, override: dict | None = None):
        return resolve_lane_llm_selection(
            self.spec.model_policy,
            override=override,
        )

    def build_client(self, llm_selection):
        return build_provider_client(llm_selection)

    def build_llm_runtime_context(
        self,
        prompt_text: str,
        *,
        override: dict | None = None,
    ) -> dict:
        llm_selection = self.llm_selection(override=override)
        return {
            "system_blocks": self.build_system_prompt_blocks(prompt_text),
            "llm_selection": llm_selection,
            "client": self.build_client(llm_selection),
        }
