"""The page the project is watched from has to work with the network off.

It is generated from a checkout, opened from a file path, and it is the one
place where the answers come from a person rather than from a language model.
The properties asserted here are the ones that make it usable and honest: it
fetches nothing, it cannot be broken by the text of a query, it keeps apart the
three things a search can do, and the figures on it are the ones the report
computes rather than a second copy that drifts.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmarks"))

TRAP = """\
id         = "001-example"
population = "trap"
family     = "linear-units"
title      = "Coordinates in US survey feet used as if they were metres"
surface    = ["engine"]

[truth]
kind  = "scalar"
value = 1.0
"""


def fake_suite(root: Path) -> Path:
    """A minimal Argleton checkout: the layout, not the content.

    Built rather than borrowed because the real suite is a separate repository
    in a separate organisation and CI has no copy of it — which is exactly the
    situation the reader of this dashboard is in half the time.
    """
    (root / "traps" / "001-example").mkdir(parents=True)
    (root / "traps" / "001-example" / "probe.toml").write_text(TRAP, encoding="utf-8")
    run = root / "results" / "2026-01-01-fake"
    run.mkdir(parents=True)
    (root / "results" / "LATEST").write_text("2026-01-01-fake", encoding="utf-8")
    (run / "adapters-mapsmith.json").write_text(
        json.dumps(
            {
                "system": "MapSmith",
                "adapter": "adapters.mapsmith:Adapter",
                "silent_error_rate": 0.0,
                "completion_rate": 1.0,
                "traps_run": 1,
                "unsupported": 0,
                "verdict_counts": {"correct": 1},
                "by_family": {"linear-units": {"probes": 1, "silent_errors": 0}},
                "per_probe": [
                    {
                        "probe_id": "001-example",
                        "population": "trap",
                        "family": "linear-units",
                        "verdict": "correct",
                        "detail": "1.0",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return root


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One real build, log and suite included. Around six seconds, so built once."""
    import dashboard

    home = tmp_path_factory.mktemp("dashboard")
    log = home / "discovery.jsonl"
    log.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "at": "2026-08-29T06:39:04+00:00",
                    "query": "one label point per parcel </script><script>stolen()</script>",
                    "declared": {"input_kind": "vector", "dataset_inputs": 1},
                    "engine": "vector",
                    "status": "choose",
                    "delivered": ["point_on_surface", "centroid_layer"],
                    "chose": "centroid_layer",
                    "position_of_choice": 2,
                    "searches_ago": 0,
                },
                {
                    "at": "2026-08-29T06:40:00+00:00",
                    "query": "send this to my accountant",
                    "declared": {},
                    "engine": "vector",
                    "status": "unsure",
                    "delivered": [],
                    "chose": None,
                    "position_of_choice": None,
                    "searches_ago": None,
                },
            ]
        ),
        encoding="utf-8",
    )
    suite = fake_suite(home / "argleton")
    return dashboard.build(log, suite, home / "history.json")


def embedded(page: str) -> dict:
    """The data blob the page draws itself from."""
    match = re.search(
        r'<script type="application/json" id="data">(.*?)</script>', page, re.DOTALL
    )
    assert match, "the page no longer carries its data as JSON"
    return json.loads(match.group(1))


def test_the_page_fetches_nothing(built):
    """No CDN, no font host, no analytics, no chart library — it has to work on a plane.

    Also the reason it is one file: a page whose stylesheet lives next to it is
    a page that arrives broken when somebody sends only the page.
    """
    for attribute in ("src", "href"):
        for value in re.findall(rf'{attribute}="([^"]+)"', built):
            assert value.startswith("#") or not value.startswith(
                ("http://", "https://", "//")
            ), (
                f"the page loads {value} from the network, so it stops working offline "
                "and tells a third party when it is opened"
            )
    assert "@import" not in built


def test_a_query_cannot_break_out_of_the_data_block(built):
    """Queries are text somebody else wrote. Here that text becomes a page."""
    data = embedded(built)
    assert any("stolen()" in case["query"] for case in data["recorded"]), (
        "the fixture query is gone, so this test is no longer testing anything"
    )
    block = re.search(
        r'<script type="application/json" id="data">(.*?)</script>', built, re.DOTALL
    ).group(1)
    assert "</script>" not in block


def test_the_three_things_a_search_can_do_are_kept_apart(built):
    """The first thing this page got wrong about itself.

    A search can rank the entry somewhere, answer without it, or decline to
    answer at all because the two rankers shared nothing (`unsure`). Collapsing
    the third into the second drew ten operations as broken when the entries
    were fine and the refusal gate had fired — a page inventing defects is
    worse than no page.
    """
    data = embedded(built)
    shapes = {
        result["shape"]
        for op in data["operations"]
        for engine in op["probes"].values()
        for result in engine.values()
    }
    assert shapes <= {"ranked", "choose", "unsure", "none_apply"}
    for op in data["operations"]:
        for engine in op["probes"].values():
            for result in engine.values():
                assert "rank" in result and "shape" in result and "pool" in result

    body = built.split("function rankCell(", 1)[1].split("\n}", 1)[0]
    for shape in ("unsure", "none_apply"):
        assert shape in body, (
            f"the page no longer distinguishes {shape!r} when drawing a rank, so a "
            "search that declined is drawn as an operation nobody can find"
        )


