"""Lane-specific Research chat runtime helpers."""

from __future__ import annotations

import hashlib
import json
import uuid

from mapmover import logger
from mapmover.corpus_registry import corpus_registry
from mapmover.progress_bus import ProgressEvent
from mapmover.research_chat_helpers import (
    RESEARCH_MAX_TOKENS,
    _broad_research_fallback_message,
    _compact_manifest_for_prompt,
    _compact_tool_result_for_prompt,
    _content_block_types,
    _extract_text,
    _fallback_display_message,
    _history_messages,
    _research_map_payload_from_tool_result,
    _research_memory_messages,
    _temperature_kwargs,
    _tool_call_signature,
)
from mapmover.research_postprocessor import normalize_research_result
from mapmover.research_preprocessor import build_research_hint_context, preprocess_research_query
from mapmover.research_prompt import build_research_system_prompt
from mapmover.research_runtime import (
    build_research_messages,
    finalize_research_response,
    run_research_final_synthesis,
    run_research_tool_loop,
)
from mapmover.research_tools import RESEARCH_TOOL_DEFINITIONS, execute_research_tool
from mapmover.runtime.orchestrator_policy import DEFAULT_RESEARCH_RETRY_POLICY
from mapmover.runtime.llm_policy import (
    build_provider_runtime_context,
    resolve_lane_llm_selection,
)
from mapmover.runtime.prompt_runtime import build_cached_system_prompt_blocks
from mapmover.runtime.research_retry_runtime import (
    build_research_tool_guardrail_message,
    run_research_rescue_synthesis,
)
from mapmover.runtime.warning_primitives import build_display_warning_result
from mapmover.llm_usage import ensure_recorder


RESEARCH_TOOL_PROGRESS_MESSAGES = {
    "ask_research_sources": "Binding the Research source corpus...",
    "get_research_pack": "Inspecting the published source contract...",
    "query_research_source_data": "Querying grounded source rows...",
    "build_artifact_display_subset": "Preparing the map display...",
}

def json_dumps_safe(value) -> str:
    return json.dumps(value, default=str)


def research_request_id(session_id: str, query: str) -> str:
    query_hash = hashlib.md5((query or "").encode("utf-8")).hexdigest()[:8]
    session_hash = hashlib.md5((session_id or "").encode("utf-8")).hexdigest()[:8]
    return f"research_{session_hash}_{query_hash}_{uuid.uuid4().hex[:8]}"


