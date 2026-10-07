"""The front door has to lead everywhere, and say only true things.

The benchmark results were public for a day and nobody could find them: no
link from the README. Writing something and publishing something are not the
same act, and the difference is invisible to every other test in this suite.
These checks are mechanical on purpose — taste cannot be automated, but
reachability, dead links and stale numbers can.
"""

import asyncio
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
SITE_TEMPLATE = ROOT / "site" / "index.template.html"
SITE_BUILD = ROOT / "site" / "build.py"
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")

# Root pages a visitor is expected to find from the front door. CLAUDE.md is
# deliberately not here: it is a contributor guide for AI assistants, which
# clients read by convention, not a page we ask a human to navigate to.
ROOT_PAGES_NOT_LINKED_ON_PURPOSE = {"README.md", "CLAUDE.md"}


def _showcase_pages() -> list[Path]:
    """Every markdown page the showcase is made of, wherever it lives."""
    pages = [README, *sorted(ROOT.glob("*.md")), *sorted((ROOT / "docs").glob("*.md"))]
    pages += [ROOT / "examples" / "README.md", ROOT / "benchmarks" / "gabench-ab" / "README.md"]
    seen: dict[Path, None] = {}
    for page in pages:
        if page.exists():
            seen.setdefault(page.resolve(), None)
    return list(seen)


def _links(markdown: Path) -> set[str]:
    return {m.group(1) for m in LINK.finditer(markdown.read_text(encoding="utf-8"))}


def _local_links(markdown: Path) -> set[str]:
    return {t for t in _links(markdown) if not t.startswith(("http://", "https://", "mailto:"))}


def _reachable_from_readme() -> set[Path]:
    """Files linked by the README, plus files linked by those (two clicks)."""
    seen: set[Path] = set()
    frontier = [README]
    for _ in range(2):
        nxt = []
        for page in frontier:
            for target in _local_links(page):
                resolved = (page.parent / target).resolve()
                if not resolved.exists():
                    continue
                # linking a directory reaches its README: that is the page
                # GitHub renders for it
                if resolved.is_dir() and (resolved / "README.md").exists():
                    resolved = (resolved / "README.md").resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    if resolved.suffix == ".md":
                        nxt.append(resolved)
        frontier = nxt
    return seen


@pytest.mark.parametrize(
    "page", _showcase_pages(), ids=lambda p: str(p.relative_to(ROOT)).replace("\\", "/")
)
def test_every_local_link_resolves(page):
    """A broken relative link is a 404 for every visitor."""
    missing = [t for t in _local_links(page) if not (page.parent / t).exists()]
    assert not missing, f"{page.name} links to files that do not exist: {missing}"


def test_every_docs_page_is_reachable_from_the_readme():
    """Publishing a page nobody can navigate to is not publishing it."""
    reachable = _reachable_from_readme()
    orphans = [
        p.name for p in sorted((ROOT / "docs").glob("*.md")) if p.resolve() not in reachable
    ]
    assert not orphans, (
        f"docs pages unreachable from the README within two clicks: {orphans}. "
        "Link them, or they do not exist as far as a visitor is concerned."
    )


def test_every_root_page_is_reachable_from_the_readme():
    """SECURITY.md sat unlinked for two releases: GitHub renders a tab for it,
    so nobody noticed the README never pointed at the one page that documents
    what MapSmith does *not* protect."""
    reachable = _reachable_from_readme()
    orphans = [
        p.name
        for p in sorted(ROOT.glob("*.md"))
        if p.name not in ROOT_PAGES_NOT_LINKED_ON_PURPOSE and p.resolve() not in reachable
    ]
    assert not orphans, (
        f"root pages unreachable from the README within two clicks: {orphans}. "
        "Link them, or accept that visitors will never read them."
    )


def test_every_readme_anchor_points_at_a_heading():
    """In-page links are how the first screen reaches the proof further down;
    renaming a heading silently turns them into scroll-to-nowhere."""
    text = README.read_text(encoding="utf-8")
    slugs = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\s-]", "", heading.lower()).strip()
        slugs.add(re.sub(r"\s+", "-", slug))
    anchors = set(re.findall(r"\]\(#([^)\s]+)\)", text))
    assert anchors <= slugs, f"README anchors with no matching heading: {sorted(anchors - slugs)}"


def test_the_notebook_gallery_is_reachable():
    reachable = _reachable_from_readme()
    notebooks = sorted((ROOT / "examples").glob("*.ipynb"))
    assert notebooks, "the gallery lost its notebooks"
    # the gallery README counts as the entry point for the notebooks
    gallery = (ROOT / "examples" / "README.md").resolve()
    assert gallery in reachable, "the notebook gallery is not linked from the README"
    linked = _local_links(ROOT / "examples" / "README.md")
    unlinked = [n.name for n in notebooks if n.name not in linked]
    assert not unlinked, f"notebooks missing from the gallery index: {unlinked}"


def test_the_readme_tool_table_matches_the_registered_tools():
    """A tool table that drifts turns the front page into documentation of a
    product that no longer exists."""
    from mapsmith import server

    registered = {t.name for t in server.mcp._tool_manager.list_tools()}
    # The table under `## Tools`, and not every table on the page whose first
    # cell is a backticked identifier. That looser reading held while there was
    # only one such table; the first other one -- a two-column table of
    # georeferencing fields, generated from a run -- was read as three tools
    # that had been removed. A guard that fires on a page being *extended* is a
    # guard somebody edits the page to appease.
    page = README.read_text(encoding="utf-8")
    start = page.index("\n## Tools\n")
    section = page[start:].split("\n## ", 2)[1]
    documented = set(re.findall(r"^\| `([a-z_]+)` \|", section, re.MULTILINE))
    assert documented, (
        "no tool table found under `## Tools`, so this compares an empty set "
        "with the registered tools and passes on a page that lost its table"
    )
    assert registered == documented, (
        f"missing from the README: {sorted(registered - documented)}; "
        f"documented but gone: {sorted(documented - registered)}"
    )


def test_the_readme_tool_count_matches_the_registered_tools():
    """"16 goal-level tools" is a number, and numbers rot. The claim appears
    twice (the pitch and the limitations), so both have to move together."""
    from mapsmith import server

    registered = len(server.mcp._tool_manager.list_tools())
    text = README.read_text(encoding="utf-8")
    counted = {int(n) for n in re.findall(r"\b(\d+)\s+(?:goal-level\s+)?tools\b", text)}
    wrong = {n for n in counted if n != registered}
    assert not wrong, (
        f"the README claims {sorted(wrong)} tools but {registered} are registered"
    )


def test_the_roadmap_does_not_list_a_shipped_tool_as_future_work():
    """A roadmap that promises what already runs makes the rest look sloppy."""
    from mapsmith import server

    registered = {t.name for t in server.mcp._tool_manager.list_tools()}
    todo = re.findall(r"^- \[ \] (.+)$", README.read_text(encoding="utf-8"), re.MULTILINE)
    shipped_but_promised = {
        name for name in registered for item in todo if re.search(rf"\b{name}\b", item)
    }
    assert not shipped_but_promised, (
        f"the roadmap lists shipped tools as future work: {sorted(shipped_but_promised)}. "
        "Tick the box, or say precisely which part is still missing."
    )


def test_the_changelog_covers_the_released_version():
    """A release with no entry means the visitor cannot tell what changed —
    and the version in pyproject is what PyPI will publish, so they must agree."""
    from mapsmith import __version__

    # regex, not tomllib: a substring check over the raw text stays true however
    # the dependency is expressed — extra, marker or version pin
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert declared and declared.group(1) == __version__, (
        f"pyproject says {declared.group(1) if declared else '?'}, "
        f"the package says {__version__}"
    )
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[{re.escape(__version__)}\]", changelog, re.MULTILINE), (
        f"CHANGELOG.md has no section for the current version {__version__}"
    )


def test_the_glama_manifest_parses_and_names_the_owner():
    """`glama.json` is read by a third party, and its own documentation lists
    "syntax errors" as the usual reason a claim fails. Nothing else in this repo
    would notice: it is not imported, not packaged and not executed, so a stray
    comma would sit there being silently ignored by the one reader it has."""
    manifest = ROOT / "glama.json"
    assert manifest.exists(), "glama.json is a listed quality-checklist item"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["$schema"] == "https://glama.ai/mcp/schemas/server.json"
    assert data["maintainers"] == ["mapsmith-ai"], (
        "the maintainer is the GitHub account that owns the listing; any other "
        "name here fails the claim without saying why"
    )


#: The paths whose changes reach someone who installs the release. The two
#: guards below compare the README and the changelog with the difference
#: between the tag and HEAD in THESE paths, because that is the difference the
#: README promises to name: "a tool that is not there", not a test that moved.
SHIPPED = ("src", "pyproject.toml", "server.json")


