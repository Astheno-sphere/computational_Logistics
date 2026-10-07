"""Canonical SI units per quantity (engine-agnostic vocabulary)."""
from __future__ import annotations

CANONICAL_UNITS = {
    "WaterLevel": "m",
    "WaterDepth": "m",
    "Discharge": "m3/s",
    "DischargeInStructure": "m3/s",
    "FlowVelocity": "m/s",
    "CrestLevel": "m",
    "GateLevel": "m",
    "Rainfall": "mm/h",
}


def unit_for(quantity: str) -> str:
    return CANONICAL_UNITS.get(quantity, "")
