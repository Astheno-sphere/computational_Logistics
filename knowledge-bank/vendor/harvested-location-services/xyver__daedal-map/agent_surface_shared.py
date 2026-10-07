from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from typing import Callable, Iterable

from pack_registry_shared import (
    agent_data_workflow,
    pack_display_name,
    pack_mcp_server_profile,
    pack_registry_alias,
    published_pack_ids,
    tool_family_catalog_entry,
    tool_family_ids,
)
from pack_pricing_shared import FREE_PACK_IDS, PAID_PACK_IDS

CURRENT_HOSTED_PACK_IDS: tuple[str, ...] = published_pack_ids()

# Canonical public origins. The apex host 301s to www, so machine-facing files
# always link www directly.
DEFAULT_SITE_ORIGIN = "https://www.daedalmap.com"
DEFAULT_APP_ORIGIN = "https://app.daedalmap.com"
LOC_ID_GUIDE_PATH = "/loc_id"
CONTACT_EMAIL = "contact@daedalmap.com"


_PACK_ID_PROVIDER: Callable[[], Iterable[str]] | None = None


def set_pack_id_provider(provider: Callable[[], Iterable[str]] | None) -> None:
    """Register the host's published-catalog pack ids as the source of truth.

    The website passes the same prewarmed catalog records that /packs and the
    sitemap use; the app passes its prewarmed API catalog. Without a provider,
    or when it returns nothing (catalog not loaded), the code registry is the
    fallback so these files never render empty.
    """
    global _PACK_ID_PROVIDER
    _PACK_ID_PROVIDER = provider


def current_pack_ids() -> tuple[str, ...]:
    if _PACK_ID_PROVIDER is not None:
        try:
            ids = tuple(dict.fromkeys(str(pid).strip() for pid in _PACK_ID_PROVIDER() if str(pid or "").strip()))
        except Exception:
            ids = ()
        if ids:
            return ids
    return CURRENT_HOSTED_PACK_IDS


def facade_pack_ids() -> tuple[str, ...]:
    """Published packs that also have an MCP facade in the registry."""
    registered = set(CURRENT_HOSTED_PACK_IDS)
    return tuple(pack_id for pack_id in current_pack_ids() if pack_id in registered)


def free_pack_ids() -> tuple[str, ...]:
    return tuple(pack_id for pack_id in current_pack_ids() if pack_id in FREE_PACK_IDS)


def paid_pack_ids() -> tuple[str, ...]:
    return tuple(pack_id for pack_id in current_pack_ids() if pack_id in PAID_PACK_IDS)


def pack_count() -> int:
    return len(current_pack_ids())


def pack_label(pack_id: str) -> str:
    return pack_display_name(pack_id)


def free_pack_csv() -> str:
    return ", ".join(free_pack_ids())


def paid_pack_csv() -> str:
    return ", ".join(paid_pack_ids())


def free_pack_display_csv() -> str:
    return ", ".join(pack_label(pack_id) for pack_id in free_pack_ids())


def paid_pack_display_csv() -> str:
    return ", ".join(pack_label(pack_id) for pack_id in paid_pack_ids())


def render_for_agents_registry_quickstart() -> str:
    """Render the human quickstart from the same registries as MCP discovery."""
    steps = "".join(
        "<li>Call <code>{tool}</code>: {outcome}</li>".format(
            tool=escape(str(step.get("tool") or "")),
            outcome=escape(str(step.get("outcome") or "")),
        )
        for step in agent_data_workflow()
    )
    geography = tool_family_catalog_entry("geography")
    tools = "".join(
        "<li><code>{name}</code> - {summary}</li>".format(
            name=escape(str(tool.get("name") or "")),
            summary=escape(str(tool.get("summary") or "")),
        )
        for tool in geography.get("tools") or []
    )
    data_tools = "".join(
        "<li><code>{name}</code> - {summary}</li>".format(
            name=escape(entry["name"]),
            summary=escape(entry["description"].split(". ", 1)[0].rstrip(".") + "."),
        )
        for entry in data_tool_entries()
    )
    access_note = (
        escape(DATA_TOOL_ACCESS_NOTE)
        .replace("`get_catalog`", "<code>get_catalog</code>")
        .replace("`get_pack`", "<code>get_pack</code>")
    )
    return (
        "<h2>First successful flow</h2>"
        f'<ol class="detail-list">{steps}</ol>'
        "<p>Each successful row query returns <code>resolved_query</code>; copy it to rerun the resolved request deterministically.</p>"
        "<h2>Data tools</h2>"
        f'<ul class="detail-list">{data_tools}</ul>'
        f"<p>{access_note}</p>"
        "<h2>Choose your first geography job</h2>"
        f'<ul class="detail-list">{tools}</ul>'
        '<p><a class="docs-next-link" href="/docs/geometry-tools">Open the geography tool guide</a></p>'
    )


