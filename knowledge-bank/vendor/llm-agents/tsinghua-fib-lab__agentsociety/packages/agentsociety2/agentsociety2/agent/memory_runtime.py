"""Core memory runtime for PersonAgent.

中文：封装 PersonAgent 的记忆上下文、检索工具、抽取和合并流程。
English: Encapsulates memory context, retrieval tools, extraction, and consolidation.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from agentsociety2.agent.memory import (
    AgentMemoryStore,
    MemoryConsolidationConfig,
    MemoryExtractionResult,
)
from agentsociety2.agent.person_prompt import xml_block

MEMORY_CONSOLIDATION_SYSTEM_PROMPT = """
Rewrite MEMORY.md for a simulated person.

You MUST output the complete refreshed MEMORY.md as Markdown directly in your
response message. Do NOT call any tool. Do NOT wrap the output in JSON, code
fences, or quotes. Do NOT escape or remove newlines. Write real Markdown with
real line breaks — your response is written to MEMORY.md verbatim.

Formatting rules (critical):
- Start with a single H1 line: `# Memory`.
- Every section heading MUST be on its own line as `## <Section Name>`.
- Every bullet MUST be on its own line and start with `- `.
- Put one blank line between the H1 and the first section, and between sections.
- Use plain `- text` bullets; no nested sub-bullets.
- Keep the document compact, stable, and useful as long-term background.

Use exactly these section headings, in this order:
## Identity And Profile
## Stable Preferences
## Relationships
## Durable Goals And Commitments
## Important Past Events
## Known Constraints

Verbatim example of the required structure and line breaks — imitate it exactly:

# Memory

## Identity And Profile
- 28-year-old female, marketing analyst, Bachelor's degree.
- Home AOI 500038964; work AOI 500021584.

## Stable Preferences
- Sleeps 23:00-07:00.

## Relationships
- None recorded.

## Durable Goals And Commitments
- None recorded.

## Important Past Events
- None recorded.

## Known Constraints
- None recorded.

Section guidance:
- Identity And Profile includes age, education, occupation, home AOI, work AOI,
  workplace, and other profile facts.
- Relationships is only for named people or social ties, never home/work
  locations.
- Stable Preferences is only for durable preferences or routines, not one-day
  sleep or meal segments.

