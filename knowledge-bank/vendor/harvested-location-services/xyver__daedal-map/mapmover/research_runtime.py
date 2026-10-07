"""Shared helper routines for the Research chat runtime."""

from __future__ import annotations

import json


def _requires_cross_source_query_evidence(query: str) -> bool:
    """Return whether a question needs returned rows, not metadata alone.

    Source contracts can establish what is *possible*, but cannot establish that
    two sources actually share compatible rows.  Keep this deliberately narrow
    so definition/availability questions remain metadata-only.
    """
    normalized = " ".join(str(query or "").casefold().split())
    cross_source_terms = (
        "normalized", "per capita", "per-capita", "join", "bridge",
    )
    return any(term in normalized for term in cross_source_terms)


def _has_loc_id_bridge_query(tool_trace: list[dict]) -> bool:
    """Whether a cross-source answer actually tried a returned loc_id bridge."""
    for entry in tool_trace:
        if not isinstance(entry, dict) or entry.get("name") != "query_research_source_data":
            continue
        query = (entry.get("input") or {}).get("query") or {}
        filters = query.get("filters") or {} if isinstance(query, dict) else {}
        if isinstance(filters, dict) and filters.get("region_ids"):
            return True
    return False


def build_research_messages(
    *,
    prompt_manifest: dict,
    hint_context: str,
    research_memory: dict | None,
    chat_history: list | None,
    query: str,
    research_memory_messages_func,
    history_messages_func,
) -> list[dict]:
    """Build the Anthropic message array for one Research request."""
    return [
        {
            "role": "user",
            "content": [{
                "type": "text",
                "text": "Active corpus manifest JSON:\n" + json.dumps(prompt_manifest, default=str, separators=(",", ":")),
                "cache_control": {"type": "ephemeral"},
            }],
        },
        *(
            [{
                "role": "user",
                "content": "Research preprocessor hints:\n" + hint_context,
            }]
            if hint_context else []
        ),
        *research_memory_messages_func(research_memory),
        *history_messages_func(chat_history or []),
        {"role": "user", "content": query},
    ]


