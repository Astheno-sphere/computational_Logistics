"""Typed plan models — the wire contract an agent's planner writes against.

FastMCP publishes these pydantic models as the tools' JSON schema, so any MCP
client sees the exact plan grammar. Everything is `extra="forbid"`: a planner
that invents fields gets a schema error it can act on, not silent acceptance.

Dataflow is symbolic: a string argument ``"$<step_id>"`` means "the output
dataset of that step". The step list IS the execution order, and references
may only point backwards — which makes every plan acyclic by construction and
turns the benchmark's dominant failure class (mis-ordered operations) into a
static, machine-readable error.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

STEP_ID_PATTERN = r"^[a-z][a-z0-9_]{0,31}$"
REFERENCE = re.compile(r"^\$([a-z][a-z0-9_]{0,31})$")

StepId = Annotated[str, StringConstraints(pattern=STEP_ID_PATTERN)]
ArgKey = Annotated[str, StringConstraints(min_length=1, max_length=64)]
ArgString = Annotated[str, StringConstraints(max_length=4096)]
ArgList = Annotated[list[ArgString], Field(max_length=256)]
ArgValue = ArgString | bool | int | float | ArgList


class PlanStep(BaseModel):
    """One operation invocation inside a plan."""

    model_config = ConfigDict(extra="forbid")

    id: StepId = Field(description="Unique step name, e.g. 'buffer_wells'")
    operation: Annotated[str, StringConstraints(min_length=1, max_length=64)] = Field(
        description="Operation name from list_operations (must be 'available')"
    )
    arguments: dict[ArgKey, ArgValue] = Field(
        default_factory=dict,
        max_length=32,
        description="Arguments as documented in the catalog; '$step_id' strings "
        "reference the output of an earlier step",
    )
    comment: Annotated[str, StringConstraints(max_length=2000)] = Field(
        default="", description="Optional rationale; recorded in the plan manifest"
    )


class Plan(BaseModel):
    """A validated-before-execution geoprocessing plan (an implicit DAG)."""

    model_config = ConfigDict(extra="forbid")

    goal: Annotated[str, StringConstraints(max_length=4000)] = Field(
        default="", description="The user goal this plan serves; goes in the manifest"
    )
    steps: list[PlanStep] = Field(
        min_length=1, max_length=50, description="Steps in execution order"
    )

    def sha256(self) -> str:
        """Deterministic fingerprint of the canonical plan JSON.

        Numbers are normalized (300 and 300.0 hash identically) so semantically
        equal plans dedup to the same fingerprint; bools stay bools.
        """
        canonical = json.dumps(
            _normalize_numbers(self.model_dump()), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_numbers(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, list):
        return [_normalize_numbers(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_numbers(v) for k, v in value.items()}
    return value


class Issue(BaseModel):
    """One machine-actionable validation finding."""

    code: str
    step_id: str | None = None
    message: str


class SimulatedOutput(BaseModel):
    """What a step will produce, as derived by static validation."""

    output: str
    crs: str  # "EPSG:xxxx", a WKT/name string, or "unknown"


class ValidationReport(BaseModel):
    """Outcome of static plan validation. `errors` non-empty => invalid."""

    valid: bool
    errors: list[Issue] = Field(default_factory=list)
    warnings: list[Issue] = Field(default_factory=list)
    notes: list[Issue] = Field(default_factory=list)
    simulated_outputs: dict[str, SimulatedOutput] = Field(default_factory=dict)
