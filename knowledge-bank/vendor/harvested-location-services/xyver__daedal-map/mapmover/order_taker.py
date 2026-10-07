"""
Order Taker - interprets user requests into structured orders.
Single LLM call using catalog.json and conversions.json for data awareness.
"""

from __future__ import annotations

from dotenv import load_dotenv

from .constants import CHAT_HISTORY_LLM_LIMIT
from .data_loading import load_catalog
from .llm_tools import execute_tool, format_tool_result_for_llm, format_tools_for_provider
from .progress_bus import ProgressEvent
from .runtime.preprocessor_context_runtime import build_tier3_context, build_tier4_context
from .runtime.llm_policy import (
    build_provider_runtime_context,
    resolve_lane_llm_selection,
    sampling_kwargs,
)
from .runtime.geography_reference import load_conversions
from .runtime.prompt_runtime import build_cached_system_prompt_blocks
from .explore_prompt import build_explore_system_prompt
from .runtime.order_taker_response import parse_llm_response


EXPLORER_TOOL_PROGRESS_MESSAGES = {
    "get_source_details": "Looking up source details...",
    "get_source_reference": "Reading source documentation...",
    "list_source_metrics": "Listing available metrics...",
    "list_multiple_sources_metrics": "Comparing source metrics...",
    "list_packs": "Listing available packs...",
    "get_pack_details": "Looking up pack details...",
}

load_dotenv()


def interpret_request(
    user_query: str,
    chat_history: list = None,
    hints: dict = None,
    progress=None,
    usage_recorder=None,
    system_prompt_builder=build_explore_system_prompt,
    system_prompt_block_builder=build_cached_system_prompt_blocks,
    llm_selection=None,
) -> dict:
    """
    Interpret user request and return structured order or response.
    """
    catalog = load_catalog()
    conversions = load_conversions()
    system_prompt = system_prompt_builder(catalog, conversions)

    messages = [{"role": "system", "content": system_prompt}]
    if hints:
        context_parts = []
        tier3_context = build_tier3_context(hints)
        if tier3_context:
            context_parts.append(tier3_context)
        tier4_context = build_tier4_context(hints)
        if tier4_context:
            context_parts.append(tier4_context)
        if context_parts:
            messages.append({
                "role": "system",
                "content": "[CURRENT CONTEXT - USE THIS FOR THE CURRENT QUERY]\n" + "\n".join(context_parts),
            })

    if chat_history:
        for msg in chat_history[-CHAT_HISTORY_LLM_LIMIT:]:
            content = msg.get("content", "")
            if not content or not content.strip():
                continue
            messages.append({
                "role": msg.get("role", "user"),
                "content": content,
            })

    messages.append({"role": "user", "content": user_query})

    llm_runtime = build_provider_runtime_context(
        selection=llm_selection or resolve_lane_llm_selection("explore_fast_haiku_default")
    )
    llm_selection = llm_runtime["llm_selection"]
    client = llm_runtime["client"]
    system_content = ""
    chat_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_content += msg["content"] + "\n\n"
        else:
            chat_messages.append(msg)

    tools = format_tools_for_provider("anthropic")
    max_tool_iterations = 3
    system_blocks = system_prompt_block_builder(system_content.strip())

    from .llm_usage import ensure_recorder

    usage_recorder, owns_recorder = ensure_recorder(
        usage_recorder, surface="explorer", call_kind="order_taker",
    )
    try:
        for iteration in range(max_tool_iterations + 1):
            response = client.messages.create(
                model=llm_selection.model,
                system=system_blocks,
                messages=chat_messages,
                tools=tools,
                max_tokens=500,
                **sampling_kwargs(llm_selection.model, llm_selection.temperature),
            )
            if usage_recorder is not None:
                usage_recorder.record(response)

            if response.stop_reason == "tool_use":
                tool_results = []
                # Preserve the provider's complete assistant turn verbatim.
                # Sonnet 5 enables adaptive thinking by default and requires
                # thinking blocks (including their signatures) to be passed
                # back unchanged on the next tool-loop request.
                assistant_content = list(response.content)
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        if progress is not None:
                            friendly = EXPLORER_TOOL_PROGRESS_MESSAGES.get(
                                tool_name,
                                f"Running {tool_name}...",
                            )
                            progress(ProgressEvent(
                                stage="tool",
                                message=friendly,
                                extra={"tool": tool_name, "iteration": iteration},
                            ))
                        result = execute_tool(tool_name, tool_input)
                        formatted_result = format_tool_result_for_llm(result)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": formatted_result,
                        })

                chat_messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                })
                chat_messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                continue
            break

        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text
        return parse_llm_response(content.strip(), hints=hints, user_query=user_query)
    finally:
        if owns_recorder:
            usage_recorder.flush(skip_if_empty=True)