def example_free_pack_ids(limit: int = 4) -> tuple[str, ...]:
    """Current free packs to name in examples; never a hand-written list."""
    return free_pack_ids()[:limit]


def example_paid_pack_ids(limit: int = 2) -> tuple[str, ...]:
    return paid_pack_ids()[:limit]


def example_facade_ids(limit: int = 6) -> tuple[str, ...]:
    return facade_pack_ids()[:limit]


def _code_list(items, *, prefix: str = "", conjunction: str = "or") -> str:
    quoted = [f"`{prefix}{item}`" for item in items]
    if len(quoted) <= 1:
        return "".join(quoted)
    return ", ".join(quoted[:-1]) + f", {conjunction} {quoted[-1]}"


def current_pack_code_bullets() -> str:
    return "\n".join(f"- `{pack_id}`" for pack_id in current_pack_ids())


def facade_link_bullets(app_origin: str) -> str:
    lines: list[str] = []
    base = app_origin.rstrip("/")
    for pack_id in facade_pack_ids():
        line = f"- [{pack_id}]({base}/mcp/{pack_id})"
        alias = pack_registry_alias(pack_id)
        if alias:
            line += f" - registry-published under the searchable name `{alias}`"
        lines.append(line)
    return "\n".join(lines)


def facade_server_json_lines(app_origin: str) -> str:
    base = app_origin.rstrip("/")
    return "\n".join(f"- `GET {base}/mcp/{pack_id}/server.json`" for pack_id in facade_pack_ids())


def facade_transport_lines(app_origin: str) -> str:
    base = app_origin.rstrip("/")
    lines: list[str] = []
    for pack_id in facade_pack_ids():
        lines.append(f"- `GET {base}/mcp/{pack_id}`")
        lines.append(f"- `POST {base}/mcp/{pack_id}`")
    return "\n".join(lines)


def geography_tools_section(app_origin: str) -> str:
    """Registry-driven markdown block for geography/utility tool families.

    Tool families (e.g. geography) are not data packs, so they are not in
    published_pack_ids(); they are surfaced here from tool_family_ids() so the
    machine-readable agent surfaces advertise the free loc_id spine tools.
    """
    base = app_origin.rstrip("/")
    blocks: list[str] = []
    for family_id in tool_family_ids():
        entry = tool_family_catalog_entry(family_id)
        profile = pack_mcp_server_profile(family_id)
        tool_line = ", ".join(f"`{tool.get('name')}`" for tool in (entry.get("tools") or []))
        blocks.append(
            f"- `{family_id}` utility family (free) - {entry.get('description')}\n"
            f"  - facade: `{base}/mcp/{family_id}` (registry name `{profile.get('name')}`)\n"
            f"  - tools: {tool_line}\n"
            f"  - also reachable on the umbrella `{base}/mcp`; no payment required"
        )
    return "\n".join(blocks)


def data_tool_entries() -> list[dict[str, str]]:
    """Published data query and event drill-down tools, from the MCP data contract."""
    from mcp_data_contract_shared import (
        DATA_QUERY_TOOL_IDS,
        DATA_RELATIONSHIP_TOOL_IDS,
        DATA_TOOL_DESCRIPTIONS,
    )
    from mcp_surface_shared import build_tool_definitions

    published = {str(definition.get("name") or "") for definition in build_tool_definitions()}
    names = [*sorted(DATA_QUERY_TOOL_IDS), *sorted(DATA_RELATIONSHIP_TOOL_IDS)]
    return [
        {"name": name, "description": DATA_TOOL_DESCRIPTIONS[name]}
        for name in names
        if name in published
    ]


DATA_TOOL_ACCESS_NOTE = (
    "Access is set per pack: `get_catalog` and `get_pack` report whether a pack is free or paid "
    "before you query it."
)


def data_tools_section() -> str:
    """Markdown block for the data query tools that follow get_catalog and get_pack."""
    lines = [f"- `{entry['name']}` - {entry['description']}" for entry in data_tool_entries()]
    lines.append(f"- {DATA_TOOL_ACCESS_NOTE}")
    return "\n".join(lines)


