import json
from unittest import mock

from mapmover import ops_feed_registry


def _registry(feed_id: str) -> dict:
    return {
        "schema_version": 1,
        "feeds": [
            {
                "feed_id": feed_id,
                "timeline": {
                    "provider": "saved_history",
                    "preload_history": False,
                },
            }
        ],
    }


def test_default_ops_registry_read_is_cached(tmp_path) -> None:
    path = tmp_path / "ops_feed_registry.json"
    path.write_text(json.dumps(_registry("first")), encoding="utf-8")
    ops_feed_registry.clear_ops_feed_registry_cache()

    with mock.patch.object(ops_feed_registry, "REGISTRY_PATH", path):
        first = ops_feed_registry.load_ops_feed_records()
        path.write_text(json.dumps(_registry("second")), encoding="utf-8")
        second = ops_feed_registry.load_ops_feed_records()

    assert first[0]["feed_id"] == "first"
    assert second is first
    ops_feed_registry.clear_ops_feed_registry_cache()


def test_explicit_registry_path_bypasses_process_cache(tmp_path) -> None:
    path = tmp_path / "ops_feed_registry.json"
    path.write_text(json.dumps(_registry("first")), encoding="utf-8")
    first = ops_feed_registry.load_ops_feed_records(path)
    path.write_text(json.dumps(_registry("second")), encoding="utf-8")
    second = ops_feed_registry.load_ops_feed_records(path)

    assert first[0]["feed_id"] == "first"
    assert second[0]["feed_id"] == "second"