def test_work_since_the_last_tag_is_announced_under_unreleased():
    """`main` ahead of the last tag with nothing under `[Unreleased]` is a
    changelog that says the project has stopped.

    On 2026-09-02 there were eleven commits and 4371 insertions past v0.4.0 and
    the file went straight from its header to `## [0.4.0]`. Among the things it
    did not mention: a dataset written to disk with no manifest beside it —
    invariant 2, in shipped code. `CHANGELOG.md` declares that it follows Keep a
    Changelog, which prescribes the section; of the four public surfaces it was
    the only one still describing the last release as the present.

    This is not a one-off. Every release empties the section and every commit
    after it refills it, so the gap reopens on a schedule.
    """
    tag = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if tag.returncode != 0:
        pytest.skip("no version tag reachable from HEAD (shallow clone?)")
    ahead = subprocess.run(
        # What an installer gets, not every commit (2026-09-26): a commit to the
        # site build or a test changes nothing in the package, and counting it
        # made the page announce a difference the release does not have.
        ["git", "rev-list", "--count", f"{tag.stdout.strip()}..HEAD", "--", *SHIPPED],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if ahead.returncode != 0:
        pytest.skip("cannot count commits since the tag")
    if int(ahead.stdout.strip()) == 0:
        return  # freshly tagged: an empty Unreleased is the correct state

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.search(r"^## \[Unreleased\]", changelog, re.MULTILINE)
    assert heading, (
        f"{ahead.stdout.strip()} commits since {tag.stdout.strip()} and "
        f"CHANGELOG.md has no [Unreleased] section"
    )
    # The section must carry entries, not just exist: an empty heading passes a
    # presence check while saying exactly as little as no heading at all.
    #
    # Unless the work has already been moved into the section for the version
    # in the tree, which is the state on the eve of a tag: the block is dated,
    # `[Unreleased]` is legitimately empty, and the tag that would make this
    # check skip does not exist yet. Without this, the release procedure has a
    # step that cannot be performed with the suite green, and a check nobody
    # can satisfy is a check that gets bypassed.
    body = changelog[heading.end():].split("\n## ", 1)[0]
    entries = [ln for ln in body.splitlines() if ln.startswith("- ")]
    from mapsmith import __version__ as in_tree

    dated = re.search(rf"^## \[{re.escape(in_tree)}\]", changelog, re.MULTILINE)
    # Only on the eve of the tag. Once `v{in_tree}` exists, its block is the
    # released one, and counting its entries made this check unable to fail on
    # any commit after a release -- the state it exists to catch (2026-09-26).
    tagged = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/v{in_tree}"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).returncode == 0
    if dated and not tagged:
        released = changelog[dated.end():].split("\n## ", 1)[0]
        entries += [ln for ln in released.splitlines() if ln.startswith("- ")]
    assert entries, (
        f"{ahead.stdout.strip()} commits since {tag.stdout.strip()} and neither "
        f"[Unreleased] nor [{in_tree}] has entries"
    )


def test_server_json_declares_the_version_being_released():
    """The registry entry carries the version in three places — the server, the
    PyPI package and the OCI tag — and a release bumps them by hand. One left
    behind publishes a listing that points at the previous image."""
    import json

    from mapsmith import __version__

    data = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert data["version"] == __version__, (
        f"server.json says {data['version']}, the package says {__version__}"
    )
    for package in data["packages"]:
        if package["registryType"] == "pypi":
            assert package["version"] == __version__, (
                f"server.json pypi package pinned at {package['version']}"
            )
        if package["registryType"] == "oci":
            assert package["identifier"].endswith(f":{__version__}"), (
                f"server.json OCI tag is {package['identifier']}, not :{__version__}"
            )


def test_the_citation_file_matches_the_released_version():
    """Zenodo mints a DOI from this file on every GitHub release, and whatever it
    says at that instant is archived permanently. A stale version here does not
    fail a build or bother a user: it produces a citation that names the wrong
    software, in a record that cannot be edited away."""
    import datetime as dt

    from mapsmith import __version__

    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

    declared = re.search(r'^version:\s*"([^"]+)"', citation, re.MULTILINE)
    assert declared, "CITATION.cff has no version"
    assert declared.group(1) == __version__, (
        f"CITATION.cff says {declared.group(1)}, the package says {__version__}. "
        f"A release archives this file as it stands."
    )

    released = re.search(r'^date-released:\s*"(\d{4}-\d{2}-\d{2})"', citation, re.MULTILINE)
    assert released, "CITATION.cff has no date-released"
    assert dt.date.fromisoformat(released.group(1)) <= dt.datetime.now(tz=dt.UTC).date(), (
        f"CITATION.cff claims a release on {released.group(1)}, which has not happened. "
        f"The date is written by hand before tagging, and a slipped tag leaves it false."
    )

    assert "mapsmith-ai/MapSmith" in citation, "repository-code does not point at this repository"


def test_the_archive_metadata_uses_a_licence_identifier_zenodo_resolves():
    """SPDX and Zenodo disagree about case, and nothing warns you.

    CFF requires SPDX identifiers, written `AGPL-3.0-or-later`. Zenodo's licence
    vocabulary is keyed lowercase and returns 404 on anything else, so citation
    metadata that is correct by its own standard names a licence the archive
    cannot resolve, and the release is archived without it.

    That is why this file exists rather than letting CITATION.cff speak for
    itself. Its sibling repositories learned the same thing twice: a list of
    licences where one string was required, then a capital letter.
    """
    import json

    metadata = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    licence = metadata.get("license")

    assert isinstance(licence, str), (
        f"license must be a single string, got {type(licence).__name__}: {licence!r}"
    )
    assert licence == licence.lower(), (
        f"Zenodo's licence identifiers are lowercase and it 404s on anything "
        f"else; {licence!r} would not resolve"
    )


def test_the_archive_metadata_does_not_contradict_the_rest_of_the_release():
    """Zenodo ignores CITATION.cff entirely when .zenodo.json is present, so the
    two carry the same facts twice and nothing at release time notices them
    drifting. This is the cost of the fix above, paid here."""
    import json

    from mapsmith import __version__

    metadata = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

    assert metadata["version"] == __version__, (
        f".zenodo.json archives {metadata['version']} while the package is "
        f"{__version__}. Zenodo reads this file from inside the tag, so a "
        f"release cannot correct it afterwards."
    )
    title = re.search(r'^title:\s*"(.+)"', citation, re.MULTILINE)
    assert title and metadata["title"] == title.group(1), (
        f".zenodo.json titles the record {metadata['title']!r}; CITATION.cff "
        f"says {title.group(1) if title else None!r}"
    )
    for creator in (c["name"] for c in metadata["creators"]):
        assert creator in citation, (
            f".zenodo.json credits {creator!r}, absent from CITATION.cff"
        )


def test_the_registry_ownership_proof_is_in_every_place_it_is_read_from():
    """The MCP Registry proves ownership by matching one string in three
    artifacts: the README marker it reads from the repository, the Dockerfile
    label it reads from the image, and server.json itself. Any of them missing
    or drifting fails publication — at release time, which is the most
    expensive moment to find out."""
    import json

    name = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))["name"]
    readme = README.read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {name} -->" in readme, (
        f"the README has no '<!-- mcp-name: {name} -->' marker"
    )
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert f'LABEL io.modelcontextprotocol.server.name="{name}"' in dockerfile, (
        f"the Dockerfile does not label the image with {name}"
    )


def test_the_pypi_page_has_no_relative_link():
    """PyPI renders the README with nothing to resolve a relative link against,
    so every `](docs/...)` and every screenshot was a 404 on pypi.org until
    2026-09-26. The build rewrites them to GitHub URLs pinned to the release tag
    (pyproject.toml, hatch-fancy-pypi-readme). This applies the configured
    substitutions the way the hook does -- Python `re`, in order, the version
    interpolated afterwards -- and fails on any target still relative, or
    rewritten to a file the tag would not have."""
    import tomllib

    from mapsmith import __version__

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "readme" in metadata["project"].get("dynamic", []), (
        "the readme is static again, so the build ships the relative links as they are"
    )
    hook = metadata["tool"]["hatch"]["metadata"]["hooks"]["fancy-pypi-readme"]
    assert [f.get("path") for f in hook["fragments"]] == ["README.md"], (
        "the PyPI description is no longer exactly the README; this test reads the wrong text"
    )
    text = README.read_text(encoding="utf-8")
    for rule in hook["substitutions"]:
        text = re.sub(rule["pattern"], rule["replacement"], text)
    text = text.replace("$HFPR_VERSION", __version__)

    targets = re.findall(r"\]\(([^)\s]+)\)", text)
    relative = [t for t in targets if not re.match(r"https?://|mailto:|#", t)]
    assert not relative, f"these links are still relative on pypi.org: {relative}"

    pinned = re.compile(
        r"https://(?:raw\.githubusercontent\.com/mapsmith-ai/MapSmith/"
        r"|github\.com/mapsmith-ai/MapSmith/(?:blob|tree)/)v"
        + re.escape(__version__)
        + r"/([^#)]*)"
    )
    rewritten = [m.group(1) for t in targets if (m := pinned.match(t))]
    assert rewritten, "no link was rewritten to the tag, so the substitutions matched nothing"
    missing = sorted({p for p in rewritten if not (ROOT / p).exists()})
    assert not missing, f"rewritten to paths the repository does not have: {missing}"
    assert "<!-- mcp-name: " in text, "the rewrite dropped the Registry ownership marker"


def test_the_funding_manifest_is_valid_and_findable_by_a_human():
    """funding.json is a content category of its own, and the failure mode is
    the familiar one: a crawler finds it at the root, a visitor never does. It
    is also a page of claims — keep it parseable and keep it linked."""
    import json

    manifest = ROOT / "funding.json"
    assert manifest.exists(), "funding.json is gone"
    data = json.loads(manifest.read_text(encoding="utf-8"))  # invalid JSON = invisible
    assert data.get("projects"), "funding.json declares no project"
    assert "funding.json" in README.read_text(encoding="utf-8"), (
        "funding.json is mentioned nowhere a visitor reads: link it from the README"
    )


def test_the_word_gis_survives_where_a_search_can_see_it():
    """MapSmith was absent from every curated list of GIS MCP servers while its
    package description, its registry entry and its first line all said
    "geoprocessing" and never "GIS" — which is the word people search for. A
    rewrite that drops it again should fail here, not in six months of silence."""
    import json

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    description = re.search(r'^description\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert description and "GIS" in description.group(1), (
        "the PyPI description does not contain the word GIS"
    )
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))["description"]
    assert "GIS" in registry, "the MCP Registry description does not contain the word GIS"
    first_screen = README.read_text(encoding="utf-8").split("## Quickstart")[0]
    assert "GIS" in first_screen, "the README says what it is without ever saying GIS"

    # The site is the other front door and this test never looked at it, which
    # is how the h1 and the <title> spent their whole life saying "geoprocessing"
    # and never "GIS" while the assertions above were green. A search engine
    # weights those two strings above everything else on the page.
    template = SITE_TEMPLATE.read_text(encoding="utf-8")
    for label, pattern in (
        ("<title>", r"<title>(.*?)</title>"),
        ("og:title", r'<meta property="og:title" content="(.*?)">'),
        ("<h1>", r"<h1>(.*?)</h1>"),
        ("meta description", r'<meta name="description" content="(.*?)">'),
    ):
        found = re.search(pattern, template, re.DOTALL)
        assert found, f"the site template has no {label}"
        assert "GIS" in found.group(1), (
            f"the site {label} says what MapSmith is without ever saying GIS: "
            f"{found.group(1)!r}"
        )


# The one-line description of MapSmith is copied onto nine surfaces, and until
# 2026-09-11 nothing compared them. It was reworded on five of them by hand;
# whether the other four had been missed or left behind deliberately was not
# recorded anywhere, which is the same state as having forgotten.
RETIRED_DESCRIPTION = re.compile(r"for AI agents|gives (AI agents|an AI agent)|to AI agents", re.IGNORECASE
)

# The regex above matches a PHRASE, and on 2026-09-12 an adversarial read found
# what that costs: it was green while `funding.json` advertised the project as a
# suite "for geospatial AI" and tagged it `ai-agents`, and while `pyproject.toml`
# carried the same keyword. Those are the machine-readable fields a directory,
# an aggregator or a reviewer reads FIRST, and no wording of the tagline reaches
# them. A guard that can only see one sentence is a guard that cannot fail on
# the surface that matters most.
#
# So the concept is checked in two more places, in the two shapes it actually
# takes: as a label in a classifier list, and as a positioning phrase that names
# AI as the subject rather than the caller.
RETIRED_LABELS = {"ai-agents", "ai-agent", "llm-tools", "llm", "ai", "agents", "genai"}
RETIRED_POSITIONING = re.compile(
    r"geospatial AI|AI[- ]native|AI for GIS|GIS for AI|AI-powered", re.IGNORECASE
)


def _classifier_lists() -> dict[str, list[str]]:
    """Every machine-readable list of labels this project publishes about itself.

    Derived, not enumerated: if a future `funding.json` grows a second project
    entry it is picked up, and if the keys are renamed upstream this raises
    instead of quietly checking nothing."""
    import json
    import tomllib

    lists: dict[str, list[str]] = {}
    funding = json.loads((ROOT / "funding.json").read_text(encoding="utf-8"))
    projects = funding["projects"]
    assert projects, "funding.json declares no project, so its tags cannot be checked"
    for project in projects:
        lists[f"funding.json:{project['guid']}:tags"] = project["tags"]
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lists["pyproject.toml:keywords"] = metadata["project"]["keywords"]
    lists["pyproject.toml:classifiers"] = metadata["project"]["classifiers"]
    return lists


def test_the_labels_we_publish_do_not_say_the_subject_is_AI():
    """A tagline is prose and a tag is a filter, and only one of them decides
    which list a project turns up in. Both were saying the same retired thing
    until the prose was fixed alone."""
    lists = _classifier_lists()
    # Anti-vacuity on what the check must SEE, never on what it must find: if
    # the derivation stops reaching the lists -- a renamed key, a restructured
    # funding.json -- this fails rather than passing over an empty set.
    for expected in ("funding.json:mapsmith:tags", "pyproject.toml:keywords"):
        assert expected in lists, (
            f"{expected} is no longer reachable, so this guard is checking a subset "
            f"of what it was written to check: {sorted(lists)}"
        )
    for where, labels in lists.items():
        assert labels, f"{where} is empty, so checking it proves nothing"
        hits = sorted({label for label in labels if label.strip().lower() in RETIRED_LABELS})
        assert not hits, (
            f"{where} still classifies MapSmith under {hits}. The tagline stopped "
            f"saying the subject is AI; a label is read by more tools than the "
            f"tagline is read by people."
        )


