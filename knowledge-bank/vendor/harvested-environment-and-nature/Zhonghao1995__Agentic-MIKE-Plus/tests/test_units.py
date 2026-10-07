"""Unit tests for the canonical unit vocabulary."""
from mikeplus_mcp.contracts.units import unit_for


def test_known_quantities():
    assert unit_for("Discharge") == "m3/s"
    assert unit_for("WaterLevel") == "m"
    assert unit_for("FlowVelocity") == "m/s"


def test_unknown_quantity_returns_empty_string():
    assert unit_for("SomethingMadeUp") == ""