def run_research_tool_loop(
    *,
    client,
    model: str,
    temperature: float,
    system_prompt_blocks: list[dict],
    messages: list[dict],
    max_tool_iterations: int,
    research_tool_definitions,
    max_tokens: int,
    temperature_kwargs_func,
    usage_recorder,
    session_id: str,
    query: str,
    manifest: dict,
    logger,
    progress,
    progress_event_cls,
    progress_messages: dict,
    execute_research_tool_func,
    force_large_display: bool,
    display_warning_policy,
    tool_call_signature_func,
    research_map_payload_from_tool_result_func,
    compact_tool_result_for_prompt_func,
    build_guardrail_message_func,
):
    """Run the Research tool loop until text synthesis or a display warning."""
    response = None
    final_display = None
    final_displays: list[dict] = []
    display_warning = None
    tool_iterations_used = 0
    tool_trace: list[dict] = []
    recent_tool_signatures: list[str] = []
    last_guardrail_message: str | None = None
    missing_cross_source_evidence_prompted = False
    missing_loc_id_bridge_prompted = False

    for iteration in range(max_tool_iterations + 1):
        try:
            response = client.messages.create(
                model=model,
                system=system_prompt_blocks,
                messages=messages,
                tools=research_tool_definitions,
                max_tokens=max_tokens,
                **temperature_kwargs_func(model, temperature),
            )
            if usage_recorder is not None:
                usage_recorder.record(response)
        except Exception:
            approx_message_chars = sum(len(json.dumps(message, default=str)) for message in messages)
            logger.exception(
                "Research Anthropic call failed iteration=%s session=%s query=%r approx_message_chars=%s artifact_count=%s",
                iteration,
                session_id,
                query[:120],
                approx_message_chars,
                manifest.get("artifact_count"),
            )
            raise

        if response.stop_reason != "tool_use":
            has_data_query = any(
                entry.get("name") == "query_research_source_data"
                for entry in tool_trace
                if isinstance(entry, dict)
            )
            if (
                not missing_cross_source_evidence_prompted
                and _requires_cross_source_query_evidence(query)
                and not has_data_query
            ):
                # Do not let a fluent metadata-only response turn a possible
                # join into a claimed one. Give the model one bounded repair
                # turn to obtain row evidence, then let its final answer stand.
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "This cross-source comparison has no returned data-query evidence yet. "
                        "Before answering, call query_research_source_data for the relevant "
                        "sources. For a claimed join, verify a compatible real row or state "
                        "plainly that the join is not confirmed."
                    ),
                })
                missing_cross_source_evidence_prompted = True
                continue
            if (
                _requires_cross_source_query_evidence(query)
                and has_data_query
                and not missing_loc_id_bridge_prompted
                and not _has_loc_id_bridge_query(tool_trace)
            ):
                # Independent top-N samples are not join evidence. Require the
                # second source to be queried with a concrete loc_id obtained
                # from the first source, or a plainly bounded non-confirmation.
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": (
                        "The returned queries are independent samples, not a loc_id bridge. "
                        "Take one concrete loc_id returned by one source and query the other "
                        "source with filters.region_ids for that exact id. Only then claim a "
                        "compatible join; otherwise say the attempted exact-id bridge did not match."
                    ),
                })
                missing_loc_id_bridge_prompted = True
                continue
            break
        tool_iterations_used += 1

        assistant_content = []
        tool_results = []
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                if progress is not None:
                    friendly = progress_messages.get(
                        block.name,
                        f"Running {block.name}...",
                    )
                    progress(progress_event_cls(
                        stage="tool",
                        message=friendly,
                        extra={"tool": block.name, "iteration": iteration},
                    ))
                tool_result = execute_research_tool_func(
                    session_id,
                    block.name,
                    block.input,
                    force_large_display=force_large_display,
                    display_warning_policy=display_warning_policy,
                    original_query=query,
                )
                tool_trace.append(
                    {
                        "name": block.name,
                        "input": block.input if isinstance(block.input, dict) else {},
                        "outcome": tool_result.get("outcome") if isinstance(tool_result, dict) else None,
                        "effective_metrics": (
                            list(tool_result.get("metrics") or [])
                            if isinstance(tool_result, dict) and block.name == "query_research_source_data"
                            else []
                        ),
                        "error_code": (
                            ((tool_result.get("error") or {}).get("code"))
                            if isinstance(tool_result, dict) and isinstance(tool_result.get("error"), dict)
                            else None
                        ),
                    }
                )
                recent_tool_signatures.append(tool_call_signature_func(block.name, block.input))
                if len(recent_tool_signatures) > 8:
                    recent_tool_signatures = recent_tool_signatures[-8:]
                if isinstance(tool_result, dict) and isinstance(tool_result.get("display_warning"), dict):
                    display_warning = tool_result.get("display_warning")
                if (
                    isinstance(tool_result, dict)
                    and block.name == "build_artifact_display_subset"
                    and tool_result.get("geojson")
                ):
                    final_display = research_map_payload_from_tool_result_func(tool_result)
                    final_displays.append(final_display)
                    if progress is not None:
                        progress(progress_event_cls(
                            stage="display",
                            message="Updating the map display...",
                            extra={"map_payload": final_display},
                        ))
                compact_tool_result = compact_tool_result_for_prompt_func(block.name, tool_result)
                assistant_content.append(block)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(compact_tool_result, default=str),
                    }
                )
            else:
                assistant_content.append(block)

        if display_warning:
            break

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})
        guardrail_message = build_guardrail_message_func(
            tool_iterations_used=tool_iterations_used,
            recent_tool_signatures=recent_tool_signatures,
        )
        if guardrail_message and guardrail_message != last_guardrail_message:
            messages.append({"role": "user", "content": guardrail_message})
            last_guardrail_message = guardrail_message

    return {
        "response": response,
        "messages": messages,
        "display_warning": display_warning,
        "final_display": final_display,
        "final_displays": final_displays,
        "tool_iterations_used": tool_iterations_used,
        "tool_trace": tool_trace,
    }