def geography_workflow_section() -> str:
    """Return question-first instructions for the current geography MCP roster."""
    return (
        "1. Point to loc_id: call `resolve_point` with one coordinate or a bounded array; it stops at Admin 3. For Admin 4-6, group results by shallow scope and call `resolve_deep_point` with one coordinate or array plus one `shallow_loc_id` per call.\n"
        "2. What a loc_id is connected to: call `get_loc_id_info`; add `include_references=true` for exact attached crosswalks and `include_hierarchy=true` for strict stored ancestry.\n"
        "3. Dataset to loc_id: pass bounded, structurally filtered column samples to `identify_dataset_geography`; it selects the column, country, level, and system. For one already-selected identifier column, use `identify_reference_system`. Resolve a known outside code or name with `convert_reference` and omit `to_system`; provide `to_system` only when another reference system is the desired output.\n"
        "4. Shape lookup: call `get_geometry` with its default `include_polygon=false` for availability, metadata, bbox, and centroid; set `include_polygon=true` only when shape coordinates are needed. If the requested record is historical, return it first; present any `supersession` prompt as a second question and do not fetch the successor until the caller chooses it.\n"
        "5. Coverage discovery: call `get_catalog(catalog='geometry', detail='lite')`, then `get_pack(catalog='geometry', pack_id='<family>', country_scope='<ISO3>')` for country systems, vintages, levels, and artifacts. A listed family-country pair is exchangeable through loc_id.\n"
        "6. Relationship between two loc_ids: call `compare_geographies`. For bounded shapes under a supported administrative parent and level, use the `scope` input on `get_geometry`.\n"
        "7. Batch rule: use a bounded batch where supported; split deep work by Admin1 owner.\n"
        "8. If the right path is unclear: call `get_tool_help` with a topic, then with one exact visible tool name. Future estimate/create/status builder contracts are retained internally but are not part of the public MCP roster."
    )


GEOMETRY_COVERAGE_LABEL = "global baseline plus 8+ deeper countries"


def data_pack_count_label() -> str:
    return str(pack_count())


def coverage_section(app_origin: str, site_origin: str) -> str:
    return (
        "## Coverage\n\n"
        f"- Data: {data_pack_count_label()} maintained data packs across natural hazards, hazard risk, economic, business, and development indicators, population, and climate. "
        f"Call GET {app_origin}/api/v1/catalog for the live pack index and each pack's access lane.\n"
        f"- Geometry: {GEOMETRY_COVERAGE_LABEL}. "
        f"Call `get_catalog(catalog='geometry')` or GET {app_origin}/api/v1/geometry/catalog for current country and family coverage.\n"
        f"- Downloads: [{site_origin}/downloadable/]({site_origin}/downloadable/) - programs, data packs, and geometry packages\n"
    )


def pack_sentence() -> str:
    return ", ".join(facade_pack_ids())


def free_vs_paid_sentence() -> str:
    return (
        f"Free packs: {free_pack_csv()}. "
        f"Paid packs, charged per call from account credit: {paid_pack_csv()}."
    )


def agent_ai_plugin_description_for_model(*, app_origin: str, docs_origin: str, include_examples: bool) -> str:
    base = (
        "Resolve geographic references to loc_id identities, inspect relationships, discover and "
        "retrieve reusable geometry, follow published crosswalks, and query maintained data across "
        "disasters (earthquakes, tsunamis, volcanoes, "
        "hurricanes, tornadoes, floods), UN SDG indicators, World Factbook country "
        "profiles, and World Bank development indicators. "
        f"If your runtime supports remote MCP, start with {app_origin.rstrip('/')}/mcp"
    )
    if include_examples:
        base += (
            f" and read {docs_origin.rstrip('/')}/agents. "
            "For raw HTTP discovery, start with GET /api/v1/catalog, then GET /api/v1/packs/{pack_id}, "
            "then POST /api/v1/query/dataset. "
        )
    else:
        base += (
            " and /mcp/server.json first. "
            "For raw HTTP discovery, start with GET /api/v1/catalog, then GET /api/v1/packs/{pack_id}, "
            "then POST /api/v1/query/dataset with the structured body from quick_start.first_query_template. "
        )
    base += (
        "Compatible data packs join directly through loc_id. The administrative spine is the main "
        "join surface; postal, watershed, Indigenous land, forest, and other geography families "
        "retain distinct identities and connect through published crosswalks when one exists. "
        "Geography tools use loc_id as the durable identifier. Start with get_tool_help(topic='geometry'), "
        "then get_catalog(catalog='geometry') and get_pack for country and family coverage. "
        "Use identify_reference_system when an input column is unknown. "
        "resolve_point, resolve_deep_point, get_loc_id_info, and get_geometry accept a bounded batch. "
        "request_id is optional but recommended for tracing and idempotency. "
        f"{free_vs_paid_sentence()}"
    )
    return base


