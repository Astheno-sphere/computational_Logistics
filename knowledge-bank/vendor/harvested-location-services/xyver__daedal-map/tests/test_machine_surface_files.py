"""Guards for the generated machine-facing files (llms, robots.txt, security.txt).

These files are rendered from the pack registry at request time. The tests fail
if hand-written content creeps back in: apex links that redirect, facades or
packs that are no longer published, or a security.txt that can expire.
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent_surface_shared as surface
from pack_registry_shared import tool_family_alias_ids, tool_family_ids

RENDERED = {
    "app_llms": surface.render_app_llms_txt(),
    "site_llms": surface.render_site_llms_txt(),
    "site_llms_full": surface.render_site_llms_full(),
}


def test_machine_files_never_link_the_redirecting_apex_host():
    for name, text in RENDERED.items():
        assert not re.search(r"https?://daedalmap\.com", text), name


def test_named_mcp_facades_are_currently_published():
    allowed = set(surface.facade_pack_ids()) | set(tool_family_ids()) | set(tool_family_alias_ids()) | {"account", "x402"}
    for name, text in RENDERED.items():
        for segment in re.findall(r"/mcp/([a-z0-9_.-]+)", text):
            if segment == "server.json":
                continue
            assert segment in allowed, (name, segment)


def test_pack_count_comes_from_the_registry():
    for name, text in RENDERED.items():
        assert "20+" not in text, name
    assert surface.data_pack_count_label() == str(len(surface.current_pack_ids()))


def test_loc_id_guide_uses_the_canonical_path():
    for name, text in RENDERED.items():
        assert "/docs/loc-id" not in text, name


def test_robots_allows_crawlers_and_names_the_sitemap():
    robots = surface.render_robots_txt(sitemap_url="https://www.daedalmap.com/sitemap.xml", llms_url="https://www.daedalmap.com/llms.txt")
    assert robots.startswith("User-agent: *\nAllow: /\n")
    assert "Disallow" not in robots
    assert "Sitemap: https://www.daedalmap.com/sitemap.xml" in robots
    assert "LLMs-txt:" not in robots
    for line in robots.splitlines():
        assert not line or line.startswith(("User-agent:", "Allow:", "Sitemap:", "#")), line


def test_security_txt_expires_within_a_year_and_points_at_support():
    now = datetime(2026, 10, 1, tzinfo=timezone.utc)
    text = surface.render_security_txt(canonical_url="https://www.daedalmap.com/.well-known/security.txt", now=now)
    expires = datetime.strptime(re.search(r"Expires: (\S+)", text).group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert now < expires and (expires - now).days < 365
    assert "Contact: https://www.daedalmap.com/support" in text
    assert "Contact: mailto:" in text


def test_catalog_provider_drives_pack_lists_and_registry_is_fallback():
    try:
        surface.set_pack_id_provider(lambda: ["floods", "earthquakes", "not_in_registry"])
        assert surface.current_pack_ids() == ("floods", "earthquakes", "not_in_registry")
        assert surface.facade_pack_ids() == ("floods", "earthquakes")
        assert surface.data_pack_count_label() == "3"
        assert "/mcp/not_in_registry" not in surface.render_site_llms_full()
        surface.set_pack_id_provider(lambda: [])
        assert surface.current_pack_ids() == surface.CURRENT_HOSTED_PACK_IDS
    finally:
        surface.set_pack_id_provider(None)
