"""Reusable progress event bus across the sync/async boundary.

Long-running synchronous work (LLM tool-use loops, multi-step
orchestrations, etc.) often runs on a worker thread via
`asyncio.to_thread` so the event loop is not blocked. The async caller
still wants to surface real-time progress to the client without polling
or guessing what the worker is doing.

`ProgressBus` solves that with a thread-safe `asyncio.Queue`:

- the async streaming endpoint creates a `ProgressBus` and obtains a
  `thread_emitter()` callable
- the worker function accepts that callable and invokes it from any
  thread whenever a progress milestone is reached
- the streaming endpoint awaits `drain_until(worker_task)` and yields
  events as they arrive, with an optional heartbeat fallback so the
  client never sees long silent gaps

This is the canonical shape we want for explorer chat, research chat,
and future ops mode flows so users get consistent real-time progress.

Reference docs:

- `RAILWAY_PREWARM.md` covers the runtime/prewarm layers
- `cloud_management.md` covers the perf posture overall
- streaming endpoints in `routes/chat.py` and `routes/research.py` are
  the canonical consumers
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional


@dataclass
class ProgressEvent:
    """One progress milestone emitted by a worker.

    `stage` is the SSE stage label the client sees (e.g. "thinking",
    "tool", "preparing"). `message` is the user-facing string. `extra`
    is opaque context for clients that want to render richer state
    (tool name, iteration number, etc).
    """

    stage: str
    message: str
    extra: dict = field(default_factory=dict)


class ProgressBus:
    """Thread-safe progress channel between a sync worker and an async caller.

    Construct on the event loop thread. Pass `thread_emitter()` into
    `asyncio.to_thread(worker, ..., progress=...)`. Iterate
    `drain_until(task)` from the streaming endpoint to receive events
    as they arrive.
    """

    def __init__(self) -> None:
        # We capture the running loop so the worker can schedule queue
        # writes onto it from any thread via call_soon_threadsafe.
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()

    def thread_emitter(self) -> Callable[[ProgressEvent], None]:
        """Return a callable safe to invoke from a worker thread."""
        loop = self._loop
        queue = self._queue

        def _emit(event: ProgressEvent) -> None:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                # Loop closed (client disconnected, app shutting down).
                # The worker should not raise just because nobody is
                # listening to its progress; silently drop the event.
                pass

        return _emit

    async def drain_until(
        self,
        task: "asyncio.Task[Any]",
        *,
        heartbeat_seconds: float = 5.0,
        heartbeat: Optional[Callable[[int], ProgressEvent]] = None,
    ) -> AsyncIterator[ProgressEvent]:
        """Yield events until `task` completes.

        Real events are yielded as soon as the worker emits them. If no
        event arrives within `heartbeat_seconds`, the optional
        `heartbeat(idle_count)` factory produces a fallback event so the
        client sees motion instead of silence. `idle_count` increments
        on each consecutive heartbeat fire so callers can rotate
        messages.
        """
        idle_count = 0
        while not task.done():
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=heartbeat_seconds,
                )
                idle_count = 0
                yield event
            except asyncio.TimeoutError:
                if heartbeat is not None and not task.done():
                    yield heartbeat(idle_count)
                    idle_count += 1

        # Drain anything that landed between the last get() and the
        # task completing, so late-arriving milestones are not lost.
        while not self._queue.empty():
            yield self._queue.get_nowait()


# Sentinel for callers who want to keep their function signature flat
# but pass "no progress reporting" without a None check at every site.
def noop_emitter(event: ProgressEvent) -> None:  # pragma: no cover
    """No-op emitter for callers that do not want progress reporting."""
    return None
