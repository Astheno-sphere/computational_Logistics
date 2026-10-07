"""Lane-owned Research orchestrator runtime helpers."""

from __future__ import annotations

import asyncio
from mapmover.runtime.orchestrator_result_cap import (
    cap_runtime_result_field,
    cap_runtime_result_list_field,
)


def apply_research_runtime_result_cap(
    result: dict,
    *,
    load_source_metadata_func=None,
) -> dict:
    if not isinstance(result, dict) or load_source_metadata_func is None:
        return result
    next_result, cap_info = cap_runtime_result_field(
        result,
        field_name="display",
        source_id=str(((result.get("display") or {}).get("source_id") or result.get("source_id") or "")).strip(),
        load_source_metadata_func=load_source_metadata_func,
    )
    if cap_info:
        next_result["cap_info"] = cap_info
        next_result["truncated"] = True

    next_result, cap_infos = cap_runtime_result_list_field(
        next_result,
        field_name="displays",
        source_id_func=lambda display_item, outer_result: display_item.get("source_id") or outer_result.get("source_id"),
        load_source_metadata_func=load_source_metadata_func,
    )
    if cap_infos and "cap_info" not in next_result:
        next_result["cap_info"] = cap_infos[-1]
        next_result["truncated"] = True
    return next_result


def run_research_orchestrator_sync(
    *,
    run_research_chat_func,
    load_source_metadata_func,
    **kwargs,
) -> dict:
    result = run_research_chat_func(**kwargs)
    return apply_research_runtime_result_cap(
        result,
        load_source_metadata_func=load_source_metadata_func,
    )


def wrap_research_capped_result_task(
    *,
    load_source_metadata_func,
    raw_task: asyncio.Task,
) -> asyncio.Task:
    async def capped_result_task():
        result = await raw_task
        return apply_research_runtime_result_cap(
            result,
            load_source_metadata_func=load_source_metadata_func,
        )

    return asyncio.create_task(capped_result_task())
