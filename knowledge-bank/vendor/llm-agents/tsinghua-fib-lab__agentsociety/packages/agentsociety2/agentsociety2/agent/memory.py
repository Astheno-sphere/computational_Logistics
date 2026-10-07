"""File-backed core memory for PersonAgent.

中文：为 PersonAgent 提供基于工作区文件的核心记忆存储。
English: Provides workspace-file storage for PersonAgent core memory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator

MEMORY_MD_PATH = "MEMORY.md"
MEMORY_DIR = "memory"
EPISODES_PATH = f"{MEMORY_DIR}/episodes.jsonl"
MEMORY_STATE_PATH = f"{MEMORY_DIR}/state.json"
MEMORY_MD_SECTIONS = (
    "Identity And Profile",
    "Stable Preferences",
    "Relationships",
    "Durable Goals And Commitments",
    "Important Past Events",
    "Known Constraints",
)
MEMORY_STABLE_TYPES = {
    "identity",
    "preference",
    "relationship",
    "conflict",
    "resolution",
}

DEFAULT_MEMORY_MD = """# Memory

## Identity And Profile
- None recorded yet.

## Stable Preferences
- None recorded yet.

## Relationships
- None recorded yet.

## Durable Goals And Commitments
- None recorded yet.

## Important Past Events
- None recorded yet.