def render_app_llms_txt(*, app_origin: str = DEFAULT_APP_ORIGIN, site_origin: str = DEFAULT_SITE_ORIGIN) -> str:
    return (
        "# DaedalMap App\n\n"
        "This host is the human-facing app at app.daedalmap.com.\n"
        "If you are an agent, crawler, or developer bot, use the MCP server or agent docs instead of the app UI.\n\n"
        "## MCP first\n"
        f"- Remote MCP server: {app_origin}/mcp\n"
        f"- MCP server metadata: {app_origin}/mcp/server.json\n"
        "- Registry identity: com.daedalmap/county-map\n"
        "- Current transport: streamable HTTP\n"
        "- MCP wraps the same discovery and execution lane as the hosted API\n\n"
        "## Agent lane\n"
        f"- Start here for agents: {site_origin}/agents\n"
        f"- Developer guide: {site_origin}/devs\n"
        f"- Agent examples: {site_origin}/docs/agent-examples\n"
        f"- loc_id guide: {site_origin}{LOC_ID_GUIDE_PATH}\n"
        f"- Geometry tools: {site_origin}/docs/geometry-tools\n"
        f"- Full machine-readable guide: {site_origin}/llms-full.txt\n\n"
        "## Live machine-facing endpoints\n"
        f"- GET {app_origin}/mcp/server.json\n"
        f"- GET {app_origin}/mcp\n"
        f"- POST {app_origin}/mcp\n"
        f"- GET {app_origin}/api/v1/guide\n"
        f"- GET {app_origin}/api/v1/catalog\n"
        f"- GET {app_origin}/api/v1/packs/{{pack_id}}\n"
        f"- POST {app_origin}/api/v1/query/dataset\n\n"
        "## Complete public catalog snapshots\n"
        f"- Data catalog: {app_origin}/api/v1/catalog/download\n"
        f"- Geometry discovery: {app_origin}/api/v1/geometry/catalog\n"
        "- Use the catalog endpoints instead of crawling underlying object paths.\n\n"
        f"{coverage_section(app_origin, site_origin)}\n"
        "## Geography utility tools (free)\n"
        "Free geographic reference and geometry tools: resolve coordinates and codes, inspect loc_id identities and relationships, discover published coverage, retrieve boundaries, and follow available crosswalks without flattening distinct geography families.\n"
        f"{geography_tools_section(app_origin)}\n\n"
        "### Choose the tool by question\n"
        f"{geography_workflow_section()}\n\n"
        "## Data tools\n"
        f"{data_tools_section()}\n\n"
        "## App UI\n"
        f"- Human-facing app: {app_origin}\n"
        f"- Website and docs: {site_origin}\n"
        f"- Source coverage: {site_origin}/docs/source-map\n"
        f"- Data packs: {site_origin}/packs\n"
        "- GitHub (open runtime): https://github.com/xyver/daedal-map\n\n"
        "## Crawlers and bots\n"
        "Use the MCP server and agent API lane above. request_id is optional but recommended for tracing and idempotency. Keep requests narrow and respect rate limits; broad live scans may be rejected with guidance.\n"
    )


