"""The auto-discovery registry must surface exactly the expected tools with valid schemas.

Imports stay license-free: discovery imports the ``tools/`` modules, which only pull in
lightweight types + the worker launcher (never mikeplus / mikeio).
"""
from mikeplus_mcp.registry import discover_tools

EXPECTED = {
    # license-gated (mikeplus)
    "mike_model_info",
    "mike_get_values",
    "mike_set_values",
    "mike_run",
    "mike_set_scenario",
    "mike_import_swmm",
    # license-free (mikeio1d / mikeio / pure python)
    "mike_results_list",
    "mike_results_summary",
    "mike_results_read",
    "mike_results_compare",
    "mike_results_flooding",
    "mike_plot_rain_flow",
    "mike_plot_timeseries",
    "mike_plot_network",
    "mike_plot_compare",
    "mike_plot_profile",
    "mike_rain_to_dfs0",
    "mike_manifest_write",
}


def test_discovers_exactly_the_expected_tools():
    names = [t.name for t in discover_tools()]
    assert set(names) == EXPECTED


def test_tool_names_are_unique():
    names = [t.name for t in discover_tools()]
    assert len(names) == len(set(names))


def test_every_tool_has_a_valid_input_schema():
    for t in discover_tools():
        assert t.description.strip(), f"{t.name} has no description"
        schema = t.input_schema
        assert schema.get("type") == "object", f"{t.name} schema is not an object"
        assert "properties" in schema, f"{t.name} schema has no properties"
        # every declared required field must be a defined property
        for req in schema.get("required", []):
            assert req in schema["properties"], f"{t.name} requires undefined field {req!r}"
