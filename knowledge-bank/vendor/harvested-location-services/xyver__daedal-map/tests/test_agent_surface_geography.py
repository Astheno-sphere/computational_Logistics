from agent_surface_shared import (
    geography_workflow_section,
    render_app_llms_txt,
    render_site_llms_full,
    render_site_llms_txt,
)
from pack_registry_shared import tool_family_catalog_entry


def test_llm_surfaces_cover_every_current_geography_tool() -> None:
    tool_names = [
        str(item.get("name") or "")
        for item in tool_family_catalog_entry("geography").get("tools") or []
    ]
    surfaces = (render_app_llms_txt(), render_site_llms_txt(), render_site_llms_full())

    assert len(tool_names) == 11
    assert "identify_dataset_geography" in tool_names
    for surface in surfaces:
        for tool_name in tool_names:
            assert f"`{tool_name}`" in surface
        assert "All packs share a loc_id" not in surface
        assert "four user-facing modes" not in surface
        assert "include_references=true" in surface
        assert "country_scope" in surface
        assert "shallow scope" in surface
        assert "get_boundary" not in surface
        assert "loc_id_hierarchy" not in surface
        assert "loc_id_references" not in surface
        assert "resolve_points" not in surface
        assert "resolve_deep_points" not in surface
    for surface in surfaces[1:]:
        assert "reusable geometry" in surface
        assert "published crosswalks" in surface


def test_geography_workflow_is_question_first_and_bounded() -> None:
    workflow = geography_workflow_section()

    assert "Point to loc_id" in workflow
    assert "What a loc_id is connected to" in workflow
    assert "Shape lookup" in workflow
    assert "bounded batch" in workflow
    assert "not part of the public MCP roster" in workflow
    assert "Advanced builder foundation" not in workflow
    assert "Durable uploads, saved projects, and custom downloadable artifacts" not in workflow


def test_agent_surfaces_list_every_published_data_query_tool() -> None:
    from agent_surface_shared import data_tool_entries, render_for_agents_registry_quickstart
    from mcp_data_contract_shared import DATA_QUERY_TOOL_IDS, DATA_RELATIONSHIP_TOOL_IDS
    from mcp_surface_shared import build_tool_definitions

    published = {definition["name"] for definition in build_tool_definitions()}
    expected = sorted((DATA_QUERY_TOOL_IDS | DATA_RELATIONSHIP_TOOL_IDS) & published)
    assert expected == ["get_data", "get_event"]
    assert [entry["name"] for entry in data_tool_entries()] == expected

    quickstart = render_for_agents_registry_quickstart()
    assert "<h2>Data tools</h2>" in quickstart
    assert all(ord(ch) < 128 for ch in quickstart)
    for surface in (render_app_llms_txt(), render_site_llms_txt(), render_site_llms_full(), quickstart):
        for name in expected:
            assert name in surface
        assert "report whether a pack is free or paid" in surface