def render_site_llms_txt(*, app_origin: str = DEFAULT_APP_ORIGIN, site_origin: str = DEFAULT_SITE_ORIGIN) -> str:
    return (
        "# DaedalMap\n\n"
        "> If you are an agent, crawler, or developer bot, start with the agent lane, not the consumer app.\n\n"
        "DaedalMap exposes geographic reference and geometry tools, maintained data packs, a live remote MCP server, and a hosted HTTP API.\n"
        "This file is the machine-readable router. For explanation, examples, and current pack notes, follow the agent docs.\n\n"
        "## Start here\n\n"
        f"- Agent overview: [{site_origin}/agents]({site_origin}/agents)\n"
        f"- Developer guide: [{site_origin}/devs]({site_origin}/devs)\n"
        f"- Umbrella MCP endpoint: [{app_origin}/mcp]({app_origin}/mcp)\n"
        f"- MCP server metadata: [{app_origin}/mcp/server.json]({app_origin}/mcp/server.json)\n"
        f"- HTTP discovery: [{app_origin}/api/v1/guide]({app_origin}/api/v1/guide), [{app_origin}/api/v1/catalog]({app_origin}/api/v1/catalog), [{app_origin}/api/v1/packs/earthquakes]({app_origin}/api/v1/packs/earthquakes)\n"
        f"- Catalogs: [data]({app_origin}/api/v1/catalog/download), [geometry]({app_origin}/api/v1/geometry/catalog/download)\n"
        f"- Expanded machine guide: [{site_origin}/llms-full.txt]({site_origin}/llms-full.txt)\n\n"
        "## Product surface\n\n"
        "DaedalMap is geographic interoperability infrastructure: durable loc_id identities, reusable geometry, published crosswalks, and maintained data over one reference graph. Maps, Research, Ops, downloads, and agent tools are access surfaces over that foundation.\n\n"
        f"- [{site_origin}/]({site_origin}/) - project overview and conversion entrance\n"
        f"- [{site_origin}/geometry]({site_origin}/geometry) - published country geometry, families, representations, sources, and QA\n"
        f"- [{site_origin}/explore]({site_origin}/explore) - Explore mode (demo entry, ask a question, no account)\n"
        f"- [{site_origin}/research]({site_origin}/research) - Research mode (build a corpus, cross-domain history)\n"
        f"- [{site_origin}/ops]({site_origin}/ops) - Ops mode (live operational watch, focused feeds)\n"
        f"- [{site_origin}/feeds]({site_origin}/feeds) - hosted live-feed status surface under Ops\n"
        f"- [{site_origin}/agents]({site_origin}/agents) - overview for AI agents (this lane)\n"
        f"- [{site_origin}/devs]({site_origin}/devs) - developer guide: clients, API keys, payment\n"
        f"- [{site_origin}/packs]({site_origin}/packs) - public pack catalog\n"
        f"- [{site_origin}/downloadable/]({site_origin}/downloadable/) - downloads: programs, data packs, and geometry packages\n"
        f"- [{site_origin}/about]({site_origin}/about) - founder, mission, open-engine framing\n"
        "- [https://github.com/xyver/daedal-map](https://github.com/xyver/daedal-map) - open engine source (self-host path)\n\n"
        "## Recommended hierarchy\n\n"
        "- Humans and developers start at `/devs`\n"
        "- Agents reading HTML start at `/agents`\n"
        "- Bots and crawlers start at `/llms.txt`\n"
        "- MCP-capable clients should use `/mcp`\n"
        "- Direct HTTP clients should use `/api/v1/guide`, `/api/v1/catalog`, `/api/v1/packs/{pack_id}`, and `/api/v1/query/dataset`\n"
        f"- Narrow pack facades such as {_code_list(example_facade_ids(2), prefix='/mcp/', conjunction='and')} are for registry discoverability, not the main product entry point\n\n"
        "## Live endpoints\n\n"
        f"- [GET /mcp/server.json]({app_origin}/mcp/server.json)\n"
        f"- [GET /mcp]({app_origin}/mcp)\n"
        f"- [POST /mcp]({app_origin}/mcp)\n"
        f"- [GET /api/v1/guide]({app_origin}/api/v1/guide)\n"
        f"- [GET /api/v1/catalog]({app_origin}/api/v1/catalog)\n"
        f"- [GET /api/v1/packs/{{pack_id}}]({app_origin}/api/v1/packs/earthquakes)\n"
        f"- [POST /api/v1/query/dataset]({app_origin}/api/v1/query/dataset)\n\n"
        f"{coverage_section(app_origin, site_origin)}\n"
        "## Registry facades\n\n"
        f"{facade_link_bullets(app_origin)}\n\n"
        "## Geography utility tools (free)\n\n"
        "A free geographic reference and geometry family: resolve coordinates and codes, inspect loc_id identities and relationships, discover country and family coverage, retrieve boundaries, and follow published crosswalks. The administrative spine is the main join surface; other geography families retain distinct identities.\n\n"
        f"{geography_tools_section(app_origin)}\n\n"
        "### Choose the tool by question\n\n"
        f"{geography_workflow_section()}\n\n"
        "## Data tools\n\n"
        f"{data_tools_section()}\n\n"
        "## Current live contract\n\n"
        "- MCP discovery first is valid: read `server.json`, then call `tools/list`, then follow `get_catalog` -> `get_pack` -> `get_data`\n"
        "- Free discovery first: `guide`, `catalog`, and pack detail\n"
        "- `request_id` is optional but recommended for tracing and idempotency\n"
        "- Paid execution second: an unpaid request to `POST /api/v1/query/dataset` returns `402` with the exact price before any charge\n"
        "- MCP is a wrapper over the same underlying hosted discovery and paid execution lanes\n"
        "- Paid MCP calls on `/mcp` return `payment_choice_required`; pay with account credit on `/mcp/account` (`X-API-Key`)\n\n"
        "## Related docs\n\n"
        f"- [For AI agents]({site_origin}/agents)\n"
        f"- [Developer guide]({site_origin}/devs)\n"
        f"- [Agent Examples]({site_origin}/docs/agent-examples)\n"
        f"- [loc_id Guide]({site_origin}{LOC_ID_GUIDE_PATH})\n"
        f"- [Geometry Family Definitions]({site_origin}/docs/geometry-families)\n"
        f"- [Geometry Tools]({site_origin}/docs/geometry-tools)\n"
        "- [GitHub (open runtime)](https://github.com/xyver/daedal-map)\n"
    )


