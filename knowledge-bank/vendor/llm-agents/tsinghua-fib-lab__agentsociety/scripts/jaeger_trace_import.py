#!/usr/bin/env python3
"""Import AgentSociety trace JSONL files into Jaeger via OTLP HTTP.

Usage::

    # 1. Start Jaeger (podman or docker)
    podman run -d --name jaeger -p 16686:16686 -p 4318:4318 \\
        jaegertracing/all-in-one:latest

    docker run -d --name jaeger -p 16686:16686 -p 4318:4318 \\
        jaegertracing/all-in-one:latest

    # 2. Import trace files
    python scripts/jaeger_trace_import.py run_dir/trace/

    # 3. Open Jaeger UI
    http://localhost:16686

If you only have local ``events.jsonl`` files (per-agent, pre-sharding)::

    python scripts/jaeger_trace_import.py run_dir/agents/ --legacy

The script reads *all* ``trace_*.jsonl`` files under the given directory,
partitions them by ``trace_id``, and sends each trace as a batch of spans
to the Jaeger OTLP HTTP endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

OTLP_HTTP_ENDPOINT = "http://localhost:4318/v1/traces"


def _jsonl_records(root: Path, *, glob: str = "trace_*.jsonl") -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob(glob)):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  skip malformed line in {path}", file=sys.stderr)
    return records


def _legacy_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("events.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                import logging
                logging.getLogger(__name__).debug("Skipping malformed JSON line in trace file")
    return records


def _group_by_trace(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    traces: dict[str, list[dict[str, Any]]] = {}
    for r in records:
        tid = r.get("trace_id", "unknown")
        traces.setdefault(tid, []).append(r)
    return traces


def _to_otlp_span(record: dict[str, Any]) -> dict[str, Any]:
    """Convert one AgentSociety JSONL record to an OTLP span."""
    _resource = record.get("resource", {})
    _scope = record.get("scope", {})
    attrs = record.get("attributes", {})

    return {
        "traceId": _hex_to_bytes(record.get("trace_id", "")),
        "spanId": _hex_to_bytes(record.get("span_id", "")),
        "parentSpanId": _hex_to_bytes(record.get("parent_span_id", ""))
        if record.get("parent_span_id")
        else "",
        "name": record.get("name", ""),
        "kind": 1,  # INTERNAL
        "startTimeUnixNano": str(record.get("start_time_unix_nano", 0)),
        "endTimeUnixNano": str(record.get("end_time_unix_nano", 0)),
        "status": {"code": 1 if record.get("status", {}).get("code") == "ok" else 2},
        "attributes": [
            {"key": k, "value": _attr_value(v)}
            for k, v in attrs.items()
            if not isinstance(v, (dict, list))
        ],
    }


def _hex_to_bytes(hex_str: str) -> str:
    """Convert hex string to base64-encoded bytes (OTLP format)."""
    import base64
    if not hex_str:
        return ""
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError:
        return ""
    return base64.b64encode(raw).decode()


def _attr_value(v: Any) -> dict[str, Any]:
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}


def _build_otlp_payload(
    traces: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    resource_spans: list[dict[str, Any]] = []
    for trace_id, spans in traces.items():
        # Group spans by resource (service.name + agent.id)
        by_resource: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for s in spans:
            res = s.get("resource", {})
            key = (res.get("service.name", ""), res.get("agent.id", 0))
            by_resource.setdefault(key, []).append(s)

        for (service_name, agent_id), group_spans in by_resource.items():
            scope_spans: list[dict[str, Any]] = []
            # Group by scope
            by_scope: dict[str, list[dict[str, Any]]] = {}
            for s in group_spans:
                sc = s.get("scope", {})
                key = f"{sc.get('name', '')}/{sc.get('version', '')}"
                by_scope.setdefault(key, []).append(s)

            for scope_key, ss in by_scope.items():
                first = ss[0].get("scope", {})
                scope_spans.append({
                    "scope": {
                        "name": first.get("name", "agentsociety2"),
                        "version": first.get("version", "v2"),
                    },
                    "spans": [_to_otlp_span(s) for s in ss],
                })

            resource_spans.append({
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}},
                        {"key": "agent.id", "value": {"intValue": str(agent_id)}},
                    ]
                },
                "scopeSpans": scope_spans,
            })

    return {"resourceSpans": resource_spans}


def send_to_jaeger(
    traces: dict[str, list[dict[str, Any]]],
    *,
    endpoint: str = OTLP_HTTP_ENDPOINT,
    dry_run: bool = False,
) -> None:
    import urllib.request

    payload = _build_otlp_payload(traces)
    body = json.dumps(payload).encode()

    if dry_run:
        out_path = Path("jaeger_payload.json")
        out_path.write_bytes(body)
        print(f"Dry-run: wrote {len(body):,} bytes to {out_path}")
        return

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"Sent {len(body):,} bytes → {resp.status} {resp.reason}")
    except urllib.error.URLError as e:
        print(f"Failed to connect to Jaeger at {endpoint}: {e}", file=sys.stderr)
        print("Is Jaeger running?  podman start jaeger", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace_dir",
        type=Path,
        help="Directory containing trace_*.jsonl files (or agents/ for --legacy).",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Read per-agent events.jsonl files instead of sharded trace_*.jsonl.",
    )
    parser.add_argument(
        "--endpoint",
        default=OTLP_HTTP_ENDPOINT,
        help=f"Jaeger OTLP HTTP endpoint (default: {OTLP_HTTP_ENDPOINT}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write OTLP payload to jaeger_payload.json instead of sending.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only import the first N traces (0 = all).",
    )
    args = parser.parse_args()

    if not args.trace_dir.is_dir():
        print(f"Not a directory: {args.trace_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading traces from {args.trace_dir}...")
    if args.legacy:
        records = _legacy_records(args.trace_dir)
    else:
        records = _jsonl_records(args.trace_dir)

    if not records:
        print("No trace records found.", file=sys.stderr)
        sys.exit(1)

    traces = _group_by_trace(records)
    print(f"Found {len(records):,} spans across {len(traces):,} traces")

    if args.limit > 0 and len(traces) > args.limit:
        keys = list(traces.keys())[: args.limit]
        traces = {k: traces[k] for k in keys}
        print(f"Limited to {args.limit} traces")

    send_to_jaeger(traces, endpoint=args.endpoint, dry_run=args.dry_run)


if __name__ == "__main__":
    main()