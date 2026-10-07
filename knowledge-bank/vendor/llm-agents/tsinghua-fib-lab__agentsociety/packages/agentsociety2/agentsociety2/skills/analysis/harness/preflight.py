from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from agentsociety2.skills.analysis.harness.operations import AnalysisOperationSpec

OperationAvailabilityState = Literal[
    "AVAILABLE",
    "BLOCKED_BY_PHASE",
    "BLOCKED_BY_GATE",
    "MISSING_DEPENDENCY",
    "UNHEALTHY",
    "DISABLED",
    "INVALID_INPUT",
]


class OperationAvailability(BaseModel):
    """Machine-readable result shared by CLI dry-run and orchestration."""

    model_config = ConfigDict(frozen=True)

    operation_id: str
    status: OperationAvailabilityState
    reasons: tuple[str, ...] = Field(default_factory=tuple)
    missing_inputs: tuple[str, ...] = Field(default_factory=tuple)
    missing_gates: tuple[str, ...] = Field(default_factory=tuple)
    checked_capabilities: dict[str, str] = Field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status == "AVAILABLE"


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _resolved_capability(requirement: str, values: Mapping[str, Any]) -> str | None:
    resolved = requirement
    for input_spec in values:
        resolved = resolved.replace(f"{{{input_spec}}}", str(values[input_spec]))
    if "{" in resolved or "}" in resolved:
        return None
    return resolved


def evaluate_operation_availability(
    spec: AnalysisOperationSpec,
    *,
    phase: str | None = None,
    passed_gates: Iterable[str] = (),
    current_gate_pass: bool = False,
    capability_states: Mapping[str, str] | None = None,
    values: Mapping[str, Any] | None = None,
    check_inputs: bool = True,
) -> OperationAvailability:
    values = values or {}
    passed = set(passed_gates)
    capability_states = capability_states or {}

    missing_inputs = (
        tuple(
            input_spec.name
            for input_spec in spec.inputs
            if input_spec.required and not _is_present(values.get(input_spec.name))
        )
        if check_inputs
        else ()
    )
    input_reasons: list[str] = []
    for group in spec.input_groups if check_inputs else ():
        present = [name for name in group.members if _is_present(values.get(name))]
        if group.mode == "exactly_one" and len(present) != 1:
            input_reasons.append(
                f"input group {group.id} requires exactly one of: "
                + ", ".join(group.members)
            )
        elif group.mode == "at_least_one" and group.required and not present:
            input_reasons.append(
                f"input group {group.id} requires at least one of: "
                + ", ".join(group.members)
            )
    if missing_inputs or input_reasons:
        reasons = [
            *(f"missing required input: {name}" for name in missing_inputs),
            *input_reasons,
        ]
        return OperationAvailability(
            operation_id=spec.id,
            status="INVALID_INPUT",
            reasons=tuple(reasons),
            missing_inputs=missing_inputs,
        )

    checked_capabilities: dict[str, str] = {}
    for requirement in spec.capability_requirements:
        capability_id = _resolved_capability(requirement, values)
        if capability_id is None:
            continue
        state = capability_states.get(capability_id, "unhealthy")
        checked_capabilities[capability_id] = state
        if state == "disabled":
            return OperationAvailability(
                operation_id=spec.id,
                status="DISABLED",
                reasons=(f"capability is disabled: {capability_id}",),
                checked_capabilities=checked_capabilities,
            )
        if state == "missing_dependency":
            return OperationAvailability(
                operation_id=spec.id,
                status="MISSING_DEPENDENCY",
                reasons=(f"capability dependency is missing: {capability_id}",),
                checked_capabilities=checked_capabilities,
            )
        if state != "available":
            return OperationAvailability(
                operation_id=spec.id,
                status="UNHEALTHY",
                reasons=(f"capability is unhealthy or unknown: {capability_id}",),
                checked_capabilities=checked_capabilities,
            )

    missing_gates = tuple(sorted(set(spec.depends_on_gates) - passed))
    if missing_gates:
        return OperationAvailability(
            operation_id=spec.id,
            status="BLOCKED_BY_GATE",
            reasons=("required gate(s) not passed: " + ", ".join(missing_gates),),
            missing_gates=missing_gates,
            checked_capabilities=checked_capabilities,
        )
    if spec.requires_current_gate and not current_gate_pass:
        return OperationAvailability(
            operation_id=spec.id,
            status="BLOCKED_BY_GATE",
            reasons=("current phase gate has not passed",),
            checked_capabilities=checked_capabilities,
        )
    if (
        phase is not None
        and spec.phase_policy == "enforced"
        and phase not in spec.phases
    ):
        return OperationAvailability(
            operation_id=spec.id,
            status="BLOCKED_BY_PHASE",
            reasons=(
                f"operation is not available in phase {phase}; expected one of: "
                + ", ".join(spec.phases),
            ),
            checked_capabilities=checked_capabilities,
        )
    return OperationAvailability(
        operation_id=spec.id,
        status="AVAILABLE",
        checked_capabilities=checked_capabilities,
    )
