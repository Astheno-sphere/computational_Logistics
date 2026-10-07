"""Shared runtime helpers for Research retry, guardrail, and rescue flow."""

from __future__ import annotations


def build_research_tool_guardrail_message(
    *,
    retry_policy,
    tool_iterations_used: int,
    recent_tool_signatures: list[str],
) -> str | None:
    if tool_iterations_used < retry_policy.guardrail_start_iteration:
        return None

    repeated_signature = (
        len(recent_tool_signatures) >= 2
        and recent_tool_signatures[-1] == recent_tool_signatures[-2]
    )
    repeated_recently = (
        len(recent_tool_signatures) >= 3
        and len(set(recent_tool_signatures[-3:])) == 1
    )

    if tool_iterations_used >= retry_policy.strong_guardrail_iteration or repeated_recently:
        message = (
            "Tool budget reminder: you have already used several tool rounds. "
            "Do not keep retrying the same artifact with slightly different filters. "
            "Either write the best grounded answer from the evidence you already have, "
            "or ask one short clarifying question if a key ambiguity is blocking the answer. "
            "If the answer depends on an exact loc_id-based subset join between already loaded artifacts, "
            "do that exact join instead of switching to an approximate top-N synthesis. "
            "Prefer a partial grounded answer over more exploratory retries."
        )
    else:
        message = (
            "Tool budget reminder: if you cannot isolate the answer after a few tool rounds, "
            "stop and either answer from the evidence already gathered or ask one short clarifying question. "
            "If one exact loc_id-based join across loaded artifacts would settle the question, do that instead. "
            "Do not assume a filter failed just because the preview is capped."
        )

    if repeated_signature:
        message += " You appear to be repeating a very similar tool pattern; switch to synthesis or clarification now."
    return message


def run_research_rescue_synthesis(
    *,
    client,
    model: str,
    temperature: float,
    system_prompt,
    messages: list[dict],
    session_id: str,
    query: str,
    retry_policy,
    temperature_kwargs_func,
    ensure_recorder_func,
    usage_recorder=None,
    logger,
    max_tokens: int,
):
    rescue_messages = list(messages)
    rescue_messages.append(
        {
            "role": "user",
            "content": retry_policy.rescue_prompt,
        }
    )
    usage_recorder, owns_rescue = ensure_recorder_func(
        usage_recorder,
        surface="research",
        call_kind="research_rescue",
        session_id=session_id,
    )
    try:
        try:
            response = client.messages.create(
                model=model,
                system=system_prompt,
                messages=rescue_messages,
                max_tokens=max_tokens,
                **temperature_kwargs_func(model, temperature),
            )
            if usage_recorder is not None:
                usage_recorder.record(response)
            return response
        except Exception:
            logger.exception(
                "Research rescue synthesis call failed session=%s query=%r",
                session_id,
                query[:120],
            )
            return None
    finally:
        if owns_rescue:
            usage_recorder.flush(skip_if_empty=True)
