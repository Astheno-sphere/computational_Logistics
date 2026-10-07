from __future__ import annotations

import importlib.util
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from agentsociety2.skills.analysis.harness.operations import EDA_PROFILE_NAMES

CapabilityState = Literal["available", "missing_dependency", "unhealthy", "disabled"]


class AnalysisCapabilityStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    state: CapabilityState
    detail: str = ""
    required_modules: tuple[str, ...] = Field(default_factory=tuple)


EDA_PROFILE_MODULES: dict[str, tuple[str, ...]] = {
    "quick-stats": ("pandas",),
    "ydata": ("pandas", "ydata_profiling"),
    "sweetviz": ("pandas", "sweetviz"),
    "missingno": ("pandas", "matplotlib", "missingno"),
    "correlation": ("pandas", "matplotlib"),
    "pygwalker": ("pandas", "pygwalker"),
    "datatable": ("pandas",),
    "plotly-profile": ("pandas", "plotly"),
    "eda-hub": (),
    "bundle": ("pandas",),
}

if tuple(EDA_PROFILE_MODULES) != EDA_PROFILE_NAMES:  # pragma: no cover
    raise RuntimeError("EDA capability profiles do not match the operation contract")


def _probe_modules(modules: Iterable[str]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    unhealthy: list[str] = []
    for module in modules:
        try:
            found = importlib.util.find_spec(module)
        except ModuleNotFoundError:
            missing.append(module)
            continue
        except (ImportError, ValueError) as exc:
            unhealthy.append(f"{module}: {exc}")
            continue
        if found is None:
            missing.append(module)
    return missing, unhealthy


def analysis_capability_statuses() -> list[AnalysisCapabilityStatus]:
    statuses: list[AnalysisCapabilityStatus] = []
    for profile, modules in EDA_PROFILE_MODULES.items():
        missing, unhealthy = _probe_modules(modules)
        state: CapabilityState
        if unhealthy:
            state = "unhealthy"
            detail = "Dependency probe failed: " + "; ".join(unhealthy)
        elif missing:
            state = "missing_dependency"
            detail = f"Missing Python module(s): {', '.join(missing)}"
        else:
            state = "available"
            detail = "Required Python modules are importable."
        if profile == "bundle" and state == "available":
            optional = [
                name
                for name in ("ydata", "pygwalker", "datatable", "plotly-profile")
                if any(_probe_modules(EDA_PROFILE_MODULES[name]))
            ]
            if optional:
                detail = (
                    "Core bundle is available; optional profile(s) will be skipped: "
                    + ", ".join(optional)
                )
        statuses.append(
            AnalysisCapabilityStatus(
                id=f"eda.{profile}",
                name=f"EDA profile: {profile}",
                state=state,
                detail=detail,
                required_modules=modules,
            )
        )

    statuses.extend(
        [
            AnalysisCapabilityStatus(
                id="report.html",
                name="Bilingual HTML report assembly",
                state="available",
                detail="Built-in report bundle and EDA embedding helpers are available.",
            ),
            AnalysisCapabilityStatus(
                id="report.render-validation",
                name="Browser-rendered report validation",
                state="disabled",
                detail="Headless browser acceptance is not part of the P0 harness.",
            ),
        ]
    )
    return statuses


def get_eda_capability_status(profile: str) -> AnalysisCapabilityStatus:
    capability_id = f"eda.{profile}"
    for status in analysis_capability_statuses():
        if status.id == capability_id:
            return status
    raise KeyError(profile)


def capability_payload() -> list[dict]:
    return [status.model_dump(mode="json") for status in analysis_capability_statuses()]