def run_research_chat(
    *,
    session_id: str,
    query: str,
    chat_history: list | None = None,
    research_memory: dict | None = None,
    progress=None,
    force_large_display: bool = False,
    usage_recorder=None,
    rescue_usage_recorder=None,
    display_warning_policy=None,
    retry_policy=None,
    system_prompt_builder=build_research_system_prompt,
    system_prompt_block_builder=build_cached_system_prompt_blocks,
    llm_selection=None,
) -> dict:
    """Synchronous research pipeline."""
    retry_policy = retry_policy or DEFAULT_RESEARCH_RETRY_POLICY
    manifest = corpus_registry.manifest(session_id)
    if manifest.get("artifact_count", 0) == 0 and not manifest.get("saved_corpus"):
        return {
            "type": "chat",
            "message": "No data is loaded into the Research workspace yet. Select a saved corpus and load it into Research first.",
            "corpus": manifest,
        }
    if manifest.get("artifact_count", 0) == 0 and manifest.get("saved_corpus"):
        saved = manifest.get("saved_corpus") or {}
        pack_count = int(saved.get("pack_count") or 0)
        source_count = int(saved.get("source_count") or 0)
        return {
            "type": "chat",
            "message": (
                f'Research workspace "{saved.get("name") or "Saved corpus"}" is selected, '
                f'with {pack_count} pack{"s" if pack_count != 1 else ""}'
                + (
                    f' and {source_count} direct source{"s" if source_count != 1 else ""}'
                    if source_count
                    else ""
                )
                + ". I can use that workspace definition to stay oriented, but I do not have loaded Research artifacts to analyze yet. "
                  "Load that corpus into Research first, or expand the Research loader later so this corpus hydrates concrete artifacts."
            ),
            "corpus": manifest,
        }

    llm_runtime = build_provider_runtime_context(
        selection=llm_selection or resolve_lane_llm_selection("research_deep_sonnet_opus_default")
    )
    llm_selection = llm_runtime["llm_selection"]
    model = llm_runtime["model"]
    temperature = llm_runtime["temperature"]
    system_prompt = system_prompt_builder(manifest)
    research_hints = preprocess_research_query(query, manifest)
    hint_context = build_research_hint_context(research_hints)
    prompt_manifest = _compact_manifest_for_prompt(manifest)
    system_prompt_blocks = system_prompt_block_builder(system_prompt)
    messages = build_research_messages(
        prompt_manifest=prompt_manifest,
        hint_context=hint_context,
        research_memory=research_memory,
        chat_history=chat_history,
        query=query,
        research_memory_messages_func=_research_memory_messages,
        history_messages_func=_history_messages,
    )

    client = llm_runtime["client"]
    usage_recorder, owns_main = ensure_recorder(
        usage_recorder,
        surface="research",
        call_kind="research_main",
        session_id=session_id,
    )
    rescue_usage_recorder, owns_rescue = ensure_recorder(
        rescue_usage_recorder,
        surface="research",
        call_kind="research_rescue",
        session_id=session_id,
    )
    try:
        tool_state = run_research_tool_loop(
            client=client,
            model=model,
            temperature=temperature,
            system_prompt_blocks=system_prompt_blocks,
            messages=messages,
            max_tool_iterations=(retry_policy.max_tool_iterations if retry_policy is not None else 8),
            research_tool_definitions=RESEARCH_TOOL_DEFINITIONS,
            max_tokens=RESEARCH_MAX_TOKENS,
            temperature_kwargs_func=_temperature_kwargs,
            usage_recorder=usage_recorder,
            session_id=session_id,
            query=query,
            manifest=manifest,
            logger=logger,
            progress=progress,
            progress_event_cls=ProgressEvent,
            progress_messages=RESEARCH_TOOL_PROGRESS_MESSAGES,
            execute_research_tool_func=execute_research_tool,
            force_large_display=force_large_display,
            display_warning_policy=display_warning_policy,
            tool_call_signature_func=_tool_call_signature,
            research_map_payload_from_tool_result_func=_research_map_payload_from_tool_result,
            compact_tool_result_for_prompt_func=_compact_tool_result_for_prompt,
            build_guardrail_message_func=lambda **kwargs: build_research_tool_guardrail_message(
                retry_policy=retry_policy,
                **kwargs,
            ),
        )
        response = tool_state["response"]
        messages = tool_state["messages"]
        display_warning = tool_state["display_warning"]
        final_display = tool_state["final_display"]
        final_displays = tool_state["final_displays"]
        tool_iterations_used = tool_state["tool_iterations_used"]

        if display_warning:
            logger.info(
                "Research display warning session=%s query=%r level=%s row_count=%s soft_cap=%s hard_cap=%s force=%s",
                session_id,
                query[:120],
                display_warning.get("level"),
                display_warning.get("row_count"),
                display_warning.get("soft_cap"),
                display_warning.get("hard_cap"),
                force_large_display,
            )
            return build_display_warning_result(
                display_warning or {},
                corpus=manifest,
                query=query,
            )

        if response and response.stop_reason == "tool_use":
            response = run_research_final_synthesis(
                client=client,
                model=model,
                temperature=temperature,
                system_prompt_blocks=system_prompt_blocks,
                messages=messages,
                max_tokens=RESEARCH_MAX_TOKENS,
                temperature_kwargs_func=_temperature_kwargs,
                usage_recorder=usage_recorder,
                progress=progress,
                progress_event_cls=ProgressEvent,
                logger=logger,
                session_id=session_id,
                query=query,
            )

        final_result = finalize_research_response(
            response=response,
            client=client,
            model=model,
            temperature=temperature,
            system_prompt_blocks=system_prompt_blocks,
            messages=messages,
            session_id=session_id,
            query=query,
            manifest=manifest,
            research_hints=research_hints,
            final_display=final_display,
            final_displays=final_displays,
            tool_iterations_used=tool_iterations_used,
            rescue_usage_recorder=rescue_usage_recorder,
            progress=progress,
            progress_event_cls=ProgressEvent,
            logger=logger,
            extract_text_func=_extract_text,
            content_block_types_func=_content_block_types,
            run_research_rescue_synthesis_func=lambda **kwargs: run_research_rescue_synthesis(
                retry_policy=retry_policy,
                temperature_kwargs_func=_temperature_kwargs,
                ensure_recorder_func=ensure_recorder,
                logger=logger,
                max_tokens=RESEARCH_MAX_TOKENS,
                **kwargs,
            ),
            fallback_display_message_func=_fallback_display_message,
            broad_research_fallback_message_func=_broad_research_fallback_message,
            normalize_research_result_func=normalize_research_result,
        )
        # Keep an auditable record of the bounded tool choices behind this
        # answer. It contains inputs/outcomes only, never copied source rows.
        final_result["research_tool_trace"] = tool_state.get("tool_trace") or []
        return final_result
    finally:
        if owns_main:
            usage_recorder.flush(skip_if_empty=True)
        if owns_rescue:
            rescue_usage_recorder.flush(skip_if_empty=True)
