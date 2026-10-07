"""OTel-compatible tracing for AgentSociety2.

Exports
-------
TraceSpan
    Runtime span dataclass.
JsonlTraceWriter
    Single-file OTel JSONL writer (one per agent); delegates storage to a
    sharded backend.
ShardedAppendSink
    Distributed, lock-free append-only sink sharded by ``trace_id[:2]`` (256
    files). Each writer process holds its own instance and appends directly
    via ``os.write(O_APPEND)`` — no central Ray actor, so it cannot deadlock.
ShardedTraceWriter
    Backward-compatible alias for :class:`ShardedAppendSink`.
TraceProxy
    Serializable config (just an output dir) from which each consumer builds
    its own ``ShardedAppendSink``.
new_trace_id
    Generate a 32-char hex UUID trace ID.
"""

from agentsociety2.trace.sharded_writer import (
    JsonlTraceWriter,
    ShardedAppendSink,
    TraceProxy,
    build_local_sink,
    new_trace_id,
)
from agentsociety2.trace.span import TraceSpan

ShardedTraceWriter = ShardedAppendSink

__all__ = [
    "JsonlTraceWriter",
    "ShardedAppendSink",
    "ShardedTraceWriter",
    "TraceProxy",
    "TraceSpan",
    "build_local_sink",
    "new_trace_id",
]
