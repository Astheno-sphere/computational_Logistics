"""The recorder must be invisible when off, honest when on, and never in the way.

Three properties, and the third is the one with teeth: this writes a file as a
side effect of a read-only tool, so every failure mode of the writing has to end
in the search still answering. A discovery log that can break discovery is worse
than no discovery log.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mapsmith import discovery_log


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Each test starts with an empty buffer and no memory of past paths.

    The module caches resolved destinations on purpose (the guard runs once per
    configuration), which means a test that changes the variable inherits the
    previous test's answer unless the cache is cleared here.
    """
    monkeypatch.delenv("MAPSMITH_DISCOVERY_LOG", raising=False)
    monkeypatch.delenv("MAPSMITH_WORKSPACE", raising=False)
    discovery_log._pending.clear()
    discovery_log._resolved.clear()
    yield
    discovery_log._pending.clear()
    discovery_log._resolved.clear()


def _search(query="where do these overlap", delivered=("clip_layer", "overlay_layers")):
    discovery_log.record_search(query, {"input_kind": "vector"}, "lexical", list(delivered), "choose")


def test_nothing_is_written_or_remembered_when_the_variable_is_unset(tmp_path):
    """Off is off: no file, and nothing accumulating in memory either.

    The second half matters as much as the first. A buffer that fills up on a
    long-running server whose operator never asked for a log is a leak, and an
    invisible one.
    """
    _search()
    discovery_log.record_run("clip_layer")
    assert discovery_log._pending == []
    assert list(tmp_path.iterdir()) == []


def test_a_search_and_the_run_that_follows_become_one_line(tmp_path, monkeypatch):
    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))

    _search("where do these two layers overlap")
    assert not log.exists(), "a search alone is buffered, not written"

    discovery_log.record_run("overlay_layers")
    record = json.loads(log.read_text(encoding="utf-8").strip())
    assert record["query"] == "where do these two layers overlap"
    assert record["declared"] == {"input_kind": "vector"}
    assert record["chose"] == "overlay_layers"
    assert record["position_of_choice"] == 2, "second of the two delivered"
    assert record["searches_ago"] == 0
    assert record["engine"] == "lexical"


def test_a_run_nobody_searched_for_is_not_attributed_to_a_search(tmp_path, monkeypatch):
    """The label has to come from a pairing, not from proximity.

    An agent that already knows the tool name calls it without searching. Making
    that a case would put a query in front of an operation nobody chose from it.
    """
    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))

    _search("where do these overlap", delivered=["clip_layer"])
    discovery_log.record_run("reproject_layer")

    assert not log.exists()
    assert discovery_log._pending[0]["chose"] is None


def test_a_search_nothing_followed_is_written_as_such(tmp_path, monkeypatch):
    """`chose: null` is data. It says the catalogue did not serve a request."""
    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))

    for index in range(discovery_log.WINDOW + 1):
        _search(f"request number {index}")

    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, "only the search pushed out of the window is written"
    evicted = json.loads(lines[0])
    assert evicted["query"] == "request number 0"
    assert evicted["chose"] is None


def test_flush_writes_what_is_still_buffered(tmp_path, monkeypatch):
    """Registered at exit, so a server that stops does not lose its last searches."""
    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))
    _search("one")
    _search("two")
    discovery_log.flush()
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 2
    assert discovery_log._pending == []


def test_a_path_outside_the_workspace_is_refused_and_the_search_still_answers(
    tmp_path, monkeypatch, capsys
):
    """The containment rule holds here too, and refusal is not an exception.

    A log path is an untrusted-ish string like any other — set by whoever
    launched the server, but pointing anywhere on the filesystem — so it goes
    through the same guard as a tool argument. What it must NOT do is propagate:
    `list_operations` is read-only and has to keep answering.
    """
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "elsewhere.jsonl"
    monkeypatch.setenv("MAPSMITH_WORKSPACE", str(workspace))
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(outside))

    assert discovery_log.destination() is None
    _search()
    discovery_log.record_run("clip_layer")

    assert not outside.exists()
    assert "will not write to" in capsys.readouterr().err

    inside = workspace / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(inside))
    _search()
    discovery_log.record_run("clip_layer")
    assert inside.exists(), "a path inside the workspace is accepted"


def test_a_broken_destination_does_not_reach_the_caller(tmp_path, monkeypatch):
    """Whatever the filesystem does, a search answers.

    A directory where a file should be is the cheapest way to make every write
    raise. Nothing here asserts a message: the contract is only that the calls
    return.
    """
    directory = tmp_path / "not-a-file.jsonl"
    directory.mkdir()
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(directory))

    for index in range(discovery_log.WINDOW + 2):
        _search(f"request {index}")
    discovery_log.record_run("clip_layer")
    discovery_log.flush()


def test_list_operations_records_what_it_delivered(tmp_path, monkeypatch):
    """The hook, through the real tool, on the real catalog.

    Unit tests of this module prove the recorder works; this proves it is
    connected, which is the part that silently stops being true.
    """
    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))
    from mapsmith import catalog, server

    answer = server.list_operations(
        query="reduce the number of vertices in these boundaries",
        input_kind="vector",
        dataset_inputs=1,
    )
    delivered = [entry["name"] for entry in catalog.entries(answer)]
    assert delivered, "the search returned nothing, so this proves nothing"

    discovery_log.flush()
    record = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["delivered"] == delivered
    assert record["declared"] == {"input_kind": "vector", "dataset_inputs": 1}
    assert record["status"] in ("ranked", "choose", "unsure")


