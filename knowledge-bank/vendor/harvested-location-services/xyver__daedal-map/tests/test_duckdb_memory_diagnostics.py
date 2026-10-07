from types import SimpleNamespace

from mapmover import duckdb_helpers as d


class FakeConnection:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.closed = False

    def execute(self, sql):
        assert sql == "SELECT * FROM duckdb_memory()"
        if self.error:
            raise self.error
        cursor = SimpleNamespace(description=[("tag",), ("memory_usage_bytes",), ("temporary_storage_bytes",)])
        cursor.fetchall = lambda: self.rows
        return cursor

    def close(self):
        self.closed = True


def setup_pool(monkeypatch, entries, *, created=None, generation=7):
    monkeypatch.setattr(d, "_QUERY_POOL", d.queue.LifoQueue(maxsize=16))
    monkeypatch.setattr(d, "_QUERY_POOL_GENERATION", generation)
    monkeypatch.setattr(d, "_QUERY_POOL_CREATED", created if created is not None else len(entries))
    monkeypatch.setattr(d, "_QUERY_POOL_ACTIVITY", {
        "active": 0, "active_high_water": 0, "acquisitions": 0,
        "releases": 0, "discards": 0, "wait_count": 0,
        "wait_seconds_total": 0.0, "wait_seconds_max": 0.0, "timeouts": 0,
    })
    for entry in entries:
        d._QUERY_POOL.put(entry)


def test_inspect_samples_idle_and_sums_memory(monkeypatch):
    first = FakeConnection([("buffer", 100, 4)])
    second = FakeConnection([("temp", 200, 30)])
    setup_pool(monkeypatch, [(first, 7), (second, 7)], created=4)
    report = d.inspect_query_pool_memory()
    assert report["created"] == 4
    assert report["idle"] == 2
    assert report["inuse_estimate"] == 2
    assert report["memory_usage_bytes"] == 300
    assert report["temporary_storage_bytes"] == 34
    assert len(report["details"]) == 2
    assert report["active_leases"] == 0
    assert d._QUERY_POOL.qsize() == 2


def test_stale_generation_is_discarded_and_errors_are_skipped(monkeypatch):
    stale = FakeConnection([("old", 9, 1)])
    broken = FakeConnection(error=RuntimeError("bad diagnostic query"))
    setup_pool(monkeypatch, [(stale, 6), (broken, 7)], created=2)
    report = d.inspect_query_pool_memory()
    assert report["skipped"] == 2
    assert report["sampled_idle"] == 0
    assert stale.closed
    assert d._QUERY_POOL.qsize() == 1


def test_pool_activity_tracks_high_water_without_diagnostic_leases(monkeypatch):
    first = FakeConnection()
    second = FakeConnection()
    setup_pool(monkeypatch, [(first, 7), (second, 7)])
    con1, generation1 = d._acquire_query_connection()
    con2, generation2 = d._acquire_query_connection()
    active = d.query_pool_activity_status()
    assert active["active"] == 2
    assert active["active_high_water"] == 2
    assert active["acquisitions"] == 2
    d._release_query_connection(con1, generation=generation1)
    d._release_query_connection(con2, generation=generation2)
    released = d.query_pool_activity_status()
    assert released["active"] == 0
    assert released["releases"] == 2
    d.inspect_query_pool_memory()
    assert d.query_pool_activity_status()["releases"] == 2
