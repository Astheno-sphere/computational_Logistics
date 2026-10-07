import json
from datetime import datetime

import pytest

from agentsociety2.agent.base.todo import (
    MAX_TERMINAL_TODOS,
    TERMINAL_TODO_STATUSES,
    TODO_ARCHIVE_PATH,
    TODO_STATE_PATH,
    TodoStateStore,
)


def test_todo_state_initializes_empty_state(tmp_path):
    store = TodoStateStore(tmp_path)

    state = store.ensure()

    assert state == {
        "todos": [],
        "active_todo_id": None,
        "updated_at": state["updated_at"],
    }
    assert (tmp_path / TODO_STATE_PATH).exists()


def test_todo_state_adds_metadata_and_defaults(tmp_path):
    store = TodoStateStore(tmp_path)

    result = store.add(
        {
            "title": "go to work",
            "kind": "work",
            "priority": 1.5,
            "metadata": {"location": {"type": "aoi", "id": "work_aoi"}},
        }
    )

    todo = result["todo"]
    assert todo["title"] == "go to work"
    assert todo["priority"] == 1.0
    assert todo["metadata"]["location"]["id"] == "work_aoi"
    assert todo["status"] == "pending"


def test_todo_state_rejects_invalid_status_with_pydantic(tmp_path):
    store = TodoStateStore(tmp_path)

    with pytest.raises(ValueError, match="status"):
        store.add({"title": "bad status", "status": "unknown"})


def test_todo_state_rejects_invalid_due_with_pydantic(tmp_path):
    store = TodoStateStore(tmp_path)

    with pytest.raises(ValueError, match="ISO datetime"):
        store.add({"title": "bad due", "due": "tomorrow morning"})


def test_todo_state_start_enforces_single_active(tmp_path):
    store = TodoStateStore(tmp_path)
    first = store.add({"title": "first"})["todo"]
    second = store.add({"title": "second"})["todo"]

    store.start(first["id"])
    state = store.start(second["id"])["state"]

    assert state["active_todo_id"] == second["id"]
    statuses = {todo["id"]: todo["status"] for todo in state["todos"]}
    assert statuses[first["id"]] == "pending"
    assert statuses[second["id"]] == "active"


def test_todo_state_complete_clears_active(tmp_path):
    store = TodoStateStore(tmp_path)
    todo = store.add({"title": "finish me"})["todo"]
    store.start(todo["id"])

    state = store.complete(todo["id"], outcome="done well")["state"]

    assert state["active_todo_id"] is None
    finished = state["todos"][0]
    assert finished["status"] == "done"
    assert finished["notes"] == "done well"


def test_todo_state_defer_records_reason_and_new_due(tmp_path):
    store = TodoStateStore(tmp_path)
    todo = store.add({"title": "later"})["todo"]

    result = store.defer(todo["id"], new_due="2026-01-02T14:00:00", reason="busy")

    updated = result["todo"]
    assert updated["status"] == "deferred"
    assert updated["due"] == "2026-01-02T14:00:00"
    assert updated["blocking_reason"] == "busy"


def test_todo_state_prompt_context_selects_due_and_active(tmp_path):
    store = TodoStateStore(tmp_path)
    active = store.add({"title": "active", "due": "2026-01-02T09:00:00"})["todo"]
    store.add({"title": "soon", "priority": 0.9, "due": "2026-01-02T09:10:00"})
    store.add({"title": "later", "priority": 1.0, "due": "2026-01-02T12:00:00"})
    store.start(active["id"])

    context = store.build_prompt_context(datetime(2026, 1, 2, 9, 0, 0))

    assert context["active"]["id"] == active["id"]
    assert [todo["title"] for todo in context["due_now"]] == ["active", "soon"]
    assert "next_recommended" not in context


def test_todo_state_normalizes_missing_metadata_in_seed(tmp_path):
    path = tmp_path / TODO_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"todos":[{"id":"seed","title":"seeded","status":"pending"}],"active_todo_id":null}',
        encoding="utf-8",
    )

    state = TodoStateStore(tmp_path).ensure()

    assert state["todos"][0]["metadata"] == {}


def _add_and_complete(store, title):
    todo = store.add({"title": title})["todo"]
    return store.complete(todo["id"])["todo"]


def test_todo_state_auto_archives_overflow_terminal(tmp_path):
    store = TodoStateStore(tmp_path)
    overflow = 3
    total = MAX_TERMINAL_TODOS + overflow
    for index in range(total):
        _add_and_complete(store, f"task {index}")

    state = store.load()
    terminal = [t for t in state["todos"] if t["status"] in TERMINAL_TODO_STATUSES]
    assert len(terminal) == MAX_TERMINAL_TODOS

    archive_path = tmp_path / TODO_ARCHIVE_PATH
    assert archive_path.exists()
    archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
    assert len(archived) == overflow
    assert all("archived_at" in record for record in archived)
    archived_titles = {record["title"] for record in archived}
    assert archived_titles == {f"task {i}" for i in range(overflow)}


def test_todo_state_clear_completed_keeps_recent_and_preserves_active(tmp_path):
    store = TodoStateStore(tmp_path)
    for index in range(5):
        _add_and_complete(store, f"done {index}")
    active = store.add({"title": "still going"})["todo"]
    store.start(active["id"])

    result = store.clear_completed(keep_recent=2)

    state = result["state"]
    titles = {todo["title"] for todo in state["todos"]}
    # most recent two done items + the active item remain in the main list
    assert {"done 3", "done 4", "still going"} == titles
    assert result["archived"] == 3
    archive_path = tmp_path / TODO_ARCHIVE_PATH
    archived = [json.loads(line) for line in archive_path.read_text().splitlines() if line.strip()]
    assert {record["title"] for record in archived} == {"done 0", "done 1", "done 2"}


def test_todo_state_never_archives_in_progress_statuses(tmp_path):
    store = TodoStateStore(tmp_path)
    pending = store.add({"title": "pending"})["todo"]
    active = store.add({"title": "active"})["todo"]
    store.start(active["id"])
    deferred = store.defer(
        store.add({"title": "deferred"})["todo"]["id"], reason="waiting"
    )["todo"]
    blocked = store.update(
        store.add({"title": "blocked"})["todo"]["id"], {"status": "blocked"}
    )["todo"]
    # saturate with terminal todos so auto-archive fires on save
    for index in range(MAX_TERMINAL_TODOS + 2):
        _add_and_complete(store, f"done {index}")

    result = store.clear_completed(keep_recent=0)
    state = result["state"]
    ids_in_state = {todo["id"] for todo in state["todos"]}

    # every non-terminal item survives both auto-archive and the explicit clear
    assert {pending["id"], active["id"], deferred["id"], blocked["id"]} <= ids_in_state
    assert not any(
        todo["status"] in TERMINAL_TODO_STATUSES for todo in state["todos"]
    )
    assert state["active_todo_id"] == active["id"]