def render_site_llms_full(*, app_origin: str = DEFAULT_APP_ORIGIN, site_origin: str = DEFAULT_SITE_ORIGIN) -> str:
    return (
        "# DaedalMap Bot Surface\n\n"
        "This file is the expanded machine-oriented guide to the live hosted DaedalMap bot lane.\n"
        "If you are an agent or crawler, prefer this over the human marketing pages and do not start with the human app UI.\n\n"
        "## Lane split\n\n"
        "- `www.daedalmap.com` is the documentation and marketing lane\n"
        "- `app.daedalmap.com` is the human-facing runtime\n"
        f"- `{app_origin}/mcp` is the bot-facing runtime\n"
        "- bots should use the MCP server first and the direct HTTP API second\n"
        "- bots should not treat the human mapping app as the primary programmable interface\n\n"
        "## Canonical bot docs\n\n"
        f"- [For AI agents]({site_origin}/agents) - canonical public listing for agent directories, MCP clients, current packs, and first-call flow\n"
        f"- [Developer guide]({site_origin}/devs) - client setup, API keys, and payment\n"
        f"- [Agent Examples]({site_origin}/docs/agent-examples)\n"
        f"- [loc_id Guide]({site_origin}{LOC_ID_GUIDE_PATH})\n"
        f"- [Geometry Tools]({site_origin}/docs/geometry-tools)\n"
        f"- [Geometry Family Definitions]({site_origin}/docs/geometry-families)\n\n"
        "## Publishing and directory layers\n\n"
        "DaedalMap's public agent surface is organized into three discovery layers:\n\n"
        f"- Ultimate listing: `{site_origin}/agents`\n"
        f"- Machine-readable listing: `{site_origin}/llms.txt` and `{site_origin}/llms-full.txt`\n"
        f"- Umbrella MCP: `{app_origin}/mcp`\n"
        f"- Individual MCP facades: pack-specific endpoints such as `{app_origin}/mcp/{example_facade_ids(1)[0]}`\n\n"
        "Use the ultimate listing for broad directories and GitHub awesome lists. Use\n"
        "the umbrella MCP when a directory requires a direct MCP endpoint. Use the\n"
        "individual MCP facades only where pack-specific search matters, such as the\n"
        "official MCP Registry.\n\n"
        "Recommended hierarchy:\n\n"
        f"- Humans and developers start at `{site_origin}/devs`\n"
        f"- Agents reading HTML start at `{site_origin}/agents`\n"
        f"- Bots and crawlers start at `{site_origin}/llms.txt`\n"
        f"- MCP-capable clients should use `{app_origin}/mcp`\n"
        "- Direct HTTP clients should use the hosted `/api/v1/...` discovery and query endpoints\n"
        "- Pack-specific facades are for registry discoverability, not the main product entry point\n\n"
        "Suggested broad directory entry:\n\n"
        "DaedalMap Geographic Reference and Geometry - Geographic interoperability infrastructure\n"
        "for agents and researchers. Identify reference systems, transform\n"
        "coordinates and boundaries, build crosswalks, assign stable loc_id values,\n"
        "prepare your own data, discover available geography dynamically, and\n"
        f"connect compatible datasets. Start at {site_origin}/agents.\n\n"
        "## Hosted bot entry points\n\n"
        f"- `GET {app_origin}/mcp/server.json`\n"
        f"{facade_server_json_lines(app_origin)}\n"
        f"- `GET {app_origin}/api/v1/guide`\n"
        f"- `GET {app_origin}/api/v1/catalog`\n"
        f"- `GET {app_origin}/api/v1/packs/{{pack_id}}`\n"
        f"- `POST {app_origin}/api/v1/query/dataset`\n"
        f"- `GET {app_origin}/mcp`\n"
        f"- `POST {app_origin}/mcp`\n"
        f"{facade_transport_lines(app_origin)}\n\n"
        "## Complete public catalog snapshots\n\n"
        f"- Data: `{app_origin}/api/v1/catalog/download`\n"
        f"- Geometry: `{app_origin}/api/v1/geometry/catalog/download`\n"
        "- Use these bounded discovery surfaces instead of crawling the downloadable object tree.\n\n"
        f"{coverage_section(app_origin, site_origin)}\n"
        "## Geography utility tools (free)\n\n"
        "Alongside maintained data packs, DaedalMap exposes a free geographic reference and geometry family. These tools resolve coordinates and codes, inspect loc_id identities and relationships, discover published country and family coverage, retrieve boundaries and bounding boxes, and follow available crosswalks. The administrative spine is the main join surface; postal, watershed, Indigenous land, forest, and other families retain distinct identities rather than being forced onto one universal key.\n\n"
        f"{geography_tools_section(app_origin)}\n\n"
        "### Choose the tool by question\n\n"
        f"{geography_workflow_section()}\n\n"
        "## Data tools\n\n"
        f"{data_tools_section()}\n\n"
        "## Registry summary\n\n"
        "DaedalMap is a remote MCP server and hosted geographic reference, geometry, and data API for deterministic,\n"
        f"geography-aware queries across {data_pack_count_label()} curated data packs, with geometry covering a {GEOMETRY_COVERAGE_LABEL}.\n"
        "Free discovery lives at `GET /api/v1/guide`, `GET /api/v1/catalog`, and\n"
        "`GET /api/v1/packs/{pack_id}`. Execution lives at `POST /api/v1/query/dataset`.\n"
        f"{free_pack_display_csv()} are free lanes. {paid_pack_display_csv()} challenge via HTTP `402`.\n"
        "MCP is available at `/mcp` and wraps the same hosted discovery and execution lane.\n"
        "Floods and tornadoes have dedicated MCP facades alongside the other\n"
        "registry-published packs.\n\n"
        "Short bot-facing positioning:\n\n"
        "- free loc_id resolution, reference identification, geometry discovery and retrieval, and published crosswalk tools\n"
        "- remote MCP server for earthquake, tsunami, volcano, hurricane, flood, tornado, SDG, World Factbook, and development-indicator data queries\n"
        "- free discovery plus mixed free and paid structured retrieval\n"
        "- deterministic outputs over a maintained geographic reference graph and reusable geometry library\n"
        f"- the umbrella MCP is the canonical live product; pack facades such as `{pack_sentence()}` are narrow official-registry entrypoints over the same shared backend\n"
        "- Smithery remains pointed at the umbrella MCP entrypoint\n\n"
        "Suggested tags:\n\n"
        "- geographic intelligence\n"
        "- disaster intelligence\n"
        "- data API\n"
        "- MCP\n"
        "- remote MCP\n\n"
        "## Expected first flow\n\n"
        "1. Read `GET /mcp/server.json`\n"
        f"2. Call `tools/list` on `POST /mcp` or on a narrow facade such as {_code_list(example_facade_ids(), prefix='POST /mcp/')}\n"
        "3. Read `GET /api/v1/catalog`\n"
        "4. Read one pack detail from `GET /api/v1/packs/{pack_id}`\n"
        f"5. Make one free request for {_code_list(example_free_pack_ids())}\n"
        f"6. Make one unpaid request for {_code_list(example_paid_pack_ids())}\n"
        "7. Expect HTTP `402` on the paid pack\n"
        "8. Retry with a payment-aware client and expect structured rows on success\n"
        "9. `request_id` is optional but recommended for tracing and idempotency\n\n"
        "## Current access behavior\n\n"
        f"- {free_pack_display_csv()} are free lanes\n"
        f"- {paid_pack_display_csv()} are challenge-first via HTTP `402`\n"
        "- Paid calls are charged from account credit through a scoped API key; new accounts start with free credit\n"
        "- Requests above the live source maximum reject before payment instead of charging\n\n"
        "## Current proven hosted examples\n\n"
        "- Free proof:\n"
        f"  - `{example_free_pack_ids(1)[0]}`\n"
        "  - `limit = 3`\n"
        "  - returns rows directly\n"
        "- Paid minimal proof:\n"
        "  - `earthquakes`\n"
        "  - `limit = 3`\n"
        "  - challenge amount `10000` base units\n"
        "- Free max proof:\n"
        "  - `volcanoes`\n"
        "  - `limit = 500`\n"
        "  - returns rows directly\n"
        "- Paid mid-sized proof:\n"
        "  - `earthquakes`\n"
        "  - `limit = 250`\n"
        "  - challenge amount `25000` base units\n"
        "- Above-max rejection proof:\n"
        "  - `tsunamis`\n"
        "  - `limit = 501`\n"
        "  - status `400`\n"
        "  - code `result_too_large`\n"
        "  - no payment challenge\n\n"
        "## MCP note\n\n"
        "The MCP endpoint is not a separate data product.\n"
        "It wraps the same discovery and paid execution lanes, with the same flagship packs, limits, and payment behavior.\n"
        f"If a client supports remote MCP, use `{app_origin}/mcp` as the first choice.\n"
        "If not, use the hosted HTTP API lane directly.\n"
        f"For official-registry discoverability, narrow facades such as {_code_list(example_facade_ids(), prefix=app_origin + '/mcp/', conjunction='and')} can be listed as pack-specific entrypoints without changing the runtime architecture.\n\n"
        "## Supported clients\n\n"
        "Document directly:\n\n"
        "- Claude Code\n"
        "- Codex\n"
        "- ChatGPT developer mode\n"
        "- Gemini SDKs\n"
        "- Mistral SDK workflows\n\n"
        "Treat as runtime-dependent rather than model-specific:\n\n"
        "- Qwen\n"
        "- DeepSeek\n"
        "- Gemma\n"
        "- Llama\n\n"
        "For those local or open-weight model families, the important question is whether the host runtime can connect to a remote MCP server.\n"
        f"If yes, use `{app_origin}/mcp`.\n"
        "If not, use the hosted HTTP API lane directly.\n\n"
        "## Geography note\n\n"
        "Read the `loc_id` guide before assuming region filters behave the same across all packs.\n"
        "Country ids and hierarchical geography are common, but tsunami examples may also use reviewed named-water loc_ids such as `IHO1953-240001002` for the Mediterranean Sea; `XOO` is deprecated.\n\n"
        "## Human-facing pages\n\n"
        "DaedalMap is geographic reference infrastructure built from durable loc_id identities, reusable geometry, published crosswalks, and maintained data. The human pages are access surfaces over that foundation; they are not four separate products.\n\n"
        f"- [{site_origin}/]({site_origin}/) - product overview and conversion entrance.\n"
        f"- [{site_origin}/geometry]({site_origin}/geometry) - published country geometry, families, representations, sources, QA, and downloads.\n"
        f"- [{site_origin}/explore]({site_origin}/explore) - Explore mode. Demo entry for an undecided visitor. No account required. Primary action: open the hosted app and ask a question. Audience: basic map explorers, undecided visitors.\n"
        f"- [{site_origin}/research]({site_origin}/research) - Research mode. Bounded analytical workspace pitch. Primary action: build a corpus. Audience: academics, researchers, lab teams. Carries the \"every pack joins on loc_id\" credibility moment and the preserved-data section.\n"
        f"- [{site_origin}/ops]({site_origin}/ops) - Ops mode. Live operational watch. Primary action: choose your feeds. Audience: emergency-management teams, partners, operational buyers.\n"
        f"- [{site_origin}/feeds]({site_origin}/feeds) - Hosted status surface listing active live feeds, source agencies, cadence, and matching pack links. This is part of the private hosted control plane, not the self-host runtime tree.\n"
        f"- [{site_origin}/agents]({site_origin}/agents) - Overview for AI agents: capabilities, endpoints, tools, and minimal calls.\n"
        f"- [{site_origin}/devs]({site_origin}/devs) - Developer guide: connect a client, API keys, payment, HTTP API. Audience: developers, MCP/agent builders.\n"
        f"- [{site_origin}/packs]({site_origin}/packs) - Public pack catalog.\n"
        f"- [{site_origin}/about]({site_origin}/about) - Founder, mission, open-engine framing.\n"
        f"- [{site_origin}/docs]({site_origin}/docs) - Docs index.\n"
        f"- [{site_origin}/pricing]({site_origin}/pricing) - Pricing.\n"
        f"- [{app_origin}]({app_origin}) - Hosted app (Explore mode default surface).\n"
        "- [https://github.com/xyver/daedal-map](https://github.com/xyver/daedal-map) - Open engine source (self-host path, contributor pipeline).\n"
    )