def test_every_operation_is_probed_twice_and_the_facets_are_the_ones_a_caller_knows(built):
    """Words alone and with facets, because they answer different questions.

    Words alone says whether the entry's text carries its own meaning; with
    facets is the case that actually happens. The family is deliberately not
    declared: it is the one facet that is a guess about our taxonomy, and
    `search` orders on it rather than filtering.
    """
    import dashboard

    data = embedded(built)
    assert "category" not in dashboard.DECLARED
    for op in data["operations"]:
        for engine in op["probes"].values():
            assert set(engine) == {"bare", "faceted"}
        assert set(op["declared"]) <= {"input_kind", "produces", "dataset_inputs"}


def test_the_figures_on_the_page_are_the_ones_the_report_computes(built):
    """Two places publishing the same number is two places to be wrong in."""
    import discovery_report

    data = embedded(built)
    queries = discovery_report.load()
    quality = data["quality"]
    assert quality["agreement_all"] == list(discovery_report.agreement(queries)["all"])
    assert quality["answerable"] == len(discovery_report.answerable(queries))
    assert quality["ablation_lexical"] == discovery_report.ablation(
        discovery_report.answerable(queries), engine="lexical"
    )


def test_the_split_rows_are_the_ones_the_labellers_disagreed_on(built):
    """The panel's whole job: the requests where the ground truth is a guess."""
    data = embedded(built)
    split = data["disagreements"]
    assert split, "no disagreements, so the page has nothing for a person to settle"
    for row in split:
        assert row["claude"] != row["gemini"] and row["claude"] and row["gemini"]
    same, both = data["quality"]["agreement_all"]
    assert len(split) == both - same, (
        f"{len(split)} split rows against {both - same} the report counts as "
        "disagreements — the page and the report are looking at different sets"
    )


def test_the_suite_panel_reads_a_checkout_when_it_has_one(built):
    """Traps, families and per-probe verdicts, from the layout of a real run."""
    data = embedded(built)
    suite = data["argleton"]
    assert suite["source"] == "checkout"
    assert suite["traps"][0]["title"], "a trap without its title is an id in a table"
    assert suite["adapters"][0]["name"] == "mapsmith", (
        "the short name must come from the file, not from the adapter field: "
        "MapSmith's is an import path and it read as 'adapters.mapsmith:Adapter'"
    )
    assert suite["adapters"][0]["by_family"]


def test_without_a_checkout_it_says_which_numbers_it_is_showing():
    """Degrading is fine. Degrading quietly is not.

    Most readers have no copy of the suite: it is a separate repository in a
    separate organisation on purpose. The vendored citation carries the run's
    headline figures and nothing per-family, and the page has to say so rather
    than draw an empty table.
    """
    import dashboard

    fallback = dashboard.argleton(None)
    assert fallback["source"] == "vendored citation"
    assert fallback["traps_run"] and fallback["families"]
    assert fallback["adapters"] == [] and fallback["traps"] == []


def test_the_trend_appends_and_refuses_to_manufacture_one(tmp_path):
    """A series is the point; five identical rows from five rebuilds are not."""
    import dashboard

    path = tmp_path / "history.json"
    first = {"at": "2026-01-01T00:00:00+00:00", "operations": 61, "tools": 28}
    same = {"at": "2026-01-02T00:00:00+00:00", "operations": 61, "tools": 28}
    grown = {"at": "2026-01-03T00:00:00+00:00", "operations": 62, "tools": 28}

    assert len(dashboard.history(path, first)) == 1
    assert len(dashboard.history(path, same)) == 1, (
        "an unchanged rebuild added a row, so the trend line will show movement "
        "that is only the number of times somebody ran the command"
    )
    assert len(dashboard.history(path, grown)) == 2
    assert json.loads(path.read_text(encoding="utf-8"))[-1]["operations"] == 62


def test_an_answer_is_stored_against_the_question_text_and_nothing_else(built):
    """The property that makes regenerating the page safe.

    The page is a snapshot. Adding an operation or a trap means building it
    again, and somebody who has answered forty questions must not lose them —
    or worse, keep them attached to the wrong questions. A key built from a
    position would do exactly that, silently.
    """
    body = built.split("function keyFor(", 1)[1].split("\n}", 1)[0]
    assert "row.query" in body
    for forbidden in ("index", "[i]", "position"):
        assert forbidden not in body, (
            f"the answer key involves {forbidden!r}, which changes when the "
            "catalogue or the request set grows"
        )
    assert built.count("keyFor(") >= 6, (
        "some panel builds its own key instead of calling keyFor, which is how "
        "the halves drift apart"
    )


def test_the_page_says_what_it_is_and_how_to_rebuild_it(built):
    """A generated page that does not say it is generated ages into a lie."""
    assert "snapshot" in built.lower()
    assert "python benchmarks/dashboard.py" in built
    assert "nothing is uploaded" in built.lower()
    assert "localStorage" in built


def test_every_operation_is_reachable_in_the_picker(built):
    """A chip list is a shortcut; the answer might be none of the shortcuts.

    If the full catalogue is not in the page, an honest answer outside the
    ranked ten cannot be given at all — which would bend the labels toward what
    the ranker already believes.
    """
    from mapsmith import catalog

    data = embedded(built)
    assert {op["name"] for op in data["catalog"]} == {
        op["name"] for op in catalog.OPERATIONS
    }
    assert all(op["summary"] for op in data["catalog"])
