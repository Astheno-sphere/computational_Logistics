"""Plan execution: validated first, sequential, audit trail always on disk.

Execution never starts on an invalid plan (execute() re-validates — trusting a
stale validate_plan result would be a TOCTOU hole). Steps run in list order;
the first failure stops the run, but everything already produced — outputs and
their per-step provenance manifests — stays on disk, and the plan manifest is
written even for partial runs: the audit trail survives the error, same
invariant as every MapSmith writer.

Deterministic repair happens inside the writers (verify.repair_and_reverify),
which is the only place that knows how to fix an output mechanically; what
reaches here are the results, including non-critical warnings the plan echoes
back per step so a completed run that produced nothing cannot look like a win.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..provenance import redact_secrets
from .models import REFERENCE, Plan
from .registry import BINDINGS
from .validator import validate

# step-result keys worth echoing back to the agent (full details live in provenance)
_ECHO_KEYS = (
    "output", "provenance", "feature_count", "crs", "engine_used", "verified",
    "warnings",  # non-critical verification failures (empty results, disjoint inputs)
    "repairs",  # geometry MapSmith rewrote: must not be invisible at plan level
)


def execute(plan: Plan) -> dict[str, Any]:
    """Validate, then run the plan. Returns per-step results and the plan manifest."""
    report = validate(plan)
    if not report.valid:
        return {
            "executed": False,
            "reason": "plan failed validation — nothing was run",
            "validation": report.model_dump(),
        }

    started = datetime.now(UTC).isoformat()
    outputs: dict[str, str] = {}
    steps: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None

    for step in plan.steps:
        binding = BINDINGS[step.operation]
        kwargs = _resolve_arguments(step.arguments, outputs, binding.input_args)
        record: dict[str, Any] = {"id": step.id, "operation": step.operation}
        clock = time.perf_counter()
        try:
            result = binding.loader()(**kwargs)
        except Exception as exc:  # noqa: BLE001 — every engine failure must reach the manifest
            record["status"] = "failed"
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["elapsed_ms"] = round((time.perf_counter() - clock) * 1000, 1)
            steps.append(record)
            failure = {"step_id": step.id, "error": record["error"]}
            break
        record["status"] = "ok"
        record["elapsed_ms"] = round((time.perf_counter() - clock) * 1000, 1)
        if isinstance(result, dict):
            for key in _ECHO_KEYS:
                if key in result:
                    record[key] = result[key]
        if binding.output_arg:
            value = kwargs.get(binding.output_arg)
            if isinstance(value, str) and value:
                outputs[step.id] = value
        steps.append(record)

    manifest_path = _write_plan_manifest(plan, report, steps, outputs, started)
    response: dict[str, Any] = {
        "executed": failure is None,
        "plan_sha256": plan.sha256(),
        "steps": steps,
        "plan_manifest": manifest_path,
    }
    if failure:
        response["failed_step"] = failure
        response["reason"] = (
            f"step '{failure['step_id']}' failed; earlier outputs and their "
            "provenance manifests are kept on disk"
        )
    if report.warnings:
        response["validation_warnings"] = [w.model_dump() for w in report.warnings]
    # a plan can run to completion with every step producing nothing: surface it
    flagged = [
        {"step_id": s["id"], "warnings": s["warnings"]} for s in steps if s.get("warnings")
    ]
    if flagged:
        response["step_warnings"] = flagged
    return response


def _resolve_arguments(
    arguments: dict[str, Any], outputs: dict[str, str], input_args: tuple[str, ...]
) -> dict[str, Any]:
    """Replace '$step_id' references with concrete output paths.

    Only dataset input arguments resolve references (validation rejects '$refs'
    anywhere else), so a value like predicate='$x' can never be rewritten into
    an unexpected path.
    """
    resolved: dict[str, Any] = {}
    for key, value in arguments.items():
        if key in input_args and isinstance(value, str):
            match = REFERENCE.match(value)
            if match:
                value = outputs[match.group(1)]
        resolved[key] = value
    return resolved


def _write_plan_manifest(
    plan: Plan,
    report: Any,
    steps: list[dict[str, Any]],
    outputs: dict[str, str],
    started: str,
) -> str | None:
    """Write the plan-level manifest next to the last produced output."""
    if not outputs:
        return None
    from .. import __version__

    last_output = list(outputs.values())[-1]
    manifest_path = f"{last_output}.plan.json"
    manifest = {
        "mapsmith_version": __version__,
        "plan_sha256": plan.sha256(),
        "goal": plan.goal,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "steps": [
            {
                **record,
                "comment": next(
                    (s.comment for s in plan.steps if s.id == record["id"] and s.comment),
                    None,
                ),
            }
            for record in steps
        ],
        "validation": {
            "warnings": [w.model_dump() for w in report.warnings],
            "notes": [n.model_dump() for n in report.notes],
        },
    }
    # Redacted whole, at the single exit point, rather than field by field.
    # This manifest never passes through ProvenanceRecord — it is a dict built
    # here — so the redaction applied to every record did not cover it, and
    # three of its fields carry model- or user-written text: `goal`, each step's
    # `comment`, and the `error` of a failed one. That last one was the sharp
    # case: the message refusing a credential quoted the credential. Redacting
    # here rather than on the three fields is deliberate — a field added later
    # is covered without anyone having to remember. `<output>.plan.json` is a
    # manifest like the others, and manifests are meant to be shared.
    Path(manifest_path).write_text(
        json.dumps(redact_secrets(manifest), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest_path