def test_no_front_door_surface_positions_the_project_as_AI():
    """The retired phrase has synonyms, and one of them was live on the funding
    page under a different shape: a plan named 'A correctness suite for
    geospatial AI'. Same claim, no match for the phrase regex."""
    surfaces = {
        "README.md": README.read_text(encoding="utf-8"),
        "funding.json": (ROOT / "funding.json").read_text(encoding="utf-8"),
        "pyproject.toml": (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        "server.json": (ROOT / "server.json").read_text(encoding="utf-8"),
        "site/index.template.html": SITE_TEMPLATE.read_text(encoding="utf-8").split(
            "<section", 1
        )[0],
    }
    for name, text in surfaces.items():
        found = RETIRED_POSITIONING.search(text)
        assert not found, (
            f"{name} positions the project as {found.group(0)!r}. What is being "
            f"described is geospatial computation; AI is who calls it."
        )

# The ratchet is spent, and on 2026-09-13 it was dissolved rather than left
# empty. It held four surfaces that still carried the retired wording, each for
# a reason about publication mechanics: two titles inside records archived under
# a DOI, and two strings that only reach a reader on the next PyPI release or
# MCP Registry publish. All four are reworded now, and the reasons were about
# WHEN the change takes effect, never about whether to make it.
#
# An empty ratchet is a dictionary a loop walks in zero iterations, which is the
# guard that cannot fail -- this file has caught that shape twice. So the four
# join the surfaces that are checked outright, below, and the deferred ones are
# the deferred ones no longer.


def test_the_one_line_description_does_not_say_two_different_things():
    """MapSmith describes itself in one line on nine surfaces, and a reader
    meets several of them in a row: the README tagline, then the package
    summary on PyPI, then the title of the thing they are about to cite. They
    were reworded five at a time by hand, which is how the tenth gets missed.

    All nine are checked outright since 2026-09-13. Until then four were held in
    a ratchet, deferred for reasons about when a change reaches a reader; the
    note above the regex says what became of it."""
    import json

    head = SITE_TEMPLATE.read_text(encoding="utf-8").split("<section", 1)[0]
    current = {
        "README.md": README.read_text(encoding="utf-8"),
        "src/mapsmith/__init__.py": (ROOT / "src" / "mapsmith" / "__init__.py").read_text(
            encoding="utf-8"
        ),
        "site/index.template.html": head,
        "CLAUDE.md": (ROOT / "CLAUDE.md").read_text(encoding="utf-8"),
        "funding.json": (ROOT / "funding.json").read_text(encoding="utf-8"),
        # The four that used to be deferred. See the note above the regex.
        "CITATION.cff": (ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        ".zenodo.json": (ROOT / ".zenodo.json").read_text(encoding="utf-8"),
        "pyproject.toml": (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        "server.json": (ROOT / "server.json").read_text(encoding="utf-8"),
    }
    # Anti-vacuity on what the check must SEE. The first version of this counted
    # the entries, and a deliberate sabotage walked straight past it: swapping
    # `CITATION.cff` for a placeholder holding an empty string kept the count at
    # nine and matched nothing, so the guard reported success while no longer
    # reading one of the files it exists to read. Naming them is the fix, and
    # every one is read from disk right above -- a name here with no file behind
    # it raises rather than passes.
    assert set(current) == {
        "README.md",
        "src/mapsmith/__init__.py",
        "site/index.template.html",
        "CLAUDE.md",
        "funding.json",
        "CITATION.cff",
        ".zenodo.json",
        "pyproject.toml",
        "server.json",
    }, f"this guard is no longer walking the nine published surfaces: {sorted(current)}"
    for name, text in current.items():
        assert text.strip(), (
            f"{name} was read as empty, so searching it proves nothing about "
            f"what that surface says"
        )
    for name, text in current.items():
        found = RETIRED_DESCRIPTION.search(text)
        assert not found, (
            f"{name} still describes MapSmith as being {found.group(0)!r}, which the "
            f"other front-door surfaces stopped saying. The subject of the sentence "
            f"is the geoprocessing, not whoever is calling it."
        )

    # The two archived titles are held equal to each other by
    # test_the_archive_metadata_does_not_contradict_the_rest_of_the_release.
    # Nothing holds them equal to the README, on purpose: a DOI'd title is a
    # citation for a release that has already shipped, and it is allowed to
    # differ from a README that has moved on. What it is NOT allowed to do is
    # keep saying something the project has retired -- that is the loop above,
    # which since 2026-09-13 covers these two as well.
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    archived = re.search(r'^title:\s*"(.+)"', citation, re.MULTILINE)
    assert archived, "CITATION.cff has no title to compare"
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))["description"]
    assert "provenance" in archived.group(1) and "provenance" in registry, (
        "a description may age, but every one of them has to name the thing that "
        "makes MapSmith different"
    )


# --------------------------------------------------------------------------
# mapsmith.dev. The site is the other front door, and until 2026-08-25 no test
# looked at it: the workflow checked that no placeholder survived the build and
# nothing checked what the page said. A generated page drifts exactly like a
# README, and worse, because the repository still reads correctly while it does.
# --------------------------------------------------------------------------


def test_the_site_names_only_tools_that_exist():
    """A name on the published page outlives the thing it describes.

    Checked against tools AND catalogue operations, because since D-037 an
    operation is reachable without a tool of its own: `point_on_surface` has no
    tool and is not a ghost. The guard still bites on a name that was removed or
    never existed, which is what it is for.

    Every `<table class="tools">` is checked, not the first one. It used to read
    only the first, and the moment a second table was added above the tool table
    the guard started checking the wrong one — reporting a real operation as a
    ghost, which is how this was noticed.
    """
    from mapsmith import catalog, server

    known = {t.name for t in server.mcp._tool_manager.list_tools()}
    known |= {op["name"] for op in catalog.OPERATIONS}
    tables = re.findall(
        r'<table class="tools".*?</table>', SITE_TEMPLATE.read_text(encoding="utf-8"), re.DOTALL
    )
    assert tables, "the site template lost its tool table"
    named = {n for table in tables for n in re.findall(r"\b([a-z]+(?:_[a-z]+)+)\b", table)}
    ghosts = sorted(named - known)
    assert not ghosts, (
        f"mapsmith.dev names things that do not exist: {ghosts}. "
        "The page is generated, so nothing else will ever notice."
    )

def test_every_number_on_the_site_comes_from_a_placeholder_the_build_fills():
    """Both directions. A `{{NEW_COUNT}}` nobody fills breaks the build (which
    is fine, it is loud); a placeholder the build still computes and the page
    no longer shows is a claim that quietly left the shop window."""
    template = SITE_TEMPLATE.read_text(encoding="utf-8")
    build = SITE_BUILD.read_text(encoding="utf-8")
    in_page = set(re.findall(r"\{\{[A-Z_]+\}\}", template))
    assert in_page, "the site template lost its placeholders"
    filled = {p for p in re.findall(r'"(\{\{[A-Z_]+\}\})"', build)}
    assert not in_page - filled, f"placeholders the build does not fill: {sorted(in_page - filled)}"
    assert not filled - in_page, (
        f"the build computes values the page no longer shows: {sorted(filled - in_page)}"
    )


def test_the_twin_project_is_linked_from_both_of_our_front_doors():
    """The mirror image of the defect a reader found on 2026-08-24: argleton.org
    was linked from its own repository's homepage field, which nobody sees, and
    from nowhere in its README. Here the risk is the same one facing outward —
    the strongest evidence MapSmith has is a suite that grades it and lives in
    another organisation, so both front doors have to point at it, and the
    README has to do it on the first screen rather than in a roadmap entry
    four hundred lines down."""
    first_screen = README.read_text(encoding="utf-8").split("## Quickstart")[0]
    assert "argleton.org" in first_screen, (
        "the README's first screen does not link the correctness suite that grades MapSmith"
    )
    assert "argleton.org" in SITE_TEMPLATE.read_text(encoding="utf-8"), (
        "mapsmith.dev states the silent-error problem and never points at the instrument "
        "that measures it"
    )
    assert "argleton" in (ROOT / "docs" / "benchmarks.md").read_text(encoding="utf-8").lower(), (
        "benchmarks.md is where the hand-off to Argleton is declared; it no longer names it"
    )


# Words that promise instead of stating. Each one has a concrete replacement:
# a number, a mechanism, or a link to a measurement.
_MARKETING = (
    "revolutionary", "seamless", "blazing", "cutting-edge", "game-chang", "effortless",
    "state-of-the-art", "unleash", "supercharge", "next-generation", "world-class",
    "turbocharg", "magical",
)


@pytest.mark.parametrize(
    "page", _showcase_pages(), ids=lambda p: str(p.relative_to(ROOT)).replace("\\", "/")
)
def test_the_showcase_states_instead_of_selling(page):
    """The audience is GIS engineers: an adjective where a number belongs reads
    as a claim nobody measured."""
    text = page.read_text(encoding="utf-8").lower()
    found = sorted({w for w in _MARKETING if w in text})
    assert not found, f"{page.name} sells instead of stating: {found}"


def test_every_screenshot_is_actually_shown():
    """An image nobody links to is either a stale UI we forgot to delete or a
    screenshot we forgot to publish. Both are worth one line of test."""
    images = sorted((ROOT / "docs" / "images").glob("*"))
    if not images:
        return
    referenced = {
        (page.parent / target).resolve()
        for page in _showcase_pages()
        for target in _local_links(page)
    }
    unused = [i.name for i in images if i.resolve() not in referenced]
    assert not unused, f"images in docs/images nobody displays: {unused}"


def _notebook_output_text(notebook: Path) -> str:
    import json

    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    chunks = []
    for cell in cells:
        for output in cell.get("outputs", []):
            chunks.append("".join(output.get("text", [])))
            chunks.append(json.dumps(output.get("data", {})))
            if output.get("output_type") == "error":
                chunks.append("\n".join(output.get("traceback", [])))
    return "\n".join(chunks)


@pytest.mark.parametrize(
    "notebook", sorted((ROOT / "examples").glob("*.ipynb")), ids=lambda p: p.name
)
def test_the_gallery_shows_the_current_release(notebook):
    """The notebooks are committed *with their outputs*: that is the point (a
    visitor reads results without running anything), and it is also how a
    manifest from the previous release stays on display forever.

    Reads `producer.version` off the PARSED manifests since 2026-09-09. It used
    to grep the output text for `mapsmith_version`, a field of our own invention
    that has been removed -- and the form of the assertion was
    `shown <= {__version__}`, which is true of the empty set. Two of the three
    notebooks already satisfied it by showing nothing at all, so the guard was
    green on notebooks it was not reading. Anchoring on parsed manifests makes
    it impossible to be vacuous quietly: the companion test below fixes exactly
    which notebooks must contain one.
    """
    from mapsmith import __version__

    manifests = _manifests_shown_in(notebook)
    if notebook.name in NOTEBOOKS_SHOWING_A_MANIFEST:
        assert manifests, (
            f"{notebook.name} is declared as showing a manifest and none parsed "
            "out of its output. Re-run it, or move it out of "
            "`NOTEBOOKS_SHOWING_A_MANIFEST` on purpose."
        )
    for manifest in manifests:
        shown = (manifest.get("producer") or {}).get("version")
        assert shown == __version__, (
            f"{notebook.name} displays a manifest from {shown!r} and this is "
            f"{__version__} -- re-run the notebook instead of editing its output"
        )


def _manifests_shown_in(notebook: Path) -> list[dict]:
    """Every complete provenance manifest printed in a notebook's output.

    Parsed rather than pattern-matched, which is the point: a manifest printed
    through a slice — `json.dumps(manifest, indent=2)[:1500]`, which is what
    notebook 01 did — does not parse, so it is not counted, so the "at least
    one" assertion below fails instead of quietly having nothing to check.
    """
    text = _notebook_output_text(notebook)
    decoder = json.JSONDecoder()
    found = []
    for start in re.finditer(r"^\{", text, re.MULTILINE):
        try:
            candidate, _ = decoder.raw_decode(text[start.start() :])
        except ValueError:
            continue
        if isinstance(candidate, dict) and {"operation", "engine"} <= candidate.keys():
            found.append(candidate)
    return found


#: Which notebooks are expected to display a full provenance manifest. Declared
#: rather than counted, because summing over the gallery was itself vacuous: the
#: first version of this test asserted `sum(...) > 0`, which notebook 01 satisfies
#: on its own, so 02 and 03 could have gone back to showing pre-0.3.0 records with
#: the suite still green. That is the defect this test exists to close, one level
#: up. A notebook that starts or stops showing one fails here until somebody says
#: so on purpose — the safe direction.
NOTEBOOKS_SHOWING_A_MANIFEST = {"01_verified_geoprocessing.ipynb"}


def test_the_gallery_displays_a_conforming_manifest():
    """The vacuous half, and the one that was missing.

    `shown <= {__version__}` is true of the empty set. Two notebooks displayed
    manifests written before 0.3.0 — no `spec_version`, which the specification
    *requires*, and no `producer`, which it recommends — and `"path":
    "data\\\\wells.gpkg"` with the Windows separator that issue #30 fixed and the
    README says is fixed. The guard read a field those manifests do not have,
    found nothing, compared nothing to `{__version__}`, and passed. It had been
    passing for two releases.

    So the claim is stated positively and checked positively: the gallery shows
    a manifest *where it is meant to*, it parses, and it conforms — against both
    the validator and the schema, for the reason the front-page guard gives.
    """
    import importlib.util

    from mapsmith import __version__

    notebooks = sorted((ROOT / "examples").glob("*.ipynb"))
    shown = {n.name: _manifests_shown_in(n) for n in notebooks}
    displaying = {name for name, found in shown.items() if found}
    assert displaying == NOTEBOOKS_SHOWING_A_MANIFEST, (
        f"the gallery displays manifests in {sorted(displaying)}, and this test "
        f"expects {sorted(NOTEBOOKS_SHOWING_A_MANIFEST)}. A notebook that stopped "
        "showing one may be printing it through a slice, which no longer parses; "
        "a notebook that started showing one needs adding here, so that it is "
        "checked rather than merely tolerated."
    )

    spec = importlib.util.spec_from_file_location(
        "spec_validator", ROOT / "tests" / "data" / "manifest_spec_validator.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "tests" / "data" / "manifest-v1.schema.json").read_text(encoding="utf-8")
    )
    checker = jsonschema.Draft202012Validator(schema)

    for name, manifests in shown.items():
        for manifest in manifests:
            problems = module.problems(manifest) + [
                error.message for error in checker.iter_errors(manifest)
            ]
            assert problems == [], (
                f"{name} displays a manifest that is not a conforming record: "
                f"{problems}. Re-run the notebook; do not edit its output."
            )
            assert manifest.get("producer", {}).get("version") == __version__, (
                f"{name} displays a manifest produced by "
                f"{manifest.get('producer', {}).get('version')!r} and this is "
                f"{__version__} — re-run it."
            )
            for recorded in manifest.get("inputs", []):
                assert "\\" not in recorded.get("path", ""), (
                    f"{name} displays a manifest with a Windows separator in "
                    f"{recorded['path']!r}. Paths in a manifest are POSIX on "
                    "every platform (#30), and the gallery is where a reader "
                    "checks whether that is true."
                )


@pytest.mark.parametrize(
    "notebook", sorted((ROOT / "examples").glob("*.ipynb")), ids=lambda p: p.name
)
def test_the_gallery_notebooks_ran_clean(notebook):
    """An unexecuted cell or a traceback in the gallery reads as "this does not
    work", whatever the surrounding prose says."""
    import json

    cells = json.loads(notebook.read_text(encoding="utf-8"))["cells"]
    code = [c for c in cells if c["cell_type"] == "code" and "".join(c["source"]).strip()]
    silent = [i for i, c in enumerate(code) if not c.get("outputs")]
    errors = [
        i
        for i, c in enumerate(code)
        if any(o.get("output_type") == "error" for o in c.get("outputs", []))
    ]
    assert not errors, f"{notebook.name} ships a traceback in cells {errors}"
    assert not silent, (
        f"{notebook.name} has code cells with no saved output ({silent}): the gallery "
        "is meant to be readable without running it"
    )


def test_no_stale_version_strings_in_the_docs():
    """The provenance example in the README carries a version; a stale one
    tells visitors they are reading about an old release.

    On `producer.version` since 2026-09-09, and it was VACUOUS before that: it
    grepped for `mapsmith_version`, which the README's example has never
    contained, so the set was always empty and `shown <= {__version__}` was
    always true. Measured, not suspected -- zero occurrences on the day it was
    re-pointed. The `assert quoted` below is what stops that from recurring.
    """
    from mapsmith import __version__

    text = README.read_text(encoding="utf-8")
    # PARSED, not grepped. A bare `"version":` also matches the GeoParquet
    # level and anything else the page quotes -- the first attempt at this
    # failed on a `1.0.1` from a neighbouring block, which is a regex reading
    # a word where a field was meant.
    decoder = json.JSONDecoder()
    quoted = set()
    for start in re.finditer(r"^\{", text, re.MULTILINE):
        try:
            candidate, _ = decoder.raw_decode(text[start.start():])
        except ValueError:
            continue
        producer = candidate.get("producer") if isinstance(candidate, dict) else None
        if isinstance(producer, dict) and "version" in producer:
            quoted.add(producer["version"])
    assert quoted, (
        "the README shows no manifest with a `producer.version`, so this guard "
        "is checking nothing. Either the example was removed or its shape "
        "changed; a version check with no version to check is worse than none."
    )
    assert quoted <= {__version__}, (
        f"README shows producer.version {sorted(quoted)} but this is {__version__}"
    )


def test_the_readme_says_which_release_it_describes():
    """The version in PROSE, which the JSON check above does not see.

    Both live within thirty lines of each other, both name a release, and the
    0.4.0 release commit moved one and not the other: the manifest example said
    0.4.0 while the sentence above it still said "this page describes 0.3.0" --
    on a page documenting seventy-four operations, a stack switch and a manifest
    field that 0.3.0 does not have. The reader most exposed is the one arriving
    on release day, which is precisely when nobody re-reads the paragraph.

    The sentence also promises to name the difference when `main` runs ahead of
    the published artifact, so a mismatch is allowed -- as long as the page says
    which is which rather than simply naming the wrong one.
    """
    from mapsmith import __version__

    text = README.read_text(encoding="utf-8")
    match = re.search(r"This page describes \*\*([0-9][^*]*)\*\*", text)
    assert match, (
        "the sentence saying which release this page describes has been "
        "reworded or removed; update this test with it rather than dropping it"
    )
    stated = match.group(1)
    nearby = text[match.start() : match.start() + 800]
    # NOT the word "ahead". The paragraph's own promise is the sentence "when
    # `main` runs ahead of the published artifact this paragraph says so", so a
    # substring check for "ahead of" matches the boilerplate and passes on a page
    # that says nothing -- which is what the first version of this check did,
    # green on a README twenty-one commits behind its own tree. The marker is
    # the thing the promise actually owes a reader: a pointer to the list of
    # what is different, which no conditional sentence carries by accident.
    UNRELEASED = "CHANGELOG.md#unreleased"
    says_ahead = UNRELEASED in nearby
    if stated != __version__:
        assert says_ahead, (
            f"the README says it describes {stated} and this checkout is "
            f"{__version__}. That is allowed only while the paragraph also says "
            "main is ahead and names the difference -- it does not."
        )

    # The half the version comparison cannot see, and the reason it could not
    # fail. `__version__` does not move between releases, so a page describing
    # 0.4.0 on a checkout of 0.4.0 satisfied the check above no matter how far
    # `main` had run past the tag -- and the sentence promises more than the
    # number: it promises to SAY SO when it has. Twenty-one commits past v0.4.0,
    # including eight renamed manifest keys, the paragraph still read as though
    # the tag and the tree were the same thing. The condition is the tag, so the
    # guard now fails from the first commit after a release rather than from a
    # version bump that happens at the end.
    tag = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--match", "v*"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if tag.returncode != 0:
        pytest.skip("no version tag reachable from HEAD (shallow clone?)")
    counted = subprocess.run(
        # What an installer gets, not every commit (2026-09-26): a commit to the
        # site build or a test changes nothing in the package, and counting it
        # made the page announce a difference the release does not have.
        ["git", "rev-list", "--count", f"{tag.stdout.strip()}..HEAD", "--", *SHIPPED],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if counted.returncode != 0:
        pytest.skip("cannot count commits since the tag")
    commits = int(counted.stdout.strip())

    # The eve of a tag, the same exception the [Unreleased] guard makes: the
    # page already describes the version in the tree, whose changelog block is
    # dated, and whose tag does not exist yet. Without it the release commit
    # cannot be green before the tag, and the release procedure tags only on
    # green -- a check nobody can satisfy is a check that gets bypassed. Found
    # on the 0.7.0 release commit.
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    tagged = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/v{__version__}"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    ).returncode == 0
    eve_of_tag = (
        stated == __version__
        and not tagged
        and re.search(rf"^## \[{re.escape(__version__)}\] - \d{{4}}-\d\d-\d\d", changelog, re.MULTILINE)
    )
    if commits and not eve_of_tag:
        assert says_ahead, (
            f"{commits} commits since {tag.stdout.strip()} and the paragraph "
            f"does not say main is ahead and link {UNRELEASED}. It promises to, "
            "and the reader it is written for is the one installing the release "
            "while reading a page written against the tree."
        )
    else:
        # And the other direction, because the sentence is emptied by a release
        # rather than by a person: freshly tagged, "main is ahead" is false, and
        # a false reassurance survives longer than a missing one.
        assert not says_ahead, (
            f"HEAD is {tag.stdout.strip()} itself and the paragraph still "
            f"points at {UNRELEASED} as a difference from the release. Remove "
            "the sentence as part of the release."
        )


def test_the_published_manifest_carries_no_build_directory(tmp_path):
    """Only the input paths used to be stripped, and `output.path` went live as
    `/tmp/mapsmith-site-xxxx/basins.tif` -- on a workstation, with the user's
    home directory in it. Stripped on the serialised text, so any field goes."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

    workdir = tmp_path / "mapsmith-site-abc123"
    workdir.mkdir()
    manifest = {
        "inputs": [{"path": f"{workdir.as_posix()}/dem.tif"}],
        "output": {"path": f"{workdir.as_posix()}/basins.tif"},
        "notes": [f"read {workdir}\\dem.tif"],
    }
    stripped = json.dumps(build.strip_workdir(manifest, workdir))
    assert "mapsmith-site-abc123" not in stripped, stripped
    assert build.strip_workdir(manifest, workdir)["output"]["path"] == "basins.tif"


def test_the_site_names_what_main_has_that_the_release_does_not():
    """The site's paragraph makes the README's promise and nothing kept it.

    Between the 0.6.0 fixes and the tag, mapsmith.dev said "this page describes
    0.5.1" beside an operation 0.5.1 does not have. The build now renders the
    lead of every `[Unreleased]` entry, and nothing when there are none.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("site_build", ROOT / "site" / "build.py")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

    assert "{{AHEAD}}" in SITE_TEMPLATE.read_text(encoding="utf-8"), (
        "the site template no longer renders the ahead-of-release sentence"
    )
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    leads = re.findall(r"^- \*\*(.+?)\*\*", unreleased, flags=re.MULTILINE | re.DOTALL)
    rendered = build.unreleased_html(changelog, "9.9.9")
    if leads:
        assert "is ahead of 9.9.9" in rendered
        assert rendered.count("<li>") == len(leads)
    else:
        assert rendered == ""

    quiet = "# Changelog\n\n## [Unreleased]\n\nNothing yet.\n\n## [1.0.0] - 2026-01-01\n\n- **Old.**\n"
    assert build.unreleased_html(quiet, "1.0.0") == ""
    busy = quiet.replace("Nothing yet.", "### Fixed\n\n- **A `thing` was\n  wrong.** Details.")
    # With its heading: a Fixed lead names the defect, and bare it read as
    # though main had it.
    assert "<li>Fixed: A <code>thing</code> was wrong.</li>" in build.unreleased_html(busy, "1.0.0")
    with pytest.raises(RuntimeError):
        build.unreleased_html("# Changelog\n", "1.0.0")


def test_the_readme_does_not_say_the_product_is_unchanged_while_it_is_not():
    """The pointer to `[Unreleased]` is checked above; what the paragraph SAYS
    about the difference was not, and on 2026-09-25 it was false.

    It said main was ahead of 0.5.1 by two pages of the site and "nothing in
    the installable product changed" -- true when written on 2026-09-22, false
    from 2026-09-24, when `[Unreleased]` gained a Changed and six Fixed entries:
    a renamed manifest key and six operations that stopped giving wrong
    answers. The pointer was there, so the guard above was green. A reader who
    trusts the sentence does not follow the link.

    So the reassurance is allowed only while it can be true: while the
    unreleased section changes and fixes nothing.
    """
    # Whitespace collapsed first: the sentence that started this was wrapped
    # after "product", and the first version of this check searched the raw
    # text, found nothing and passed on the very paragraph it was written for.
    text = " ".join(README.read_text(encoding="utf-8").split())
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    touches_the_product = [
        heading
        for heading in ("### Changed", "### Fixed", "### Removed", "### Security")
        if heading in unreleased
    ]
    reassurances = [
        phrase
        for phrase in ("nothing in the installable product changed",)
        if phrase in text.lower()
    ]
    assert not (touches_the_product and reassurances), (
        f"the README says {reassurances[0]!r} while [Unreleased] has "
        f"{', '.join(touches_the_product)}: rewrite the paragraph to name what "
        "main changes, or release it"
    )


def test_declared_dependencies_are_not_advertised_as_future_work():
    """"More to come: X" for an X that already ships reads as either sloppy or
    dishonest, and both cost the same."""
    text = README.read_text(encoding="utf-8")
    # read as text, not via tomllib: a substring check stays true however the
    # dependency is expressed — extra, marker or version pin
    all_deps = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # substrings, so the check survives renaming "WhiteboxTools" to the name of
    # the library we actually depend on ("Whitebox Workflows")
    shipped = {"Whitebox": "whitebox", "DuckDB": "duckdb", "exactextract": "exactextract"}
    coming = re.search(r"more to come:([^)]*)\)", text)
    if not coming:
        return
    wrong = [name for name, pkg in shipped.items() if pkg in all_deps and name in coming.group(1)]
    assert not wrong, f"listed as future work but already a dependency: {wrong}"


# A URL written bare in markdown is rendered as a clickable link by GitHub. For
# an illustrative address that is not meant to resolve, that produces a link a
# reader follows and finds nothing — which reads as a broken page rather than as
# an example. Fenced or inline code is not linked, so that is where they belong.
BARE_URL = re.compile(r"(?<![(`\[<])https?://[^\s)\]`<>\"]+")
ILLUSTRATIVE_HOSTS = ("evil.tld", "example.com", "example.org", "attacker", "internal.")


@pytest.mark.parametrize("page", _showcase_pages(), ids=lambda p: p.name)
def test_an_illustrative_url_is_never_rendered_as_a_link(page: Path):
    """`https://evil.tld/x.gpkg` explains an attack; it is not somewhere to go."""
    text = page.read_text(encoding="utf-8")
    # Code fences are already safe, and stripping them keeps the check honest
    # rather than making authors escape things twice.
    outside_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    offenders = [
        m.group(0)
        for m in BARE_URL.finditer(outside_code)
        if any(host in m.group(0) for host in ILLUSTRATIVE_HOSTS)
    ]
    assert not offenders, (
        f"{page.name}: illustrative URLs rendered as clickable links — wrap them in "
        f"backticks so a reader does not follow one and find nothing: {offenders}"
    )


# Vendor names we do not write in public, at all: no note, no table row, no
# comparison. The reason is not politeness — it is that a public comparison
# invites a reply we have no standing to have, and a single sentence about a
# vendor is enough to frame this project as competing with one rather than
# measuring anything. The GDAL driver short names below are the one exception:
# they are identifiers GDAL itself emits, and the deny-list test that keeps new
# drivers from arriving unreviewed cannot spell them any other way.
VENDOR_SILENCE = re.compile(r"esri|arcgis|arcpy|arcmap", re.IGNORECASE)
# Identifiers that belong to somebody else's API, not mentions of a vendor: two
# GDAL driver names and one keyword argument of whitebox-workflows. A rule about
# what the project SAYS cannot forbid the spelling of a function parameter it has
# to pass -- but the list stays short and explicit, so a new entry is a decision
# rather than a hole.
DRIVER_IDENTIFIERS = (
    "ESRI Shapefile", "ESRIJSON", "esri_pntr",
    # The value of a manifest's `engine.name`, and of the module that produces
    # it. A record that could not name the engine that made the numbers would
    # be useless, and naming it is the opposite of a comparison — it is the
    # admission that a different engine ran. Same principle as the driver names
    # above: an identifier of somebody else's thing, not a claim about it.
    "\"ArcGIS Pro\"", "ArcGISPro.exe",
)


def _tracked_text_files() -> list[Path]:
    """Every tracked file a stranger can read, source included."""
    import subprocess

    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True
    ).stdout.split("\n")
    keep = {".md", ".py", ".html", ".yml", ".yaml", ".toml", ".json", ".cff", ".txt", ".ipynb"}
    return [
        ROOT / name
        for name in out
        if name and (ROOT / name).suffix in keep and (ROOT / name).exists()
    ]


#: What a comparison looks like when it is written down. A percentage, a score,
#: a ratio, or a word that ranks. A plain count is none of these: "2198 tools
#: are installed, 1274 run on your licence" describes the reader's own machine
#: and is the fact that explains why a fallback exists.
COMPARATIVE = re.compile(
    r"\d+(\.\d+)?\s*%"
    r"|\b0\.\d+\b"
    r"|\b\d+\s*/\s*\d+\b"
    # Words only where they RANK, which in English means they carry a "than".
    # The bare adjectives were tried and are too common in ordinary prose:
    # "behind an extension" and "worse than a match" are not benchmarks, and a
    # guard that cries on those gets switched off — which leaves less
    # protection than a narrower rule that nobody disables.
    r"|\b(faster|slower|better|worse|more accurate|less accurate)\s+than\b"
    r"|\b(beats|outperforms)\b",
    re.IGNORECASE,
)
#: How far from the name a figure still reads as being about it. Two lines of
#: prose: far enough to catch "ArcGIS Pro. … 35% of tasks", short enough that an
#: unrelated number three paragraphs down does not trip it.
COMPARISON_WINDOW = 160


def test_no_vendor_is_named_beside_a_figure():
    """The name is allowed; the name next to a number is not (D-057).

    This used to forbid the name outright, and D-044 was right to while Esri was
    only something we measured. D-056 made it a MODE of the product — a stack
    the caller can choose — and a product with an Esri mode names it in the
    README, in the opening handshake, and in the message that says the licence
    is missing. Silence and the mode cannot both exist.

    So the line moved to where it actually protects something: **integrating is
    not comparing.** Saying "MapSmith calls what you have installed" describes
    this project. Putting a score beside that name is a benchmark, and D-057
    keeps benchmarks unpublished.

    What is deliberately NOT relaxed: Argleton's own guard still forbids the
    name outright, because Argleton is the surface a comparison would live on.
    """
    offenders = {}
    for page in _tracked_text_files():
        if page.resolve() == Path(__file__).resolve():
            continue  # this file names them in order to constrain them
        text = page.read_text(encoding="utf-8", errors="replace")
        for identifier in DRIVER_IDENTIFIERS:
            text = text.replace(identifier, "")
        hits = []
        for match in VENDOR_SILENCE.finditer(text):
            start = max(0, match.start() - COMPARISON_WINDOW)
            window = text[start : match.end() + COMPARISON_WINDOW]
            figure = COMPARATIVE.search(window)
            if figure:
                line = text[: match.start()].count("\n") + 1
                hits.append(f"line {line}: {match.group(0)!r} near {figure.group(0)!r}")
        if hits:
            offenders[str(page.relative_to(ROOT)).replace("\\", "/")] = hits
    assert not offenders, (
        "a vendor is named beside a figure, which is a comparison however it is "
        f"phrased, and D-057 keeps those unpublished: {offenders}. Say the thing "
        "without the number, or move the number somewhere the name is not."
    )


NUMBER_WORDS_TO_INT = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
    "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def test_the_pages_count_the_operations_that_actually_refuse_an_ambiguous_raster():
    """A count of callers, stated in prose on two surfaces, counted from src/.

    This page promised the refusal for a whole release while the function had
    **no caller in src/** — a test called it directly and went green. The fix
    gave it nine callers, and the prose then said "an operation that computes
    from the georeferencing refuses", which is a different overstatement: the
    terrain and sampling operations do not call it, so sixteen of the
    twenty-five raster operations were covered by a sentence and not by code.

    Now the pages name the number, which means the number can go stale the next
    time one is wired — so it is counted here instead of remembered. Prose in
    words, not digits, on purpose: a phrase is what a reader believes, and a
    phrase is what this reads.
    """
    callers = set()
    for source in (ROOT / "src" / "mapsmith").rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        callers.update(
            re.findall(
                r"""refuse_ambiguous_georeferencing\(\s*[^,]+,\s*["']([a-z_]+)["']""",
                text,
            )
        )
    assert callers, (
        "nothing in src/ calls refuse_ambiguous_georeferencing. That was the "
        "defect: the README promised the refusal, a decision record declared it, "
        "and the only caller was a test."
    )

    stated = []
    for page in (README, SITE_TEMPLATE):
        text = page.read_text(encoding="utf-8")
        for word in re.findall(
            r"\b([a-z]+) operations that read a raster's grid directly", text
        ):
            stated.append((page.name, word))
    assert stated, (
        "neither the README nor the site page states how many operations refuse "
        "an ambiguously georeferenced raster. Say the number — the version "
        "without one said 'an operation that computes', which is every raster "
        "operation and was false for sixteen of them."
    )
    for name, word in stated:
        assert NUMBER_WORDS_TO_INT.get(word) == len(callers), (
            f"{name} says {word!r} operations refuse an ambiguous raster and "
            f"{len(callers)} call the refusal: {sorted(callers)}"
        )


def test_the_roadmap_does_not_list_a_shipped_operation_as_future_work():
    """The tool-name version of this check stopped being enough.

    Operations can now ship without a tool of their own, so a capability can be
    live and still sit unticked on the roadmap — which is how "stream network
    extraction" stayed listed as future work on the day `extract_streams`
    shipped. Names are matched by stem so the prose form of a capability
    ("stream network extraction") is caught alongside the identifier.

    Parentheticals are stripped before matching, because that is where an item
    names a shipped operation as *context* for something new rather than as the
    promise: "per-zone embedding vectors (multiband zonal statistics)" promises
    the embeddings, not `zonal_statistics`. Matching the main clause keeps the
    check sharp without an allow-list that would grow until it meant nothing."""
    from mapsmith import catalog

    available = [
        entry["name"] for entry in catalog.OPERATIONS if entry.get("status") == "available"
    ]
    todo = re.findall(r"^- \[ \] (.+)$", README.read_text(encoding="utf-8"), re.MULTILINE)
    offenders = {}
    for name in available:
        stems = [token.rstrip("s") for token in name.split("_") if len(token.rstrip("s")) > 3]
        if not stems:
            continue
        for item in todo:
            promise = re.sub(r"\([^)]*\)", "", item)
            if all(re.search(rf"\b{stem}", promise, re.IGNORECASE) for stem in stems):
                offenders[name] = item
    assert not offenders, (
        f"the roadmap lists shipped operations as future work: {offenders}. "
        "Tick the box, or say precisely which part is still missing."
    )


def test_no_public_page_states_a_python_floor_that_disagrees_with_the_package():
    """`pyproject.toml` is the floor; a page that names a different one is a lie
    a newcomer discovers as a failed install.

    CONTRIBUTING said 3.10 for a day after the floor moved to 3.12 (D-038), and
    the only reader who would ever notice is the one it costs the most."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    declared = re.search(r'requires-python\s*=\s*">=\s*(\d+\.\d+)"', pyproject)
    assert declared, "pyproject.toml no longer declares requires-python in a readable form"
    floor = declared.group(1)
    stated = re.compile(r"Python\s*(?:>=|≥|>)\s*(\d+\.\d+)")
    offenders = {}
    for page in _showcase_pages():
        for found in stated.findall(page.read_text(encoding="utf-8")):
            if found != floor:
                offenders[str(page.relative_to(ROOT)).replace("\\", "/")] = found
    assert not offenders, (
        f"pyproject requires Python >={floor} but these pages say otherwise: {offenders}"
    )

def test_every_test_fixture_is_tracked_by_git():
    """A file the tests read must be a file CI has.

    `tests/data/` is ignored wholesale with per-filename exceptions, which is
    the right default for datasets and the wrong shape for vendored
    dependencies: the exception is a filename, so the SECOND vendored file is
    ignored by default. That has now happened twice -- the spec validator, then
    the schema beside it on 2026-08-26 -- and both times the symptom was a suite
    that passed locally and a CI that could not find the file. The `.gitignore`
    comment recording the first one did not prevent the second, because prose
    does not run."""
    import subprocess

    tracked = set(
        subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "tests/data"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
    )
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests" / "data").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    missing = sorted(on_disk - tracked)
    assert not missing, (
        f"these files are read by the tests and not tracked by git: {missing}. "
        "CI checks out the repository, not this machine: add them, or the suite "
        "passes here and fails there."
    )

NUMBER_WORDS = {
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
    21: "twenty-one", 22: "twenty-two", 23: "twenty-three", 24: "twenty-four",
    25: "twenty-five", 26: "twenty-six",
}


def test_the_changelog_block_for_this_version_counts_what_is_actually_here():
    """The counts in `[Unreleased]` age exactly like the README's, and nothing watched them.

    On 2026-08-28 that block said "18 → 27" against 28 registered tools (and 18→28
    is ten, not nine), "41 operations (39 available, 2 planned)" against 51/49/2,
    and `spec_version 1.0.0-draft.2` against the draft.3 the code emits. Three
    stale numbers in the file a packager reads to decide what a release contains.
    """
    from mapsmith import __version__, catalog, server

    # The block for the version in the tree, not simply the first one. Cutting
    # the 0.3.0 release moved these counts out of `[Unreleased]` and into a
    # dated section, and a test anchored on "the first block" would have gone on
    # passing over an empty one — which is worse than failing.
    changelog = README.parent.joinpath("CHANGELOG.md").read_text(encoding="utf-8")
    blocks = changelog.split("## [")
    # The block for the version in the tree AND the unreleased one, joined.
    # Taking only the first that exists meant that between two releases the
    # counts were checked against the dated section and the `[Unreleased]`
    # entries -- the ones about to become a release body -- were checked by
    # nothing. A stale spec_version sat there until the eve of a tag for
    # exactly that reason, and would have turned the suite red at the bump
    # instead of being caught while it was being written.
    block = "\n".join(
        b
        for b in blocks
        if b.startswith((f"{__version__}]", "Unreleased]"))
    )
    assert block.strip(), (
        f"the changelog has no section for {__version__} and no [Unreleased] one, "
        "so nothing here is checking the counts a packager reads"
    )

    tools = len(asyncio.run(server.mcp.list_tools()))
    total = len(catalog.OPERATIONS)
    available = sum(1 for op in catalog.OPERATIONS if op["status"] == "available")
    planned = total - available

    wrong = []
    # Anchored on the sentence that states the shipped shape. Loose patterns match
    # prose about the 800-operation scale projection, which is a different number
    # about a different catalogue.
    for pattern, actual, what in (
        (r"18 → (\d+)\.\*\*", tools, "tools"),
        (r"catalogue is\s+at (\d+) operations", total, "catalogue operations"),
        (r"operations \((\d+) available", available, "available operations"),
        (r"available, (\d+) planned\)", planned, "planned operations"),
    ):
        for found in re.findall(pattern, block):
            if int(found) != actual:
                wrong.append(f"{what}: CHANGELOG says {found}, there are {actual}")
    assert not wrong, (
        "the [Unreleased] block describes a different product from the one in this "
        f"tree: {wrong}"
    )

    from mapsmith import provenance

    emitted = provenance.SPEC_VERSION
    # The DECLARATION must be the version the writers emit. Every other mention
    # may only be a draft that has already happened: an entry explaining that a
    # field entered the format in draft.4 is true and stays true, and the first
    # version of this check forbade it -- it compared every backticked draft in
    # the block, so a correct historical sentence failed the release. That is
    # the same shape as a guard accusing a page that is right, which this
    # repository has now met in three different files.
    # The NEWEST section that declares a spec_version is the one that speaks for
    # the product, and the older ones are history. Until 2026-09-24 this read
    # every declaration in `[Unreleased]` and `[{__version__}]` together, so the
    # moment `[Unreleased]` announced draft.6 the 0.5.1 section's true sentence
    # "records still declare `spec_version` `1.0.0-draft.5`" failed the build --
    # the fourth time here a guard has accused a page that was right.
    unreleased = next((b for b in blocks if b.startswith("Unreleased]")), "")
    newest = unreleased if re.search(r"`spec_version`\s+`1\.0\.0-draft", unreleased) else block
    declared = re.findall(r"`spec_version`\s+`(1\.0\.0-draft\.\d+)`", newest)
    assert declared, (
        "the [Unreleased] block no longer declares which spec_version the "
        "records carry; that sentence is what a consumer of the manifests reads"
    )
    for found in declared:
        assert found == emitted, (
            f"the CHANGELOG announces spec_version {found} and the writers emit "
            f"{emitted}"
        )
    latest = int(emitted.rsplit(".", 1)[1])
    for found in re.findall(r"`1\.0\.0-draft\.(\d+)`", block):
        assert int(found) <= latest, (
            f"the CHANGELOG mentions draft.{found}, which is ahead of the "
            f"{emitted} these writers emit"
        )


def test_no_page_cites_an_argleton_run_other_than_the_vendored_one():
    """The citation guards the numbers; this guards the pointer beside them.

    A run folder and a `spec_commit` are what a reader clicks to check a number,
    and they aged separately from the number itself: on 2026-08-28 the table in
    `docs/benchmarks.md` carried the right figures under a link to the previous
    day's run, which happened to have the same ones. A stale link under a correct
    number is worse than a stale number, because it looks verified.

    The same applies to the family count written as a word. "Nineteen-family run"
    survived a family being added because no test reads English numerals.
    """
    citation = json.loads((ROOT / "docs" / "argleton-run.json").read_text(encoding="utf-8"))
    run, commit, families = citation["run"], citation["spec_commit"], citation["families"]

    pages = [README, SITE_TEMPLATE, *(ROOT / "docs").glob("*.md")]
    wrong = []
    for page in pages:
        prose = page.read_text(encoding="utf-8")
        for stale in re.findall(r"results/(20\d\d-\d\d-\d\d[a-z0-9-]*)", prose):
            if stale != run:
                wrong.append(f"{page.name}: links results/{stale}, citation says {run}")
        if f"`{commit}`" not in prose and f"results/{run}" in prose:
            wrong.append(f"{page.name}: links the run but does not quote spec_commit {commit}")
        for n, word in NUMBER_WORDS.items():
            if f"{word}-family" in prose.lower() and n != families:
                wrong.append(
                    f"{page.name}: says '{word}-family' where the citation has {families}"
                )
    assert not wrong, (
        "these pages point at an Argleton run that is not the published one, so a "
        f"reader checking a number lands on the wrong folder: {wrong}"
    )


def test_every_argleton_number_quoted_here_matches_the_vendored_citation():
    """Argleton's numbers are the ones this repo cannot count for itself.

    Tool, test and catalogue counts come from this source tree, so the build
    computes them and they cannot drift. Argleton is a separate repository in a
    separate organisation — on purpose — so its numbers arrive as prose, and
    prose ages: the trap count was hand-typed and went stale three times in four
    days (eight families, then eighteen, then twenty traps).

    `docs/argleton-run.json` is the single vendored citation, written by the
    publish script when a run is published. Everything quoted here must agree
    with it, and the site template must not hand-type the count at all.
    """
    import json

    citation = json.loads((ROOT / "docs" / "argleton-run.json").read_text(encoding="utf-8"))
    traps = citation["traps_run"]
    spelled = {
        18: "eighteen", 19: "nineteen", 20: "twenty", 21: "twenty-one",
        22: "twenty-two", 23: "twenty-three", 24: "twenty-four", 25: "twenty-five",
        26: "twenty-six", 27: "twenty-seven", 28: "twenty-eight", 29: "twenty-nine",
        # Extended as the suite grows, and the failure mode of forgetting is the
        # safe one twice over: an absent word makes the loop below find nothing
        # and the `checked` assertion fires. On 2026-09-02 the count reached 31
        # and this map stopped at 30, so every page stated a figure no pattern
        # could see — which is the guard saying "I can no longer guard" rather
        # than passing over nothing.
        30: "thirty", 31: "thirty-one", 32: "thirty-two", 33: "thirty-three",
        34: "thirty-four", 35: "thirty-five",
    }

    template = (ROOT / "site" / "index.template.html").read_text(encoding="utf-8")
    assert "{{TRAP_COUNT}}" in template, (
        "the site template no longer reads the trap count from the citation"
    )
    for wrong in (v for k, v in spelled.items() if k != traps):
        assert f"{wrong} traps" not in template.lower(), (
            f"the template hand-types {wrong!r} traps; the published run has {traps}"
        )

    # Markdown is prose and cannot hold a placeholder, so it is checked instead:
    # any trap count it states must be the published one. README and docs/, which
    # are the pages a reader arrives at.
    pages = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    checked = 0
    for page in pages:
        text = page.read_text(encoding="utf-8").lower()
        for number, word in spelled.items():
            for phrase in (f"{word} traps", f"over {number} traps", f"on {number} traps"):
                if phrase in text:
                    checked += 1
                    assert number == traps, (
                        f"{page.name} says {phrase!r}; the published run "
                        f"({citation['run']}) has {traps} traps"
                    )
    assert checked, (
        "no page states a trap count any more — if the claim moved, move this check with it "
        "rather than leaving it passing over nothing"
    )

    # The two rates, same argument. They reached the page on 2026-09-22, one of
    # them into the stats strip beside "375 TASK-RUNS", which is where a reader
    # skimming for a number stops. A rate is exactly the kind of figure that
    # moves when a denominator grows, and the trap count above has already gone
    # stale three times in four days for that reason.
    ours = f"{citation['mapsmith_silent_error_rate']:.2f}"
    naive = f"{citation['naive_silent_error_rate']:.4f}"
    assert "{{SILENT_ERRORS}}" in template and "{{NAIVE_SILENT_ERRORS}}" in template, (
        "the site template no longer reads the silent-error rates from the citation"
    )
    for page in pages:
        text = page.read_text(encoding="utf-8")
        for phrase, right in (("silent errors", ours), ("silent error rate", ours)):
            for match in re.finditer(rf"([0-9]\.[0-9]+)\s+{phrase}", text):
                assert match.group(1) == right, (
                    f"{page.name} says {match.group(0)!r}; the published run "
                    f"({citation['run']}) puts MapSmith at {right}"
                )
        for stale in re.finditer(r"0\.9[0-9]{3}", text):
            assert stale.group(0) == naive, (
                f"{page.name} states {stale.group(0)}, which is a naive rate from "
                f"an earlier run; the published one is {naive}"
            )


def test_the_readme_catalog_counts_are_the_real_ones():
    """Two numbers in the discovery section, both hand-typed, both already wrong.

    The sentence read "41 today, and 28 of them have no tool of their own" on
    27/08/2026 with 51 entries and 26 without a tool -- and the 28 was not a
    stale count of anything, it was the count of exposed TOOLS from a paragraph
    further up, reused for a different claim. The site build computes the first
    number from the catalog; the README states it in prose, so it needs this.
    """
    import re

    from mapsmith import catalog

    text = README.read_text(encoding="utf-8")
    match = re.search(
        r"operation MapSmith can perform — (\d+) today, and (\d+) of them have no "
        r"tool of their own",
        text,
    )
    assert match, (
        "the sentence carrying the catalog counts has been reworded; update this "
        "test with it rather than deleting it"
    )
    stated_total, stated_toolless = int(match.group(1)), int(match.group(2))
    assert stated_total == len(catalog.OPERATIONS)
    assert stated_toolless == sum(
        1 for entry in catalog.OPERATIONS if entry.get("tool") is None
    )

    # And the one in "When not to use MapSmith", which said 75 on the release
    # commit of 0.6.0 while three other lines of the page said 76. A reader
    # deciding whether the product is broad enough reads that bullet and not
    # the discovery section.
    breadth = re.search(
        r"full breadth of a desktop GIS\.\*\*\s+(\d+) operations", text
    )
    assert breadth, "the 'full breadth of a desktop GIS' bullet has been reworded"
    assert int(breadth.group(1)) == len(catalog.OPERATIONS), (
        f"'When not to use MapSmith' says {breadth.group(1)} operations; the "
        f"catalogue has {len(catalog.OPERATIONS)}"
    )


def test_the_retrieval_numbers_agree_between_the_readme_and_the_site():
    """The same measurement is quoted on two surfaces, in prose, in two formats.

    Exactly the shape that has rotted twice in this repository. The build
    generates the tool and catalogue counts, but it cannot generate these —
    running the measurement would make every site build load an embedding model
    and embed 850 documents — so the guard is that the two surfaces cannot
    disagree, while `test_retrieval_at_scale` says whether what they agree on is
    still true.

    The two pages do not carry the SAME amount of detail on purpose: the README
    is where the ablation tables live, the site compresses them. So this checks
    the claims that appear on both, not that one is a copy of the other.
    """
    readme = README.read_text(encoding="utf-8")
    site = SITE_TEMPLATE.read_text(encoding="utf-8")

    # The product's own numbers, and the ones the clarification path rests on.
    # If one surface is edited and the other is not, this is what catches it.
    # This list has been rewritten twice in two days, and both times because a
    # published number was wrong rather than because a surface drifted. 70% came
    # from twenty queries we wrote ourselves; 51% replaced it from the independent
    # set; 48% is the same measurement over the larger set, and it stopped being
    # the headline when the answer became a delivered SET rather than a ranking.
    # Whichever numbers are current have to be on both surfaces, which is the
    # whole job of this test.
    shared = [
        ("118", "independent requests the retrieval numbers come from"),
        # Was "60%" until 2026-08-29, and it had been stale for three catalogue
        # sizes: it passed only because that string happened to appear in two
        # unrelated sentences on the two pages. A shared-number check that
        # matches by coincidence is worse than one that is missing.
        ("58%", "our ranking, found@3, once arity is declared"),
        ("69%", "a model choosing from the delivered candidates"),
        ("70%", "where the two model labellers agree with each other"),
        ("4.4", "plausible families per request, why family cannot filter"),
        # Replaced the 800-operation projection on 2026-08-29: the wall it
        # projected arrived at sixty-one, so the pages now carry what happened
        # rather than what was expected to.
        ("34", "candidates before arity was declared — the set that broke it"),
        ("45%", "delivered while the set was too large to hand over"),
        ("0.90", "top-3 agreement when an answer exists"),
        ("0.18", "top-3 agreement when it does not"),
        ("9 of 11", "unanswerable queries the clarification catches"),
        ("centroid_layer", "the defect the discovery contract found"),
    ]
    missing = [
        f"{value} ({what})"
        for value, what in shared
        if value not in readme or value not in site
    ]
    assert not missing, (
        "these claims are not on both surfaces any more, so one of them has been "
        f"edited and the other has not: {missing}"
    )

    # And a number that appears on both must appear with the same value. The
    # ablation table lives in the README; where the site repeats one of its rows,
    # the row has to match.
    import re

    rows = re.findall(r"^[|] (\d+) [|] (\d+)% [|] (\d+)% [|]$", readme, re.MULTILINE)
    for size, lexical, vector in rows:
        pattern = rf"<tr><td>{size} operations</td><td>(\d+)%</td><td>(\d+)%</td></tr>"
        found = re.search(pattern, site)
        if not found:
            continue  # the site is allowed to carry less, not to carry it wrong
        assert found.groups() == (lexical, vector), (
            f"at {size} operations the README says {lexical}% / {vector}% and the site "
            f"says {found.group(1)}% / {found.group(2)}%"
        )


def test_the_readme_and_the_site_offer_the_same_places_to_follow():
    """Two front doors, one list of channels, and no reason for them to differ.

    Added 2026-09-04 with the LinkedIn Page, which is the case that showed why
    it was needed: the README carried the channels and the site carried none, so
    a channel could be added to one surface and be invisible on the other with
    nothing going red. A Page nobody can reach from anywhere converts nobody,
    which is the same defect as a page written and not linked -- twice made
    here already.

    `UPDATE_CHANNELS` in the site build is the one place; this asserts the
    README says the same thing, in the same order, and nothing else.
    """
    import ast
    import re

    tree = ast.parse(SITE_BUILD.read_text(encoding="utf-8"))
    declared = next(
        (
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "UPDATE_CHANNELS"
                for t in node.targets
            )
        ),
        None,
    )
    assert declared, "site/build.py no longer declares UPDATE_CHANNELS"

    text = README.read_text(encoding="utf-8")
    sentence = re.search(r"Updates:\s*(.+?)\.\s*\n", text, re.DOTALL)
    assert sentence, "the README no longer carries an 'Updates:' line"
    in_readme = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", sentence.group(1))
    assert in_readme == [tuple(pair) for pair in declared], (
        f"the README lists {in_readme} and site/build.py declares {declared}; "
        "add the channel to UPDATE_CHANNELS and to the README, not to one of them"
    )
    assert "{{UPDATE_CHANNELS}}" in SITE_TEMPLATE.read_text(encoding="utf-8"), (
        "the site template no longer renders UPDATE_CHANNELS, so the site build "
        "would drop the channels while this test kept passing"
    )


def test_the_site_build_is_at_least_valid_python(tmp_path):
    """The suite stayed green with a syntax error in `site/build.py`.

    On 2026-08-29 a bad edit left an `if` at the wrong indentation there, and
    1391 tests passed anyway: this file reads `build.py` as *text* — to check
    the sentences it emits — and nothing ever compiles it. The site is one of
    the four public surfaces, so its builder being broken is a broken showcase
    that only shows up when somebody deploys.

    Compiling is not building, and it deliberately stops short of running the
    thing: a real build takes minutes and needs the engines. What it buys is
    that the failure arrives from the test suite rather than from Pages.

    The byte-code goes into this test's own `tmp_path`, not next to the source.
    It used to write `build.pyc` beside `build.py` and delete it afterwards,
    which is a **shared path**: two runs of the suite over the same checkout
    raced on it, and on 2026-08-31 two independent parallel runs each produced a
    different failure, both green in isolation. Two runs at once is not a
    supported configuration, but a suite that goes red once on a shared checkout
    will do it again on a runner with retries — where it looks like a defect in
    the product rather than in the test. A test that writes outside `tmp_path`
    has to justify it, and this one could not.
    """
    import py_compile

    for script in (SITE_BUILD, ROOT / "benchmarks" / "worked_example.py"):
        try:
            py_compile.compile(
                str(script), doraise=True, cfile=str(tmp_path / f"{script.stem}.pyc")
            )
        except py_compile.PyCompileError as broken:  # pragma: no cover
            raise AssertionError(f"{script.name} does not compile: {broken}") from None


def test_the_manifest_on_the_front_page_conforms_to_the_specification():
    """The record a third-party implementer copies had none of the required fields.

    Eighty lines above it the page says "Records carry `spec_version`, and CI
    validates real MapSmith output against the spec's own validator" — and the
    only manifest a reader sees under that sentence carried no `spec_version`,
    no `producer` and no `verification`. It was hand-written and had drifted for
    two releases while every generated surface stayed correct.

    Validated against the specification's own validator, vendored from the
    published repository rather than reimplemented here.
    """
    import importlib.util

    blocks = re.findall(r"```json\n(.*?)\n```", README.read_text(encoding="utf-8"), re.DOTALL)
    manifests = [
        json.loads(block)
        for block in blocks
        if '"operation"' in block and '"engine"' in block
    ]
    assert manifests, (
        "the README no longer shows a manifest, or the block stopped looking like "
        "one — this guard would then pass on a page with nothing to check"
    )

    spec = importlib.util.spec_from_file_location(
        "spec_validator", ROOT / "tests" / "data" / "manifest_spec_validator.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "tests" / "data" / "manifest-v1.schema.json").read_text(encoding="utf-8")
    )
    checker = jsonschema.Draft202012Validator(schema)
    for manifest in manifests:
        # BOTH implementations. The schema is the normative one, and a page that
        # says "conforming" on the strength of the lenient one of two is the
        # sentence a reader trusts — a `pipeline: null` divergence between them
        # was live when this test was written.
        problems = module.problems(manifest) + [
            error.message for error in checker.iter_errors(manifest)
        ]
        assert problems == [], (
            f"the manifest on the front page is not a conforming record: "
            f"{problems}. It is what an implementer copies."
        )
        # And it must be the version THIS code writes, which neither validator
        # can require: section 5 makes any `1.x.y` conforming on purpose, so
        # both implementations accept a label two drafts old and the check above
        # is structurally unable to fail on it. It sat at `draft.3` while the
        # emitter wrote `draft.5`, four lines under a sentence calling this
        # "the record a third-party implementer copies".
        from mapsmith.provenance import SPEC_VERSION

        assert manifest["spec_version"] == SPEC_VERSION, (
            f"the front-page record says spec_version {manifest['spec_version']} "
            f"and this build emits {SPEC_VERSION}; an implementer copying it "
            "writes records claiming a draft we no longer produce"
        )


def test_every_manifest_a_reader_can_see_obeys_the_key_rule():
    """D-077 on the surfaces, not only in the source.

    `test_every_crs_decisions_key_in_the_source_obeys_the_spec` sweeps the
    writing sites. It cannot see these: the record on the front page is typed
    by hand, and the ones in the gallery are frozen output from a run that has
    already happened. Both are what an implementer copies, and the two
    conformance guards beside this one cannot catch a wrong key, because the
    schema permits extra keys in `crs_decisions` on purpose — a record carrying
    `measurement_crs` validates against both implementations and is still the
    defect the Unreleased entry is about.

    The vocabulary is read from the vendored schema and the prefix predicate is
    shared with the runtime half, so one rule has one definition here too.
    """
    from conftest import _EXTENSION_KEY, _spec_crs_keys

    allowed = _spec_crs_keys()
    shown: list[tuple[str, dict]] = []
    for block in re.findall(r"```json\n(.*?)\n```", README.read_text(encoding="utf-8"), re.DOTALL):
        if '"operation"' in block and '"engine"' in block:
            shown.append(("README.md", json.loads(block)))
    for notebook in sorted((ROOT / "examples").glob("*.ipynb")):
        shown += [(notebook.name, m) for m in _manifests_shown_in(notebook)]

    # Positive first: a sweep over nothing is the shape of guard this file
    # keeps finding. Every surface named above has to produce a record with a
    # `crs_decisions` object, or the reader is being shown something else.
    with_decisions = [(where, m) for where, m in shown if m.get("crs_decisions")]
    assert with_decisions, (
        "no manifest with `crs_decisions` is visible on the README or in the "
        "gallery, so this test compared nothing. If a page stopped showing one, "
        "that is the finding."
    )
    for where, manifest in with_decisions:
        for key in manifest["crs_decisions"]:
            assert key in allowed or _EXTENSION_KEY.fullmatch(key), (
                f"{where} shows a manifest whose `crs_decisions` carries {key!r}, "
                f"which is neither a key section 3.7 recommends ({sorted(allowed)}) "
                "nor an extension named `x-mapsmith:<name>`. This is the record a "
                "third-party implementer copies, so a key here teaches the format "
                "wrongly. Re-run the notebook rather than editing its output."
            )


def test_the_front_page_record_carries_the_keys_the_operation_really_writes():
    """The two guards above cannot see a key that is MISSING.

    Both of them ask whether what is shown is permitted. Neither asks whether
    it is complete, and the schema permits an absent extension key by design —
    so a hand-typed record can quietly stop being the record the software
    writes, which is what happened twice. It lacked `spec_version` for two
    releases; and on 2026-09-06, the day `docs/manifest-vocabulary.md` was
    published to tell implementers that a metric operation on a geographic CRS
    records `x-mapsmith:round_trip`, the front page was still showing exactly
    that operation with no such key.

    So this one does not compare the page against a list. It RUNS the operation
    the page names, with the parameters the page shows, and compares the key
    set — the only version of this check that cannot itself go stale when the
    next extension key is added.
    """
    pytest.importorskip("geopandas")
    import tempfile

    blocks = re.findall(r"```json\n(.*?)\n```", README.read_text(encoding="utf-8"), re.DOTALL)
    shown = [
        json.loads(block)
        for block in blocks
        if '"operation"' in block and '"engine"' in block
    ]
    shown = [m for m in shown if m.get("operation") == "buffer_layer" and m.get("crs_decisions")]
    assert shown, (
        "the README no longer shows a `buffer_layer` record with `crs_decisions`. "
        "If the front page moved to another operation, point this test at it — "
        "do not delete it, or the page goes back to being unchecked."
    )

    import geopandas
    from shapely.geometry import LineString

    from mapsmith import server

    workspace = Path(tempfile.mkdtemp())
    source = workspace / "rivers.gpkg"
    geopandas.GeoDataFrame(
        {"id": [1]},
        geometry=[LineString([(9.0, 45.0), (9.01, 45.01)])],
        crs="EPSG:4326",
    ).to_file(source, driver="GPKG")

    import os

    previous = os.environ.get("MAPSMITH_WORKSPACE")
    os.environ["MAPSMITH_WORKSPACE"] = str(workspace)
    try:
        run = getattr(server.buffer_layer, "fn", server.buffer_layer)
        for manifest in shown:
            distance = manifest["parameters"]["distance_meters"]
            output = workspace / "out.gpkg"
            run(input_path=str(source), distance_meters=distance, output_path=str(output))
            emitted = json.loads(
                (workspace / "out.gpkg.provenance.json").read_text(encoding="utf-8")
            )
            # RECURSIVE, since 2026-09-07. It compared top-level keys only, and
            # on that day `x-mapsmith:round_trip` gained a sub-key and lost two:
            # this assertion would have stayed green with `applied_twice` still
            # on the front page and `return_transformation` missing from it.
            # A guard whose docstring says it exists because "a hand-typed
            # record can quietly stop being the record the software writes"
            # cannot stop at the first level of an object the software nests.
            def missing_paths(written, shown_here, prefix=""):
                gaps = []
                for key, value in written.items():
                    here = f"{prefix}{key}"
                    if key not in shown_here:
                        gaps.append(here)
                    elif isinstance(value, dict) and isinstance(shown_here[key], dict):
                        gaps += missing_paths(value, shown_here[key], f"{here}.")
                return gaps

            missing = missing_paths(emitted["crs_decisions"], manifest["crs_decisions"])
            assert not missing, (
                f"the record on the front page is missing {sorted(missing)} from "
                f"`crs_decisions`, which `buffer_layer` writes for this very call. "
                "It is typed by hand and it has drifted. Copy the emitted record "
                "rather than editing around the gap, and note the change in "
                "docs/manifest-vocabulary.md if the key is new."
            )
    finally:
        if previous is None:
            os.environ.pop("MAPSMITH_WORKSPACE", None)
        else:
            os.environ["MAPSMITH_WORKSPACE"] = previous


def test_the_published_doi_is_the_concept_doi():
    """Two DOIs exist per release and only one is safe to write down.

    Zenodo mints a version DOI for each release and one concept DOI that always
    resolves to the newest. A version DOI hard-coded into a file nobody
    re-reads becomes a citation for a superseded release the moment the next one
    lands. The sibling repositories carry the same guard, which is how this one
    came to be written before it was needed here.
    """
    yaml = pytest.importorskip("yaml")

    readme = README.read_text(encoding="utf-8")
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))

    # The PARSED `doi` field, not a grep of the file. The first version searched
    # the text, so deleting the `doi:` line left the test green because the
    # string still appeared in the `identifiers:` block below it — and the
    # converters that turn a CFF into archive metadata read `doi`, not
    # `identifiers`: with the field removed, the DOI vanishes from their output
    # entirely. Measuring something adjacent to the claim, in a test written to
    # stop exactly that.
    declared = citation.get("doi")
    assert declared, (
        "CITATION.cff has no `doi` field. An `identifiers:` entry alone does "
        "not reach the converters, so the DOI would disappear from the archive "
        "metadata while still appearing in the file."
    )

    in_readme = set(re.findall(r"10\.5281/zenodo\.(\d+)", readme))
    assert in_readme, "the README publishes no DOI of its own"
    assert declared.split(".")[-1] in in_readme, (
        f"CITATION.cff declares {declared} and the README cites "
        f"zenodo.{sorted(in_readme)}"
    )
    # One DOI in the citation file, and it must be the concept one: a version
    # DOI written here becomes a citation for a superseded release at the next
    # tag.
    everywhere = set(re.findall(r"10\.5281/zenodo\.(\d+)",
                               (ROOT / "CITATION.cff").read_text(encoding="utf-8")))
    assert everywhere == {declared.split(".")[-1]}, (
        f"CITATION.cff mentions more than one DOI: {sorted(everywhere)}"
    )


@pytest.mark.slow
def test_every_case_on_the_page_was_really_executed():
    """The steppable cases, run here, and checked for having anything in them.

    The page says of these cases that nothing is drawn and nothing is typed in.
    That sentence is worth exactly as much as this test: a case whose beats
    render empty looks identical to a case that ran, because the titles are
    written by hand and only the contents come from an execution.

    So each kind of beat is checked for the thing that could only come from a
    real run -- a narrowing from the catalogue, a refusal message from an
    engine, check counts from a manifest on disk, a chain recovered by walking
    digests. The analysis case is also required to REACH those beats: an
    exception on the third step would otherwise produce a short, tidy,
    completely honest-looking case.
    """
    import sys
    import tempfile

    sys.path.insert(0, str(ROOT / "benchmarks"))
    import playground

    with tempfile.TemporaryDirectory(prefix="mapsmith-cases-test-") as tmp:
        cases = playground.build(Path(tmp))["cases"]

    by_id = {case["id"]: case for case in cases}
    assert set(by_id) == {"analysis", "refusal"}, sorted(by_id)

    analysis = by_id["analysis"]
    kinds = [beat["kind"] for beat in analysis["beats"]]
    for required in ("question", "discovery", "refused", "ran", "answer", "lineage"):
        assert required in kinds, (
            f"the analysis case never reached a {required!r} beat, so the page "
            f"would render a shorter story than it claims: {kinds}"
        )

    narrowing = [b for b in analysis["beats"] if b["kind"] == "discovery"]
    assert len(narrowing) >= 3, len(narrowing)
    for beat in narrowing:
        assert beat["catalogue"] and beat["candidates"], beat
        assert beat["candidates"] < beat["catalogue"], (
            "a narrowing beat that narrows nothing is the page's own claim "
            f"failing quietly: {beat}"
        )

    ran = [b for b in analysis["beats"] if b["kind"] == "ran"]
    assert len(ran) >= 4, len(ran)
    for beat in ran:
        assert beat["checks_total"], f"{beat['title']} reports no checks at all"
        assert beat["checks_passed"] == beat["checks_total"], beat
        assert beat["engine"] and "None" not in str(beat["engine"]), beat

    walk = next(b for b in analysis["beats"] if b["kind"] == "lineage")
    assert len(walk["steps"]) == len(ran), (
        "the recovered chain has a different number of steps from the run that "
        f"produced it: {len(walk['steps'])} against {len(ran)}"
    )
    assert walk["verified"] is True, walk["summary"]
    assert all(step["claim"] == "reverified" for step in walk["steps"]), walk["steps"]

    refusal = by_id["refusal"]
    refused = [b for b in refusal["beats"] if b["kind"] == "refused"]
    assert refused, "the refusal case did not refuse, which is the whole case"
    message = refused[0]["message"]
    assert "georeferenced twice" in message, message
    # The local build directory must not reach the page, and neither must the
    # separator it was built with. Stripping the temporary directory and leaving
    # the slash behind made this block come out one way on Windows and another
    # on Linux, so the committed README and the CI run disagreed by one
    # character -- a build product that depends on its host, which is the defect
    # issue #30 removed from the manifests themselves.
    assert message.startswith("terrain.tif "), message
    assert "\\" not in message and "AppData" not in message, message
    inspected = next(b for b in refusal["beats"] if b["kind"] == "inspect")
    assert inspected["georeferencing"], (
        "the inspection beat is empty, so the page shows a file being examined "
        "and nothing being found"
    )


@pytest.mark.slow
def test_the_readme_cases_block_is_what_a_real_run_produces():
    """The block between the markers, regenerated and compared.

    The worked example above it has had this guard since 0.3.0, for a reason
    that applies here with more force: this block quotes an engine's refusal
    message verbatim and prints a chain recovered from digests. Both are the
    kind of text somebody tidies while editing the prose around it, and a
    tidied refusal message is a claim about what the software says that the
    software no longer says.

        python benchmarks/playground.py --write-readme
    """
    import sys
    import tempfile

    sys.path.insert(0, str(ROOT / "benchmarks"))
    import playground

    page = README.read_text(encoding="utf-8")
    assert playground.START in page and playground.END in page, (
        "the markers are gone from README.md, so nothing regenerates that block "
        "and nothing compares it with a run"
    )
    shown = page[page.index(playground.START): page.index(playground.END) + len(playground.END)]

    with tempfile.TemporaryDirectory(prefix="mapsmith-cases-readme-") as tmp:
        fresh = playground.markdown(playground.build(Path(tmp))["cases"])

    assert shown.strip() == fresh.strip(), (
        "the cases block in README.md is not what a run produces now. Run "
        "`python benchmarks/playground.py --write-readme` and read the diff "
        "before committing it: a difference here is either the software "
        "changing or the page having been edited by hand."
    )


def test_no_public_file_carries_a_mangled_character():
    """UTF-8 read as cp1252 and saved back, on a page somebody reads.

    Found on 2026-09-22 in the Argleton README, in the pasted terminal output
    of a run: three lines in which a plus-minus sign and two em dashes had each
    become a short run of Latin-1 punctuation. Public since the block was
    written, and invisible to every other guard there because the file parsed,
    the links resolved and the numbers were right. The engine blocks beside it
    were clean, which is the tell: only the lines carrying one of those two
    characters were touched, so the damage arrived through a console capture
    and not through an editor.

    The same guard runs in all three public repositories, because the way in
    is the same everywhere: a terminal on this machine, a copy, a paste.

    The markers are derived rather than listed -- each is what cp1252 makes of
    a character these repositories actually use. A hand-written list would be
    a finite map of the kind that has already gone stale here twice.
    """
    import subprocess

    damage = set()
    # Written as code points rather than typed: ruff rejects these characters
    # in a string literal as ambiguous, which they are -- that is the point of
    # them. Typing them would also put the damage this looks for into the file
    # that looks for it, which is how the first version of this test failed.
    suspect = "".join(chr(point) for point in (
        0x00B1, 0x2014, 0x2013, 0x2018, 0x2019, 0x201C, 0x201D,
        0x2026, 0x21D2, 0x00E8, 0x00E9, 0x00E0,
    ))
    for character in suspect:
        mangled = character.encode("utf-8").decode("cp1252", errors="replace")
        if chr(0xFFFD) not in mangled:
            damage.add(mangled)

    listed = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    damaged = []
    for name in listed:
        path = ROOT / name
        if path.resolve() == Path(__file__).resolve():
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if any(marker in line for marker in damage):
                damaged.append(f"{name}:{number}")
    assert not damaged, (
        "these tracked lines carry cp1252 mojibake, which means a character was "
        f"written once and saved twice: {damaged[:10]}"
    )