def run_research_final_synthesis(
    *,
    client,
    model: str,
    temperature: float,
    system_prompt_blocks: list[dict],
    messages: list[dict],
    max_tokens: int,
    temperature_kwargs_func,
    usage_recorder,
    progress,
    progress_event_cls,
    logger,
    session_id: str,
    query: str,
):
    """Run the last non-tool synthesis turn after a tool loop."""
    if progress is not None:
        progress(progress_event_cls(
            stage="writing",
            message="Finishing the analysis...",
            extra={"phase": "final_synthesis"},
        ))
    try:
        response = client.messages.create(
            model=model,
            system=system_prompt_blocks,
            messages=messages,
            max_tokens=max_tokens,
            **temperature_kwargs_func(model, temperature),
        )
        if usage_recorder is not None:
            usage_recorder.record(response)
        return response
    except Exception:
        logger.exception(
            "Research final synthesis call failed after max tool iterations session=%s query=%r",
            session_id,
            query[:120],
        )
        return None


def finalize_research_response(
    *,
    response,
    client,
    model: str,
    temperature: float,
    system_prompt_blocks: list[dict],
    messages: list[dict],
    session_id: str,
    query: str,
    manifest: dict,
    research_hints: dict,
    final_display: dict | None,
    final_displays: list[dict],
    tool_iterations_used: int,
    rescue_usage_recorder,
    progress,
    progress_event_cls,
    logger,
    extract_text_func,
    content_block_types_func,
    run_research_rescue_synthesis_func,
    fallback_display_message_func,
    broad_research_fallback_message_func,
    normalize_research_result_func,
):
    """Finish a Research response after the tool loop is complete."""
    if progress is not None:
        progress(progress_event_cls(
            stage="writing",
            message="Drafting the answer...",
            extra={"phase": "compose"},
        ))

    text = extract_text_func(response.content if response else [])
    if not text:
        logger.warning(
            "Research response missing text session=%s query=%r stop_reason=%s content_types=%s tool_iterations_used=%s artifact_count=%s",
            session_id,
            query[:120],
            getattr(response, "stop_reason", None) if response else None,
            content_block_types_func(response.content if response else []),
            tool_iterations_used,
            manifest.get("artifact_count"),
        )
        rescue_response = run_research_rescue_synthesis_func(
            client=client,
            model=model,
            temperature=temperature,
            system_prompt=system_prompt_blocks,
            messages=messages,
            session_id=session_id,
            query=query,
            usage_recorder=rescue_usage_recorder,
        )
        rescue_text = extract_text_func(rescue_response.content if rescue_response else [])
        if rescue_text:
            response = rescue_response
            text = rescue_text
        else:
            logger.warning(
                "Research rescue synthesis also missing text session=%s query=%r stop_reason=%s content_types=%s",
                session_id,
                query[:120],
                getattr(rescue_response, "stop_reason", None) if rescue_response else None,
                content_block_types_func(rescue_response.content if rescue_response else []),
            )
    if not text:
        text = fallback_display_message_func(final_display) or broad_research_fallback_message_func(query, manifest, research_hints)
    result = {
        "type": "chat",
        "message": text,
        "corpus": manifest,
        "research_hints": research_hints,
    }
    if final_display:
        for key, value in final_display.items():
            result[key] = value
    if final_displays:
        result["layers"] = final_displays
    if final_display:
        display_geojson = final_display.get("geojson") or {}
        display_features = display_geojson.get("features") or []
        logger.info(
            "Research final response session=%s query=%r message_len=%s data_type=%s source_id=%s features=%s years=%s layers=%s",
            session_id,
            query[:120],
            len(text or ""),
            final_display.get("data_type"),
            final_display.get("source_id"),
            len(display_features),
            len(final_display.get("years") or []),
            len(final_displays),
        )
    else:
        logger.info(
            "Research final response session=%s query=%r message_len=%s display_action=none",
            session_id,
            query[:120],
            len(text or ""),
        )
    return normalize_research_result_func(result, lane="research")