## Known Constraints
- None recorded yet.
"""


@dataclass(frozen=True)
class MemoryConsolidationConfig:
    """Configuration for deciding when to refresh MEMORY.md.

    Args:
        pending_threshold: Number of pending episodes that triggers consolidation.
        interval_steps: Step interval that triggers consolidation.
        high_importance_threshold: Importance score that triggers consolidation.
        max_memory_chars: Maximum desired size for MEMORY.md prompt context.
    """

    pending_threshold: int = 10
    interval_steps: int = 8
    high_importance_threshold: float = 0.75
    max_memory_chars: int = 4000


MemoryEpisodeType = Literal[
    "commitment",
    "relationship",
    "preference",
    "goal",
    "conflict",
    "resolution",
    "identity",
    "observation",
    "routine",
]


class ExtractedMemoryEpisode(BaseModel):
    """Validated LLM-produced memory point before persistence metadata is added.

    Args:
        type: Memory category used for consolidation decisions.
        importance: Importance score from 0.0 to 1.0.
        keywords: Grep-friendly keywords for later retrieval.
        text: One durable fact to remember.
        source: Source label for the memory.
        refs: Optional memory IDs referenced by this memory.
    """

    type: MemoryEpisodeType = "observation"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    keywords: list[str] = Field(default_factory=list, max_length=12)
    text: str = Field(min_length=1, max_length=1000)
    source: str = Field(default="step_result", max_length=80)
    refs: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("keywords", "refs", mode="before")
    @classmethod
    def _coerce_string_list(cls, value: Any) -> list[str]:
        """Normalize optional list-like fields to unique strings.

        Args:
            value: Raw field value from Pydantic validation.

        Returns:
            A list of stripped unique strings.
        """
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in result:
                result.append(text)
        return result

    @field_validator("text", "source")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        """Strip whitespace from required text fields.

        Args:
            value: Raw text value.

        Returns:
            The stripped text.
        """
        return value.strip()


class MemoryExtractionResult(BaseModel):
    """Function-call result for step memory extraction.

    Args:
        memories: Memory points extracted from one step.
    """

    memories: list[ExtractedMemoryEpisode] = Field(default_factory=list, max_length=8)


class MemoryConsolidationResult(BaseModel):
    """Function-call result for MEMORY.md consolidation.

    Args:
        memory_md: Full refreshed MEMORY.md content.
    """

    memory_md: str = Field(min_length=1, max_length=20000)

    @field_validator("memory_md")
    @classmethod
    def _strip_memory_md(cls, value: str) -> str:
        """Strip whitespace from MEMORY.md content.

        Args:
            value: Raw MEMORY.md content.

        Returns:
            The stripped MEMORY.md content.
        """
        return value.strip()


class AgentMemoryStore:
    """Workspace file store for core agent memory.

    ``episodes.jsonl`` is the canonical append-only event memory source.
    ``MEMORY.md`` is compact context derived from episodes.

    Args:
        workspace_root: Root directory of one agent workspace.
        agent_id: Numeric agent id used in persisted episode records.
    """

    trigger_types: ClassVar[set[str]] = {
        "commitment",
        "relationship",
        "preference",
        "goal",
        "conflict",
        "resolution",
        "identity",
    }

    def __init__(self, workspace_root: Path, *, agent_id: int) -> None:
        """Initialize the file-backed memory store.

        Args:
            workspace_root: Root directory of one agent workspace.
            agent_id: Numeric agent id used in memory records.

        Returns:
            None.
        """
        self.root = workspace_root
        self.agent_id = agent_id
        # Lazily-loaded in-memory mirror of episodes.jsonl. Avoids re-reading +
        # re-parsing the whole file on every iter_episodes()/search()/range()
        # call (was O(n) per call and blocked the event loop). Single-writer
        # (append_episodes) keeps it consistent; set to None to force a reload.
        self._episodes_cache: list[dict[str, Any]] | None = None

    @property
    def memory_md_path(self) -> Path:
        """Return the MEMORY.md path.

        Args:
            None.

        Returns:
            Absolute path to MEMORY.md.
        """
        return self.root / MEMORY_MD_PATH

    @property
    def episodes_path(self) -> Path:
        """Return the episodes JSONL path.

        Args:
            None.

        Returns:
            Absolute path to memory/episodes.jsonl.
        """
        return self.root / EPISODES_PATH

    @property
    def state_path(self) -> Path:
        """Return the memory state path.

        Args:
            None.

        Returns:
            Absolute path to memory/state.json.
        """
        return self.root / MEMORY_STATE_PATH

    def ensure(self) -> None:
        """Create memory files if they do not exist.

        Args:
            None.

        Returns:
            None.
        """
        (self.root / MEMORY_DIR).mkdir(parents=True, exist_ok=True)
        if not self.episodes_path.exists():
            self.episodes_path.write_text("", encoding="utf-8")
        if not self.memory_md_path.exists():
            self.memory_md_path.write_text(DEFAULT_MEMORY_MD, encoding="utf-8")
        if not self.state_path.exists():
            self.write_state(self.default_state())

    def default_state(self) -> dict[str, Any]:
        """Build the default memory state.

        Args:
            None.

        Returns:
            A new default memory state dictionary.
        """
        return {
            "schema_version": 1,
            "last_consolidated_tick": None,
            "last_consolidated_episode_id": None,
            "last_consolidated_step": 0,
            "pending_episode_count": 0,
            "episode_counter": 0,
        }

    def read_state(self) -> dict[str, Any]:
        """Read memory state from disk.

        Args:
            None.

        Returns:
            State dictionary merged with default keys.
        """
        self.ensure()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8") or "{}")
        except Exception:
            data = {}
        state = self.default_state()
        if isinstance(data, dict):
            state.update(data)
        return state

    def write_state(self, state: dict[str, Any]) -> None:
        """Write memory state to disk.

        Args:
            state: State dictionary to persist.

        Returns:
            None.
        """
        (self.root / MEMORY_DIR).mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def read_memory_md(self, *, max_chars: int | None = None) -> str:
        """Read compact long-term memory.

        Args:
            max_chars: Optional character budget. Long content is truncated.

        Returns:
            MEMORY.md text, possibly truncated.
        """
        self.ensure()
        text = self.memory_md_path.read_text(encoding="utf-8")
        if max_chars is not None and max_chars > 0 and len(text) > max_chars:
            return text[:max_chars] + "\n...<truncated>"
        return text

    def write_memory_md(
        self, content: str, *, step_count: int, tick: int | None
    ) -> None:
        """Write compact long-term memory and update consolidation state.

        Args:
            content: Full MEMORY.md content.
            step_count: Current agent step count.
            tick: Current simulation tick, if available.

        Returns:
            None.
        """
        self.ensure()
        text = self.normalize_memory_md(
            content,
            max_chars=MemoryConsolidationConfig().max_memory_chars,
        )
        self.memory_md_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        state = self.read_state()
        last = self.recent(limit=1)
        state.update(
            {
                "last_consolidated_tick": tick,
                "last_consolidated_episode_id": last[0]["id"] if last else None,
                "last_consolidated_step": step_count,
                "pending_episode_count": 0,
            }
        )
        self.write_state(state)

    def normalize_memory_md(
        self,
        content: str,
        *,
        max_chars: int = 4000,
    ) -> str:
        """Apply minimal structural guards to LLM-produced MEMORY.md content.

        The LLM is asked (via the consolidation prompt) to return well-formed
        Markdown directly; this only ensures a top-level heading and a length
        bound. It deliberately does NOT reflow or rewrite the text.

        Args:
            content: Raw MEMORY.md content produced by the LLM.
            max_chars: Maximum output character budget.

        Returns:
            MEMORY.md text with a top-level heading and bounded length.
        """
        text = str(content or "").strip()
        if not text:
            text = DEFAULT_MEMORY_MD.strip()
        if not text.lstrip().startswith("#"):
            text = "# Memory\n\n" + text
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars].rstrip()
        return text.rstrip() + "\n"

    def append_episodes(
        self,
        episodes: list[dict[str, Any]],
        *,
        tick: int,
        t: datetime,
        step_count: int,
    ) -> list[dict[str, Any]]:
        """Append normalized memory episodes and return written records.

        Args:
            episodes: Raw episode dictionaries from the memory extractor.
            tick: Current simulation tick.
            t: Current simulation time.
            step_count: Current agent step count.

        Returns:
            Episode records written to memory/episodes.jsonl.
        """
        self.ensure()
        state = self.read_state()
        counter = int(state.get("episode_counter") or 0)
        written: list[dict[str, Any]] = []
        for raw in episodes:
            text = " ".join(str(raw.get("text") or "").strip().split())
            if not text:
                continue
            counter += 1
            keywords_raw = raw.get("keywords")
            keywords = (
                [str(item).strip() for item in keywords_raw if str(item).strip()]
                if isinstance(keywords_raw, list)
                else []
            )
            refs_raw = raw.get("refs")
            refs = (
                [str(item).strip() for item in refs_raw if str(item).strip()]
                if isinstance(refs_raw, list)
                else []
            )
            try:
                importance = float(raw.get("importance", 0.5))
            except Exception:
                importance = 0.5
            importance = max(0.0, min(1.0, importance))
            record = {
                "id": f"m_{tick:08d}_{counter:06d}",
                "agent_id": self.agent_id,
                "tick": tick,
                "tick_duration_sec": tick,
                "step_index": step_count,
                "time": t.isoformat(),
                "step_count": step_count,
                "type": str(raw.get("type") or "observation").strip() or "observation",
                "importance": importance,
                "keywords": keywords,
                "text": text,
                "source": str(raw.get("source") or "step_result").strip()
                or "step_result",
                "refs": refs,
            }
            written.append(record)
        if not written:
            return []

        with self.episodes_path.open("a", encoding="utf-8") as f:
            for record in written:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        # Keep the in-memory cache in sync. If the cache was never loaded, leave
        # it None — a later iter_episodes() will lazy-load from disk (which now
        # includes these records). Single-writer per store → no race.
        if self._episodes_cache is not None:
            self._episodes_cache.extend(written)
        state["episode_counter"] = counter
        state["pending_episode_count"] = int(
            state.get("pending_episode_count") or 0
        ) + len(written)
        self.write_state(state)
        return written

    def iter_episodes(self) -> list[dict[str, Any]]:
        """Read all valid memory episodes.

        Uses the in-memory cache (loaded once on first access, kept in sync by
        append_episodes) so repeated calls no longer re-read/re-parse the whole
        episodes.jsonl. Returns a shallow copy so callers cannot mutate the
        cache.

        Args:
            None.

        Returns:
            Parsed episode dictionaries in file order.
        """
        return list(self._load_episodes_cache())

    def _load_episodes_cache(self) -> list[dict[str, Any]]:
        """Lazily load and cache all episodes from disk.

        Args:
            None.

        Returns:
            The in-memory episode list (the cache itself).
        """
        if self._episodes_cache is None:
            self.ensure()
            records: list[dict[str, Any]] = []
            for line in self.episodes_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    records.append(item)
            self._episodes_cache = records
        return self._episodes_cache

    def recent(self, *, limit: int = 8) -> list[dict[str, Any]]:
        """Read the latest memory episodes.

        Args:
            limit: Maximum number of episodes to return.

        Returns:
            Latest episode dictionaries in chronological order.
        """
        limit = max(1, int(limit or 8))
        return self.iter_episodes()[-limit:]

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search memory episodes by substring.

        Args:
            query: Case-insensitive substring to search in serialized episodes.
            limit: Maximum number of matches to return.

        Returns:
            Matching episode dictionaries, newest first.
        """
        q = str(query or "").strip().lower()
        if not q:
            return []
        limit = max(1, int(limit or 20))
        matches: list[dict[str, Any]] = []
        for item in reversed(self.iter_episodes()):
            haystack = json.dumps(item, ensure_ascii=False).lower()
            if q in haystack:
                matches.append(item)
            if len(matches) >= limit:
                break
        return matches

    def read_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Read exact memory episodes by id.

        Args:
            ids: Memory episode IDs to read.

        Returns:
            Episode dictionaries whose IDs match the input list.
        """
        wanted = {str(item).strip() for item in ids if str(item).strip()}
        if not wanted:
            return []
        return [item for item in self.iter_episodes() if str(item.get("id")) in wanted]

    def range(
        self,
        *,
        start_step: int | None = None,
        end_step: int | None = None,
        start_tick: int | None = None,
        end_tick: int | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Read memory episodes in a step, tick-duration, or time range.

        Args:
            start_step: Inclusive lower step-index bound.
            end_step: Inclusive upper step-index bound.
            start_tick: Inclusive lower tick bound.
            end_tick: Inclusive upper tick bound.
            start_time: Inclusive ISO datetime lower bound.
            end_time: Inclusive ISO datetime upper bound.
            limit: Maximum number of episodes to return.

        Returns:
            Matching episode dictionaries in chronological order.
        """
        start_dt = self._parse_dt(start_time)
        end_dt = self._parse_dt(end_time)
        result: list[dict[str, Any]] = []
        for item in self.iter_episodes():
            step_index = self._episode_step_index(item)
            if start_step is not None and (
                step_index is None or step_index < start_step
            ):
                continue
            if end_step is not None and (step_index is None or step_index > end_step):
                continue
            tick = self._episode_tick_duration(item)
            if start_tick is not None and (tick is None or tick < start_tick):
                continue
            if end_tick is not None and (tick is None or tick > end_tick):
                continue
            item_dt = self._parse_dt(str(item.get("time") or ""))
            if start_dt is not None and (item_dt is None or item_dt < start_dt):
                continue
            if end_dt is not None and (item_dt is None or item_dt > end_dt):
                continue
            result.append(item)
            if len(result) >= max(1, int(limit or 50)):
                break
        return result

    @staticmethod
    def _episode_step_index(item: dict[str, Any]) -> int | None:
        """Return the event step index from a memory episode.

        Args:
            item: Memory episode dictionary.

        Returns:
            Step index when present and parseable, otherwise None.
        """
        for key in ("step_index", "step_count"):
            raw = item.get(key)
            if isinstance(raw, int) or str(raw).isdigit():
                return int(raw)
        return None

    @staticmethod
    def _episode_tick_duration(item: dict[str, Any]) -> int | None:
        """Return the per-step tick duration from a memory episode.

        Args:
            item: Memory episode dictionary.

        Returns:
            Tick duration in seconds when present and parseable, otherwise None.
        """
        for key in ("tick_duration_sec", "tick"):
            raw = item.get(key)
            if isinstance(raw, int) or str(raw).isdigit():
                return int(raw)
        return None

    def should_consolidate(
        self,
        new_episodes: list[dict[str, Any]],
        *,
        step_count: int,
        config: MemoryConsolidationConfig,
    ) -> tuple[bool, str]:
        """Decide whether MEMORY.md should be refreshed.

        Args:
            new_episodes: Newly appended episode records.
            step_count: Current agent step count.
            config: Consolidation trigger configuration.

        Returns:
            A pair of ``(should_consolidate, reason)``.
        """
        self.ensure()
        if not self.memory_md_path.exists():
            return True, "MEMORY.md missing"
        memory_text = self.memory_md_path.read_text(encoding="utf-8")
        if len(memory_text) > config.max_memory_chars:
            return True, "MEMORY.md exceeds context budget"
        for item in new_episodes:
            item_type = str(item.get("type") or "").strip().lower()
            is_candidate = self.is_long_term_memory_candidate(item)
            if (
                is_candidate
                and self._episode_importance(item) >= config.high_importance_threshold
            ):
                return True, "high-importance episode"
            if (
                is_candidate
                and item_type in self.trigger_types
                and item_type != "identity"
            ):
                return True, "trigger episode type"
        state = self.read_state()
        if int(state.get("pending_episode_count") or 0) >= config.pending_threshold:
            if any(
                self.is_long_term_memory_candidate(item)
                for item in self.unconsolidated()
            ):
                return True, "pending episode threshold"
        last_step = int(state.get("last_consolidated_step") or 0)
        if step_count - last_step >= config.interval_steps and any(
            self.is_long_term_memory_candidate(item) for item in self.unconsolidated()
        ):
            return True, "consolidation interval"
        return False, ""

    @staticmethod
    def _episode_importance(episode: dict[str, Any]) -> float:
        """Return a bounded importance score from an episode.

        Args:
            episode: Persisted or candidate memory episode.

        Returns:
            Importance score between 0.0 and 1.0.
        """
        try:
            importance = float(episode.get("importance") or 0.0)
        except Exception:
            importance = 0.0
        return max(0.0, min(1.0, importance))

    @classmethod
    def is_long_term_memory_candidate(cls, episode: dict[str, Any]) -> bool:
        """Return whether an episode should be offered for MEMORY.md consolidation.

        Args:
            episode: Persisted or candidate memory episode.

        Returns:
            True when LLM-provided structure marks the episode as durable enough
            to include in the consolidation prompt.
        """
        episode_type = str(episode.get("type") or "").strip().lower()
        importance = cls._episode_importance(episode)
        if episode_type in MEMORY_STABLE_TYPES:
            return True
        if episode_type in {"commitment", "goal"}:
            return importance >= 0.6
        if episode_type == "observation":
            return importance >= 0.85
        return False

    def unconsolidated(self) -> list[dict[str, Any]]:
        """Read episodes written after the last consolidation cursor.

        Args:
            None.

        Returns:
            Episode dictionaries that have not been consolidated into MEMORY.md.
        """
        state = self.read_state()
        last_id = state.get("last_consolidated_episode_id")
        records = self.iter_episodes()
        if not last_id:
            return records
        for idx, item in enumerate(records):
            if item.get("id") == last_id:
                return records[idx + 1 :]
        return records

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        """Parse an ISO datetime if possible.

        Args:
            value: Optional datetime string.

        Returns:
            Parsed datetime, or None when parsing fails.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
