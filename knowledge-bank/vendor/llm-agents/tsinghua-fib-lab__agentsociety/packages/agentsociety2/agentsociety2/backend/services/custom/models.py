"""Shared diagnostic models for custom-module backend services."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

IssueSeverity = Literal["error", "warning"]


class CompatibilityIssue(BaseModel):
    """A compatibility issue discovered during scan or validation."""

    code: str
    message: str
    severity: IssueSeverity = "error"
    check: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ScanDiagnostic(BaseModel):
    """Structured scan output for a single custom module candidate."""

    module_kind: Literal["agent", "env_module"]
    module_path: str
    file_path: str
    class_name: str | None = None
    accepted: bool = False
    issues: list[CompatibilityIssue] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationCheck(BaseModel):
    """A structured validation check."""

    name: str
    passed: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
