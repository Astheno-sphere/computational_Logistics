"""Serializable replay proxy + per-process sink builder.

Replay writes used to funnel through a single Ray actor wrapping SQLite. That
central write path is gone.

:class:`ReplayProxy` is now a serializable config dataclass carrying only the
output directory (+ an enable flag). Each consumer — the env router actor, the
society, each agent Ray task — builds its own process-local
:class:`~agentsociety2.storage.replay_sink.ReplaySink` from ``replay_dir`` and
appends directly. No central actor, no Ray round-trip on the write path, no
deadlock. ``enabled=False`` short-circuits to a no-op (the escape hatch for
extreme scale, where replay can be skipped entirely).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentsociety2.storage.replay_sink import ReplaySink, build_replay_sink


@dataclass
class ReplayProxy:
    """Serializable config for distributed replay writing.

    Carries only the replay output directory and an enable flag — no Ray actor
    handle. Methods lazily build+cache a process-local
    :class:`ReplaySink` (from ``replay_dir``) on first use and delegate, so each
    agent Ray task / env actor that receives a deserialized copy gets its own
    sink and its own file descriptors. ``enabled=False`` makes every method a
    no-op.
    """

    replay_dir: str | None = None
    enabled: bool = True

    # Process-local sink, built lazily on first write. NOT serialized across
    # Ray task boundaries — ReplaySink holds open fds + a threading.Lock (both
    # unpicklable) and is per-process. Each Ray task that receives a
    # deserialized copy rebuilds its own sink from replay_dir.
    _sink: Any = None

    def _get_sink(self) -> ReplaySink | None:
        sink = self._sink
        if sink is None:
            sink = build_replay_sink(self)
            self._sink = sink
        return sink

    # --- pickle/cloudpickle: drop the process-local sink so the proxy can
    # cross Ray task boundaries. Each side rebuilds its own sink. ---
    def __getstate__(self) -> dict[str, Any]:
        return {"replay_dir": self.replay_dir, "enabled": self.enabled}

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.replay_dir = state.get("replay_dir")
        self.enabled = state.get("enabled", True)
        self._sink = None

    async def write(self, table: str, data: dict[str, Any]) -> None:
        if not self.enabled:
            return
        sink = self._get_sink()
        if sink is None:
            return
        await sink.write(table, data)

    async def write_batch(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not self.enabled:
            return
        sink = self._get_sink()
        if sink is None:
            return
        await sink.write_batch(table, rows)

    async def register_table(self, schema: Any) -> None:
        if not self.enabled:
            return
        sink = self._get_sink()
        if sink is None:
            return
        await sink.register_table(schema)

    async def register_dataset(self, spec: Any, columns: Any) -> None:
        if not self.enabled:
            return
        sink = self._get_sink()
        if sink is None:
            return
        await sink.register_dataset(spec, columns)

    async def close(self) -> None:
        sink = self._sink
        if sink is not None:
            await sink.close()
            self._sink = None


__all__ = ["ReplayProxy", "build_replay_sink"]