def test_running_an_operation_by_name_records_that_operation(tmp_path, monkeypatch):
    """The by-name path logged the wrapper's name instead of the operation's.

    `run_operation` called `_run("run_operation", ...)`, and "run_operation" is
    not a name in the catalogue — so the row could never be paired with the
    search that led to it and came back `chose: null`. Forty-six operations of
    seventy-four are reachable only by name, so that was most of the log.

    The previous version of this test read `server.py` **as text** and asserted
    that one line was present. It passed for as long as the defect existed,
    because the line it looked for was the defective one — and it went red the
    moment the fix touched that line, which is the wrong thing for a test to
    notice. Same lesson as the georeferencing refusal that had no callers: a
    test that inspects a call site proves the call site exists and says nothing
    about what it does.
    """
    import json

    import geopandas as gpd
    from shapely.geometry import Point

    from mapsmith import server

    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))
    monkeypatch.setenv("MAPSMITH_WORKSPACE", str(tmp_path))

    source = tmp_path / "points.parquet"
    gpd.GeoDataFrame(
        {"i": [1, 2]},
        geometry=[Point(500000, 5000000), Point(500100, 5000100)],
        crs="EPSG:32632",
    ).to_parquet(source)

    # The search first, because the pairing IS the thing under test: a run is
    # attributed to the most recent search whose delivered set held it, so with
    # no search there is no row to complete and nothing is written at all.
    from mapsmith import catalog

    offered = server.list_operations(
        query="buffer points by a distance in metres",
        input_kind="vector",
        dataset_inputs=1,
    )
    delivered = [entry["name"] for entry in catalog.entries(offered)]
    assert "buffer_layer" in delivered, (
        f"the search did not offer buffer_layer ({delivered}), so this test would "
        "pass on an unpaired run"
    )

    server.run_operation(
        "buffer_layer",
        {
            "input_path": str(source),
            "distance_meters": 10.0,
            "output_path": str(tmp_path / "out.parquet"),
        },
    )

    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    chosen = [r.get("chose") for r in rows if r.get("chose")]
    assert "buffer_layer" in chosen, (
        f"the log recorded {chosen} — the operation that ran has to be the one "
        "written down, or the row cannot be paired with the search that led to it"
    )
    assert "run_operation" not in chosen, "the wrapper's name is not a catalogue name"


def test_the_environment_variable_is_documented(monkeypatch):
    """Off-by-default features that nobody can find are just dead code."""
    readme = Path(discovery_log.__file__).parents[2] / "README.md"
    assert "MAPSMITH_DISCOVERY_LOG" in readme.read_text(encoding="utf-8")


def test_the_log_holds_no_paths_only_the_query_and_the_names(tmp_path, monkeypatch):
    """A deliberate limit on what this collects.

    The record could carry the arguments an operation ran with, and that would
    make richer cases. It would also mean a file in the workspace accumulating
    every dataset path a caller touched, which is a different product with a
    different conversation attached. Queries and operation names, nothing else.
    """
    log = tmp_path / "discovery.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))
    _search()
    discovery_log.record_run("clip_layer")
    record = json.loads(log.read_text(encoding="utf-8").strip())
    assert set(record) == {
        "at",
        "query",
        "declared",
        "engine",
        "status",
        "delivered",
        "chose",
        "position_of_choice",
        "searches_ago",
        "matched_by",
    }


def test_the_recorder_survives_being_switched_on_mid_process(tmp_path, monkeypatch):
    """Nothing is cached that would keep it off after the variable appears.

    The resolved-destination cache is keyed on the raw value for this reason: a
    process that starts with the variable unset must start recording when it is
    set, not stay off because `None` got cached under the empty string.
    """
    assert discovery_log.destination() is None
    log = tmp_path / "late.jsonl"
    monkeypatch.setenv("MAPSMITH_DISCOVERY_LOG", str(log))
    assert discovery_log.destination() == log


def test_the_documentation_says_it_does_not_train_anything():
    """The one claim about this feature that must never quietly change.

    If a future version does learn from the log, this test fails and somebody
    has to delete the sentence deliberately — which is the moment to notice that
    the ranker would then be learning from an ordering it produced.
    """
    doc = discovery_log.__doc__ or ""
    assert "does not learn from them" in doc
    assert "benchmark" in doc


def test_the_variable_is_read_at_call_time_not_at_import_time():
    """Import order must not decide whether the feature works.

    A module-level read would freeze the answer at whatever the environment was
    when `mapsmith` was first imported, which on a server is before anything the
    operator does. The first line of this test used to also assert
    `... or True` — a tautology, the defect this project has now shipped twice —
    and ruff caught it, which is the argument for keeping SIM222 on.
    """
    source = Path(discovery_log.__file__).read_text(encoding="utf-8")
    body = source.split("def destination(", 1)[1]
    assert 'os.environ.get("MAPSMITH_DISCOVERY_LOG"' in body
