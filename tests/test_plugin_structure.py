import json

from conftest import ROOT
from kb_assemble import frontmatter


def test_every_skill_has_valid_frontmatter_named_like_its_folder():
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert len(skills) >= 4
    for s in skills:
        fm, err = frontmatter(s.read_text())
        assert err is None, s
        assert fm["name"] == s.parent.name, s
        assert len(fm["description"]) > 60, s


def test_agents_have_name_description_tools():
    for a in (ROOT / "agents").glob("*.md"):
        fm, err = frontmatter(a.read_text())
        assert err is None and fm["name"] == a.stem and fm["description"] and fm["tools"], a


def test_router_points_only_at_existing_skills():
    text = (ROOT / "skills/cl-foundations/SKILL.md").read_text()
    for name in ("osm-network", "vrp-solve", "gh-datatree", "opt-model", "dcm-estimate", "abm-transport", "dmdu-explore",
                 "visual-narrative"):
        assert "`%s`" % name in text and (ROOT / "skills" / name / "SKILL.md").exists()


def test_plugin_manifest():
    m = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert m["name"] == "asthenosphere" and m["version"]
