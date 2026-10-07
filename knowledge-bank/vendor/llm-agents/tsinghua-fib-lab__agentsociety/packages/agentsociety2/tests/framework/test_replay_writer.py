import pytest

from agentsociety2.storage import ReplayWriter


@pytest.mark.asyncio
async def test_replay_writer_init_creates_replay_dir_for_legacy_db_path(tmp_path):
    db_path = tmp_path / "nested" / "sqlite.db"
    writer = ReplayWriter(db_path)
    await writer.init()
    assert db_path.with_suffix("").is_dir()
    await writer.close()


@pytest.mark.asyncio
async def test_replay_writer_close_idempotent(tmp_path):
    db_path = tmp_path / "sqlite.db"
    writer = ReplayWriter(db_path)
    await writer.init()
    await writer.close()
    await writer.close()


@pytest.mark.asyncio
async def test_replay_writer_legacy_db_path_writes_jsonl(tmp_path):
    db_path = tmp_path / "sqlite.db"
    writer = ReplayWriter(db_path)
    await writer.write("events", {"id": 1})
    await writer.close()
    replay_dir = db_path.with_suffix("")
    assert replay_dir.is_dir()
    assert list(replay_dir.glob("events.*.jsonl"))