Do not promote into long-term memory:
- Current-step actions.
- One-day schedules.
- Timestamps.
- Routine simulation events.
""".strip()


@dataclass(frozen=True)
class MemoryRuntimeConfig:
    """Runtime config for core file-backed memory.

    Args:
        enabled: Whether core memory is enabled.
        context_max_chars: Character budget for MEMORY.md prompt context.
        recent_limit: Number of recent episodes to include in prompt context.
        consolidation: Programmatic consolidation trigger config.
    """

    enabled: bool = True
    context_max_chars: int = 4000
    recent_limit: int = 8
    consolidation: MemoryConsolidationConfig = field(
        default_factory=MemoryConsolidationConfig
    )


class PersonMemoryRuntime:
    """Owns memory context, retrieval tools, extraction, and consolidation.

    Args:
        agent_id: Numeric agent id.
        agent_name: Display name of the simulated person.
        config: Memory runtime configuration.
        get_model_name: Callback returning the active LLM model name.
        dispatch_llm: Callback used to call the LLM dispatcher.
        get_profile: Callback returning the current agent profile.
        logger: Logger-like object used for warnings.
    """

    def __init__(
        self,
        *,
        agent_id: int,
        agent_name: str,
        config: MemoryRuntimeConfig,
        get_model_name: Callable[[], str | None],
        dispatch_llm: Callable[..., Awaitable[Any]],
        get_profile: Callable[[], Any],
        logger: Any,
        trace_span: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize the memory runtime.

        Args:
            agent_id: Numeric agent id.
            agent_name: Display name of the simulated person.
            config: Memory runtime configuration.
            get_model_name: Callback returning the active LLM model name.
            dispatch_llm: Callback used to call the LLM dispatcher.
            get_profile: Callback returning the current agent profile.
            logger: Logger-like object used for warnings.
            trace_span: Optional context-manager factory for OTel spans, used to
                trace memory LLM calls and file-I/O phases (which otherwise have
                no span and appear as unexplained gaps in agent.step).

        Returns:
            None.
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.config = config
        self._get_model_name = get_model_name
        self._dispatch_llm = dispatch_llm
        self._get_profile = get_profile
        self._logger = logger
        self._trace_span_cb = trace_span
        self._store: AgentMemoryStore | None = None

    def _span(self, name: str, **attributes: Any) -> Any:
        """Return a span context manager (or a no-op when tracing is absent).

        Args:
            name: Span name.
            attributes: Start attributes.

        Returns:
            Context manager.
        """
        if self._trace_span_cb is None:
            return nullcontext()
        return self._trace_span_cb(name, attributes=dict(attributes) or None)

    @property
    def enabled(self) -> bool:
        """Return whether memory is enabled.

        Args:
            None.

        Returns:
            True when core memory should run.
        """
        return self.config.enabled

    def ensure_store(self, workspace_root: Path) -> AgentMemoryStore | None:
        """Return initialized core memory store when enabled.

        Args:
            workspace_root: Root directory of one agent workspace.

        Returns:
            Memory store when enabled, otherwise None.
        """
        if not self.enabled:
            return None
        if self._store is None:
            self._store = AgentMemoryStore(workspace_root, agent_id=self.agent_id)
        self._store.ensure()
        return self._store

    @property
    def store(self) -> AgentMemoryStore | None:
        """Return the current memory store.

        Args:
            None.

        Returns:
            Memory store when enabled and initialized, otherwise None.
        """
        return self._store if self.enabled else None

    def build_context(self) -> dict[str, Any]:
        """Build compact prompt context from MEMORY.md and recent episodes.

        Args:
            None.

        Returns:
            Prompt-ready memory context dictionary.
        """
        store = self.store
        if store is None:
            return {}
        return {
            "memory_md": store.read_memory_md(max_chars=self.config.context_max_chars),
            "recent_episodes": store.recent(limit=self.config.recent_limit)
            if self.config.recent_limit > 0
            else [],
            "files": {
                "summary": "MEMORY.md",
                "episodes": "memory/episodes.jsonl",
            },
        }

    def dispatch_tool(
        self, action: str, args: dict[str, Any]
    ) -> tuple[bool, str, dict[str, Any]]:
        """Dispatch built-in read-only memory retrieval tools.

        Args:
            action: Memory tool name.
            args: Tool arguments from the model.

        Returns:
            Tuple of ``(ok, observation, data)``.
        """
        store = self.store
        if store is None:
            return (
                False,
                "memory feature is disabled",
                {"error": "memory feature is disabled"},
            )
        if action == "memory_recent":
            data = {"episodes": store.recent(limit=int(args.get("limit") or 8))}
            return (
                True,
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                data,
            )
        if action == "memory_search":
            data = {
                "episodes": store.search(
                    str(args.get("query") or ""),
                    limit=int(args.get("limit") or 20),
                )
            }
            return (
                True,
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                data,
            )
        if action == "memory_range":
            start_step = args.get("start_step")
            end_step = args.get("end_step")
            start_tick = args.get("start_tick")
            end_tick = args.get("end_tick")
            data = {
                "episodes": store.range(
                    start_step=int(start_step) if start_step is not None else None,
                    end_step=int(end_step) if end_step is not None else None,
                    start_tick=int(start_tick) if start_tick is not None else None,
                    end_tick=int(end_tick) if end_tick is not None else None,
                    start_time=str(args.get("start_time") or "") or None,
                    end_time=str(args.get("end_time") or "") or None,
                    limit=int(args.get("limit") or 50),
                )
            }
            return (
                True,
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                data,
            )
        if action == "memory_read":
            ids = args.get("ids")
            id_list = [str(item) for item in ids] if isinstance(ids, list) else []
            data = {"episodes": store.read_ids(id_list)}
            return (
                True,
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                data,
            )
        return False, f"unknown action: {action}", {"action": action}

    async def after_step(
        self,
        *,
        tick: int,
        t: datetime,
        step_count: int,
        finish_memories: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Ingest step memories and refresh MEMORY.md when triggers fire.

        Memory generation lives entirely in the step-mode ``finish`` tool —
        there is no dedicated extraction LLM call (no fallback). ``finish_memories``
        carries the episodes the model recorded inline; when it is absent or
        empty (e.g. the loop hit the turn limit without a finish, or the model
        reported nothing notable) nothing is recorded this step.

        Args:
            tick: Current simulation tick.
            t: Current simulation time.
            step_count: Current agent step count.
            finish_memories: Memories recorded inline by the step-mode finish
                tool. ``None`` / empty means record nothing this step.

        Returns:
            Episode records written during this step.
        """
        store = self.store
        if store is None or not finish_memories:
            return []
        try:
            with self._span("memory.extract", operation_type="memory"):
                memories = self._validate_finish_memories(finish_memories)
        except Exception as exc:
            # Don't drop the whole step when the model supplied malformed
            # episodes: fall back to per-item validation, coercing any invalid
            # item into a minimal valid episode so the durable info the model
            # did provide still survives. Only truly empty input yields nothing.
            self._logger.warning(
                "Agent %s: finish-memory validation failed (%s); coercing "
                "individual items as fallback",
                self.agent_id,
                exc,
            )
            memories = self._validate_finish_memories_lenient(finish_memories)
            if not memories:
                return []
        with self._span("memory.append_episodes", operation_type="memory"):
            written = await asyncio.to_thread(
                store.append_episodes,
                memories,
                tick=tick,
                t=t,
                step_count=step_count,
            )
        if not written:
            return []
        with self._span("memory.should_consolidate", operation_type="memory"):
            should, reason = await asyncio.to_thread(
                store.should_consolidate,
                written,
                step_count=step_count,
                config=self.config.consolidation,
            )
        if should:
            try:
                with self._span("memory.consolidate", operation_type="memory"):
                    await self._consolidate_memory_md(
                        tick=tick,
                        t=t,
                        step_count=step_count,
                        reason=reason,
                    )
            except Exception as exc:
                self._logger.warning(
                    "Agent %s: memory consolidation failed: %s", self.agent_id, exc
                )
        return written

    def _validate_finish_memories(self, raw: Any) -> list[dict[str, Any]]:
        """Validate memories supplied inline by the step-mode ``finish`` tool.

        Same episode shape as the ``record_step_memories`` tool; validated
        through :class:`MemoryExtractionResult` so malformed input raises (the
        caller then falls back to a dedicated extraction call). No LLM call.

        Args:
            raw: The ``memories`` list from the finish tool arguments.

        Returns:
            Validated episode dicts ready for ``store.append_episodes``.
        """
        if not isinstance(raw, list):
            raise ValueError("finish `memories` must be a list")
        parsed = MemoryExtractionResult.model_validate({"memories": raw})
        return [item.model_dump() for item in parsed.memories]

    def _validate_finish_memories_lenient(self, raw: Any) -> list[dict[str, Any]]:
        """Best-effort fallback validation for finish memories.

        Used when strict :meth:`_validate_finish_memories` raises (one bad
        item poisoned the whole list). Validates each item independently:
        valid episodes are kept as-is; invalid items are coerced into a
        minimal valid ``observation`` episode built from whatever text the
        model provided, tagged ``source=finish_memory_coerced`` so the
        downgrade is traceable. Items with no usable text are dropped.

        Args:
            raw: The ``memories`` list from the finish tool arguments.

        Returns:
            Validated/coerced episode dicts ready for ``store.append_episodes``
            (possibly empty).
        """
        if not isinstance(raw, list):
            return []
        from agentsociety2.agent.memory import ExtractedMemoryEpisode

        coerced: list[dict[str, Any]] = []
        for item in raw:
            try:
                episode = ExtractedMemoryEpisode.model_validate(item)
                coerced.append(episode.model_dump())
                continue
            except Exception:
                self._logger.debug(
                    "Skipping malformed memory episode during validation", exc_info=True
                )
            # Coerce: salvage any text-like field from the raw item.
            text = ""
            if isinstance(item, Mapping):
                for key in ("text", "content", "summary", "description"):
                    candidate = str(item.get(key) or "").strip()
                    if candidate:
                        text = candidate
                        break
            elif isinstance(item, str):
                text = item.strip()
            if not text:
                continue
            try:
                episode = ExtractedMemoryEpisode.model_validate(
                    {
                        "type": "observation",
                        "importance": 0.4,
                        "text": text[:1000],
                        "source": "finish_memory_coerced",
                    }
                )
                coerced.append(episode.model_dump())
            except Exception:
                continue
        return coerced

    async def _consolidate_memory_md(
        self,
        *,
        tick: int,
        t: datetime,
        step_count: int,
        reason: str,
    ) -> None:
        """Refresh MEMORY.md from current compact memory and recent episodes.

        Args:
            tick: Current simulation tick.
            t: Current simulation time.
            step_count: Current agent step count.
            reason: Programmatic trigger reason.

        Returns:
            None.
        """
        model_name = self._require_model_name()
        store = self._require_store()

        def _gather_consolidation_input() -> tuple[
            list[dict[str, Any]], list[dict[str, Any]], str
        ]:
            # All sync store I/O (now mostly cache-backed for unconsolidated/
            # search; read_memory_md is one small file read). Coalesced into a
            # single thread offload so none of it blocks the event loop.
            new_eps = [
                item
                for item in store.unconsolidated()
                if store.is_long_term_memory_candidate(item)
            ]
            if not new_eps:
                return [], [], ""
            keywords = {
                str(keyword)
                for episode in new_eps
                for keyword in episode.get("keywords", [])
                if str(keyword).strip()
            }
            related: list[dict[str, Any]] = []
            for keyword in sorted(keywords)[:12]:
                related.extend(store.search(keyword, limit=3))
            related_by_id = {str(item.get("id")): item for item in related}
            current_md = store.read_memory_md(max_chars=self.config.context_max_chars)
            return new_eps, list(related_by_id.values())[:30], current_md

        new_episodes, related_list, current_md = await asyncio.to_thread(
            _gather_consolidation_input
        )
        if not new_episodes:
            return
        payload = {
            "reason": reason,
            "tick": tick,
            "time": t.isoformat(),
            "current_memory_md": current_md,
            "new_episodes": new_episodes[-30:],
            "related_old_episodes": related_list,
            "max_chars": self.config.context_max_chars,
        }
        messages = [
            {
                "role": "system",
                "content": MEMORY_CONSOLIDATION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": xml_block(
                    "memory_consolidation_input",
                    json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                ),
            },
        ]
        with self._span(
            "llm.completion",
            operation_type="llm",
            llm_purpose="memory_consolidate",
            llm_model=model_name,
        ):
            response = await self._dispatch_llm(
                model=model_name,
                messages=messages,
                stream=False,
                # 单次摘要重写，推理无收益且拖慢每步收尾。
                thinking="off",
            )
        # 直接取 LLM 返回的 Markdown 文本作为新 MEMORY.md，不走 tool calling。
        content = ""
        if getattr(response, "choices", None):
            message = getattr(response.choices[0], "message", None)
            content = str(getattr(message, "content", "") or "")
        content = content.strip()
        if not content:
            # No usable output: keep the existing MEMORY.md. Warn (don't raise)
            # so this is visible — because the consolidation cursor is only
            # advanced on a successful write, a model that consistently returns
            # empty would re-trigger consolidation every step and burn LLM
            # calls. The caller already bounds this via interval_steps.
            self._logger.warning(
                "Agent %s: memory consolidation returned empty content; "
                "MEMORY.md left unchanged (consolidation may re-trigger).",
                self.agent_id,
            )
            return
        await asyncio.to_thread(
            store.write_memory_md, content, step_count=step_count, tick=tick
        )

    def _parse_tool_call_response(
        self, response: Any, expected_name: str
    ) -> dict[str, Any]:
        """Parse one required tool call argument object from an LLM response.

        Args:
            response: Raw LLM response object.
            expected_name: Required tool call function name.

        Returns:
            Parsed tool argument dictionary.
        """
        if not getattr(response, "choices", None):
            return {}
        message = getattr(response.choices[0], "message", None)
        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            name = str(getattr(function, "name", "") or "").strip()
            if name != expected_name:
                continue
            raw_args = str(getattr(function, "arguments", "") or "{}")
            try:
                from agentsociety2.agent.json_utils import jr_parse_from_llm

                parsed = jr_parse_from_llm(raw_args)
            except Exception:
                parsed = json.loads(raw_args)
            return dict(parsed) if isinstance(parsed, Mapping) else {}
        content = str(getattr(message, "content", "") or "").strip()
        if not content:
            return {}
        try:
            from agentsociety2.agent.json_utils import jr_parse_from_llm

            parsed = jr_parse_from_llm(content)
        except Exception:
            try:
                parsed = json.loads(content)
            except Exception:
                return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}

    def _require_model_name(self) -> str:
        """Return the configured model name.

        Args:
            None.

        Returns:
            Active model name.
        """
        model_name = self._get_model_name()
        assert model_name is not None, "LLM is not initialized"
        return model_name

    def _require_store(self) -> AgentMemoryStore:
        """Return the initialized memory store.

        Args:
            None.

        Returns:
            Active memory store.
        """
        store = self.store
        if store is None:
            raise RuntimeError("Memory store is not initialized")
        return store