AI_CRAWLER_USER_AGENTS: tuple[str, ...] = (
    "GPTBot",
    "OAI-SearchBot",
    "ClaudeBot",
    "Claude-SearchBot",
    "PerplexityBot",
    "Googlebot",
    "Google-Extended",
    "Bingbot",
    "Applebot-Extended",
    "Amazonbot",
    "meta-externalagent",
    "CCBot",
)


def render_robots_txt(*, sitemap_url: str | None = None, llms_url: str | None = None) -> str:
    """robots.txt for every DaedalMap host: allow all crawlers and name the sitemap.

    The explicit Allow groups document the AI and search crawlers we want; the
    wildcard group already allows them. llms.txt is not a robots.txt directive,
    so it is named only in a comment.
    """
    lines = ["User-agent: *", "Allow: /", ""]
    for agent in AI_CRAWLER_USER_AGENTS:
        lines += [f"User-agent: {agent}", "Allow: /", ""]
    if sitemap_url:
        lines += [f"Sitemap: {sitemap_url}", ""]
    if llms_url:
        lines += ["# LLM guide (llms.txt convention; not a robots.txt directive):", f"# {llms_url}", ""]
    return "\n".join(lines)


def render_security_txt(*, canonical_url: str, site_origin: str = DEFAULT_SITE_ORIGIN, now: datetime | None = None) -> str:
    """RFC 9116 security.txt. Expires is always 180 days ahead, so it never lapses."""
    current = now or datetime.now(timezone.utc)
    expires = (current + timedelta(days=180)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        f"Contact: mailto:{CONTACT_EMAIL}\n"
        f"Contact: {site_origin}/support\n"
        f"Expires: {expires.strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
        "Preferred-Languages: en\n"
        f"Canonical: {canonical_url}\n"
        f"Policy: {site_origin}/terms\n"
    )
